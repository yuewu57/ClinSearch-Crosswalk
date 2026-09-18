"""Build a compact, descriptor-complete MeSH 2026 exact-resolution snapshot.

Inputs are already downloaded and SHA-256-locked NLM production-year XML.
No live lookup, fuzzy mapping, benchmark-specific correction or source editing.
SCR XML is used only to establish direct pharmacological-action targets.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ovid_pubmed_converter.engine import (  # noqa: E402
    HISTORICAL_MESH_ALIASES,
    _mesh_cache_key,
    normalize_mesh_lookup_label,
)

YEAR = 2026
KIND = 'nlm-mesh-descriptor-exact-index'
CLASSES = {'1': 'TopicalDescriptor', '2': 'PublicationType',
           '3': 'CheckTag', '4': 'GeographicalDescriptor'}
REFERENCE = '8ca2ca49984d13e46612332964f3131e49ee64'
# Record the actual immutable reference without relying on filesystem Git state.
REFERENCE = '8ca2ca49984d13e466ae12332964f3131e49ee64'
BASE_NAME = 'mesh2026_descriptor_snapshot_v1_YW_18092026'
DESCRIPTOR_ID = re.compile(r'D(?:\d{6}|\d{9})\Z')


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def stable_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(',', ':'), allow_nan=False) + '\n').encode('utf-8')


def records(path: Path, record_tag: str, root_tag: str):
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rb') as f:
        prefix = f.read(8192)
    if b'20260101' not in prefix or b'<!ENTITY' in prefix:
        raise ValueError(f'{path.name}: missing 2026 production DTD or unexpected entity')
    with opener(path, 'rb') as f:
        events = ET.iterparse(f, events=('start', 'end'))
        _, root = next(events)
        if root.tag != root_tag:
            raise ValueError(f'{path.name}: unexpected XML root {root.tag}')
        for event, item in events:
            if event == 'end' and item.tag == record_tag:
                yield item
                item.clear()
                root.clear()


def text(item: ET.Element, path: str) -> str:
    value = item.findtext(path)
    if value is None or not value.strip():
        raise ValueError(f'missing required field {path}')
    return value.strip()


def pa_ids(item: ET.Element) -> set[str]:
    return {text(pa, 'DescriptorReferredTo/DescriptorUI') for pa in
            item.findall('PharmacologicalActionList/PharmacologicalAction')}


def resolve(snapshot: dict, label: str) -> dict:
    """Independent data adapter; same preferred/entry/approved-alias policy."""
    key = _mesh_cache_key(label)
    lookup = HISTORICAL_MESH_ALIASES.get(key, label)
    target = _mesh_cache_key(lookup)
    preferred = snapshot['preferred'].get(target, [])
    candidates = preferred or snapshot['entry'].get(target, [])
    if not candidates:
        return {'status': 'unresolved', 'reason': 'no_exact_preferred_or_entry_match'}
    if len(candidates) != 1:
        return {'status': 'ambiguous', 'reason': 'multiple_exact_descriptor_matches' if preferred else 'entry_term_maps_to_multiple_descriptors',
                'candidate_uris': ['http://id.nlm.nih.gov/mesh/' + ui for ui in candidates]}
    ui = candidates[0]
    name, cls, pa = snapshot['descriptors'][ui]
    return {'status': 'resolved', 'source_label': normalize_mesh_lookup_label(label),
            'matched_label': normalize_mesh_lookup_label(lookup),
            'match_type': 'historical' if key in HISTORICAL_MESH_ALIASES else ('preferred' if preferred else 'entry'),
            'canonical_label': name, 'descriptor_id': ui,
            'descriptor_uri': 'http://id.nlm.nih.gov/mesh/' + ui,
            'record_class': cls, 'is_pharmacological_action': pa, 'mesh_year': YEAR}


def build(source_dir: Path, output_dir: Path, evaluation_cache: Path) -> dict:
    lock_path = source_dir / 'acquisition_provenance_v1_YW_18092026.json'
    lock = json.loads(lock_path.read_text(encoding='utf-8'))
    if lock.get('requested_mesh_year') != YEAR:
        raise ValueError('source lock must identify MeSH 2026')
    required = {'desc2026.xml.gz', 'supp2026.xml.gz', 'qual2026.xml'}
    locked = {s['filename']: s for s in lock['sources']}
    if not required <= locked.keys():
        raise ValueError('source lock omits required files')
    for source in locked.values():
        path = source_dir / source['filename']
        if path.name != source['filename'] or sha256(path) != source['sha256']:
            raise ValueError(f'source hash mismatch: {path.name}')
        if path.stat().st_size != source['bytes']:
            raise ValueError(f'source size mismatch: {path.name}')
    before = sha256(evaluation_cache)
    old = json.loads(evaluation_cache.read_text(encoding='utf-8'))
    if old.get('schema_version') != 1 or len(old.get('records', {})) != 620:
        raise ValueError('expected the unchanged 620-record evaluation cache')

    descriptors = {}
    preferred = defaultdict(set)
    entry = defaultdict(set)
    direct_d = set()
    term_count = 0
    for item in records(source_dir / 'desc2026.xml.gz', 'DescriptorRecord', 'DescriptorRecordSet'):
        ui = text(item, 'DescriptorUI')
        name = text(item, 'DescriptorName/String')
        cls = CLASSES.get(item.get('DescriptorClass'))
        if not DESCRIPTOR_ID.fullmatch(ui) or ui in descriptors or cls is None:
            raise ValueError(f'invalid/duplicate descriptor or class: {ui}')
        descriptors[ui] = [name, cls, False]
        preferred[_mesh_cache_key(name)].add(ui)
        terms = item.findall('ConceptList/Concept/TermList/Term/String')
        if not terms:
            raise ValueError(f'descriptor has no terms: {ui}')
        for term in terms:
            if not term.text or not term.text.strip():
                raise ValueError(f'empty term: {ui}')
            entry[_mesh_cache_key(term.text)].add(ui)
            term_count += 1
        direct_d.update(pa_ids(item))
    if len(descriptors) != lock['parsed']['desc2026.xml.gz']['record_count'] or len(descriptors) < 30000:
        raise ValueError('descriptor completeness check failed')

    direct_s = set()
    scr_count = 0
    for item in records(source_dir / 'supp2026.xml.gz', 'SupplementalRecord', 'SupplementalRecordSet'):
        scr_count += 1
        direct_s.update(pa_ids(item))
    if scr_count != lock['parsed']['supp2026.xml.gz']['record_count']:
        raise ValueError('SCR completeness check failed')
    targets = direct_d | direct_s
    if targets - descriptors.keys():
        raise ValueError(f'PA targets absent from descriptors: {sorted(targets - descriptors.keys())}')
    for ui in targets:
        descriptors[ui][2] = True

    snapshot = {
        'schema_version': 2, 'kind': KIND, 'snapshot_id': BASE_NAME, 'mesh_year': YEAR,
        'source': 'NLM MeSH 2026 production XML; direct PA links from Descriptor and SCR XML',
        'frozen_at_utc': max(s['downloaded_at_utc'] for s in locked.values()),
        'normalization': 'Reference _mesh_cache_key: typography, whitespace, casefold; no word deletion, stemming or fuzzy matching',
        'reference_engine_commit': REFERENCE,
        'historical_aliases': HISTORICAL_MESH_ALIASES,
        'descriptors': dict(sorted(descriptors.items())),
        'preferred': {key: sorted(values) for key, values in sorted(preferred.items())},
        'entry': {key: sorted(values) for key, values in sorted(entry.items())},
        'coverage': 'All 2026 Descriptor records and their TermList strings. SCR names and qualifier resolution are not substituted into descriptor queries.',
        'attribution': 'Courtesy of the U.S. National Library of Medicine. NLM does not endorse this application.',
        'currency_notice': 'Frozen historical snapshot; not a claim to reflect the most current or accurate NLM data.',
    }
    for key, target_label in HISTORICAL_MESH_ALIASES.items():
        if resolve(snapshot, key)['status'] != 'resolved':
            raise ValueError(f'approved historical alias did not resolve: {key} => {target_label}')

    comparison = {'equivalent_metadata': 0, 'different_metadata': [], 'unresolved': []}
    fields = ('descriptor_id', 'canonical_label', 'record_class', 'is_pharmacological_action')
    for key, record in sorted(old['records'].items()):
        new = resolve(snapshot, key)
        if new['status'] != 'resolved':
            comparison['unresolved'].append({'key': key, 'snapshot': new, 'evaluation': record})
        elif all(new.get(k) == record.get(k) for k in fields):
            comparison['equivalent_metadata'] += 1
        else:
            comparison['different_metadata'].append({'key': key, 'evaluation': {k: record.get(k) for k in fields}, 'snapshot': {k: new.get(k) for k in fields}})
    probes = ['Physical Therapy Techniques', 'Patient Education', 'Electrical Stimulation',
              'Anal Canal and Neoplasms', 'Card iac Output', 'Bladder, Neurogenic',
              'Telepsychiatry', 'Cell Phones', 'Respiration Artificial',
              'Occupational Therapist', 'Physical Therapist', 'Speech Therapist']
    stats = {
        'descriptors': len(descriptors), 'descriptor_classes': dict(Counter(v[1] for v in descriptors.values())),
        'descriptor_term_occurrences': term_count,
        'preferred_keys': len(preferred), 'entry_keys': len(entry),
        'unique_lookup_keys': len(set(preferred) | set(entry)),
        'ambiguous_preferred_keys': sum(len(v) > 1 for v in preferred.values()),
        'ambiguous_entry_keys': sum(len(v) > 1 and k not in preferred for k, v in entry.items()),
        'scr_records_scanned_for_direct_pa': scr_count,
        'direct_pa_targets_from_descriptors': len(direct_d),
        'direct_pa_targets_from_scrs': len(direct_s),
        'direct_pa_targets_union': len(targets),
        'approved_historical_aliases': len(HISTORICAL_MESH_ALIASES),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = stable_json(snapshot)
    output = output_dir / (BASE_NAME + '.json')
    output.write_bytes(payload)
    # Explicit browser-friendly compact index; gzip artifact for distribution.
    with (output_dir / (BASE_NAME + '.json.gz')).open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=9) as gz:
            gz.write(payload)
    manifest = {
        'snapshot_id': BASE_NAME, 'mesh_year': YEAR, 'frozen_at_utc': snapshot['frozen_at_utc'],
        'snapshot_sha256': sha256(output), 'snapshot_bytes': len(payload),
        'snapshot_gzip_sha256': sha256(output_dir / (BASE_NAME + '.json.gz')),
        'snapshot_gzip_bytes': (output_dir / (BASE_NAME + '.json.gz')).stat().st_size,
        'source_acquisition': lock, 'statistics': stats,
        'builder_sha256': sha256(Path(__file__)),
        'reference_engine_commit': REFERENCE,
        'evaluation_cache': {'filename': evaluation_cache.name, 'sha256': before, 'records': 620, 'unchanged': before == sha256(evaluation_cache)},
        'evaluation_cache_comparison': comparison,
        'previous_unresolved_probe_results': {label: resolve(snapshot, label) for label in probes},
        'scope': snapshot['coverage'],
        'pa_policy': 'Direct PharmacologicalActionList targets across desc2026 and supp2026; do not use pa2026 ancestor-expanded grouping file.',
        'not_proven': ['Historical benchmark terminology configuration equivalence', 'PubMed/Ovid retrieval equivalence', 'Coverage of every historical, malformed, SCR or qualifier input'],
    }
    (output_dir / ('mesh2026_snapshot_manifest_v1_YW_18092026.json')).write_bytes(stable_json(manifest))
    print(json.dumps({k: manifest[k] for k in ['snapshot_id', 'snapshot_sha256', 'snapshot_bytes', 'snapshot_gzip_bytes', 'statistics', 'evaluation_cache', 'evaluation_cache_comparison', 'previous_unresolved_probe_results']}, indent=2))
    if before != sha256(evaluation_cache):
        raise ValueError('evaluation cache changed unexpectedly')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--evaluation-cache', type=Path, default=ROOT / 'resources/mesh_resolution_cache_v20_v1_YW_18092026.json')
    args = parser.parse_args()
    build(args.source_dir, args.output_dir, args.evaluation_cache)


if __name__ == '__main__':
    main()

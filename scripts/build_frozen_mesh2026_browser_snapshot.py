"""Build the frozen MeSH 2026 browser snapshot from official NLM XML.

This deployment helper deliberately reconstructs the already-reviewed compact
snapshot and refuses to emit anything unless both NLM source hashes and the
final snapshot hash match the frozen provenance constants.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

PREFIX = "https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/"
SOURCES = {
    "desc2026.gz": {
        "sha256": "ccd4d0d33bebfd4c836a59e7dd0c635b1d4e20c4f5a6abc55e2eb0ba4c8716dd",
        "bytes": 16812612,
    },
    "supp2026.gz": {
        "sha256": "5d487dbb55807724465065f5c0945c630290a0a6decee14618f5380c574d87ab",
        "bytes": 47287269,
    },
}
EXPECTED_SNAPSHOT_SHA256 = "7ebdeba5e6c6d09b154e053e57777d746b51939a50bad8deac5b14bd07c7a6da"
EXPECTED_SNAPSHOT_BYTES = 12222418
EXPECTED_EVALUATION_CACHE_CANONICAL_SHA256 = "34467e3deb46ec6a6709ad0123bf86f7d637aaec091e2a149437c03770b71caf"
EXPECTED_ENGINE_SHA256 = "004ba1b5001cff625ccc1e5d703adf56b2312d7510370327e2514c6070b84348"
YEAR = 2026


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_sha256(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return sha256_bytes(raw)


def check_xml_header(prefix: bytes) -> None:
    if b"<!ENTITY" in prefix or re.search(br"<!DOCTYPE[^>]*\[", prefix):
        raise ValueError("Internal DTD/entity declarations are not accepted")
    if not re.search(br"recordset_20260101\.dtd", prefix):
        raise ValueError("Source does not declare the expected MeSH 2026 DTD")


def download(path: Path, name: str) -> None:
    expected = SOURCES[name]
    if path.exists():
        if path.stat().st_size == expected["bytes"] and sha256_file(path) == expected["sha256"]:
            print(f"[REUSE] {name}: frozen SHA-256 verified", flush=True)
            return
        raise ValueError(f"Existing {name} does not match the frozen source")
    url = PREFIX + name
    path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        temporary = None
        try:
            print(f"[DOWNLOAD] {url} (attempt {attempt + 1}/4)", flush=True)
            request = Request(
                url,
                headers={
                    "User-Agent": "ClinSearch-CrossWalk-MeSH2026-frozen-browser/1.0",
                    "Accept-Encoding": "identity",
                },
            )
            with urlopen(request, timeout=90) as response:
                final = urlparse(response.geturl())
                original = urlparse(url)
                if (
                    final.scheme != "https"
                    or final.hostname not in {"nlmpubs.nlm.nih.gov", "ftp.nlm.nih.gov"}
                    or final.path != original.path
                ):
                    raise ValueError(f"Unexpected NLM redirect: {response.geturl()}")
                h = hashlib.sha256()
                size = 0
                with tempfile.NamedTemporaryFile(
                    mode="wb", dir=path.parent, prefix=name + ".", delete=False
                ) as out:
                    temporary = Path(out.name)
                    while chunk := response.read(1024 * 1024):
                        out.write(chunk)
                        h.update(chunk)
                        size += len(chunk)
                        if size > 2 * 1024**3:
                            raise ValueError("Source exceeded 2 GiB safety bound")
            if size != expected["bytes"] or h.hexdigest() != expected["sha256"]:
                raise ValueError(f"{name} differs from the frozen NLM source")
            with gzip.open(temporary, "rb") as stream:
                check_xml_header(stream.read(32768))
            os.replace(temporary, path)
            return
        except (OSError, ValueError, EOFError) as exc:
            if temporary is not None and temporary.exists():
                temporary.unlink()
            if attempt == 3:
                raise RuntimeError(f"Unable to acquire frozen {name}: {exc}") from exc
            time.sleep(2**attempt)


def iter_records(path: Path, root_name: str, record_name: str):
    with gzip.open(path, "rb") as stream:
        prefix = stream.read(32768)
        check_xml_header(prefix)
        stream.seek(0)
        context = ET.iterparse(stream, events=("start", "end"))
        event, root = next(context)
        if event != "start" or root.tag != root_name:
            raise ValueError(f"Unexpected XML root {root.tag!r}")
        if root.attrib.get("LanguageCode", "eng") != "eng":
            raise ValueError("Expected English MeSH")
        for event, elem in context:
            if event == "end" and elem.tag == record_name:
                yield elem
                root.clear()


def build(repo: Path, source_dir: Path) -> bytes:
    import sys
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo / "browser/python"))
    from mesh_snapshot_resolver_v1_YW_18092026 import CLASSES, KIND, UID, validate_snapshot

    from ovid_pubmed_converter import engine

    engine_bytes = (
        (repo / "src/ovid_pubmed_converter/engine.py")
        .read_text(encoding="utf-8")
        .replace("\r\n", "\n")
        .encode("utf-8")
    )
    if sha256_bytes(engine_bytes) != EXPECTED_ENGINE_SHA256:
        raise ValueError("Reference engine differs from frozen snapshot provenance")

    evaluation_cache = repo / "resources/mesh_resolution_cache_v20_v1_YW_18092026.json"
    if canonical_json_sha256(evaluation_cache) != EXPECTED_EVALUATION_CACHE_CANONICAL_SHA256:
        raise ValueError("The 620-record evaluation cache changed semantically")

    descriptors: dict[str, list] = {}
    preferred = defaultdict(set)
    terms = defaultdict(set)
    pa_desc: set[str] = set()
    pa_scr: set[str] = set()
    classes = Counter()
    term_occurrences = 0

    for record in iter_records(source_dir / "desc2026.gz", "DescriptorRecordSet", "DescriptorRecord"):
        ui = record.findtext("DescriptorUI")
        label = record.findtext("DescriptorName/String")
        cls = record.attrib.get("DescriptorClass", "1")
        if not ui or not UID.fullmatch(ui) or not label or cls not in CLASSES:
            raise ValueError(f"Malformed or unsupported descriptor {ui!r}")
        if ui in descriptors:
            raise ValueError(f"Duplicate descriptor {ui}")
        descriptors[ui] = [label, cls, False]
        classes[CLASSES[cls]] += 1
        preferred[engine._mesh_cache_key(label)].add(ui)
        found = record.findall("ConceptList/Concept/TermList/Term/String")
        if not found:
            raise ValueError(f"Descriptor {ui} has no Term strings")
        own = set()
        for element in found:
            if not element.text or not element.text.strip():
                raise ValueError(f"Empty Term string in {ui}")
            key = engine._mesh_cache_key(element.text)
            terms[key].add(ui)
            own.add(key)
            term_occurrences += 1
        if engine._mesh_cache_key(label) not in own:
            raise ValueError(f"Preferred label absent from TermList for {ui}")
        for element in record.findall(
            "PharmacologicalActionList/PharmacologicalAction/"
            "DescriptorReferredTo/DescriptorUI"
        ):
            pa_desc.add(element.text)

    supplementary_records = 0
    seen_scr = set()
    for record in iter_records(source_dir / "supp2026.gz", "SupplementalRecordSet", "SupplementalRecord"):
        ui = record.findtext("SupplementalRecordUI")
        if not ui or not re.fullmatch(r"C\d+", ui) or ui in seen_scr:
            raise ValueError(f"Invalid or duplicate supplementary record {ui!r}")
        seen_scr.add(ui)
        supplementary_records += 1
        for element in record.findall(
            "PharmacologicalActionList/PharmacologicalAction/"
            "DescriptorReferredTo/DescriptorUI"
        ):
            pa_scr.add(element.text)

    pa_targets = pa_desc | pa_scr
    dangling = sorted(pa_targets - descriptors.keys())
    if dangling:
        raise ValueError(f"PA targets absent from descriptors: {dangling[:20]}")
    for ui in pa_targets:
        descriptors[ui][2] = True

    aliases = {}
    for key, target in engine.HISTORICAL_MESH_ALIASES.items():
        target_key = engine._mesh_cache_key(target)
        if len(preferred.get(target_key, [])) != 1:
            raise ValueError(f"Historical alias target is not unique: {target}")
        aliases[engine._mesh_cache_key(key)] = target

    payload = {
        "schema_version": 2,
        "kind": KIND,
        "mesh_year": YEAR,
        "source": "NLM MeSH 2026 Descriptor XML; direct PA targets from Descriptor and SCR XML",
        "scope": "complete-current-descriptors-and-exact-Term-labels",
        "normalization": "reference _mesh_cache_key; typography/whitespace/case only",
        "attribution": "Courtesy of the U.S. National Library of Medicine",
        "frozen_data_notice": (
            "Frozen MeSH 2026 snapshot, not automatically updated; it may not reflect "
            "the latest NLM data. NLM does not endorse this application."
        ),
        "descriptors": dict(sorted(descriptors.items())),
        "preferred": {k: sorted(v) for k, v in sorted(preferred.items())},
        "terms": {k: sorted(v) for k, v in sorted(terms.items())},
        "project_aliases": dict(sorted(aliases.items())),
    }
    counts = validate_snapshot(payload)
    counts.update(
        {
            "descriptor_classes": dict(sorted(classes.items())),
            "descriptor_Term_occurrences": term_occurrences,
            "supplementary_records_scanned_for_PA": supplementary_records,
            "direct_PA_targets_from_descriptors": len(pa_desc),
            "direct_PA_targets_from_SCRs": len(pa_scr),
            "PA_targets_found_only_in_SCRs": len(pa_scr - pa_desc),
            "entry_keys_shadowed_by_preferred_label_priority": sum(
                key in preferred and bool(candidates - preferred[key])
                for key, candidates in terms.items()
            ),
        }
    )
    payload["counts"] = counts
    payload["source_sha256"] = {
        name: SOURCES[name]["sha256"] for name in sorted(SOURCES)
    }
    payload["reference_engine_sha256"] = EXPECTED_ENGINE_SHA256
    raw = (
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    if len(raw) != EXPECTED_SNAPSHOT_BYTES or sha256_bytes(raw) != EXPECTED_SNAPSHOT_SHA256:
        raise ValueError("Rebuilt snapshot does not match the frozen reviewed artifact")
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    source_dir = args.source_dir.resolve()
    output = args.output.resolve()
    try:
        for name in SOURCES:
            download(source_dir / name, name)
        raw = build(repo, source_dir)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(raw)
        os.replace(temporary, output)
        print(
            json.dumps(
                {
                    "snapshot": str(output),
                    "bytes": len(raw),
                    "sha256": sha256_bytes(raw),
                    "descriptors": 31110,
                    "label_keys": 267012,
                    "evaluation_cache_unchanged": True,
                },
                indent=2,
            )
        )
        return 0
    except (OSError, ValueError, RuntimeError, EOFError, ET.ParseError, ImportError) as exc:
        print(f"[STOPPED] {exc}", file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

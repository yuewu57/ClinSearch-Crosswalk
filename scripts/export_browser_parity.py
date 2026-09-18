"""Generate native-Python expected outputs for browser/WASM comparison.

--check verifies the frozen source manifest before generating local test data.
--freeze is an explicit maintainer action after a reviewed reference change.
Fixture caches are synthetic and are written only under browser/parity/.
"""
import argparse
import base64
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from ovid_pubmed_converter.engine import MeshResolver  # noqa: E402
from ovid_pubmed_converter.outputs import audit_csv, converted_rtf, one_line_query, strategy_text  # noqa: E402
from ovid_pubmed_converter.web_service import convert_paste, convert_rtf  # noqa: E402

REFERENCE_COMMIT = '8ca2ca49984d13e466ae12332964f3131e49ee64'
DEST = ROOT / 'browser/parity'


def source_hashes():
    return {
        str(p.relative_to(ROOT)).replace('\\', '/'): hashlib.sha256(
            p.read_text(encoding='utf-8').replace('\r\n', '\n').encode('utf-8')
        ).hexdigest()
        for p in sorted((ROOT / 'src/ovid_pubmed_converter').glob('*.py'))
    }


def plain_case(identifier, source, **extra):
    return {'id': identifier, 'request': {'mode': 'paste', 'source': source, **extra},
            'cache': {'schema_version': 1, 'records': {}, 'mesh_year': None}}


def cases():
    output = []
    for case in json.loads((DEST / 'fixtures.json').read_text(encoding='utf-8')):
        item = plain_case(case['id'], case['source'])
        if case.get('endDate'):
            item['request']['endDate'] = case['endDate']
        item['assertions'] = case['expected']
        output.append(item)
    for directory in sorted((ROOT / 'tests/fixtures').glob('[0-9][0-9]_*')):
        if not (directory / 'input_strategy.txt').exists():
            continue
        opts_path = directory / 'input_options.json'
        opts = json.loads(opts_path.read_text()) if opts_path.exists() else {}
        mesh_path = directory / 'mesh_records.json'
        records = json.loads(mesh_path.read_text()) if mesh_path.exists() else {}
        cache = {'schema_version': 1, 'mesh_year': 2026, 'records': records}
        source = (directory / 'input_strategy.txt').read_text(encoding='utf-8')
        output.append({'id': directory.name + '_paste', 'cache': cache,
                       'request': {'mode': 'paste', 'source': source, 'endDate': opts.get('end_date')}})
        if (directory / 'input.rtf').exists():
            output.append({'id': directory.name + '_rtf', 'cache': cache,
                           'request': {'mode': 'rtf', 'dataBase64': base64.b64encode(
                               (directory / 'input.rtf').read_bytes()).decode('ascii')}})
    extra = {
        'date_without_end': '1 asthma.tw.\n2 2022*.dt.\n3 1 and 2',
        'date_not': '1 asthma.tw.\n2 2022*.ed,dt.\n3 1 not 2',
        'date_ed': '1 asthma.tw.\n2 2022*.ed.\n3 1 and 2',
        'date_reverse': '1 asthma.tw.\n2 (2021* or 2022*).dt,ed.\n3 1 and 2',
        'date_mixed': '1 asthma.tw.\n2 (cancer or 2022*).ed,dt.\n3 1 and 2',
        'limit_chain': '1 asthma.tw.\n2 limit 1 to humans\n3 limit 2 to english language',
        'limit_forward': '1 limit 2 to humans\n2 asthma.tw.\n3 1 and 2',
        'limit_self': '1 limit 1 to humans',
        'limit_malformed': '1 limit 2 to',
        'limit_invalid_chain': '1 limit 99 to humans\n2 limit 1 to humans',
        'frequency_zero': '1 cancer.ab./freq=0',
        'frequency_embedded': '1 cancer.ab./freq=2 or asthma.ab.',
        'frequency_unused': '1 cancer.ab./freq=x\n2 asthma.tw.',
        'multifield_3': '1 cancer.ti,ab,kf. or asthma.ab.',
        'short_root': '1 HIV*.tw. or job*.tw. or abc*.tw.',
        'proximity': '1 (upper adj3 respiratory tract infection*).tw.',
        'protected_identifier': '1 anti-PD-L1.tw. or 5-FU.tw.',
        'strict_animal': '1 (animal not human).sh.',
        'wildcard_literal_not': '1 "not otherwise specified*".tw.',
        'wildcard_literal_and': '1 "research and develop*".tw.',
        'wildcard_legacy_tag': '1 "breast* cancer*"[Title/Abstract]',
        'wildcard_journal': '1 "cancer journal*"[Journal]',
        'mesh_unknown': '1 Unknown Heading/',
        'mesh_wildcard_slash': '1 therap*/',
        'publication_unverified': '1 Unverified Example.pt.',
        'controlled_suffixes': '1 (adverse effects or drug therapy).fs.\n2 Insulin Glargine.nm.\n3 1 or 2',
        'comments': '1 (comment on or erratum for).cm.',
        'comment_unknown': '1 unknown relation.cm.',
        'duplicate_rows': '1 asthma.tw.\n1 cancer.tw.',
        'undefined': '1 asthma.tw.\n2 1 and 99',
        'cycle': '1 2\n2 1',
        'quote_error': '1 "asthma.tw.',
        'early_closing': '1 )asthma.tw.(',
        'empty_final': '1 asthma.tw.\n2.',
        'unnumbered': 'asthma.tw.\nwheeze.tw.\n1 or 2',
        'year_continuation': '1 asthma.tw.\n2 (2019 or\n2020 or 2021).tw.\n3 1 and 2',
        'range_references': '1 asthma.tw.\n2 wheeze.tw.\n3 cough.tw.\n4 or/1-3',
    }
    output += [plain_case(key, val) for key, val in extra.items()]
    for key, raw in {
        'rtf_plain_text': b'Medline:\n1 asthma.tw.\n2 wheeze.tw.\n3 1 or 2',
        'rtf_recovered': b'{\\rtf1\\ansi Medline:\\par asthma.tw.\\par wheeze.tw.\\par 1 or 2}',
        'rtf_cp1252': b'{\\rtf1\\ansi\\ansicpg1252 Medline:\\par 1 caf\xe9.tw.}',
        'rtf_unicode': b'{\\rtf1\\ansi\\uc1 Medline:\\par 1 caf\\u233?.tw.}',
        'rtf_markup_text': b'{\\rtf1\\ansi Medline:\\par 1 \\"<script>alert(1)</script>\\".tw.}',
    }.items():
        output.append({'id': key, 'request': {'mode': 'rtf', 'dataBase64': base64.b64encode(raw).decode()},
                       'cache': {'schema_version': 1, 'records': {}, 'mesh_year': None}})
    return output


def expected(case):
    request, cache = case['request'], case['cache']
    resolver = MeshResolver(cache_path=None, mode='cache-only')
    resolver.records = dict(cache['records'])
    resolver.mesh_year = cache['mesh_year']
    if request['mode'] == 'paste':
        result = convert_paste(request['source'], request.get('endDate'), resolver=resolver)
    else:
        result = convert_rtf(base64.b64decode(request['dataBase64']), resolver=resolver)
    # Derived independently of browser_bridge.py from the reference public API.
    input_warnings = [w for w in result.warnings if w in {
        'rtf_line_numbers_recovered_from_medline_paragraph_order',
        'plain_text_file_uploaded_with_rtf_extension',
    }]
    value = {'result': asdict(result), 'strategyText': strategy_text(result),
             'oneLineQuery': one_line_query(result), 'auditCsv': audit_csv(result),
             'convertedRtf': converted_rtf(result).decode('ascii'),
             'inputWarnings': input_warnings, 'adapterError': None}
    a = case.get('assertions', {})
    assert result.validation_status.value == a.get('validationStatus', result.validation_status.value)
    if 'strategyLines' in a:
        assert value['strategyText'].splitlines() == a['strategyLines'], case['id']
    if 'oneLineQuery' in a:
        assert value['oneLineQuery'] == a['oneLineQuery'], case['id']
    for flag in a.get('rowAuditFlagsContain', []):
        assert any(flag in row.audit_flags for row in result.rows), (case['id'], flag)
    for num, status in a.get('rowValidationStatuses', {}).items():
        assert next(row for row in result.rows if row.number == int(num)).validation_status == status
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--freeze', action='store_true')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    manifest = {'referenceCommit': REFERENCE_COMMIT, 'hashPolicy': 'UTF-8 with LF newlines',
                'sourceHashes': source_hashes()}
    target = DEST / 'reference-manifest.json'
    if args.freeze:
        target.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    if not target.exists() or json.loads(target.read_text()) != manifest:
        raise SystemExit('Reference source hashes changed. Review first; --freeze is explicit.')
    values = cases()
    for case in values:
        case['expected'] = expected(case)
    (DEST / 'generated.json').write_text(json.dumps(values, indent=2) + '\n', encoding='utf-8')
    print(f'Native reference verified: {len(values)} cases; all result/audit fields exported.')


if __name__ == '__main__':
    main()

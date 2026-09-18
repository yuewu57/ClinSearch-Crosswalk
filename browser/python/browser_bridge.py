"""Data-only bridge to the unchanged Python reference; native and WebAssembly.

No source string is evaluated as Python. MeSH resolution is always cache-only.
The terminology payload is parsed once during worker initialization and reused
for subsequent conversions in that worker.
"""
import base64
import json
from dataclasses import asdict, replace

from mesh_snapshot_resolver_v1_YW_18092026 import resolver_from_payload

from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.outputs import audit_csv, converted_rtf, one_line_query, strategy_text
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 1000
MAX_QUERY_CHARS = 2 * 1024 * 1024
MAX_NESTING = 100

_RESOLVER = None


def initialize_cache_json(cache_json):
    """Parse and install one immutable cache/snapshot for this worker."""
    global _RESOLVER
    payload = json.loads(cache_json)
    _RESOLVER = resolver_from_payload(payload)
    return True


def _check_depth(text):
    depth = 0
    quoted = False
    for char in text:
        if char == '"':
            quoted = not quoted
        elif not quoted and char == '(':
            depth += 1
            if depth > MAX_NESTING:
                raise ValueError('browser_nesting_limit_exceeded')
        elif not quoted and char == ')':
            depth = max(0, depth - 1)


def _check_expanded_query_size(result):
    """Count expanded bytes before the reference renderer allocates the query."""
    rows = {
        row.output_number if row.output_number is not None else row.number: row.converted
        for row in result.rows if row.converted
    }
    rows.update(dict(result.synthetic_rows))
    import re
    token = re.compile(r'"[^"\n]*"|#(\d+)\b')
    memo = {}

    def size(number, visiting):
        if number in memo:
            return memo[number]
        if number in visiting or number not in rows:
            raise ValueError('browser_query_reference_invalid')
        if len(visiting) > MAX_NESTING:
            raise ValueError('browser_dependency_depth_limit_exceeded')
        expr = rows[number]
        total = len(expr)
        for match in token.finditer(expr):
            if match.group(1):
                total += size(int(match.group(1)), visiting + (number,)) + 2
                if total > MAX_QUERY_CHARS:
                    raise ValueError('browser_expanded_query_limit_exceeded')
        memo[number] = total
        return total

    if result.validation_status.value == 'ok' and result.final_line_number is not None:
        size(result.final_line_number, ())


def _run(request):
    if _RESOLVER is None:
        raise ValueError('browser_runtime_cache_not_initialized')

    mode = request.get('mode')
    if mode == 'paste':
        source = request.get('source')
        if not isinstance(source, str) or len(source.encode('utf-8')) > MAX_BYTES:
            raise ValueError('browser_input_empty_or_too_large')
        if not source.strip():
            raise ValueError('browser_input_empty_or_too_large')
        _check_depth(source)
        strategy = parse_strategy_text(source, end_date=request.get('endDate'))
    elif mode == 'rtf':
        encoded = request.get('dataBase64')
        if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
            raise ValueError('browser_rtf_empty_or_too_large')
        data = base64.b64decode(encoded, validate=True)
        if not data or len(data) > MAX_BYTES:
            raise ValueError('browser_rtf_empty_or_too_large')
        strategy = parse_rtf_bytes(data)
        del data
    else:
        raise ValueError('browser_input_mode_invalid')

    if len(strategy.rows) > MAX_ROWS:
        raise ValueError('browser_row_limit_exceeded')
    for row in strategy.rows:
        _check_depth(row.source)

    result = convert_strategy(strategy, mesh_resolver=_RESOLVER)
    input_warnings = tuple(strategy.metadata.get('input_warnings', ()) or ())
    if input_warnings:
        result = replace(
            result,
            warnings=tuple(dict.fromkeys(result.warnings + input_warnings)),
            audit_events=tuple(dict.fromkeys(result.audit_events + input_warnings)),
        )
    _check_expanded_query_size(result)
    query = one_line_query(result)
    return {
        'result': asdict(result),
        'strategyText': strategy_text(result),
        'oneLineQuery': query,
        'auditCsv': audit_csv(result),
        'convertedRtf': converted_rtf(result).decode('ascii'),
        'inputWarnings': list(input_warnings),
        'adapterError': None,
    }


def run_request_json(request_json):
    """One request in, one JSON result out; no user data persists between calls."""
    try:
        value = _run(json.loads(request_json))
    except (TypeError, ValueError, UnicodeError, RecursionError, MemoryError) as exc:
        known = str(exc).split(':', 1)[0]
        code = (
            known
            if known.startswith(('browser_', 'rtf_', 'invalid_rtf_', 'one_line_'))
            else 'browser_input_processing_failed'
        )
        value = {
            'result': {
                'validation_status': 'manual_review_required',
                'rows': [],
                'final_line_number': None,
                'final_query': None,
                'warnings': [],
                'audit_events': [],
                'validation_errors': [code],
                'removed_line_numbers': [],
                'synthetic_rows': [],
            },
            'strategyText': '',
            'oneLineQuery': '',
            'auditCsv': '',
            'convertedRtf': '',
            'inputWarnings': [],
            'adapterError': code,
        }
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))

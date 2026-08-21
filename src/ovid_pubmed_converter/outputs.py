"""In-memory output renderers shared by the web and CLI adapters."""

import csv
import io
import json
import re

from . import engine
from .models import ConversionResult, ValidationStatus


_LINE_REFERENCE_RE = re.compile(r"#(?P<number>\d+)\b")


def _rendered_strategy_map(result: ConversionResult) -> dict[int, str]:
    """Return the final rendered PubMed row map, including synthetic aliases."""
    rows = {
        row.output_number if row.output_number is not None else row.number: row.converted
        for row in result.rows
        if row.converted
    }
    rows.update(dict(result.synthetic_rows))
    return rows


def _replace_references_outside_quotes(expression: str, replacement) -> str:
    """Replace ``#N`` line references only outside double-quoted PubMed text."""
    parts = re.split(r'("[^"]*")', expression)
    for index in range(0, len(parts), 2):
        parts[index] = _LINE_REFERENCE_RE.sub(replacement, parts[index])
    return "".join(parts)


def _contains_reference_outside_quotes(expression: str) -> bool:
    parts = re.split(r'("[^"]*")', expression)
    return any(_LINE_REFERENCE_RE.search(parts[index]) for index in range(0, len(parts), 2))


def one_line_query(result: ConversionResult) -> str:
    """Resolve the validated final PubMed row recursively into one executable query.

    Only rows reachable from ``result.final_line_number`` are expanded. Unused
    converted rows are deliberately excluded. Every substituted line reference
    is parenthesized so Boolean precedence is preserved. A sole-reference alias
    resolves directly to its target to avoid unnecessary wrapper parentheses.
    References inside quoted PubMed text are never interpreted as row links.
    """
    if result.validation_status is not ValidationStatus.OK:
        return ""
    if result.final_line_number is None:
        return ""

    rows = _rendered_strategy_map(result)
    final_line = result.final_line_number
    if final_line not in rows:
        raise ValueError(f"one_line_final_row_missing:#{final_line}")

    memo: dict[int, str] = {}

    def resolve(number: int, stack: tuple[int, ...] = ()) -> str:
        if number in memo:
            return memo[number]
        if number in stack:
            cycle = "->".join(f"#{item}" for item in stack + (number,))
            raise ValueError(f"one_line_cyclic_reference:{cycle}")
        if number not in rows:
            raise ValueError(f"one_line_dangling_reference:#{number}")

        expression = rows[number].strip()
        sole_reference = re.fullmatch(r"#(?P<number>\d+)\b", expression)
        if sole_reference is not None:
            resolved = resolve(int(sole_reference.group("number")), stack + (number,))
            memo[number] = resolved
            return resolved

        def replace_reference(match: re.Match) -> str:
            reference = int(match.group("number"))
            return f"({resolve(reference, stack + (number,))})"

        resolved = _replace_references_outside_quotes(expression, replace_reference)
        resolved = re.sub(r"\s+", " ", resolved).strip()
        memo[number] = resolved
        return resolved

    query = resolve(final_line)
    local_errors = engine.validate_converted_expression(query, allow_line_references=False)
    if local_errors:
        raise ValueError("one_line_query_validation_failed:" + ";".join(local_errors))
    if _contains_reference_outside_quotes(query):
        raise ValueError("one_line_query_contains_unresolved_reference")
    return query


def strategy_text(result: ConversionResult) -> str:
    rows = [
        (row.output_number if row.output_number is not None else row.number, row.converted)
        for row in result.rows
        if row.converted
    ]
    rows.extend(result.synthetic_rows)
    rows.sort(key=lambda item: item[0])
    return "\n".join(f"#{number} {converted}" for number, converted in rows) + "\n"


def audit_csv(result: ConversionResult) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "line_number",
            "original",
            "converted",
            "flags",
            "validation_status",
            "validation_errors",
        ]
    )
    for row in result.rows:
        writer.writerow(
            [
                row.number,
                row.original,
                row.converted,
                "; ".join(row.audit_flags),
                row.validation_status,
                "; ".join(row.validation_errors),
            ]
        )
    return stream.getvalue()


def validation_report(result: ConversionResult) -> str:
    resolved_query = one_line_query(result)
    payload = {
        "status": result.validation_status.value,
        "final_line": result.final_line_number,
        "one_line_query": resolved_query or None,
        "warnings": result.warnings,
        "errors": result.validation_errors,
        "note": "A validation/manual-review failure must not be submitted to PubMed.",
    }
    return json.dumps(payload, indent=2) + "\n"


def converted_rtf(result: ConversionResult) -> bytes:
    body = "PubMed:\n" + strategy_text(result)
    text = "{\\rtf1\\ansi\\ansicpg1252\\uc1\n" + engine._escape_text_for_rtf(body) + "\n}"
    return text.encode("ascii")

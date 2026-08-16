"""Shared deterministic strategy conversion API used by web and CLI."""

from . import engine
from .audit import flatten_audit
from .models import ConvertedRow, ConversionResult, Strategy, ValidationStatus


def convert_strategy(strategy: Strategy, *, mesh_resolver=None) -> ConversionResult:
    """Convert a canonical strategy without UI or output-file dependencies."""
    resolver = mesh_resolver or engine.MeshResolver(cache_path=None, mode="cache-only")
    engine.ACTIVE_MESH_RESOLVER = resolver
    rows = [(row.number, row.source) for row in strategy.rows]
    if not rows:
        errors = strategy.source_errors or ("no_strategy_rows",)
        return ConversionResult(
            ValidationStatus.VALIDATION_FAILED,
            (),
            None,
            None,
            (),
            (),
            tuple(errors),
        )

    known = {number for number, _ in rows}
    omit_dates = strategy.end_date is not None
    uncached: set[str] = set()
    original_mode = resolver.mode
    try:
        resolver.mode = "cache-only"
        prefix = "mesh_resolution_fallback_to_source_heading:"
        for _number, expression in rows:
            _converted, flags = engine.convert_line(
                expression,
                known_line_numbers=known,
                omit_ovid_update_dates=omit_dates,
            )
            for flag in flags:
                if flag.startswith(prefix):
                    label = flag[len(prefix) :].partition(":")[0]
                    if label:
                        uncached.add(label)
    finally:
        resolver.mode = original_mode
    if uncached:
        resolver.prefetch(uncached)

    converted: dict[int, str] = {}
    originals: dict[int, str] = {}
    flags_by_line: dict[int, list[str]] = {}
    protected_errors: dict[int, list[str]] = {}
    try:
        resolver.mode = "cache-only"
        for number, expression in rows:
            output, flags = engine.convert_line(
                expression,
                known_line_numbers=known,
                omit_ovid_update_dates=omit_dates,
            )
            errors = engine.validate_protected_hyphenated_terms(expression, output, flags)
            converted[number] = output
            originals[number] = expression
            protected_errors[number] = errors
            flags_by_line[number] = list(dict.fromkeys(flags + errors))
    finally:
        resolver.mode = original_mode

    changed = True
    while changed:
        changed = False
        dropped = {number for number, value in converted.items() if value == engine.DROP_ATOM}
        for number in sorted(converted):
            if number in dropped:
                continue
            value, did_change = engine.simplify_dropped_line_references(
                converted[number], dropped, flags_by_line[number], number
            )
            if did_change:
                converted[number] = value
                flags_by_line[number] = list(dict.fromkeys(flags_by_line[number]))
                changed = True

    dropped = {number for number, value in converted.items() if value == engine.DROP_ATOM}
    surviving = {number: value for number, value in converted.items() if number not in dropped}
    order = [number for number, _ in rows if number in surviving]
    final_number = order[-1] if order else None
    active = engine.final_query_dependency_closure(surviving, final_number)
    line_errors: dict[int, list[str]] = {}
    for number in converted:
        line_errors[number] = [] if number in dropped else list(
            dict.fromkeys(
                engine.validate_converted_expression(converted[number], allow_line_references=True)
                + protected_errors[number]
            )
        )

    active_map = {number: surviving[number] for number in active if number in surviving}
    all_errors = list(strategy.source_errors) + engine.validate_reference_graph(active_map)
    for number in sorted(active):
        all_errors.extend(f"line_#{number}:{error}" for error in line_errors[number])
    if final_number is None:
        all_errors.append("final_query_empty_after_short_root_cleanup")
    all_errors = list(dict.fromkeys(all_errors))

    if final_number is None:
        status = ValidationStatus.MANUAL_REVIEW_REQUIRED
    elif all_errors:
        status = ValidationStatus.VALIDATION_FAILED
    else:
        status = ValidationStatus.OK

    converted_rows = []
    for number, _expression in rows:
        if number in dropped:
            row_status = "removed_after_short_root_cleanup"
            rendered = ""
            errors = ()
        else:
            errors = tuple(line_errors[number])
            row_status = (
                "ok" if not errors else "validation_failed" if number in active else "warning_unused_line"
            )
            rendered = converted[number]
        converted_rows.append(
            ConvertedRow(
                number,
                originals[number],
                rendered,
                tuple(flags_by_line[number]),
                row_status,
                errors,
            )
        )

    warning_flags = tuple(
        event
        for event in flatten_audit(flags_by_line)
        if any(token in event for token in ("warning", "fallback", "approximation", "manual"))
    )
    return ConversionResult(
        status,
        tuple(converted_rows),
        final_number,
        surviving.get(final_number) if final_number is not None else None,
        warning_flags,
        flatten_audit(flags_by_line),
        tuple(all_errors),
        tuple(sorted(dropped)),
    )

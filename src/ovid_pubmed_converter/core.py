"""Shared deterministic v21 strategy conversion API used by web and CLI."""

from . import engine as base_engine
from . import engine_v21
from .audit import flatten_audit
from .models import ConversionResult, ConvertedRow, Strategy, ValidationStatus


def convert_strategy(strategy: Strategy, *, mesh_resolver=None) -> ConversionResult:
    """Convert a canonical strategy under the approved v21 rules."""
    resolver = mesh_resolver or base_engine.MeshResolver(cache_path=None, mode="cache-only")
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

    raw_limit_aliases = {
        number: base
        for number, expression in rows
        if (base := engine_v21.parse_ovid_limit_alias(expression)) is not None
    }
    invalid_limit_errors: dict[int, list[str]] = {}
    candidate_limit_aliases: dict[int, int] = {}
    for limit_row, base_row in raw_limit_aliases.items():
        if base_row not in known:
            invalid_limit_errors.setdefault(limit_row, []).append(
                f"ovid_limit_base_reference_undefined:#{limit_row}->#{base_row}"
            )
        elif base_row >= limit_row:
            invalid_limit_errors.setdefault(limit_row, []).append(
                f"ovid_limit_base_must_reference_prior_row:#{limit_row}->#{base_row}"
            )
        else:
            candidate_limit_aliases[limit_row] = base_row
    try:
        limit_aliases = engine_v21.resolve_limit_aliases(candidate_limit_aliases)
    except ValueError as exc:
        for limit_row in candidate_limit_aliases:
            invalid_limit_errors.setdefault(limit_row, []).append(str(exc))
        limit_aliases = {}

    # Cache-prefetch discovery remains isolated exactly as in v20.
    uncached: set[str] = set()
    discovery_resolver = base_engine.MeshResolver(cache_path=None, mode="cache-only")
    with base_engine.mesh_resolver_context(discovery_resolver):
        prefix = "mesh_resolution_fallback_to_source_heading:"
        for _number, expression in rows:
            _converted, flags = engine_v21.convert_line(
                expression,
                known_line_numbers=known,
                omit_ovid_update_dates=omit_dates,
            )
            for flag in flags:
                if flag.startswith(prefix):
                    label = flag[len(prefix) :].partition(":")[0]
                    if label:
                        uncached.add(label)
    if uncached:
        resolver.prefetch(uncached)

    converted: dict[int, str] = {}
    originals: dict[int, str] = {}
    flags_by_line: dict[int, list[str]] = {}
    protected_errors: dict[int, list[str]] = {}
    with base_engine.mesh_resolver_context(resolver):
        for number, expression in rows:
            output, flags = engine_v21.convert_line(
                expression,
                known_line_numbers=known,
                omit_ovid_update_dates=omit_dates,
            )
            errors = base_engine.validate_protected_hyphenated_terms(expression, output, flags)
            converted[number] = output
            originals[number] = expression
            protected_errors[number] = errors
            flags_by_line[number] = list(dict.fromkeys(flags + errors))

    # A syntactically valid LIMIT command may still point at an undefined or
    # non-prior row. Keep such a row for manual review; do not silently drop it.
    for number, errors in invalid_limit_errors.items():
        converted[number] = base_engine.MANUAL_REVIEW_ATOM
        protected_errors[number] = []
        retained_flags = [
            flag
            for flag in flags_by_line[number]
            if not flag.startswith("ovid_limit_line_ignored_redirect_to_source_")
            and flag != "major_semantic_approximation_recall_broadened"
        ]
        flags_by_line[number] = list(
            dict.fromkeys(
                retained_flags
                + ["invalid_ovid_limit_alias_manual_review_required"]
                + errors
            )
        )

    # References to valid LIMIT rows inherit the LIMIT base before removal.
    if limit_aliases:
        for number in sorted(converted):
            if number in limit_aliases or converted[number] == base_engine.DROP_ATOM:
                continue
            rewritten = engine_v21.rewrite_hash_line_references(converted[number], limit_aliases)
            if rewritten != converted[number]:
                converted[number] = rewritten
                flags_by_line[number].append("references_to_ignored_limit_rows_redirected")
                flags_by_line[number] = list(dict.fromkeys(flags_by_line[number]))

    # v21 database-update date rows are intentionally discarded. An AND
    # reference to such a row is the normal update-search wrapper and can be
    # simplified by the inherited dropped-row logic below. OR/NOT use is not a
    # filter wrapper and is therefore retained as an explicit manual-review
    # defect instead of being simplified silently.
    update_date_rows = {
        number
        for number, flags in flags_by_line.items()
        if "ovid_database_update_date_filter_ignored" in flags
    }
    if update_date_rows:
        for number in sorted(converted):
            if number in update_date_rows or converted[number] in {
                base_engine.DROP_ATOM,
                base_engine.MANUAL_REVIEW_ATOM,
            }:
                continue
            refs = set(base_engine.referenced_line_numbers(converted[number]))
            affected = sorted(refs & update_date_rows)
            if not affected:
                continue
            boolean_parts = [
                part.strip().upper()
                for part in base_engine.split_top_level_boolean(converted[number])
            ]
            if "OR" in boolean_parts or "NOT" in boolean_parts:
                converted[number] = base_engine.MANUAL_REVIEW_ATOM
                protected_errors[number] = []
                flags_by_line[number].append(
                    "ovid_update_date_reference_in_or_not_manual_review_required:"
                    + ",".join(f"#{ref}" for ref in affected)
                )
                flags_by_line[number] = list(dict.fromkeys(flags_by_line[number]))

    # Existing v20 dropped-row simplification, after LIMIT redirection and the
    # v21 update-date OR/NOT safety gate.
    changed = True
    while changed:
        changed = False
        dropped = {
            number for number, value in converted.items() if value == base_engine.DROP_ATOM
        }
        for number in sorted(converted):
            if number in dropped:
                continue
            value, did_change = base_engine.simplify_dropped_line_references(
                converted[number], dropped, flags_by_line[number], number
            )
            if did_change:
                converted[number] = value
                flags_by_line[number] = list(dict.fromkeys(flags_by_line[number]))
                changed = True

    dropped = {
        number for number, value in converted.items() if value == base_engine.DROP_ATOM
    }
    surviving_source_order = [number for number, _ in rows if number not in dropped]

    # Preserve v20 numbering unless valid LIMIT removal explicitly requires
    # consecutive output renumbering. Update-date removal alone never renumbers.
    renumber_due_to_limit = bool(limit_aliases)
    if renumber_due_to_limit:
        renumber_map = {
            old_number: new_number
            for new_number, old_number in enumerate(surviving_source_order, start=1)
        }
    else:
        renumber_map = {number: number for number in surviving_source_order}

    surviving: dict[int, str] = {}
    for old_number in surviving_source_order:
        new_number = renumber_map[old_number]
        surviving[new_number] = engine_v21.rewrite_hash_line_references(
            converted[old_number], renumber_map
        )
        if renumber_due_to_limit and old_number != new_number:
            flags_by_line[old_number].append(
                f"output_row_renumbered:#{old_number}->#{new_number}"
            )
            flags_by_line[old_number] = list(dict.fromkeys(flags_by_line[old_number]))

    source_final = rows[-1][0]
    synthetic_rows: list[tuple[int, str]] = []
    synthetic_final_number: int | None = None
    if source_final in limit_aliases:
        effective_source = limit_aliases[source_final]
        if effective_source not in renumber_map:
            final_number = max(surviving) if surviving else None
            source_level_errors = [
                (
                    "effective_final_query_source_removed_after_limit_alias:"
                    f"#{source_final}->#{effective_source}"
                )
            ]
        else:
            target = renumber_map[effective_source]
            source_level_errors = []
            if surviving and max(surviving) == target:
                final_number = target
            else:
                synthetic_final_number = (max(surviving) + 1) if surviving else 1
                surviving[synthetic_final_number] = f"#{target}"
                synthetic_rows.append((synthetic_final_number, f"#{target}"))
                final_number = synthetic_final_number
                flags_by_line[source_final].append(
                    "synthetic_final_alias_after_ignored_limit:"
                    f"#{synthetic_final_number}->#{target}"
                )
                flags_by_line[source_final] = list(dict.fromkeys(flags_by_line[source_final]))
    else:
        source_level_errors = []
        final_number = renumber_map[surviving_source_order[-1]] if surviving_source_order else None

    active = base_engine.final_query_dependency_closure(surviving, final_number)
    active_source = {
        old_number
        for old_number, new_number in renumber_map.items()
        if new_number in active
    }

    line_errors: dict[int, list[str]] = {}
    for old_number in converted:
        if old_number in dropped:
            line_errors[old_number] = []
        else:
            new_number = renumber_map[old_number]
            line_errors[old_number] = list(
                dict.fromkeys(
                    base_engine.validate_converted_expression(
                        surviving[new_number], allow_line_references=True
                    )
                    + protected_errors[old_number]
                )
            )

    active_map = {number: surviving[number] for number in active if number in surviving}
    all_errors = (
        list(strategy.source_errors)
        + source_level_errors
        + base_engine.validate_reference_graph(active_map)
    )
    if synthetic_final_number is not None:
        all_errors.extend(
            f"line_#{synthetic_final_number}(synthetic_final_alias):{error}"
            for error in base_engine.validate_converted_expression(
                surviving[synthetic_final_number], allow_line_references=True
            )
        )
    for old_number in sorted(active_source):
        new_number = renumber_map[old_number]
        all_errors.extend(
            f"line_#{new_number}(source_#{old_number}):{error}"
            for error in line_errors[old_number]
        )
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
    for old_number, _expression in rows:
        if old_number in dropped:
            if old_number in limit_aliases:
                row_status = "removed_ignored_ovid_limit"
            elif "ovid_database_update_date_filter_ignored" in flags_by_line[old_number]:
                row_status = "removed_ignored_ovid_update_date"
            elif (
                "ovid_ed_dt_update_line_omitted_external_end_date_applied"
                in flags_by_line[old_number]
            ):
                row_status = "removed_ignored_ovid_update_date"
            else:
                row_status = "removed_after_short_root_cleanup"
            rendered = ""
            errors = ()
            output_number = None
        else:
            errors = tuple(line_errors[old_number])
            row_status = (
                "ok"
                if not errors
                else "validation_failed"
                if old_number in active_source
                else "warning_unused_line"
            )
            output_number = renumber_map[old_number]
            rendered = surviving[output_number]
        converted_rows.append(
            ConvertedRow(
                old_number,
                originals[old_number],
                rendered,
                tuple(flags_by_line[old_number]),
                row_status,
                errors,
                output_number=output_number,
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
        synthetic_rows=tuple(synthetic_rows),
    )

"""v21 conversion layer over the frozen v20 engine.

The mature v20 implementation remains in ``engine``. This module adds only
approved v21 semantics: Ovid /freq handling, LIMIT-row classification helpers,
and PubMed wildcard-phrase dequoting after v20 canonicalisation.
"""

import re

from .engine import *  # noqa: F403
from .engine import _escape_text_for_rtf
from .engine import convert_line as _convert_line_v20

OUTPUT_VERSION = "v21"
# MeSH semantics did not change in v21; reuse the maintained v20 cache.
DEFAULT_MESH_CACHE_NAME = "mesh_resolution_cache_v20_YW_16082026.json"


def strip_ovid_frequency_requirement(line: str):
    """Remove a complete Ovid ``/freq=N`` suffix for integer ``N >= 1``.

    ``freq=1`` is redundant. ``freq>1`` is an audited recall-broadening
    approximation. Malformed/non-positive frequency syntax is forced to manual
    review so it cannot drift into quoted free text.
    """
    flags: list[str] = []
    normalized = normalize_unicode(line).strip()  # noqa: F405
    match = re.fullmatch(
        r"(?P<base>.+?)\s*/\s*freq\s*=\s*(?P<n>\d+)\s*",
        normalized,
        flags=re.I,
    )
    if match is not None:
        n = int(match.group("n"))
        base = tidy_spaces(match.group("base"))  # noqa: F405
        if n >= 1 and base:
            if n == 1:
                flags.append("ovid_frequency_constraint_removed_as_redundant:freq=1")
            else:
                flags.append(f"ovid_frequency_constraint_ignored:freq={n}")
                flags.append("major_semantic_approximation_recall_broadened")
            return base, flags
        flags.append(f"invalid_ovid_frequency_constraint_manual_review_required:freq={n}")
        return MANUAL_REVIEW_ATOM, flags  # noqa: F405

    if re.search(r"/\s*freq\b", normalized, flags=re.I):
        flags.append("malformed_or_unsupported_ovid_frequency_constraint_manual_review_required")
        return MANUAL_REVIEW_ATOM, flags  # noqa: F405
    return normalized, flags


def parse_ovid_limit_alias(line: str) -> int | None:
    """Return the source row referenced by a complete ``limit N to ...`` row."""
    match = re.fullmatch(
        r"\s*limit\s+#?(?P<base>\d+)\s+to\s+(?P<condition>\S(?:.*\S)?)\s*",
        normalize_unicode(line),  # noqa: F405
        flags=re.I,
    )
    return int(match.group("base")) if match else None


def is_ovid_limit_like_line(line: str) -> bool:
    return re.match(r"\s*limit\b", normalize_unicode(line), flags=re.I) is not None  # noqa: F405


def resolve_limit_aliases(limit_aliases: dict[int, int]) -> dict[int, int]:
    """Resolve chained LIMIT aliases conservatively."""
    resolved: dict[int, int] = {}
    for source in limit_aliases:
        seen: set[int] = {source}
        target = limit_aliases[source]
        while target in limit_aliases:
            if target in seen:
                raise ValueError(f"circular_ovid_limit_alias_at_#{source}")
            seen.add(target)
            target = limit_aliases[target]
        resolved[source] = target
    return resolved


def rewrite_hash_line_references(expr: str, mapping: dict[int, int]) -> str:
    if not mapping or "#" not in expr:
        return expr
    return re.sub(
        r"#(?P<n>\d+)",
        lambda m: f"#{mapping.get(int(m.group('n')), int(m.group('n')))}",
        expr,
    )


def dequote_wildcard_fielded_phrases(line: str):
    """Remove quotes from safe wildcard phrases after PubMed tag canonicalisation.

    Literal OR/NOT (and any surviving AND) keep the phrase quoted to avoid
    reinterpreting phrase text as PubMed Boolean syntax. Ovid runtime stopword
    handling occurs earlier in v20, so e.g. ``research and develop*`` may
    already have become ``research[tw] AND develop*[tw]``; v21 intentionally
    preserves that inherited recall-oriented behaviour.
    """
    flags: list[str] = []
    pattern = re.compile(
        r'"(?P<phrase>[^"\n]*\*[^"\n]*)"\[(?P<tag>ti|tiab|tw|all|ta)\]',
        flags=re.I,
    )

    def repl(match: re.Match) -> str:
        phrase = re.sub(r"\s+", " ", match.group("phrase")).strip()
        if not phrase or " " not in phrase:
            return match.group(0)
        tag = match.group("tag").lower()
        boolean_token = re.search(r"\b(AND|OR|NOT)\b", phrase, flags=re.I)
        if boolean_token is not None:
            flags.append(
                "wildcard_phrase_quotes_retained_due_literal_boolean_token:"
                f"{boolean_token.group(1).upper()}:{phrase}[{tag}]"
            )
            return f'"{phrase}"[{tag}]'
        flags.append(f"wildcard_phrase_quotes_removed_field_tag_preserved:{phrase}[{tag}]")
        return f"{phrase}[{tag}]"

    return pattern.sub(repl, line), flags


def convert_line(
    expr: str,
    known_line_numbers: set[int] | None = None,
    *,
    omit_ovid_update_dates: bool = False,
):
    """Apply v21 pre/post-processing around the frozen v20 line converter."""
    line = normalize_unicode(expr.strip())  # noqa: F405

    limit_base = parse_ovid_limit_alias(line)
    if limit_base is not None:
        return DROP_ATOM, [  # noqa: F405
            f"ovid_limit_line_ignored_redirect_to_source_#{limit_base}",
            "major_semantic_approximation_recall_broadened",
        ]
    if is_ovid_limit_like_line(line):
        return MANUAL_REVIEW_ATOM, [  # noqa: F405
            "malformed_or_unsupported_ovid_limit_line_manual_review_required"
        ]

    line, frequency_flags = strip_ovid_frequency_requirement(line)
    if line == MANUAL_REVIEW_ATOM:  # noqa: F405
        return line, frequency_flags

    converted, flags = _convert_line_v20(
        line,
        known_line_numbers=known_line_numbers,
        omit_ovid_update_dates=omit_ovid_update_dates,
    )
    converted, wildcard_flags = dequote_wildcard_fielded_phrases(converted)
    return converted, list(dict.fromkeys(frequency_flags + flags + wildcard_flags))

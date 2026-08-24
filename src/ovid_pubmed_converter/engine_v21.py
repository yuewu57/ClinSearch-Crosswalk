"""v21 conversion layer over the frozen v20 engine.

The mature v20 implementation remains in ``engine``. This module adds only
approved v21 semantics: Ovid /freq handling, LIMIT-row classification helpers,
Ovid database-update date-filter removal, PubMed-safe grouped wildcard-phrase
rendering, and the v21 conformance fix for inline Ovid multi-field free-text
suffixes such as ``.ti,ab.``.
"""

import re

from .engine import (
    DROP_ATOM,
    MANUAL_REVIEW_ATOM,
    convert_field_tags,
    convert_ovid_stopword_free_text,
    normalize_unicode,
    quote_free_text_field_expressions,
    tidy_spaces,
)
from .engine import convert_line as _convert_line_v20

OUTPUT_VERSION = "v21"
# MeSH semantics did not change in v21; reuse the maintained v20 cache.
DEFAULT_MESH_CACHE_NAME = "mesh_resolution_cache_v20_YW_16082026.json"


OVID_FREE_TEXT_FIELD = r"(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)"
INLINE_OVID_MULTIFIELD_RE = re.compile(
    r'(?<![A-Za-z0-9])'
    r'(?P<expr>'
    r'"[^"\n]+"'
    r'|'
    r'(?!(?:and|or|not|adj\d*|next)\b)'
    r'[A-Za-z0-9*?$#\047\-]+'
    r'(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*?$#\047\-]+)*'
    r')'
    r'\s*\.(?P<fields>'
    + OVID_FREE_TEXT_FIELD
    + r'(?:\s*,\s*'
    + OVID_FREE_TEXT_FIELD
    + r')+)\s*\.?',
    flags=re.IGNORECASE,
)


def preserve_inline_ovid_multifield_free_text(line: str):
    """Pre-convert inline Ovid multi-field free-text atoms safely.

    The frozen v20 engine correctly maps a complete ``.ti,ab.`` field list
    when it sees the atom in isolation, but an inherited inline matcher can
    otherwise split the first field from the remainder inside a longer Boolean
    expression, producing malformed output such as ``[ti],ab.``.

    v21 isolates each atomic multi-field object, applies the inherited v20
    stopword/quotation/field mapping to that object, and then passes the whole
    expression into the ordinary v20 converter. This changes no approved field
    semantics; it only preserves the complete field list until the existing
    multifield mapper is applied.
    """
    flags: list[str] = []

    def repl(match: re.Match) -> str:
        fields = match.group("fields")
        fragment = f"{match.group('expr')}.{fields}."
        stopworded, stopword_flags = convert_ovid_stopword_free_text(fragment)
        quoted = quote_free_text_field_expressions(stopworded)
        converted, field_flags = convert_field_tags(quoted)
        flags.extend(stopword_flags)
        flags.extend(field_flags)
        flags.append(
            "v21_inline_multifield_suffix_preserved:"
            + re.sub(r"\s+", "", fields).lower()
        )
        return converted

    converted = INLINE_OVID_MULTIFIELD_RE.sub(repl, line)
    return converted, list(dict.fromkeys(flags))


def split_multifield_residue_flags(line: str) -> list[str]:
    """Detect malformed remnants of a split Ovid multi-field suffix."""
    flags: list[str] = []
    if re.search(
        r"\[(?:ti|tiab|tw|all|ta)\]\s*,\s*"
        r"(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)\b",
        line,
        flags=re.IGNORECASE,
    ):
        flags.append("split_ovid_multifield_suffix_after_pubmed_tag")
    if re.search(
        r"\.(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)\.\s*,\s*"
        r"(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)\b",
        line,
        flags=re.IGNORECASE,
    ):
        flags.append("split_ovid_multifield_suffix_before_pubmed_tag")
    return flags


def strip_ovid_frequency_requirement(line: str):
    """Remove a complete Ovid ``/freq=N`` suffix for integer ``N >= 1``.

    ``freq=1`` is redundant. ``freq>1`` is an audited recall-broadening
    approximation. Malformed/non-positive frequency syntax is forced to manual
    review so it cannot drift into quoted free text.
    """
    flags: list[str] = []
    normalized = normalize_unicode(line).strip()
    match = re.fullmatch(
        r"(?P<base>.+?)\s*/\s*freq\s*=\s*(?P<n>\d+)\s*",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is not None:
        n = int(match.group("n"))
        base = tidy_spaces(match.group("base"))
        if n >= 1 and base:
            if n == 1:
                flags.append("ovid_frequency_constraint_removed_as_redundant:freq=1")
            else:
                flags.append(f"ovid_frequency_constraint_ignored:freq={n}")
                flags.append("major_semantic_approximation_recall_broadened")
            return base, flags
        flags.append(f"invalid_ovid_frequency_constraint_manual_review_required:freq={n}")
        return MANUAL_REVIEW_ATOM, flags

    if re.search(r"/\s*freq\b", normalized, flags=re.IGNORECASE):
        flags.append("malformed_or_unsupported_ovid_frequency_constraint_manual_review_required")
        return MANUAL_REVIEW_ATOM, flags
    return normalized, flags


def parse_ovid_limit_alias(line: str) -> int | None:
    """Return the source row referenced by a complete Ovid ``limit N to ...`` row."""
    match = re.fullmatch(
        r"\s*limit\s+#?(?P<base>\d+)\s+to\s+(?P<condition>\S(?:.*\S)?)\s*",
        normalize_unicode(line),
        flags=re.IGNORECASE,
    )
    return int(match.group("base")) if match else None


def is_ovid_limit_like_line(line: str) -> bool:
    return (
        re.match(r"\s*limit\b", normalize_unicode(line), flags=re.IGNORECASE)
        is not None
    )


def resolve_limit_aliases(limit_aliases: dict[int, int]) -> dict[int, int]:
    """Resolve chained LIMIT aliases conservatively."""
    resolved: dict[int, int] = {}
    for source, initial_target in limit_aliases.items():
        seen: set[int] = {source}
        target = initial_target
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


def is_pure_ovid_database_update_date_line(line: str) -> bool:
    """Identify a pure numeric Ovid MEDLINE database-update date filter.

    v21 treats whole rows using ``.ed.``, ``.dt.``, ``.ed,dt.`` or
    ``.dt,ed.`` as update-search bookkeeping only when the expression before
    the suffix contains numeric date prefixes, ``*``, parentheses, ``OR`` and
    whitespace, with no clinical terms or other fields.
    """
    normalized = normalize_unicode(line).strip()
    match = re.fullmatch(
        r"(?P<body>.+?)\s*\.\s*(?:ed|dt|ed\s*,\s*dt|dt\s*,\s*ed)\s*\.?",
        normalized,
        flags=re.IGNORECASE,
    )
    if match is None:
        return False
    body = re.sub(r"\bOR\b", " ", match.group("body"), flags=re.IGNORECASE)
    return re.fullmatch(r"[\d*()\s]+", body) is not None


def group_wildcard_fielded_phrases(line: str):
    """Render safe wildcard phrases using PubMed-valid phrase-tag grouping.

    v20 may emit a wildcard-bearing multi-word free-text atom in quotes, for
    example ``\"minimal change nephr*\"[tw]``. PubMed's multi-term field-tag
    phrase syntax keeps the field tag attached to the phrase itself. v21 wraps
    that complete fielded expression for explicit grouping::

        \"A* B* C*\"[tw] -> (A* B* C*[tw])

    The field tag is therefore inside the outer parentheses. The invalid form
    ``(A* B* C*)[tw]`` must not be emitted because it attempts to qualify a
    parenthesized Boolean group rather than the multi-term phrase.

    No Boolean separator is inserted between phrase terms and the field tag is
    not duplicated per token. Literal standalone Boolean words remain quoted
    so phrase text cannot be reinterpreted as PubMed Boolean syntax.
    """
    flags: list[str] = []
    pattern = re.compile(
        r'"(?P<phrase>[^"\n]*\*[^"\n]*)"\[(?P<tag>ti|tiab|tw|all|ta)\]',
        flags=re.IGNORECASE,
    )

    def repl(match: re.Match) -> str:
        phrase = re.sub(r"\s+", " ", match.group("phrase")).strip()
        if not phrase or " " not in phrase:
            return match.group(0)
        tag = match.group("tag").lower()
        boolean_token = re.search(
            r"\b(AND|OR|NOT)\b",
            phrase,
            flags=re.IGNORECASE,
        )
        if boolean_token is not None:
            flags.append(
                "wildcard_phrase_quotes_retained_due_literal_boolean_token:"
                f"{boolean_token.group(1).upper()}:{phrase}[{tag}]"
            )
            return f'"{phrase}"[{tag}]'
        flags.append(
            f"wildcard_phrase_grouped_pubmed_phrase_tag_preserved:{phrase}[{tag}]"
        )
        return f"({phrase}[{tag}])"

    return pattern.sub(repl, line), flags


def convert_line(
    expr: str,
    known_line_numbers: set[int] | None = None,
    *,
    omit_ovid_update_dates: bool = False,
):
    """Apply v21 pre/post-processing around the frozen v20 line converter."""
    line = normalize_unicode(expr.strip())

    limit_base = parse_ovid_limit_alias(line)
    if limit_base is not None:
        return DROP_ATOM, [
            f"ovid_limit_line_ignored_redirect_to_source_#{limit_base}",
            "major_semantic_approximation_recall_broadened",
        ]
    if is_ovid_limit_like_line(line):
        return MANUAL_REVIEW_ATOM, [
            "malformed_or_unsupported_ovid_limit_line_manual_review_required"
        ]

    if is_pure_ovid_database_update_date_line(line):
        date_flags = ["ovid_database_update_date_filter_ignored"]
        if omit_ovid_update_dates:
            date_flags.append(
                "external_end_date_applied_instead_of_ovid_update_date_filter"
            )
        else:
            date_flags.extend(
                [
                    "ovid_update_date_filter_ignored_without_external_end_date",
                    "major_semantic_approximation_recall_broadened",
                ]
            )
        return DROP_ATOM, date_flags

    line, frequency_flags = strip_ovid_frequency_requirement(line)
    if line == MANUAL_REVIEW_ATOM:
        return line, frequency_flags

    line, multifield_flags = preserve_inline_ovid_multifield_free_text(line)
    converted, flags = _convert_line_v20(
        line,
        known_line_numbers=known_line_numbers,
        omit_ovid_update_dates=omit_ovid_update_dates,
    )
    converted, wildcard_flags = group_wildcard_fielded_phrases(converted)
    residue_flags = split_multifield_residue_flags(converted)
    if residue_flags:
        return MANUAL_REVIEW_ATOM, list(
            dict.fromkeys(
                frequency_flags
                + multifield_flags
                + flags
                + wildcard_flags
                + ["v21_split_multifield_suffix_manual_review_required"]
                + residue_flags
            )
        )
    return converted, list(
        dict.fromkeys(frequency_flags + multifield_flags + flags + wildcard_flags)
    )

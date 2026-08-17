from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import re
import csv
import itertools
import argparse
import unicodedata
import json
import os
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path("dataset_60_cochrane_20260621ver")
OUTPUT_VERSION = "v20"

# Version 20 maintenance corrections (16 August 2026):
# - use a v20-labelled default MeSH cache filename
# - label deterministic RTF parser metadata as v20
# - label MeSH HTTP User-Agent as v20
# - correct CLI description from Version 19 to Version 20
# These are release-label/governance corrections only; approved conversion
# semantics are unchanged. A legacy cache may still be supplied explicitly
# with --mesh-cache when required.

# Version 20 corrections (28 July 2026):
# - PubMed has no executable abstract-only [ab] field tag; every Ovid .ab.
#   expression is now mapped to PubMed Title/Abstract [tiab]
# - normalizes legacy/generated [ab] and [Abstract] tags to [tiab] during the
#   final ESearch-safe pass, including already converted input strategies
# - removes [ab] from the PubMed field whitelist so local validation cannot
#   approve a query that NCBI ESearch will reject with error "ab"
#
# Version 19 corrections (27 July 2026):
# - removes all ignorable RTF destinations (including Word themedata) before
#   text extraction so embedded Office hexadecimal payloads cannot become rows
# - accepts list numbers that are separated from their strategy expression by
#   a physical line break, preserving the first and final strategy rows
# - scopes list-number structure validation to the parsed MEDLINE row sequence
#   rather than requiring every list item in the whole document to belong to it
# - follows the project recall rule: slash headings use [mh]/[pt], never :noexp
# - unresolved MeSH/API/cache lookups fall back to the original Ovid heading
#   with an audit warning instead of destroying the query with a manual marker
# - retains original online MeSH failure reasons for the conversion audit
# - adds reviewed mapping Nephrosis Lipoid -> Nephrosis, Lipoid
# - if a pure .ed,dt. final row is omitted because End_date is supplied, the
#   last surviving substantive row becomes the final query
# - validation failures in unused rows are recorded in the audit but do not
#   invalidate the final-query dependency closure
#
# Version 18 updates (27 July 2026):
# - deterministic RTF extraction: preserves {\listtext ...} strategy numbers,
#   tracks persistent group-scoped \ucN state, decodes every \uN control, and
#   rejects row-count, row-order, reference, final-line, or RTF-residue defects
# - normalized Unicode hyphen/quote variants before strategy conversion
# - added protected hyphenated-term validation to detect deleted identifier text
# - made generated RTF Unicode-safe by writing non-ASCII text as \uN? escapes
# - NEW STRICT RULE: the complete Ovid line `(animal not human).sh.` is
#   converted exactly to `(animals[mh] NOT humans[mh])`
# - exact MeSH API/cache resolution of preferred, entry, and reviewed historical
#   headings before controlled-field tagging; unresolved/ambiguous headings fail
#   closed instead of silently becoming guessed [mh] expressions
# - controlled headings follow the recall-oriented [mh]/[pt] project rule
# - applicable exploded pharmacological-action headings use ([mh] OR [pa])
# - explicit historical study-design mappings distinguish topical descriptors
#   from publication types
# - pure .ed,dt. update lines are omitted only when an external End_date exists;
#   dependent Boolean references are simplified and the omission is audited
# - Ovid runtime stopwords are removed only from free-text field expressions;
#   remaining distinct terms are ANDed and repeated terms are deduplicated
# - all Version 17 conversion rules below are retained
#
# Version 17 rules retained:
# - main MeSH descriptor only; attached slash subheadings are ignored
# - strict slash/Boolean boundary so OR cannot become a subheading
# - wildcard-bearing slash atoms fall back to free text [tw]
# - short-root truncation uses curated morphology/acronym/identifier rules
# - unknown short-root truncation is literalized rather than deleted
# - internal short-prefix wildcards are collapsed conservatively
# - ? and # are parsed separately, with curated interpretation before generic expansion
# - hyphenated anti-?estrogen spelling is mapped to anti-estrogen / anti-oestrogen
# - exact slash publication-type headings use a closed whitelist
# - local syntax/reference validation and Windows-friendly CLI

MESH_API_BASE = "https://id.nlm.nih.gov/mesh"
DEFAULT_MESH_CACHE_NAME = "mesh_resolution_cache_v20_YW_16082026.json"
MESH_CACHE_SCHEMA_VERSION = 1

# Ovid MEDLINE run-time stopwords. These are applied only after an expression
# has been classified as free text; they are never removed from MeSH headings,
# entry terms, publication types, subheadings, or other controlled objects.
OVID_RUNTIME_STOPWORDS = {
    "and", "as", "for", "from", "is", "of",
    "that", "the", "this", "to", "was", "were",
}

# Reviewed source-label aliases whose current preferred labels have changed.
# The current preferred target is still resolved through the MeSH API/cache so
# its UID, record class, and pharmacological-action status remain verifiable.
HISTORICAL_MESH_ALIASES = {
    "heart failure, congestive": "Heart Failure",
    "conscious sedation": "Procedural Sedation",
    "pain, postoperative": "Postoperative Pain",
    "randomized controlled trials": "Randomized Controlled Trials as Topic",
    "clinical trials": "Clinical Trials as Topic",
    "evaluation studies": "Evaluation Studies as Topic",
    "fracture, bone": "Fractures, Bone",
    "double blind method": "Double-Blind Method",
    "follow up studies": "Follow-Up Studies",
    "nephrosis lipoid": "Nephrosis, Lipoid",
}

OPTIONAL_SINGLE_CHAR_VARIANTS = [""] + list("abcdefghijklmnopqrstuvwxyz")
MANDATORY_SINGLE_CHAR_VARIANTS = list("abcdefghijklmnopqrstuvwxyz")
MAX_GENERIC_SINGLE_CHAR_EXPANSIONS = 729

# Curated whole-atom exceptions are applied before generic ?/# expansion.
# Keys are lower-case normalized Ovid atoms. Values preserve any later
# truncation marker so Rule 4 can process it normally.
SINGLE_CHAR_WILDCARD_SPECIAL_EXCEPTIONS = {
    "isch?emi$": ["ischemi$", "ischaemi$"],
    "randomi?ed": ["randomised", "randomized"],
    "?estrogen$": ["estrogen$", "oestrogen$"],
    "?estrogen*": ["estrogen*", "oestrogen*"],
    "?estrogen": ["estrogen", "oestrogen"],
    "anti-?estrogen$": ["anti-estrogen$", "anti-oestrogen$"],
    "anti-?estrogen*": ["anti-estrogen*", "anti-oestrogen*"],
    "anti-?estrogen": ["anti-estrogen", "anti-oestrogen"],
    "?estradiol": ["estradiol", "oestradiol"],
    "?esophagus": ["esophagus", "oesophagus"],
    "shon?s": ["shones", "shone's", "shone"],
}

STOP_HEADINGS = {
    "embase:",
    "pubmed:",
    "central:",
    "cochrane:",
    "cinahl:",
    "scopus:",
    "web of science:",
}


# MeSH / MEDLINE floating subheading abbreviations used by Rules 7 and 9.
MESH_SUBHEADING_MAP = {
    "ad": "administration and dosage",
    "ae": "adverse effects",
    "ag": "agonists",
    "an": "analysis",
    "bl": "blood",
    "cf": "cerebrospinal fluid",
    "ch": "chemistry",
    "ci": "chemically induced",
    "cl": "classification",
    "co": "complications",
    "ct": "contraindications",
    "dh": "diet therapy",
    "di": "diagnosis",
    "dt": "drug therapy",
    "ec": "economics",
    "eh": "ethnology",
    "em": "embryology",
    "en": "enzymology",
    "ep": "epidemiology",
    "es": "ethics",
    "et": "etiology",
    "ge": "genetics",
    "hi": "history",
    "im": "immunology",
    "me": "metabolism",
    "mi": "microbiology",
    "mo": "mortality",
    "nu": "nursing",
    "pa": "pathology",
    "pc": "prevention and control",
    "pd": "pharmacology",
    "ph": "physiology",
    "pk": "pharmacokinetics",
    "po": "poisoning",
    "pp": "physiopathology",
    "px": "psychology",
    "ra": "radiography",
    "rh": "rehabilitation",
    "ri": "radionuclide imaging",
    "rt": "radiotherapy",
    "su": "surgery",
    "th": "therapy",
    "tu": "therapeutic use",
    "ul": "ultrastructure",
    "ur": "urine",
    "vi": "virology",
}


# PubMed Comments/Corrections relation search tokens for Ovid MEDLINE .cm.
# These are special relation tokens, not PubMed field tags.
COMMENT_CORRECTION_CM_MAP = {
    "comment in": "hascommentin",
    "comment on": "hascommenton",
    "corrected and republished in": "hascorrectedrepublishedin",
    "corrected and republished from": "hascorrectedrepublishedfrom",
    "dataset use reported in": "hasassociatedpublication",
    "dataset described in": "hasassociateddataset",
    "erratum in": "haserratumin",
    "erratum for": "haserratumfor",
    "expression of concern in": "hasexpressionofconcernin",
    "expression of concern for": "hasexpressionofconcernfor",
    "original report in": "hasoriginalreportin",
    "republished in": "hasrepublishedin",
    "republished from": "hasrepublishedfrom",
    "retracted and republished in": "hasretractedandrepublishedin",
    "retracted and republished from": "hasretractedandrepublishedfrom",
    "retraction in": "hasretractionin",
    "retraction of": "hasretractionof",
    "summary for patients in": "hassummaryforpatientsin",
    "update in": "hasupdatein",
    "update of": "hasupdateof",
}

COMMENT_CORRECTION_CM_TOKENS = set(COMMENT_CORRECTION_CM_MAP.values())

STRICT_ANIMAL_ONLY_FILTER_RE = re.compile(
    r"\(\s*animal\s+not\s+human\s*\)\s*\.sh\.?",
    flags=re.I,
)

# Terms containing both a hyphen and alphanumeric material are especially
# vulnerable to the historical RTF Unicode bug (for example MDX-1106 and
# anti-PD-L1). They must remain present after conversion.
PROTECTED_HYPHENATED_TERM_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?=[A-Za-z0-9-]*[A-Za-z])"
    r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+"
    r"(?:[$*]\d*)?"
    r"(?![A-Za-z0-9])"
)


# ---------------------------------------------------------------------
# RTF IO
# ---------------------------------------------------------------------

def _skip_one_rtf_fallback_character(raw: str, index: int) -> int:
    """
    Skip one ANSI fallback character following an RTF ``\\uN`` control.

    A fallback character may be a literal character, a hex escape such as
    ``\\'96``, or an escaped RTF symbol such as ``\\-``. Formatting-group
    braces are not consumed as fallback text.
    """
    if index >= len(raw):
        return index

    if raw[index] in "{}":
        return index

    if raw[index] != "\\":
        return index + 1

    if index + 1 >= len(raw):
        return index + 1

    symbol = raw[index + 1]
    if symbol == "'" and index + 3 < len(raw):
        if re.fullmatch(r"[0-9a-fA-F]{2}", raw[index + 2:index + 4]):
            return index + 4

    if symbol in r"\{}~-_":
        return index + 2

    # A control word can itself represent one fallback character.
    if symbol.isalpha():
        cursor = index + 1
        while cursor < len(raw) and raw[cursor].isalpha():
            cursor += 1
        if cursor < len(raw) and raw[cursor] in "+-":
            cursor += 1
        while cursor < len(raw) and raw[cursor].isdigit():
            cursor += 1
        if cursor < len(raw) and raw[cursor] == " ":
            cursor += 1
        return cursor

    return min(index + 2, len(raw))


def decode_rtf_unicode_controls(raw: str) -> str:
    """
    Decode RTF Unicode controls while preserving group-scoped ``\\ucN`` state.

    RTF's ``\\ucN`` setting persists until the current group ends. Version 17
    decoded only the first ``\\uc0\\uN`` pair and removed the persistent
    ``\\uc0`` instruction. A later parser could therefore delete the first
    character following each subsequent ``\\uN`` control. This state-aware
    scanner handles every Unicode control before the main RTF-to-text pass.
    """
    output: list[str] = []
    uc_stack = [1]
    index = 0

    while index < len(raw):
        char = raw[index]

        if char == "{":
            output.append(char)
            uc_stack.append(uc_stack[-1])
            index += 1
            continue

        if char == "}":
            output.append(char)
            if len(uc_stack) > 1:
                uc_stack.pop()
            index += 1
            continue

        if char != "\\" or index + 1 >= len(raw):
            output.append(char)
            index += 1
            continue

        next_char = raw[index + 1]
        if next_char in r"\{}":
            output.append(raw[index:index + 2])
            index += 2
            continue

        if not next_char.isalpha():
            output.append(raw[index:index + 2])
            index += 2
            continue

        word_end = index + 1
        while word_end < len(raw) and raw[word_end].isalpha():
            word_end += 1
        control_word = raw[index + 1:word_end].lower()

        parameter_end = word_end
        if parameter_end < len(raw) and raw[parameter_end] in "+-":
            parameter_end += 1
        digits_start = parameter_end
        while parameter_end < len(raw) and raw[parameter_end].isdigit():
            parameter_end += 1

        parameter = None
        if parameter_end > digits_start:
            parameter = int(raw[word_end:parameter_end])

        control_end = parameter_end
        if control_end < len(raw) and raw[control_end] == " ":
            control_end += 1

        if control_word == "uc" and parameter is not None:
            uc_stack[-1] = max(0, parameter)
            index = control_end
            continue

        if control_word == "u" and parameter is not None:
            code_unit = parameter if parameter >= 0 else parameter + 65536
            if 0 <= code_unit <= 65535:
                output.append(chr(code_unit))

            index = control_end
            fallback_remaining = uc_stack[-1]
            while fallback_remaining > 0 and index < len(raw):
                new_index = _skip_one_rtf_fallback_character(raw, index)
                if new_index == index:
                    break
                index = new_index
                fallback_remaining -= 1
            continue

        output.append(raw[index:control_end])
        index = control_end

    # Join any valid UTF-16 surrogate pairs emitted by consecutive RTF
    # Unicode controls; replace only genuinely unpaired surrogates.
    return (
        "".join(output)
        .encode("utf-16-le", errors="surrogatepass")
        .decode("utf-16-le", errors="replace")
    )


def clean_extracted_text(text: str) -> str:
    lines = [x.strip() for x in text.replace("\r", "\n").splitlines() if x.strip()]

    start = 0
    for i, line in enumerate(lines):
        if line.lower().startswith(("title:", "objectives:", "p:", "medline:", "pubmed:")):
            start = i
            break

    return "\n".join(lines[start:])


def preserve_rtf_listtext_numbers(raw: str):
    """
    Replace every RTF ``{\\listtext ...}`` destination with visible numbering.

    General RTF readers are allowed to discard ``listtext`` destinations. That
    behaviour is correct for prose documents but destructive for numbered Ovid
    strategies because the list label is the strategy line identifier. This
    balanced-group scanner runs before all other RTF stripping.
    """
    output: list[str] = []
    numbers: list[int] = []
    index = 0
    marker_re = re.compile(r"\{\\listtext\b", flags=re.I)

    while index < len(raw):
        match = marker_re.search(raw, index)
        if match is None:
            output.append(raw[index:])
            break

        output.append(raw[index:match.start()])
        depth = 0
        cursor = match.start()
        in_escape = False

        while cursor < len(raw):
            char = raw[cursor]
            if in_escape:
                in_escape = False
            elif char == "\\":
                in_escape = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            cursor += 1

        if depth != 0:
            raise ValueError("Unbalanced RTF listtext group")

        group = raw[match.start():cursor]
        visible = re.sub(r"\\[A-Za-z]+-?\d*\s?", " ", group)
        visible = visible.replace("{", " ").replace("}", " ").replace("\\", " ")
        number_match = re.search(r"(?<!\d)(\d+)\s*[\.)]?", visible)
        if number_match is None:
            raise ValueError(f"RTF listtext group has no numeric label: {group[:120]!r}")

        number = int(number_match.group(1))
        numbers.append(number)
        output.append(f"{number}.\\tab ")
        index = cursor

    return "".join(output), numbers


def remove_ignorable_rtf_destinations(raw: str):
    r"""
    Remove complete RTF ignorable destinations such as ``{\*\themedata ...}``.

    Word stores themes, list tables, XML namespaces, generator metadata, and
    other non-visible payloads in groups beginning ``{\*``. Removing only the
    control word while retaining the group body leaks binary/hexadecimal data
    into the extracted strategy. ``listtext`` labels have already been made
    visible by ``preserve_rtf_listtext_numbers`` and are not ignorable groups.
    """
    output: list[str] = []
    removed_destinations: list[str] = []
    index = 0
    marker_re = re.compile(r"\{\\\*\\(?P<name>[A-Za-z]+)", flags=re.I)

    while index < len(raw):
        match = marker_re.search(raw, index)
        if match is None:
            output.append(raw[index:])
            break

        output.append(raw[index:match.start()])
        depth = 0
        cursor = match.start()
        escaped = False

        while cursor < len(raw):
            char = raw[cursor]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    cursor += 1
                    break
            cursor += 1

        if depth != 0:
            raise ValueError(
                f"Unbalanced ignorable RTF destination: {match.group('name')}"
            )

        removed_destinations.append(match.group("name").lower())
        # Retain a separator so adjacent visible text cannot be concatenated.
        output.append("\n")
        index = cursor

    return "".join(output), removed_destinations


def _decode_rtf_hex_escape(match: re.Match) -> str:
    byte = bytes([int(match.group(1), 16)])
    return byte.decode("cp1252", errors="replace")


def rtf_to_text_deterministic(raw: str) -> str:
    """
    Convert the simple RTF used by the Cochrane source files to plain text.

    This intentionally avoids an optional parser whose handling of
    ``listtext`` changed the strategy structure. The extractor preserves
    physical line breaks used by the source files and removes formatting
    controls only after Unicode, list numbering, escaped characters, and
    explicit ``\\par``/``\\line`` breaks have been handled.
    """
    placeholders = {
        r"\\": "\ue000",
        r"\{": "\ue001",
        r"\}": "\ue002",
    }
    for source, target in placeholders.items():
        raw = raw.replace(source, target)

    raw = re.sub(r"\\'([0-9a-fA-F]{2})", _decode_rtf_hex_escape, raw)
    raw = re.sub(r"\\par(?![A-Za-z])\s?", "\n", raw)
    raw = re.sub(r"\\line(?![A-Za-z])\s?", "\n", raw)
    raw = re.sub(r"\\tab(?![A-Za-z])\s?", "\t", raw)
    raw = raw.replace(r"\~", " ").replace(r"\_", "-").replace(r"\-", "")

    named_symbols = {
        "emdash": "-",
        "endash": "-",
        "lquote": "'",
        "rquote": "'",
        "ldblquote": '"',
        "rdblquote": '"',
        "bullet": " ",
    }
    for control, replacement in named_symbols.items():
        raw = re.sub(rf"\\{control}(?![A-Za-z])\s?", replacement, raw, flags=re.I)

    # TextEdit-style source files use a lone backslash immediately before a
    # physical newline. It is structural RTF punctuation, not visible text.
    raw = re.sub(r"\\(?=\r?\n)", "", raw)

    # Parameters may be negative (for example ``\\fi-720``). Matching the
    # complete control word prevents the old ``\\par`` substitution from
    # leaving ``eftab720`` or ``tightenfactor0`` behind.
    raw = re.sub(r"\\[A-Za-z]+-?\d*\s?", "", raw)
    raw = raw.replace("{", "").replace("}", "")

    raw = (
        raw.replace("\ue000", "\\")
        .replace("\ue001", "{")
        .replace("\ue002", "}")
    )
    raw = re.sub(r"\n+", "\n", raw)
    return raw


def read_rtf_as_text_with_metadata(path: Path):
    data = path.read_bytes()
    declaration = re.search(rb"\\ansicpg(\d+)", data[:4096], flags=re.I)
    codepage = int(declaration.group(1)) if declaration else 1252
    # Some historical project files contain UTF-8 bytes despite an ANSI
    # header. Prefer strict UTF-8 only when the complete byte stream is valid;
    # otherwise honour the declared ANSI code page without discarding bytes.
    try:
        raw = data.decode("utf-8", errors="strict")
        byte_encoding = "utf-8-compatibility"
    except UnicodeDecodeError:
        encoding = "cp1252" if codepage == 1252 else f"cp{codepage}"
        try:
            raw = data.decode(encoding, errors="strict")
        except LookupError as exc:
            raise ValueError(f"unsupported_rtf_ansi_code_page:{codepage}") from exc
        byte_encoding = encoding
    raw, list_numbers = preserve_rtf_listtext_numbers(raw)
    raw, ignored_destinations = remove_ignorable_rtf_destinations(raw)
    raw = decode_rtf_unicode_controls(raw)
    text = clean_extracted_text(rtf_to_text_deterministic(raw))
    return text, {
        "parser": "builtin_deterministic_v20",
        "list_item_count": len(list_numbers),
        "list_numbers": list_numbers,
        "ignored_destination_count": len(ignored_destinations),
        "ignored_destinations": ignored_destinations,
        "ansi_code_page": codepage,
        "byte_encoding": byte_encoding,
    }


def read_rtf_as_text(path: Path) -> str:
    """Backward-compatible text-only wrapper."""
    text, _metadata = read_rtf_as_text_with_metadata(path)
    return text


def _escape_text_for_rtf(text: str) -> str:
    escaped: list[str] = []
    for char in text:
        if char == "\n":
            escaped.append("\\par\n")
        elif char == "\t":
            escaped.append("\\tab ")
        elif char in r"\{}":
            escaped.append("\\" + char)
        elif 32 <= ord(char) <= 126:
            escaped.append(char)
        else:
            utf16 = char.encode("utf-16-le")
            for offset in range(0, len(utf16), 2):
                code_unit = int.from_bytes(utf16[offset:offset + 2], "little")
                signed = code_unit if code_unit < 32768 else code_unit - 65536
                escaped.append(f"\\u{signed}?")
    return "".join(escaped)


def write_rtf(path: Path, text: str) -> None:
    body = _escape_text_for_rtf(text)
    path.write_text(
        "{\\rtf1\\ansi\\ansicpg1252\\uc1\n" + body + "\n}",
        encoding="ascii",
    )


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def normalize_unicode(line: str) -> str:
    line = unicodedata.normalize("NFKC", line)
    replacements = {
        "‐": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
        "‑": "-", "﹘": "-", "﹣": "-", "－": "-",
        "’": "'", "‘": "'", "‚": "'", "‛": "'",
        "“": '"', "”": '"', "„": '"',
        "\u00a0": " ", "\u2007": " ", "\u202f": " ",
        "â€™": "'", "â€˜": "'", "â€œ": '"', "â€": '"',
        "â€“": "-", "â€”": "-",
    }
    for source, target in replacements.items():
        line = line.replace(source, target)
    return line


def tidy_spaces(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    line = re.sub(r"\s+\)", ")", line)
    line = re.sub(r"\(\s+", "(", line)
    return line


def normalize_boolean_outside_quotes(line: str) -> str:
    """
    Normalize Boolean operators only outside double-quoted strings.
    This prevents:
        "Anesthesia and Analgesia"[Mesh]
    from becoming:
        "Anesthesia AND Analgesia"[Mesh]
    """
    parts = re.split(r'("[^"]*")', line)

    for i in range(0, len(parts), 2):
        parts[i] = re.sub(r"\band\b", "AND", parts[i], flags=re.I)
        parts[i] = re.sub(r"\bor\b", "OR", parts[i], flags=re.I)
        parts[i] = re.sub(r"\bnot\b", "NOT", parts[i], flags=re.I)

    return "".join(parts)


def is_strict_animal_only_filter(line: str) -> bool:
    """Return True only for the complete legacy Ovid animal-only filter line."""
    return STRICT_ANIMAL_ONLY_FILTER_RE.fullmatch(line.strip()) is not None


def is_pure_ovid_ed_dt_update_line(line: str) -> bool:
    """
    Identify a whole-line Boolean list of numeric date prefixes in .ed,dt.

    The rule is intentionally narrow: concept terms, other fields, AND/NOT, or
    mixed text prevent omission.
    """
    match = re.fullmatch(
        r"(?P<body>.+?)\s*\.(?:ed\s*,\s*dt|dt\s*,\s*ed)\.?",
        line.strip(),
        flags=re.I,
    )
    if match is None:
        return False
    body = re.sub(r"\bOR\b", " ", match.group("body"), flags=re.I)
    return re.fullmatch(r"[\d*()\s]+", body) is not None


def validate_protected_hyphenated_terms(
    original: str, converted: str, audit_flags: list[str] | None = None
) -> list[str]:
    """
    Confirm that hyphenated terms survive the Ovid-to-PubMed conversion.

    Truncation markers are excluded from the comparison because Ovid ``$`` may
    legitimately become PubMed ``*``. Case and Unicode hyphen style are also
    normalized before comparison.
    """
    normalized_original = normalize_unicode(original)
    normalized_converted = normalize_unicode(converted).casefold()
    errors = []
    verified_mesh_rename = any(
        flag.startswith("mesh_resolved:") for flag in (audit_flags or [])
    )

    for match in PROTECTED_HYPHENATED_TERM_RE.finditer(normalized_original):
        original_term = match.group(0)
        comparison_term = re.sub(r"[$*]\d*$", "", original_term).casefold()
        if (
            comparison_term
            and comparison_term not in normalized_converted
            and not verified_mesh_rename
        ):
            errors.append(f"protected_hyphenated_term_not_preserved:{original_term}")

    return list(dict.fromkeys(errors))


# ---------------------------------------------------------------------
# MeSH controlled-vocabulary resolver
# ---------------------------------------------------------------------

def normalize_mesh_lookup_label(label: str) -> str:
    """Normalize typography and spacing without deleting or reordering words."""
    label = normalize_unicode(label).strip().strip('"')
    return re.sub(r"\s+", " ", label).strip()


def _mesh_cache_key(label: str) -> str:
    return normalize_mesh_lookup_label(label).casefold()


class MeshResolver:
    """
    Resolve exact MeSH preferred/entry/historical headings and record classes.

    The resolver deliberately does not use fuzzy or nearest-term matching. It
    caches the canonical label, UID, descriptor class, match type, MeSH year,
    and whether the descriptor is used as a pharmacological-action target.
    """

    def __init__(self, cache_path: Path | None = None, mode: str = "online", timeout: float = 30.0):
        if mode not in {"online", "cache-only"}:
            raise ValueError("MeSH mode must be 'online' or 'cache-only'")
        self.cache_path = cache_path
        self.mode = mode
        self.timeout = timeout
        self.mesh_year: int | None = None
        self.records: dict[str, dict] = {}
        # Successful mappings are persisted in ``records``. Unsuccessful
        # results from the current online preflight remain available here so
        # the conversion audit reports the real API/lookup reason rather than
        # replacing it with a generic cache miss.
        self.session_results: dict[str, dict] = {}
        self.dirty = False
        self._load()

    def _load(self) -> None:
        if self.cache_path is None or not self.cache_path.exists():
            return
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Cannot read MeSH cache {self.cache_path}: {exc}") from exc
        if payload.get("schema_version") != MESH_CACHE_SCHEMA_VERSION:
            raise RuntimeError(
                f"Unsupported MeSH cache schema in {self.cache_path}: "
                f"{payload.get('schema_version')!r}"
            )
        self.mesh_year = payload.get("mesh_year")
        records = payload.get("records", {})
        if not isinstance(records, dict):
            raise RuntimeError(f"Invalid MeSH cache records in {self.cache_path}")
        self.records = records

    def flush(self) -> None:
        if not self.dirty or self.cache_path is None:
            return
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": MESH_CACHE_SCHEMA_VERSION,
            "mesh_year": self.mesh_year,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "source": "NLM MeSH RDF Lookup and SPARQL APIs",
            "records": dict(sorted(self.records.items())),
        }
        temporary = self.cache_path.with_suffix(self.cache_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.cache_path)
        self.dirty = False

    def _request_json(self, path: str, params: dict) -> object:
        url = f"{MESH_API_BASE}/{path}?{urlencode(params)}"
        retryable_error: Exception | None = None
        for attempt in range(4):
            request = Request(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "Cochrane-Ovid-PubMed-Converter-v20/1.0",
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise RuntimeError(f"MeSH API request failed for {path}: {exc}") from exc
                retryable_error = exc
            except (URLError, TimeoutError, OSError) as exc:
                retryable_error = exc
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"MeSH API returned invalid JSON for {path}: {exc}") from exc

            if attempt < 3:
                time.sleep(1.5 * (2 ** attempt))

        raise RuntimeError(
            f"MeSH API request failed after retries for {path}: {retryable_error}"
        ) from retryable_error

    def _ensure_mesh_year(self) -> None:
        if self.mesh_year is not None or self.mode != "online":
            return
        payload = self._request_json("lookup/years", {})
        if isinstance(payload, dict):
            current = payload.get("current")
        elif (
            isinstance(payload, list)
            and payload
            and payload[0] == "current"
            and len(payload) >= 2
        ):
            current = payload[1]
        else:
            current = None
        try:
            current_year = int(current)
        except (TypeError, ValueError):
            raise RuntimeError("MeSH API did not return a valid current vocabulary year")
        self.mesh_year = current_year
        self.dirty = True

    def _descriptor_metadata(self, descriptor_uri: str):
        classes = (
            "meshv:TopicalDescriptor meshv:PublicationType "
            "meshv:CheckTag meshv:GeographicalDescriptor"
        )
        query = f"""
PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?label ?class ?isPA WHERE {{
  <{descriptor_uri}> rdfs:label ?label ; a ?class .
  VALUES ?class {{ {classes} }}
  BIND(EXISTS {{
    ?substance meshv:pharmacologicalAction <{descriptor_uri}>
  }} AS ?isPA)
}}
""".strip()
        payload = self._request_json(
            "sparql",
            {
                "query": query,
                "format": "JSON",
                "inference": "false",
                "limit": 20,
            },
        )
        return self._parse_sparql_descriptor_rows(payload)

    @staticmethod
    def _parse_sparql_descriptor_rows(payload: object):
        try:
            bindings = payload["results"]["bindings"]  # type: ignore[index]
        except (KeyError, TypeError):
            raise RuntimeError("MeSH SPARQL response has no result bindings")

        rows = []
        for binding in bindings:
            label = binding.get("label", {}).get("value")
            class_uri = binding.get("class", {}).get("value")
            is_pa_value = binding.get("isPA", {}).get("value", "0")
            descriptor_uri = binding.get("descriptor", {}).get("value")
            if not label or not class_uri:
                continue
            rows.append({
                "canonical_label": label,
                "record_class": class_uri.rsplit("#", 1)[-1],
                "is_pharmacological_action": str(is_pa_value).lower() in {"1", "true"},
                "descriptor_uri": descriptor_uri,
            })
        return rows

    def _map_terms_to_descriptors(self, term_uris: list[str]):
        values = " ".join(f"<{uri}>" for uri in sorted(set(term_uris)))
        classes = (
            "meshv:TopicalDescriptor meshv:PublicationType "
            "meshv:CheckTag meshv:GeographicalDescriptor"
        )
        query = f"""
PREFIX meshv: <http://id.nlm.nih.gov/mesh/vocab#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?descriptor ?label ?class ?isPA WHERE {{
  VALUES ?term {{ {values} }}
  ?descriptor meshv:concept ?concept ;
              rdfs:label ?label ;
              a ?class .
  VALUES ?class {{ {classes} }}
  ?concept (meshv:preferredTerm|meshv:term) ?term .
  BIND(EXISTS {{
    ?substance meshv:pharmacologicalAction ?descriptor
  }} AS ?isPA)
}}
""".strip()
        payload = self._request_json(
            "sparql",
            {
                "query": query,
                "format": "JSON",
                "inference": "false",
                "limit": 50,
            },
        )
        return self._parse_sparql_descriptor_rows(payload)

    def _exact_lookup(self, source_label: str):
        original = normalize_mesh_lookup_label(source_label)
        alias_target = HISTORICAL_MESH_ALIASES.get(original.casefold())
        lookup_label = alias_target or original
        forced_match_type = "historical" if alias_target else None

        descriptor_matches = self._request_json(
            "lookup/descriptor",
            {"label": lookup_label, "match": "exact", "limit": 20},
        )
        if not isinstance(descriptor_matches, list):
            raise RuntimeError("MeSH descriptor lookup returned a non-list response")

        descriptor_uris = sorted({
            item.get("resource")
            for item in descriptor_matches
            if isinstance(item, dict) and item.get("resource")
        })
        if len(descriptor_uris) > 1:
            return {
                "status": "ambiguous",
                "reason": "multiple_exact_descriptor_matches",
                "candidate_uris": descriptor_uris,
            }

        match_type = forced_match_type
        if descriptor_uris:
            rows = self._descriptor_metadata(descriptor_uris[0])
            if len(rows) != 1:
                return {
                    "status": "ambiguous",
                    "reason": "descriptor_metadata_not_unique",
                    "candidate_uris": descriptor_uris,
                }
            row = rows[0]
            descriptor_uri = descriptor_uris[0]
            if match_type is None:
                match_type = (
                    "preferred"
                    if _mesh_cache_key(row["canonical_label"]) == _mesh_cache_key(original)
                    else "entry"
                )
        else:
            term_matches = self._request_json(
                "lookup/term",
                {"label": original, "match": "exact", "limit": 20},
            )
            if not isinstance(term_matches, list):
                raise RuntimeError("MeSH term lookup returned a non-list response")
            term_uris = sorted({
                item.get("resource")
                for item in term_matches
                if isinstance(item, dict) and item.get("resource")
            })
            if not term_uris:
                return {"status": "unresolved", "reason": "no_exact_preferred_or_entry_match"}
            rows = self._map_terms_to_descriptors(term_uris)
            unique = {
                (
                    row.get("descriptor_uri"),
                    row.get("canonical_label"),
                    row.get("record_class"),
                    row.get("is_pharmacological_action"),
                )
                for row in rows
            }
            if len(unique) != 1:
                return {
                    "status": "ambiguous",
                    "reason": "entry_term_maps_to_multiple_descriptors",
                    "candidate_uris": sorted(
                        {row.get("descriptor_uri") for row in rows if row.get("descriptor_uri")}
                    ),
                }
            row = rows[0]
            descriptor_uri = row["descriptor_uri"]
            match_type = forced_match_type or "entry"

        descriptor_id = descriptor_uri.rstrip("/").rsplit("/", 1)[-1]
        return {
            "status": "resolved",
            "source_label": original,
            "matched_label": lookup_label,
            "match_type": match_type,
            "canonical_label": row["canonical_label"],
            "descriptor_id": descriptor_id,
            "descriptor_uri": descriptor_uri,
            "record_class": row["record_class"],
            "is_pharmacological_action": bool(row["is_pharmacological_action"]),
            "mesh_year": self.mesh_year,
        }

    def resolve(self, source_label: str):
        key = _mesh_cache_key(source_label)
        cached = self.records.get(key)
        if cached is not None:
            return dict(cached)
        session_result = self.session_results.get(key)
        if session_result is not None:
            return dict(session_result)
        if self.mode == "cache-only":
            return {
                "status": "unresolved",
                "reason": "cache_miss_in_cache_only_mode",
                "source_label": normalize_mesh_lookup_label(source_label),
            }

        try:
            self._ensure_mesh_year()
            result = self._exact_lookup(source_label)
        except RuntimeError as exc:
            return {
                "status": "unresolved",
                "reason": "mesh_api_unavailable",
                "detail": str(exc),
                "source_label": normalize_mesh_lookup_label(source_label),
            }

        if result.get("status") == "resolved":
            self.records[key] = dict(result)
            self.dirty = True
        return result

    def prefetch(self, source_labels, max_workers: int = 4) -> dict[str, dict]:
        """
        Resolve a bounded batch concurrently, then persist successful mappings.

        Conversion itself remains deterministic and cache-based after this
        preflight. Exact lookup semantics are unchanged; concurrency only
        reduces network latency for large strategies.
        """
        labels_by_key = {
            _mesh_cache_key(label): normalize_mesh_lookup_label(label)
            for label in source_labels
            if normalize_mesh_lookup_label(label)
        }
        missing = {
            key: label
            for key, label in labels_by_key.items()
            if key not in self.records
        }
        if not missing or self.mode == "cache-only":
            return {
                key: dict(self.records.get(key, {
                    "status": "unresolved",
                    "reason": "cache_miss_in_cache_only_mode",
                    "source_label": label,
                }))
                for key, label in labels_by_key.items()
            }

        try:
            self._ensure_mesh_year()
        except RuntimeError as exc:
            failed = {
                key: {
                    "status": "unresolved",
                    "reason": "mesh_api_unavailable",
                    "detail": str(exc),
                    "source_label": label,
                }
                for key, label in labels_by_key.items()
            }
            self.session_results.update({key: dict(value) for key, value in failed.items()})
            return failed

        fetched: dict[str, dict] = {}

        def worker(key: str, label: str):
            try:
                return key, self._exact_lookup(label)
            except RuntimeError as exc:
                return key, {
                    "status": "unresolved",
                    "reason": "mesh_api_unavailable",
                    "detail": str(exc),
                    "source_label": label,
                }

        with ThreadPoolExecutor(max_workers=max(1, min(max_workers, 3))) as pool:
            futures = [
                pool.submit(worker, key, label)
                for key, label in missing.items()
            ]
            for future in as_completed(futures):
                key, result = future.result()
                fetched[key] = result
                self.session_results[key] = dict(result)
                if result.get("status") == "resolved":
                    self.records[key] = dict(result)
                    self.dirty = True

        # Persist the completed preflight before line-by-line conversion.
        self.flush()
        output = {}
        for key, label in labels_by_key.items():
            output[key] = dict(
                self.records.get(
                    key,
                    fetched.get(
                        key,
                        {
                            "status": "unresolved",
                            "reason": "prefetch_did_not_return_a_result",
                            "source_label": label,
                        },
                    ),
                )
            )
        # Keep both successful and unsuccessful preflight outcomes available
        # during the subsequent cache-only conversion pass.
        self.session_results.update({key: dict(value) for key, value in output.items()})
        return output


ACTIVE_MESH_RESOLVER: MeshResolver | None = None  # Legacy inspection compatibility.
_MESH_RESOLVER_CONTEXT: ContextVar[MeshResolver | None] = ContextVar(
    "mesh_resolver", default=None
)


def configure_mesh_resolver(cache_path: Path | None, mode: str = "online") -> MeshResolver:
    global ACTIVE_MESH_RESOLVER
    ACTIVE_MESH_RESOLVER = MeshResolver(cache_path=cache_path, mode=mode)
    _MESH_RESOLVER_CONTEXT.set(ACTIVE_MESH_RESOLVER)
    return ACTIVE_MESH_RESOLVER


def get_mesh_resolver() -> MeshResolver:
    global ACTIVE_MESH_RESOLVER
    contextual = _MESH_RESOLVER_CONTEXT.get()
    if contextual is not None:
        return contextual
    if ACTIVE_MESH_RESOLVER is None:
        ACTIVE_MESH_RESOLVER = MeshResolver(cache_path=None, mode="online")
    return ACTIVE_MESH_RESOLVER


@contextmanager
def mesh_resolver_context(resolver: MeshResolver):
    """Bind a resolver to only the current thread/task conversion context."""
    token = _MESH_RESOLVER_CONTEXT.set(resolver)
    try:
        yield resolver
    finally:
        _MESH_RESOLVER_CONTEXT.reset(token)


# ---------------------------------------------------------------------
# Rule 1. Process single-character wildcards ? and #
# ---------------------------------------------------------------------

def _preserve_initial_case(source: str, value: str) -> str:
    if source[:1].isupper() and value:
        return value[:1].upper() + value[1:]
    return value


def _regular_plural(word: str) -> str:
    """Return a conservative regular English plural for terminal ? handling."""
    lower = word.lower()
    if re.search(r"(?:s|x|z|ch|sh)$", lower):
        return word + "es"
    if re.search(r"[^aeiou]y$", lower):
        return word[:-1] + ("IES" if word[-1:].isupper() else "ies")
    return word + "s"


def _curated_single_char_variants(atom: str, flags: list[str] | None = None) -> list[str] | None:
    """Apply special, UK/US spelling, plural, and irregular rules first."""
    stripped = atom.strip()
    key = stripped.lower()

    if key in SINGLE_CHAR_WILDCARD_SPECIAL_EXCEPTIONS:
        values = [_preserve_initial_case(stripped, x) for x in SINGLE_CHAR_WILDCARD_SPECIAL_EXCEPTIONS[key]]
        if flags is not None:
            flags.append(f"single_char_wildcard_special_exception_applied:{atom}")
        return values

    # Irregular woman/women pattern. # is mandatory, but both source spellings
    # are retained because this has been an explicit project exception.
    irregular = re.search(r"wom[?#]n", stripped, flags=re.I)
    if irregular:
        original = irregular.group(0)
        forms = ["Woman", "Women"] if original[:1].isupper() else ["woman", "women"]
        values = [stripped[:irregular.start()] + form + stripped[irregular.end():] for form in forms]
        if flags is not None:
            flags.append(f"short_root_irregular_plural_expanded_using_curated_dictionary:{atom}")
        return values

    # Generic UK/US -ise/-ize family. This covers organi#ation*, organi#e*,
    # centrali#ed, traumati#ed, desensiti#ation, and randomi?ed.
    m = re.fullmatch(r"(?P<prefix>.*i)[?#](?P<suffix>(?:ation|ations|e|ed|es|ing)(?:[$*]\d*)?)", stripped, flags=re.I)
    if m:
        values = [m.group("prefix") + letter + m.group("suffix") for letter in ("s", "z")]
        if flags is not None:
            flags.append(f"uk_us_ise_ize_pattern_expanded:{atom}")
        return values

    # Generic -or/-our family represented by an optional character before r,
    # e.g. colo?r and tumo?r.
    m = re.fullmatch(r"(?P<prefix>.*o)\?(?P<suffix>r[A-Za-z0-9$*\-]*)", stripped, flags=re.I)
    if m:
        values = [m.group("prefix") + m.group("suffix"), m.group("prefix") + "u" + m.group("suffix")]
        if flags is not None:
            flags.append(f"uk_us_or_our_pattern_expanded:{atom}")
        return values

    # A terminal optional character is most often singular/plural in the
    # supplied Cochrane strategies. Apply the plural to the final word of an
    # atomic phrase, e.g. control group? -> control group OR control groups.
    if stripped.endswith("?") and stripped.count("?") == 1 and "#" not in stripped:
        base = stripped[:-1]
        m = re.search(r"([A-Za-z]+)$", base)
        if m:
            plural = _regular_plural(m.group(1))
            values = [base, base[:m.start(1)] + plural]
            if flags is not None:
                flags.append(f"terminal_optional_wildcard_interpreted_as_singular_plural:{atom}")
            return values

    return None


def expand_question_word(word: str, flags: list[str] | None = None):
    """
    Version 16 single-character wildcard hierarchy:
      1. curated exceptions and generic UK/US spelling patterns;
      2. regular/irregular plural interpretation;
      3. exhaustive generic fallback: ? = empty+a-z, # = a-z.

    ``?`` and ``#`` are never conflated. If an atom would exceed the bounded
    generic expansion limit, the atom is returned as MANUAL_REVIEW_ATOM.
    """
    if "?" not in word and "#" not in word:
        return [word]

    curated = _curated_single_char_variants(word, flags)
    if curated is not None:
        return _dedupe([re.sub(r"\s+", " ", x).strip() for x in curated if x.strip()])

    positions = [(i, ch) for i, ch in enumerate(word) if ch in {"?", "#"}]
    choices = [OPTIONAL_SINGLE_CHAR_VARIANTS if ch == "?" else MANDATORY_SINGLE_CHAR_VARIANTS for _, ch in positions]
    expansion_count = 1
    for choice in choices:
        expansion_count *= len(choice)
    if expansion_count > MAX_GENERIC_SINGLE_CHAR_EXPANSIONS:
        if flags is not None:
            flags.append(f"single_char_wildcard_expansion_limit_exceeded:{word}:{expansion_count}")
        return [MANUAL_REVIEW_ATOM]

    variants = []
    for repls in itertools.product(*choices):
        chars = list(word)
        for (pos, _), repl in sorted(zip(positions, repls), reverse=True):
            chars[pos] = repl
        variants.append("".join(chars))

    if flags is not None:
        if "?" in word:
            flags.append(f"generic_optional_wildcard_expanded_empty_plus_26_letters:{word}")
        if "#" in word:
            flags.append(f"generic_mandatory_wildcard_expanded_26_letters:{word}")
    return _dedupe([re.sub(r"\s+", " ", x).strip() for x in variants if x.strip()])


def quote_question_variant(atom: str) -> str:
    """Quote a generated ?/# variant only when it is a multi-word atom."""
    atom = atom.strip()
    if atom.startswith('"') and atom.endswith('"'):
        return atom
    if re.search(r"\s+", atom):
        return f'"{atom}"'
    return atom


def expand_question_atom(atom: str, flags: list[str]) -> str:
    """Expand one complete atomic free-text unit under the V16 hierarchy."""
    if "?" not in atom and "#" not in atom:
        return atom

    variants = expand_question_word(atom, flags)
    if variants == [MANUAL_REVIEW_ATOM]:
        return MANUAL_REVIEW_ATOM
    flags.append(f"expanded_single_char_wildcard_atom:{atom}->{len(variants)}variants")
    rendered = [quote_question_variant(v) for v in variants]
    if len(rendered) == 1:
        return rendered[0]
    return "(" + " OR ".join(rendered) + ")"


def expand_question_hash_marks(line: str):
    """
    Rule 1: expand ? and # before any other conversion.

    Expansion is atom-aware:
      - single token: tumo?r -> (tumor OR tumosr OR ...)
      - multi-word atom: gonadotrop?in releasing hormone agonist*
        -> ("gonadotropin releasing hormone agonist*" OR ...)

    The atom matcher must not cross Boolean/proximity operators,
    parentheses, quoted-string boundaries, field suffixes, or line-reference
    boundaries.
    """
    flags = []

    if "?" not in line and "#" not in line:
        return line, flags

    token = r"[?A-Za-z0-9][A-Za-z0-9$*?#\-]*"
    non_op_token = r"(?!(?:AND|OR|NOT|adj\d*|next)\b)" + token

    # Match one complete atomic run of one or more non-operator tokens.
    # The negative lookbehind for '.' prevents field tags such as .ti. from
    # being treated as free-text atoms after the real phrase has been matched.
    atom_pat = re.compile(
        r"(?<![A-Za-z0-9\]\.])"
        r"(?P<atom>" + non_op_token + r"(?:\s+" + non_op_token + r")*)"
        r"(?![A-Za-z0-9])",
        flags=re.I,
    )

    def convert_unquoted_segment(seg: str) -> str:
        def atom_repl(m):
            atom = m.group("atom")
            if "?" not in atom and "#" not in atom:
                return atom
            parts = atom.split()
            if any(is_boolean_or_proximity_token(x) for x in parts):
                return atom
            return expand_question_atom(atom, flags)

        return atom_pat.sub(atom_repl, seg)

    out = []
    quote_parts = re.split(r'("[^"]*")', line)

    for part in quote_parts:
        if not part:
            continue
        if part.startswith('"') and part.endswith('"'):
            inner = part[1:-1]
            if "?" in inner or "#" in inner:
                out.append(expand_question_atom(inner, flags))
            else:
                out.append(part)
        else:
            out.append(convert_unquoted_segment(part))

    return "".join(out), flags


# ---------------------------------------------------------------------
# Rule 3. Convert Boolean line references
# ---------------------------------------------------------------------

def is_boolean_reference_line(line: str) -> bool:
    """
    True only if the whole expression is made from:
    line references, #line references, AND/OR/NOT, parentheses, and spaces.
    """
    tmp = line.strip()

    tmp = re.sub(r"#\d+", "", tmp)
    tmp = re.sub(r"\b\d+\b", "", tmp)
    tmp = re.sub(r"\b(and|or|not|AND|OR|NOT)\b", "", tmp, flags=re.I)
    tmp = re.sub(r"[()\s]", "", tmp)

    return tmp == ""


def convert_boolean_references(line: str) -> str:
    """
    Convert pure Boolean line-reference expressions.

    Examples:
        or/1-3 -> #1 OR #2 OR #3
        and/4-6 -> #4 AND #5 AND #6
        29 not (28 or 27) -> #29 NOT (#28 OR #27)
    """

    def expand_range(op: str, a: str, b: str) -> str:
        return f" {op.upper()} ".join(
            f"#{i}" for i in range(int(a), int(b) + 1)
        )

    line = re.sub(
        r"\bor/(\d+)-(\d+)",
        lambda m: expand_range("OR", m.group(1), m.group(2)),
        line,
        flags=re.I,
    )

    line = re.sub(
        r"\band/(\d+)-(\d+)",
        lambda m: expand_range("AND", m.group(1), m.group(2)),
        line,
        flags=re.I,
    )

    line = re.sub(
        r"\bor/([0-9,\s]+)",
        lambda m: " OR ".join(
            f"#{x.strip()}" for x in m.group(1).split(",") if x.strip()
        ),
        line,
        flags=re.I,
    )

    line = re.sub(
        r"\band/([0-9,\s]+)",
        lambda m: " AND ".join(
            f"#{x.strip()}" for x in m.group(1).split(",") if x.strip()
        ),
        line,
        flags=re.I,
    )

    if is_boolean_reference_line(line):
        line = normalize_boolean_outside_quotes(line)
        line = re.sub(r"(?<![#\w])(\d+)(?!\w)", r"#\1", line)

    return line


# ---------------------------------------------------------------------
# Rule 4. Convert truncation
# ---------------------------------------------------------------------

PUBMED_MIN_WILDCARD_PREFIX_ALNUM = 4
EMPTY_ATOM = "__EMPTY_ATOM__"  # retained only for backward-compatible validation
DROP_ATOM = "__DROP_SHORT_ROOT_ATOM__"
MANUAL_REVIEW_ATOM = "__MANUAL_REVIEW_REQUIRED__"
PUBMED_EMPTY_QUERY = "(all[sb] NOT all[sb])"

# Curated short-root morphology. Known terms receive singular/plural forms;
# unknown roots are retained literally without the unsupported wildcard.
SHORT_ROOT_MORPHOLOGY_VARIANTS = {
    "job": ["job", "jobs"],
    "dog": ["dog", "dogs"],
}

# Curated biomedical acronym expansions agreed for Version 16. The standalone
# acronym is retained because it captures many spaced/hyphenated constructions;
# explicit compact forms cover common concatenations that may otherwise be lost.
SHORT_ROOT_BIOMEDICAL_EXCEPTIONS = {
    "HIV": ["HIV", "HIV1", "HIV2", "HIV-1", "HIV-2"],
    "HBV": ["HBV", "HBVDNA", "HBV-DNA"],
    "HCV": ["HCV", "HCVRNA", "HCV-RNA"],
    "HPV": ["HPV", "HPV16", "HPV18", "HPV-16", "HPV-18"],
    "HSV": ["HSV", "HSV1", "HSV2", "HSV-1", "HSV-2"],
    "EBV": ["EBV", "EBVDNA", "EBV-DNA"],
    "CMV": ["CMV", "CMVDNA", "CMV-DNA"],
    "RSV": ["RSV", "RSVA", "RSVB", "RSV-A", "RSV-B"],
    "RBC": ["RBC", "RBCs"],
    "PRBC": ["PRBC", "PRBCs"],
}

# Phrase-level exceptions where literalizing only the final short root would
# preserve too little of a common expression.
SHORT_ROOT_PHRASE_EXCEPTIONS = {
    "drop out*": ["drop out", "drop outs"],
    "drop out$": ["drop out", "drop outs"],
}

# A short stem followed by a separate identifier is different from Ovid
# limited truncation.  Only explicitly curated stems are expanded.
SHORT_ROOT_IDENTIFIER_STEMS = {
    "typ": "type",
}


def alnum_len(text: str) -> int:
    """Count alphanumeric characters before the first wildcard."""
    return sum(1 for ch in text if ch.isalnum())


def quote_if_multiword_atom(atom: str) -> str:
    atom = atom.strip()
    if atom in {EMPTY_ATOM, DROP_ATOM, MANUAL_REVIEW_ATOM}:
        return atom
    if atom.startswith('"') and atom.endswith('"'):
        return atom
    if re.search(r"\s+", atom):
        return f'"{atom}"'
    return atom


def is_boolean_or_proximity_token(token: str) -> bool:
    return re.fullmatch(r"(?:AND|OR|NOT|adj\d*|next)", token.strip(), flags=re.I) is not None


def first_truncation_marker(token: str):
    """Return the first non-leading Ovid $/$N/*/*N truncation marker."""
    for i, ch in enumerate(token):
        if ch not in {"$", "*"}:
            continue
        if i == 0:
            continue
        j = i + 1
        digits = ""
        while j < len(token) and token[j].isdigit():
            digits += token[j]
            j += 1
        return {
            "index": i,
            "symbol": ch,
            "limit": int(digits) if digits else None,
            "after_index": j,
        }
    return None


def token_has_truncation(token: str) -> bool:
    return first_truncation_marker(token) is not None


def make_empty_atom(flags: list[str], flag: str, original: str | None = None) -> str:
    """Backward-compatible helper for non-short-root rules."""
    flags.append(f"{flag}:{original}" if original else flag)
    return EMPTY_ATOM


def convert_valid_root_truncation_token(token: str, flags: list[str]) -> str:
    """Convert executable Ovid truncation to PubMed unlimited ``*``."""
    out = []
    i = 0
    while i < len(token):
        ch = token[i]
        if ch == "$":
            j = i + 1
            digits = ""
            while j < len(token) and token[j].isdigit():
                digits += token[j]
                j += 1
            if digits:
                flags.append("limited_ovid_truncation_approximated_as_pubmed_unlimited_wildcard")
            else:
                flags.append("converted_ovid_dollar_truncation_to_pubmed_star")
            out.append("*")
            i = j
            continue
        if ch == "*":
            j = i + 1
            digits = ""
            while j < len(token) and token[j].isdigit():
                digits += token[j]
                j += 1
            if digits:
                flags.append("limited_ovid_star_truncation_approximated_as_pubmed_unlimited_wildcard")
                out.append("*")
                i = j
                continue
            out.append("*")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _render_single_token_variants(variants: list[str]) -> str:
    variants = _dedupe(variants)
    rendered = [quote_if_multiword_atom(x) for x in variants]
    if len(rendered) == 1:
        return rendered[0]
    return "(" + " OR ".join(rendered) + ")"


def _trailing_short_root_match(token: str):
    return re.fullmatch(r"(?P<root>[A-Za-z0-9-]+)(?P<mark>[$*])(?P<limit>\d*)", token)


def _identifier_variants(base: str, identifier: str) -> list[str]:
    """Create agreed spacing/hyphen/concatenation/underscore variants."""
    return [
        f'"{base} {identifier}"',
        f'"{base}-{identifier}"',
        f"{base}{identifier}",
        f'"{base}_{identifier}"',
    ]


def convert_short_root_token_variants(token: str, flags: list[str]) -> list[str]:
    """
    Convert one token under the V16 no-silent-deletion policy.

    For fewer than four alphanumeric characters before the first truncation:
      1. use irregular/biomedical/morphology dictionaries when available;
      2. for an internal short-prefix wildcard, concatenate the literal
         fragments and preserve any later executable wildcard;
      3. otherwise remove only the unsupported wildcard and keep the literal
         root. No short-root atom is deleted merely because its root is short.
    """
    if is_boolean_or_proximity_token(token) or not token_has_truncation(token):
        return [token]

    if re.fullmatch(r"wom[$*](?:\d+)?n", token, flags=re.I):
        flags.append(f"short_root_irregular_plural_expanded_using_curated_dictionary:{token}")
        flags.append("major_semantic_approximation_possible_recall_loss")
        return ["woman", "women"]

    marker = first_truncation_marker(token)
    if marker is None:
        return [token]

    root = token[:marker["index"]]
    if alnum_len(root) >= PUBMED_MIN_WILDCARD_PREFIX_ALNUM:
        return [convert_valid_root_truncation_token(token, flags)]

    trailing = _trailing_short_root_match(token)
    if trailing:
        root_text = trailing.group("root")
        upper = root_text.upper()
        lower = root_text.lower()

        if upper in SHORT_ROOT_BIOMEDICAL_EXCEPTIONS:
            flags.append(f"short_root_biomedical_acronym_expanded_using_curated_dictionary:{token}")
            flags.append("major_semantic_approximation_possible_recall_loss")
            return list(SHORT_ROOT_BIOMEDICAL_EXCEPTIONS[upper])

        if lower in SHORT_ROOT_MORPHOLOGY_VARIANTS:
            flags.append(f"short_root_morphology_expanded_using_curated_dictionary:{token}")
            flags.append("major_semantic_approximation_possible_recall_loss")
            return list(SHORT_ROOT_MORPHOLOGY_VARIANTS[lower])

        flags.append(f"unknown_short_root_truncation_literalized:{token}->{root_text}")
        flags.append("major_semantic_approximation_possible_recall_loss")
        return [root_text]

    # Internal short-prefix wildcard: collapse the first unsupported marker by
    # concatenating its literal fragments, then re-evaluate. oc*ular* becomes
    # ocular*, while intrao*cular is already executable and is handled above.
    collapsed = token[:marker["index"]] + token[marker["after_index"]:]
    if collapsed == token or not collapsed:
        flags.append(f"short_root_internal_wildcard_manual_review_required:{token}")
        return [MANUAL_REVIEW_ATOM]
    flags.append(f"internal_short_prefix_wildcard_collapsed:{token}->{collapsed}")
    flags.append("major_semantic_approximation_possible_recall_loss")
    return convert_short_root_token_variants(collapsed, flags)


def convert_truncation_token(token: str, flags: list[str], context: str = "token") -> str:
    """Backward-compatible wrapper that renders token alternatives."""
    return _render_single_token_variants(convert_short_root_token_variants(token, flags))


def _convert_identifier_phrase(atom: str, flags: list[str]) -> str | None:
    """
    Expand a curated short stem followed by a *separate* identifier.

    ``typ* 1`` is an identifier phrase. ``typ*1`` is Ovid limited truncation
    and is not interpreted as "type 1".
    """
    m = re.fullmatch(
        r"(?P<root>[A-Za-z]{1,3})(?P<mark>[$*])\s+(?P<identifier>[A-Za-z0-9]+)",
        atom.strip(),
    )
    if not m:
        return None
    root = m.group("root").lower()
    if root not in SHORT_ROOT_IDENTIFIER_STEMS:
        return None
    base = SHORT_ROOT_IDENTIFIER_STEMS[root]
    identifier = m.group("identifier")
    flags.append(f"short_root_identifier_pattern_expanded:{atom}->{base}:{identifier}")
    flags.append("major_semantic_approximation_possible_recall_loss")
    return "(" + " OR ".join(_identifier_variants(base, identifier)) + ")"


def convert_truncation_atom(atom: str, flags: list[str]) -> str:
    """Convert truncation within a complete atomic token or phrase."""
    atom = atom.strip()
    if not atom:
        return atom

    phrase_key = atom.lower()
    if phrase_key in SHORT_ROOT_PHRASE_EXCEPTIONS:
        values = SHORT_ROOT_PHRASE_EXCEPTIONS[phrase_key]
        flags.append(f"short_root_phrase_exception_expanded:{atom}")
        return "(" + " OR ".join(quote_if_multiword_atom(x) for x in values) + ")"

    identifier_expansion = _convert_identifier_phrase(atom, flags)
    if identifier_expansion is not None:
        return identifier_expansion

    words = atom.split()
    phrase_context = len(words) > 1
    alternatives_per_word: list[list[str]] = []

    for word in words:
        variants = convert_short_root_token_variants(word, flags)
        if MANUAL_REVIEW_ATOM in variants:
            return MANUAL_REVIEW_ATOM
        alternatives_per_word.append(variants)

    phrase_variants = []
    for combo in itertools.product(*alternatives_per_word):
        candidate = " ".join(combo)
        phrase_variants.append(quote_if_multiword_atom(candidate) if phrase_context else quote_if_multiword_atom(candidate))
    phrase_variants = _dedupe(phrase_variants)
    if len(phrase_variants) == 1:
        return phrase_variants[0]
    return "(" + " OR ".join(phrase_variants) + ")"


def render_empty_atoms(line: str) -> str:
    return line.replace(EMPTY_ATOM, PUBMED_EMPTY_QUERY)


def is_empty_rendered(line: str) -> bool:
    return line.strip() in {EMPTY_ATOM, PUBMED_EMPTY_QUERY}


def convert_truncation(line: str):
    """
    Convert Ovid truncation under the Version 16 no-silent-deletion policy.

    Valid roots retain/receive PubMed ``*``. Curated short roots expand to
    morphology, biomedical-acronym, phrase, or identifier alternatives. Unknown
    short-root truncation is literalized by removing only the unsupported
    wildcard; internal short-prefix wildcards are collapsed conservatively.
    """
    flags: list[str] = []

    # Remove unsupported leading free-text stars. MeSH focus markers and
    # wildcard-bearing slash atoms are classified before this step.
    if re.search(r'(?<![\w"\]])\*+(?=[A-Za-z0-9])', line):
        flags.append("removed_unsupported_leading_free_text_star")
    line = re.sub(r'(?<![\w"\]])\*+(?=[A-Za-z0-9])', "", line)

    if "$" not in line and "*" not in line:
        return line, flags

    flags.append("processed_ovid_truncation_symbols")
    quote_parts = re.split(r'("[^"]*")', line)

    def convert_quoted_segment(seg: str) -> str:
        inner = seg[1:-1]
        if "$" not in inner and "*" not in inner:
            return seg
        return convert_truncation_atom(inner, flags)

    def convert_unquoted_segment(seg: str) -> str:
        token = r"[A-Za-z0-9][A-Za-z0-9$*\-]*"
        non_op_token = r"(?!(?:AND|OR|NOT|adj\d*|next)\b)" + token
        phrase_pat = re.compile(
            r"(?<![A-Za-z0-9\]])"
            r"(?P<phrase>" + non_op_token + r"(?:\s+" + non_op_token + r")+)"
            r"(?![A-Za-z0-9])",
            flags=re.I,
        )

        def phrase_repl(m):
            phrase = m.group("phrase")
            if "$" not in phrase and "*" not in phrase:
                return phrase
            if any(is_boolean_or_proximity_token(x) for x in phrase.split()):
                return phrase
            return convert_truncation_atom(phrase, flags)

        seg = phrase_pat.sub(phrase_repl, seg)

        token_pat = re.compile(
            r"(?<![A-Za-z0-9\]])"
            r"(?P<token>[A-Za-z0-9][A-Za-z0-9$*\-]*(?:[$*]\d*)[A-Za-z0-9$*\-]*)"
            r"(?![A-Za-z0-9])"
        )

        def token_repl(m):
            tok = m.group("token")
            if is_boolean_or_proximity_token(tok):
                return tok
            return convert_truncation_token(tok, flags)

        return token_pat.sub(token_repl, seg)

    converted_parts = []
    for part in quote_parts:
        if not part:
            continue
        if part.startswith('"') and part.endswith('"'):
            converted_parts.append(convert_quoted_segment(part))
        else:
            converted_parts.append(convert_unquoted_segment(part))

    return "".join(converted_parts), flags


def _simplify_drop_expr_core(expr: str, flags: list[str], context: str = "") -> str:
    expr = expr.strip()
    if not expr or expr == DROP_ATOM:
        return DROP_ATOM

    if is_wrapped_by_outer_parens(expr):
        inner = _simplify_drop_expr_core(expr[1:-1], flags, context=context)
        return DROP_ATOM if inner == DROP_ATOM else f"({inner})"

    groups, found = split_by_top_level_operator(expr, "OR")
    if found:
        simplified = [_simplify_drop_expr_core(g, flags, context=context) for g in groups if g.strip()]
        survivors = [g for g in simplified if g != DROP_ATOM]
        if len(survivors) != len(simplified):
            flags.append("short_root_removal_narrowed_or_expression")
        if not survivors:
            return DROP_ATOM
        return " OR ".join(survivors)

    groups, found = split_by_top_level_operator(expr, "AND")
    if found:
        simplified = [_simplify_drop_expr_core(g, flags, context=context) for g in groups if g.strip()]
        survivors = [g for g in simplified if g != DROP_ATOM]
        if len(survivors) != len(simplified):
            flags.append("short_root_removal_broadened_and_expression")
        if not survivors:
            return DROP_ATOM
        return " AND ".join(survivors)

    groups, found = split_by_top_level_operator(expr, "NOT")
    if found:
        lhs = _simplify_drop_expr_core(groups[0], flags, context=context)
        if lhs == DROP_ATOM:
            flags.append("short_root_removal_deleted_not_expression_with_missing_lhs")
            return DROP_ATOM
        for rhs_raw in groups[1:]:
            rhs = _simplify_drop_expr_core(rhs_raw, flags, context=context)
            if rhs == DROP_ATOM:
                flags.append("short_root_removal_removed_not_rhs")
                continue
            lhs = f"{lhs} NOT {rhs}"
        return lhs

    return expr


def simplify_drop_atoms_in_line(line: str, flags: list[str], context: str = ""):
    """Remove DROP_ATOM operands while preserving a valid Boolean AST."""
    # A field suffix attached directly to a dropped atom must disappear with it.
    line = re.sub(
        re.escape(DROP_ATOM) + r"\s*\.(?:[a-z]{2})(?:\s*,\s*[a-z]{2})*\.?",
        DROP_ATOM,
        line,
        flags=re.I,
    )
    if DROP_ATOM not in line:
        return line, False

    original = line
    whole_line = re.match(
        r"^(?P<expr>.+?)\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})*)\s*\.?$",
        line,
        flags=re.I,
    )
    if whole_line and not re.search(r'\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.', whole_line.group("expr"), flags=re.I):
        simplified = _simplify_drop_expr_core(whole_line.group("expr"), flags, context=context)
        if simplified == DROP_ATOM:
            return DROP_ATOM, True
        rebuilt = simplified + f'.{whole_line.group("fields")}.'
        return rebuilt, rebuilt != original

    simplified = _simplify_drop_expr_core(line, flags, context=context)
    return simplified, simplified != original


def simplify_dropped_line_references(
    expr: str,
    dropped_line_numbers: set[int],
    flags: list[str],
    current_num: int,
):
    """Replace references to dropped lines and simplify the containing AST."""
    refs = referenced_line_numbers(expr)
    affected = sorted({r for r in refs if r in dropped_line_numbers})
    if not affected:
        return expr, False

    replaced = re.sub(
        r"#(\d+)",
        lambda m: DROP_ATOM if int(m.group(1)) in dropped_line_numbers else m.group(0),
        expr,
    )
    for ref in affected:
        flags.append(f"dropped_short_root_line_reference_simplified:#{ref} in #{current_num}")
    simplified, _ = simplify_drop_atoms_in_line(replaced, flags, context=f"line_reference_#{current_num}")
    return simplified, simplified != expr

# ---------------------------------------------------------------------
# Rule 2. Quote atomic multi-word free-text phrases
# ---------------------------------------------------------------------

def quote_atom(atom: str) -> str:
    prefix = atom[:len(atom) - len(atom.lstrip())]
    suffix = atom[len(atom.rstrip()):]
    core = atom.strip()

    if not core:
        return atom

    if core in {EMPTY_ATOM, DROP_ATOM, MANUAL_REVIEW_ATOM} or core == PUBMED_EMPTY_QUERY:
        return atom

    if core.startswith('"') and core.endswith('"'):
        return atom

    if re.fullmatch(r"#?\d+", core):
        return atom

    if "[" in core and "]" in core:
        return atom

    if is_boolean_or_proximity_token(core):
        return atom

    word_like = re.findall(r"[A-Za-z0-9][A-Za-z0-9*$\-]*", core)

    if len(word_like) >= 2 and re.search(r"\s+", core):
        return prefix + '"' + core + '"' + suffix

    return atom


def top_level_contains_operator(expr: str, include_proximity: bool = True) -> bool:
    """Detect top-level Boolean/proximity operators outside quotes/parens."""
    depth = 0
    in_quote = False
    i = 0
    n = len(expr)

    while i < n:
        ch = expr[i]
        if ch == '"':
            in_quote = not in_quote
            i += 1
            continue
        if not in_quote:
            if ch == "(":
                depth += 1
                i += 1
                continue
            if ch == ")":
                depth -= 1
                i += 1
                continue
            if depth == 0:
                m = re.match(r"(?:AND|OR|NOT|adj\d*|next)", expr[i:], flags=re.I)
                if m:
                    before = expr[i - 1] if i > 0 else ""
                    after_i = i + len(m.group(0))
                    after = expr[after_i] if after_i < n else ""
                    before_ok = (i == 0) or before.isspace() or before in "()"
                    after_ok = (after_i == n) or after.isspace() or after in "()"
                    if before_ok and after_ok:
                        if include_proximity or re.fullmatch(r"AND|OR|NOT", m.group(0), flags=re.I):
                            return True
        i += 1
    return False


def quote_atomic_phrases_expr(expr: str) -> str:
    """
    Quote atomic multi-word phrases inside a Boolean/proximity expression,
    without quoting the entire Boolean/proximity group.
    """
    parts = re.split(
        r'("[^"]*"|\(|\)|\bAND\b|\bOR\b|\bNOT\b|\badj\d*\b|\bnext\b)',
        expr,
        flags=re.I,
    )

    out = []

    for p in parts:
        if p == "" or p in {"(", ")"}:
            out.append(p)
            continue

        if p.startswith('"') and p.endswith('"'):
            out.append(p)
            continue

        if re.fullmatch(r"\b(and|or|not)\b", p.strip(), flags=re.I):
            out.append(p.upper())
            continue

        if re.fullmatch(r"\b(adj\d*|next)\b", p.strip(), flags=re.I):
            out.append(p)
            continue

        out.append(quote_atom(p))

    return "".join(out)


def quote_free_text_field_expressions(line: str) -> str:
    """
    Apply phrase quotation before field-tag conversion.

    Whole-expression field suffixes are only applied when the suffix is on a
    single atom/phrase or on an explicitly parenthesized group.  A final
    suffix on an unparenthesized Boolean/proximity expression is treated as
    local to the right-hand atom by the inline matcher.
    """
    if is_boolean_reference_line(line):
        return line

    whole_line_field = re.match(
        r"^(?P<expr>.+?)\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})*)\s*\.?$",
        line,
        flags=re.I,
    )

    if whole_line_field:
        expr = whole_line_field.group("expr").strip()
        fields = whole_line_field.group("fields")

        # Only treat as whole-line if expression has no other inline field
        # suffix and is either an atom/phrase or an explicitly parenthesized
        # Boolean/proximity group.
        if not re.search(r'\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.', expr, flags=re.I):
            fields_l = [f.strip().lower() for f in fields.split(",")]
            first_field = fields_l[0]
            allowed = {"ti", "ab", "tw", "kf", "mp", "af", "jw", "jn", "ot", "hw"}
            safe_scope = is_wrapped_by_outer_parens(expr) or not top_level_contains_operator(expr, include_proximity=True)
            if safe_scope and (first_field in allowed or len(fields_l) > 1):
                return quote_atomic_phrases_expr(expr) + f".{fields}."

    field_suffix = r"(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)"

    inline_field_pat = re.compile(
        r'(?<![A-Za-z0-9])'
        r'(?P<expr>'
        r'"[^"]+"'
        r'|'
        r'(?!(?:and|or|not|adj\d*|next)\b)'
        r'[A-Za-z0-9*$\-]+(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*$\-]+)+'
        r')'
        r'\s*\.(?P<field>' + field_suffix + r')\.?',
        flags=re.I,
    )

    line = inline_field_pat.sub(
        lambda m: quote_atom(m.group("expr")) + f".{m.group('field')}.",
        line,
    )

    # v10: free-text Boolean-looking words are underdetermined. We still
    # treat standalone AND/OR/NOT as Boolean operators, but we quote any
    # resulting multi-word free-text atoms on either side.
    return quote_atomic_phrases_expr(line)


# ---------------------------------------------------------------------
# Rule 2.4. Recall-preserving Ovid runtime-stopword conversion
# ---------------------------------------------------------------------

OVID_FREE_TEXT_FIELDS = {"ti", "ab", "tw", "kf", "mp", "af", "jw", "jn", "ot", "hw"}


def _convert_ovid_stopword_atom(atom: str, flags: list[str]) -> str:
    prefix = atom[:len(atom) - len(atom.lstrip())]
    suffix = atom[len(atom.rstrip()):]
    core = atom.strip()
    if not core or should_not_add_field(core):
        return atom
    if core.startswith('"') and core.endswith('"'):
        core = core[1:-1].strip()

    # Do not reinterpret punctuation-heavy identifiers or already structured
    # expressions. Hyphenated words remain single tokens, so "skin-to-skin"
    # is not changed merely because it contains the letters "to".
    if not re.fullmatch(r"[A-Za-z0-9*?$#'\-]+(?:\s+[A-Za-z0-9*?$#'\-]+)+", core):
        return atom

    tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9*?$#'\-]*", core)
    removed = [token for token in tokens if token.casefold() in OVID_RUNTIME_STOPWORDS]
    if not removed:
        return atom

    content: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token.casefold() in OVID_RUNTIME_STOPWORDS:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        content.append(token)

    flags.append(
        "ovid_stopword_and_conversion:"
        f"removed={','.join(x.casefold() for x in removed)}:"
        f"source={core}"
    )
    if len(content) < len(tokens) - len(removed):
        flags.append(f"ovid_stopword_conversion_deduplicated_terms:{core}")

    if not content:
        flags.append(f"manual_review_ovid_stopword_phrase_no_content_terms:{core}")
        return MANUAL_REVIEW_ATOM
    if len(content) == 1:
        return prefix + content[0] + suffix
    return prefix + "(" + " AND ".join(content) + ")" + suffix


def _rewrite_ovid_stopwords_in_boolean_expr(expr: str, flags: list[str]) -> str:
    stripped = expr.strip()
    if not stripped:
        return expr
    if is_wrapped_by_outer_parens(stripped):
        inner = stripped[1:-1]
        return "(" + _rewrite_ovid_stopwords_in_boolean_expr(inner, flags) + ")"

    parts = split_top_level_boolean(stripped)
    if len(parts) > 1:
        output: list[str] = []
        for part in parts:
            if re.fullmatch(r"AND|OR|NOT", part.strip(), flags=re.I):
                output.append(f" {part.strip().upper()} ")
            else:
                output.append(_rewrite_ovid_stopwords_in_boolean_expr(part, flags))
        return tidy_spaces("".join(output))
    return _convert_ovid_stopword_atom(stripped, flags)


def convert_ovid_stopword_free_text(line: str):
    """
    Remove Ovid runtime stopwords only inside explicit free-text field objects.

    Remaining distinct terms are joined by AND. Explicit Boolean operators are
    parsed before this rule, so an unquoted standalone ``and`` remains Boolean
    logic rather than being deleted as phrase text.
    """
    flags: list[str] = []
    whole_line = re.match(
        r"^(?P<expr>.+?)\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})*)\s*\.?$",
        line,
        flags=re.I,
    )
    if whole_line:
        expr = whole_line.group("expr").strip()
        fields = [f.strip().lower() for f in whole_line.group("fields").split(",")]
        no_inner_suffix = not re.search(
            r"\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.",
            expr,
            flags=re.I,
        )
        safe_scope = (
            is_wrapped_by_outer_parens(expr)
            or not top_level_contains_operator(expr, include_proximity=True)
        )
        if no_inner_suffix and safe_scope and set(fields) <= OVID_FREE_TEXT_FIELDS:
            rewritten = _rewrite_ovid_stopwords_in_boolean_expr(expr, flags)
            return rewritten + "." + whole_line.group("fields") + ".", flags

    field_suffix = r"(?:ti|ab|tw|kf|mp|af|jw|jn|ot|hw)"
    inline_field_pat = re.compile(
        r'(?<![A-Za-z0-9])'
        r'(?P<expr>'
        r'"[^"]+"'
        r'|'
        r'(?!(?:and|or|not|adj\d*|next)\b)'
        r'[A-Za-z0-9*?$#\047\-]+'
        r'(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*?$#\047\-]+)+'
        r')'
        r'\s*\.(?P<field>' + field_suffix + r')\.?',
        flags=re.I,
    )

    def inline_repl(match):
        converted = _convert_ovid_stopword_atom(match.group("expr"), flags)
        return converted + f".{match.group('field')}."

    return inline_field_pat.sub(inline_repl, line), flags

# ---------------------------------------------------------------------
# Rule 5. Convert adjacency
# ---------------------------------------------------------------------

def convert_adjacency(line: str) -> str:
    # Ovid proximity operators adj/adjN and next are approximated as AND.
    return re.sub(r"\b(?:adj\d*|next)\b", "AND", line, flags=re.I)



# ---------------------------------------------------------------------
# Rule 6. Convert standard Cochrane RCT filter terms
# ---------------------------------------------------------------------

def convert_cochrane_rct_filter_terms(line: str) -> str:
    """
    High-priority exact Cochrane RCT filter conversion.

    Rule 6 intentionally maps common RCT-filter .ab. terms to [tiab]
    and generic .ab. terms both map to PubMed [tiab].
    """
    field_end = r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))"

    animal_exclusion_patterns = [
        r"\bexp\s+animals/\s+not\s+humans\.sh\.?",
        r"\bexp\s+animals/\s+not\s+humans/",
        r"\banimals/\s+not\s+humans/",
        r"\banimals\.sh\.?\s+not\s+humans\.sh\.?",
    ]
    for pat in animal_exclusion_patterns:
        line = re.sub(pat + field_end, "animals[mh] NOT humans[mh]", line, flags=re.I)

    # Older Cochrane animal-only exclusion form. Keep replacement grouped.
    line = re.sub(
        r"\(?\s*animals\s+not\s+\(\s*humans\s+and\s+animals\s*\)\s*\)?\.sh\.?(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))",
        "(animals[mh] NOT humans[mh])",
        line,
        flags=re.I,
    )

    # Explicit legacy study-design mappings. Plural "trials" slash headings
    # are topical descriptors; singular trial publication types are [pt].
    exact = [
        (
            r"\bexp\s+randomized\s+controlled\s+trials/",
            '"Randomized Controlled Trials as Topic"[mh]',
        ),
        (
            r"\brandomized\s+controlled\s+trials/",
            '"Randomized Controlled Trials as Topic"[mh]',
        ),
        (
            r"\bexp\s+clinical\s+trials/",
            '"Clinical Trials as Topic"[mh]',
        ),
        (
            r"\bclinical\s+trials/",
            '"Clinical Trials as Topic"[mh]',
        ),
        (
            r"\bexp\s+evaluation\s+studies/",
            '"Evaluation Studies as Topic"[mh]',
        ),
        (
            r"\bevaluation\s+studies/",
            '"Evaluation Studies as Topic"[mh]',
        ),
        (
            r"\bcomparative\s+study\.sh\.?",
            '"Comparative Study"[pt]',
        ),
        (
            r"\bexp\s+randomized\s+controlled\s+trial/",
            '"Randomized Controlled Trial"[pt]',
        ),
        (
            r"\brandomized\s+controlled\s+trial\.pt\.?",
            '"Randomized Controlled Trial"[pt]',
        ),
        (
            r"\bcontrolled\s+clinical\s+trial\.pt\.?",
            '"Controlled Clinical Trial"[pt]',
        ),
        (
            r"\bclinical\s+trial\.pt\.?",
            '"Clinical Trial"[pt]',
        ),
        (r"\bplacebo\.ab\.?", "placebo[tiab]"),
        (r"\bdrug\s+therapy\.fs\.?", "drug therapy[sh]"),
        (r"\bdt\.fs\.?", "drug therapy[sh]"),
        (r"\brandomly\.ab\.?", "randomly[tiab]"),
        (r"\btrial\.ab\.?", "trial[tiab]"),
        (r"\btrial\.ti\.?", "trial[ti]"),
        (r"\bgroups\.ab\.?", "groups[tiab]"),
        (r"\bexp\s+animals/", "animals[mh]"),
        (r"\banimals/", "animals[mh]"),
        (r"\banimals\.sh\.?", "animals[mh]"),
        (r"\bhumans/", "humans[mh]"),
        (r"\bhumans\.sh\.?", "humans[mh]"),
        (
            r"\bclinical\s+trials\s+as\s+topic\.sh\.?",
            '"Clinical Trials as Topic"[mh]',
        ),
    ]

    for pat, repl in exact:
        line = re.sub(pat + field_end, repl, line, flags=re.I)

    # Wildcarded randomi?ed.ab. / randomi#ed.ab. after Rule 1 may become
    # a parenthesized group followed by .ab.; map to [tiab] as an RCT-filter case.
    line = re.sub(
        r"\(([^()]*randomi[^()]*)\)\.ab\.?" + field_end,
        lambda m: "(" + distribute_ovid_suffix_inside_expr(
            normalize_boolean_outside_quotes(m.group(1)),
            "[tiab]",
            lambda atom, _flags=None: atom.strip(),
        ) + ")",
        line,
        flags=re.I,
    )

    line = re.sub(r"\brandomized\.ab\.?" + field_end, "randomized[tiab]", line, flags=re.I)
    line = re.sub(r"\brandomised\.ab\.?" + field_end, "randomised[tiab]", line, flags=re.I)

    return line



# ---------------------------------------------------------------------
# V16 exact slash publication-type headings
# ---------------------------------------------------------------------

# Closed, exact-title whitelist. No fuzzy inference is allowed. A title not in
# this table continues through ordinary MeSH handling.
EXACT_SLASH_PUBLICATION_TYPE_HEADINGS = {
    "randomized controlled trial": "Randomized Controlled Trial",
    "controlled clinical trial": "Controlled Clinical Trial",
    "clinical trial": "Clinical Trial",
    "clinical trial, phase i": "Clinical Trial, Phase I",
    "clinical trial, phase ii": "Clinical Trial, Phase II",
    "clinical trial, phase iii": "Clinical Trial, Phase III",
    "clinical trial, phase iv": "Clinical Trial, Phase IV",
    "pragmatic clinical trial": "Pragmatic Clinical Trial",
    "observational study": "Observational Study",
}


def convert_exact_publication_type_slash_descriptors(line: str):
    """Convert only exact whitelisted slash headings to PubMed [pt]."""
    flags: list[str] = []
    boundary = r'(?<![\w\]])'
    bool_boundary = r'(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))'

    for key, canonical in sorted(EXACT_SLASH_PUBLICATION_TYPE_HEADINGS.items(), key=lambda x: len(x[0]), reverse=True):
        title_pattern = re.escape(key).replace(r'\ ', r'\s+')
        pattern = re.compile(
            boundary + r'(?P<exp>exp\s+)?\*?(?:"?' + title_pattern + r'"?)\s*/'
            r'(?:(?!(?:AND|OR|NOT)\b)[a-z]{1,3}(?:\s*,\s*(?!(?:AND|OR|NOT)\b)[a-z]{1,3})*)?'
            + bool_boundary,
            flags=re.I,
        )
        def repl(match):
            tag = "[pt]" if match.group("exp") else "[pt]"
            return f'"{canonical}"{tag}'

        line, count = pattern.subn(repl, line)
        if count:
            flags.append(f"exact_slash_publication_type_heading_converted:{canonical}")
    return line, flags


# ---------------------------------------------------------------------
# Rule 7.1.2. Wildcard-bearing slash atoms
# ---------------------------------------------------------------------

def _render_wildcard_slash_term(term: str, flags: list[str]) -> str:
    term = normalize_unicode(term.strip().strip('"'))
    variants = expand_question_word(term, flags)
    rendered: list[str] = []

    for variant in variants:
        converted = convert_truncation_atom(variant, flags)
        if converted == MANUAL_REVIEW_ATOM:
            return MANUAL_REVIEW_ATOM
        rendered.append(f"{converted}[tw]")

    rendered = list(dict.fromkeys(rendered))
    flags.append("wildcard_bearing_slash_atom_fell_back_to_free_text")
    if len(rendered) == 1:
        return rendered[0]
    return "(" + " OR ".join(rendered) + ")"


def convert_wildcard_bearing_slash_atoms(line: str):
    """
    Convert slash-terminated objects containing free-text wildcard syntax
    before ordinary MeSH parsing. One optional leading ``*`` is treated as an
    Ovid focus marker and removed; the object then becomes free text [tw].
    """
    flags: list[str] = []
    bool_boundary = r'(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))'
    slash_tail = (
        r'/'
        r'(?P<subs>(?!(?:AND|OR|NOT)\b)[a-z]{1,3}'
        r'(?:\s*,\s*(?!(?:AND|OR|NOT)\b)[a-z]{1,3})*)?'
        + bool_boundary
    )
    boundary = r'(?<![\w\]"])'

    placeholders: dict[str, str] = {}

    def replace_match(m):
        term = m.group("term")
        if not any(ch in term for ch in "?#$*"):
            return m.group(0)
        if m.groupdict().get("subs"):
            flags.append("wildcard_bearing_slash_attached_suffix_ignored")
        rendered = _render_wildcard_slash_term(term, flags)
        key = f"__V14_WC_SLASH_{len(placeholders)}__"
        placeholders[key] = rendered
        return key

    quoted_pat = re.compile(
        boundary
        + r'(?:(?:exp)\s+)?\*?"(?P<term>[^"]+)"\s*'
        + slash_tail,
        flags=re.I,
    )
    line = quoted_pat.sub(replace_match, line)

    wc_word = r"[A-Za-z0-9][A-Za-z0-9,\047?#$*\-]*"
    first_wc_word = r"(?!(?:AND|OR|NOT)\b)(?!\d+\b)" + wc_word
    unquoted_term = first_wc_word + r"(?:\s+" + wc_word + r")*"
    unquoted_pat = re.compile(
        boundary
        + r'(?:(?:exp)\s+)?\*?(?P<term>' + unquoted_term + r')\s*'
        + slash_tail,
        flags=re.I,
    )
    line = unquoted_pat.sub(replace_match, line)

    for key, value in placeholders.items():
        line = line.replace(key, value)

    return line, flags

# ---------------------------------------------------------------------
# Rule 7. Convert MeSH descriptors token by token
# ---------------------------------------------------------------------

def resolve_mesh_subheading(code: str, flags: list[str]) -> str:
    code = code.strip().lower()
    if code in MESH_SUBHEADING_MAP:
        return MESH_SUBHEADING_MAP[code]
    flags.append(f"unknown_mesh_subheading_abbreviation_preserved:{code}")
    return code



def render_mesh_descriptor(
    term: str,
    subheads: str | None = None,
    flags: list[str] | None = None,
    *,
    exploded: bool = False,
) -> str:
    """
    Resolve and render one Ovid controlled heading.

    Stopwords are intentionally preserved during resolution. Under the
    project's recall-oriented rule, ordinary and explicitly exploded Ovid
    headings both use PubMed [mh]/[pt]; ``:noexp`` is never introduced. An
    applicable explicitly exploded pharmacological-action descriptor expands
    inside the same Boolean atom to ``([mh] OR [pa])``.
    """
    if flags is None:
        flags = []

    raw = term.strip()
    had_focus = raw.startswith("*")
    term = normalize_mesh_lookup_label(raw)
    term = term.lstrip("*").strip()

    if had_focus:
        flags.append("ovid_mesh_focus_marker_ignored_for_recall")
    if subheads:
        flags.append("ovid_attached_mesh_subheading_ignored_main_descriptor_only")
    if re.search(r"\b(?:and|or|not)\b", term, flags=re.I):
        flags.append(f"slash_terminated_mesh_descriptor_contains_boolean_word_protected:{term}")
    if any(ch in term for ch in "?#$*"):
        flags.append(f"wildcard_bearing_slash_atom_unhandled_manual_review_required:{term}")
        return MANUAL_REVIEW_ATOM

    resolution = get_mesh_resolver().resolve(term)
    status = resolution.get("status")
    if status != "resolved":
        reason = resolution.get("reason", "unknown")
        # Preserve v17's safe, recall-oriented behaviour when external
        # verification is unavailable or the historical Ovid punctuation is
        # not an exact current API label. The warning remains fully auditable.
        flags.append(
            f"mesh_resolution_fallback_to_source_heading:{term}:{status}:{reason}"
        )
        flags.append(f"ovid_heading_exploded:{'yes' if exploded else 'no'}")
        return f'"{term}"[mh]'

    canonical = resolution["canonical_label"]
    descriptor_id = resolution["descriptor_id"]
    record_class = resolution["record_class"]
    match_type = resolution["match_type"]
    flags.append(
        "mesh_resolved:"
        f"{term}=>{canonical}|{descriptor_id}|{match_type}|{record_class}"
    )
    flags.append(f"ovid_heading_exploded:{'yes' if exploded else 'no'}")

    if record_class == "PublicationType":
        tag = "pt"
    elif record_class in {"TopicalDescriptor", "GeographicalDescriptor", "CheckTag"}:
        tag = "mh"
    else:
        flags.append(f"manual_review_unsupported_mesh_record_class:{term}:{record_class}")
        return MANUAL_REVIEW_ATOM

    mesh_atom = f'"{canonical}"[{tag}]'
    if (
        exploded
        and tag == "mh"
        and resolution.get("is_pharmacological_action")
    ):
        flags.append(
            f"exploded_pharmacological_action_expanded_to_mh_or_pa:{canonical}"
        )
        return f'("{canonical}"[mh] OR "{canonical}"[pa])'
    return mesh_atom


def convert_mesh_descriptors(line: str):
    """
    Convert ordinary Ovid MEDLINE headings after exact MeSH resolution.
    Attached slash subheading restrictions are consumed and ignored under the
    retained main-descriptor-only rule. A Boolean token after a bare slash is
    always external.
    """
    flags: list[str] = []
    boundary = r'(?<![\w\]])'
    bool_boundary = r'(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))'

    # No whitespace is allowed between '/' and an attached subheading code.
    # AND/OR/NOT are explicitly excluded from the optional code capture.
    slash = (
        r'/'
        r'(?P<subs>(?!(?:AND|OR|NOT)\b)[a-z]{1,3}'
        r'(?:\s*,\s*(?!(?:AND|OR|NOT)\b)[a-z]{1,3})*)?'
        + bool_boundary
    )

    word = r'[A-Za-z0-9][A-Za-z0-9,\047\-]*'
    first_word = r'(?!(?:AND|OR|NOT)\b)(?!\d+\b)' + word
    unquoted_term = first_word + r'(?:\s+' + word + r')*'

    def make_repl(exploded: bool):
        def repl(m):
            full = m.group(0)
            rendered = render_mesh_descriptor(
                m.group("term"),
                m.groupdict().get("subs"),
                flags,
                exploded=exploded,
            )
            if re.search(r'/\s*(?:AND|OR|NOT)\b', full, flags=re.I):
                flags.append("boolean_after_bare_mesh_slash_preserved_as_external_operator")
            flags.append("slash_terminated_mesh_descriptor_protected_before_boolean_parsing")
            return rendered
        return repl

    patterns = [
        (boundary + r'\bexp\s+\*?"(?P<term>[^"]+)"\s*' + slash, True),
        (boundary + r'\*?"(?P<term>[^"]+)"\s*' + slash, False),
        (boundary + r'\*?"(?P<term>[^"]+)"\s*\.sh\.?' + bool_boundary, False),
        (boundary + r'\bexp\s+\*?(?P<term>' + unquoted_term + r')\s*' + slash, True),
        (boundary + r'\*?(?P<term>' + unquoted_term + r')\s*\.sh\.?' + bool_boundary, False),
        (boundary + r'\*?(?P<term>' + unquoted_term + r')\s*' + slash, False),
    ]

    for pattern, exploded in patterns:
        line = re.sub(pattern, make_repl(exploded), line, flags=re.I)

    return line, flags

# ---------------------------------------------------------------------
# Helpers for group-level Ovid suffix distribution (.pt., .fs., .nm., .pa.)
# ---------------------------------------------------------------------

def transform_publication_type_atom(atom: str, flags: list[str] | None = None) -> str:
    value = atom.strip()
    if flags is not None and value.casefold() not in {
        "randomized controlled trial",
        "controlled clinical trial",
    }:
        flags.append(f"unverified_generic_publication_type_value:{value}")
    return value


def transform_subheading_atom(atom: str, flags: list[str] | None = None) -> str:
    atom = atom.strip()
    key = atom.lower()
    if key in MESH_SUBHEADING_MAP:
        return MESH_SUBHEADING_MAP[key]
    return atom


def transform_nm_atom(atom: str, flags: list[str] | None = None) -> str:
    atom = atom.strip().strip('"')
    if re.search(r"\s+", atom):
        return f'"{atom}"'
    return atom


def transform_pa_atom(atom: str, flags: list[str] | None = None) -> str:
    atom = atom.strip().strip('"')
    return f'"{atom}"'


def normalize_cm_relation_key(text: str) -> str:
    """Normalize a .cm. relation label for table lookup."""
    text = text.strip().strip('"')
    text = re.sub(r"\s+", " ", text)
    return text.lower().strip()


def render_unknown_cm_relation(raw: str, flags: list[str] | None = None) -> str:
    """
    Unknown .cm. labels are kept executable as all-fields text with an audit
    warning rather than being silently collapsed to Comment[pt].
    """
    raw = raw.strip().strip('"')
    if flags is not None:
        flags.append(f"unknown_cm_relation_preserved_as_all_fields:{raw}")
    if re.search(r"\s+", raw):
        return f'"{raw}"[all]'
    return f"{raw}[all]"


def transform_cm_atom(atom: str, flags: list[str] | None = None) -> str:
    """
    Convert one terminal Ovid .cm. Comments/Corrections relation label to a
    PubMed relation token such as hascommenton or haserratumfor.
    """
    atom = atom.strip()
    key = normalize_cm_relation_key(atom)

    if key in COMMENT_CORRECTION_CM_MAP:
        token = COMMENT_CORRECTION_CM_MAP[key]
        if flags is not None:
            flags.append(f"converted_cm_comments_corrections_relation:{key}->{token}")
        return token

    if key in COMMENT_CORRECTION_CM_TOKENS:
        return key

    return render_unknown_cm_relation(atom, flags)


def distribute_ovid_suffix_inside_expr(expr: str, tag: str, transform_atom, flags: list[str] | None = None) -> str:
    """
    Distribute an Ovid suffix tag into terminal atoms of a Boolean expression.
    The expression is assumed not to include the surrounding parentheses.
    """
    parts = split_top_level_boolean(expr)
    out = []

    for part in parts:
        stripped = part.strip()

        if re.fullmatch(r"AND|OR|NOT", stripped, flags=re.I):
            out.append(f" {stripped.upper()} ")
            continue

        if is_wrapped_by_outer_parens(stripped):
            leading = part[: len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            inner = stripped[1:-1]
            out.append(
                f"{leading}({distribute_ovid_suffix_inside_expr(inner, tag, transform_atom, flags)}){trailing}"
            )
            continue

        if should_not_add_field(stripped):
            out.append(part)
            continue

        leading = part[: len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()):]
        transformed = transform_atom(stripped, flags)
        out.append(f"{leading}{transformed}{tag}{trailing}")

    return tidy_spaces("".join(out))


def find_first_parenthesized_ovid_suffix_span(line: str, suffixes: set[str]):
    """
    Find the first balanced parenthesized group immediately followed by one
    of the requested Ovid suffixes, e.g. (a OR b).pt.
    """
    stack = []
    in_quote = False
    n = len(line)
    i = 0

    suffix_pat = re.compile(
        r"\s*\.(?P<suffix>" + "|".join(re.escape(s) for s in sorted(suffixes)) + r")\.?(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))",
        flags=re.I,
    )

    while i < n:
        ch = line[i]
        if ch == '"':
            in_quote = not in_quote
            i += 1
            continue

        if not in_quote:
            if ch == "(":
                stack.append(i)
            elif ch == ")" and stack:
                open_i = stack.pop()
                m = suffix_pat.match(line[i + 1:])
                if m:
                    suffix_start = i + 1 + m.start()
                    suffix_end = i + 1 + m.end()
                    return open_i, i, suffix_start, suffix_end, m.group("suffix").lower()
        i += 1

    return None


def convert_group_level_ovid_suffixes(line: str, suffixes: set[str], tag: str, transform_atom, flags: list[str] | None = None):
    changed = False

    while True:
        span = find_first_parenthesized_ovid_suffix_span(line, suffixes)
        if span is None:
            break

        open_i, close_i, suffix_start, suffix_end, suffix = span
        inner = line[open_i + 1: close_i]
        new_inner = distribute_ovid_suffix_inside_expr(
            normalize_boolean_outside_quotes(inner),
            tag,
            transform_atom,
            flags,
        )
        line = line[:open_i] + "(" + new_inner + ")" + line[suffix_end:]
        changed = True

    return line, changed


# ---------------------------------------------------------------------
# Rule 8. Convert publication types
# ---------------------------------------------------------------------

def convert_publication_types(line: str):
    flags: list[str] = []
    field_end = r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))"

    line, changed = convert_group_level_ovid_suffixes(
        line,
        {"pt"},
        "[pt]",
        transform_publication_type_atom,
        flags,
    )
    if changed:
        flags.append("distributed_group_level_publication_type_suffix")

    def replace_publication_type(match: re.Match) -> str:
        value = transform_publication_type_atom(match.group(1), flags)
        return f"{value}[pt]"

    line = re.sub(
        r"\b([A-Za-z][A-Za-z0-9 \-]+)\.pt\.?" + field_end,
        replace_publication_type,
        line,
        flags=re.I,
    )

    return line, flags


# ---------------------------------------------------------------------
# Rule 9. Convert floating subheadings
# ---------------------------------------------------------------------

def convert_subheadings(line: str):
    flags: list[str] = []
    field_end = r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))"

    line, changed = convert_group_level_ovid_suffixes(
        line,
        {"fs"},
        "[sh]",
        transform_subheading_atom,
        flags,
    )
    if changed:
        flags.append("distributed_group_level_floating_subheading_suffix")

    def fs_repl(m):
        raw = m.group(1).strip()
        expanded = transform_subheading_atom(raw, flags)
        if raw.lower() not in MESH_SUBHEADING_MAP and len(raw) <= 3:
            flags.append(f"unknown_floating_subheading_abbreviation_preserved:{raw}")
        return f"{expanded}[sh]"

    line = re.sub(
        r"\b([A-Za-z][A-Za-z0-9 \-]+)\.fs\.?" + field_end,
        fs_repl,
        line,
        flags=re.I,
    )

    return line, flags


# ---------------------------------------------------------------------
# Rules 10-11. Convert .nm. and .pa.
# ---------------------------------------------------------------------

def convert_nm_pa(line: str):
    flags: list[str] = []
    field_end = r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))"

    line, changed = convert_group_level_ovid_suffixes(
        line,
        {"nm"},
        "[nm]",
        transform_nm_atom,
        flags,
    )
    if changed:
        flags.append("distributed_group_level_nm_suffix")

    line, changed = convert_group_level_ovid_suffixes(
        line,
        {"pa"},
        "[pa]",
        transform_pa_atom,
        flags,
    )
    if changed:
        flags.append("distributed_group_level_pa_suffix")

    line = re.sub(
        r"\b([A-Za-z0-9][A-Za-z0-9 ,\-]*)\.nm\.?" + field_end,
        lambda m: f"{transform_nm_atom(m.group(1).strip(), flags)}[nm]",
        line,
        flags=re.I,
    )

    line = re.sub(
        r"\b([A-Za-z0-9][A-Za-z0-9 ,\-]*)\.pa\.?" + field_end,
        lambda m: f"{transform_pa_atom(m.group(1).strip(), flags)}[pa]",
        line,
        flags=re.I,
    )

    return line, flags


# ---------------------------------------------------------------------
# Rule 12. Convert field-tagged search terms token by token
# ---------------------------------------------------------------------

def choose_pubmed_field_tag(fields: list[str], audit_flags: list[str] | None = None) -> str:
    fields = [f.strip().lower() for f in fields if f.strip()]
    fset = set(fields)

    if "af" in fset:
        return "[all]"

    if fset & {"tw", "mp"}:
        return "[tw]"

    if fset & {"ot", "hw", "nm"}:
        if audit_flags is not None:
            if "ot" in fset:
                audit_flags.append("ovid_ot_approximated_as_pubmed_text_word")
            if "hw" in fset:
                audit_flags.append("ovid_hw_approximated_as_pubmed_text_word")
        return "[tw]"

    if fset <= {"ti", "ab", "kf"}:
        if fset == {"ti"}:
            return "[ti]"
        if fset == {"ab"}:
            if audit_flags is not None:
                audit_flags.append("ovid_abstract_field_approximated_as_pubmed_title_abstract")
            return "[tiab]"
        # kf alone, or any ti/ab/kf combination involving kf, maps to [tiab].
        return "[tiab]"

    if audit_flags is not None:
        audit_flags.append(f"unsupported_multifield_mapping_defaulted_to_tw:{','.join(fields)}")
    return "[tw]"


def apply_field(expr: str, tag: str, field: str = "") -> str:
    expr = expr.strip()

    if tag == "[ta]" and field == "jn":
        expr = expr.strip('"')
        return f'"{expr}"[ta]'

    # Quote single-token alphanumeric-hyphen terms before attaching a free-text
    # field tag to avoid ambiguous tokenization, e.g. S-1, SN-38, 5-FU.
    if (
        tag not in {"[ta]", "[pt]", "[sh]", "[nm]", "[pa]", "[mh]"}
        and not (expr.startswith('"') and expr.endswith('"'))
        and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\*?", expr)
    ):
        expr = f'"{expr}"'

    return f"{expr}{tag}"



def find_first_parenthesized_text_field_suffix_span(line: str):
    """Find a balanced group followed by a free-text Ovid field list."""
    stack: list[int] = []
    in_quote = False
    suffix_pat = re.compile(
        r"\s*\.(?P<fields>(?:ti|ab|tw|kf|mp|af|jn|jw|ot|hw)"
        r"(?:\s*,\s*(?:ti|ab|tw|kf|mp|af|jn|jw|ot|hw))*)\.?"
        r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))",
        flags=re.I,
    )

    for i, ch in enumerate(line):
        if ch == '"':
            in_quote = not in_quote
            continue
        if in_quote:
            continue
        if ch == '(':
            stack.append(i)
        elif ch == ')' and stack:
            open_i = stack.pop()
            m = suffix_pat.match(line[i + 1:])
            if m:
                return open_i, i, i + 1 + m.start(), i + 1 + m.end(), m.group("fields")
    return None


def convert_parenthesized_text_field_suffixes(line: str, flags: list[str]):
    changed = False
    while True:
        span = find_first_parenthesized_text_field_suffix_span(line)
        if span is None:
            break
        open_i, close_i, _suffix_start, suffix_end, raw_fields = span
        fields = [f.strip().lower() for f in raw_fields.split(',')]
        tag = choose_pubmed_field_tag(fields, flags)
        inner = line[open_i + 1:close_i]
        transformed = distribute_ovid_suffix_inside_expr(
            normalize_boolean_outside_quotes(inner),
            tag,
            lambda atom, _flags=None: atom.strip(),
            flags,
        )
        line = line[:open_i] + '(' + transformed + ')' + line[suffix_end:]
        changed = True
    return line, changed


def convert_field_tags(line: str):
    flags: list[str] = []

    line, group_changed = convert_parenthesized_text_field_suffixes(line, flags)
    if group_changed:
        flags.append("distributed_parenthesized_ovid_text_field_suffix")

    simple = {
        "ti": "[ti]",
        "ab": "[tiab]",
        "tw": "[tw]",
        "kf": "[tiab]",
        "mp": "[tw]",
        "af": "[all]",
        "jw": "[ta]",
        "ot": "[tw]",
        "hw": "[tw]",
    }


    whole_line = re.match(
        r"^(?P<expr>.+?)\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})*)\s*\.?$",
        line,
        flags=re.I,
    )

    if whole_line:
        expr = whole_line.group("expr").strip()
        fields = [f.strip().lower() for f in whole_line.group("fields").split(",")]

        if not re.search(r'\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.', expr, flags=re.I):
            safe_scope = is_wrapped_by_outer_parens(expr) or not top_level_contains_operator(expr, include_proximity=True)
            if safe_scope:
                if fields == ["jn"]:
                    return apply_field(expr, "[ta]", "jn"), flags
                if fields == ["jw"]:
                    return apply_field(expr, "[ta]", "jw"), flags

                tag = choose_pubmed_field_tag(fields, flags)
                return apply_field(expr, tag, fields[0] if fields else ""), flags

    start = r'(?<![A-Za-z0-9])'

    multifield_pat = re.compile(
        start +
        r'(?P<expr>'
        r'"[^"]+"'
        r'|'
        r'\([^()]+\)'
        r'|'
        r'(?!(?:and|or|not|adj\d*|next)\b)'
        r'[A-Za-z0-9*$\-]+(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*$\-]+)*'
        r')'
        r'\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})+)\s*\.?',
        flags=re.I,
    )

    line = multifield_pat.sub(
        lambda m: apply_field(
            m.group("expr"),
            choose_pubmed_field_tag([f.strip().lower() for f in m.group("fields").split(",")], flags),
        ),
        line,
    )

    # Inline .jn.
    line = re.sub(
        start +
        r'(?P<expr>'
        r'"[^"]+"'
        r'|'
        r'(?!(?:and|or|not|adj\d*|next)\b)'
        r'[A-Za-z0-9*$\-]+(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*$\-]+)*'
        r')'
        r'\s*\.jn\.?',
        lambda m: apply_field(m.group("expr"), "[ta]", "jn"),
        line,
        flags=re.I,
    )

    simple_pat = re.compile(
        start +
        r'(?P<expr>'
        r'"[^"]+"'
        r'|'
        r'\([^()]+\)'
        r'|'
        r'(?!(?:and|or|not|adj\d*|next)\b)'
        r'[A-Za-z0-9*$\-]+(?:\s+(?!(?:and|or|not|adj\d*|next)\b)[A-Za-z0-9*$\-]+)*'
        r')'
        r'\s*\.(?P<field>ti|ab|tw|kf|mp|af|jw|ot|hw)\.?',
        flags=re.I,
    )

    line = simple_pat.sub(
        lambda m: apply_field(
            m.group("expr"),
            simple[m.group("field").lower()],
            m.group("field").lower(),
        ),
        line,
    )

    return line, flags

# ---------------------------------------------------------------------
# Rule 13. Final recursive distribution of group-level field tags
# ---------------------------------------------------------------------


PUBMED_TAG_AT_END_RE = re.compile(r"\[[^\]]+\]\s*$")

DISTRIBUTABLE_FIELD_TAGS = {
    "tw": "[tw]",
    "Text Word": "[tw]",
    "Text Words": "[tw]",
    "all": "[all]",
    "All Fields": "[all]",
    "ti": "[ti]",
    "Title": "[ti]",
    "ab": "[tiab]",
    "Abstract": "[tiab]",
    "tiab": "[tiab]",
    "Title/Abstract": "[tiab]",
    "ta": "[ta]",
    "Journal": "[ta]",
}

DISTRIBUTABLE_TAG_PATTERN = re.compile(
    r"\s*\[(tw|Text Word|Text Words|all|All Fields|ti|Title|ab|Abstract|tiab|Title/Abstract|ta|Journal)\]",
    flags=re.I,
)



def canonical_distributable_tag(tag_name: str) -> str:
    for k, v in DISTRIBUTABLE_FIELD_TAGS.items():
        if k.lower() == tag_name.lower():
            return v
    # Short tags are canonical in final output.
    return f"[{tag_name.lower()}]"


def is_wrapped_by_outer_parens(expr: str) -> bool:
    """
    True if expr is exactly one parenthesized expression, ignoring outer spaces.
    """
    s = expr.strip()
    if not (s.startswith("(") and s.endswith(")")):
        return False

    depth = 0
    in_quote = False

    for i, ch in enumerate(s):
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    return False

    return depth == 0


def is_standalone_boolean_at(expr: str, i: int):
    """
    Return a Boolean operator match at expr[i:] only when AND/OR/NOT is a
    standalone token in the original string.

    Do not rely on re.match(..., expr[i:]) with \b because slicing makes the
    start of the slice look like a word boundary.  That incorrectly splits
    words ending in operator-looking text, e.g. translator* -> translat OR *.

    A Boolean token must be separated by whitespace, parentheses, or line
    boundaries.  This follows the converter rule that OR/AND/NOT inside a
    searched word must not be interpreted as Boolean syntax.
    """
    m = re.match(r"(?:AND|OR|NOT)", expr[i:], flags=re.I)
    if not m:
        return None

    before = expr[i - 1] if i > 0 else ""
    after_i = i + len(m.group(0))
    after = expr[after_i] if after_i < len(expr) else ""

    before_ok = (i == 0) or before.isspace() or before in "()"
    after_ok = (after_i == len(expr)) or after.isspace() or after in "()"

    if before_ok and after_ok:
        return m
    return None


def split_top_level_boolean(expr: str):
    """
    Split an expression into top-level pieces and Boolean operators.
    Parentheses and quoted strings are respected.

    Boolean recognition is token-based in the original expression.  It must
    not split words such as operator, donor, notation, or translator*.
    """
    parts = []
    start = 0
    i = 0
    depth = 0
    in_quote = False
    n = len(expr)

    while i < n:
        ch = expr[i]

        if ch == '"':
            in_quote = not in_quote
            i += 1
            continue

        if not in_quote:
            if ch == "(":
                depth += 1
                i += 1
                continue
            if ch == ")":
                depth -= 1
                i += 1
                continue

            if depth == 0:
                m = is_standalone_boolean_at(expr, i)
                if m:
                    before = expr[start:i]
                    if before:
                        parts.append(before)
                    parts.append(m.group(0).upper())
                    i += len(m.group(0))
                    start = i
                    continue

        i += 1

    tail = expr[start:]
    if tail:
        parts.append(tail)

    return parts


# ---------------------------------------------------------------------
# Empty-set Boolean simplification
# ---------------------------------------------------------------------

def split_by_top_level_operator(expr: str, op: str):
    """Split expr by a chosen top-level Boolean operator."""
    parts = split_top_level_boolean(expr)
    groups = []
    current = []
    found = False

    for part in parts:
        if re.fullmatch(op, part.strip(), flags=re.I):
            groups.append("".join(current).strip())
            current = []
            found = True
        else:
            current.append(part)

    groups.append("".join(current).strip())
    return groups, found


def strip_balanced_outer_parens(expr: str) -> str:
    s = expr.strip()
    while is_wrapped_by_outer_parens(s):
        s = s[1:-1].strip()
    return s


def _simplify_empty_expr_core(expr: str, flags: list[str], context: str = "") -> str:
    """
    Recursively simplify Boolean expressions containing EMPTY_ATOM.

    Rules:
        A OR EMPTY   -> A
        A AND EMPTY  -> EMPTY
        A NOT EMPTY  -> A
        EMPTY NOT A  -> EMPTY
    """
    expr = expr.strip()

    if not expr:
        return expr

    if expr == EMPTY_ATOM or expr == PUBMED_EMPTY_QUERY:
        return EMPTY_ATOM

    # Simplify one fully wrapped expression first.
    if is_wrapped_by_outer_parens(expr):
        inner = expr[1:-1]
        simplified_inner = _simplify_empty_expr_core(inner, flags, context=context)
        if simplified_inner == EMPTY_ATOM:
            return EMPTY_ATOM
        return f"({simplified_inner})"

    # OR has the lowest effective binding in the converter simplifier.
    groups, found = split_by_top_level_operator(expr, "OR")
    if found:
        simplified = [
            _simplify_empty_expr_core(g, flags, context=context)
            for g in groups
            if g.strip()
        ]
        non_empty = [g for g in simplified if g != EMPTY_ATOM]
        if len(non_empty) != len(simplified):
            flags.append("empty_atoms_removed_from_or_expression")
        if not non_empty:
            flags.append("or_expression_resolved_to_empty_set")
            return EMPTY_ATOM
        return " OR ".join(non_empty)

    groups, found = split_by_top_level_operator(expr, "AND")
    if found:
        simplified = [
            _simplify_empty_expr_core(g, flags, context=context)
            for g in groups
            if g.strip()
        ]
        if any(g == EMPTY_ATOM for g in simplified):
            flags.append("empty_atom_caused_and_expression_to_be_empty")
            return EMPTY_ATOM
        return " AND ".join(simplified)

    groups, found = split_by_top_level_operator(expr, "NOT")
    if found:
        if not groups:
            return expr
        lhs = _simplify_empty_expr_core(groups[0], flags, context=context)
        for rhs_raw in groups[1:]:
            rhs = _simplify_empty_expr_core(rhs_raw, flags, context=context)
            if lhs == EMPTY_ATOM:
                flags.append("empty_lhs_caused_not_expression_to_be_empty")
                return EMPTY_ATOM
            if rhs == EMPTY_ATOM:
                flags.append("empty_rhs_removed_from_not_expression")
                continue
            lhs = f"{lhs} NOT {rhs}"
        return lhs

    return expr


def simplify_empty_atoms_in_line(line: str, flags: list[str], context: str = ""):
    """
    Simplify EMPTY_ATOM in a converted line. If a whole-line Ovid field suffix
    is present, simplify the expression before reattaching the suffix. If the
    expression becomes empty, drop the suffix and return EMPTY_ATOM.
    """
    if EMPTY_ATOM not in line and PUBMED_EMPTY_QUERY not in line:
        return line, False

    original = line

    whole_line = re.match(
        r"^(?P<expr>.+?)\s*\.(?P<fields>[a-z]{2}(?:\s*,\s*[a-z]{2})*)\s*\.?$",
        line,
        flags=re.I,
    )

    if whole_line:
        expr = whole_line.group("expr").strip()
        fields = whole_line.group("fields")
        if not re.search(r'\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.', expr, flags=re.I):
            simplified = _simplify_empty_expr_core(expr, flags, context=context)
            if simplified == EMPTY_ATOM:
                flags.append("line_resolved_to_empty_set_after_short_root_truncation_removal")
                return EMPTY_ATOM, original != EMPTY_ATOM
            return simplified + f".{fields}.", simplified + f".{fields}." != original

    simplified = _simplify_empty_expr_core(line, flags, context=context)
    if simplified == EMPTY_ATOM:
        flags.append("line_resolved_to_empty_set_after_short_root_truncation_removal")
    return simplified, simplified != original


def finalize_empty_atoms(line: str, flags: list[str]) -> str:
    """Render any remaining internal EMPTY_ATOM marker as a PubMed empty set."""
    if EMPTY_ATOM not in line:
        return line

    line, changed = simplify_empty_atoms_in_line(line, flags, context="final")
    if line == EMPTY_ATOM:
        flags.append("final_line_rendered_as_pubmed_empty_set")
    return render_empty_atoms(line)


def referenced_line_numbers(expr: str):
    return [int(x) for x in re.findall(r"#(\d+)", expr)]


def simplify_empty_line_references(expr: str, empty_line_numbers: set[int], flags: list[str], current_num: int):
    """
    Replace references to already-empty lines with EMPTY_ATOM, simplify the
    Boolean expression, and emit downstream warnings.
    """
    refs = referenced_line_numbers(expr)
    empty_refs = sorted({r for r in refs if r in empty_line_numbers})
    if not empty_refs:
        return expr, False

    original = expr

    def repl(m):
        n = int(m.group(1))
        if n in empty_line_numbers:
            return EMPTY_ATOM
        return m.group(0)

    expr_with_empty = re.sub(r"#(\d+)", repl, expr)

    # Warning classification based on the expression where empty refs appear.
    upper_expr = normalize_boolean_outside_quotes(expr)
    for ref in empty_refs:
        if re.search(r"\bAND\b", upper_expr, flags=re.I):
            flags.append(f"empty_line_reference_caused_and_expression_to_be_empty:#{ref} in #{current_num}")
        elif re.search(r"\bOR\b", upper_expr, flags=re.I):
            flags.append(f"empty_line_reference_removed_from_or_expression:#{ref} in #{current_num}")
        elif re.search(r"\bNOT\b", upper_expr, flags=re.I):
            flags.append(f"empty_line_reference_simplified_in_not_expression:#{ref} in #{current_num}")
        else:
            flags.append(f"empty_line_reference_replaced:#{ref} in #{current_num}")

    simplified, changed = simplify_empty_atoms_in_line(expr_with_empty, flags, context=f"line_reference_#{current_num}")
    simplified = finalize_empty_atoms(simplified, flags)
    return simplified, simplified != original

def should_not_add_field(atom: str) -> bool:
    core = atom.strip()

    if not core:
        return True

    if core in {EMPTY_ATOM, DROP_ATOM, MANUAL_REVIEW_ATOM} or core == PUBMED_EMPTY_QUERY:
        return True

    if re.fullmatch(r"AND|OR|NOT", core, flags=re.I):
        return True

    if re.fullmatch(r"#?\d+", core):
        return True

    # Already has a PubMed field tag at the end, e.g. [Mesh], [mh], [pt], [tiab].
    if PUBMED_TAG_AT_END_RE.search(core):
        return True

    return False


def add_field_to_atom(atom: str, tag: str) -> str:
    prefix = atom[: len(atom) - len(atom.lstrip())]
    suffix = atom[len(atom.rstrip()):]
    core = atom.strip()

    if should_not_add_field(core):
        return atom

    # Robustness for PubMed/E-utilities: quote single-token alphanumeric-hyphen
    # terms when a field tag is distributed into a Boolean group, e.g.
    # S-1, SN-38, 5-FU, accu-chek.
    if (
        not (core.startswith('"') and core.endswith('"'))
        and re.fullmatch(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)+\*?", core)
    ):
        core = f'"{core}"'

    return f"{prefix}{core} {tag}{suffix}"


def distribute_field_inside_expr(expr: str, tag: str) -> str:
    """
    Recursively push a field tag into terminal free-text atoms.

    Example:
        a OR (b AND c)
    becomes:
        a [Text Word] OR (b [Text Word] AND c [Text Word])
    """
    parts = split_top_level_boolean(expr)
    out = []

    for part in parts:
        stripped = part.strip()

        if re.fullmatch(r"AND|OR|NOT", stripped, flags=re.I):
            out.append(f" {stripped.upper()} ")
            continue

        if is_wrapped_by_outer_parens(stripped):
            leading = part[: len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            inner = stripped[1:-1]
            out.append(f"{leading}({distribute_field_inside_expr(inner, tag)}){trailing}")
            continue

        out.append(add_field_to_atom(part, tag))

    return "".join(out)


def find_first_group_field_tag_span(line: str):
    """
    Find the first balanced parenthesized group immediately followed by a
    distributable field tag.

    Returns (open_index, close_index, tag_start, tag_end, canonical_tag), or None.
    """
    stack = []
    in_quote = False
    i = 0
    n = len(line)

    while i < n:
        ch = line[i]

        if ch == '"':
            in_quote = not in_quote
            i += 1
            continue

        if not in_quote:
            if ch == "(":
                stack.append(i)
            elif ch == ")" and stack:
                open_i = stack.pop()
                after = line[i + 1:]
                m = DISTRIBUTABLE_TAG_PATTERN.match(after)
                if m:
                    tag_start = i + 1 + m.start()
                    tag_end = i + 1 + m.end()
                    tag = canonical_distributable_tag(m.group(1))
                    return open_i, i, tag_start, tag_end, tag

        i += 1

    return None


def distribute_group_field_tags(line: str):
    """
    Final cleanup: convert selected group-level field tags into atom-level tags.

    Examples:
        (sepsis OR septic*) [Text Word]
            -> (sepsis [Text Word] OR septic* [Text Word])
        (aspirin OR placebo) [All Fields]
            -> (aspirin [All Fields] OR placebo [All Fields])
    """
    changed = False

    while True:
        span = find_first_group_field_tag_span(line)
        if span is None:
            break

        open_i, close_i, tag_start, tag_end, tag = span
        inner = line[open_i + 1: close_i]
        new_inner = distribute_field_inside_expr(inner, tag)
        line = line[:open_i] + "(" + new_inner + ")" + line[tag_end:]
        changed = True

    return line, changed


# Backward-compatible function name for older callers.
def distribute_group_text_words(line: str):
    return distribute_group_field_tags(line)



# ---------------------------------------------------------------------
# Rule 14. Final ESearch-safe normalization
# ---------------------------------------------------------------------

LEGACY_TAG_NORMALIZATION = {
    "Text Word": "tw",
    "Text Words": "tw",
    "All Fields": "all",
    "Title": "ti",
    "Abstract": "tiab",
    "Title/Abstract": "tiab",
    "ab": "tiab",
    "Mesh": "mh",
    "MeSH Terms": "mh",
    "Publication Type": "pt",
    "Subheading": "sh",
    "MeSH Subheading": "sh",
    "Journal": "ta",
    "Date - Publication": "dp",
    "Supplementary Concept": "nm",
    "Pharmacological Action": "pa",
}


def final_esearch_safe_normalize(line: str, flags: list[str] | None = None) -> str:
    """Normalize legacy/readable PubMed tags to short executable tags."""
    if flags is None:
        flags = []

    def tag_repl(m):
        raw = m.group(1).strip()
        norm = LEGACY_TAG_NORMALIZATION.get(raw, raw)
        return f"[{norm.lower()}]"

    before = line
    line = re.sub(r"\[([^\]]+)\]", tag_repl, line)

    # Remove spaces before tags, e.g. random* [tiab] -> random*[tiab].
    line = re.sub(r"\s+\[([a-z]+(?::noexp)?)\]", r"[\1]", line)

    # Ensure a PubMed field tag does not glue to a following Boolean operator,
    # e.g. "Analgesia"[mh]OR -> "Analgesia"[mh] OR.
    line = re.sub(
        r"(\[[a-z]+(?::noexp)?\])(?=(?:AND|OR|NOT)\b)",
        r"\1 ",
        line,
        flags=re.I,
    )

    if line != before:
        flags.append("final_esearch_safe_tag_normalization_applied")

    return line


# ---------------------------------------------------------------------
# v10 audit helper: free-text Boolean-looking words are underdetermined
# ---------------------------------------------------------------------

def _looks_like_free_text_operand_for_boolean_phrase_risk(operand: str) -> bool:
    """Return True only for a genuinely unquoted, untagged free-text operand."""
    x = operand.strip()
    if not x:
        return False

    # A parenthesized line-reference/controlled group is not free text.
    if is_wrapped_by_outer_parens(x):
        inner = x[1:-1].strip()
        if re.search(r"#\d+", inner) or re.search(r"\[[^\]]+\]", inner):
            return False
        x = inner

    if re.search(r"#\d+", x):
        return False
    if re.fullmatch(r"#?\d+", x):
        return False
    if re.search(r"\[[^\]]+\]", x):
        return False
    if x in {EMPTY_ATOM, DROP_ATOM, MANUAL_REVIEW_ATOM, PUBMED_EMPTY_QUERY}:
        return False
    if re.fullmatch(r"has[a-z0-9]+", x, flags=re.I):
        return False
    if x.startswith('"') and x.endswith('"'):
        return False

    # Controlled/special Ovid suffixes are not unresolved free text.
    if re.search(r"\.(?:sh|pt|fs|nm|pa|cm)\.?$", x, flags=re.I):
        return False
    if re.search(r"/(?:[a-z]{1,3}(?:\s*,\s*[a-z]{1,3})*)?$", x, flags=re.I):
        return False

    # Remove a local free-text field suffix only for word counting.
    x = re.sub(r"\.(?:ti|ab|tw|kf|mp|af|jn|jw|ot|hw)(?:\s*,\s*[a-z]{2})*\.?$", "", x, flags=re.I).strip()
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9*$\-]*", x)
    return len(words) >= 2


def audit_free_text_boolean_phrase_boundary_risk(line: str, flags: list[str]) -> None:
    """
    Record ambiguity only when both sides of a standalone Boolean operator are
    genuine unquoted free-text phrases. Controlled objects, line-reference
    groups, relation tokens, and tagged expressions are excluded.
    """
    if is_boolean_reference_line(line):
        return
    parts = split_top_level_boolean(line)
    if len(parts) < 3:
        return
    for i, part in enumerate(parts):
        if not re.fullmatch(r"AND|OR|NOT", part.strip(), flags=re.I):
            continue
        left = parts[i - 1] if i > 0 else ""
        right = parts[i + 1] if i + 1 < len(parts) else ""
        if (
            _looks_like_free_text_operand_for_boolean_phrase_risk(left)
            and _looks_like_free_text_operand_for_boolean_phrase_risk(right)
        ):
            snippet = tidy_spaces("".join(parts[max(0, i-1): min(len(parts), i+2)]))
            flags.append(f"free_text_boolean_word_may_be_phrase_boundary:{snippet}")
            return

# ---------------------------------------------------------------------
# Main line conversion
# ---------------------------------------------------------------------
def normalize_mixed_line_references(
    line: str,
    known_line_numbers: set[int] | None = None,
):
    """
    Convert mixed numeric line references only when the number is an actual
    strategy line number. This avoids corrupting years, doses, identifiers,
    or other searchable numbers such as ``2020 and Asthma/``.
    """
    flags: list[str] = []
    known = known_line_numbers or set()

    def convert_num(raw: str) -> str:
        n = int(raw)
        if n in known:
            return f"#{n}"
        if known:
            flags.append(f"mixed_numeric_token_not_converted_to_line_reference:{n}")
        return raw

    line = re.sub(
        r'(^|\()\s*(\d+)(?=\s+(?:and|or|not)\b)',
        lambda m: f"{m.group(1)}{convert_num(m.group(2))}",
        line,
        flags=re.I,
    )

    line = re.sub(
        r'\b(and|or|not)\s+(\d+)(?=\s*(?:$|\)|\b(?:and|or|not)\b))',
        lambda m: f"{m.group(1).upper()} {convert_num(m.group(2))}",
        line,
        flags=re.I,
    )

    return line, flags


def _replace_known_cm_relations(text: str, flags: list[str] | None = None) -> str:
    """
    Replace known Comments/Corrections relation labels inside a .cm. expression
    before Boolean splitting. This protects labels containing words such as
    'and' from being split as Boolean syntax.
    """
    out = text

    for label, token in sorted(COMMENT_CORRECTION_CM_MAP.items(), key=lambda kv: len(kv[0]), reverse=True):
        label_pat = re.escape(label).replace(r"\ ", r"\s+")

        def known_repl(_m, *, _label=label, _token=token):
            if flags is not None:
                flags.append(f"converted_cm_comments_corrections_relation:{_label}->{_token}")
            return _token

        # Quoted form, e.g. "comment on"
        out = re.sub(
            r'"' + label_pat + r'"',
            known_repl,
            out,
            flags=re.I,
        )

        # Unquoted form with token boundaries.
        out = re.sub(
            r'(?<![A-Za-z0-9])' + label_pat + r'(?![A-Za-z0-9])',
            known_repl,
            out,
            flags=re.I,
        )

    return out


def convert_cm_expression(expr: str, flags: list[str]) -> str:
    """
    Convert the inside of a group-level .cm. expression.

    Example:
        (comment on OR erratum for).cm.
        -> (hascommenton OR haserratumfor)
    """
    expr = _replace_known_cm_relations(expr, flags)
    expr = normalize_boolean_outside_quotes(expr)

    parts = split_top_level_boolean(expr)
    out = []

    for part in parts:
        stripped = part.strip()

        if not stripped:
            out.append(part)
            continue

        if re.fullmatch(r"AND|OR|NOT", stripped, flags=re.I):
            out.append(f" {stripped.upper()} ")
            continue

        if is_wrapped_by_outer_parens(stripped):
            leading = part[: len(part) - len(part.lstrip())]
            trailing = part[len(part.rstrip()):]
            inner = stripped[1:-1]
            out.append(f"{leading}({convert_cm_expression(inner, flags)}){trailing}")
            continue

        if stripped.lower() in COMMENT_CORRECTION_CM_TOKENS:
            out.append(part)
            continue

        leading = part[: len(part) - len(part.lstrip())]
        trailing = part[len(part.rstrip()):]
        out.append(f"{leading}{transform_cm_atom(stripped, flags)}{trailing}")

    return tidy_spaces("".join(out))


def convert_comment_fields(line: str):
    """
    Convert Ovid MEDLINE .cm. Comments/Corrections field expressions before
    free-text phrase quotation.

    Known .cm. relation labels are mapped to PubMed Comments/Corrections
    relation tokens, e.g.:
        comment on.cm.      -> hascommenton
        comment in.cm.      -> hascommentin
        erratum for.cm.     -> haserratumfor
        retraction of.cm.   -> hasretractionof
        (comment on OR erratum for).cm. -> (hascommenton OR haserratumfor)

    Unknown .cm. labels are not silently converted to Comment[pt]. They are
    rendered as all-fields text and audited.
    """
    flags: list[str] = []
    field_end = r"(?=\s*(?:$|\)|\(|\bAND\b|\bOR\b|\bNOT\b))"

    # Group-level .cm. distribution.
    changed = False
    while True:
        span = find_first_parenthesized_ovid_suffix_span(line, {"cm"})
        if span is None:
            break

        open_i, close_i, suffix_start, suffix_end, _suffix = span
        inner = line[open_i + 1: close_i]
        new_inner = convert_cm_expression(inner, flags)
        line = line[:open_i] + "(" + new_inner + ")" + line[suffix_end:]
        changed = True

    if changed:
        flags.append("distributed_group_level_comment_correction_cm_suffix")

    # Quoted inline .cm. form, e.g. "comment on".cm.
    line = re.sub(
        r'"(?P<label>[^"]+)"\s*\.cm\.?' + field_end,
        lambda m: transform_cm_atom(m.group("label"), flags),
        line,
        flags=re.I,
    )

    # Known unquoted inline .cm. forms. Longest labels first to avoid partial
    # matches such as "republished in" inside "corrected and republished in".
    known_alt = "|".join(
        re.escape(label).replace(r"\ ", r"\s+")
        for label in sorted(COMMENT_CORRECTION_CM_MAP, key=len, reverse=True)
    )

    line = re.sub(
        r'\b(?P<label>' + known_alt + r')\s*\.cm\.?' + field_end,
        lambda m: transform_cm_atom(m.group("label"), flags),
        line,
        flags=re.I,
    )

    # Generic fallback for simple unknown .cm. labels.
    line = re.sub(
        r"\b(?P<label>[A-Za-z][A-Za-z ]*)\s*\.cm\.?" + field_end,
        lambda m: transform_cm_atom(m.group("label"), flags),
        line,
        flags=re.I,
    )

    return line, flags

def convert_line(
    expr: str,
    known_line_numbers: set[int] | None = None,
    *,
    omit_ovid_update_dates: bool = False,
):
    flags = []

    line = normalize_unicode(expr.strip())

    # Version 18 strict whole-line rule. Short-circuiting prevents generic
    # ``.sh.`` handling from turning the singular words into [tw] terms.
    if is_strict_animal_only_filter(line):
        return (
            "(animals[mh] NOT humans[mh])",
            ["v18_strict_animal_only_filter_applied"],
        )

    if omit_ovid_update_dates and is_pure_ovid_ed_dt_update_line(line):
        return (
            DROP_ATOM,
            ["ovid_ed_dt_update_line_omitted_external_end_date_applied"],
        )

    # Convert mixed line references only when they match actual strategy rows.
    line, mixed_ref_flags = normalize_mixed_line_references(line, known_line_numbers)
    flags.extend(mixed_ref_flags)

    # High-priority exact RCT/animal filters must run before generic MeSH conversion.
    line = convert_cochrane_rct_filter_terms(line)
  
    # Ovid .cm. must be protected before phrase quotation.
    line, cm_flags = convert_comment_fields(line)
    flags.extend(cm_flags)

    # Convert only exact whitelisted slash publication-type headings before
    # generic MeSH handling. No fuzzy study-design inference is used.
    line, slash_pt_flags = convert_exact_publication_type_slash_descriptors(line)
    flags.extend(slash_pt_flags)

    # Classify wildcard-bearing slash atoms before ordinary MeSH conversion.
    line, wc_slash_flags = convert_wildcard_bearing_slash_atoms(line)
    flags.extend(wc_slash_flags)

    # Convert/protect ordinary MeSH descriptors before wildcard and phrase processing.
    line, mesh_flags = convert_mesh_descriptors(line)
    flags.extend(mesh_flags)

    # v10 audit: unquoted free-text AND/OR/NOT is treated as Boolean logic,
    # but may have been intended as phrase-internal wording. Audit only.
    audit_free_text_boolean_phrase_boundary_risk(line, flags)

    # Rule 1: ? and # wildcard expansion.
    line, q_flags = expand_question_hash_marks(line)
    flags.extend(q_flags)

    # Rule 4: truncation.
    line, trunc_flags = convert_truncation(line)
    flags.extend(trunc_flags)

    # Rule 5: adjacency. Keep unparenthesized final field suffixes local:
    #   upper adj3 respiratory tract infection*.tw.
    # -> upper AND "respiratory tract infection*"[tw]
    before_adj = line
    if re.search(r"\b(adj\d*|next)\b", line, flags=re.I):
        flags.append("ovid_adjacency_converted_to_and")
        if not re.match(r"^\s*\(.*\)\s*\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.?\s*$", line, flags=re.I):
            if re.search(r"\b(adj\d*|next)\b.+\.[a-z]{2}(?:\s*,\s*[a-z]{2})*\.?\s*$", line, flags=re.I):
                flags.append("unparenthesized_proximity_field_scope_treated_as_local")
    line = convert_adjacency(line)

    # Normalize Boolean operators before DROP/EMPTY simplification.
    line = normalize_boolean_outside_quotes(line)

    # Version 16: after proximity has become Boolean syntax, remove unknown
    # short-root atoms and simplify nested Boolean groups safely.
    line, drop_simplified = simplify_drop_atoms_in_line(line, flags, context="post_truncation_and_adjacency")
    if drop_simplified:
        flags.append("simplified_dropped_short_root_atoms_after_truncation")
    if line == DROP_ATOM:
        flags.append("entire_line_removed_after_short_root_cleanup")
        return DROP_ATOM, list(dict.fromkeys(flags))

    # Simplify internal EMPTY_ATOM before field-tag conversion.
    line, empty_simplified = simplify_empty_atoms_in_line(line, flags, context="post_truncation")
    if empty_simplified:
        flags.append("simplified_empty_atoms_after_truncation")

    # Convert generic controlled-field suffixes before free-text phrase quotation.
    # Otherwise multi-word atoms such as clinical trial.pt., adverse effects.fs.,
    # Insulin Glargine.nm., and Protein Kinase Inhibitors.pa. may be incorrectly
    # quoted as free-text phrases before their Ovid suffix is recognized.
    line, pt_flags = convert_publication_types(line)
    flags.extend(pt_flags)

    line, sh_flags = convert_subheadings(line)
    flags.extend(sh_flags)

    line, nm_pa_flags = convert_nm_pa(line)
    flags.extend(nm_pa_flags)

    # Ovid runtime stopwords apply only to the remaining explicit free-text
    # objects. Controlled headings have already been resolved and protected.
    line, stopword_flags = convert_ovid_stopword_free_text(line)
    flags.extend(stopword_flags)

    # Rule 2: phrase quotation in remaining free-text expressions only.
    line = quote_free_text_field_expressions(line)

    # Rule 3: Boolean line references.
    line = convert_boolean_references(line)

    # Boolean normalization outside quotes.
    line = normalize_boolean_outside_quotes(line)

    # Re-apply exact RCT terms in case previous steps exposed them.
    line = convert_cochrane_rct_filter_terms(line)

    # Generic free-text field conversions. Controlled suffixes above are kept as
    # a second pass here for safety, but the important pass is before quotation.
    line, pt_flags = convert_publication_types(line)
    flags.extend(pt_flags)

    line, sh_flags = convert_subheadings(line)
    flags.extend(sh_flags)

    line, nm_pa_flags = convert_nm_pa(line)
    flags.extend(nm_pa_flags)

    line, field_flags = convert_field_tags(line)
    flags.extend(field_flags)

    # Rule 13: distribute selected group-level field tags to terminal atoms.
    line, distributed = distribute_group_field_tags(line)
    if distributed:
        flags.append("distributed_group_level_field_tags")

    # A second EMPTY simplification pass catches any remaining markers after
    # phrase quotation and field-tag conversion.
    line, empty_simplified = simplify_empty_atoms_in_line(line, flags, context="post_field_tags")
    if empty_simplified:
        flags.append("simplified_empty_atoms_after_field_tags")

    line = normalize_boolean_outside_quotes(line)
    line = tidy_spaces(line)
    line = finalize_empty_atoms(line, flags)
    line = final_esearch_safe_normalize(line, flags)
    line = tidy_spaces(line)

    # Deduplicate audit flags while preserving order.
    flags = list(dict.fromkeys(flags))

    return line, flags


# ---------------------------------------------------------------------
# Medline block extraction and row parsing
# ---------------------------------------------------------------------

def find_medline_block(lines):
    start = None

    for i, line in enumerate(lines):
        if line.strip().lower() == "medline:":
            start = i
            break

    if start is None:
        return None, None

    end = len(lines)

    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip().lower()

        if stripped in STOP_HEADINGS:
            end = j
            break

    return start, end


def parse_strategy_rows(block_lines):
    """
    Parse numbered Ovid rows, including Word list labels emitted on a line of
    their own (for example ``1.`` followed by ``Ankle Fractures/``).

    A standalone integer without ``.`` or ``)`` is not treated as a row label;
    this avoids confusing an unnumbered Boolean-reference expression with a
    Word list number. When a punctuated list label has no same-line text, the
    next physical line is always its expression, even when that expression
    begins with a numeric line reference such as ``10 and 21``.
    """
    cleaned = [x.strip() for x in block_lines if x.strip()]
    punctuated_re = re.compile(r"^(?P<num>\d+)[\.)](?:\s*(?P<expr>.*))?$")
    plain_re = re.compile(r"^(?P<num>\d+)\s+(?P<expr>.+)$")
    has_numbered = any(punctuated_re.match(x) or plain_re.match(x) for x in cleaned)

    if not has_numbered:
        return [(i, expr) for i, expr in enumerate(cleaned, start=1)]

    rows: list[tuple[int, str]] = []
    current_num: int | None = None
    current_parts: list[str] = []

    for line in cleaned:
        # A standalone Word list label owns the following physical line. This
        # check must precede the unpunctuated-row pattern because a valid
        # Boolean expression may itself begin with a number.
        if current_num is not None and not current_parts:
            current_parts.append(line)
            continue

        # A physical continuation beginning with a calendar year is not an
        # Ovid row merely because it starts with digits. This is especially
        # common in wrapped date/publication expressions from Word lists.
        possible_plain = plain_re.match(line)
        if (
            current_num is not None
            and current_parts
            and possible_plain
            and 1000 <= int(possible_plain.group("num")) <= 2999
            and current_num < 1000
        ):
            current_parts.append(line)
            continue

        match = punctuated_re.match(line)
        if match is None:
            match = plain_re.match(line)

        if match:
            if current_num is not None:
                rows.append((current_num, " ".join(current_parts).strip()))

            current_num = int(match.group("num"))
            initial = match.group("expr") or ""
            current_parts = [initial.strip()] if initial.strip() else []
            continue

        if current_num is not None:
            current_parts.append(line)

    if current_num is not None:
        rows.append((current_num, " ".join(current_parts).strip()))

    return rows


RTF_CONTROL_RESIDUE_RE = re.compile(
    r"\\[A-Za-z]+|"
    r"\b(?:pardeftab|partightenfactor|eftab\d+|tightenfactor\d+|"
    r"ilvl\d+|ls\d+|tx\d+|fi-?\d+|li-?\d+)\b",
    flags=re.I,
)


def _is_contiguous_subsequence(needle: list[int], haystack: list[int]) -> bool:
    if not needle:
        return True
    width = len(needle)
    return any(haystack[i:i + width] == needle for i in range(len(haystack) - width + 1))


def validate_source_structure(block_lines, rows, rtf_metadata: dict) -> list[str]:
    errors: list[str] = []
    row_numbers = [number for number, _expr in rows]

    if any(left >= right for left, right in zip(row_numbers, row_numbers[1:])):
        errors.append("source_row_numbers_not_strictly_increasing")
    if len(row_numbers) != len(set(row_numbers)):
        errors.append("duplicate_source_row_number")

    # ``list_numbers`` covers the whole RTF document. A document may contain
    # other numbered lists before or after MEDLINE, so require only that the
    # parsed MEDLINE sequence occurs contiguously in the full list sequence.
    list_numbers = list(rtf_metadata.get("list_numbers", []) or [])
    if list_numbers and row_numbers and not _is_contiguous_subsequence(row_numbers, list_numbers):
        errors.append(
            "rtf_list_number_sequence_not_found_for_medline_block:"
            f"listtext={','.join(map(str, list_numbers))}:"
            f"rows={','.join(map(str, row_numbers))}"
        )

    for number, expr in rows:
        residue = RTF_CONTROL_RESIDUE_RE.search(expr)
        if residue:
            errors.append(
                f"source_rtf_control_residue_in_#{number}:{residue.group(0)}"
            )
    if not rows:
        errors.append("no_strategy_rows")
    elif not rows[-1][1].strip():
        errors.append("empty_final_source_row")

    return list(dict.fromkeys(errors))



PUBMED_FIELD_WHITELIST = {
    "ti", "tiab", "tw", "all", "mh", "pt", "sh",
    "ta", "dp", "nm", "pa", "sb", 
}


def _outside_double_quotes(text: str) -> str:
    parts = re.split(r'("[^"]*")', text)
    # Keep a neutral operand placeholder so Boolean operators on either side
    # of a quoted atom are not falsely treated as adjacent.
    return "".join(" QATOM " if p.startswith('"') and p.endswith('"') else p for p in parts)


def validate_converted_expression(expr: str, *, allow_line_references: bool = True) -> list[str]:
    """Return fatal local-validation errors for one converted expression."""
    errors: list[str] = []
    s = expr.strip()
    outside = _outside_double_quotes(s)

    if not s:
        errors.append("empty_expression")
    if '"""' in s:
        errors.append("triple_quote_sequence")
    if s.count('"') % 2:
        errors.append("unbalanced_double_quotes")
    # Ordered delimiter validation: equal counts alone cannot detect an early
    # closing delimiter. Quoted text has already been replaced in ``outside``.
    paren_balance = 0
    paren_early_close = False
    for ch in outside:
        if ch == '(':
            paren_balance += 1
        elif ch == ')':
            paren_balance -= 1
            if paren_balance < 0:
                paren_early_close = True
                break
    if paren_early_close:
        errors.append("unexpected_closing_parenthesis")
    elif paren_balance > 0:
        errors.append(f"missing_closing_parenthesis:{paren_balance}")

    bracket_balance = 0
    bracket_early_close = False
    for ch in outside:
        if ch == '[':
            bracket_balance += 1
        elif ch == ']':
            bracket_balance -= 1
            if bracket_balance < 0:
                bracket_early_close = True
                break
    if bracket_early_close:
        errors.append("unexpected_closing_square_bracket")
    elif bracket_balance > 0:
        errors.append(f"missing_closing_square_bracket:{bracket_balance}")
    if '$' in outside:
        errors.append("residual_ovid_dollar")
    if '?' in outside:
        errors.append("residual_ovid_question_wildcard")
    if re.search(r'#(?!\d+\b)', outside):
        errors.append("residual_ovid_hash_wildcard")
    if '/' in outside:
        errors.append("residual_ovid_slash_outside_quoted_literal")
    if re.search(r'\bexp\b', outside, flags=re.I):
        errors.append("residual_ovid_exp")
    if re.search(r'\b(?:adj\d*|next)\b', outside, flags=re.I):
        errors.append("residual_ovid_proximity_operator")
    if re.search(r'\.(?:ti|ab|tw|kf|mp|af|jn|jw|ot|hw|pt|fs|sh|nm|pa|cm)(?:\s*,\s*[a-z]{2})*\.?(?=\s|$|\))', outside, flags=re.I):
        errors.append("residual_ovid_field_suffix")
    if re.search(r'(?<![\w\]])\*(?=[A-Za-z0-9"(])', outside):
        errors.append("unsupported_leading_free_text_star")
    if EMPTY_ATOM in s or PUBMED_EMPTY_QUERY in s:
        errors.append("converter_generated_empty_set_or_marker")
    if DROP_ATOM in s:
        errors.append("dropped_short_root_atom_marker")
    if MANUAL_REVIEW_ATOM in s:
        errors.append("manual_review_required_marker")
    if re.search(r'^\s*(?:AND|OR|NOT)\b|\b(?:AND|OR|NOT)\s*$', outside, flags=re.I):
        errors.append("dangling_boolean_operator")
    if re.search(r'\b(?:AND|OR|NOT)\s+(?:AND|OR|NOT)\b', outside, flags=re.I):
        errors.append("adjacent_boolean_operators")

    for field in re.findall(r'\[\s*([^\]]+?)\s*\]', s):
        if field.lower() not in PUBMED_FIELD_WHITELIST:
            errors.append(f"unknown_pubmed_field_tag:{field}")

    malformed_patterns = {
        "known_triple_quote_mesh_regression": r'"""',
        "known_boolean_consumed_as_mesh_subheading": r'/(?:or|and|not)"?\[mh\]',
        "known_leading_star_group_regression": r'(?<!\w)\*\s*\(',
        "known_residual_slash_after_quote": r'"\s*/',
    }
    for name, pattern in malformed_patterns.items():
        if re.search(pattern, s, flags=re.I):
            errors.append(name)

    if not allow_line_references and re.search(r'#\d+\b', outside):
        errors.append("unresolved_line_reference")

    return list(dict.fromkeys(errors))


def validate_reference_graph(converted_map: dict[int, str]) -> list[str]:
    errors: list[str] = []
    known = set(converted_map)
    graph: dict[int, set[int]] = {}

    for n, expr in converted_map.items():
        refs = set(referenced_line_numbers(expr))
        undefined = sorted(refs - known)
        for ref in undefined:
            errors.append(f"undefined_line_reference:#{ref}_in_#{n}")
        graph[n] = refs & known

    state: dict[int, int] = {}
    stack: list[int] = []

    def visit(node: int):
        marker = state.get(node, 0)
        if marker == 1:
            try:
                idx = stack.index(node)
                cycle = stack[idx:] + [node]
            except ValueError:
                cycle = [node, node]
            errors.append("cyclic_line_reference:" + "->".join(f"#{x}" for x in cycle))
            return
        if marker == 2:
            return
        state[node] = 1
        stack.append(node)
        for child in graph.get(node, set()):
            visit(child)
        stack.pop()
        state[node] = 2

    for node in sorted(graph):
        visit(node)

    return list(dict.fromkeys(errors))

def final_query_dependency_closure(converted_map: dict[int, str], final_line_number: int | None) -> set[int]:
    """Return all surviving rows reachable from the selected final query."""
    if final_line_number is None or final_line_number not in converted_map:
        return set()
    closure: set[int] = set()
    stack = [final_line_number]
    while stack:
        number = stack.pop()
        if number in closure or number not in converted_map:
            continue
        closure.add(number)
        stack.extend(referenced_line_numbers(converted_map[number]))
    return closure


# ---------------------------------------------------------------------
# File conversion
# ---------------------------------------------------------------------


def convert_file(
    input_rtf: Path,
    output_rtf: Path,
    audit_csv: Path,
    output_txt: Path | None = None,
    validation_txt: Path | None = None,
):
    text, rtf_metadata = read_rtf_as_text_with_metadata(input_rtf)
    lines = text.splitlines()
    start, end = find_medline_block(lines)

    if start is None:
        print(f"No Medline block found: {input_rtf}")
        return {"converted": False, "validation_status": "no_medline_block", "errors": ["no_medline_block"]}

    before = lines[:start]
    medline_block = lines[start + 1:end]
    after = lines[end:]
    rows = parse_strategy_rows(medline_block)
    source_structure_errors = validate_source_structure(
        medline_block,
        rows,
        rtf_metadata,
    )

    if not rows:
        return {"converted": False, "validation_status": "no_strategy_rows", "errors": ["no_strategy_rows"]}

    external_end_date = next(
        (
            match.group(1).strip()
            for line in before
            if (match := re.match(r"^\s*End_date\s*:\s*(.+?)\s*$", line, flags=re.I))
        ),
        None,
    )
    omit_ovid_update_dates = external_end_date is not None

    known_line_numbers = {num for num, _expr in rows}

    # Discover uncached controlled headings without network access, then
    # resolve them as one bounded concurrent preflight. The real conversion
    # below reads verified mappings from cache and therefore does not make a
    # serial API request for every heading.
    mesh_resolver = get_mesh_resolver()
    uncached_mesh_labels: set[str] = set()
    original_mesh_mode = mesh_resolver.mode
    try:
        mesh_resolver.mode = "cache-only"
        prefix = "mesh_resolution_fallback_to_source_heading:"
        for _original_num, expr in rows:
            _converted, preflight_flags = convert_line(
                expr,
                known_line_numbers=known_line_numbers,
                omit_ovid_update_dates=omit_ovid_update_dates,
            )
            for flag in preflight_flags:
                if not flag.startswith(prefix):
                    continue
                payload = flag[len(prefix):]
                label, separator, _rest = payload.partition(":")
                if separator and label:
                    uncached_mesh_labels.add(label)
    finally:
        mesh_resolver.mode = original_mesh_mode

    if uncached_mesh_labels:
        mesh_resolver.prefetch(uncached_mesh_labels)

    converted_map: dict[int, str] = {}
    original_map: dict[int, str] = {}
    flags_map: dict[int, list[str]] = {}
    protected_term_errors_map: dict[int, list[str]] = {}

    # The conversion pass is cache-only even when the preflight was online.
    # This prevents an unsuccessful preflight request from being retried
    # serially for every occurrence of the same heading.
    conversion_mesh_mode = mesh_resolver.mode
    try:
        mesh_resolver.mode = "cache-only"
        for original_num, expr in rows:
            converted, flags = convert_line(
                expr,
                known_line_numbers=known_line_numbers,
                omit_ovid_update_dates=omit_ovid_update_dates,
            )
            converted_map[original_num] = converted
            original_map[original_num] = expr
            protected_term_errors = validate_protected_hyphenated_terms(expr, converted, flags)
            protected_term_errors_map[original_num] = protected_term_errors
            flags.extend(protected_term_errors)
            flags_map[original_num] = list(dict.fromkeys(flags))
    finally:
        mesh_resolver.mode = conversion_mesh_mode

    # Propagate complete-line removals through downstream references until the
    # dropped-line set stabilizes. A dropped line is not an empty set: its
    # operand and associated Boolean operator are removed syntactically.
    changed = True
    while changed:
        changed = False
        dropped_line_numbers = {n for n, expr in converted_map.items() if expr == DROP_ATOM}
        for n in sorted(converted_map):
            if n in dropped_line_numbers:
                continue
            updated, did_change = simplify_dropped_line_references(
                converted_map[n], dropped_line_numbers, flags_map[n], n
            )
            if did_change:
                converted_map[n] = updated
                flags_map[n] = list(dict.fromkeys(flags_map[n]))
                changed = True

    dropped_line_numbers = {n for n, expr in converted_map.items() if expr == DROP_ATOM}
    surviving_map = {n: expr for n, expr in converted_map.items() if n not in dropped_line_numbers}
    surviving_row_order = [n for n, _expr in rows if n in surviving_map]
    final_line_number = surviving_row_order[-1] if surviving_row_order else None
    final_line_dropped = final_line_number is None
    active_line_numbers = final_query_dependency_closure(surviving_map, final_line_number)

    line_errors_map: dict[int, list[str]] = {}
    for n in sorted(converted_map):
        if n in dropped_line_numbers:
            line_errors_map[n] = []
        else:
            line_errors_map[n] = list(dict.fromkeys(
                validate_converted_expression(
                    converted_map[n],
                    allow_line_references=True,
                )
                + protected_term_errors_map.get(n, [])
            ))

    active_map = {n: surviving_map[n] for n in active_line_numbers if n in surviving_map}
    reference_errors = validate_reference_graph(active_map)
    all_errors = list(source_structure_errors) + list(reference_errors)
    for n in sorted(active_line_numbers):
        all_errors.extend(f"line_#{n}:{e}" for e in line_errors_map.get(n, []))
    if final_line_dropped:
        all_errors.append("final_query_empty_after_short_root_cleanup")
    all_errors = list(dict.fromkeys(all_errors))

    if final_line_dropped:
        validation_status = "manual_review_required"
    else:
        validation_status = "ok" if not all_errors else "validation_failed"

    converted_rows = [
        f"#{n} {converted_map[n]}"
        for n, _ in rows
        if n not in dropped_line_numbers
    ]
    if final_line_dropped:
        converted_rows.append("MANUAL_REVIEW_REQUIRED: final query empty after short-root cleanup")
    output_text = "\n".join(before + ["PubMed:"] + converted_rows + after)

    write_rtf(output_rtf, output_text)
    if output_txt is not None:
        output_txt.write_text(output_text + "\n", encoding="utf-8")

    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "line_number", "original", "converted", "flags",
                "validation_status", "validation_errors",
            ],
        )
        writer.writeheader()
        for n, _expr in rows:
            if n in dropped_line_numbers:
                row_status = "removed_after_short_root_cleanup"
                row_errors = ""
                rendered = ""
            else:
                if not line_errors_map[n]:
                    row_status = "ok"
                elif n in active_line_numbers:
                    row_status = "validation_failed"
                else:
                    row_status = "warning_unused_line"
                row_errors = "; ".join(line_errors_map[n])
                rendered = converted_map[n]
            writer.writerow({
                "line_number": n,
                "original": original_map[n],
                "converted": rendered,
                "flags": "; ".join(flags_map[n]),
                "validation_status": row_status,
                "validation_errors": row_errors,
            })

    if validation_txt is not None:
        summary = [
            f"input={input_rtf}",
            f"status={validation_status}",
            f"rtf_parser={rtf_metadata.get('parser')}",
            f"rtf_list_items={rtf_metadata.get('list_item_count', 0)}",
            f"rtf_ignored_destinations={rtf_metadata.get('ignored_destination_count', 0)}",
            f"strategy_lines={len(rows)}",
            f"active_final_query_lines={','.join('#'+str(n) for n in sorted(active_line_numbers)) or 'none'}",
            f"surviving_lines={len(surviving_map)}",
            f"removed_lines={','.join('#'+str(n) for n in sorted(dropped_line_numbers)) or 'none'}",
            f"final_line={'#' + str(final_line_number) if final_line_number is not None else 'none'}",
            f"external_end_date={external_end_date or 'none'}",
            f"omit_pure_ed_dt_update_lines={'yes' if omit_ovid_update_dates else 'no'}",
            "",
            "fatal_errors:",
        ]
        summary.extend(all_errors or ["none"])
        summary.extend([
            "",
            "note:",
            "A validation/manual-review failure must not be submitted to PubMed or stored as retrieval count 0.",
        ])
        validation_txt.write_text("\n".join(summary) + "\n", encoding="utf-8")

    if all_errors:
        print(f"WARNING: local validation/manual review for {input_rtf.name} ({len(all_errors)} issue(s)).")
        for err in all_errors[:10]:
            print(f"  - {err}")

    return {
        "converted": True,
        "validation_status": validation_status,
        "errors": all_errors,
        "lines": len(rows),
        "surviving_lines": len(surviving_map),
        "removed_lines": sorted(dropped_line_numbers),
    }


def build_arg_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Convert Cochrane Ovid MEDLINE strategies to PubMed syntax using "
            "the Version 20 corrected deterministic-RTF, MeSH-assisted, "
            "pharmacological-action, strict-filter, stopword, "
            "main-descriptor, and curated-short-root rules."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help=(
            "Root directory containing one subfolder per Cochrane ID. "
            "Each subfolder must contain <CDID>.rtf. "
            f"Default: {ROOT}"
        ),
    )
    parser.add_argument(
        "--study",
        "--cdid",
        dest="study",
        help="Convert only one Cochrane ID subfolder, for example CD015066.",
    )
    parser.add_argument(
        "--strict-fail",
        action="store_true",
        help="Exit with a non-zero code when any converted study fails local validation.",
    )
    parser.add_argument(
        "--mesh-mode",
        choices=("online", "cache-only"),
        default="online",
        help=(
            "Resolve exact MeSH headings online and update the cache, or use "
            "only an existing cache and fall back to the source heading on cache misses. "
            "Default: online"
        ),
    )
    parser.add_argument(
        "--mesh-cache",
        type=Path,
        default=None,
        help=(
            "Path to the versioned MeSH resolution cache. "
            f"Default: <root>/{DEFAULT_MESH_CACHE_NAME}"
        ),
    )
    return parser


def main():
    args = build_arg_parser().parse_args()
    root = args.root.expanduser().resolve()

    if not root.exists():
        raise SystemExit(f"Root directory does not exist: {root}")
    if not root.is_dir():
        raise SystemExit(f"Root path is not a directory: {root}")

    mesh_cache = (
        args.mesh_cache.expanduser().resolve()
        if args.mesh_cache is not None
        else root / DEFAULT_MESH_CACHE_NAME
    )
    mesh_resolver = configure_mesh_resolver(mesh_cache, mode=args.mesh_mode)

    if args.study:
        candidates = [root / args.study]
        if not candidates[0].is_dir():
            raise SystemExit(f"Study subfolder does not exist: {candidates[0]}")
    else:
        candidates = [p for p in sorted(root.iterdir()) if p.is_dir()]

    created = 0
    failed_validation = 0

    try:
        for subfolder in candidates:
            folder_id = subfolder.name
            input_rtf = subfolder / f"{folder_id}.rtf"
            output_rtf = subfolder / f"{folder_id}_pubmed_{OUTPUT_VERSION}.rtf"
            output_txt = subfolder / f"{folder_id}_pubmed_{OUTPUT_VERSION}.txt"
            audit_csv = subfolder / f"{folder_id}_pubmed_audit_{OUTPUT_VERSION}.csv"
            validation_txt = subfolder / f"{folder_id}_pubmed_validation_{OUTPUT_VERSION}.txt"

            if not input_rtf.exists():
                print(f"Skipped (missing input): {input_rtf}")
                continue

            result = convert_file(
                input_rtf,
                output_rtf,
                audit_csv,
                output_txt=output_txt,
                validation_txt=validation_txt,
            )

            if result.get("converted"):
                created += 1
                if result.get("validation_status") != "ok":
                    failed_validation += 1
                print(f"Created:    {output_rtf}")
                print(f"Text QA:    {output_txt}")
                print(f"Audit:      {audit_csv}")
                print(f"Validation: {validation_txt}")
    finally:
        mesh_resolver.flush()

    print(f"\nDone. Converted {created} file(s); validation failures: {failed_validation}.")
    print(f"MeSH cache: {mesh_cache}")
    if args.strict_fail and failed_validation:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

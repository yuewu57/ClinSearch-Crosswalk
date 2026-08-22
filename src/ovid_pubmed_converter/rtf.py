"""RTF byte input adapter; semantic conversion remains in :mod:`core`."""

import re
import tempfile
from pathlib import Path

from . import engine
from .models import Strategy, StrategyRow

MAX_RTF_BYTES = 2 * 1024 * 1024

# A punctuated label (``1.`` / ``1)``) is explicit. For a plain label such as
# ``1 asthma.tw.``, the text after the integer must not begin with a Boolean
# operator; otherwise a genuine unnumbered expression such as ``1 or 2`` would
# be misclassified as a visible row label.
_NUMBERED_ROW_RE = re.compile(
    r"^\s*\d+(?:[.)](?:\s*.*)?|\s+(?!(?:and|or|not)\b)\S)",
    flags=re.IGNORECASE,
)
_FIELD_SUFFIX_RE = re.compile(
    r"\.[A-Za-z][A-Za-z0-9]*(?:\s*,\s*[A-Za-z][A-Za-z0-9]*)*\.\s*$",
    flags=re.IGNORECASE,
)
_CONTROLLED_HEADING_RE = re.compile(
    r"/(?:[A-Za-z]{1,3}(?:\s*,\s*[A-Za-z]{1,3})*)?\s*$",
    flags=re.IGNORECASE,
)
_LIMIT_ROW_RE = re.compile(
    r"^\s*limit\s+#?\d+\s+to\s+\S(?:.*\S)?\s*$",
    flags=re.IGNORECASE,
)
_FREQ_SUFFIX_RE = re.compile(r"\s*/\s*freq\s*=\s*\d+\s*$", flags=re.IGNORECASE)


def _standalone_numbered_strategy(lines: list[str], metadata: dict):
    """Recognise a whole-document numbered strategy only when unambiguous."""
    nonblank = [line for line in lines if line.strip()]
    if not nonblank or not re.match(r"^\s*1(?:[.)]\s*|\s+\S)", nonblank[0]):
        return None
    rows = engine.parse_strategy_rows(nonblank)
    errors = engine.validate_source_structure(nonblank, rows, metadata)
    if len(rows) < 2 or rows[0][0] != 1 or errors:
        return None
    return nonblank, rows


def _has_explicit_row_numbers(lines: list[str]) -> bool:
    """Return whether extracted text contains at least one visible Ovid row label."""
    return any(_NUMBERED_ROW_RE.match(line) for line in lines if line.strip())


def _looks_like_complete_ovid_row(line: str) -> bool:
    """Conservatively recognise one complete unnumbered Ovid strategy row.

    This is intentionally stricter than the semantic converter. It exists only
    to decide whether paragraph-order numbering can be recovered safely in an
    explicit ``Medline:`` RTF block.
    """
    normalized = engine.normalize_unicode(line).strip()
    if not normalized:
        return False
    if _LIMIT_ROW_RE.fullmatch(normalized):
        return True

    base = _FREQ_SUFFIX_RE.sub("", normalized).strip()
    if not base:
        return False
    if _FIELD_SUFFIX_RE.search(base) or _CONTROLLED_HEADING_RE.search(base):
        return True

    if re.search(r"\b(?:and|or|not)\b", base, flags=re.IGNORECASE):
        without_operators = re.sub(
            r"\b(?:and|or|not)\b",
            " ",
            base,
            flags=re.IGNORECASE,
        )
        return re.fullmatch(r"[\d\s()]+", without_operators) is not None
    return False


def _recover_unnumbered_medline_rows(block_lines: list[str]):
    """Assign paragraph-order numbers only when every paragraph is row-like."""
    cleaned = [line.strip() for line in block_lines if line.strip()]
    if not cleaned or not all(_looks_like_complete_ovid_row(line) for line in cleaned):
        return None
    return [(number, line) for number, line in enumerate(cleaned, start=1)]


def _decode_plain_text_disguised_as_rtf(data: bytes) -> tuple[str, str] | None:
    """Decode a non-RTF upload only when its text encoding can be identified safely."""
    candidates: list[tuple[str, str]] = []
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append(("utf-16", "utf-16"))
    elif data.startswith(b"\xef\xbb\xbf"):
        candidates.append(("utf-8-sig", "utf-8-sig"))
    else:
        candidates.append(("utf-8", "utf-8"))

    for codec, label in candidates:
        try:
            text = data.decode(codec)
        except UnicodeDecodeError:
            continue
        if "\x00" in text:
            continue
        normalized = engine.normalize_unicode(text)
        if not normalized.strip():
            continue
        return normalized, label
    return None


def _strategy_from_extracted_text(
    text: str,
    metadata: dict,
    *,
    input_mode: str,
    source_prefix: str,
    require_medline_heading: bool = False,
    initial_warnings: tuple[str, ...] = (),
) -> Strategy:
    """Build a Strategy from already decoded RTF/plain-text input."""
    lines = text.splitlines()
    start, end = engine.find_medline_block(lines)
    input_warnings = list(initial_warnings)

    if start is None:
        if require_medline_heading:
            return Strategy(
                (),
                source_errors=("plain_text_rtf_missing_medline_heading",),
                metadata={
                    **metadata,
                    "input_mode": input_mode,
                    "source_format": f"{source_prefix}_missing_medline_heading",
                    "input_warnings": tuple(input_warnings),
                },
            )
        standalone = _standalone_numbered_strategy(lines, metadata)
        if standalone is None:
            return Strategy(
                (),
                source_errors=("standalone_rtf_strategy_not_unambiguously_identified",),
                metadata={**metadata, "input_mode": input_mode},
            )
        _block, rows = standalone
        before = []
        errors: list[str] = []
        source_format = f"{source_prefix}_standalone_numbered_strategy"
    else:
        before = lines[:start]
        block = lines[start + 1 : end]
        if _has_explicit_row_numbers(block):
            rows = engine.parse_strategy_rows(block)
            errors = engine.validate_source_structure(block, rows, metadata)
            source_format = f"{source_prefix}_explicit_medline_block"
        else:
            recovered = _recover_unnumbered_medline_rows(block)
            if recovered is None:
                return Strategy(
                    (),
                    source_errors=("rtf_medline_block_missing_reliable_line_numbers",),
                    metadata={
                        **metadata,
                        "input_mode": input_mode,
                        "source_format": f"{source_prefix}_explicit_medline_block_unnumbered_ambiguous",
                        "input_warnings": tuple(input_warnings),
                    },
                )
            rows = recovered
            # No visible Word/Ovid list labels were used for this recovery, so
            # list-number metadata elsewhere in the document must not be used
            # to validate the inferred sequence.
            recovery_metadata = {**metadata, "list_numbers": []}
            errors = engine.validate_source_structure(block, rows, recovery_metadata)
            source_format = f"{source_prefix}_explicit_medline_block_unnumbered_recovered"
            input_warnings.append("rtf_line_numbers_recovered_from_medline_paragraph_order")

    end_date = next(
        (
            match.group(1).strip()
            for line in before
            if (match := re.match(r"^\s*End_date\s*:\s*(.+?)\s*$", line, flags=re.IGNORECASE))
        ),
        None,
    )
    metadata = {
        **metadata,
        "input_mode": input_mode,
        "source_format": source_format,
        "input_warnings": tuple(input_warnings),
    }
    return Strategy(
        tuple(StrategyRow(number, expression) for number, expression in rows),
        end_date=end_date,
        source_errors=tuple(errors),
        metadata=metadata,
    )


def parse_rtf_bytes(data: bytes) -> Strategy:
    """Decode an RTF upload, including conservatively recognised plain-text impostors."""
    if not data or len(data) > MAX_RTF_BYTES:
        raise ValueError("rtf_upload_empty_or_too_large")

    if data.lstrip().startswith(b"{\\rtf"):
        with tempfile.TemporaryDirectory(prefix="ovid-pubmed-") as directory:
            path = Path(directory) / "input.rtf"
            path.write_bytes(data)
            text, metadata = engine.read_rtf_as_text_with_metadata(path)
        return _strategy_from_extracted_text(
            text,
            metadata,
            input_mode="rtf",
            source_prefix="rtf",
        )

    decoded = _decode_plain_text_disguised_as_rtf(data)
    if decoded is None:
        raise ValueError("invalid_rtf_signature")
    text, encoding = decoded
    metadata = {
        "list_numbers": [],
        "plain_text_encoding": encoding,
    }
    return _strategy_from_extracted_text(
        text,
        metadata,
        input_mode="plain_text_disguised_as_rtf",
        source_prefix="plain_text_rtf",
        require_medline_heading=True,
        initial_warnings=("plain_text_file_uploaded_with_rtf_extension",),
    )

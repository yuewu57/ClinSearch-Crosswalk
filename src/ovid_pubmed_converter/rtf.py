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
    r"\.[A-Za-z][A-Za-z0-9]*(?:\s*,\s*[A-Za-z][A-Za-z0-9]*)*\.?\s*$",
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


def _decode_plain_text_upload(data: bytes) -> tuple[str, str]:
    """Decode text masquerading as .rtf using only unambiguous common encodings."""
    candidates: list[tuple[str, str]] = []
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        candidates.append(("utf-16", "utf-16"))
    else:
        candidates.extend((("utf-8-sig", "utf-8"), ("utf-16", "utf-16")))

    for codec, label in candidates:
        try:
            text = data.decode(codec)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "\x00" in text:
            continue
        if not text.strip():
            continue
        return engine.normalize_unicode(text), label
    raise ValueError("invalid_rtf_signature")


def parse_rtf_bytes(data: bytes) -> Strategy:
    """Decode an RTF upload or safely recognisable plain-text .rtf strategy."""
    if not data or len(data) > MAX_RTF_BYTES:
        raise ValueError("rtf_upload_empty_or_too_large")

    input_warnings: list[str] = []
    if data.lstrip().startswith(b"{\\rtf"):
        with tempfile.TemporaryDirectory(prefix="ovid-pubmed-") as directory:
            path = Path(directory) / "input.rtf"
            path.write_bytes(data)
            text, metadata = engine.read_rtf_as_text_with_metadata(path)
    else:
        text, encoding = _decode_plain_text_upload(data)
        metadata = {"plain_text_encoding": encoding, "list_numbers": []}
        input_warnings.append("rtf_extension_plain_text_decoded")

    lines = text.splitlines()
    start, end = engine.find_medline_block(lines)

    if start is None:
        standalone = _standalone_numbered_strategy(lines, metadata)
        if standalone is None:
            return Strategy(
                (),
                source_errors=("standalone_rtf_strategy_not_unambiguously_identified",),
                metadata={**metadata, "input_mode": "rtf"},
            )
        _block, rows = standalone
        before = []
        errors: list[str] = []
        source_format = "standalone_numbered_strategy"
    else:
        before = lines[:start]
        block = lines[start + 1 : end]
        if _has_explicit_row_numbers(block):
            rows = engine.parse_strategy_rows(block)
            errors = engine.validate_source_structure(block, rows, metadata)
            source_format = "explicit_medline_block"
        else:
            recovered = _recover_unnumbered_medline_rows(block)
            if recovered is None:
                return Strategy(
                    (),
                    source_errors=("rtf_medline_block_missing_reliable_line_numbers",),
                    metadata={
                        **metadata,
                        "input_mode": "rtf",
                        "source_format": "explicit_medline_block_unnumbered_ambiguous",
                    },
                )
            rows = recovered
            # No visible Word/Ovid list labels were used for this recovery, so
            # list-number metadata elsewhere in the document must not be used
            # to validate the inferred sequence.
            recovery_metadata = {**metadata, "list_numbers": []}
            errors = engine.validate_source_structure(block, rows, recovery_metadata)
            source_format = "explicit_medline_block_unnumbered_recovered"
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
        "input_mode": "rtf",
        "source_format": source_format,
        "input_warnings": tuple(input_warnings),
    }
    return Strategy(
        tuple(StrategyRow(number, expression) for number, expression in rows),
        end_date=end_date,
        source_errors=tuple(errors),
        metadata=metadata,
    )

"""RTF byte input adapter; semantic conversion remains in :mod:`core`."""

import re
import tempfile
from pathlib import Path

from . import engine
from .models import Strategy, StrategyRow

MAX_RTF_BYTES = 2 * 1024 * 1024


def parse_rtf_bytes(data: bytes) -> Strategy:
    """Decode an RTF upload and return the same Strategy model as paste mode."""
    if not data or len(data) > MAX_RTF_BYTES:
        raise ValueError("rtf_upload_empty_or_too_large")
    if not data.lstrip().startswith(b"{\\rtf"):
        raise ValueError("invalid_rtf_signature")
    with tempfile.TemporaryDirectory(prefix="ovid-pubmed-") as directory:
        path = Path(directory) / "input.rtf"
        path.write_bytes(data)
        text, metadata = engine.read_rtf_as_text_with_metadata(path)
    lines = text.splitlines()
    start, end = engine.find_medline_block(lines)
    if start is None:
        return Strategy((), source_errors=("no_medline_block",), metadata=metadata)
    before = lines[:start]
    block = lines[start + 1 : end]
    rows = engine.parse_strategy_rows(block)
    errors = engine.validate_source_structure(block, rows, metadata)
    end_date = next(
        (
            match.group(1).strip()
            for line in before
            if (match := re.match(r"^\s*End_date\s*:\s*(.+?)\s*$", line, flags=re.I))
        ),
        None,
    )
    metadata = {**metadata, "input_mode": "rtf"}
    return Strategy(
        tuple(StrategyRow(number, expression) for number, expression in rows),
        end_date=end_date,
        source_errors=tuple(errors),
        metadata=metadata,
    )

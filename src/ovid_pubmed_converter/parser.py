"""Canonical parsing for pasted and RTF-normalised Ovid strategies."""

from . import engine
from .models import Strategy, StrategyRow


def parse_strategy_text(text: str, *, end_date: str | None = None) -> Strategy:
    """Parse pasted strategy text into one canonical representation."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
    nonblank = [line for line in lines if line.strip()]
    rows = engine.parse_strategy_rows(nonblank)
    errors = engine.validate_source_structure(nonblank, rows, {})
    return Strategy(
        rows=tuple(StrategyRow(number, expression) for number, expression in rows),
        end_date=end_date.strip() if end_date and end_date.strip() else None,
        source_errors=tuple(errors),
        metadata={"input_mode": "paste"},
    )

"""Public, UI-independent conversion result models."""

from dataclasses import dataclass, field

try:
    from enum import StrEnum
except ImportError:  # Python 3.10 compatibility
    from enum import Enum

    class StrEnum(str, Enum):
        """Minimal Python 3.10-compatible backport of enum.StrEnum."""

        def __str__(self) -> str:
            return str(self.value)

        def __format__(self, spec: str) -> str:
            return format(self.value, spec)


class ValidationStatus(StrEnum):
    OK = "ok"
    VALIDATION_FAILED = "validation_failed"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


@dataclass(frozen=True)
class StrategyRow:
    number: int
    source: str


@dataclass(frozen=True)
class Strategy:
    rows: tuple[StrategyRow, ...]
    end_date: str | None = None
    source_errors: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ConvertedRow:
    number: int
    original: str
    converted: str
    audit_flags: tuple[str, ...]
    validation_status: str
    validation_errors: tuple[str, ...]
    output_number: int | None = None


@dataclass(frozen=True)
class ConversionResult:
    validation_status: ValidationStatus
    rows: tuple[ConvertedRow, ...]
    final_line_number: int | None
    final_query: str | None
    warnings: tuple[str, ...]
    audit_events: tuple[str, ...]
    validation_errors: tuple[str, ...]
    removed_line_numbers: tuple[int, ...] = ()
    synthetic_rows: tuple[tuple[int, str], ...] = ()

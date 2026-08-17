"""In-memory output renderers shared by the web and CLI adapters."""

import csv
import io
import json

from . import RULESET_VERSION, __version__
from .engine import _escape_text_for_rtf
from .models import ConversionResult


def strategy_text(result: ConversionResult) -> str:
    return "\n".join(f"#{row.number} {row.converted}" for row in result.rows if row.converted) + "\n"


def audit_csv(result: ConversionResult) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(
        [
            "software_version",
            "conversion_ruleset",
            "line_number",
            "original",
            "converted",
            "flags",
            "validation_status",
            "validation_errors",
        ]
    )
    for row in result.rows:
        writer.writerow(
            [
                __version__,
                RULESET_VERSION,
                row.number,
                row.original,
                row.converted,
                "; ".join(row.audit_flags),
                row.validation_status,
                "; ".join(row.validation_errors),
            ]
        )
    return stream.getvalue()


def validation_report(result: ConversionResult) -> str:
    payload = {
        "software_version": __version__,
        "conversion_ruleset": RULESET_VERSION,
        "status": result.validation_status.value,
        "final_line": result.final_line_number,
        "errors": result.validation_errors,
        "note": "A validation/manual-review failure must not be submitted to PubMed.",
    }
    return json.dumps(payload, indent=2) + "\n"


def converted_rtf(result: ConversionResult) -> bytes:
    body = "PubMed:\n" + strategy_text(result)
    return ("{\\rtf1\\ansi\\ansicpg1252\\uc1\n" + _escape_text_for_rtf(body) + "\n}").encode("ascii")

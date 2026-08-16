"""Testable web workflow functions without Streamlit dependencies."""

from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.mesh import load_mesh_resolver, production_cache_path
from ovid_pubmed_converter.outputs import (
    audit_csv,
    converted_rtf,
    strategy_text,
    validation_report,
)
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes


def web_resolver():
    """Use the repository cache, then exact NLM lookup, then safe fallback."""
    return load_mesh_resolver(
        production_cache_path(),
        online=True,
        persist_updates=False,
    )


def convert_paste(text: str, end_date: str | None = None, *, resolver=None):
    strategy = parse_strategy_text(text, end_date=end_date)
    return convert_strategy(strategy, mesh_resolver=resolver or web_resolver())


def convert_rtf(data: bytes, *, resolver=None):
    strategy = parse_rtf_bytes(data)
    return convert_strategy(strategy, mesh_resolver=resolver or web_resolver())


def download_payloads(result, *, include_rtf: bool = False) -> dict[str, bytes]:
    payloads = {
        "pubmed_strategy.txt": strategy_text(result).encode("utf-8"),
        "pubmed_audit.csv": audit_csv(result).encode("utf-8"),
        "pubmed_validation.json": validation_report(result).encode("utf-8"),
    }
    if include_rtf:
        payloads["pubmed_strategy.rtf"] = converted_rtf(result)
    return payloads

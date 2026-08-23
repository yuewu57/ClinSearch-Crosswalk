"""Testable web workflow functions without Streamlit dependencies."""

from dataclasses import replace

from ovid_pubmed_converter import engine_v21
from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.mesh import load_mesh_resolver, production_cache_path
from ovid_pubmed_converter.outputs import (
    audit_csv,
    converted_rtf,
    one_line_query,
    strategy_text,
    validation_report,
)
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes


def has_eligible_update_date_construct(text: str) -> bool:
    """Return whether paste text contains a v21 pure database-update date row."""
    strategy = parse_strategy_text(text)
    return any(
        engine_v21.is_pure_ovid_database_update_date_line(row.source)
        for row in strategy.rows
    )


def user_facing_validation_error(error: str) -> str:
    """Render input-adapter errors clearly while preserving audit identifiers."""
    if error == "standalone_rtf_strategy_not_unambiguously_identified":
        return (
            'No explicit "Medline:" section or unique coherent numbered Ovid '
            "strategy could be identified in the RTF. Re-export the Ovid strategy "
            "with line numbers, use the example RTF template, or paste the strategy instead."
        )
    if error == "plain_text_rtf_missing_medline_heading":
        return (
            "The uploaded .rtf file was actually plain text, but no explicit Medline: "
            "section could be identified safely. Re-export it as a genuine RTF or add the "
            "Medline: heading and numbered Ovid strategy rows."
        )
    if error == "rtf_medline_block_missing_reliable_line_numbers":
        return (
            'A "Medline:" section was found, but strategy line numbers were missing and '
            "the extracted paragraphs could not be identified safely as complete Ovid rows. "
            "Re-export with line numbers, use the example RTF template, or paste one logical "
            "search row per line."
        )
    return error


def user_facing_warning(warning: str) -> str:
    """Render high-value web warnings in plain language."""
    if warning == "plain_text_file_uploaded_with_rtf_extension":
        return (
            "The uploaded .rtf file was actually plain text rather than Rich Text Format. "
            "Evidentia decoded the text safely and processed its explicit Medline: strategy. "
            "Verify the converted result before retrieval."
        )
    if warning == "rtf_line_numbers_recovered_from_medline_paragraph_order":
        return (
            "The uploaded RTF had a Medline section but no visible strategy line numbers. "
            "Evidentia assigned line numbers by paragraph order because every paragraph "
            "looked like a complete Ovid row. Verify the reconstructed numbering and final "
            "query before retrieval."
        )
    if warning == "major_semantic_approximation_recall_broadened":
        return (
            "At least one Ovid construct was intentionally broadened rather than reproduced "
            "exactly in PubMed. Check the line-by-line audit; this can occur when a LIMIT, "
            "/freq>1, or database-update date restriction is omitted."
        )
    if warning.startswith("mesh_resolution_fallback_to_source_heading:"):
        return (
            "A controlled heading could not be confirmed by the exact MeSH resolver and an "
            "audited fallback was used. Check the line-by-line audit."
        )
    return warning


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
    result = convert_strategy(strategy, mesh_resolver=resolver or web_resolver())
    input_warnings = tuple(strategy.metadata.get("input_warnings", ()) or ())
    if not input_warnings:
        return result
    warnings = tuple(dict.fromkeys(result.warnings + input_warnings))
    audit_events = tuple(dict.fromkeys(result.audit_events + input_warnings))
    return replace(result, warnings=warnings, audit_events=audit_events)


def download_payloads(result, *, include_rtf: bool = False) -> dict[str, bytes]:
    query = one_line_query(result)
    payloads = {
        "pubmed_query.txt": ((query + "\n") if query else "").encode("utf-8"),
        "pubmed_strategy.txt": strategy_text(result).encode("utf-8"),
        "pubmed_audit.csv": audit_csv(result).encode("utf-8"),
        "pubmed_validation.json": validation_report(result).encode("utf-8"),
    }
    if include_rtf:
        payloads["pubmed_strategy.rtf"] = converted_rtf(result)
    return payloads

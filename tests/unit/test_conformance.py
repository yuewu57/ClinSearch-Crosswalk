from ovid_pubmed_converter import engine
from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes


def test_generic_publication_type_is_audited():
    result = convert_strategy(parse_strategy_text("1 Unverified Example.pt."))
    assert result.rows[0].converted == "Unverified Example[pt]"
    assert "unverified_generic_publication_type_value:Unverified Example" in result.audit_events[0]


def test_verified_mesh_rename_exempts_protected_hyphen_check():
    errors = engine.validate_protected_hyphenated_terms(
        "Double-Blind Method/", '"Double Blind Method"[mh]', ["mesh_resolved:Double-Blind Method=>Double Blind Method"]
    )
    assert errors == []


def test_unresolved_mesh_falls_back_executably():
    result = convert_strategy(parse_strategy_text("1 Unresolved Heading/"))
    assert result.rows[0].converted == '"Unresolved Heading"[mh]'
    assert any("mesh_resolution_fallback_to_source_heading" in event for event in result.audit_events)


def test_invalid_reference_fails_active_query():
    result = convert_strategy(parse_strategy_text("1 asthma.tw.\n2 1 and 99"))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert any("undefined_line_reference" in error for error in result.validation_errors)


def test_duplicate_numbers_fail_source_validation():
    result = convert_strategy(parse_strategy_text("1 asthma.tw.\n1 wheeze.tw."))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert "duplicate_source_row_number" in result.validation_errors


def test_missing_medline_block_is_reported():
    strategy = parse_rtf_bytes(b"{\\rtf1\\ansi no strategy}")
    assert strategy.source_errors == ("no_medline_block",)


def test_invalid_rtf_signature_rejected():
    try:
        parse_rtf_bytes(b"not rtf")
    except ValueError as exc:
        assert str(exc) == "invalid_rtf_signature"
    else:
        raise AssertionError("invalid upload accepted")


def test_wildcard_expansion_limit_fails_validation_deterministically():
    result = convert_strategy(parse_strategy_text("1 a????.tw."))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert result.final_query == "__MANUAL_REVIEW_REQUIRED__[tw]"
    assert result.validation_errors == ("line_#1:manual_review_required_marker",)

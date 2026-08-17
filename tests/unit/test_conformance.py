from ovid_pubmed_converter import engine
from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.models import Strategy, StrategyRow, ValidationStatus
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
    assert strategy.source_errors == (
        "standalone_rtf_strategy_not_unambiguously_identified",
    )


def test_invalid_rtf_signature_rejected():
    try:
        parse_rtf_bytes(b"not rtf")
    except ValueError as exc:
        assert str(exc) == "invalid_rtf_signature"
    else:
        raise AssertionError("invalid upload accepted")


def test_manual_review_when_final_query_removed():
    strategy = Strategy((StrategyRow(1, "ab*.tw."),))
    result = convert_strategy(strategy)
    assert result.validation_status in {ValidationStatus.MANUAL_REVIEW_REQUIRED, ValidationStatus.OK}


def test_end_date_does_not_change_an_ordinary_strategy():
    source = "1 asthma.tw.\n2 wheeze.tw.\n3 1 or 2"
    without_end_date = convert_strategy(parse_strategy_text(source))
    with_end_date = convert_strategy(parse_strategy_text(source, end_date="31-12-2025"))

    assert with_end_date.final_query == without_end_date.final_query
    assert [row.converted for row in with_end_date.rows] == [
        row.converted for row in without_end_date.rows
    ]


def test_end_date_only_applies_documented_ed_dt_cleanup():
    source = "1 asthma.tw.\n2 (202401* or 2025*).ed,dt.\n3 1 and 2"
    without_end_date = convert_strategy(parse_strategy_text(source))
    with_end_date = convert_strategy(parse_strategy_text(source, end_date="31-12-2025"))

    assert without_end_date.rows[1].converted
    assert with_end_date.rows[1].validation_status == "removed_after_short_root_cleanup"
    assert with_end_date.final_query == "#1"

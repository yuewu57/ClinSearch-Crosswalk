from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.outputs import strategy_text
from ovid_pubmed_converter.parser import parse_strategy_text


def test_freq_one_is_removed_as_redundant():
    result = convert_strategy(parse_strategy_text("1 cancer.ab./freq=1"))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "cancer[tiab]"
    assert "ovid_frequency_constraint_removed_as_redundant:freq=1" in result.rows[0].audit_flags


def test_freq_gt_one_is_recall_broadening():
    result = convert_strategy(parse_strategy_text("1 cancer.ab./freq=2"))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "cancer[tiab]"
    assert "ovid_frequency_constraint_ignored:freq=2" in result.rows[0].audit_flags
    assert "major_semantic_approximation_recall_broadened" in result.rows[0].audit_flags


def test_malformed_freq_requires_review_when_active():
    result = convert_strategy(parse_strategy_text("1 cancer.ab./freq=x"))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert any("manual_review_required_marker" in error for error in result.validation_errors)


def test_limit_row_is_removed_redirected_and_renumbered():
    source = (
        "1 asthma.tw.\n2 wheeze.tw.\n3 1 or 2\n4 limit 3 to humans\n"
        "5 cancer.tw.\n6 4 and 5"
    )
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[3].validation_status == "removed_ignored_ovid_limit"
    assert strategy_text(result).splitlines() == [
        "#1 asthma[tw]",
        "#2 wheeze[tw]",
        "#3 #1 OR #2",
        "#4 cancer[tw]",
        "#5 #3 AND #4",
    ]


def test_final_limit_preserves_effective_query_with_synthetic_alias():
    source = "1 asthma.tw.\n2 cancer.tw.\n3 limit 1 to humans"
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.final_line_number == 3
    assert result.final_query == "#1"
    assert result.synthetic_rows == ((3, "#1"),)
    assert strategy_text(result).splitlines()[-1] == "#3 #1"


def test_invalid_unused_limit_is_warning_not_file_failure():
    source = "1 asthma.tw.\n2 limit 99 to humans\n3 cancer.tw."
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[1].validation_status == "warning_unused_line"
    assert "major_semantic_approximation_recall_broadened" not in result.rows[1].audit_flags


def test_invalid_active_limit_fails():
    source = "1 asthma.tw.\n2 limit 99 to humans\n3 1 or 2"
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED


def test_wildcard_phrase_dequotes_after_tag_canonicalisation():
    result = convert_strategy(parse_strategy_text('1 "breast* cancer*"[Title/Abstract]'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "breast* cancer*[tiab]"


def test_literal_or_in_wildcard_phrase_keeps_quotes():
    result = convert_strategy(parse_strategy_text('1 "law or polic*".tw.'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == '"law or polic*"[tw]'


def test_inherited_and_stopword_behaviour_is_accepted():
    result = convert_strategy(parse_strategy_text('1 "research and develop*".tw.'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "(research[tw] AND develop*[tw])"


def test_ed_dt_omission_alone_does_not_trigger_v21_renumbering():
    source = "1 asthma.tw.\n2 (202401* or 2025*).ed,dt.\n3 cancer.tw.\n4 1 and 3"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2025"))
    assert result.validation_status is ValidationStatus.OK
    assert strategy_text(result).splitlines() == [
        "#1 asthma[tw]",
        "#3 cancer[tw]",
        "#4 #1 AND #3",
    ]

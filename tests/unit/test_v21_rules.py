from ovid_pubmed_converter import engine_v21
from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.outputs import one_line_query, strategy_text
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
    assert one_line_query(result) == ""


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
    assert one_line_query(result) == (
        "((asthma[tw]) OR (wheeze[tw])) AND (cancer[tw])"
    )


def test_final_limit_preserves_effective_query_with_synthetic_alias():
    source = "1 asthma.tw.\n2 cancer.tw.\n3 limit 1 to humans"
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.final_line_number == 3
    assert result.final_query == "#1"
    assert result.synthetic_rows == ((3, "#1"),)
    assert strategy_text(result).splitlines()[-1] == "#3 #1"
    assert one_line_query(result) == "asthma[tw]"


def test_one_line_query_recursively_expands_only_final_dependencies():
    source = (
        "1 asthma.tw.\n"
        "2 wheeze.tw.\n"
        "3 1 or 2\n"
        "4 unusedterm.tw.\n"
        "5 3 and 1"
    )
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    query = one_line_query(result)
    assert query == "((asthma[tw]) OR (wheeze[tw])) AND (asthma[tw])"
    assert "unusedterm" not in query
    assert "#" not in query


def test_invalid_unused_limit_is_warning_not_file_failure():
    source = "1 asthma.tw.\n2 limit 99 to humans\n3 cancer.tw."
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[1].validation_status == "warning_unused_line"
    assert "major_semantic_approximation_recall_broadened" not in result.rows[1].audit_flags
    assert one_line_query(result) == "cancer[tw]"


def test_invalid_active_limit_fails():
    source = "1 asthma.tw.\n2 limit 99 to humans\n3 1 or 2"
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert one_line_query(result) == ""


def test_wildcard_phrase_is_grouped_after_tag_canonicalisation():
    result = convert_strategy(parse_strategy_text('1 "breast* cancer*"[Title/Abstract]'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "(breast* cancer*[tiab])"
    assert (
        "wildcard_phrase_grouped_pubmed_phrase_tag_preserved:breast* cancer*[tiab]"
        in result.rows[0].audit_flags
    )


def test_three_word_wildcard_phrase_is_grouped_without_boolean_separators():
    result = convert_strategy(parse_strategy_text('1 "alpha* beta* gamma*".tw.'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "(alpha* beta* gamma*[tw])"
    assert " AND " not in result.rows[0].converted
    assert ")[tw]" not in result.rows[0].converted


def test_literal_or_in_wildcard_phrase_keeps_quotes():
    result = convert_strategy(parse_strategy_text('1 "law or polic*".tw.'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == '"law or polic*"[tw]'


def test_inherited_and_stopword_behaviour_is_accepted():
    result = convert_strategy(parse_strategy_text('1 "research and develop*".tw.'))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "(research[tw] AND develop*[tw])"


def test_inline_tiab_multifield_suffix_is_preserved_inside_boolean_expression():
    source = (
        "1 exp Respiratory Protective Devices/ or exp Masks/ or exp N95 Respirators/ "
        "or surgical mask.ti,ab. or surgical masks.ti,ab. or medical masks.ti,ab. "
        "or air purifying respirator.ti,ab. or air purifying respirators.ti,ab."
    )
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    converted = result.rows[0].converted
    assert '"surgical mask"[tiab]' in converted
    assert '"surgical masks"[tiab]' in converted
    assert '"air purifying respirator"[tiab]' in converted
    assert '"air purifying respirators"[tiab]' in converted
    assert "[ti],ab." not in converted
    assert ".ti.,ab." not in converted
    assert "v21_inline_multifield_suffix_preserved:ti,ab" in result.rows[0].audit_flags


def test_inline_tiab_multifield_preserves_stopword_rule():
    result = convert_strategy(
        parse_strategy_text("1 quality of life.ti,ab. or surgical mask.ti,ab.")
    )
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == (
        '(quality[tiab] AND life[tiab]) OR "surgical mask"[tiab]'
    )


def test_inline_tiab_kf_maps_complete_field_set():
    result = convert_strategy(
        parse_strategy_text("1 cancer.ti,ab,kf. or asthma.ab.")
    )
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[0].converted == "cancer[tiab] OR asthma[tiab]"
    assert "v21_inline_multifield_suffix_preserved:ti,ab,kf" in result.rows[0].audit_flags


def test_split_multifield_residue_detector_rejects_known_malformed_forms():
    assert engine_v21.split_multifield_residue_flags('"surgical mask"[ti],ab.') == [
        "split_ovid_multifield_suffix_after_pubmed_tag"
    ]
    assert engine_v21.split_multifield_residue_flags('"surgical mask".ti.,ab.') == [
        "split_ovid_multifield_suffix_before_pubmed_tag"
    ]


def test_update_date_filter_is_removed_with_external_end_date():
    source = "1 asthma.tw.\n2 (202401* or 2025*).ed,dt.\n3 1 and 2"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2025"))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[1].validation_status == "removed_ignored_ovid_update_date"
    assert "ovid_database_update_date_filter_ignored" in result.rows[1].audit_flags
    assert (
        "external_end_date_applied_instead_of_ovid_update_date_filter"
        in result.rows[1].audit_flags
    )
    assert strategy_text(result).splitlines() == [
        "#1 asthma[tw]",
        "#3 #1",
    ]
    assert one_line_query(result) == "asthma[tw]"


def test_update_date_filter_is_removed_without_external_end_date_with_warning():
    source = "1 asthma.tw.\n2 2022*.dt.\n3 1 and 2"
    result = convert_strategy(parse_strategy_text(source))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[1].validation_status == "removed_ignored_ovid_update_date"
    assert "ovid_update_date_filter_ignored_without_external_end_date" in result.rows[1].audit_flags
    assert "major_semantic_approximation_recall_broadened" in result.rows[1].audit_flags
    assert one_line_query(result) == "asthma[tw]"


def test_single_ed_and_reversed_dt_ed_forms_are_removed():
    for expression in ("2022*.ed.", "(2021* or 2022*).dt,ed."):
        source = f"1 asthma.tw.\n2 {expression}\n3 1 and 2"
        result = convert_strategy(parse_strategy_text(source, end_date="31-12-2022"))
        assert result.validation_status is ValidationStatus.OK
        assert result.rows[1].validation_status == "removed_ignored_ovid_update_date"
        assert one_line_query(result) == "asthma[tw]"


def test_mixed_non_numeric_ed_dt_expression_is_not_silently_discarded():
    source = "1 asthma.tw.\n2 (cancer or 2022*).ed,dt.\n3 1 and 2"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2022"))
    assert result.rows[1].validation_status != "removed_ignored_ovid_update_date"


def test_update_date_reference_under_or_requires_manual_review():
    source = "1 asthma.tw.\n2 2022*.ed,dt.\n3 1 or 2"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2022"))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert any(
        "ovid_update_date_reference_in_or_not_manual_review_required" in flag
        for flag in result.rows[2].audit_flags
    )
    assert one_line_query(result) == ""


def test_update_date_reference_under_not_requires_manual_review():
    source = "1 asthma.tw.\n2 2022*.ed,dt.\n3 1 not 2"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2022"))
    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert any(
        "ovid_update_date_reference_in_or_not_manual_review_required" in flag
        for flag in result.rows[2].audit_flags
    )
    assert one_line_query(result) == ""


def test_cd005595_style_update_wrapper_is_discarded_without_renumbering():
    source = (
        "1 ankle.tw.\n"
        "2 fracture.tw.\n"
        "3 1 or 2\n"
        "4 rehabilitation.tw.\n"
        "5 3 and 4\n"
        "23 (201107* or 201108* or 201109* or 201110* or 201111* or 201112* "
        "or 2012* or 2013* or 2014* or 2015* or 2016* or 2017* or 2018* "
        "or 2019* or 2020* or 2021* or 2022*).ed,dt.\n"
        "24 5 and 23"
    )
    result = convert_strategy(parse_strategy_text(source, end_date="29-03-2023"))
    assert result.validation_status is ValidationStatus.OK
    assert result.rows[-2].number == 23
    assert result.rows[-2].validation_status == "removed_ignored_ovid_update_date"
    assert result.final_line_number == 24
    assert result.final_query == "#5"
    assert strategy_text(result).splitlines()[-1] == "#24 #5"
    assert one_line_query(result) == "((ankle[tw]) OR (fracture[tw])) AND (rehabilitation[tw])"


def test_update_date_omission_alone_does_not_trigger_v21_renumbering():
    source = "1 asthma.tw.\n2 (202401* or 2025*).ed,dt.\n3 cancer.tw.\n4 1 and 3"
    result = convert_strategy(parse_strategy_text(source, end_date="31-12-2025"))
    assert result.validation_status is ValidationStatus.OK
    assert strategy_text(result).splitlines() == [
        "#1 asthma[tw]",
        "#3 cancer[tw]",
        "#4 #1 AND #3",
    ]
    assert one_line_query(result) == "(asthma[tw]) AND (cancer[tw])"

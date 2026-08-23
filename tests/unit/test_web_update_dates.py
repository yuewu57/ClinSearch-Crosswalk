from ovid_pubmed_converter.engine import MeshResolver
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.outputs import one_line_query, strategy_text
from ovid_pubmed_converter.web_service import (
    convert_paste,
    has_eligible_update_date_construct,
)


def cache_only_resolver() -> MeshResolver:
    return MeshResolver(cache_path=None, mode="cache-only")


def test_online_cd005595_style_update_date_rows_are_removed():
    rows = [f"{number} unusedterm{number}.tw." for number in range(1, 22)]
    rows.extend(
        [
            "22 asthma.tw.",
            (
                "23 (201107* or 201108* or 201109* or 201110* or 201111* or "
                "201112* or 2012* or 2013* or 2014* or 2015* or 2016* or "
                "2017* or 2018* or 2019* or 2020* or 2021* or 2022*).ed,dt."
            ),
            "24 22 and 23",
        ]
    )

    result = convert_paste("\n".join(rows), resolver=cache_only_resolver())

    assert result.validation_status is ValidationStatus.OK
    assert result.rows[22].number == 23
    assert result.rows[22].converted == ""
    assert result.rows[22].validation_status == "removed_ignored_ovid_update_date"
    assert "ovid_database_update_date_filter_ignored" in result.rows[22].audit_flags
    assert result.final_line_number == 24
    assert result.final_query == "#22"
    assert one_line_query(result) == "asthma[tw]"

    rendered = strategy_text(result)
    assert "#23 " not in rendered
    assert "201107" not in rendered
    assert "2022" not in rendered
    assert "#24 #22" in rendered


def test_web_detection_uses_all_v21_database_update_date_suffixes():
    assert has_eligible_update_date_construct("1 (2021* or 2022*).ed.")
    assert has_eligible_update_date_construct("1 (2021* or 2022*).dt.")
    assert has_eligible_update_date_construct("1 (2021* or 2022*).ed,dt.")
    assert has_eligible_update_date_construct("1 (2021* or 2022*).dt,ed.")
    assert not has_eligible_update_date_construct("1 (cancer or 2022*).ed,dt.")

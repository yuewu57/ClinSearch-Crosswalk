import json
from pathlib import Path

import pytest

from ovid_pubmed_converter.engine import MeshResolver
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.web_service import (
    convert_paste,
    convert_rtf,
    download_payloads,
    has_eligible_update_date_construct,
    user_facing_validation_error,
    user_facing_warning,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "01_basic_mesh"
APP_PATH = Path(__file__).parents[2] / "web" / "app.py"


def fixture_resolver() -> MeshResolver:
    resolver = MeshResolver(cache_path=None, mode="cache-only")
    resolver.records = json.loads((FIXTURE / "mesh_records.json").read_text(encoding="utf-8"))
    return resolver


def test_web_paste_rtf_and_download_smoke():
    paste = convert_paste(
        (FIXTURE / "input_strategy.txt").read_text(encoding="utf-8"),
        resolver=fixture_resolver(),
    )
    rtf = convert_rtf((FIXTURE / "input.rtf").read_bytes(), resolver=fixture_resolver())

    assert paste.validation_status is ValidationStatus.OK
    assert rtf.validation_status is ValidationStatus.OK
    assert paste.final_query == rtf.final_query == '"Asthma"[mh]'
    assert [row.converted for row in paste.rows] == [row.converted for row in rtf.rows]

    payloads = download_payloads(rtf, include_rtf=True)
    assert payloads["pubmed_query.txt"] == b'"Asthma"[mh]\n'
    assert payloads["pubmed_strategy.txt"] == b'#1 "Asthma"[mh]\n'
    assert b"line_number,original,converted" in payloads["pubmed_audit.csv"]
    assert b'"status": "ok"' in payloads["pubmed_validation.json"]
    assert b'"one_line_query": "\\\"Asthma\\\"[mh]"' in payloads["pubmed_validation.json"]
    assert b'"warnings":' in payloads["pubmed_validation.json"]
    assert payloads["pubmed_strategy.rtf"].startswith(b"{\\rtf1")


def test_streamlit_application_imports_without_errors():
    pytest.importorskip("streamlit")
    streamlit_testing = __import__("streamlit.testing.v1", fromlist=["AppTest"])
    app = streamlit_testing.AppTest.from_file(APP_PATH)
    app.run(timeout=10)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Paste strategy", "Upload RTF"]
    assert app.title[0].value == "Evidentia-CSC: a Clinical Search Convertor"
    assert not app.text_input

    app.text_area[0].set_value("1 (202401* or 2025*).ed,dt.").run()
    assert [field.label for field in app.text_input] == ["External source-search end date"]


def test_web_resolver_uses_bundled_cache_in_exact_online_mode():
    from ovid_pubmed_converter.web_service import web_resolver

    resolver = web_resolver()
    assert resolver.mode == "online"
    assert resolver.cache_path is None


def test_web_workflow_falls_back_when_exact_nlm_service_is_unavailable():
    class UnavailableResolver(MeshResolver):
        def _ensure_mesh_year(self):
            raise RuntimeError("simulated NLM outage")

    result = convert_paste(
        "1 Unresolved Heading/",
        resolver=UnavailableResolver(cache_path=None, mode="online"),
    )

    assert result.final_query == '"Unresolved Heading"[mh]'
    assert any("mesh_api_unavailable" in event for event in result.audit_events)


def test_rtf_template_matches_equivalent_paste_strategy():
    template = Path("resources/rtf_input_template.rtf").read_bytes()
    source = "1. exp Asthma/\n2. asthma.tw.\n3. 1 or 2"

    paste = convert_paste(source, resolver=fixture_resolver())
    rtf = convert_rtf(template, resolver=fixture_resolver())

    assert paste.final_query == rtf.final_query
    assert [row.converted for row in paste.rows] == [row.converted for row in rtf.rows]
    assert download_payloads(paste)["pubmed_query.txt"] == download_payloads(rtf)[
        "pubmed_query.txt"
    ]


def test_utf16_plain_text_with_rtf_extension_is_accepted_and_audited():
    source = (
        "Medline:\r\n\r\n"
        "1. (e-health or ehealth).tw, kf\r\n"
        "2. exp speech therapy/\r\n"
        "3. 1 or 2\r\n"
    )
    data = source.encode("utf-16")

    result = convert_rtf(data, resolver=fixture_resolver())

    assert result.validation_status is ValidationStatus.OK
    assert [row.number for row in result.rows] == [1, 2, 3]
    assert "rtf_extension_plain_text_decoded" in result.warnings
    message = user_facing_warning("rtf_extension_plain_text_decoded")
    assert "actually plain text" in message
    assert "decoded it safely" in message
    assert download_payloads(result)["pubmed_query.txt"]


def test_unnumbered_medline_rtf_is_recovered_by_paragraph_order():
    data = b"{\\rtf1\\ansi Medline:\\par exp Asthma/\\par asthma.tw.\\par 1 or 2}"
    result = convert_rtf(data, resolver=fixture_resolver())

    assert result.validation_status is ValidationStatus.OK
    assert result.final_query == "#1 OR #2"
    assert [row.number for row in result.rows] == [1, 2, 3]
    assert "rtf_line_numbers_recovered_from_medline_paragraph_order" in result.warnings
    assert "Verify the reconstructed numbering" in user_facing_warning(result.warnings[-1])
    assert download_payloads(result)["pubmed_query.txt"] == (
        b'("Asthma"[mh]) OR (asthma[tw])\n'
    )


def test_ambiguous_unnumbered_medline_rtf_is_rejected():
    data = (
        b"{\\rtf1\\ansi Medline:\\par exp Asthma/\\par "
        b"wrapped continuation without an Ovid field\\par 1 or 2}"
    )
    result = convert_rtf(data, resolver=fixture_resolver())

    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    assert result.validation_errors == ("rtf_medline_block_missing_reliable_line_numbers",)
    message = user_facing_validation_error(result.validation_errors[0])
    assert "line numbers were missing" in message
    assert "could not be identified safely" in message
    assert download_payloads(result)["pubmed_query.txt"] == b""


def test_end_date_advanced_option_detection_is_specific_to_ed_dt():
    assert not has_eligible_update_date_construct("1 asthma.tw.")
    assert not has_eligible_update_date_construct("1 asthma.tw. or 2025.ed,dt.")
    assert has_eligible_update_date_construct("1 (202401* or 2025*).ed,dt.")


def test_ambiguous_standalone_rtf_has_clear_user_error():
    result = convert_rtf(b"{\\rtf1\\ansi arbitrary report text}", resolver=fixture_resolver())

    assert result.validation_status is ValidationStatus.VALIDATION_FAILED
    message = user_facing_validation_error(result.validation_errors[0])
    assert 'No explicit "Medline:" section' in message
    assert "re-export" in message.lower()

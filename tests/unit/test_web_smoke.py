import json
from pathlib import Path

import pytest

from ovid_pubmed_converter.engine import MeshResolver
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.web_service import convert_paste, convert_rtf, download_payloads


FIXTURE = Path(__file__).parents[1] / "fixtures" / "01_basic_mesh"


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
    assert payloads["pubmed_strategy.txt"] == b'#1 "Asthma"[mh]\n'
    assert b"line_number,original,converted" in payloads["pubmed_audit.csv"]
    assert b'"status": "ok"' in payloads["pubmed_validation.json"]
    assert payloads["pubmed_strategy.rtf"].startswith(b"{\\rtf1")


def test_streamlit_application_imports_without_errors():
    pytest.importorskip("streamlit")
    streamlit_testing = __import__("streamlit.testing.v1", fromlist=["AppTest"])
    app = streamlit_testing.AppTest.from_file("web/app.py")
    app.run(timeout=10)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Paste strategy", "Upload RTF"]


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

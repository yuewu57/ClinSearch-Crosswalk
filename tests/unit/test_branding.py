from pathlib import Path

from web.branding import (
    AFFILIATION_LABEL,
    BRAND_ASSET_DIRECTORY,
    BRAND_NAME,
    FUNCTIONAL_SUBTITLE,
    INSTITUTIONAL_AFFILIATION,
    PRODUCT_NAME,
    QUE2_LOGO_PATH,
    STRATHCLYDE_LOGO_PATH,
)

ROOT = Path(__file__).parents[2]


def test_presentation_identity_and_attribution_are_preserved():
    assert BRAND_NAME == "Que²"
    assert PRODUCT_NAME == "ClinSearch-CrossWalk: a Clinical Search Convertor"
    assert FUNCTIONAL_SUBTITLE == "Ovid MEDLINE → PubMed"
    assert AFFILIATION_LABEL == "Institutional affiliation"
    assert INSTITUTIONAL_AFFILIATION == "University of Strathclyde Glasgow"


def test_legacy_brand_paths_remain_metadata_not_required_assets():
    assert BRAND_ASSET_DIRECTORY == ROOT / "assets" / "brand"
    assert QUE2_LOGO_PATH == BRAND_ASSET_DIRECTORY / "Que2_brand.png"
    assert STRATHCLYDE_LOGO_PATH == BRAND_ASSET_DIRECTORY / "strath_brand.jpg"
    # Public release snapshots may omit brand images entirely.


def test_public_app_does_not_load_or_render_logos():
    app = (ROOT / "web/app.py").read_text(encoding="utf-8")
    for token in ("b64encode", "QUE2_LOGO_PATH", "STRATHCLYDE_LOGO_PATH", "<img"):
        assert token not in app
    assert "st.title(PRODUCT_NAME)" in app
    assert "INSTITUTIONAL_AFFILIATION" in app
    assert "PolyForm Noncommercial" in app
    assert "CITATION.cff" in app


def test_public_browser_surface_uses_release_branding_without_legacy_logos():
    app = (ROOT / "browser/src/main.ts").read_text(encoding="utf-8")
    assert "ClinSearch-CrossWalk" in app
    assert "Ovid MEDLINE" in app
    assert "PubMed" in app
    assert "<img" not in app
    assert "assets/brand/" not in app
    assert "ASSOCIATED PAPER" in app
    assert "PolyForm Noncommercial" not in app
    assert "Source licence" in app

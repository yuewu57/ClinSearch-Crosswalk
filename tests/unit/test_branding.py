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
    assert PRODUCT_NAME == "Evidentia-CSC: a Clinical Search Convertor"
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


def test_public_site_has_neutral_title_with_credit_and_citation():
    index = (ROOT / "site/index.html").read_text(encoding="utf-8")
    assert "<h1>Evidentia-CSC: a Clinical Search Convertor</h1>" in index
    assert '<p class="subtitle">Ovid MEDLINE → PubMed</p>' in index
    assert "<img" not in index
    assert "assets/brand/" not in index
    assert "University of Strathclyde Glasgow" in index
    assert "CITATION.cff" in index
    assert "PolyForm Noncommercial" in index

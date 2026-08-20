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


def test_presentation_brand_hierarchy_is_explicit():
    assert BRAND_NAME == "Que²"
    assert PRODUCT_NAME == "Evidentia-CSC: a Clinical Search Convertor"
    assert FUNCTIONAL_SUBTITLE == "Ovid MEDLINE → PubMed"
    assert AFFILIATION_LABEL == "Institutional affiliation"
    assert INSTITUTIONAL_AFFILIATION == "University of Strathclyde Glasgow"


def test_co_brand_assets_use_the_existing_repository_images():
    assert BRAND_ASSET_DIRECTORY == Path(__file__).parents[2] / "assets" / "brand"
    assert QUE2_LOGO_PATH == BRAND_ASSET_DIRECTORY / "Que2_brand.png"
    assert STRATHCLYDE_LOGO_PATH == BRAND_ASSET_DIRECTORY / "strath_brand.jpg"
    assert QUE2_LOGO_PATH.name == "Que2_brand.png"
    assert STRATHCLYDE_LOGO_PATH.name == "strath_brand.jpg"
    assert QUE2_LOGO_PATH.is_file()
    assert STRATHCLYDE_LOGO_PATH.is_file()


def test_static_site_presents_brand_product_and_affiliation_in_order():
    index = (Path(__file__).parents[2] / "site" / "index.html").read_text(encoding="utf-8")

    que2_position = index.index('../assets/brand/Que2_brand.png')
    title_position = index.index("<h1>Evidentia-CSC: a Clinical Search Convertor</h1>")
    subtitle_position = index.index("<p class=\"subtitle\">Ovid MEDLINE → PubMed</p>")
    affiliation_position = index.index('class="institutional-affiliation"')
    affiliation_label_position = index.index('class="affiliation-label"')
    strathclyde_position = index.index('../assets/brand/strath_brand.jpg')

    assert que2_position < title_position < subtitle_position
    assert subtitle_position < affiliation_position < affiliation_label_position
    assert affiliation_label_position < strathclyde_position
    assert 'class="co-brand"' not in index
    assert 'class="brand-separator"' not in index

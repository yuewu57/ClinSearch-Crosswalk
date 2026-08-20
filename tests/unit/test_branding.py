from pathlib import Path

from web.branding import (
    BRAND_ASSET_DIRECTORY,
    BRAND_NAME,
    FUNCTIONAL_SUBTITLE,
    PRODUCT_NAME,
    QUE2_LOGO_PATH,
    STRATHCLYDE_LOGO_PATH,
)


def test_presentation_brand_hierarchy_is_explicit():
    assert BRAND_NAME == "Que²"
    assert PRODUCT_NAME == "Evidentia-CSC: a Clinical Search Convertor"
    assert FUNCTIONAL_SUBTITLE == "Ovid MEDLINE → PubMed"


def test_co_brand_assets_use_the_existing_repository_images():
    assert BRAND_ASSET_DIRECTORY == Path(__file__).parents[2] / "assets" / "brand"
    assert QUE2_LOGO_PATH == BRAND_ASSET_DIRECTORY / "Que2_brand.png"
    assert STRATHCLYDE_LOGO_PATH == BRAND_ASSET_DIRECTORY / "strath_brand.jpg"
    assert QUE2_LOGO_PATH.is_file()
    assert STRATHCLYDE_LOGO_PATH.is_file()


def test_static_site_places_both_brand_images_before_the_product_title():
    index = (Path(__file__).parents[2] / "site" / "index.html").read_text(encoding="utf-8")

    que2_position = index.index('../assets/brand/Que2_brand.png')
    separator_position = index.index('class="brand-separator"')
    strathclyde_position = index.index('../assets/brand/strath_brand.jpg')
    title_position = index.index("<h1>Evidentia Search Strategy Convertor</h1>")

    assert que2_position < separator_position < strathclyde_position < title_position

from web.branding import (
    FUNCTIONAL_SUBTITLE,
    PRODUCT_NAME,
    QUE2_BRAND_ALT,
    QUE2_BRAND_PATH,
    STRATH_BRAND_ALT,
    STRATH_BRAND_PATH,
)


def test_presentation_brand_hierarchy_is_explicit():
    assert QUE2_BRAND_ALT == "Que² — Intelligence Compounded"
    assert STRATH_BRAND_ALT == "University of Strathclyde Glasgow"
    assert QUE2_BRAND_PATH.as_posix().endswith("assets/brand/que2_brand.png")
    assert STRATH_BRAND_PATH.as_posix().endswith("assets/brand/strath_brand.jpg")
    assert PRODUCT_NAME == "Evidentia Search Strategy Convertor"
    assert FUNCTIONAL_SUBTITLE == "Ovid MEDLINE → PubMed"

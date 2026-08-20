from web.branding import BRAND_NAME, FUNCTIONAL_SUBTITLE, PRODUCT_NAME


def test_presentation_brand_hierarchy_is_explicit():
    assert BRAND_NAME == "Que²"
    assert PRODUCT_NAME == "Evidentia Search Strategy Convertor"
    assert FUNCTIONAL_SUBTITLE == "Ovid MEDLINE → PubMed"

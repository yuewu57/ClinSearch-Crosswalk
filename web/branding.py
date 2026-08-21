"""Presentation-only brand hierarchy for the interactive application."""

from pathlib import Path

BRAND_ASSET_DIRECTORY = Path(__file__).resolve().parents[1] / "assets" / "brand"
QUE2_LOGO_PATH = BRAND_ASSET_DIRECTORY / "Que2_brand.png"
STRATHCLYDE_LOGO_PATH = BRAND_ASSET_DIRECTORY / "strath_brand.jpg"

BRAND_NAME = "Que²"
PRODUCT_NAME = "Evidentia-CSC: a Clinical Search Convertor"
FUNCTIONAL_SUBTITLE = "Ovid MEDLINE → PubMed"
AFFILIATION_LABEL = "Institutional affiliation"
INSTITUTIONAL_AFFILIATION = "University of Strathclyde Glasgow"

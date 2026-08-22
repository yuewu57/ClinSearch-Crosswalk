from ovid_pubmed_converter.engine import MeshResolver
from ovid_pubmed_converter.models import ValidationStatus
from ovid_pubmed_converter.web_service import convert_rtf, download_payloads


def test_realistic_utf16_medline_text_uploaded_as_rtf_converts():
    source = """Medline:

1. (e-health or ehealth).tw, kf
2. exp speech therapy/
3. exp occupational therapy/
4. telemedicine/or telerehabilitation/or telehealth/ or telepsychiatry/
5. (telemedicine or tele medicine or tele-medicine or telerehab* or telepsychiatr*).tw,kf
6. (text messag* or video conferenc*).tw,kf
7. ((online or web or remote* or virtual or digital) adj1 (intervention* or therap* or aftercare or rehab* or consult*)).tw,kf
8. occupational therapist/or physical therapist/or speech therapist/
9. exp physical therapy/
10. 1 or 4 or 5 or 6 or 7
11. 2 or 3 or 8 or 9
12. 10 and 11
"""
    resolver = MeshResolver(cache_path=None, mode="cache-only")

    result = convert_rtf(source.encode("utf-16"), resolver=resolver)

    assert result.validation_status is ValidationStatus.OK
    assert [row.number for row in result.rows] == list(range(1, 13))
    assert result.final_query == "#10 AND #11"
    assert "plain_text_file_uploaded_with_rtf_extension" in result.warnings

    payloads = download_payloads(result)
    assert payloads["pubmed_strategy.txt"]
    assert payloads["pubmed_query.txt"]
    assert b"#" not in payloads["pubmed_query.txt"]

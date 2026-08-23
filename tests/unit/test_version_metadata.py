from ovid_pubmed_converter import RULESET_VERSION, __version__


def test_software_and_ruleset_versions_are_separate():
    assert __version__ == "0.1.1"
    assert RULESET_VERSION == "v21"

import json
from pathlib import Path

import pytest
from conftest import resolver_for

from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.outputs import strategy_text
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes

FIXTURE_IDS = [
    path.name
    for path in sorted((Path(__file__).parents[1] / "fixtures").glob("[0-9][0-9]_*"))
    if (path / "fixture.json").exists()
]


@pytest.mark.parametrize("fixture_id", FIXTURE_IDS)
def test_paste_and_rtf_fixture_modes_are_identical(fixture_root, fixture_id):
    directory = fixture_root / fixture_id
    definition = json.loads((directory / "fixture.json").read_text(encoding="utf-8"))
    options = json.loads((directory / "input_options.json").read_text(encoding="utf-8"))
    expected = (directory / "expected_pubmed.txt").read_text(encoding="utf-8")

    paste = parse_strategy_text(
        (directory / "input_strategy.txt").read_text(encoding="utf-8"),
        end_date=options.get("end_date"),
    )
    rtf = parse_rtf_bytes((directory / "input.rtf").read_bytes())
    paste_result = convert_strategy(paste, mesh_resolver=resolver_for(directory))
    rtf_result = convert_strategy(rtf, mesh_resolver=resolver_for(directory))

    assert strategy_text(paste_result) == expected
    assert strategy_text(rtf_result) == expected
    assert paste_result.validation_status.value == definition["expected_validation_status"]
    assert rtf_result.validation_status.value == definition["expected_validation_status"]
    paste_audit = "\n".join(paste_result.audit_events)
    rtf_audit = "\n".join(rtf_result.audit_events)
    for required in definition["required_audit_substrings"]:
        assert required in paste_audit
        assert required in rtf_audit
    for forbidden in definition["forbidden_audit_substrings"]:
        assert forbidden not in paste_audit
        assert forbidden not in rtf_audit
    for forbidden in definition["forbidden_output_substrings"]:
        assert forbidden not in expected


def test_standalone_numbered_ovid_rtf_regression(fixture_root):
    """A marker-free but structurally unambiguous Ovid RTF matches paste mode."""
    directory = fixture_root / "17_standalone_ovid_rtf"
    paste = parse_strategy_text((directory / "input_strategy.txt").read_text(encoding="utf-8"))
    rtf = parse_rtf_bytes((directory / "input.rtf").read_bytes())

    assert rtf.metadata["source_format"] == "standalone_numbered_strategy"
    assert rtf.source_errors == ()
    assert [(row.number, row.source) for row in rtf.rows] == [
        (row.number, row.source) for row in paste.rows
    ]

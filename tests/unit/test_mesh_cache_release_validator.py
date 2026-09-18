import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "scripts" / "validate_mesh_cache_release.py"
SPEC = importlib.util.spec_from_file_location("validate_mesh_cache_release", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _valid_record():
    return {
        "status": "resolved",
        "source_label": "Asthma",
        "matched_label": "Asthma",
        "match_type": "preferred",
        "canonical_label": "Asthma",
        "descriptor_id": "D001249",
        "descriptor_uri": "http://id.nlm.nih.gov/mesh/D001249",
        "record_class": "TopicalDescriptor",
        "is_pharmacological_action": False,
        "mesh_year": 2026,
    }


def test_release_cache_validator_accepts_verified_nonempty_cache(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": 2026,
                "generated_at_utc": "2026-09-18T12:00:00+00:00",
                "source": "NLM MeSH RDF Lookup and SPARQL APIs",
                "records": {"asthma": _valid_record()},
            }
        ),
        encoding="utf-8",
    )

    report = MODULE.validate_cache(cache)

    assert report["release_ready"] is True
    assert report["records"] == 1
    assert report["errors"] == []
    assert len(report["sha256"]) == 64


def test_release_cache_validator_rejects_empty_starter_cache(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": None,
                "generated_at_utc": None,
                "source": "Empty starter cache",
                "records": {},
            }
        ),
        encoding="utf-8",
    )

    report = MODULE.validate_cache(cache)

    assert report["release_ready"] is False
    assert "release_cache_is_empty" in report["errors"]
    assert "mesh_year_missing_or_not_integer" in report["errors"]


def test_release_cache_validator_rejects_fixture_metadata(tmp_path):
    cache = tmp_path / "cache.json"
    record = _valid_record()
    record["descriptor_uri"] = "fixture://D001249"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": 2026,
                "generated_at_utc": "2026-09-18T12:00:00+00:00",
                "source": "NLM MeSH RDF Lookup and SPARQL APIs",
                "records": {"asthma": record},
            }
        ),
        encoding="utf-8",
    )

    report = MODULE.validate_cache(cache)

    assert report["release_ready"] is False
    assert any("synthetic_fixture_metadata_detected" in error for error in report["errors"])


def test_release_cache_validator_allows_empty_starter_for_development(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": None,
                "generated_at_utc": None,
                "source": "Empty v20 starter cache; exact NLM results may be added at runtime",
                "records": {},
            }
        ),
        encoding="utf-8",
    )

    report = MODULE.validate_cache(cache, require_nonempty=False)

    assert report["release_ready"] is True
    assert report["errors"] == []
    assert "cache_is_empty" in report["warnings"]


def test_release_cache_validator_accepts_extended_descriptor_id(tmp_path):
    cache = tmp_path / "cache.json"
    record = _valid_record()
    record["descriptor_id"] = "D000069340"
    record["descriptor_uri"] = "http://id.nlm.nih.gov/mesh/D000069340"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": 2026,
                "generated_at_utc": "2026-09-18T12:00:00+00:00",
                "source": "NLM MeSH RDF Lookup and SPARQL APIs",
                "records": {"deprescriptions": record},
            }
        ),
        encoding="utf-8",
    )

    report = MODULE.validate_cache(cache)

    assert report["release_ready"] is True
    assert report["errors"] == []

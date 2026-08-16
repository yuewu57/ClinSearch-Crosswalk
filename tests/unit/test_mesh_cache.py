import json

from ovid_pubmed_converter import mesh_cache
from ovid_pubmed_converter.engine import MeshResolver


def test_cache_builder_scans_private_text_corpus_without_copying_it(tmp_path, monkeypatch):
    dataset = tmp_path / "private-corpus"
    dataset.mkdir()
    (dataset / "study.txt").write_text("1 Asthma/", encoding="utf-8")
    output = tmp_path / "production-cache.json"
    resolver = MeshResolver(cache_path=output, mode="cache-only")
    resolver.records["asthma"] = {
        "status": "resolved",
        "source_label": "Asthma",
        "matched_label": "Asthma",
        "match_type": "preferred",
        "canonical_label": "Asthma",
        "descriptor_id": "D001249",
        "descriptor_uri": "https://id.nlm.nih.gov/mesh/D001249",
        "record_class": "TopicalDescriptor",
        "is_pharmacological_action": False,
        "mesh_year": 2026,
    }
    resolver.mesh_year = 2026
    resolver.dirty = True
    monkeypatch.setattr(mesh_cache, "load_mesh_resolver", lambda *_args, **_kwargs: resolver)

    report = mesh_cache.build_cache(dataset, output, pattern="**/*.txt")

    assert report["files_scanned"] == 1
    assert report["resolved_records"] == 1
    assert report["failed_inputs"] == []
    assert report["unresolved_headings"] == []
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert set(payload["records"]) == {"asthma"}
    assert "1 Asthma/" not in output.read_text(encoding="utf-8")
    assert mesh_cache.inspect_cache(output)["records"] == 1

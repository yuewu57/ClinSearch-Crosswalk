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


def test_production_cache_path_prefers_newest_dated_cache(tmp_path, monkeypatch):
    from ovid_pubmed_converter import mesh

    bootstrap = tmp_path / "mesh_resolution_cache_v20_v1.json"
    older = tmp_path / "mesh_resolution_cache_v20_v1_YW_01012026.json"
    newest = tmp_path / "mesh_resolution_cache_v20_v1_YW_16082026.json"
    for path in (bootstrap, newest, older):
        path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mesh, "_RESOURCES", tmp_path)

    assert mesh.production_cache_path() == newest


def test_hosted_resolver_loads_cache_without_retaining_write_path(tmp_path):
    from ovid_pubmed_converter.mesh import load_mesh_resolver

    cache = tmp_path / "mesh_resolution_cache_v20_v1_YW_16082026.json"
    cache.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mesh_year": 2026,
                "records": {
                    "asthma": {
                        "status": "resolved",
                        "canonical_label": "Asthma",
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    resolver = load_mesh_resolver(cache, online=True, persist_updates=False)

    assert resolver.mode == "online"
    assert resolver.records["asthma"]["canonical_label"] == "Asthma"
    assert resolver.cache_path is None

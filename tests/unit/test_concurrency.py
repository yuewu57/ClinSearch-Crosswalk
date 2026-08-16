from concurrent.futures import ThreadPoolExecutor

from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.engine import MeshResolver
from ovid_pubmed_converter.parser import parse_strategy_text


def _resolver(source: str, canonical: str) -> MeshResolver:
    resolver = MeshResolver(cache_path=None, mode="cache-only")
    resolver.records[source.casefold()] = {
        "status": "resolved",
        "source_label": source,
        "matched_label": source,
        "match_type": "preferred",
        "canonical_label": canonical,
        "descriptor_id": f"TEST_{canonical}",
        "descriptor_uri": f"test://mesh/{canonical}",
        "record_class": "TopicalDescriptor",
        "is_pharmacological_action": False,
        "mesh_year": 2026,
    }
    return resolver


def test_concurrent_conversions_keep_resolvers_isolated():
    strategies = [parse_strategy_text("1 Shared Heading/") for _ in range(20)]
    resolvers = [
        _resolver("Shared Heading", "Canonical Alpha"),
        _resolver("Shared Heading", "Canonical Beta"),
    ]

    def convert(index: int) -> str:
        result = convert_strategy(strategies[index], mesh_resolver=resolvers[index % 2])
        return result.rows[0].converted

    with ThreadPoolExecutor(max_workers=8) as executor:
        outputs = list(executor.map(convert, range(len(strategies))))

    assert outputs[::2] == ['"Canonical Alpha"[mh]'] * 10
    assert outputs[1::2] == ['"Canonical Beta"[mh]'] * 10


def test_concurrent_style_stale_cache_writers_merge_records(tmp_path):
    from ovid_pubmed_converter.mesh import load_mesh_resolver

    cache = tmp_path / "cache.json"
    cache.write_text(
        '{"schema_version": 1, "mesh_year": 2026, "records": {}}',
        encoding="utf-8",
    )
    first = load_mesh_resolver(cache)
    second = load_mesh_resolver(cache)
    first.records["alpha"] = {"status": "resolved", "canonical_label": "Alpha"}
    first.dirty = True
    second.records["beta"] = {"status": "resolved", "canonical_label": "Beta"}
    second.dirty = True

    first.flush()
    second.flush()

    reloaded = load_mesh_resolver(cache)
    assert set(reloaded.records) == {"alpha", "beta"}

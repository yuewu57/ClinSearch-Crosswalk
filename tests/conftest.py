import json
from pathlib import Path

import pytest

from ovid_pubmed_converter.engine import MeshResolver


@pytest.fixture
def fixture_root() -> Path:
    return Path(__file__).parent / "fixtures"


def resolver_for(directory: Path) -> MeshResolver:
    resolver = MeshResolver(cache_path=None, mode="cache-only")
    mesh_file = directory / "mesh_records.json"
    if mesh_file.exists():
        resolver.records = json.loads(mesh_file.read_text(encoding="utf-8"))
        resolver.mesh_year = 2026
    return resolver

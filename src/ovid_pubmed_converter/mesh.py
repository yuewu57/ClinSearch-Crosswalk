"""Exact cache-first MeSH resolution and production cache location."""

import json
from pathlib import Path
from threading import RLock

from .engine import MeshResolver

_CACHE_WRITE_LOCK = RLock()
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_RESOURCES = _REPOSITORY_ROOT / "resources"


class LockedMeshResolver(MeshResolver):
    """Serialize atomic cache updates made by concurrent local web sessions."""

    def flush(self) -> None:
        with _CACHE_WRITE_LOCK:
            if self.dirty and self.cache_path is not None and self.cache_path.exists():
                payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
                disk_records = payload.get("records", {})
                if isinstance(disk_records, dict):
                    self.records = {**disk_records, **self.records}
                self.mesh_year = self.mesh_year or payload.get("mesh_year")
            super().flush()


def production_cache_path() -> Path:
    """Return the newest bundled dated cache, or the empty v1 bootstrap cache."""
    dated = sorted(_RESOURCES.glob("mesh_resolution_cache_v20_v1_YW_*.json"))
    return dated[-1] if dated else _RESOURCES / "mesh_resolution_cache_v20_v1.json"


def load_mesh_resolver(
    cache_path: Path | None = None,
    *,
    online: bool = False,
    persist_updates: bool = True,
) -> MeshResolver:
    """Create a cache-first exact resolver with normative source-heading fallback."""
    resolver = LockedMeshResolver(
        cache_path=cache_path,
        mode="online" if online else "cache-only",
    )
    if not persist_updates:
        # Records were loaded during construction. Disabling the write target
        # keeps a hosted app independent of repository filesystem writability.
        resolver.cache_path = None
    return resolver

"""Exact cache-first MeSH resolution."""

from pathlib import Path

from .engine import MeshResolver


def load_mesh_resolver(cache_path: Path | None = None, *, online: bool = False) -> MeshResolver:
    """Create an exact-only resolver; public conversion defaults to reproducible cache-only."""
    return MeshResolver(cache_path=cache_path, mode="online" if online else "cache-only")

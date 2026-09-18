"""Compact, offline MeSH descriptor snapshot adapter; no conversion rules changed.

Uses the reference engine's exact label normalizer. The snapshot has complete
current descriptor/Term coverage, not a reconstruction of historical Ovid MeSH.
Supplementary records supply direct PA links only, never invented [mh] aliases.
"""
from __future__ import annotations

import re
from typing import Any

from ovid_pubmed_converter.engine import (
    MeshResolver,
    _mesh_cache_key,
    normalize_mesh_lookup_label,
)

SCHEMA = 2
KIND = "nlm-mesh-descriptor-exact-snapshot"
CLASSES = {
    "1": "TopicalDescriptor",
    "2": "PublicationType",
    "3": "CheckTag",
    "4": "GeographicalDescriptor",
}
UID = re.compile(r"D(?:\d{6}|\d{9})\Z")


def validate_snapshot(data: dict[str, Any]) -> dict[str, int]:
    """Exhaustive structural checks. Source authenticity needs the source lock."""
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA:
        raise ValueError("browser_snapshot_schema_invalid")
    if data.get("kind") != KIND or data.get("mesh_year") != 2026:
        raise ValueError("browser_snapshot_kind_or_year_invalid")
    for field in ("descriptors", "preferred", "terms", "project_aliases"):
        if not isinstance(data.get(field), dict):
            raise ValueError(f"browser_snapshot_{field}_invalid")
    descriptors = data["descriptors"]
    if not descriptors:
        raise ValueError("browser_snapshot_empty")
    for ui, record in descriptors.items():
        if not UID.fullmatch(ui):
            raise ValueError(f"browser_snapshot_descriptor_id_invalid:{ui}")
        if not isinstance(record, list) or len(record) != 3:
            raise ValueError("browser_snapshot_descriptor_record_invalid")
        label, cls, pa = record
        if not isinstance(label, str) or not label.strip() or cls not in CLASSES:
            raise ValueError("browser_snapshot_descriptor_metadata_invalid")
        if not isinstance(pa, bool):
            raise ValueError("browser_snapshot_pa_metadata_invalid")
        if ui not in data["preferred"].get(_mesh_cache_key(label), []):
            raise ValueError("browser_snapshot_missing_preferred_label")
    for field in ("preferred", "terms"):
        for key, candidates in data[field].items():
            if not isinstance(key, str) or not key or key != _mesh_cache_key(key):
                raise ValueError("browser_snapshot_key_not_normalized")
            if (not isinstance(candidates, list) or not candidates
                    or candidates != sorted(set(candidates))):
                raise ValueError("browser_snapshot_candidate_list_invalid")
            if any(ui not in descriptors for ui in candidates):
                raise ValueError("browser_snapshot_dangling_descriptor")
            if field == "preferred" and any(
                _mesh_cache_key(descriptors[ui][0]) != key for ui in candidates
            ):
                raise ValueError("browser_snapshot_preferred_label_mismatch")
    for key, target in data["project_aliases"].items():
        if key != _mesh_cache_key(key) or not isinstance(target, str):
            raise ValueError("browser_snapshot_project_alias_invalid")
        targets = data["preferred"].get(_mesh_cache_key(target), [])
        if len(targets) != 1:
            raise ValueError("browser_snapshot_project_alias_target_not_unique")
        if key in data["preferred"] and data["preferred"][key] != targets:
            raise ValueError("browser_snapshot_project_alias_overrides_current_heading")
    return {
        "descriptors": len(descriptors),
        "preferred_label_keys": len(data["preferred"]),
        "term_label_keys": len(data["terms"]),
        "all_label_keys": len(set(data["preferred"]) | set(data["terms"])),
        "ambiguous_preferred_keys": sum(len(x) > 1 for x in data["preferred"].values()),
        "ambiguous_entry_only_keys": sum(
            len(v) > 1 and k not in data["preferred"] for k, v in data["terms"].items()
        ),
        "pharmacological_action_targets": sum(rec[2] for rec in descriptors.values()),
        "inherited_project_aliases": len(data["project_aliases"]),
    }


class SnapshotResolver(MeshResolver):
    """Resolve on demand without expanding the compact index into a huge cache."""

    def __init__(self, data: dict[str, Any], *, validate: bool = True):
        super().__init__(cache_path=None, mode="cache-only")
        if validate:
            validate_snapshot(data)
        elif (data.get("schema_version") != SCHEMA or data.get("kind") != KIND
              or data.get("mesh_year") != 2026):
            raise ValueError("browser_snapshot_schema_invalid")
        self.snapshot = data
        self.mesh_year = 2026

    def resolve(self, source_label: str) -> dict[str, Any]:
        original = normalize_mesh_lookup_label(source_label)
        key = _mesh_cache_key(original)
        target = self.snapshot["project_aliases"].get(key)
        lookup_key = _mesh_cache_key(target) if target else key
        preferred = self.snapshot["preferred"].get(lookup_key, [])
        if preferred:
            candidates = preferred
            match_type = "historical" if target else "preferred"
            reason = "multiple_exact_descriptor_matches"
        else:
            candidates = self.snapshot["terms"].get(key, [])
            match_type = "entry"
            reason = "entry_term_maps_to_multiple_descriptors"
        if not candidates:
            return {
                "status": "unresolved",
                "reason": "no_exact_preferred_or_entry_match_in_frozen_snapshot",
                "source_label": original,
            }
        if len(candidates) != 1:
            return {
                "status": "ambiguous",
                "reason": reason,
                "candidate_uris": [
                    f"http://id.nlm.nih.gov/mesh/{ui}" for ui in candidates
                ],
                "source_label": original,
            }
        ui = candidates[0]
        label, cls, pa = self.snapshot["descriptors"][ui]
        return {
            "status": "resolved",
            "source_label": original,
            "matched_label": target or original,
            "match_type": match_type,
            "canonical_label": label,
            "descriptor_id": ui,
            "descriptor_uri": f"http://id.nlm.nih.gov/mesh/{ui}",
            "record_class": CLASSES[cls],
            "is_pharmacological_action": pa,
            "mesh_year": 2026,
        }

    def prefetch(self, source_labels, max_workers: int = 4):
        del max_workers
        return {_mesh_cache_key(label): self.resolve(label) for label in source_labels}


def resolver_from_payload(cache: dict[str, Any]) -> MeshResolver:
    """Browser bridge entry; schema-1 evaluation-cache behaviour is preserved."""
    if not isinstance(cache, dict):
        raise ValueError("browser_cache_schema_invalid")
    if cache.get("schema_version") == SCHEMA:
        return SnapshotResolver(cache, validate=False)
    if cache.get("schema_version") != 1:
        raise ValueError("browser_cache_schema_invalid")
    if not isinstance(cache.get("records"), dict):
        raise TypeError("browser_cache_records_invalid")
    resolver = MeshResolver(cache_path=None, mode="cache-only")
    resolver.records = dict(cache["records"])
    resolver.mesh_year = cache.get("mesh_year")
    return resolver

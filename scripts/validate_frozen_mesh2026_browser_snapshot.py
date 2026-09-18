"""Validate the frozen MeSH 2026 browser snapshot before packaging."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

EXPECTED_SNAPSHOT_SHA256 = "7ebdeba5e6c6d09b154e053e57777d746b51939a50bad8deac5b14bd07c7a6da"
EXPECTED_SNAPSHOT_BYTES = 12222418
EXPECTED_EVALUATION_CACHE_CANONICAL_SHA256 = "34467e3deb46ec6a6709ad0123bf86f7d637aaec091e2a149437c03770b71caf"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json_sha256(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    raw = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    snapshot = args.snapshot.resolve()
    sys.path.insert(0, str(repo / "src"))
    sys.path.insert(0, str(repo / "browser/python"))

    try:
        raw = snapshot.read_bytes()
        actual = hashlib.sha256(raw).hexdigest()
        if len(raw) != EXPECTED_SNAPSHOT_BYTES or actual != EXPECTED_SNAPSHOT_SHA256:
            raise ValueError("snapshot bytes do not match the frozen reviewed artifact")

        from mesh_snapshot_resolver_v1_YW_18092026 import validate_snapshot

        data = json.loads(raw)
        counts = validate_snapshot(data)
        expected_counts = {
            "descriptors": 31110,
            "preferred_label_keys": 31110,
            "term_label_keys": 267012,
            "all_label_keys": 267012,
            "ambiguous_preferred_keys": 0,
            "ambiguous_entry_only_keys": 0,
            "pharmacological_action_targets": 567,
            "inherited_project_aliases": 10,
        }
        if counts != expected_counts:
            raise ValueError(f"unexpected snapshot counts: {counts}")
        if data.get("counts", {}).get("supplementary_records_scanned_for_PA") != 324046:
            raise ValueError("supplementary PA scan count differs from frozen provenance")
        if data.get("source_sha256") != {
            "desc2026.gz": "ccd4d0d33bebfd4c836a59e7dd0c635b1d4e20c4f5a6abc55e2eb0ba4c8716dd",
            "supp2026.gz": "5d487dbb55807724465065f5c0945c630290a0a6decee14618f5380c574d87ab",
        }:
            raise ValueError("source hashes differ from frozen provenance")

        evaluation_cache = repo / "resources/mesh_resolution_cache_v20_v1_YW_18092026.json"
        if canonical_json_sha256(evaluation_cache) != EXPECTED_EVALUATION_CACHE_CANONICAL_SHA256:
            raise ValueError("evaluation provenance cache changed semantically")

        print(json.dumps({
            "snapshot_valid": True,
            "sha256": actual,
            "descriptors": counts["descriptors"],
            "label_keys": counts["all_label_keys"],
            "evaluation_cache_canonical_sha256": EXPECTED_EVALUATION_CACHE_CANONICAL_SHA256,
        }))
        return 0
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError, ImportError) as exc:
        print(f"Snapshot validation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

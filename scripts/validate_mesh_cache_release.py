"""Validate a populated MeSH cache before freezing a public release."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ALLOWED_RECORD_CLASSES = {
    "TopicalDescriptor",
    "PublicationType",
    "CheckTag",
    "GeographicalDescriptor",
}
ALLOWED_MATCH_TYPES = {"preferred", "entry", "historical"}
DESCRIPTOR_ID_RE = re.compile(r"^D(?:\d{6}|\d{9})$")
NLM_MESH_PREFIX = "http://id.nlm.nih.gov/mesh/"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_cache(path: Path, *, require_nonempty: bool = True) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    if payload.get("schema_version") != 1:
        errors.append("schema_version_must_equal_1")

    records = payload.get("records")
    if not isinstance(records, dict):
        errors.append("records_must_be_an_object")
        records = {}

    is_empty_development_cache = not records and not require_nonempty

    mesh_year = payload.get("mesh_year")
    if not isinstance(mesh_year, int):
        if is_empty_development_cache and mesh_year is None:
            warnings.append("mesh_year_unset_for_empty_development_cache")
        else:
            errors.append("mesh_year_missing_or_not_integer")

    generated_at = payload.get("generated_at_utc")
    if not _valid_timestamp(generated_at):
        if is_empty_development_cache and generated_at is None:
            warnings.append("generated_at_utc_unset_for_empty_development_cache")
        else:
            errors.append("generated_at_utc_missing_or_not_timezone_aware")

    source = payload.get("source")
    if not isinstance(source, str) or not source.strip():
        errors.append("source_missing")

    if require_nonempty and not records:
        errors.append("release_cache_is_empty")
    elif not records:
        warnings.append("cache_is_empty")

    classes: Counter[str] = Counter()
    matches: Counter[str] = Counter()
    pharmacological_actions = 0

    for key, record in sorted(records.items()):
        prefix = f"record:{key}"
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{prefix}:invalid_cache_key")
            continue
        if not isinstance(record, dict):
            errors.append(f"{prefix}:record_must_be_an_object")
            continue

        serialized = json.dumps(record, sort_keys=True)
        if re.search(r"FIXTURE_|fixture://", serialized, flags=re.IGNORECASE):
            errors.append(f"{prefix}:synthetic_fixture_metadata_detected")

        if record.get("status") != "resolved":
            errors.append(f"{prefix}:status_must_be_resolved")

        for field in ("source_label", "canonical_label", "descriptor_uri"):
            value = record.get(field)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{prefix}:{field}_missing")

        descriptor_id = record.get("descriptor_id")
        if not isinstance(descriptor_id, str) or not DESCRIPTOR_ID_RE.fullmatch(descriptor_id):
            errors.append(f"{prefix}:invalid_descriptor_id")
        else:
            descriptor_uri = record.get("descriptor_uri")
            if isinstance(descriptor_uri, str):
                if not descriptor_uri.startswith(NLM_MESH_PREFIX):
                    errors.append(f"{prefix}:descriptor_uri_not_nlm_mesh")
                if not descriptor_uri.rstrip("/").endswith("/" + descriptor_id):
                    errors.append(f"{prefix}:descriptor_uri_id_mismatch")

        record_class = record.get("record_class")
        if record_class not in ALLOWED_RECORD_CLASSES:
            errors.append(f"{prefix}:unsupported_record_class:{record_class}")
        elif isinstance(record_class, str):
            classes[record_class] += 1

        match_type = record.get("match_type")
        if match_type not in ALLOWED_MATCH_TYPES:
            errors.append(f"{prefix}:unsupported_match_type:{match_type}")
        elif isinstance(match_type, str):
            matches[match_type] += 1

        is_pa = record.get("is_pharmacological_action")
        if not isinstance(is_pa, bool):
            errors.append(f"{prefix}:is_pharmacological_action_must_be_boolean")
        elif is_pa:
            pharmacological_actions += 1

        record_year = record.get("mesh_year")
        if isinstance(mesh_year, int) and record_year != mesh_year:
            errors.append(
                f"{prefix}:mesh_year_mismatch:{record_year!r}!={mesh_year!r}"
            )

    return {
        "path": str(path),
        "sha256": _sha256(path),
        "schema_version": payload.get("schema_version"),
        "mesh_year": mesh_year,
        "generated_at_utc": generated_at,
        "source": source,
        "records": len(records),
        "record_classes": dict(sorted(classes.items())),
        "match_types": dict(sorted(matches.items())),
        "pharmacological_action_records": pharmacological_actions,
        "errors": errors,
        "warnings": warnings,
        "release_ready": not errors and (bool(records) or not require_nonempty),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="Allow an empty starter cache for development checks only.",
    )
    args = parser.parse_args()

    report = validate_cache(args.cache, require_nonempty=not args.allow_empty)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["release_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

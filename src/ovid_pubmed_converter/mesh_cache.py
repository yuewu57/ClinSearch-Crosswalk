"""Build or inspect versioned exact-resolution MeSH caches."""

import argparse
import json
from pathlib import Path

from .core import convert_strategy
from .mesh import load_mesh_resolver
from .parser import parse_strategy_text
from .rtf import parse_rtf_bytes


def _strategy_files(dataset_root: Path, pattern: str):
    for path in sorted(dataset_root.glob(pattern)):
        if path.is_file() and path.suffix.casefold() in {".rtf", ".txt"}:
            yield path


def build_cache(dataset_root: Path, output: Path, *, pattern: str = "**/*.rtf") -> dict:
    """Resolve controlled headings found in a private corpus using exact NLM lookup."""
    if not dataset_root.is_dir():
        raise ValueError(f"dataset_root_is_not_a_directory:{dataset_root}")
    resolver = load_mesh_resolver(output, online=True)
    files = 0
    failed_inputs: list[str] = []
    unresolved_headings: set[str] = set()
    for path in _strategy_files(dataset_root, pattern):
        files += 1
        try:
            data = path.read_bytes()
            strategy = (
                parse_rtf_bytes(data)
                if path.suffix.casefold() == ".rtf"
                else parse_strategy_text(data.decode("utf-8"))
            )
            if strategy.source_errors:
                failed_inputs.append(f"{path}:{','.join(strategy.source_errors)}")
                continue
            result = convert_strategy(strategy, mesh_resolver=resolver)
            unresolved_headings.update(
                event
                for event in result.audit_events
                if "mesh_resolution_fallback_to_source_heading:" in event
            )
        except (OSError, UnicodeError, ValueError) as exc:
            failed_inputs.append(f"{path}:{exc}")
    resolver.flush()
    return {
        "files_scanned": files,
        "resolved_records": len(resolver.records),
        "mesh_year": resolver.mesh_year,
        "failed_inputs": failed_inputs,
        "unresolved_headings": sorted(unresolved_headings),
        "output": str(output),
    }


def inspect_cache(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "schema_version": payload.get("schema_version"),
        "mesh_year": payload.get("mesh_year"),
        "generated_at_utc": payload.get("generated_at_utc"),
        "records": len(payload.get("records", {})),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build an exact NLM cache from corpus files")
    build.add_argument("--dataset-root", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    build.add_argument("--glob", default="**/*.rtf", dest="pattern")
    inspect = commands.add_parser("inspect", help="Display cache metadata")
    inspect.add_argument("cache", type=Path)
    args = parser.parse_args()

    if args.command == "build":
        report = build_cache(args.dataset_root, args.output, pattern=args.pattern)
    else:
        report = inspect_cache(args.cache)
    print(json.dumps(report, indent=2))
    return 2 if report.get("failed_inputs") or report.get("unresolved_headings") else 0


if __name__ == "__main__":
    raise SystemExit(main())

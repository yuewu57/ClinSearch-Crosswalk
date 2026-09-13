"""Convert one pasted-text or RTF strategy using the production core."""

import argparse
from pathlib import Path

from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.mesh import load_mesh_resolver
from ovid_pubmed_converter.outputs import audit_csv, converted_rtf, strategy_text, validation_report
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import parse_rtf_bytes


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ClinSearch-CrossWalk: a Clinical Search Convertor: Ovid MEDLINE to PubMed"
    )
    parser.add_argument("input", type=Path, help="Ovid strategy .txt or .rtf")
    parser.add_argument("--end-date")
    parser.add_argument("--output-prefix", type=Path)
    parser.add_argument("--mesh-cache", type=Path)
    parser.add_argument("--online-mesh", action="store_true")
    args = parser.parse_args()
    data = args.input.read_bytes()
    strategy = parse_rtf_bytes(data) if args.input.suffix.lower() == ".rtf" else parse_strategy_text(data.decode("utf-8"), end_date=args.end_date)
    resolver = load_mesh_resolver(args.mesh_cache, online=args.online_mesh)
    result = convert_strategy(strategy, mesh_resolver=resolver)
    prefix = args.output_prefix or args.input.with_suffix("")
    prefix.parent.mkdir(parents=True, exist_ok=True)
    prefix.with_suffix(".pubmed.txt").write_text(strategy_text(result), encoding="utf-8")
    prefix.with_suffix(".audit.csv").write_text(audit_csv(result), encoding="utf-8")
    prefix.with_suffix(".validation.json").write_text(validation_report(result), encoding="utf-8")
    if args.input.suffix.lower() == ".rtf":
        prefix.with_suffix(".pubmed.rtf").write_bytes(converted_rtf(result))
    resolver.flush()
    print(strategy_text(result), end="")
    print(f"Validation: {result.validation_status.value}")
    return 0 if result.validation_status.value == "ok" else 2


if __name__ == "__main__":
    raise SystemExit(main())

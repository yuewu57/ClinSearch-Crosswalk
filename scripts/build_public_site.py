"""Build the static landing page with an optional verified deployment URL."""

import argparse
import ast
import json
import os
import shutil
from pathlib import Path
from urllib.parse import urlsplit


def checked_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not (parsed.hostname or "").endswith(".streamlit.app")
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port not in (None, 443)
        or parsed.query or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise ValueError("APP_URL must be a bare HTTPS *.streamlit.app URL.")
    return value.rstrip("/") + "/"


def read_versions(source: Path) -> dict[str, str]:
    values = {}
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"__version__", "RULESET_VERSION"}:
                    values[target.id] = str(node.value.value)
    if set(values) != {"__version__", "RULESET_VERSION"}:
        raise ValueError("Could not read software and ruleset versions.")
    return values


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("_public_site"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if output.exists():
        raise ValueError("Output directory already exists; use a new empty destination.")
    url = checked_url(os.getenv("APP_URL", ""))
    versions = read_versions(root / "src/ovid_pubmed_converter/__init__.py")
    shutil.copytree(root / "site", output)
    config = {"converterUrl": url, "softwareVersion": versions["__version__"],
              "rulesetVersion": versions["RULESET_VERSION"]}
    (output / "config.js").write_text(
        "window.EVIDENTIA_SITE_CONFIG = " + json.dumps(config) + ";\n", encoding="utf-8"
    )
    (output / ".nojekyll").touch()
    print("Static site built; launch link configured." if url else
          "Static site built; launch link disabled until APP_URL is configured.")


if __name__ == "__main__":
    main()

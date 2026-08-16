# Selected v20 conversion fixtures

These are **starter conformance/regression fixtures** for the public
Ovid MEDLINE → PubMed converter.

## Authority

Expected outputs represent the approved **normative v20 rule specification**,
not merely whatever the current monolithic Python file happens to produce.

For Codex/refactoring work:

1. the v20 Markdown specification is normative;
2. `expected_pubmed.txt` is the exact expected semantic output for each fixture;
3. `fixture.json` contains required audit substrings and known current-reference status;
4. paste mode and RTF-upload mode must converge on the same conversion core.

## Fixture files

Each numbered folder normally contains:

- `input_strategy.txt` — direct paste-mode strategy;
- `input.rtf` — RTF upload-mode strategy;
- `input_options.json` — optional external metadata such as `end_date`;
- `expected_pubmed.txt` — expected converted strategy;
- `fixture.json` — machine-readable assertions;
- `mesh_records.json` — only where deterministic MeSH metadata are needed.

The `mesh_records.json` files contain **fixture-only stubs**. Synthetic
descriptor IDs/URIs are intentional. Production tests should separately test
the real cache/API integration.

## Known-fail fixtures

Two fixtures intentionally encode normative requirements that the current
v20-v2 maintenance implementation is still known not to satisfy fully:

- `10_unicode_rtf`: raw Windows-1252 RTF code-page decoding;
- `11_split_list_numbering`: split Word-list labels plus a year-leading
  physical continuation that must not become a spurious row.

Codex should not weaken those fixtures to make the old implementation pass.
The implementation should be corrected to satisfy the normative specification.

## Important limitation

These 15 fixtures are selected coverage, not a complete test suite. In
particular, further dedicated fixtures should later be added for:

- generic `.pt.` audit warning;
- protected-hyphen preservation when a verified canonical MeSH rename occurs;
- comments/corrections `.cm.`;
- unresolved MeSH safe fallback;
- invalid/cyclic line references;
- unused-line versus active-query validation;
- wildcard expansion-limit/manual-review behaviour.

## Real Cochrane fixture

`15_complex_real_cochrane` uses the preserved 20-line Ovid MEDLINE strategy
from Cochrane review **CD003594**. Its RTF container is reconstructed as a
minimal deterministic test file.

# Selected v20 conversion fixtures — v2

These are starter **conformance and regression fixtures** for the public
These fixtures validate **Evidentia Search Strategy Convertor** — **Ovid MEDLINE → PubMed**.

## Authority

Expected outputs represent the approved normative v20 rule specification,
rather than merely reproducing the current monolithic Python implementation.

Authority order for development:

1. normative v20 specification;
2. approved fixture expectations;
3. current Python reference implementation.

## Fixture list

| Fixture | Current v20-v2 reference result |
|---|---|
| 01 basic MeSH | PASS |
| 02 Boolean references | PASS |
| 03 adj3 | PASS |
| 04 question wildcard | PASS |
| 05 hash wildcard | PASS |
| 06 truncation | PASS |
| 07 short root | PASS |
| 08 RCT filter | PASS |
| 09 animal filter | PASS |
| 10 RTF code-page cp1252 | **KNOWN FAIL** |
| 11 split list numbering | PASS |
| 12 year-leading continuation | **KNOWN FAIL** |
| 13 historical MeSH | PASS |
| 14 pharmacological action | PASS |
| 15 end date | PASS |
| 16 complex real Cochrane strategy | PASS |

Thus the intended current baseline is **14/16 passing normative fixtures**,
with two isolated known conformance gaps.

## Files in each fixture

A fixture normally contains:

- `input_strategy.txt` — direct paste-mode input;
- `input.rtf` — equivalent or deliberately structured RTF-upload input;
- `input_options.json` — optional metadata such as `end_date`;
- `expected_pubmed.txt` — normative expected output;
- `fixture.json` — machine-readable assertions;
- `mesh_records.json` — deterministic fixture-only MeSH stub where required.

Fixture-only MeSH records use synthetic IDs/URIs intentionally. Production
MeSH cache/API integration must be tested separately.

## Important rule for Codex

Do not modify a normative expected result merely to make the old implementation
pass.

For fixtures 10 and 12, the implementation should be corrected.

## Additional tests still recommended

Add dedicated tests later for:

- generic `.pt.` audit warning;
- protected-hyphen preservation after verified canonical MeSH renaming;
- Comments/Corrections `.cm.`;
- unresolved MeSH fallback;
- cache-only behaviour;
- invalid/undefined/cyclic references;
- active final-query dependency validation;
- wildcard-expansion limit/manual review;
- malformed RTF;
- unused invalid rows versus active invalid rows.

## Real Cochrane fixture

`16_complex_real_cochrane` preserves the 20-line Ovid MEDLINE strategy used for
CD003594. Its RTF container is reconstructed as a minimal deterministic test
wrapper rather than asserted to be byte-identical to the original source file.

# Codex integration note — fixture suite v2

Copy the `tests/` directory into the repository root.

The eventual automated harness should:

1. discover fixture folders through `tests/fixtures/manifest.json`;
2. load `fixture.json`;
3. run `input_strategy.txt` through paste-mode parsing;
4. run `input.rtf` through RTF parsing;
5. apply `input_options.json`;
6. inject `mesh_records.json` as deterministic test MeSH metadata where present;
7. assert both input modes produce `expected_pubmed.txt`;
8. assert `expected_validation_status`;
9. assert each `required_audit_substrings` value is present somewhere in audit;
10. assert forbidden output/audit substrings are absent.

Semantic output should be exact unless the normative specification is
deliberately versioned.

Current expected reference baseline:

- 14/16 fixtures pass;
- `10_rtf_codepage_cp1252` is an intentional KNOWN_FAIL;
- `12_year_leading_continuation` is an intentional KNOWN_FAIL.

`11_split_list_numbering` is intentionally separated from the year-leading
continuation defect and should pass.

Do not weaken fixtures 10 or 12 to make the old implementation pass. Correct
the implementation to satisfy normative v20.

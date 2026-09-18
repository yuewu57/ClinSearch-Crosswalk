# Development integration note — regression fixtures

The automated harness must:

1. discover fixture folders under `tests/fixtures/`;
2. load each fixture definition and input options;
3. run the paste-mode strategy through the shared parser and converter;
4. run the corresponding RTF through the deterministic RTF parser and the same converter;
5. inject fixture-only deterministic MeSH metadata where present;
6. require paste and RTF modes to produce the same approved expected PubMed strategy;
7. assert the expected validation status;
8. assert all required audit substrings;
9. assert forbidden output/audit substrings are absent;
10. run the targeted conformance suite in addition to the fixture regression suite.

All currently maintained numbered fixtures are expected to pass. Historical known-fail notes for RTF code-page handling and year-leading continuations are obsolete because those implementation gaps have been corrected and are now regression-covered.

Do not weaken a fixture to accommodate an implementation change. When a semantic change is intended, version the normative specification/ruleset first, then update the executable and regression oracle with an explicit rationale.

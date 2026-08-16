# 10_rtf_codepage_cp1252

**Purpose:** Normative RTF ANSI code-page handling.

This fixture contains an RTF document declaring `\ansicpg1252` and a genuine
raw Windows-1252 en-dash byte (`0x96`). Normative v20 behaviour is to decode
the RTF using its declared code page and then normalise the punctuation.

Files:

- `input_strategy.txt` — semantic paste-mode equivalent.
- `input.rtf` — raw Windows-1252 RTF upload input.
- `input_options.json` — options.
- `expected_pubmed.txt` — normative expected PubMed output.
- `fixture.json` — assertions and known-current-reference status.

**Current reference implementation:** KNOWN_FAIL.

Do not rewrite this fixture into UTF-8 merely to make the old implementation
pass. Fix the RTF decoder.

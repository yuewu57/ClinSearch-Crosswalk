# 10_unicode_rtf

**Purpose:** Normative RTF code-page handling: decode raw Windows-1252 correctly, then normalise Unicode punctuation.

Files:

- `input_strategy.txt` — direct-paste input.
- `input.rtf` — equivalent RTF-upload input.
- `input_options.json` — options/metadata supplied separately in paste mode.
- `expected_pubmed.txt` — normative v20 expected strategy.
- `fixture.json` — assertions and current-reference status.

**Current reference implementation:** KNOWN_FAIL. The corrected v20-v2 maintenance file still inherits the documented UTF-8-strict RTF reader and is expected to fail on this raw cp1252 byte. Codex should make this fixture pass when implementing normative Section 3.1.

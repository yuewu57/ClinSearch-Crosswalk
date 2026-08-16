# 11_split_list_numbering

**Purpose:** Preserve Word list numbering when labels and expressions are split; protect a year-leading continuation from becoming a spurious row.

Files:

- `input_strategy.txt` — direct-paste input.
- `input.rtf` — equivalent RTF-upload input.
- `input_options.json` — options/metadata supplied separately in paste mode.
- `expected_pubmed.txt` — normative v20 expected strategy.
- `fixture.json` — assertions and current-reference status.
- `mesh_records.json` — deterministic fixture-only MeSH stub.

**Current reference implementation:** KNOWN_FAIL. Split list labels themselves are supported, but the normative v20 year-leading continuation protection is documented as absent in the current executable. The physical continuation beginning '2020 ' must remain part of strategy row 2.

# 15_complex_real_cochrane

**Purpose:** End-to-end real Cochrane strategy combining MeSH, historical aliasing, free text, truncation, RCT filters, animal exclusion and line references.

Files:

- `input_strategy.txt` — direct-paste input.
- `input.rtf` — equivalent RTF-upload input.
- `input_options.json` — options/metadata supplied separately in paste mode.
- `expected_pubmed.txt` — normative v20 expected strategy.
- `fixture.json` — assertions and current-reference status.
- `mesh_records.json` — deterministic fixture-only MeSH stub.

**Source note:** Real Ovid MEDLINE strategy content from Cochrane review CD003594 (Interventions for idiopathic steroid-resistant nephrotic syndrome in children), 20 preserved numbered lines. The RTF container in this fixture is reconstructed for deterministic testing rather than copied as the original Word RTF binary.

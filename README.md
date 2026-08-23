# Evidentia-CSC: a Clinical Search Convertor

**Ovid MEDLINE → PubMed**

Part of Evidentia

A deterministic, rule-based, recall-oriented converter implementing the approved v21 rules. It translates Ovid MEDLINE syntax into PubMed syntax with line-by-line audit and local validation. It is independent of generative AI and is not affiliated with or endorsed by Cochrane, Ovid, or the U.S. National Library of Medicine (NLM).

## Purpose and features

- Paste an Ovid MEDLINE strategy or upload one RTF file.
- One shared Python conversion core for web, CLI, paste, RTF, and future benchmarks.
- Exact cache-first MeSH resolution, optional exact online lookup, and executable source-heading fallback with an audit warning.
- Structured validation, active-query dependency analysis, and TXT/CSV/JSON/RTF downloads.
- A copy-ready **one-line PubMed query** is produced by recursively expanding the validated final row; the numbered PubMed strategy is retained separately for audit and troubleshooting.
- v21 support for Ovid `/freq=N`, ignored `limit N to ...` rows with reference-safe renumbering, automatic removal of pure numeric Ovid database-update date rows, and PubMed-safe wildcard phrases.
- No accounts, database, or persistent upload storage.

Exact retrieval equivalence cannot always be guaranteed. In particular, Ovid adjacency is approximated as PubMed `AND`, Ovid `.ab.` maps to PubMed `[tiab]`, `/freq>1`, ignored LIMIT conditions, and omitted database-update date restrictions can broaden retrieval, and unresolved MeSH headings can use the documented source-heading fallback. A `validation_failed` or `manual_review_required` result requires attention and is not a validated query.

## Supported input modes

### Paste strategy

Open the default **Paste strategy** tab, enter rows such as `1 exp Asthma/`, and select **Convert**. Common `1`, `1.`, and `1)` row labels are accepted. If a pasted strategy contains no row labels, each non-empty pasted line is treated as one logical strategy row and numbered sequentially; users should therefore place exactly one logical Ovid row on each pasted line.

The online interface has **no end-date field**. Under v21, a pure numeric database-update row using `.ed.`, `.dt.`, `.ed,dt.` or `.dt,ed.` is discarded automatically and recorded in the line-by-line audit. No publication-date restriction is added to the PubMed query. The CLI `--end-date` option remains available only for automated or legacy workflows that need to preserve external metadata handling.

### RTF upload

Open **Upload RTF**, select one `.rtf` file no larger than 2 MB, and convert. A numbered Ovid RTF is preferred. The document may either contain an explicit `Medline:` block or consist entirely of one unambiguous, increasing numbered Ovid MEDLINE strategy. Do not include cover text around a standalone strategy; use the explicit `Medline:` heading when the document contains other material.

If an explicit `Medline:` block has no visible line numbers, the online RTF adapter reconstructs `1, 2, 3, ...` by extracted paragraph order only when every paragraph can be conservatively identified as a complete Ovid search row. The recovery is surfaced as a warning for user verification. Ambiguous unnumbered RTF content is rejected rather than guessed, and a standalone RTF without a `Medline:` heading still requires reliable numbering.

The byte-first parser handles declared ANSI code pages, RTF Unicode controls, ignorable destinations, and Word list labels before using the same parser and core as paste mode.

A minimal example RTF is downloadable in the upload tab. It contains only the `Medline:` heading and three example numbered rows; `Title`, `End_date`, PICO, and other metadata are not required.

## Web output

For a validated conversion, the web page shows two complementary PubMed representations:

1. **One-line PubMed query** — the primary copy-ready query. Starting from the selected final PubMed row, Evidentia recursively substitutes every referenced `#N` row and parenthesizes each substitution to preserve Boolean precedence. Only the final row's dependency closure is expanded; unused rows are not appended to the executable query.
2. **Numbered PubMed strategy** — retained for audit, comparison, and troubleshooting. It may contain local `#N` references because it represents the conversion row by row.

The one-line query is produced only for a conversion with `ok` validation status and is locally validated again with line references disallowed. The online converter does not ask for external end-date metadata and does not add a publication-date restriction when it removes an Ovid database-update date row.

## Installation and running locally

### Linux/macOS

```bash
git clone <repository-url>
cd Evidentia-convertor
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run web/app.py
```

### Windows PowerShell

```powershell
git clone <repository-url>
cd Evidentia-convertor
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
streamlit run web/app.py
```

The application is normally available at <http://localhost:8501>.

## Command-line use

```bash
python cli/batch_convert.py strategy.txt --end-date 31-12-2025
python cli/batch_convert.py strategy.rtf --mesh-cache resources/mesh_resolution_cache_v20_v1.json
python cli/batch_convert.py strategy.rtf --mesh-cache cache.json --online-mesh
```

The command writes PubMed text, audit CSV, validation JSON, and (for RTF input) converted RTF. A non-OK validation exits with status 2. Cache-only mode is the default and remains suitable for frozen benchmark runs. v21 does not change MeSH semantics, so the maintained v20-labelled cache remains compatible.

## Development, tests, and quality

```bash
python -m pip install -r requirements-dev.txt
pytest
ruff check .
pytest --cov=ovid_pubmed_converter --cov-report=term-missing && ruff check .
```

PowerShell full-quality command:

```powershell
pytest --cov=ovid_pubmed_converter --cov-report=term-missing; if ($LASTEXITCODE -eq 0) { ruff check . }
```

Regression tests use deterministic fixture records and do not require live NLM availability.

## MeSH and cache behavior

Resolution is exact only: preferred labels, exact entry terms, and reviewed historical aliases. There is no fuzzy matching. Successful optional online resolutions may be written to a versioned JSON cache. Cache misses or NLM service failures retain an executable quoted source heading with `[mh]` and add an audit warning. Only heading labels needed for exact online resolution are transmitted to NLM; complete user strategies are not transmitted.

Fixture `mesh_records.json` files contain synthetic identifiers for tests and must never be copied into production resources.

## Validation and limitations

Validation checks syntax, PubMed tags, source rows, references, cycles, and the active final-query dependency closure. Problematic unused rows remain auditable. Unsupported syntax, bounded wildcard limits, approximation flags, and unresolved cases may require manual review.

For v21, a valid whole-row `limit N to ...` is intentionally reduced to its underlying row `N`; downstream references are redirected and surviving output rows are renumbered when LIMIT removal occurs. A final LIMIT row preserves its resolved base as the effective final query, using an audited synthetic final alias when required. Valid `/freq=N` is removed; `freq=1` is redundant and `freq>1` is explicitly audited as recall broadening. Pure numeric Ovid database-update rows using `.ed.`, `.dt.`, `.ed,dt.` or `.dt,ed.` are discarded automatically. Safe quoted wildcard phrases are rendered using PubMed's phrase-level field-tag form rather than automatically splitting the words with Boolean `AND`.

The one-line query resolver does not alter these v21 conversion semantics. It operates only after conversion and validation, recursively expands the final dependency graph, preserves Boolean grouping with parentheses, and rejects unresolved/cyclic line references rather than guessing.

This software does not test live PubMed retrieval equivalence. Users remain responsible for peer review and retrieval testing of translated strategies.

## Deployment

1. Push this repository to GitHub.
2. In Streamlit Community Cloud select **Create app**.
3. Choose the repository and branch.
4. Set the entry point to `web/app.py`.
5. Deploy; no secrets or system packages are required for cache-only operation.
6. Confirm the platform uses Python 3.12 and exercise both fixture-equivalent input modes.

Optional live MeSH calls require outbound access but no repository secret. Do not configure arbitrary upload or cache filesystem paths in the web UI.

## Privacy and security

Uploads are accepted as bytes, signature-checked, size-limited, processed in a controlled temporary directory, and not intentionally retained. The app has no database and does not log complete strategies. Uploaded filenames are never interpreted as server paths, and uploaded content is never executed.

## Citation, licence, and version

See [`CITATION.cff`](CITATION.cff). Project code is Apache-2.0; MeSH terminology remains subject to NLM terms and is not relicensed by this project. See [`NOTICE`](NOTICE).

Software version: **0.1.2**. Conversion ruleset: **v21**. The v21 label identifies the conversion semantics, not the product name.

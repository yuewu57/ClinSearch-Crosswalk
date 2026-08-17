# Ovid MEDLINE → PubMed Search Strategy Converter

A deterministic, rule-based, recall-oriented converter implementing the approved v20 rules. It translates Ovid MEDLINE syntax into PubMed syntax with line-by-line audit and local validation. It is independent of generative AI and is not affiliated with or endorsed by Cochrane, Ovid, or the U.S. National Library of Medicine (NLM).

## Purpose and features

- Paste a numbered Ovid MEDLINE strategy or upload one RTF file.
- One shared Python conversion core for web, CLI, paste, RTF, and future benchmarks.
- Exact cache-first MeSH resolution, optional exact online lookup, and executable source-heading fallback with an audit warning.
- Structured validation, active-query dependency analysis, and TXT/CSV/JSON/RTF downloads.
- No accounts, database, or persistent upload storage.

Exact retrieval equivalence cannot always be guaranteed. In particular, Ovid adjacency is approximated as PubMed `AND`, Ovid `.ab.` maps to PubMed `[tiab]`, and unresolved MeSH headings can use the documented source-heading fallback. A `validation_failed` or `manual_review_required` result requires attention and is not a validated query.

## Supported input modes

### Paste strategy

Open the default **Paste strategy** tab, enter rows such as `1 exp Asthma/`, optionally enter an End date, and select **Convert pasted strategy**. Common `1`, `1.`, and `1)` row labels are accepted; a single unnumbered expression is assigned row 1.

### RTF upload

Open **Upload RTF**, select one `.rtf` file no larger than 2 MB, and convert. The document must contain a `Medline:` block. The byte-first parser handles declared ANSI code pages, RTF Unicode controls, ignorable destinations, and Word list labels before using the same parser and core as paste mode.

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

The command writes PubMed text, audit CSV, validation JSON, and (for RTF input) converted RTF. A non-OK validation exits with status 2. Cache-only mode is the default and remains suitable for frozen benchmark runs.

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

Converter version: **v20 / 20.0.0**. A suitable first public tag after deployment acceptance is `v20.0.0`.

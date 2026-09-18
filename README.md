# ClinSearch-CrossWalk

**Deterministic, recall-oriented Ovid MEDLINE → PubMed search-strategy translation with validation and line-level audit.**

ClinSearch-CrossWalk implements the approved **v21** conversion semantics. The reference converter is Python. The release-candidate browser application runs that same Python reference engine locally in the browser through Pyodide/WebAssembly behind a TypeScript interface; it is **not** a separate TypeScript reimplementation and does not require a conversion server.

> **Release-candidate status.** The public browser interface is not yet declared a final research release. Release is gated on a populated, provenance-checked MeSH cache, representative real-corpus acceptance checks, passing CI on the frozen commit, licensing/release approval, and archival metadata. See [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

## Associated manuscript

**ClinSearch-Crosswalk: a recall-oriented, auditable clinical search translation framework for Ovid MEDLINE-to-PubMed conversion**

Danqi Zhuang¹ · Fang Qi² · Xiaoyue Xi³ · Chris Robertson¹˒⁴ · Martin Halvey⁵ · Yue Wu¹˒⁶

1. Department of Mathematics and Statistics, University of Strathclyde, Glasgow, UK
2. Independent Researcher, Tianjin, China
3. Department of Medical Statistics, London School of Hygiene & Tropical Medicine, London, UK
4. Public Health Scotland, Glasgow, UK
5. Department of Computer and Information Sciences, University of Strathclyde, Glasgow, UK
6. Corresponding author: yue.wu@strath.ac.uk

Manuscript authorship and software/IP ownership are separate matters. The final paper link and archival identifier will be added only when established.

## What the software does

- Accepts pasted Ovid MEDLINE strategies and RTF input.
- Converts line by line using deterministic v21 rules.
- Preserves a numbered PubMed strategy for audit.
- Produces a copy-ready one-line PubMed query only when the active final query validates.
- Records approximations, fallbacks, omissions and manual-review conditions.
- Performs dependency-aware validation so unused malformed rows remain auditable without automatically invalidating an otherwise valid active final query.
- Uses exact, cache-first MeSH resolution only; no fuzzy or nearest-term mapping is used.
- Supports CLI, Python API and local Streamlit adapters over the same conversion core.
- Provides a static browser application that executes the unchanged reference Python engine locally through WebAssembly.

The software is independent of generative AI and is not affiliated with or endorsed by Cochrane, Ovid, or the U.S. National Library of Medicine (NLM).

## Ruleset and reference implementation

The normative conversion definition is the maintained **v20 base specification plus the approved v21 delta**:

- [v20 base specification](docs/cochrane_ovid_pubmed_conversion_rules_v20.md)
- [v21 delta](docs/cochrane_ovid_pubmed_conversion_rules_v21.md)

The Python package under `src/ovid_pubmed_converter/` is the reference executable implementation. The browser build pins and hashes the reference Python modules so conversion-rule changes cannot be introduced silently during packaging.

The software version and conversion ruleset version are intentionally separate. Current development metadata:

- Software: **0.1.2**
- Conversion ruleset: **v21**

A release version will be assigned only when the research release is frozen.

## Input

### Pasted strategy

Numbered rows such as:

```text
1 exp Asthma/
2 wheez*.tw.
3 1 or 2
```

are preferred. Common `1`, `1.` and `1)` labels are accepted. If pasted text has no row labels, each non-empty physical line is treated as one logical row.

### RTF

The RTF parser accepts an explicit `Medline:` block or an otherwise unambiguous numbered Ovid strategy. Metadata before a `Medline:` block may remain in the source document. The byte-first parser handles declared ANSI code pages, RTF Unicode controls, ignorable destinations and Word list numbering before applying the same row parser used by pasted input.

Pure Ovid database-update rows using `.ed.`, `.dt.`, `.ed,dt.` or `.dt,ed.` are handled under v21 and audited.

## Output and retrieval gate

For a successful conversion, ClinSearch-CrossWalk returns:

1. **One-line PubMed query** — recursively expands the validated final dependency closure and contains no local `#N` references.
2. **Numbered PubMed strategy** — preserves row-level structure for audit and troubleshooting.
3. **Validation status and warnings**.
4. **Line-level audit information**.
5. **Downloadable structured results** where supported by the adapter.

A one-line executable query is not exposed as validated output when the conversion status is `validation_failed` or `manual_review_required`.

## MeSH terminology

Resolution is deliberately exact only: preferred labels, exact entry terms and reviewed historical aliases. Successful mappings record canonical label, descriptor ID/URI, descriptor class, match type, MeSH year and pharmacological-action status.

The repository's `resources/mesh_resolution_cache_v20_v1.json` is an **empty development starter cache**, not the final terminology bundle. A public research release must use a populated dated cache that passes:

```bash
python scripts/validate_mesh_cache_release.py path/to/cache.json
```

See [MeSH cache provenance](docs/mesh_cache_provenance_v1_YW_18092026.md). Synthetic fixture terminology must never be promoted to production resources.

## Browser release candidate

Requirements: Node 22.12+ and the Python development environment.

```bash
python -m pip install -r requirements-dev.txt
cd browser
npm ci
npm run build
node scripts/serve-preview.mjs
```

Then open `http://127.0.0.1:4173`.

The browser application is static after build. Python, Pyodide and the selected terminology cache are self-hosted assets. Search strategies are converted in the browser; there is no conversion API, account system or database.

See:

- [Browser architecture decision](docs/browser_runtime_decision_v1_YW_18092026.md)
- [Browser deployment](docs/browser_deployment_v1_YW_18092026.md)
- [Release checklist](RELEASE_CHECKLIST.md)

## Python reference application

From the repository root:

```bash
python -m pip install -r requirements.txt
python -m streamlit run web/app.py
```

The Streamlit adapter remains useful for local/reference testing. It is not the planned public production architecture for the browser release candidate.

## Command line

```bash
python cli/batch_convert.py strategy.txt
python cli/batch_convert.py strategy.rtf --mesh-cache resources/mesh_resolution_cache_v20_v1.json
python cli/batch_convert.py strategy.rtf --mesh-cache cache.json --online-mesh
```

Cache-only mode is preferred for frozen/reproducible evaluation.

## Tests

```bash
python -m pip install -r requirements-dev.txt
pytest
ruff check .
cd browser
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The native/browser parity suite compares structured conversion results, final queries, audit fields and exports on deterministic fixtures. Passing tests establish conformance on tested cases; they do not prove universal Ovid/PubMed retrieval equivalence.

## Important limitations

Exact retrieval equivalence cannot always be guaranteed. Examples include:

- Ovid adjacency approximated using PubMed Boolean conjunction.
- Ovid `.ab.` mapped to PubMed `[tiab]`.
- valid `/freq>1` removed with explicit recall-broadening audit.
- Ovid LIMIT conditions ignored under the approved v21 policy, with safe reference handling.
- pure database-update restrictions removed under the approved v21 policy.
- unresolved MeSH headings falling back to an executable source-heading `[mh]` representation.

The software does not establish clinical relevance of retrieved records. Peer review and retrieval testing remain necessary for evidence-synthesis use.

## Privacy and security

The browser release performs conversion locally in the user's browser. There are no accounts, analytics, persistent strategy uploads or external conversion calls. Initial page/runtime loading still requires ordinary network access to the chosen static host, which may record standard asset/page requests.

Only exact heading labels are sent to NLM when the optional Python online-MeSH mode is deliberately enabled. Complete strategies are not sent for terminology lookup.

Do not enter patient, personal or confidential information.

## Citation and licence

See [CITATION.cff](CITATION.cff), [LICENSE](LICENSE), [NOTICE](NOTICE) and [licensing notes](docs/licensing.md).

The current source is available under the **PolyForm Noncommercial License 1.0.0**. This is source-available software, not OSI-approved open-source software. MeSH terminology and third-party materials remain subject to their own terms.

The exact tested commit, terminology-cache hash, release date, software tag and immutable archive/DOI will be recorded when the release candidate is frozen.

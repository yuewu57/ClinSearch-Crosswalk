# ClinSearch-Crosswalk browser preview

This development branch provides a TypeScript interface and worker around the **unchanged Python reference engine running locally through Pyodide/WebAssembly**. It is not an independent TypeScript rewrite. There is no conversion server and no live MeSH call.

## Run locally

Use Node 22.12 or later and the existing Python development environment. From the repository root:

```powershell
python -m pip install -r requirements-dev.txt
cd browser
npm ci
npm run dev
```

Open the local address printed by Vite (normally http://127.0.0.1:5173). First use loads the self-hosted runtime, about 12 MiB uncompressed. Loading is not instant; progress, cancellation and initialization timeout are provided.

To test a built static site with production security headers:

```powershell
npm run build
node scripts/serve-preview.mjs
```

Open http://127.0.0.1:4173. Do not double-click dist/index.html: workers, WebAssembly and integrity checks require HTTP(S); localhost is supported for development.

## Verify

```powershell
# Repository root; existing Python environment
python -m pytest -q
ruff check .
cd browser
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The parity tests generate native expected values independently from the Python public API for 88 cases, including existing fixtures in paste and RTF modes. They compare all structured results, final queries, audit fields and rendered exports with WebAssembly outputs, repeating each case. Additional tests cover integrity, resource limits and data/code separation. These tests demonstrate parity on tested cases, not universal correctness or live PubMed retrieval equivalence. CI reports are the pass/fail evidence for each commit.

## Reference and build integrity

Reference commit: `8ca2ca49984d13e466ae12332964f3131e49ee64`. Build-time hashes prevent silent edits to reference modules. The generated runtime manifest records source, bridge, cache and runtime provenance. Python modules are copied without conversion-rule edits. User search text is passed as JSON data, never evaluated as Python.

## Terminology cache

The repository currently contains an **empty production starter cache**. The preview reports this and uses audited source-heading fallback. It does not fabricate metadata or copy synthetic fixtures into production. Verified canonicalisation and pharmacological-action expansion require the same populated, frozen MeSH cache used by the reference run. Empty-cache behaviour is not equivalent to an online-enriched Streamlit session.

A maintainer may supply a reviewed dated cache under `resources/` using the existing naming convention, or set `MESH_CACHE_PATH` relative to the repository root at build time. The app never accepts arbitrary filesystem paths. Test caches stay in `parity/`, not production assets. Structural checks rejecting fixture IDs and malformed records are not proof of metadata authenticity.

## Features and limits

Paste/RTF input; final query; numbered strategy; original-row audit; JSON report; CSV export. Copy and query download are disabled after failure, cancellation or input edits. There are no accounts, analytics, persistent uploads or external conversion calls.

Adapter limits: 2 MiB input, 1,000 reconstructed rows, nesting/dependency depth 100, 30-second conversion timeout and bounded final-query expansion. These are explicit browser resource limits, not conversion-rule changes.

## Release boundary

Development preview only. Do not merge or publicly deploy without reviewing the runtime decision, production cache, real-corpus acceptance results and release/licensing approvals. See `../docs/browser_runtime_decision_v1_YW_18092026.md` and `../docs/browser_deployment_v1_YW_18092026.md`.

The PolyForm Noncommercial licence is unchanged. This work does not change repository visibility, branding rights or attribution.

# ClinSearch-CrossWalk browser release candidate

This branch provides a TypeScript interface and Web Worker around the **unchanged Python reference engine running locally through Pyodide/WebAssembly**. It is not an independent TypeScript rewrite. There is no conversion server and no live MeSH call.

## Run locally

Use Node 22.12 or later and the existing Python development environment. From the repository root:

```powershell
python -m pip install -r requirements-dev.txt
cd browser
npm ci
npm run dev
```

Open the address printed by Vite (normally `http://127.0.0.1:5173`).

To test the production build:

```powershell
npm run build
node scripts/serve-preview.mjs
```

Open `http://127.0.0.1:4173`. Do not double-click `dist/index.html`: workers, WebAssembly and integrity checks require HTTP(S).

## Verify

```powershell
# repository root
python -m pytest -q
ruff check .
cd browser
npm ci
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Native/WebAssembly parity tests compare structured results, final queries, audit fields and rendered exports across deterministic fixture cases, including repeated execution. These tests demonstrate parity on covered cases, not universal correctness or live PubMed retrieval equivalence.

## Reference and build integrity

Reference commit: `8ca2ca49984d13e466ae12332964f3131e49ee64`.

Build-time hashes prevent silent edits to pinned reference modules. The generated runtime manifest records source, bridge, cache and runtime provenance. User search text is passed as JSON data, never evaluated as Python.

## Terminology cache

The repository currently contains an **empty production starter cache**. It is acceptable for development fallback testing but is not the final release terminology bundle.

A release-grade cache must be populated, frozen and provenance-checked:

```powershell
python scripts/validate_mesh_cache_release.py path\to\cache.json
```

See `../docs/mesh_cache_provenance_v1_YW_18092026.md`. The browser build rejects malformed/synthetic production records but structural validation alone is not proof of metadata authenticity.

## Features and limits

Paste/RTF input; final query; numbered strategy; original-row audit; JSON report; CSV export. Copy and query download are disabled after failure, cancellation or input edits. There are no accounts, analytics, persistent uploads or external conversion calls.

Adapter limits: 2 MiB input, 1,000 reconstructed rows, nesting/dependency depth 100, 30-second conversion timeout and bounded final-query expansion. These are browser resource limits, not conversion-rule changes.

## Release gate

Do not declare the browser build a final public research release until the populated cache, representative real-corpus acceptance set, CI evidence, licensing review and release metadata are complete. See `../RELEASE_CHECKLIST.md` and `../docs/browser_deployment_v1_YW_18092026.md`.

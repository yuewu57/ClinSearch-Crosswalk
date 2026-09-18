# Browser implementation plan

## 18 September refinement — review before merge

The functional preview now uses a TypeScript interface/worker with the unchanged Python engine in Pyodide/WebAssembly. The initial independent TypeScript rewrite is deferred. This reaches the browser-only static-hosting goal with one maintained engine; it has a larger initial runtime download. See `browser_runtime_decision_v1_YW_18092026.md` for trade-offs and approval boundaries.

## Phase 0 — freeze the reference

Baseline `main` commit: `8ca2ca49984d13e466ae12332964f3131e49ee64`. Verify Python tests, module hashes, fixture outputs, audit statuses and final query. No conversion semantics are changed by browser work.

## Phase 1 — local runtime

Copy unchanged modules into a self-hosted, version-pinned WebAssembly runtime; isolate requests in a worker; allow cache-only terminology; add explicit input/time/expansion limits.

## Phase 2 — parity

Compare native Python public API outputs against browser-runtime outputs with identical inputs and cache records. Include rows, all status/audit fields, final query and rendered exports. Repeat conversions. Synthetic fixture metadata must never be bundled for production.

## Phase 3 — interface

Paste and RTF; query, numbered strategy, audit, provenance and failure gate. Clear stale output on changes, failures and cancellation. Test built security headers, network isolation, downloads and mobile layout.

## Phase 4 — release approval

Bundle the frozen production cache; complete real-corpus acceptance checks and owner review; then prepare static hosting. Do not merge or publish automatically. Main, existing Streamlit, licence and repository visibility are unchanged.

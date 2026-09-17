# Browser port plan

This branch ports the validated ClinSearch-Crosswalk conversion behaviour to a browser-side TypeScript implementation without changing the Python reference implementation on `main`.

## Phase 0 — freeze the Python reference behaviour

- identify the current authoritative Python entry points and v21 conversion layer;
- inventory regression fixtures and tests;
- define parity fixtures as input, expected translated rows, warnings/audit flags, validation status, and final executable query;
- record the source commit used as the browser-port baseline.

## Phase 1 — TypeScript conversion core

Port deterministic conversion logic in rule-priority order. Keep parsing, semantic conversion, validation, and rendering separate.

## Phase 2 — Python ↔ TypeScript parity

Run identical frozen fixtures against both implementations. Treat differences in translated rows, status, dependency structure, or material audit flags as failures unless explicitly approved.

## Phase 3 — browser UI

Provide paste and RTF input, converted PubMed strategy, audit, validation status, and copy-ready final query. Non-OK results must remain visibly gated.

## Phase 4 — static deployment

Build a browser-only production bundle suitable for Cloudflare Pages. Use a bundled frozen MeSH cache first; unresolved headings follow the approved safe fallback policy. Optional live terminology enrichment, if added later, must not alter the deterministic core.

## Baseline

Browser-port baseline commit on `main`: `8ca2ca49984d13e466ae12332964f3131e49ee64`.

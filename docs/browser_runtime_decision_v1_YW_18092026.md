# Browser runtime decision — review before merging

## Goal and refinement

Provide a free-to-access static converter without an always-on Python server while preserving the existing query/audit behaviour. The original plan was an independent TypeScript port. This preview instead uses TypeScript for UI, integrity checks and worker messages, and the unchanged Python source in Pyodide/WebAssembly for conversion. It must not be described as an independent TypeScript engine or as newly validated by the manuscript's retrieval benchmark.

One engine avoids duplicating Python regex semantics, RTF parsing, rule priority, terminology policies and dependency validation. No reference module is edited. A native TypeScript port remains possible later but is unnecessary for static hosting.

## Trade-offs

The initial static runtime download is larger and slower than a JavaScript-only application. Device memory and input limits still apply. A worker keeps the UI responsive and can be terminated; this does not guarantee unlimited input, zero downtime or instantaneous loading.

The browser profile is cache-only. Parity uses identical cache records/configuration in native Python and WebAssembly. It is not equivalent to online-enriched Streamlit with another cache. The empty production starter cache remains empty; synthetic test caches never enter deployment assets.

## Evidence

Python reference: `8ca2ca49984d13e466ae12332964f3131e49ee64`. The manifest freezes LF-normalised hashes of every module. Expected outputs come independently from the native Python public API, not the browser bridge. Comparisons include all rows, final query, statuses, errors, warnings, audit events and output renderings.

Browser end-to-end tests run the built static site with intended security headers and cover paste/RTF, gating, stale output, cancellation, network activity, markup safety, downloads and mobile layout. CI results, not this note, establish pass/fail for a specific commit.

## Approval boundaries

Work remains on `feature/browser-typescript-v1`. Do not auto-merge, change visibility/licensing, or deploy production. Obtain owner review of this runtime refinement before release. Client-side source/runtime assets are delivered to visitors even when the GitHub repository is private.

## Technical sources

https://pyodide.org/en/0.29.2/usage/working-with-bundlers.html
https://pyodide.org/en/0.29.2/usage/webworker.html
https://developers.cloudflare.com/pages/platform/limits/

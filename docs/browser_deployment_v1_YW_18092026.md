# Static browser deployment — not performed by this change

The build output is `browser/dist/`. No conversion backend, API key, database or Streamlit process is needed. Python, Pyodide and the chosen cache are self-hosted assets, not fetched from a third-party CDN at runtime.

## Public-release gates

1. Review the runtime decision and release/licensing approvals.
2. Bundle the frozen production MeSH cache and verify provenance/year.
3. Pass native tests, native/WebAssembly parity and browser end-to-end tests.
4. Check representative real benchmark strategies with the same cache as the paper. Software-fixture parity is not a new retrieval benchmark.
5. Record the tested commit, runtime and source/cache hashes.
6. Only after approval remove development/noindex notices and publish a tagged release.

## Cloudflare Pages settings

Use a separate preview project or reviewed branch, not an existing production site.

- Root: repository root (the build needs `src/` and `resources/`).
- Build: `cd browser && npm ci && npm run build`.
- Output: `browser/dist`.
- Node: at least 22.12, matching the CI major version.

The built `_headers` sets CSP and browser security headers. The WebAssembly asset is below the current 25 MiB per-file Pages limit. Check the preview URL, MIME types and headers before assigning a domain.

Account/repository authorization and domain configuration require the owner. This change makes no deployment. Do not put access tokens in repository files or chat.

The site has no analytics or strategy uploads to a conversion server; the host can still log ordinary asset/page requests. Clear terminates the worker, not a guarantee of forensic memory erasure. Initial loading requires connectivity; offline reload is not promised because no service worker is installed.

Official setup: https://developers.cloudflare.com/pages/framework-guides/deploy-anything/

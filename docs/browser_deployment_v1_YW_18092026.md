# GitHub Pages deployment — ClinSearch-CrossWalk

The public browser application is designed to run entirely as a static GitHub Pages site. The deployable output is `browser/dist/`. No conversion backend, API key, database or Streamlit process is required. Python, Pyodide and the frozen MeSH cache are packaged as first-party static assets and the conversion itself runs locally in the visitor's browser.

The expected project URL after publication is:

```text
https://yuewu57.github.io/ClinSearch-Crosswalk/
```

This URL should be treated as provisional until GitHub reports a successful Pages deployment.

## Deployment architecture

```text
GitHub Pages
    ↓
browser/dist
    ↓
TypeScript UI + Web Worker
    ↓
Pyodide / WebAssembly
    ↓
pinned Python reference converter
    ↓
frozen MeSH 2026 cache
```

The source strategy is not sent to a conversion server. GitHub may still receive ordinary requests for the page and static assets and may retain provider-level request logs.

## Release workflow

The repository contains `.github/workflows/pages.yml`.

After this release-candidate branch is reviewed and merged to `main`, the workflow:

1. validates the populated release-candidate MeSH cache;
2. runs Python regression/conformance tests and Ruff;
3. verifies the native browser parity manifest;
4. runs browser tests;
5. builds `browser/dist/`;
6. uploads that directory as the GitHub Pages artifact;
7. deploys the artifact to the `github-pages` environment.

The workflow also supports manual dispatch once it exists on the default branch.

## One-time owner setting

Before the first production deployment, open:

```text
Repository → Settings → Pages → Build and deployment → Source
```

and select:

```text
GitHub Actions
```

No Cloudflare, Streamlit deployment, server process or custom-domain setup is required for the initial release.

## Project-path compatibility

Vite uses:

```ts
base: './'
```

so generated runtime and application assets are relative to the deployed project path rather than assuming the site is hosted at the domain root. This is required for a GitHub project Pages URL such as `/ClinSearch-Crosswalk/`.

## Browser security policy

GitHub Pages does not process the repository's Cloudflare/Netlify-style `_headers` file as HTTP response-header configuration. Therefore the browser entry document includes a CSP meta policy covering the static application's script, WebAssembly, worker, connection, style, image, object, base and form boundaries.

The existing `browser/public/_headers` file is retained for local preview and alternative static hosts, but release claims must not imply that GitHub Pages applies those custom response headers.

The CSP meta element cannot provide every response-header-only control (for example `frame-ancestors`). GitHub's own HTTPS and platform response headers remain provider-controlled.

## Public-release gates

Before removing the development/noindex language and declaring the site final:

1. CI is green on the frozen release candidate;
2. the frozen MeSH cache is validated and its hash recorded in the runtime manifest;
3. representative real-corpus strategies are exercised on the deployed Pages site;
4. browser outputs are compared with the authoritative Python reference outputs for those cases;
5. desktop/mobile and light/dark/system presentation are checked at the real HTTPS URL;
6. licensing/release metadata are approved;
7. the final software tag and archival DOI are created when ready.

The representative real-corpus check is acceptance testing of the deployed implementation, not a new optimisation step or a new benchmark used to change v21 semantics.

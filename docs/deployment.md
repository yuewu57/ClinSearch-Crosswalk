# Public deployment — static browser release

ClinSearch-CrossWalk's planned public interface is the static browser application under `browser/`. It runs the pinned Python reference converter locally through Pyodide/WebAssembly. No conversion backend, database, account system or API key is required.

This document is a release procedure, not evidence that a production site is already live.

## 1. Release gates

Before public production deployment:

1. use a populated, reviewed MeSH cache and run `scripts/validate_mesh_cache_release.py`;
2. pass native Python tests and Ruff;
3. pass browser unit/parity/build/end-to-end CI;
4. run representative real-corpus acceptance checks against the authoritative Python output using the same frozen cache;
5. record the exact source commit, software/ruleset versions and cache SHA-256;
6. confirm licensing, contributor attribution and third-party notices;
7. remove development/noindex notices only after the preceding gates pass.

The private development corpus is not part of the public source release.

## 2. Build

From the repository root:

```bash
python -m pip install -r requirements-dev.txt
cd browser
npm ci
npm test
npm run build
```

The deployable output is:

```text
browser/dist/
```

Preview it over HTTP(S), not by opening `index.html` directly:

```bash
node scripts/serve-preview.mjs
```

Then open `http://127.0.0.1:4173`.

## 3. Static-host requirements

Any static host used for production must:

- publish `browser/dist/` without rewriting application assets incorrectly;
- serve JavaScript, WebAssembly and Python/runtime assets with appropriate MIME types;
- preserve the security headers emitted by the build where the platform supports custom headers;
- support HTTPS;
- not inject scripts that violate the release Content Security Policy unless that change is explicitly reviewed;
- not require strategy content to be sent to a conversion server.

Cloudflare Pages, GitHub Pages or another static host can satisfy the architecture if configured accordingly. Hosting-provider terms and logging practices must be reviewed separately.

For the current Cloudflare-oriented build settings and security checks, see [browser_deployment_v1_YW_18092026.md](browser_deployment_v1_YW_18092026.md).

## 4. Production acceptance

On the real HTTPS URL test, at minimum:

- a simple free-text strategy;
- ordinary MeSH;
- pharmacological-action behaviour using the frozen cache;
- adjacency;
- wildcard phrase handling;
- inline `.ti,ab.`;
- LIMIT;
- database-update rows;
- a long Boolean dependency chain;
- RTF upload;
- an intentionally invalid strategy;
- mobile layout and light/dark/system themes.

Compare conversion output with the authoritative Python reference for the same cases and cache. Do not substitute a visual smoke test for semantic parity.

## 5. Freeze and archive

For the release used in the paper, archive together:

- Git commit;
- software tag/version;
- ruleset version;
- terminology-cache filename and SHA-256;
- MeSH year and cache generation timestamp/source;
- CI/regression result;
- real-corpus acceptance record;
- public application URL;
- repository URL;
- release date;
- immutable archive/DOI when created.

Do not add a DOI or paper URL before it exists.

## 6. Post-release changes

Conversion-rule changes require a new ruleset/versioned release and regression review. UI-only changes must still pass browser tests. A terminology-cache replacement must be treated as a release artefact change: validate it, record its new hash and rerun the representative acceptance set before production promotion.

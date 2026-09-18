# ClinSearch-CrossWalk release-candidate checklist

This checklist separates work that is already implemented from evidence still required before the public research release.

## Conversion semantics

- [x] v20 base + approved v21 delta implemented.
- [x] Python reference API shared by paste/RTF/CLI/local web adapters.
- [x] Browser candidate executes the unchanged pinned Python reference engine through WebAssembly.
- [x] Retrieval gate blocks validated executable output for non-OK conversions.
- [x] Targeted conformance tests cover the previously documented implementation gaps.
- [ ] No further conversion-rule changes after final release freeze.

## Terminology

- [x] Exact-only MeSH resolver; no fuzzy matching.
- [x] Empty starter cache clearly identified as non-release.
- [x] Release-cache provenance validator added.
- [ ] Locate or regenerate the populated terminology cache.
- [ ] Validate cache structure/provenance.
- [ ] Record cache filename, SHA-256, MeSH year, generation timestamp/source and record count.
- [ ] Confirm no synthetic fixture records are present.
- [ ] Freeze the cache used for final acceptance/benchmark confirmation.

## Verification

- [x] Native Python regression/conformance suite in CI.
- [x] Native/WebAssembly parity suite.
- [x] Browser build and Chromium end-to-end checks.
- [ ] Run representative real-corpus acceptance cases with the frozen populated cache.
- [ ] Compare browser output to authoritative Python output for those cases.
- [ ] Record CI run/commit for the frozen release candidate.

## Public interface

- [x] Static browser architecture; no conversion backend.
- [x] System/Light/Dark themes and mobile layout checks.
- [x] Associated-paper block with placeholder rather than invented URL.
- [x] Security headers/CSP in static build.
- [ ] Select production static host.
- [ ] Deploy preview HTTPS URL.
- [ ] Verify MIME types, headers and runtime loading on the real URL.
- [ ] Verify desktop and mobile acceptance cases.
- [ ] Remove development/noindex notices only after release approval.
- [ ] Add final application URL to release documentation.

## Repository and metadata

- [x] Obsolete duplicate root v20 files removed from the release-candidate branch while canonical/historical copies remain under `docs/` and `reference/`.
- [x] Obsolete Streamlit-public-launch landing page/monitoring stack removed; Streamlit remains a local/reference adapter.
- [x] Current deployment documentation points to the static browser release.
- [ ] Decide final software release version/tag.
- [ ] Confirm approved software contributor metadata.
- [ ] Confirm rights-holder/licensing approval.
- [ ] Add actual release date.
- [ ] Create immutable archive/DOI.
- [ ] Add associated paper URL/DOI when available.
- [ ] Make repository/public snapshot available when approved.

## Paper claims

Before manuscript freeze, verify that the paper states:

- the 61 Cochrane strategies were the development/regression corpus;
- the rules were frozen before evaluation on the separately selected 14-strategy external benchmark;
- the 14-set evaluation is described as external benchmarking rather than clinical relevance validation;
- the public software architecture uses the same reference Python engine in the browser rather than a separate semantic rewrite;
- licensing is described as source-available under PolyForm Noncommercial 1.0.0 unless deliberately relicensed;
- exact release URL, repository URL and DOI are included only after they exist.

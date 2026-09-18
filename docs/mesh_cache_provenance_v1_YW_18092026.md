# MeSH cache provenance for a public ClinSearch-CrossWalk release

The public browser build should use a frozen, non-empty exact-resolution MeSH cache whose provenance can be reported alongside the software commit. The current repository file `resources/mesh_resolution_cache_v20_v1.json` is intentionally an empty starter cache and is not a release terminology bundle.

## What the release cache must contain

A release-grade cache must use schema version 1 and record:

- the MeSH vocabulary year;
- a timezone-aware generation timestamp;
- the NLM lookup source;
- only successfully resolved exact preferred-label, exact entry-term or reviewed historical-alias mappings;
- the canonical MeSH label, descriptor identifier and URI;
- descriptor class;
- pharmacological-action status;
- the MeSH year on each resolved record.

Synthetic fixture identifiers must never be copied into production resources.

## If an older populated cache exists locally

Search the development machine for files matching:

```text
mesh_resolution_cache*.json
```

For each candidate, run from the repository root:

```powershell
python scripts/validate_mesh_cache_release.py "C:\path\to\candidate.json"
```

A release candidate is acceptable only when the report shows:

```json
"release_ready": true
```

The report also prints the SHA-256 digest, record count, MeSH year, record-class counts, match-type counts and pharmacological-action count. Keep the original candidate unchanged until its provenance has been reviewed.

## If no populated cache can be found

Rebuild a cache from the private development/evaluation strategy corpus using the existing exact-only resolver. The source corpus remains private and must not be copied into the public repository.

From an environment with outbound NLM access:

```powershell
python -m ovid_pubmed_converter.mesh_cache build ^
  --dataset-root "C:\PRIVATE\clinsearch_strategy_corpus" ^
  --output "resources\mesh_resolution_cache_v20_v1_YW_DDMMYYYY.json" ^
  --glob "**/*"
```

The builder scans only `.rtf` and `.txt` files matched by the glob. It uses exact NLM lookup; it does not introduce fuzzy matching. The command returns a non-zero status when inputs fail or controlled headings remain unresolved.

Then validate the resulting file:

```powershell
python scripts/validate_mesh_cache_release.py "resources\mesh_resolution_cache_v20_v1_YW_DDMMYYYY.json"
```

Do not overwrite the empty starter cache during investigation. Add the dated populated cache only after review.

## Provenance to archive with the paper/software release

For the final evaluated release, record together:

1. exact Git commit and software tag;
2. conversion ruleset identifier;
3. cache filename;
4. cache SHA-256;
5. MeSH vocabulary year;
6. cache generation timestamp and NLM source;
7. number of resolved records and unresolved headings, if any;
8. benchmark/evaluation configuration and date;
9. regression-suite result for the same commit and cache;
10. immutable software archive/DOI once created.

The browser build already records the cache hash, record count, MeSH year, source and Python reference commit in its runtime manifest. This document defines the additional release gate: the public production cache must be non-empty and pass the validator before the development/noindex notices are removed.

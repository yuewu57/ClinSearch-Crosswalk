# MeSH resources

Production caches use the v20 JSON schema and contain exact NLM resolution metadata. Test fixture caches contain deliberately synthetic IDs and must not be promoted here. Cache-only conversion safely falls back to the quoted source heading with `[mh]` and an audit event on a miss.

## Release-candidate cache

`mesh_resolution_cache_v20_v1_YW_18092026.json`

- MeSH vocabulary year: **2026**
- Generated: **2026-09-18T13:16:43.511598+00:00**
- Source: **NLM MeSH RDF Lookup and SPARQL APIs**
- Resolved records: **620**
- Resolution policy: exact preferred labels, exact entry terms and reviewed historical aliases only.
- Unresolved or ambiguous headings are not inserted into the cache; the converter retains the audited source-heading fallback.

The empty `mesh_resolution_cache_v20_v1.json` remains only as a development/bootstrap fallback. The browser build selects the newest dated reviewed cache by default.

Validate before release promotion:

```bash
python scripts/validate_mesh_cache_release.py resources/mesh_resolution_cache_v20_v1_YW_18092026.json
```

The browser runtime manifest records the selected cache SHA-256, record count, MeSH year and source together with the pinned reference-engine provenance.

# MeSH resources

Production caches use the v20 JSON schema and contain exact NLM resolution metadata. Test fixture caches contain deliberately synthetic IDs and must not be promoted here. Cache-only conversion safely falls back to the quoted source heading with `[mh]` and an audit event on a miss.

`mesh_resolution_cache_v20_v1.json` is an intentionally empty bootstrap cache. Build a reviewed dated production cache from a private corpus without committing the corpus:

```bash
python -m ovid_pubmed_converter.mesh_cache build \
  --dataset-root /absolute/path/to/dataset_61_cochrane \
  --glob '**/*.rtf' \
  --output resources/mesh_resolution_cache_v20_v1_YW_16082026.json
```

The builder performs exact NLM resolution only and reports unresolved headings. The web app automatically selects the newest `mesh_resolution_cache_v20_v1_YW_*.json`, otherwise it uses the bootstrap cache. Cache writes within one application process are serialized and use the engine's atomic replacement behavior.

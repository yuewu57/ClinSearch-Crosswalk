# ClinSearch-CrossWalk architecture

## Reference conversion core

Both input modes converge on the same `Strategy` model. Pasted text uses `parse_strategy_text`; RTF bytes pass through deterministic byte-first normalization and then the same row semantics. `convert_strategy` is the strategy-level semantic orchestrator. It applies the approved v21 layer over the preserved v20 rule engine, exact cache-first MeSH resolution, dependency-aware validation and UI-independent `ConversionResult` construction.

The normative rule definition is the v20 base specification plus the approved v21 delta. The Python implementation under `src/ovid_pubmed_converter/` is the executable reference.

## Adapters

- **CLI:** `cli/batch_convert.py`.
- **Local Streamlit adapter:** `web/app.py`.
- **Browser release candidate:** TypeScript UI + Web Worker + pinned Pyodide runtime executing the unchanged reference Python modules locally.

The browser is therefore not an independent semantic port. Build-time source hashes and a runtime manifest bind the packaged Python modules, browser bridge, Pyodide runtime and selected MeSH cache to the release candidate.

## Browser data flow

```text
user paste / RTF bytes
        ↓
TypeScript UI
        ↓
Web Worker
        ↓
Pyodide / WebAssembly
        ↓
browser_bridge.py
        ↓
reference Python parser + converter + validator
        ↓
structured ConversionResult
        ↓
rendered query / numbered strategy / audit / downloads
```

No conversion server is required. User strategy text is passed as data and is never evaluated as Python code.

## Terminology

Production conversion is cache-first and exact only. The static browser build has no live MeSH call. A cache miss uses the approved executable source-heading fallback and is audited. A final public research release therefore freezes and hashes a reviewed populated MeSH cache.

Fixture caches contain synthetic deterministic records and are test artefacts only.

## Validation boundary

The one-line query is generated only from the validated final dependency closure. Conversion failures are not represented as zero retrieval. Unsupported or unsafe active syntax produces a non-OK result and blocks validated executable output.

Core regression tests require no network access.

# Architecture

Both input modes converge on `Strategy`: pasted text goes directly through `parse_strategy_text`; uploaded bytes go through the byte-first RTF normalizer and then the same row semantics. `convert_strategy` is the only strategy-level semantic orchestrator. It calls the preserved v20 rule engine, exact cache-first MeSH resolver, dependency-aware validation, and produces a UI-independent `ConversionResult`. CLI and Streamlit are adapters over the same API. Output renderers produce TXT, audit CSV, validation JSON, and RTF in memory.

The UI never supplies server paths. Uploaded bytes use an automatically cleaned temporary directory only during RTF normalization. Core regression tests use fixture-only exact MeSH records and no network.

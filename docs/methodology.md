# Methodology

The dated v20 specification is normative, fixtures are the approved regression oracle, and the preserved Python source is the reference implementation. Refactoring is guarded by exact semantic output comparison plus required and forbidden audit assertions. Approximations, fallback, omission, and manual-review conditions remain visible. Only errors in the final query dependency closure are fatal; unused invalid rows remain warnings.

Known reference discrepancies corrected by the package are byte/code-page RTF decoding, year-leading continuation protection, verified canonical-MeSH protected-hyphen handling, and generic publication-type audit behavior.

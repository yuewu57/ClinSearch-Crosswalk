# ClinSearch-CrossWalk methodology

ClinSearch-CrossWalk is a deterministic, recall-oriented translation framework for Ovid MEDLINE-to-PubMed conversion.

The normative rule definition is the maintained **v20 base specification plus the approved v21 delta**. The Python reference implementation is tested against deterministic fixtures and targeted conformance tests. Refactoring is guarded by exact semantic-output comparison and required/forbidden audit assertions. Approximations, fallbacks, omissions and manual-review conditions remain visible. Validation is dependency-aware: defects in the active final-query closure are fatal, while unused malformed rows remain auditable warnings.

Rule development and refinement used the 61-strategy Cochrane development/regression corpus. After the ruleset was frozen, the separately selected 14-strategy non-Cochrane corpus was used for external benchmarking rather than further rule development.

The tested implementation includes deterministic RTF byte/code-page handling, year-leading continuation protection, the verified canonical-MeSH exception for protected hyphenated terms, generic publication-type auditing, v21 frequency handling, LIMIT alias handling, database-update row handling, wildcard-phrase rendering and inline multi-field suffix preservation.

The browser release candidate does not reimplement these semantics. It executes the pinned Python reference modules through Pyodide/WebAssembly and is checked against native reference outputs on the deterministic parity suite.

Passing software regression tests establishes conformance on covered cases. Retrieval-preservation evaluation is reported separately and should not be conflated with clinical relevance or universal equivalence between Ovid MEDLINE and PubMed.

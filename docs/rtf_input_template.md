# RTF input template

Download `resources/rtf_input_template.rtf` from the web upload tab or from this repository. Its minimum visible content is:

```text
Medline:

1. exp Asthma/
2. asthma.tw.
3. 1 or 2
```

Two primary RTF structures are accepted:

1. **Explicit block:** use a `Medline:` heading when the document contains metadata, notes, or any other content. Strategy rows continue until a recognised section heading or the end of the document. Visible Ovid line numbers are strongly preferred.
2. **Standalone strategy:** the entire document is one coherent **numbered** Ovid MEDLINE strategy, beginning at row 1, containing at least two rows, and using valid increasing row structure. Arbitrary report text is rejected rather than guessed to be a strategy.

## Missing line numbers in an explicit Medline block

The web input adapter may recover missing line numbers only when an explicit `Medline:` section is present and **every extracted paragraph is conservatively recognisable as a complete Ovid search row**. In that narrow case, rows are assigned `1, 2, 3, ...` by paragraph order and the conversion result includes the warning:

```text
rtf_line_numbers_recovered_from_medline_paragraph_order
```

The reconstructed numbering must be reviewed before retrieval. If any paragraph is structurally ambiguous, the RTF is rejected rather than guessed. A standalone RTF without a `Medline:` heading is never auto-numbered.

Word list labels may be inline or on the physical line before their expression. An optional `End_date: DD-MM-YYYY` line before an explicit `Medline:` block is retained only as a technical compatibility capability for the pure `.ed,dt.` update-line rule. It is not required and does not create a PubMed publication-date filter.

## Ovid LIMIT and frequency constraints

Ovid post-search restrictions are detected and audited but are not reproduced automatically as equivalent PubMed restriction semantics:

- `limit N to ...`: the LIMIT condition is omitted, references are redirected to the underlying row `N`, and output rows are renumbered where required. Apply a corresponding PubMed filter after conversion where one exists, for example age, publication date/year, or language. Not every Ovid limit has an exact PubMed equivalent.
- `/freq=1`: removed as redundant.
- `/freq=N` for `N > 1`: the occurrence-frequency requirement is removed, producing a deliberately broader PubMed search. PubMed filters do not reproduce this term-frequency constraint.

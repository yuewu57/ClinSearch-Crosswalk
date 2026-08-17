# RTF input template

This template is for **Evidentia Search Strategy Convertor** — **Ovid MEDLINE → PubMed**, part of Evidentia.

Download `resources/rtf_input_template.rtf` from the web upload tab or from this repository. Its minimum visible content is:

```text
Medline:

1. exp Asthma/
2. asthma.tw.
3. 1 or 2
```

Two RTF structures are accepted:

1. **Explicit block:** use a `Medline:` heading when the document contains metadata, notes, or any other content. Strategy rows continue until a recognised section heading or the end of the document.
2. **Standalone strategy:** the entire document is one coherent numbered Ovid MEDLINE strategy, beginning at row 1, containing at least two rows, and using valid increasing row structure. Arbitrary report text is rejected rather than guessed to be a strategy.

Word list labels may be inline or on the physical line before their expression. An optional `End_date: DD-MM-YYYY` line before an explicit `Medline:` block is retained only as a technical compatibility capability for the v20 pure `.ed,dt.` update-line rule. It is not required and does not create a PubMed publication-date filter.

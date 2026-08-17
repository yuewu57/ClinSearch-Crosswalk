# Cochrane Ovid MEDLINE-to-PubMed Conversion Rules — v20

**Converter:** `cochrane_data_pubmed_converter_v20_cli_YW_28072026.py`  
**Rule version:** v20  
**Date:** 28 July 2026  
**Primary objective:** produce an executable, auditable, recall-oriented PubMed strategy from an Ovid MEDLINE strategy without silently deleting valid search concepts.  
**Document status:** approved normative v20 rule specification.  
**Executable conformance status:** incomplete; the attached v20 Python file does not currently implement every rule in this specification. See Section 24.

---

## 1. Governing principles

1. **Preserve previously validated behaviour.** A working conversion rule is not changed silently in a later version.
2. **Prioritise recall unless a narrower rule has been explicitly approved.** Any intentional recall–precision trade-off must be documented.
3. **Do not invent controlled-vocabulary mappings.** Exact preferred labels, exact entry terms, and reviewed historical aliases may be canonicalised; unresolved headings use a safe executable fallback.
4. **Do not silently delete source concepts.** Unsupported constructs must be converted conservatively, retained literally where possible, or marked for manual review.
5. **Keep the conversion auditable.** Every material approximation, fallback, omission, canonicalisation, or warning is recorded in the audit CSV.
6. **Do not submit invalid output to PubMed.** A strategy with `validation_failed` or `manual_review_required` status must not be used for retrieval or stored as a genuine count of zero.

---

## 2. Input and output contract

### 2.1 Expected folder structure

Each Cochrane study is held in its own subfolder:

```text
<root>/
  CDxxxxxx/
    CDxxxxxx.rtf
```

The source RTF must contain a `MEDLINE:` block. Metadata such as `End_date:` may appear before the strategy.

### 2.2 Outputs

For each processed study, v20 writes:

```text
CDxxxxxx_pubmed_v20.rtf
CDxxxxxx_pubmed_v20.txt
CDxxxxxx_pubmed_audit_v20.csv
CDxxxxxx_pubmed_validation_v20.txt
```

The audit contains:

```text
line_number
original
converted
flags
validation_status
validation_errors
```

---

## 3. RTF extraction and source-row rules

### 3.1 RTF decoding

v20 shall:

- read the RTF as bytes;
- respect the declared `\ansicpgN` code page;
- preserve valid Windows-1252 characters;
- support legacy UTF-8 content written under an ANSI RTF header through a strict compatibility path;
- decode group-scoped `\ucN` and all `\uN` controls;
- never use `errors="ignore"` to silently discard characters;
- write non-ASCII output using RTF `\uN?` escapes.

### 3.2 Ignorable RTF destinations

Complete ignorable destinations beginning with `{\*...}`, including Word metadata such as `themedata`, must be removed before visible-text extraction.

Embedded Office metadata or hexadecimal package data must never become search-strategy text.

### 3.3 Word list numbering

RTF `listtext` numbers are preserved before the remaining formatting is removed.

Both forms are accepted:

```text
1. Ankle Fractures/
```

and:

```text
1.
Ankle Fractures/
```

When a punctuated list number appears on a line by itself, the next physical line is its expression, even when that expression begins with a number:

```text
22.
10 and 21
```

This must be parsed as strategy row 22 with expression `10 and 21`.

### 3.4 Row numbering

- Row numbers must be unique.
- Row numbers must be strictly increasing.
- A standalone unpunctuated integer is not automatically treated as a row label.
- Year-leading continuation text, such as `2020 or 2021`, must not become a spurious strategy row.
- The final source row must not be empty.
- Residual RTF controls in a strategy expression are validation errors.

---

## 4. Conversion order

The ordering is part of the rule because earlier classification protects later transformations.

For each source line, v20 processes:

1. Unicode and punctuation normalisation.
2. Strict whole-line animal-only filter.
3. Optional omission of a pure `.ed,dt.` update line.
4. Mixed numeric line-reference recognition.
5. Exact Cochrane RCT and animal-filter mappings.
6. Comments/corrections `.cm.` relations.
7. Exact whitelisted slash publication types.
8. Wildcard-bearing slash objects.
9. MeSH/API-assisted controlled headings.
10. Audit of potentially ambiguous free-text Boolean wording.
11. Ovid `?` and `#` expansion.
12. Ovid truncation conversion.
13. Ovid adjacency conversion.
14. Boolean and empty/dropped-atom simplification.
15. Generic controlled suffixes: `.pt.`, `.fs.`, `.nm.`, `.pa.`.
16. Ovid runtime-stopword handling in explicit free-text fields.
17. Free-text phrase quotation.
18. Boolean line-reference conversion.
19. Generic free-text field conversion.
20. Group-level field distribution.
21. Final Boolean, tag, spacing, and ESearch-safe normalisation.
22. Local syntax, field-tag, source-structure, and reference-graph validation.

---

## 5. Single-character wildcards: `?` and `#`

### 5.1 General semantics

- Ovid `?` is treated as **zero or one character**.
- Ovid `#` is treated as **exactly one character**.
- They are parsed separately and are not conflated.
- Expansion is atom-aware and must not cross Boolean operators, proximity operators, parentheses, quoted strings, field suffixes, or line references.

### 5.2 Curated interpretations take priority

Examples include:

```text
randomi?ed
→ randomised OR randomized

?estrogen*
→ estrogen* OR oestrogen*

anti-?estrogen*
→ anti-estrogen* OR anti-oestrogen*

isch?emi$
→ ischemi$ OR ischaemi$

shon?s
→ shones OR shone's OR shone
```

Generic UK/US `-ise/-ize` and `-or/-our` patterns are expanded before exhaustive character substitution.

A terminal optional wildcard may represent a singular/plural pair:

```text
control group?
→ "control group" OR "control groups"
```

### 5.3 Generic fallback

When no curated interpretation applies:

- each `?` expands to the empty string plus `a`–`z`;
- each `#` expands to `a`–`z`;
- expansion is limited to 729 variants per atom;
- exceeding that limit generates a manual-review marker rather than an uncontrolled expansion.

---

## 6. Truncation rules

### 6.1 Standard roots

Ovid `$`, `$N`, `*`, and `*N` are converted to PubMed `*` where the root has at least four alphanumeric characters.

```text
fracture$
→ fracture*

randomi$3
→ randomi*
```

A limited Ovid truncation is therefore an audited approximation to PubMed unlimited truncation.

### 6.2 Unsupported leading stars

Unsupported leading free-text stars are removed and audited. A MeSH focus marker is handled separately before this rule.

### 6.3 Short roots

A root with fewer than four alphanumeric characters before truncation is not silently deleted.

The hierarchy is:

1. curated biomedical acronym expansion;
2. curated morphology or irregular-plural expansion;
3. curated phrase or identifier handling;
4. conservative internal-wildcard collapse;
5. literal preservation of the root after removing the unsupported wildcard.

Examples:

```text
HIV*
→ HIV OR HIV1 OR HIV2 OR HIV-1 OR HIV-2

job*
→ job OR jobs

drop out*
→ "drop out" OR "drop outs"

typ* 1
→ "type 1" OR "type-1" OR type1 OR "type_1"

oc*ular*
→ ocular*
```

An unknown trailing short root is retained literally and audited for possible recall loss:

```text
abc*
→ abc
```

### 6.4 No silent deletion

A short-root problem must not erase an otherwise valid Boolean concept without an audit trail. Where an atom is deliberately removed, dependent Boolean expressions are simplified structurally.

---

## 7. Free-text phrase and stopword rules

### 7.1 Phrase quotation

Atomic multi-word free-text expressions are quoted, while Boolean or proximity groups are not quoted as a whole.

```text
heart failure.tw.
→ "heart failure"[tw]
```

Boolean words are normalised only outside quoted strings.

### 7.2 Ovid runtime stopwords

The following stopwords are removed only after an expression has been classified as explicit free text:

```text
and, as, for, from, is, of,
that, the, this, to, was, were
```

They are never removed from:

- MeSH headings;
- entry terms;
- publication types;
- subheadings;
- comments/corrections relations;
- other controlled-vocabulary objects.

After stopword removal:

- duplicate content terms are removed;
- one remaining term is searched alone;
- multiple remaining terms are joined by `AND`.

Examples:

```text
skin to skin.tw.
→ skin[tw]

quality of life.tw.
→ (quality[tw] AND life[tw])

skin-to-skin.tw.
→ "skin-to-skin"[tw]
```

A phrase containing only stopwords becomes `__MANUAL_REVIEW_REQUIRED__` and fails active-query validation.

---

## 8. Boolean and line-reference rules

### 8.1 Boolean normalisation

Standalone `and`, `or`, and `not` outside quotes become uppercase `AND`, `OR`, and `NOT`.

Words containing these letter sequences are not split:

```text
translator*
donor
notation
```

### 8.2 Ovid line references

```text
or/1-3
→ #1 OR #2 OR #3

and/4-6
→ #4 AND #5 AND #6

29 not (28 or 27)
→ #29 NOT (#28 OR #27)
```

Mixed numeric references are converted only when the number is an actual strategy-row number. Years, doses, identifiers, and unrelated numbers are not automatically converted.

### 8.3 Reference validation

v20 detects:

- undefined references;
- circular references;
- duplicate source rows;
- invalid final-line selection.

Fatal line-level validation is applied to the final query and every line in its dependency closure. A problem in an unused line is recorded as `warning_unused_line` rather than invalidating an independent final query.

---

## 9. Adjacency and proximity

Ovid `adj`, `adjN`, and `next` are approximated as `AND`:

```text
upper adj3 respiratory tract infection*.tw.
→ upper[tw] AND "respiratory tract infection*"[tw]
```

This is an intentional recall-oriented approximation. It does not reproduce Ovid positional semantics exactly and must be audited as such.

---

## 10. MeSH and controlled-heading rules

### 10.1 Default resolution mode

The default is:

```text
--mesh-mode online
```

The converter:

1. collects unique uncached controlled-heading candidates;
2. performs an online MeSH preflight;
3. stores successful exact mappings in a persistent cache;
4. performs the actual conversion from cache/session results;
5. falls back safely to the source heading when resolution is unavailable or unresolved.

The converter does not make one API request for every repeated occurrence of a heading.

`--mesh-mode cache-only` remains available for reproducible offline runs. A cache miss in this mode uses the same executable source-heading fallback.

### 10.2 Permitted resolution types

v20 permits:

- exact preferred-label matches;
- exact MeSH entry-term matches;
- reviewed historical aliases followed by exact current-label resolution.

It does not use unrestricted fuzzy or nearest-term matching.

### 10.3 Canonical output

A verified match uses the current canonical label, descriptor ID, match type, and record class in the audit.

```text
Fracture, Bone/
→ "Fractures, Bone"[mh]

Nephrosis Lipoid/
→ "Nephrosis, Lipoid"[mh]
```

Reviewed historical aliases include:

```text
Heart Failure, Congestive       → Heart Failure
Conscious Sedation              → Procedural Sedation
Pain, Postoperative             → Postoperative Pain
Randomized Controlled Trials    → Randomized Controlled Trials as Topic
Clinical Trials                 → Clinical Trials as Topic
Evaluation Studies              → Evaluation Studies as Topic
Fracture, Bone                  → Fractures, Bone
Double Blind Method             → Double-Blind Method
Follow Up Studies               → Follow-Up Studies
Nephrosis Lipoid                → Nephrosis, Lipoid
```

### 10.4 Safe unresolved-heading fallback

An API failure, cache miss, historical punctuation mismatch, or unresolved exact label does not destroy the query.

```text
Unresolved Heading/
→ "Unresolved Heading"[mh]
```

The audit records the status and reason:

```text
mesh_resolution_fallback_to_source_heading:<term>:<status>:<reason>
```

### 10.5 Main-descriptor-only project rule

Attached Ovid slash subheadings are ignored and audited:

```text
Asthma/therapy
→ "Asthma"[mh]
```

An Ovid focus marker `*` is ignored for recall and audited.

### 10.6 Explosion policy

Both ordinary and explicitly exploded topical headings use `[mh]`; v20 never generates `[mh:noexp]` or `[pt:noexp]`.

```text
Nephrotic Syndrome/
→ "Nephrotic Syndrome"[mh]

exp Nephrotic Syndrome/
→ "Nephrotic Syndrome"[mh]
```

### 10.7 Pharmacological-action expansion

When all of the following are true:

1. the Ovid heading is explicitly exploded with `exp`;
2. the verified record class is a MeSH heading searched with `[mh]`;
3. the MeSH record is used as a pharmacological-action target;

v20 outputs:

```text
("Canonical Heading"[mh] OR "Canonical Heading"[pa])
```

This approved recall expansion does not apply to ordinary non-`exp` headings or publication-type records.

### 10.8 Record-class handling

- `TopicalDescriptor`, `GeographicalDescriptor`, and `CheckTag` → `[mh]`
- `PublicationType` → `[pt]`
- an unsupported verified record class → manual review

### 10.9 Wildcard-bearing slash objects

A slash object containing `?`, `#`, `$`, or `*` is not treated as a controlled heading. It is converted to free text with `[tw]` after wildcard/truncation processing.

```text
therap*/
→ therap*[tw]
```

---

## 11. Study-design and Cochrane RCT-filter rules

High-priority mappings run before generic controlled-heading conversion.

### 11.1 Topic descriptors versus publication types

```text
Randomized controlled trials/
→ "Randomized Controlled Trials as Topic"[mh]

Clinical trials/
→ "Clinical Trials as Topic"[mh]

Evaluation studies/
→ "Evaluation Studies as Topic"[mh]

randomized controlled trial.pt.
→ "Randomized Controlled Trial"[pt]

controlled clinical trial.pt.
→ "Controlled Clinical Trial"[pt]

clinical trial.pt.
→ "Clinical Trial"[pt]

comparative study.sh.
→ "Comparative Study"[pt]
```

### 11.2 Standard RCT free-text terms

```text
placebo.ab.     → placebo[tiab]
randomly.ab.    → randomly[tiab]
trial.ab.       → trial[tiab]
groups.ab.      → groups[tiab]
trial.ti.       → trial[ti]
randomi?ed.ab.  → randomised[tiab] OR randomized[tiab]
```

### 11.3 Floating drug-therapy subheading

```text
drug therapy.fs.
dt.fs.
→ drug therapy[sh]
```

### 11.4 Human/animal filters

```text
exp animals/ not humans.sh.
animals/ not humans/
animals.sh. not humans.sh.
→ animals[mh] NOT humans[mh]
```

The complete strict legacy line:

```text
(animal not human).sh.
```

becomes:

```text
(animals[mh] NOT humans[mh])
```

---

## 12. Publication-type slash whitelist

Only exact whitelisted slash headings are converted directly to `[pt]` without fuzzy inference:

```text
Randomized Controlled Trial
Controlled Clinical Trial
Clinical Trial
Clinical Trial, Phase I
Clinical Trial, Phase II
Clinical Trial, Phase III
Clinical Trial, Phase IV
Pragmatic Clinical Trial
Observational Study
```

An exact whitelisted slash heading is rendered with its canonical title and `[pt]`.

A non-whitelisted slash heading continues through normal MeSH resolution rather than being guessed to be a publication type.

---

## 13. Other controlled-field suffixes

### 13.1 `.pt.` publication type

```text
clinical trial.pt.
→ clinical trial[pt]
```

Parenthesised groups have `[pt]` distributed to their terminal atoms.

A generic `.pt.` value that is not independently verified remains executable but is flagged as unverified rather than silently presented as an authoritative controlled value.

### 13.2 `.fs.` floating subheading

```text
adverse effects.fs.
→ adverse effects[sh]
```

Known abbreviations are expanded through the MeSH subheading map. Unknown short abbreviations are preserved and audited.

### 13.3 `.nm.` supplementary concept

```text
Insulin Glargine.nm.
→ "Insulin Glargine"[nm]
```

### 13.4 `.pa.` pharmacological action

```text
Protein Kinase Inhibitors.pa.
→ "Protein Kinase Inhibitors"[pa]
```

---

## 14. Free-text field mapping

The approved generic field mapping is:

| Ovid field | PubMed output | Rule |
|---|---|---|
| `.ti.` | `[ti]` | title |
| `.ab.` | `[tiab]` | PubMed abstract field is approximated by Title/Abstract |
| `.kf.` | `[tiab]` | keyword-heading approximation |
| `.ti,ab.` or combinations within `ti/ab/kf` | `[tiab]` | broad common field |
| `.tw.` | `[tw]` | text word |
| `.mp.` | `[tw]` | multipurpose approximation |
| `.af.` | `[all]` | all fields |
| `.jn.` | `[ta]` | journal title/abbreviation |
| `.jw.` | `[ta]` | journal word approximation |
| `.ot.` | `[tw]` | original-title approximation, audited |
| `.hw.` | `[tw]` | heading-word approximation, audited |

Multifield rules:

1. if `.af.` is present → `[all]`;
2. else if `.tw.` or `.mp.` is present → `[tw]`;
3. else if `.ot.`, `.hw.`, or `.nm.` appears in a free-text multifield context → `[tw]` with audit where applicable;
4. else a set containing only `.ti.`, `.ab.`, and `.kf.` maps to `[ti]` only when it is exactly `{ti}`, otherwise `[tiab]`;
5. an unsupported combination defaults to `[tw]` and is audited.

Parenthesised group suffixes are distributed to each terminal free-text atom.

Single-token alphanumeric-hyphen free-text terms are quoted before field attachment:

```text
S-1.tw.
→ "S-1"[tw]
```

---

## 15. Comments and corrections: `.cm.`

Known Ovid Comments/Corrections labels are converted to PubMed relation tokens.

Examples:

```text
comment on.cm.     → hascommenton
comment in.cm.     → hascommentin
erratum for.cm.    → haserratumfor
retraction of.cm.  → hasretractionof
update of.cm.      → hasupdateof
```

Parenthesised Boolean groups are converted recursively:

```text
(comment on OR erratum for).cm.
→ (hascommenton OR haserratumfor)
```

An unknown `.cm.` relation is preserved as `[all]` free text and audited rather than being incorrectly collapsed to a generic publication type.

---

## 16. Date-update-line rule

A source line is considered a pure Ovid update-date line only when:

- the whole line consists of numeric date prefixes, parentheses, spaces, and `OR`;
- its suffix is `.ed,dt.` or `.dt,ed.`;
- it contains no concept term, different field, `AND`, or `NOT`.

Example:

```text
(201107* or 2012* or 2013*).ed,dt.
```

It is omitted only when an external `End_date` exists in the source metadata.

When omitted:

- references to the dropped line are simplified structurally;
- the omission is recorded in the audit;
- the last surviving substantive row becomes the final query.

Without an external `End_date`, the converter does not silently omit the date line.

---

## 17. Final ESearch-safe normalisation

Readable or legacy field tags are canonicalised to short executable tags.

Important mappings include:

```text
[Text Word]          → [tw]
[All Fields]         → [all]
[Title]              → [ti]
[ab]                 → [tiab]
[Abstract]           → [tiab]
[Title/Abstract]     → [tiab]
[Mesh]               → [mh]
[MeSH Terms]         → [mh]
[Publication Type]   → [pt]
[Subheading]         → [sh]
[Journal]            → [ta]
[Date - Publication] → [dp]
[Supplementary Concept] → [nm]
[Pharmacological Action] → [pa]
```

Spaces before field tags are removed, and field tags are separated safely from following Boolean operators.

v20 shall not generate or validate:

```text
[ab]
[mh:noexp]
[pt:noexp]
```

---

## 18. Protected hyphenated terms

Hyphenated free text and identifiers are treated as protected source material:

```text
MDX-1106
anti-PD-L1
SN-38
5-FU
```

Their alphanumeric-hyphen content must remain present after conversion unless an exact verified MeSH canonicalisation legitimately changes the controlled heading.

A missing protected term is a validation error for an active query line.

---

## 19. Local validation rules

### 19.1 Permitted PubMed tags

```text
ti, tiab, tw, all, mh, pt, sh,
ta, dp, nm, pa, sb
```

Any other field tag is rejected locally.

### 19.2 Syntax failures

Validation detects, among other conditions:

- empty expressions;
- unbalanced quotes, parentheses, or square brackets;
- early closing delimiters;
- residual Ovid `$`, `?`, wildcard `#`, slash, `exp`, proximity operators, or field suffixes;
- unsupported leading free-text stars;
- converter internal markers;
- dangling or adjacent Boolean operators;
- unknown PubMed field tags;
- unresolved line references;
- known historical regression patterns.

### 19.3 Status values

File-level status:

```text
ok
validation_failed
manual_review_required
```

Audit-row status:

```text
ok
validation_failed
warning_unused_line
removed_after_short_root_cleanup
```

### 19.4 Active-query rule

Only errors in the final query’s dependency closure are fatal. Errors in unused rows are retained as warnings so that they remain visible without blocking an otherwise independent final query.

### 19.5 Retrieval gate

A validation report explicitly states:

> A validation/manual-review failure must not be submitted to PubMed or stored as retrieval count 0.

---

## 20. CLI behaviour

### Convert all studies

```bash
python cochrane_data_pubmed_converter_v20_cli_YW_28072026.py \
  --root dataset_60_cochrane_20260621ver
```

### Convert one study

```bash
python cochrane_data_pubmed_converter_v20_cli_YW_28072026.py \
  --root dataset_60_cochrane_20260621ver \
  --study CD005595
```

### Cache-only run

```bash
python cochrane_data_pubmed_converter_v20_cli_YW_28072026.py \
  --root dataset_60_cochrane_20260621ver \
  --mesh-mode cache-only
```

### Strict validation exit code

```bash
python cochrane_data_pubmed_converter_v20_cli_YW_28072026.py \
  --root dataset_60_cochrane_20260621ver \
  --strict-fail
```

With `--strict-fail`, any non-`ok` study causes a non-zero program exit.

---

## 21. Frozen v20 invariants

The following rules are fixed unless a future change is explicitly discussed and approved:

```text
Ovid .ab.                 → PubMed [tiab]
Heading/                  → [mh] or verified [pt], never :noexp
exp Heading/              → [mh], with approved [mh] OR [pa] expansion where applicable
API/cache failure         → executable source-heading fallback plus warning
Attached slash subheading → ignored; retain main descriptor
Wildcard-bearing slash    → [tw]
Ovid adj/adjN/next        → AND
Pure .ed,dt. omission     → only with external End_date
Validation failure        → must not be submitted to PubMed
```

A future version must regression-test these invariants before release.

---

## 22. Known approximations and limitations

1. Ovid proximity is approximated by `AND`, not reproduced exactly.
2. Ovid limited truncation becomes PubMed unlimited `*`.
3. `.ab.` is broadened to `[tiab]`.
4. `.mp.`, `.ot.`, `.hw.`, and some multifield combinations are approximations.
5. Attached MeSH subheading restrictions are intentionally removed under the main-descriptor-only recall rule.
6. An unresolved slash heading falls back to `[mh]`; the audit, not the syntax alone, distinguishes verified from fallback headings.
7. A generic `.pt.` expression may remain executable with an audit warning even when its controlled value has not been independently verified.
8. Live online MeSH availability is external; the persistent cache and safe fallback prevent service failure from destroying the converted query.

---

## 23. Implementation consistency notes found during documentation

These are code-labelling issues, not approved conversion-rule changes:

1. The v20 source currently defines the default cache filename as:

   ```text
   mesh_resolution_cache_v19_YW_27072026.json
   ```

   The cache contents remain usable, but the filename is inconsistent with the v20 release label.

2. The CLI description currently refers to the “Version 19” corrected converter, although the executable and output version are v20.

These labels should be corrected in a subsequent explicitly documented maintenance edit; they do not change the conversion semantics stated above.

---

## 24. Current executable conformance warning

The attached file `cochrane_data_pubmed_converter_v20_cli_YW_28072026.py` does **not** currently conform fully to the approved v20 specification above. The discrepancies were discovered while checking this Markdown against the executable.

### 24.1 Implemented correctly in the current executable

The current executable does implement these important v20 rules:

```text
.ab. → [tiab]
legacy [ab] and [Abstract] → [tiab]
ordinary slash headings → [mh]
explicitly exploded pharmacological-action heading → [mh] OR [pa]
default MeSH mode → online
unresolved MeSH heading → executable source-heading [mh] fallback
ignorable RTF destination removal
split numbered-list labels such as 22. followed by 10 and 21
dependency-aware active-query validation
```

### 24.2 Rules claimed by the release notes/tests but absent from the current executable

#### A. RTF code-page handling is absent

The current function still reads:

```python
path.read_text(encoding="utf-8", errors="strict")
```

It does not currently:

- read RTF as bytes;
- detect `\ansicpgN`;
- decode raw cp1252 RTF safely;
- provide the documented UTF-8-under-ANSI compatibility path.

Therefore, the RTF code-page rule in Section 3 is the approved target rule, not the present implementation.

#### B. Year-leading continuation protection is absent

The current parser misreads:

```text
1. asthma.tw.
2. (2019 or
2020 or 2021).tw.
3. 1 and 2
```

as rows:

```text
1
2
2020
3
```

Therefore, the sequence-aware continuation rule in Section 3.4 is not yet implemented.

#### C. Protected-hyphen canonical-MeSH exemption is absent

The current protected-hyphen validator accepts only:

```python
validate_protected_hyphenated_terms(original, converted)
```

It does not inspect MeSH-resolution flags and therefore cannot exempt a verified canonical MeSH renaming from literal substring preservation.

#### D. Generic `.pt.` warning is absent

The current conversion:

```text
Unverified Example.pt.
→ Unverified Example[pt]
```

produces no `unverified_generic_publication_type_value` audit warning.

#### E. Default cache filename is still labelled v19

The current code uses:

```text
mesh_resolution_cache_v19_YW_27072026.json
```

The approved v20 maintenance correction should use a v20-labelled cache filename unless backward compatibility is deliberately retained and documented.

#### F. CLI description is still labelled Version 19

The command-line description refers to the “Version 19” corrected converter even though output files are labelled v20.

### 24.3 Regression-suite mismatch

The supplied test file and recorded test-result file do not correspond to the current executable.

Running:

```bash
python test_cochrane_data_pubmed_converter_v20_YW_28072026.py
```

fails against the current executable. The first observed failure is an audit-flag naming mismatch:

```text
test expects:
ovid_abstract_approximated_as_pubmed_title_abstract

current executable emits:
ovid_abstract_field_approximated_as_pubmed_title_abstract
```

Further tests expect the absent code-page, canonical-hyphen, cache-name, generic-publication-type-warning, and year-continuation features described above.

### 24.4 Release-control implication

Until the executable is brought into conformance and the test suite passes against that exact file:

- this Markdown should be treated as the **approved v20 rule specification**;
- the current Python file should be treated as a **partial v20 implementation**;
- the recorded “11 tests passed” result should not be treated as evidence for the current executable;
- retrieval should continue only after checking each generated validation report and query.


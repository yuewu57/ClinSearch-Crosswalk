# Cochrane Ovid MEDLINE-to-PubMed Conversion Rules — v21

**Ruleset:** v21  
**Date:** 23 August 2026  
**Base specification:** v20  
**Status:** approved v21 delta specification.

v21 preserves every approved v20 rule except where this document explicitly overrides it. The v20 rule document therefore remains the normative base specification and this document is read together with it.

## 1. Scope of v21

v21 adds five narrowly scoped behaviours:

1. Ovid `/freq=N` occurrence-frequency modifiers;
2. whole-row Ovid `limit N to ...` constructs;
3. robust PubMed handling of quoted wildcard-bearing free-text phrases;
4. consequential row-reference rewriting and renumbering required by ignored LIMIT rows;
5. removal of pure numeric Ovid MEDLINE database-update date filters using `.ed.`, `.dt.`, `.ed,dt.` or `.dt,ed.`.

v21 does **not** add automatic repair or numbering of a completely unnumbered multi-row MEDLINE strategy. That usability feature is reserved for the online/input-adapter layer, where physical line wrapping can be distinguished from logical strategy rows without changing the conversion ruleset.

All v20 invariants remain frozen unless explicitly overridden below.

## 2. Ovid `/freq=N`

A complete terminal modifier `/freq=N`, where `N` is an integer greater than or equal to 1, is removed while retaining the underlying expression.

```text
cancer.ab./freq=1
→ cancer[tiab]

cancer.ab./freq=2
→ cancer[tiab]
```

### 2.1 `freq=1`

`freq=1` is redundant because a matching fielded term already has to occur at least once. It is removed and audited as:

```text
ovid_frequency_constraint_removed_as_redundant:freq=1
```

### 2.2 `freq>1`

For `N > 1`, removing the occurrence threshold broadens retrieval and is an intentional recall-oriented approximation. It is audited with both:

```text
ovid_frequency_constraint_ignored:freq=N
major_semantic_approximation_recall_broadened
```

### 2.3 Malformed or unsupported frequency syntax

Non-positive, non-integer, embedded, or otherwise malformed `/freq` syntax must not drift into ordinary quoted PubMed free text. It generates a manual-review marker and is fatal only when the affected row lies in the final-query dependency closure.

## 3. Ovid `limit N to condition`

A complete row of the form:

```text
limit N to condition
```

is treated as an alias to source row `N` after the condition is intentionally ignored.

The LIMIT condition itself is not translated. This is an audited recall-broadening approximation.

### 3.1 Reference redirection

If a later source row references the ignored LIMIT row, that reference is redirected to the LIMIT row's resolved underlying source row before the LIMIT row is removed.

```text
1. asthma.tw.
2. wheeze.tw.
3. 1 or 2
4. limit 3 to humans
5. cancer.tw.
6. 4 and 5
```

becomes:

```text
#1 asthma[tw]
#2 wheeze[tw]
#3 #1 OR #2
#4 cancer[tw]
#5 #3 AND #4
```

### 3.2 Chained LIMIT aliases

Chained LIMIT aliases are resolved transitively to the first surviving source row.

### 3.3 Invalid LIMIT rows

A LIMIT base must refer to an existing prior source row. Undefined, forward, self-referential, malformed, or otherwise invalid LIMIT constructs are retained as manual-review defects rather than silently removed.

Under the existing active-query rule:

- an invalid LIMIT row inside the effective final-query dependency closure is fatal;
- an invalid LIMIT row completely outside that closure is retained as `warning_unused_line` and does not invalidate an independent final query.

### 3.4 Renumbering

When one or more valid LIMIT rows are removed, surviving output rows are renumbered consecutively from 1 and every line reference is rewritten consistently.

This v21 renumbering is triggered by valid LIMIT removal. Existing v20 behaviour for unrelated removals is otherwise preserved.

### 3.5 Final LIMIT row

If the final source row is a valid LIMIT row, ignoring its condition must preserve the LIMIT base as the effective final query. The converter must not simply choose the highest surviving source row.

Where necessary, a synthetic final no-op alias is emitted so the highest output row remains the retrieval row:

```text
1. asthma.tw.
2. cancer.tw.
3. limit 1 to humans
```

becomes:

```text
#1 asthma[tw]
#2 cancer[tw]
#3 #1
```

The synthetic alias is audited explicitly.

## 4. Wildcard-bearing quoted phrases

After PubMed field tags have been canonicalised, a safe quoted multi-word free-text phrase containing `*` is rendered by keeping the PubMed field tag attached to the phrase and placing grouping parentheses **outside the complete fielded expression**.

```text
"breast* cancer*"[Title/Abstract]
→ (breast* cancer*[tiab])

"renal failure*"[Text Word]
→ (renal failure*[tw])

"A* B* C*"[Text Word]
→ (A* B* C*[tw])
```

The approved canonical free-text tags for this rule are:

```text
[ti] [tiab] [tw] [all] [ta]
```

The rule deliberately preserves the internal spaces and does **not** insert Boolean separators between phrase tokens. It also does **not** duplicate the field tag across individual words.

Therefore:

```text
"A* B* C*"[tw]
```

must become:

```text
(A* B* C*[tw])
```

and must **not** become any of:

```text
(A* B* C*)[tw]
A* B* C*[tw]
A*[tw] AND B*[tw] AND C*[tw]
```

The distinction is intentional: the field tag remains part of the multi-term PubMed phrase syntax, while the outer parentheses group the already-fielded expression.

The transformation is audited as:

```text
wildcard_phrase_grouped_pubmed_phrase_tag_preserved:<phrase>[<tag>]
```

### 4.1 Literal Boolean-token protection

If a wildcard phrase reaching this stage still contains a literal standalone `OR`, `NOT`, or surviving `AND`, its quotes are retained so phrase text cannot be reinterpreted as PubMed Boolean syntax.

For example:

```text
"law or polic*".tw.
→ "law or polic*"[tw]
```

### 4.2 Inherited Ovid runtime-stopword behaviour

This protection does not override the established v20 free-text stopword rule, which runs earlier. In particular, Ovid runtime stopword `and` may already have been removed and the remaining content terms joined by Boolean `AND`.

The following is therefore accepted and intentional:

```text
"research and develop*".tw.
→ (research[tw] AND develop*[tw])
```

This is an inherited recall-oriented approximation, not a v21 defect.

## 5. Pure Ovid MEDLINE database-update date filters

Ovid MEDLINE `.ed.` and `.dt.` fields are record-processing/update dates rather than clinical search concepts. v21 therefore removes a whole row as database-update bookkeeping when all of the following are true:

1. the complete row ends in `.ed.`, `.dt.`, `.ed,dt.` or `.dt,ed.`;
2. the expression before the suffix contains only numeric date prefixes, optional `*`, parentheses, `OR`, and whitespace;
3. there are no clinical/search terms and no other fields.

Qualifying examples include:

```text
2022*.ed.
2022*.dt.
(2021* or 2022*).ed,dt.
(201107* or 201108* or 2012* or 2013*).dt,ed.
```

These rows are removed and must never be converted to free-text PubMed terms.

The base audit flag is:

```text
ovid_database_update_date_filter_ignored
```

### 5.1 External `End_date` supplied

When the source strategy has an external `End_date`, that metadata remains the retrieval-date boundary and the removed Ovid update-date row also carries:

```text
external_end_date_applied_instead_of_ovid_update_date_filter
```

### 5.2 No external `End_date`

The pure update-date row is still removed, but the loss of that source restriction is an intentional recall broadening and is audited with:

```text
ovid_update_date_filter_ignored_without_external_end_date
major_semantic_approximation_recall_broadened
```

### 5.3 Boolean dependency handling

The normal Cochrane update-search form is an `AND` wrapper:

```text
22. substantive clinical search
23. (...numeric dates...).ed,dt.
24. 22 and 23
```

After row 23 is removed, row 24 simplifies to the substantive row:

```text
#24 #22
```

This removal does **not** trigger consecutive renumbering. The surviving source row numbers are preserved unless a valid v21 LIMIT removal independently requires renumbering.

An `OR` or `NOT` reference to a removed update-date row is not treated as a normal filter wrapper and must not be silently simplified. Such a dependent row is marked for manual review with:

```text
ovid_update_date_reference_in_or_not_manual_review_required:#N
```

### 5.4 Mixed or non-numeric date-field expressions

A row such as:

```text
(cancer or 2022*).ed,dt.
```

is outside this rule and must not be silently discarded. Existing conversion/validation behavior applies.

## 6. Audit-row statuses added by v21

In addition to the v20 audit-row statuses, v21 uses:

```text
removed_ignored_ovid_limit
removed_ignored_ovid_update_date
```

A valid ignored LIMIT row also carries:

```text
major_semantic_approximation_recall_broadened
```

A removed pure update-date row carries `ovid_database_update_date_filter_ignored` plus the applicable End_date audit described above.

Invalid LIMIT rows and unsafe OR/NOT update-date dependencies remain reviewable rows rather than being silently discarded.

## 7. Regression requirements

A v21 implementation must regression-test at minimum:

- `freq=1` removal;
- `freq>1` removal and audit broadening;
- malformed `/freq` active versus unused behaviour;
- ordinary, chained, invalid, and final LIMIT rows;
- reference redirection through removed LIMIT rows;
- consecutive renumbering after LIMIT removal;
- unchanged v20 numbering when no valid LIMIT row is removed;
- wildcard phrases rendered as `(A* B* C*[xx])` with one phrase-level field tag inside the grouping parentheses;
- rejection by regression test of the invalid `(A* B* C*)[xx]` form;
- no inserted Boolean separators inside grouped wildcard phrases;
- literal Boolean words inside surviving wildcard phrases;
- inherited `"research and develop*" → (research AND develop*)` stopword behaviour;
- pure `.ed.`, `.dt.`, `.ed,dt.` and `.dt,ed.` numeric update-date removal;
- update-date removal with and without external `End_date`;
- CD005595-style `#concept AND #date` wrapper simplification;
- no renumbering caused solely by update-date removal;
- manual review for `OR`/`NOT` dependencies on removed update-date rows;
- mixed/non-numeric date-field expressions not silently discarded;
- final-query dependency closure and retrieval gating.

## 8. Frozen v21 decisions

The following are frozen for v21:

```text
/freq=1                         → remove as redundant
/freq=N, N>1                    → remove; audit recall broadening
malformed /freq                 → manual review
limit N to condition            → ignore condition; alias to N; audit broadening
valid LIMIT removal             → redirect references and consecutively renumber output
final LIMIT                      → preserve its resolved base as effective final query
"A* B* C*"[xx]                  → (A* B* C*[xx]) when safe
pure numeric .ed./.dt. row       → discard as database-update bookkeeping
pure numeric .ed,dt./.dt,ed. row → discard as database-update bookkeeping
#concept AND #date               → simplify to #concept
#concept OR/NOT #date            → manual review
```

For wildcard phrases, the field tag remains attached to the multi-term phrase inside the outer parentheses. For update-date rows, removal alone does not renumber surviving rows.

Automatic numbering of wholly unnumbered multi-row input is deliberately outside the v21 ruleset and may be implemented separately by the online converter/input-adapter layer.

# Cochrane Ovid MEDLINE-to-PubMed Conversion Rules — v21

**Ruleset:** v21  
**Date:** 21 August 2026  
**Base specification:** v20  
**Status:** approved v21 delta specification.

v21 preserves every approved v20 rule except where this document explicitly overrides it. The v20 rule document therefore remains the normative base specification and this document is read together with it.

## 1. Scope of v21

v21 adds four narrowly scoped behaviours:

1. Ovid `/freq=N` occurrence-frequency modifiers;
2. whole-row Ovid `limit N to ...` constructs;
3. robust PubMed handling of quoted wildcard-bearing free-text phrases;
4. consequential row-reference rewriting and renumbering required by ignored LIMIT rows.

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

This v21 renumbering is triggered by valid LIMIT removal. Existing v20 behaviour for unrelated removals, including the pure `.ed,dt.` rule, is otherwise preserved.

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

After PubMed field tags have been canonicalised, a safe quoted multi-word free-text phrase containing `*` may have its quotation marks removed while retaining a single phrase-level field tag.

```text
"breast* cancer*"[Title/Abstract]
→ breast* cancer*[tiab]

"renal failure*"[Text Word]
→ renal failure*[tw]
```

The approved canonical free-text tags for this rule are:

```text
[ti] [tiab] [tw] [all] [ta]
```

This is preferred to splitting the phrase into separately fielded Boolean atoms because PubMed supports wildcard phrase searching with a trailing field tag, and the phrase-level form better preserves source semantics.

### 4.1 Literal Boolean-token protection

If a wildcard phrase reaching this stage still contains a literal standalone `OR`, `NOT`, or surviving `AND`, its quotes are retained so phrase text cannot be reinterpreted as PubMed Boolean syntax.

### 4.2 Inherited Ovid runtime-stopword behaviour

This protection does not override the established v20 free-text stopword rule, which runs earlier. In particular, Ovid runtime stopword `and` may already have been removed and the remaining content terms joined by Boolean `AND`.

The following is therefore accepted and intentional:

```text
"research and develop*".tw.
→ (research[tw] AND develop*[tw])
```

This is an inherited recall-oriented approximation, not a v21 defect.

## 5. Audit-row statuses added by v21

In addition to the v20 audit-row statuses, v21 uses:

```text
removed_ignored_ovid_limit
removed_ignored_ovid_update_date
```

A valid ignored LIMIT row also carries the semantic-broadening audit flag:

```text
major_semantic_approximation_recall_broadened
```

Invalid LIMIT rows are not labelled as ignored; they remain reviewable rows.

## 6. Regression requirements

A v21 implementation must regression-test at minimum:

- `freq=1` removal;
- `freq>1` removal and audit broadening;
- malformed `/freq` active versus unused behaviour;
- ordinary, chained, invalid, and final LIMIT rows;
- reference redirection through removed LIMIT rows;
- consecutive renumbering after LIMIT removal;
- unchanged v20 numbering when no valid LIMIT row is removed;
- wildcard phrases with canonical and readable field tags;
- literal Boolean words inside surviving wildcard phrases;
- inherited `"research and develop*" → (research AND develop*)` stopword behaviour;
- final-query dependency closure and retrieval gating.

## 7. Frozen v21 decisions

The following are frozen for v21:

```text
/freq=1              → remove as redundant
/freq=N, N>1         → remove; audit recall broadening
malformed /freq      → manual review
limit N to condition → ignore condition; alias to N; audit broadening
valid LIMIT removal  → redirect references and consecutively renumber output
final LIMIT           → preserve its resolved base as effective final query
"A* B*"[xx]          → A* B*[xx] when safe, not A*[xx] AND B*[xx]
```

Automatic numbering of wholly unnumbered multi-row input is deliberately outside the v21 ruleset and may be implemented separately by the online converter/input-adapter layer.

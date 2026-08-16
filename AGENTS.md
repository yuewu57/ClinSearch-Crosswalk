# AGENTS.md

## Project authority

`docs/cochrane_ovid_pubmed_conversion_rules_v20.md` is the normative
specification for conversion semantics.

Do not modify conversion behaviour merely to simplify implementation.

If code and specification disagree, report the discrepancy and add a regression
test before changing behaviour.

## Core invariant

The converter is deterministic, recall-oriented and auditable.

No source concept may be silently deleted.

All material approximations, fallbacks and omissions must be auditable.

A `validation_failed` or `manual_review_required` result must never be presented
as a validated PubMed query.

## Development rules

Preserve the Python conversion engine as the reference implementation.

Keep web/UI code separate from conversion logic.

Run the complete test suite after any conversion-rule change.

Add a regression test for every bug fix.

Do not introduce fuzzy MeSH matching.

Use cache-first exact MeSH resolution with safe source-heading fallback.

Do not expose arbitrary filesystem paths through the web interface.

Do not store uploaded user strategies.

## Definition of done

A change is complete only when:

- tests pass;
- existing validated outputs have not regressed;
- new behaviour is covered by tests;
- audit behaviour remains intact;
- documentation is updated where necessary.

# Browser appearance update

The browser preview now uses the complete **ClinSearch-CrossWalk** wordmark at
one bold weight. Both conversion symbols (header and empty output state) point
right, from Ovid MEDLINE to PubMed. No reverse-conversion control is offered.

The teal/green palette is replaced by blue accents, a white/slate light theme,
and a navy/slate dark theme. Amber warnings and red failures retain their
meaning in both themes. Theme changes never alter or rerun conversion.

The header's **Theme** selector offers **System**, **Light**, and **Dark**.
System follows the device colour preference, including changes while the page
is open. Explicit light/dark choices are saved locally under
`clinsearch-crosswalk-theme`; choosing System removes that override. This is
appearance-only storage: no strategy, result or identifier is stored. If
browser storage is denied, the selector still works for the current page.

This update changes presentation only. The reference Python modules, worker,
cache, audit logic and validation gates are unchanged. It neither publishes the
site nor changes the repository licence or visibility.

`browser/e2e/appearance.spec.ts` checks the wordmark, one-way arrows, system and
manual themes, storage-denial handling, query/audit stability, failure gating,
and narrow layouts. It also captures real light/dark desktop and mobile
screenshots. Run the complete browser CI before release; the empty production
MeSH starter cache and real-corpus release checks remain separate requirements.

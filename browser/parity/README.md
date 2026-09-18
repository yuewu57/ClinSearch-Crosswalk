# Python ↔ TypeScript parity baseline

These fixtures freeze externally observable conversion behaviour before the TypeScript port is allowed to become a public converter.

The baseline is the `main` commit recorded in `docs/browser_port_plan.md`. Fixtures are derived from the repository's regression and v21 unit tests, not from re-interpreting the rules during the TypeScript port.

Parity is evaluated on material behaviour: translated numbered rows, final-query identity, one-line executable query, validation status, dependency-sensitive failures, and material audit flags. Formatting-only differences should be approved explicitly rather than silently normalised away.

The browser implementation must not be presented as validated until these fixtures and the broader regression corpus pass against both implementations.

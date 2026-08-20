# Deployment architecture

Que² is the parent visual brand for the Evidentia-CSC: a Clinical Search Convertor. Deployment
keeps the public presentation layer separate from the existing interactive application
and deterministic Python conversion core.

## Static landing page — GitHub Pages

The dependency-free files in `site/` are a landing-page skeleton suitable for GitHub
Pages. Pages is not enabled by this repository change, and no deployment workflow runs
automatically. When the repository owner is ready to publish it:

1. configure the actual hosted converter URL once in `site/config.js`;
2. choose a Pages publishing source or add a reviewed Pages workflow that publishes
   `site/`; and
3. enable GitHub Pages in the repository settings and verify repository-relative links
   under the selected Pages base path.

GitHub Pages serves HTML, CSS, JavaScript, and other static assets. It does **not** run a
Python process or the Streamlit server, so it cannot host the interactive converter
backend itself.

## Interactive converter — Streamlit/current Python hosting

The current interactive product remains `web/app.py`, served by Streamlit on Python-capable
hosting. Streamlit presents pasted-strategy and RTF-upload workflows and delegates through
the web-service adapter to the `ovid_pubmed_converter` core. The static landing page links
to this separately deployed application after its URL is configured.

The intended layering is:

```text
Streamlit UI (`web/app.py`)
    ↓
web-service adapter (`ovid_pubmed_converter.web_service`)
    ↓
deterministic converter core (`ovid_pubmed_converter`)
```

A future migration may replace or supplement Streamlit with a static JavaScript frontend
calling an authenticated HTTP API backed by the same Python core. That API/frontend
migration is not implemented here; it would require separate security, privacy, hosting,
and operational design before the browser could submit strategies to it.

# Static Que² / Evidentia landing page

This directory contains dependency-free static files suitable for a future GitHub Pages
site. It is deliberately separate from the Streamlit application and Python conversion
engine.

Before deployment, set `converterUrl` in `config.js` to the real hosted Streamlit
application URL. Until it is configured, **Launch Convertor** remains visibly disabled;
no production URL is assumed or fabricated.

For local review, serve the repository root (so the relative documentation links work):

```console
python -m http.server 8000
```

Then open `http://localhost:8000/site/`.

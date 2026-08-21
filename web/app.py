"""Streamlit entry point for the public converter."""

from base64 import b64encode
from pathlib import Path

import streamlit as st

from ovid_pubmed_converter import RULESET_VERSION, __version__
from ovid_pubmed_converter.mesh import production_cache_path
from ovid_pubmed_converter.rtf import MAX_RTF_BYTES
from ovid_pubmed_converter.web_service import (
    convert_paste,
    convert_rtf,
    download_payloads,
    has_eligible_update_date_construct,
    user_facing_validation_error,
    user_facing_warning,
)
from web.branding import (
    AFFILIATION_LABEL,
    FUNCTIONAL_SUBTITLE,
    PRODUCT_NAME,
    QUE2_LOGO_PATH,
    STRATHCLYDE_LOGO_PATH,
)

_CACHE_PATH = production_cache_path()
_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "resources" / "rtf_input_template.rtf"


def _image_data_uri(path: Path, mime_type: str) -> str:
    """Return the original image bytes as a browser data URI without resizing."""
    encoded = b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


_QUE2_LOGO_URI = _image_data_uri(QUE2_LOGO_PATH, "image/png")
_STRATHCLYDE_LOGO_URI = _image_data_uri(STRATHCLYDE_LOGO_PATH, "image/jpeg")

st.set_page_config(
    page_title="Evidentia-CSC: a Clinical Search Convertor",
    page_icon="🔎",
    layout="wide",
)
st.markdown(
    f"""
    <style>
    h1 {{
        font-family: Skia, "Avenir Next", "Segoe UI", sans-serif !important;
        font-weight: 500 !important;
        letter-spacing: -0.02em;
    }}
    .evidentia-brand-row {{
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 2rem;
        margin: 0 0 0.8rem;
        width: 100%;
    }}
    .evidentia-primary-brand img {{
        display: block;
        width: 210px;
        max-width: 34vw;
        height: auto;
        image-rendering: auto;
    }}
    .evidentia-affiliation {{
        margin-left: auto;
        text-align: right;
    }}
    .evidentia-affiliation-label {{
        margin: 0 0 0.35rem;
        color: #808495;
        font-size: 0.78rem;
        font-weight: 500;
        line-height: 1.2;
    }}
    .evidentia-affiliation img {{
        display: block;
        width: 135px;
        max-width: 25vw;
        height: auto;
        margin-left: auto;
        image-rendering: auto;
    }}
    @media (max-width: 700px) {{
        .evidentia-brand-row {{
            gap: 1rem;
        }}
        .evidentia-primary-brand img {{
            width: 175px;
            max-width: 48vw;
        }}
        .evidentia-affiliation img {{
            width: 115px;
            max-width: 34vw;
        }}
        .evidentia-affiliation-label {{
            font-size: 0.7rem;
        }}
    }}
    </style>
    <div class="evidentia-brand-row">
      <div class="evidentia-primary-brand">
        <img
          src="{_QUE2_LOGO_URI}"
          alt="QueSquared — Intelligence Compounded"
        >
      </div>
      <div class="evidentia-affiliation">
        <div class="evidentia-affiliation-label">{AFFILIATION_LABEL}</div>
        <img
          src="{_STRATHCLYDE_LOGO_URI}"
          alt="University of Strathclyde Glasgow"
        >
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.title(PRODUCT_NAME)
st.subheader(FUNCTIONAL_SUBTITLE)
st.caption(f"Software {__version__} · Conversion ruleset {RULESET_VERSION}")
st.info(
    "Deterministic, recall-oriented conversion. "
    "Review all warnings before retrieval."
)
st.warning(
    "Ovid LIMIT and /freq constraints are detected and audited, but their Ovid "
    "restriction semantics are not reproduced automatically in PubMed."
)
with st.expander("Important: how Ovid LIMIT and /freq are handled", expanded=True):
    st.markdown(
        "- **`limit N to ...`**: Evidentia keeps the underlying search represented by row "
        "`N`, omits the LIMIT condition, redirects later references to the base row, and "
        "renumbers surviving rows where required. After running the converted query in "
        "PubMed, apply a relevant PubMed filter **where an equivalent exists** — for example "
        "age, publication date/year, or language. Some Ovid limits do not have an exact "
        "PubMed equivalent.\n"
        "- **`/freq=1`**: removed as redundant. **`/freq=N` for `N > 1`**: the occurrence-"
        "frequency requirement is removed, so retrieval is intentionally broader. PubMed "
        "filters do not reproduce this term-frequency requirement.\n"
        "- These changes are recorded in the line-by-line audit. Review them before using "
        "the final search for evidence retrieval."
    )

with st.expander("About / Technical details"):
    st.write(f"Software version: {__version__}")
    st.write(f"Conversion ruleset: {RULESET_VERSION}")
    st.write(f"MeSH cache: {_CACHE_PATH.name}")
    st.write("MeSH mode: bundled cache → exact NLM lookup → audited fallback")

paste_tab, rtf_tab = st.tabs(["Paste strategy", "Upload RTF"])
with paste_tab:
    pasted = st.text_area(
        "Ovid MEDLINE strategy",
        height=300,
        placeholder="1 exp Asthma/\n2 asthma.tw.\n3 1 or 2",
    )
    end_date = None
    if has_eligible_update_date_construct(pasted):
        with st.expander("Advanced options"):
            end_date = st.text_input(
                "External source-search end date",
                help=(
                    "Used only for handling eligible Ovid .ed,dt. update-date lines. "
                    "This does not add a publication-date restriction to the PubMed query."
                ),
            )
    if st.button("Convert", type="primary"):
        st.session_state.conversion_result = convert_paste(pasted, end_date)
        st.session_state.conversion_was_rtf = False

with rtf_tab:
    st.write("Upload an Ovid MEDLINE search strategy (.rtf).")
    st.markdown(
        "**Preferred input:** an Ovid RTF with visible strategy line numbers.\n\n"
        "Supported:\n"
        "- a standalone **numbered** Ovid strategy; or\n"
        '- an RTF containing an explicit **"Medline:"** section.\n\n'
        "If a `Medline:` section is present but its line numbers are missing, Evidentia will "
        "only reconstruct `1, 2, 3, ...` when every extracted paragraph looks like a complete "
        "Ovid search row. The recovery is flagged for review. Ambiguous unnumbered RTFs are "
        "rejected rather than guessed. A standalone RTF without a `Medline:` heading must "
        "remain numbered."
    )
    st.download_button(
        "Download example RTF template",
        _TEMPLATE_PATH.read_bytes(),
        "ovid_medline_input_template.rtf",
        "application/rtf",
    )
    upload = st.file_uploader(
        "Upload one RTF file",
        type=["rtf"],
        help=f"Maximum {MAX_RTF_BYTES // 1024 // 1024} MB",
    )
    if st.button("Convert uploaded RTF", type="primary") and upload is not None:
        try:
            st.session_state.conversion_result = convert_rtf(upload.getvalue())
            st.session_state.conversion_was_rtf = True
        except ValueError as exc:
            st.error(f"RTF rejected: {exc}")

result = st.session_state.get("conversion_result")
if result is not None:
    include_rtf = st.session_state.get("conversion_was_rtf", False)
    payloads = download_payloads(result, include_rtf=include_rtf)

    st.header("PubMed strategy")
    output = payloads["pubmed_strategy.txt"].decode("utf-8")
    st.code(output, language=None)
    st.caption("Use the copy control in the code block to copy the full strategy.")

    st.header("Final query")
    st.code(result.final_query or "No executable final query", language=None)
    st.caption("Use the copy control in the code block to copy the final query.")

    st.header("Validation")
    if result.validation_status.value == "ok":
        st.success("Validation passed")
    elif result.validation_status.value == "manual_review_required":
        st.warning("Manual review required — this is not a validated PubMed query.")
    else:
        st.error("Validation failed — this is not a validated PubMed query.")
    for error in result.validation_errors:
        st.write(f"- {user_facing_validation_error(error)}")

    if result.warnings:
        st.warning("Review the following conversion/input warnings before retrieval:")
        for warning in result.warnings:
            st.write(f"- {user_facing_warning(warning)}")

    with st.expander(
        "Translation notes / line-by-line audit",
        expanded=result.validation_status.value != "ok",
    ):
        for row in result.rows:
            st.markdown(f"**Line {row.number} — {row.validation_status}**")
            st.code(
                f"Ovid: {row.original}\nPubMed: {row.converted or '[removed]'}",
                language=None,
            )
            for flag in row.audit_flags:
                st.write(f"- {flag}")

    st.header("Downloads")
    left, middle, right = st.columns(3)
    left.download_button(
        "TXT",
        payloads["pubmed_strategy.txt"],
        "pubmed_strategy.txt",
        "text/plain",
    )
    middle.download_button(
        "Audit CSV",
        payloads["pubmed_audit.csv"],
        "pubmed_audit.csv",
        "text/csv",
    )
    right.download_button(
        "Validation report",
        payloads["pubmed_validation.json"],
        "pubmed_validation.json",
        "application/json",
    )
    if include_rtf:
        st.download_button(
            "Converted RTF",
            payloads["pubmed_strategy.rtf"],
            "pubmed_strategy.rtf",
            "application/rtf",
        )

st.divider()
st.caption(
    "No account or database is used. Uploaded strategies are processed for the current "
    "session and are not intentionally retained. Only controlled-heading labels requiring "
    "exact resolution may be sent to NLM."
)

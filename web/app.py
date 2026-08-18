"""Streamlit entry point for the public converter."""

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
)
from web.branding import BRAND_NAME, FUNCTIONAL_SUBTITLE, PRODUCT_NAME

_CACHE_PATH = production_cache_path()
_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "resources" / "rtf_input_template.rtf"

st.set_page_config(
    page_title="Evidentia Search Strategy Convertor",
    page_icon="🔎",
    layout="wide",
)
st.caption(BRAND_NAME)
st.title(PRODUCT_NAME)
st.subheader(FUNCTIONAL_SUBTITLE)
st.caption(f"Software {__version__} · Conversion ruleset {RULESET_VERSION}")
st.info("Deterministic, recall-oriented conversion. Review all warnings before retrieval.")

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
        "Supported:\n"
        "- an RTF containing a standalone numbered Ovid strategy; or\n"
        '- an RTF containing an explicit "Medline:" section.'
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

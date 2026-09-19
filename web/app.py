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
    user_facing_validation_error,
    user_facing_warning,
)
from web.branding import FUNCTIONAL_SUBTITLE, INSTITUTIONAL_AFFILIATION, PRODUCT_NAME

_CACHE_PATH = production_cache_path()
_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "resources" / "rtf_input_template.rtf"
_LICENSE_PATH = Path(__file__).resolve().parents[1] / "LICENSE"
_REPOSITORY_URL = "https://github.com/yuewu57/ClinSearchBridge"

st.set_page_config(
    page_title=PRODUCT_NAME,
    page_icon="🔎",
    layout="wide",
)

# Public presentation deliberately does not load or render company/institution logos.
st.title(PRODUCT_NAME)
st.subheader(FUNCTIONAL_SUBTITLE)
st.caption(f"Software {__version__} · Conversion ruleset {RULESET_VERSION}")
st.caption(
    "Source available under PolyForm Noncommercial 1.0.0. "
    "See About / Technical details for permitted uses, citation and licensing."
)
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
        "- **`limit N to ...`**: ClinSearchBridge keeps the underlying search represented by row "
        "`N`, omits the LIMIT condition, redirects later references to the base row, and "
        "renumbers surviving rows where required. After running the converted query in "
        "PubMed, apply a relevant PubMed filter **where an equivalent exists** — for example "
        "age, publication date/year, or language. Some Ovid limits do not have an exact "
        "PubMed equivalent.\n"
        "- **`/freq=1`**: removed as redundant. **`/freq=N` for `N > 1`**: the occurrence-"
        "frequency requirement is removed, so retrieval is intentionally broader. PubMed "
        "filters do not reproduce this term-frequency requirement.\n"
        "- Pure numeric Ovid database-update date rows using **`.ed.`**, **`.dt.`**, "
        "**`.ed,dt.`**, or **`.dt,ed.`** are discarded automatically under v21 and recorded "
        "in the line-by-line audit. No end-date input is required in the online converter.\n"
        "- Review all audited approximations before using the final search for evidence "
        "retrieval."
    )

with st.expander("About / Technical details"):
    st.write(f"Software version: {__version__}")
    st.write(f"Conversion ruleset: {RULESET_VERSION}")
    st.write(f"MeSH cache: {_CACHE_PATH.name}")
    st.write("MeSH mode: bundled cache → exact NLM lookup → audited fallback")
    st.write("Part of ClinSearchBridge. Developed by the ClinSearchBridge contributors.")
    st.write(f"Institutional affiliation: {INSTITUTIONAL_AFFILIATION}")
    st.markdown(
        f"[Source code]({_REPOSITORY_URL}) · "
        f"[Cite this software]({_REPOSITORY_URL}/blob/main/CITATION.cff) · "
        f"[Licensing notes]({_REPOSITORY_URL}/blob/main/docs/licensing.md)"
    )
    st.write(
        "Use is governed by the PolyForm Noncommercial License 1.0.0, including "
        "its expressly permitted organisations. Uses outside its permitted purposes "
        "require a separate licence from the relevant rights-holder."
    )
    st.download_button("Download software licence", _LICENSE_PATH.read_bytes(),
                       "LICENSE", "text/plain")
    st.write("The associated paper and archived release will be linked when available.")

st.caption("Enter search strategies only. Do not upload patient, personal or confidential data.")
paste_tab, rtf_tab = st.tabs(["Paste strategy", "Upload RTF"])
with paste_tab:
    pasted = st.text_area(
        "Ovid MEDLINE strategy",
        height=300,
        placeholder="1 exp Asthma/\n2 asthma.tw.\n3 1 or 2",
    )
    if st.button("Convert", type="primary"):
        st.session_state.conversion_result = convert_paste(pasted)
        st.session_state.conversion_was_rtf = False

with rtf_tab:
    st.write("Upload an Ovid MEDLINE search strategy (.rtf).")
    st.markdown(
        "**Preferred input:** an Ovid RTF with visible strategy line numbers.\n\n"
        "Supported:\n"
        "- a standalone **numbered** Ovid strategy; or\n"
        '- an RTF containing an explicit **"Medline:"** section.\n\n'
        "If a `Medline:` section is present but its line numbers are missing, ClinSearchBridge will "
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

    st.header("Full-line PubMed conversion")
    output = payloads["pubmed_strategy.txt"].decode("utf-8")
    st.code(output, language=None)
    st.caption(
        "Use this full line-by-line conversion if you want to retain the translated search-set "
        "structure and line references."
    )

    st.header("One-line PubMed conversion")
    query = payloads["pubmed_query.txt"].decode("utf-8").strip()
    st.code(query or "No executable one-line query", language=None)
    if query:
        st.caption(
            "Use this fully expanded version if you want a single copy-ready PubMed query. "
            "It contains no ClinSearchBridge line references; review any conversion warnings and "
            "apply relevant PubMed filters before retrieval."
        )

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
    strategy_col, query_col, audit_col, validation_col = st.columns(4)
    strategy_col.download_button(
        "Full-line conversion",
        payloads["pubmed_strategy.txt"],
        "pubmed_strategy.txt",
        "text/plain",
    )
    query_col.download_button(
        "One-line conversion",
        payloads["pubmed_query.txt"],
        "pubmed_query.txt",
        "text/plain",
    )
    audit_col.download_button(
        "Audit CSV",
        payloads["pubmed_audit.csv"],
        "pubmed_audit.csv",
        "text/csv",
    )
    validation_col.download_button(
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

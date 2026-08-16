"""Streamlit entry point for the public converter."""

import streamlit as st

from ovid_pubmed_converter import __version__
from ovid_pubmed_converter.core import convert_strategy
from ovid_pubmed_converter.outputs import audit_csv, converted_rtf, strategy_text, validation_report
from ovid_pubmed_converter.parser import parse_strategy_text
from ovid_pubmed_converter.rtf import MAX_RTF_BYTES, parse_rtf_bytes

st.set_page_config(page_title="Ovid MEDLINE → PubMed Converter", page_icon="🔎", layout="wide")
st.title("Ovid MEDLINE → PubMed Converter")
st.caption(f"Converter version: v20 ({__version__}) · MeSH mode: cache-only safe fallback")
st.info("Deterministic, recall-oriented conversion. Review all warnings before retrieval.")

paste_tab, rtf_tab = st.tabs(["Paste strategy", "Upload RTF"])
strategy = None
is_rtf = False
with paste_tab:
    pasted = st.text_area("Paste Ovid MEDLINE search strategy", height=300, placeholder="1 exp Asthma/\n2 asthma.tw.\n3 1 or 2")
    end_date = st.text_input("Optional End date", help="Used for the v20 pure .ed,dt. update-line rule.")
    paste_convert = st.button("Convert pasted strategy", type="primary")
    if paste_convert:
        strategy = parse_strategy_text(pasted, end_date=end_date)
with rtf_tab:
    upload = st.file_uploader("Upload one RTF file", type=["rtf"], help=f"Maximum {MAX_RTF_BYTES // 1024 // 1024} MB")
    rtf_convert = st.button("Convert uploaded RTF", type="primary")
    if rtf_convert and upload is not None:
        try:
            strategy = parse_rtf_bytes(upload.getvalue())
            is_rtf = True
        except ValueError as exc:
            st.error(f"RTF rejected: {exc}")

if strategy is not None:
    result = convert_strategy(strategy)
    st.header("PubMed strategy")
    output = strategy_text(result)
    st.code(output, language=None)
    st.header("Final query")
    st.code(result.final_query or "No executable final query", language=None)
    st.header("Validation")
    if result.validation_status.value == "ok":
        st.success("Validation passed")
    elif result.validation_status.value == "manual_review_required":
        st.warning("Manual review required — this is not a validated PubMed query.")
    else:
        st.error("Validation failed — this is not a validated PubMed query.")
    for error in result.validation_errors:
        st.write(f"- {error}")
    with st.expander("Translation notes / line-by-line audit", expanded=result.validation_status.value != "ok"):
        for row in result.rows:
            st.markdown(f"**Line {row.number} — {row.validation_status}**")
            st.code(f"Ovid: {row.original}\nPubMed: {row.converted or '[removed]'}", language=None)
            for flag in row.audit_flags:
                st.write(f"- {flag}")
    st.header("Downloads")
    left, middle, right = st.columns(3)
    left.download_button("TXT", output, "pubmed_strategy.txt", "text/plain")
    middle.download_button("Audit CSV", audit_csv(result), "pubmed_audit.csv", "text/csv")
    right.download_button("Validation report", validation_report(result), "pubmed_validation.json", "application/json")
    if is_rtf:
        st.download_button("Converted RTF", converted_rtf(result), "pubmed_strategy.rtf", "application/rtf")

st.divider()
st.caption("No account or database is used. Uploaded strategies are processed for the current session and are not intentionally retained.")

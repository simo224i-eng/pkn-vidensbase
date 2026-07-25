import streamlit as st

st.set_page_config(
    page_title="Ejnar – Ejerskifteforsikring",
    page_icon=":material/home_work:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared import inject_css, logo
from retrieval_runtime import install_retrieval_runtime
from paragraph_runtime import install_paragraph_runtime
from metadata_runtime import install_metadata_runtime
from citation_runtime import install_citation_runtime

install_retrieval_runtime()
install_paragraph_runtime()
install_metadata_runtime()
install_citation_runtime()
inject_css()

# ── Global adgangskodegate ────────────────────────────────────────────────────
if not st.session_state.get("_autentificeret_ejnar"):
    st.markdown(
        f"<div style='text-align:center;margin-top:6rem;margin-bottom:0.4rem;'>{logo(140)}</div>"
        "<p style='text-align:center;color:#94a3b8;font-size:11px;letter-spacing:0.6px;"
        "text-transform:uppercase;font-weight:500;margin-bottom:3rem;'>Ejerskifteforsikring · "
        "Ankenævnet for Forsikrings praksis</p>",
        unsafe_allow_html=True,
    )
    col = st.columns([1.2, 1, 1.2])[1]
    with col:
        pw = st.text_input("Adgangskode", type="password", placeholder="Indtast adgangskode…")
        if st.button("Log ind", use_container_width=True, type="primary"):
            korrekt = st.secrets.get("APP_PASSWORD", "")
            if not korrekt:
                st.error("Adgangskode ikke konfigureret. Tilføj APP_PASSWORD i Streamlit secrets.")
            elif pw == korrekt:
                st.session_state["_autentificeret_ejnar"] = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
    st.stop()

pg = st.navigation([
    st.Page("pages/home.py", title="Forside", default=True),
    st.Page("pages/ejnar.py", title="Ejerskifteforsikring"),
])
pg.run()

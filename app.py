import streamlit as st

st.set_page_config(
    page_title="Harald – Juridisk Vidensbase",
    page_icon=":material/balance:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared import inject_css, logo
inject_css()

# ── Global adgangskodegate ────────────────────────────────────────────────────
if not st.session_state.get("_autentificeret_v2"):
    st.markdown(
        f"<div style='text-align:center;margin-top:6rem;margin-bottom:0.4rem;'>{logo(140)}</div>"
        "<p style='text-align:center;color:#94a3b8;font-size:11px;letter-spacing:0.6px;"
        "text-transform:uppercase;font-weight:500;margin-bottom:3rem;'>Juridisk vidensbase</p>",
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
                st.session_state["_autentificeret_v2"] = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
    st.stop()

pg = st.navigation([
    st.Page("pages/home.py",       title="Forside",             default=True),
    st.Page("pages/pkn.py",        title="Planklagenævnet"),
    st.Page("pages/mfkn.py",       title="Miljøklagenævnet"),
    st.Page("pages/sagsmappe.py",  title="Sagsmappe"),
])
pg.run()


import streamlit as st

st.set_page_config(
    page_title="Harald – Juridisk Vidensbase",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared import inject_css
inject_css()

# ── Global adgangskodegate ────────────────────────────────────────────────────
if not st.session_state.get("_autentificeret"):
    st.markdown(
        "<h2 style='font-family:Cinzel,Georgia,serif;letter-spacing:4px;"
        "text-align:center;margin-top:4rem;color:#1a0a0e;'>HARALD</h2>"
        "<p style='text-align:center;color:#94a3b8;margin-bottom:2rem;'>Juridisk Vidensbase</p>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        pw = st.text_input("Adgangskode", type="password", placeholder="Indtast adgangskode…")
        if st.button("Log ind →", use_container_width=True):
            if pw == "B465545":
                st.session_state["_autentificeret"] = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
    st.stop()

pg = st.navigation([
    st.Page("pages/home.py",                     title="Forside",            icon=":material/home:",    default=True),
    st.Page("pages/pkn.py",                      title="Planklagenævnet",    icon=":material/gavel:"),
    st.Page("pages/mfkn_beskyttelseslinjer.py",  title="Beskyttelseslinjer", icon=":material/eco:"),
    st.Page("pages/mfkn_naturtyper.py",          title="Naturtyper",         icon=":material/park:"),
])
pg.run()


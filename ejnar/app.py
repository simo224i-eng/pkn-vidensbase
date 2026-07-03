import streamlit as st

st.set_page_config(
    page_title="Ejnar – Ejerskifteforsikring",
    page_icon=":material/home_work:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared import inject_css, logo
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
    st.markdown("""
<style>
[data-testid="stForm"] {
    background: #ffffff; border: 1px solid #e2e8f0 !important; border-radius: 14px !important;
    padding: 1.6rem 1.6rem 1.2rem !important; box-shadow: 0 10px 40px rgba(15,23,42,.06);
}
</style>""", unsafe_allow_html=True)
    col = st.columns([1.2, 1, 1.2])[1]
    with col:
        # Form → Enter-tasten logger ind (før krævede det klik på knappen)
        with st.form("login_form", border=False):
            pw = st.text_input("Adgangskode", type="password",
                               placeholder="Indtast adgangskode…",
                               label_visibility="collapsed")
            log_ind = st.form_submit_button("Log ind →", use_container_width=True,
                                            type="primary")
        if log_ind:
            korrekt = st.secrets.get("APP_PASSWORD", "")
            if not korrekt:
                st.error("Adgangskode ikke konfigureret. Tilføj APP_PASSWORD i Streamlit secrets.")
            elif pw == korrekt:
                st.session_state["_autentificeret_ejnar"] = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
        st.markdown(
            "<p style='text-align:center;color:#cbd5e1;font-size:10.5px;margin-top:1rem;'>"
            "Adgang kræver kode · kontakt administratoren</p>",
            unsafe_allow_html=True,
        )
    st.stop()

pg = st.navigation([
    st.Page("pages/home.py", title="Forside", default=True),
    st.Page("pages/ejnar.py", title="Ejerskifteforsikring"),
])
pg.run()

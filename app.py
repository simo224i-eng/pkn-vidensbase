import streamlit as st

st.set_page_config(
    page_title="Harald – Juridisk Vidensbase",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

from shared import inject_css
inject_css()

pg = st.navigation([
    st.Page("pages/home.py",                     title="Forside",                   icon="🏛️", default=True),
    st.Page("pages/pkn.py",                      title="PKN — Planklagenævnet",     icon="⚖️"),
    st.Page("pages/mfkn_beskyttelseslinjer.py",  title="MFKN — Beskyttelseslinjer", icon="🌿"),
])
pg.run()

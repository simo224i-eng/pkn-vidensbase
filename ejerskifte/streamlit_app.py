"""
Streamlit-wrapper, så ejerskifte-arbejdsredskabet (det selvstændige HTML-værktøj
i tools/ejerskifte_arbejdsredskab.html) kan deployes på Streamlit Cloud.

Værktøjet er én selvstændig HTML-fil (al CSS/JS/SVG er inline), så vi indlejrer
den blot i fuld bredde. Main file path ved deploy: ejerskifte/streamlit_app.py
"""
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Ejerskifteforsikring – arbejdsredskab",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Fjern Streamlit-chrome og -margener, så værktøjet fylder hele fladen
st.markdown(
    """
    <style>
      #MainMenu, header, footer {visibility: hidden;}
      .block-container {padding: 0 !important; max-width: 100% !important;}
      [data-testid="stAppViewBlockContainer"] {padding: 0 !important;}
      [data-testid="stHeader"] {height: 0 !important;}
    </style>
    """,
    unsafe_allow_html=True,
)

# Læs HTML-værktøjet (én kilde — samme fil som telefon-linket bruger)
_html_path = Path(__file__).resolve().parent.parent / "tools" / "ejerskifte_arbejdsredskab.html"
html = _html_path.read_text(encoding="utf-8")

# Indlejr i fuld højde. Værktøjet har sin egen scroll til lange faner.
components.html(html, height=2600, scrolling=True)

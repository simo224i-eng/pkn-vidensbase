import streamlit as st
from shared import logo, inject_css

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")

inject_css()

st.markdown("""
<style>
/* Page-link knapper på forsiden */
[data-testid="stPageLink"] { margin-top: -2px !important; }
[data-testid="stPageLink"] a {
    display: flex !important; align-items: center; justify-content: center; gap: 6px;
    width: 100%; padding: 11px 16px !important;
    background: #fdf8f2 !important; color: #7a5a30 !important;
    border-radius: 0 0 14px 14px !important;
    font-size: 11px !important; font-weight: 700 !important;
    letter-spacing: 1.5px !important; text-transform: uppercase !important;
    text-decoration: none !important;
    border: 1px solid #ddd4c8 !important; border-top: none !important;
    transition: background .15s, color .15s, border-color .15s !important;
}
[data-testid="stPageLink"] a:hover {
    background: #c49a3c !important; color: #fff !important;
    border-color: #c49a3c !important;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(f'<div style="text-align:center;padding:1.5rem 0 0.5rem;">{logo(110)}</div>',
                unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:3.5rem 0 3rem;">
  {logo(120)}
  <div style="font-family:'Cinzel',Georgia,serif;font-size:2.4rem;font-weight:900;
              color:#0f172a;letter-spacing:10px;margin:1.8rem 0 0.6rem;
              text-shadow:0 1px 0 rgba(255,255,255,.6);">Harald</div>
  <div style="height:2px;width:36px;background:#c49a3c;border-radius:1px;
              margin:0 auto 1.1rem;"></div>
  <div style="font-size:12px;color:#8a9ab5;text-transform:uppercase;letter-spacing:3px;
              font-weight:500;">Juridisk Vidensbase</div>
</div>
""", unsafe_allow_html=True)

# ── Modulkort ─────────────────────────────────────────────────────────────────
_CS = ("background:#fffcf8;border-radius:14px;padding:2.2rem 2.4rem 2rem;"
       "border:1px solid #ddd4c8;border-top:4px solid {color};"
       "box-shadow:0 2px 14px rgba(60,20,20,.07);height:100%;")

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.markdown(f"""
<div style="{_CS.format(color='#8C1C2E')}">
  <div style="font-size:1.9rem;margin-bottom:1rem;">⚖️</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:.9rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.25rem;">PKN</div>
  <div style="font-size:10.5px;color:#a08070;text-transform:uppercase;letter-spacing:1.5px;
              margin-bottom:1.1rem;padding-bottom:1.1rem;border-bottom:1px solid #ece6dc;">
    Planklagenævnet · efter 2017
  </div>
  <div style="font-size:13px;color:#4a3028;line-height:1.75;margin-bottom:1.3rem;">
    Afgørelser om lokalplaner, kommuneplantillæg, planvedtagelser og landzone. Søg og analyser PKN's praksis.
  </div>
  <div style="font-size:10.5px;font-weight:600;color:#b09080;text-transform:uppercase;letter-spacing:1px;">
    Planloven · 5.000+ afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/pkn.py", label="Åbn PKN →", use_container_width=True)

with col2:
    st.markdown(f"""
<div style="{_CS.format(color='#2d6a4f')}">
  <div style="font-size:1.9rem;margin-bottom:1rem;">🌿</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:.9rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.25rem;">MFKN</div>
  <div style="font-size:10.5px;color:#a08070;text-transform:uppercase;letter-spacing:1.5px;
              margin-bottom:1.1rem;padding-bottom:1.1rem;border-bottom:1px solid #ece6dc;">
    Beskyttelseslinjer
  </div>
  <div style="font-size:13px;color:#4a3028;line-height:1.75;margin-bottom:1.3rem;">
    Afgørelser om strandbeskyttelseslinjen, sø-, å- og fortidsmindebeskyttelseslinjer og skovbyggelinjen.
  </div>
  <div style="font-size:10.5px;font-weight:600;color:#b09080;text-transform:uppercase;letter-spacing:1px;">
    Naturbeskyttelsesloven · 2.000+ afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/mfkn_beskyttelseslinjer.py", label="Åbn Beskyttelseslinjer →", use_container_width=True)

with col3:
    st.markdown(f"""
<div style="{_CS.format(color='#0e7490')}">
  <div style="font-size:1.9rem;margin-bottom:1rem;">🌾</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:.9rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.25rem;">MFKN</div>
  <div style="font-size:10.5px;color:#a08070;text-transform:uppercase;letter-spacing:1.5px;
              margin-bottom:1.1rem;padding-bottom:1.1rem;border-bottom:1px solid #ece6dc;">
    Beskyttede Naturtyper
  </div>
  <div style="font-size:13px;color:#4a3028;line-height:1.75;margin-bottom:1.3rem;">
    Afgørelser om beskyttede naturtyper – eng, mose, hede, overdrev, sø og vandløb efter NBL § 3.
  </div>
  <div style="font-size:10.5px;font-weight:600;color:#b09080;text-transform:uppercase;letter-spacing:1px;">
    NBL § 3 · 1.410+ afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/mfkn_naturtyper.py", label="Åbn Naturtyper →", use_container_width=True)

st.markdown("""
<div style="text-align:center;padding-top:2.5rem;border-top:1px solid #ece6dc;
            margin-top:2rem;margin-bottom:1rem;">
  <span style="font-size:10.5px;color:#c8bdb0;letter-spacing:1.2px;text-transform:uppercase;">
    Harald · Juridisk Vidensbase
  </span>
</div>
""", unsafe_allow_html=True)

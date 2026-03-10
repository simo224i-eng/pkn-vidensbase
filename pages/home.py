import streamlit as st
from shared import logo, inject_css
inject_css()

# ── Forside ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(120)}</div>
</div>""", unsafe_allow_html=True)

st.markdown(f"""
<style>
  .h-card-sub {{
    font-size:11px;color:#a08070;text-transform:uppercase;letter-spacing:1.5px;
    margin-bottom:1.2rem;padding-bottom:1.2rem;border-bottom:1px solid #ece6dc;
  }}
</style>

<div style="text-align:center; padding: 3rem 0 2.5rem;">
  {logo(130)}
  <h1 style="font-family:'Cinzel',Georgia,serif;font-size:2.2rem;font-weight:900;
             color:#0f172a;letter-spacing:8px;margin:1.6rem 0 0.5rem;">Harald</h1>
  <div style="height:2px;width:40px;background:#c49a3c;border-radius:1px;margin:0 auto 1rem;"></div>
  <p style="font-size:13px;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;">
    Juridisk Vidensbase · Legal Tech AI
  </p>
</div>
""", unsafe_allow_html=True)

_CARD = (
    "background:#fffcf8;border-radius:14px;padding:2.4rem 2.6rem 1.6rem;"
    "border:1px solid #ddd4c8;border-top:4px solid {color};"
    "box-shadow:0 2px 12px rgba(60,20,20,.07);height:100%;"
)

col1, col2, col3 = st.columns(3, gap="large")

with col1:
    st.html(f"""
<div style="{_CARD.format(color='#8C1C2E')}">
  <div style="font-size:2rem;margin-bottom:1.2rem;">⚖️</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:1rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.3rem;">PKN</div>
  <div class="h-card-sub">Planklagenævnet</div>
  <div style="font-size:13.5px;color:#4a3028;line-height:1.7;margin-bottom:1.4rem;">
    Afgørelser om lokalplaner, kommuneplantillæg, dispensationer og planvedtagelser.
    Søg, filtrer og analyser PKN's praksis med AI-assistance.
  </div>
  <div style="font-size:11px;font-weight:600;color:#b09080;text-transform:uppercase;
              letter-spacing:1px;">Plan- og byggeloven · 4.780+ afgørelser</div>
</div>""")
    st.page_link("pages/pkn.py", label="Åbn PKN →", use_container_width=True)

with col2:
    st.html(f"""
<div style="{_CARD.format(color='#2d6a4f')}">
  <div style="font-size:2rem;margin-bottom:1.2rem;">🌿</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:1rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.3rem;">MFKN</div>
  <div class="h-card-sub">Beskyttelseslinjer</div>
  <div style="font-size:13.5px;color:#4a3028;line-height:1.7;margin-bottom:1.4rem;">
    Afgørelser om strandbeskyttelseslinjen, sø-, å- og fortidsmindebeskyttelseslinjer,
    skovbyggelinjen og klitfredning.
  </div>
  <div style="font-size:11px;font-weight:600;color:#b09080;text-transform:uppercase;
              letter-spacing:1px;">Naturbeskyttelsesloven · 2.000+ afgørelser</div>
</div>""")
    st.page_link("pages/mfkn_beskyttelseslinjer.py", label="Åbn Beskyttelseslinjer →", use_container_width=True)

with col3:
    st.html(f"""
<div style="{_CARD.format(color='#0e7490')}">
  <div style="font-size:2rem;margin-bottom:1.2rem;">🌾</div>
  <div style="font-family:'Cinzel',Georgia,serif;font-size:1rem;font-weight:700;
              color:#1a0a0e;letter-spacing:4px;margin-bottom:.3rem;">MFKN</div>
  <div class="h-card-sub">Beskyttede Naturtyper</div>
  <div style="font-size:13.5px;color:#4a3028;line-height:1.7;margin-bottom:1.4rem;">
    Afgørelser om beskyttede naturtyper – eng, mose, hede, overdrev, sø og vandløb
    efter naturbeskyttelseslovens § 3.
  </div>
  <div style="font-size:11px;font-weight:600;color:#b09080;text-transform:uppercase;
              letter-spacing:1px;">NBL § 3 · 1.410+ afgørelser</div>
</div>""")
    st.page_link("pages/mfkn_naturtyper.py", label="Åbn Naturtyper →", use_container_width=True)

st.markdown("""
<div style="text-align:center;padding-top:2rem;border-top:1px solid #e2e8f0;margin-top:2rem;margin-bottom:2rem;">
  <p style="font-size:11px;color:#cbd5e1;letter-spacing:1px;text-transform:uppercase;">
    Harald · Legal Tech AI · Powered by Claude
  </p>
</div>
""", unsafe_allow_html=True)

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
<div style="text-align:center; padding: 3rem 0 2rem;">
  {logo(130)}
  <h1 style="font-family:'Cinzel',Georgia,serif; font-size:2.2rem; font-weight:900;
             color:#0f172a; letter-spacing:8px; margin:1.6rem 0 0.5rem;">HARALD</h1>
  <div style="height:2px;width:40px;background:#c49a3c;border-radius:1px;margin:0 auto 1rem;"></div>
  <p style="font-size:13px;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;">
    Juridisk Vidensbase · Legal Tech AI
  </p>
</div>

<div style="display:grid; grid-template-columns:1fr 1fr; gap:2rem; max-width:900px; margin:0 auto 4rem;">

  <a href="/pkn" target="_self" style="text-decoration:none; color:inherit;">
    <div class="nævn-card">
      <div class="nævn-card-icon">⚖️</div>
      <div class="nævn-card-title">PKN</div>
      <div class="nævn-card-sub">Planklagenævnet</div>
      <div class="nævn-card-desc">
        Afgørelser om lokalplaner, kommuneplantillæg, dispensationer og planvedtagelser.
        Søg, filtrer og analyser PKN's praksis med AI-assistance.
      </div>
      <div class="nævn-card-count">Plan- og byggeloven · 4.780+ afgørelser</div>
      <div class="nævn-card-cta">Åbn PKN →</div>
    </div>
  </a>

  <a href="/mfkn_beskyttelseslinjer" target="_self" style="text-decoration:none; color:inherit;">
    <div class="nævn-card mfkn">
      <div class="nævn-card-icon">🌿</div>
      <div class="nævn-card-title">MFKN</div>
      <div class="nævn-card-sub">Miljø- og Fødevareklagenævnet</div>
      <div class="nævn-card-desc">
        Afgørelser om strandbeskyttelseslinjen, sø-, å- og fortidsmindebeskyttelseslinjer,
        skovbyggelinjen og klitfredning.
      </div>
      <div class="nævn-card-count">Naturbeskyttelsesloven · 2.000+ afgørelser</div>
      <div class="nævn-card-cta mfkn">Åbn MFKN →</div>
    </div>
  </a>

</div>

<div style="text-align:center; padding-top:2rem; border-top:1px solid #e2e8f0;">
  <p style="font-size:11px; color:#cbd5e1; letter-spacing:1px; text-transform:uppercase;">
    Harald · Legal Tech AI · Powered by Claude
  </p>
</div>
""", unsafe_allow_html=True)

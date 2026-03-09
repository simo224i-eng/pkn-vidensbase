import streamlit as st
from shared import logo

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
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

col_pkn, col_mfkn = st.columns(2, gap="large")

with col_pkn:
    st.markdown("""
<div class="nævn-card">
  <div class="nævn-card-icon">⚖️</div>
  <div class="nævn-card-title">PKN</div>
  <div class="nævn-card-sub">Planklagenævnet</div>
  <div class="nævn-card-desc">
    Afgørelser om lokalplaner, kommuneplantillæg, dispensationer og planvedtagelser.
    Søg, filtrer og analyser PKN's praksis med AI-assistance.
  </div>
  <div class="nævn-card-count">Plan- og byggeloven · 4.780+ afgørelser</div>
</div>
""", unsafe_allow_html=True)
    if st.button("Åbn PKN →", use_container_width=True, key="btn_pkn"):
        st.switch_page("pages/pkn.py")

with col_mfkn:
    st.markdown("""
<div class="nævn-card mfkn">
  <div class="nævn-card-icon">🌿</div>
  <div class="nævn-card-title">MFKN</div>
  <div class="nævn-card-sub">Miljø- og Fødevareklagenævnet</div>
  <div class="nævn-card-desc">
    Afgørelser om strandbeskyttelseslinjen, sø-, å- og fortidsmindebeskyttelseslinjer,
    skovbyggelinjen og klitfredning.
  </div>
  <div class="nævn-card-count">Naturbeskyttelsesloven · 2.000+ afgørelser</div>
</div>
""", unsafe_allow_html=True)
    if st.button("Åbn MFKN →", use_container_width=True, key="btn_mfkn"):
        st.switch_page("pages/mfkn_beskyttelseslinjer.py")

st.markdown("""
<div style="text-align:center;margin-top:4rem;padding-top:2rem;border-top:1px solid #e2e8f0;">
  <p style="font-size:11px;color:#cbd5e1;letter-spacing:1px;text-transform:uppercase;">
    Harald · Legal Tech AI · Powered by Claude
  </p>
</div>
""", unsafe_allow_html=True)

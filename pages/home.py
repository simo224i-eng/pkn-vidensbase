import streamlit as st
from shared import logo, inject_css
inject_css()

# ── Forside ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(120)}</div>
</div>""", unsafe_allow_html=True)

_CARD_S = (
    "display:flex;flex-direction:column;height:100%;"
    "background:#fffcf8;border-radius:14px;padding:2.4rem 2.6rem 2rem;"
    "border:1px solid #ddd4c8;border-top:4px solid #c8b8a8;"
    "box-shadow:0 2px 12px rgba(60,20,20,.07);"
    "transition:border-top-color .18s,box-shadow .18s,transform .18s;"
)
_CTA_PKN  = (
    "display:block;text-align:center;padding:.7rem 1rem;margin-top:auto;"
    "border:1.5px solid #8C1C2E;border-radius:8px;"
    "color:#8C1C2E;font-size:13px;font-weight:600;letter-spacing:.4px;"
)
_CTA_MFKN = _CTA_PKN.replace("#8C1C2E", "#2d6a4f")

st.markdown(f"""
<style>
  .h-nav-card:hover {{
    border-top-color: #8C1C2E !important;
    box-shadow: 0 12px 40px rgba(140,28,46,.16) !important;
    transform: translateY(-4px);
  }}
  .h-nav-card.mfkn:hover {{
    border-top-color: #2d6a4f !important;
    box-shadow: 0 12px 40px rgba(45,106,79,.14) !important;
  }}
  .h-nav-card:hover .cta-pkn  {{ background:#8C1C2E; color:#fff; }}
  .h-nav-card:hover .cta-mfkn {{ background:#2d6a4f; color:#fff; }}
  .cta-pkn, .cta-mfkn {{ transition: background .15s, color .15s; }}
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

<div style="display:grid;grid-template-columns:1fr 1fr;gap:2rem;max-width:880px;margin:0 auto 4rem;">

  <a href="/pkn" target="_self" style="text-decoration:none;color:inherit;">
    <div class="h-nav-card" style="{_CARD_S}">
      <div style="font-size:2rem;margin-bottom:1.2rem;">⚖️</div>
      <div style="font-family:'Cinzel',Georgia,serif;font-size:1rem;font-weight:700;
                  color:#1a0a0e;letter-spacing:4px;margin-bottom:.3rem;">PKN</div>
      <div class="h-card-sub">Planklagenævnet</div>
      <div style="font-size:13.5px;color:#4a3028;line-height:1.7;margin-bottom:1.4rem;flex:1;">
        Afgørelser om lokalplaner, kommuneplantillæg, dispensationer og planvedtagelser.
        Søg, filtrer og analyser PKN's praksis med AI-assistance.
      </div>
      <div style="font-size:11px;font-weight:600;color:#b09080;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:1.4rem;">Plan- og byggeloven · 4.780+ afgørelser</div>
      <div class="cta-pkn" style="{_CTA_PKN}">Åbn PKN →</div>
    </div>
  </a>

  <a href="/mfkn_beskyttelseslinjer" target="_self" style="text-decoration:none;color:inherit;">
    <div class="h-nav-card mfkn" style="{_CARD_S}">
      <div style="font-size:2rem;margin-bottom:1.2rem;">🌿</div>
      <div style="font-family:'Cinzel',Georgia,serif;font-size:1rem;font-weight:700;
                  color:#1a0a0e;letter-spacing:4px;margin-bottom:.3rem;">MFKN</div>
      <div class="h-card-sub">Miljø- og Fødevareklagenævnet</div>
      <div style="font-size:13.5px;color:#4a3028;line-height:1.7;margin-bottom:1.4rem;flex:1;">
        Afgørelser om strandbeskyttelseslinjen, sø-, å- og fortidsmindebeskyttelseslinjer,
        skovbyggelinjen og klitfredning.
      </div>
      <div style="font-size:11px;font-weight:600;color:#b09080;text-transform:uppercase;
                  letter-spacing:1px;margin-bottom:1.4rem;">Naturbeskyttelsesloven · 2.000+ afgørelser</div>
      <div class="cta-mfkn" style="{_CTA_MFKN}">Åbn MFKN →</div>
    </div>
  </a>

</div>

<div style="text-align:center;padding-top:2rem;border-top:1px solid #e2e8f0;margin-bottom:2rem;">
  <p style="font-size:11px;color:#cbd5e1;letter-spacing:1px;text-transform:uppercase;">
    Harald · Legal Tech AI · Powered by Claude
  </p>
</div>
""", unsafe_allow_html=True)

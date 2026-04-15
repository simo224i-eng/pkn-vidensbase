import streamlit as st
import os, csv, zipfile, glob as _glob, datetime
from shared import logo, inject_css, sidebar_log_ud

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

inject_css()

# ── Tæl afgørelser dynamisk ──────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _tæl_afgørelser():
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _tmp = "/tmp/pkn_data"
    os.makedirs(_tmp, exist_ok=True)
    csv.field_size_limit(10_000_000)

    def _tæl_zip(pattern):
        total = 0
        for f in _glob.glob(os.path.join(_root, pattern)):
            try:
                with zipfile.ZipFile(f) as z:
                    inner = [n for n in z.namelist() if n.endswith('.csv')][0]
                    with z.open(inner) as csvf:
                        total += sum(1 for _ in csv.DictReader(__import__('io').TextIOWrapper(csvf, encoding='utf-8')))
            except Exception:
                pass
        return total

    pkn = _tæl_zip("pkn_*.csv.zip")
    mfkn = _tæl_zip("mfkn_*.csv.zip")
    n_mfkn_kat = len(_glob.glob(os.path.join(_root, "mfkn_*.csv.zip")))

    # Seneste ændringsdato for zip-filerne
    alle_zips = _glob.glob(os.path.join(_root, "pkn_*.csv.zip")) + _glob.glob(os.path.join(_root, "mfkn_*.csv.zip"))
    if alle_zips:
        seneste = max(os.path.getmtime(f) for f in alle_zips)
        dato_str = datetime.datetime.fromtimestamp(seneste).strftime("%d.%m.%Y")
    else:
        dato_str = "-"
    return pkn, mfkn, n_mfkn_kat, dato_str

_pkn_antal, _mfkn_antal, _mfkn_kat, _senest_opdateret = _tæl_afgørelser()

st.markdown("""
<style>
/* Page-link knapper på forsiden — smelter sammen med nævn-card */
[data-testid="stPageLink"] { margin-top: -2px !important; }
[data-testid="stPageLink"] a {
    display: flex !important; align-items: center; justify-content: center; gap: 6px;
    width: 100%; padding: 11px 16px !important;
    background: #ffffff !important; color: #8C1C2E !important;
    border-radius: 0 0 8px 8px !important;
    font-size: 12px !important; font-weight: 600 !important;
    letter-spacing: 0.2px !important;
    text-decoration: none !important;
    border: 1px solid #e2e8f0 !important; border-top: none !important;
    transition: background .12s, color .12s, border-color .12s !important;
}
[data-testid="stPageLink"] a:hover {
    background: #8C1C2E !important; color: #ffffff !important;
    border-color: #8C1C2E !important;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(140, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:3.5rem 0 3rem;">
  {logo(200)}
  <div style="font-size:12px;color:#64748b;text-transform:uppercase;letter-spacing:1.4px;
              font-weight:500;margin-top:1.2rem;">Juridisk vidensbase</div>
</div>
""", unsafe_allow_html=True)

# ── Modulkort ─────────────────────────────────────────────────────────────────
_CS = ("background:#ffffff;border-radius:8px 8px 0 0;padding:2rem 2.2rem 1.8rem;"
       "border:1px solid #e2e8f0;border-bottom:none;display:flex;flex-direction:column;height:100%;")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(f"""
<div style="{_CS}">
  <div style="display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;
              border-radius:8px;background:#fef2f2;margin-bottom:1.1rem;">
    <span class="material-symbols-rounded" style="font-size:22px;color:#8C1C2E;">gavel</span>
  </div>
  <div style="font-size:1.05rem;font-weight:700;color:#0f172a;letter-spacing:-0.3px;margin-bottom:0.2rem;">Planklagenævnet</div>
  <div style="font-size:11.5px;color:#64748b;font-weight:500;
              margin-bottom:1rem;padding-bottom:1rem;border-bottom:1px solid #f1f5f9;">
    PKN · afgørelser efter 2017
  </div>
  <div style="font-size:13.5px;color:#475569;line-height:1.65;margin-bottom:1.2rem;flex:1;">
    Afgørelser om lokalplaner, kommuneplantillæg, planvedtagelser og landzone.
    Søg og analyser PKN's praksis.
  </div>
  <div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.6px;">
    Planloven · {_pkn_antal:,} afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/pkn.py", label="Åbn Planklagenævnet →", use_container_width=True)

with col2:
    st.markdown(f"""
<div style="{_CS}">
  <div style="display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;
              border-radius:8px;background:#fef2f2;margin-bottom:1.1rem;">
    <span class="material-symbols-rounded" style="font-size:22px;color:#8C1C2E;">eco</span>
  </div>
  <div style="font-size:1.05rem;font-weight:700;color:#0f172a;letter-spacing:-0.3px;margin-bottom:0.2rem;">Miljø- og Fødevareklagenævnet</div>
  <div style="font-size:11.5px;color:#64748b;font-weight:500;
              margin-bottom:1rem;padding-bottom:1rem;border-bottom:1px solid #f1f5f9;">
    MFKN · alle retsområder
  </div>
  <div style="font-size:13.5px;color:#475569;line-height:1.65;margin-bottom:1.2rem;flex:1;">
    Afgørelser om beskyttelseslinjer, beskyttede naturtyper, miljøbeskyttelse, husdyrbrug,
    vandforsyning og meget mere.
  </div>
  <div style="font-size:11px;font-weight:600;color:#94a3b8;text-transform:uppercase;letter-spacing:0.6px;">
    {_mfkn_kat} retsområder · {_mfkn_antal:,} afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/mfkn.py", label="Åbn Miljøklagenævnet →", use_container_width=True)

sidebar_log_ud()

# ── Udfaldsterminologi-legende ──────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:2.5rem;padding:1.4rem 1.8rem;background:#f8fafc;border-radius:8px;border:1px solid #e2e8f0;">
  <div style="font-size:10.5px;font-weight:600;color:#64748b;
              text-transform:uppercase;letter-spacing:0.8px;margin-bottom:0.7rem;">Udfaldsterminologi</div>
  <div style="display:flex;flex-wrap:wrap;gap:10px 24px;font-size:12.5px;color:#475569;line-height:1.65;">
    <span><strong style="color:#166534;">Medhold/Ophævet/Hjemvist</strong> — klager får helt eller delvist ret</span>
    <span><strong style="color:#991b1b;">Stadfæstelse/Ikke medhold</strong> — afgørelsen fastholdes</span>
    <span><strong style="color:#92400e;">Afvist</strong> — klagen behandles ikke (frist, kompetence mv.)</span>
    <span><strong style="color:#5b21b6;">Ændring</strong> — nævnet ændrer afgørelsens indhold</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align:center;padding-top:2.5rem;border-top:1px solid #e2e8f0;
            margin-top:2rem;margin-bottom:1rem;">
  <span style="font-size:10.5px;color:#94a3b8;letter-spacing:0.6px;text-transform:uppercase;font-weight:500;">
    Harald · Juridisk vidensbase
  </span>
  <br>
  <span style="font-size:10.5px;color:#cbd5e1;letter-spacing:0.2px;">
    Data senest opdateret {_senest_opdateret}
  </span>
</div>
""", unsafe_allow_html=True)

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

col1, col2 = st.columns(2, gap="large")

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
    Planloven · {_pkn_antal:,} afgørelser
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
    Miljø- og Fødevareklagenævnet · alle retsområder
  </div>
  <div style="font-size:13px;color:#4a3028;line-height:1.75;margin-bottom:1.3rem;">
    Afgørelser om beskyttelseslinjer, beskyttede naturtyper, miljøbeskyttelse, husdyrbrug, vandforsyning og meget mere. Vælg retsområde og søg i {_mfkn_antal:,} afgørelser.
  </div>
  <div style="font-size:10.5px;font-weight:600;color:#b09080;text-transform:uppercase;letter-spacing:1px;">
    {_mfkn_kat} retsområder · {_mfkn_antal:,} afgørelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/mfkn.py", label="Åbn MFKN →", use_container_width=True)

sidebar_log_ud()

# ── Udfaldsterminologi-legende ──────────────────────────────────────────────
st.markdown(f"""
<div style="margin-top:2.5rem;padding:1.6rem 2rem;background:#f8f6f3;border-radius:10px;border:1px solid #ece6dc;">
  <div style="font-family:'Cinzel',Georgia,serif;font-size:10px;font-weight:700;color:#7a6050;
              text-transform:uppercase;letter-spacing:2px;margin-bottom:0.8rem;">Udfaldsterminologi</div>
  <div style="display:flex;flex-wrap:wrap;gap:10px 24px;font-size:12px;color:#4a3028;line-height:1.7;">
    <span><strong style="color:#166534;">Medhold/Ophævet/Hjemvist</strong> – klager får helt eller delvist ret</span>
    <span><strong style="color:#991b1b;">Stadfæstelse/Ikke medhold</strong> – afgørelsen fastholdes</span>
    <span><strong style="color:#92400e;">Afvist</strong> – klagen behandles ikke (frist, kompetence mv.)</span>
    <span><strong style="color:#5b21b6;">Ændring</strong> – nævnet ændrer afgørelsens indhold</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align:center;padding-top:2.5rem;border-top:1px solid #ece6dc;
            margin-top:2rem;margin-bottom:1rem;">
  <span style="font-size:10.5px;color:#c8bdb0;letter-spacing:1.2px;text-transform:uppercase;">
    Harald · Juridisk Vidensbase
  </span>
  <br>
  <span style="font-size:10px;color:#b0a898;letter-spacing:0.5px;">
    Data senest opdateret {_senest_opdateret}
  </span>
</div>
""", unsafe_allow_html=True)

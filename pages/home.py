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
[data-testid="stPageLink"] { margin-top: -1px !important; }
[data-testid="stPageLink"] a {
    display: flex !important; align-items: center; justify-content: center; gap: 8px;
    width: 100%; padding: 13px 16px !important;
    background: #8C1C2E !important;
    border-radius: 0 0 8px 8px !important;
    font-size: 14px !important; font-weight: 600 !important;
    letter-spacing: 0.1px !important;
    text-decoration: none !important;
    border: 1px solid #8C1C2E !important; border-top: none !important;
    transition: background .15s ease !important;
}
[data-testid="stPageLink"] a,
[data-testid="stPageLink"] a *,
[data-testid="stPageLink"] a p,
[data-testid="stPageLink"] a span {
    color: #ffffff !important; fill: #ffffff !important;
}
[data-testid="stPageLink"] a:hover { background: #73111F !important; }
[data-testid="stPageLink"] a:hover * { color:#fff !important; }
.h-hero-title { font-size: 12px; color: var(--fg-tertiary); text-transform: uppercase;
    letter-spacing: .18em; font-weight: 600; margin-top: 1.5rem; }
.h-mod-card { background: var(--bg); border-radius: var(--r) var(--r) 0 0;
    padding: 2rem 2rem 1.6rem; border: 1px solid var(--border); border-bottom: none;
    display: flex; flex-direction: column; height: 100%; box-shadow: var(--sh-sm);
    transition: box-shadow var(--ease); }
[data-testid="stHorizontalBlock"]:hover .h-mod-card { box-shadow: var(--sh-md); }
.h-mod-name { font-size: 1.05rem; font-weight: 700; color: var(--fg);
    letter-spacing: -0.02em; margin-bottom: 0.3rem; }
.h-mod-tag { display:inline-block; font-size: 11px; color: var(--accent);
    background: var(--accent-tint); font-weight: 600; letter-spacing: .04em;
    padding: 2px 8px; border-radius: var(--r-pill); margin-bottom: 1rem; width: fit-content; }
.h-mod-desc { font-size: 14px; color: var(--fg-secondary); line-height: 1.65;
    margin-bottom: 1.4rem; flex: 1; }
.h-mod-count { font-size: 12px; font-weight: 600; color: var(--fg-tertiary);
    letter-spacing: .02em; padding-top: 1rem; border-top: 1px solid var(--border); }
.h-legend { margin-top: 2.5rem; padding: 1.2rem 1.6rem; background: var(--surface);
    border-radius: var(--r); border: 1px solid var(--border); }
.h-legend-h { font-size: 11px; font-weight: 600; color: var(--fg-tertiary);
    text-transform: uppercase; letter-spacing: .08em; margin-bottom: 0.7rem; }
.h-legend-row { display:flex; flex-wrap:wrap; gap:8px 22px; font-size:13px;
    color: var(--fg-secondary); line-height:1.7; }
.h-foot { text-align:center; padding-top:2rem; margin:1.5rem 0 1rem;
    font-size:12px; color: var(--fg-tertiary); letter-spacing:.02em; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(124, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:4rem 0 2.5rem;">
  {logo(170)}
  <div class="h-hero-title">Juridisk vidensbase</div>
</div>
""", unsafe_allow_html=True)

# ── Modulkort ─────────────────────────────────────────────────────────────────
col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown(f"""
<div class="h-mod-card">
  <div class="h-mod-name">Planklagenævnet</div>
  <span class="h-mod-tag">PKN</span>
  <div class="h-mod-desc">
    Afgørelser om lokalplaner, kommuneplantillæg, planvedtagelser, landzone
    og lovliggørelse. Søg og analysér PKN's praksis med AI.
  </div>
  <div class="h-mod-count">{_pkn_antal:,} afgørelser</div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/pkn.py", label="Åbn Planklagenævnet", use_container_width=True)

with col2:
    st.markdown(f"""
<div class="h-mod-card">
  <div class="h-mod-name">Miljø- og Fødevareklagenævnet</div>
  <span class="h-mod-tag">MFKN</span>
  <div class="h-mod-desc">
    Afgørelser om beskyttelseslinjer, beskyttede naturtyper, miljøbeskyttelse,
    husdyrbrug, vandforsyning og meget mere.
  </div>
  <div class="h-mod-count">{_mfkn_kat} retsområder &middot; {_mfkn_antal:,} afgørelser</div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/mfkn.py", label="Åbn Miljøklagenævnet", use_container_width=True)

sidebar_log_ud()

# ── Udfaldsterminologi-legende ──────────────────────────────────────────────
st.markdown("""
<div class="h-legend">
  <div class="h-legend-h">Udfaldsterminologi</div>
  <div class="h-legend-row">
    <span><strong style="color:var(--ok);">Medhold / Ophævet / Hjemvist</strong> — klager får ret</span>
    <span><strong style="color:var(--no);">Stadfæstelse / Ikke medhold</strong> — fastholdes</span>
    <span><strong style="color:var(--warn);">Afvist</strong> — behandles ikke</span>
    <span><strong style="color:var(--violet);">Ændring</strong> — ændres</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div class="h-foot">Data opdateret {_senest_opdateret}</div>
""", unsafe_allow_html=True)

import streamlit as st
import os, csv, zipfile, glob as _glob, datetime
from shared import logo, inject_css, sidebar_log_ud

if not st.session_state.get("_autentificeret_ejnar"):
    st.switch_page("app.py")
    st.stop()

inject_css()

# ── Tæl afgørelser dynamisk ──────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def _tæl_afgørelser():
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv.field_size_limit(10_000_000)

    def _tæl(pattern):
        total = 0
        for f in _glob.glob(os.path.join(_root, pattern)):
            try:
                if f.endswith(".zip"):
                    with zipfile.ZipFile(f) as z:
                        inner = [n for n in z.namelist() if n.endswith('.csv')][0]
                        with z.open(inner) as csvf:
                            total += sum(1 for _ in csv.DictReader(__import__('io').TextIOWrapper(csvf, encoding='utf-8')))
                else:
                    with open(f, newline="", encoding="utf-8") as csvf:
                        total += sum(1 for _ in csv.DictReader(csvf))
            except Exception:
                pass
        return total

    antal = _tæl("ejnar_*.csv") + _tæl("ejnar_*.csv.zip")
    alle_data = _glob.glob(os.path.join(_root, "ejnar_*.csv*"))
    if alle_data:
        seneste = max(os.path.getmtime(f) for f in alle_data)
        dato_str = datetime.datetime.fromtimestamp(seneste).strftime("%d.%m.%Y")
    else:
        dato_str = "-"
    return antal, dato_str

_antal, _senest_opdateret = _tæl_afgørelser()

st.markdown("""
<style>
[data-testid="stPageLink"] { margin-top: -1px !important; }
[data-testid="stPageLink"] a {
    display: flex !important; align-items: center; justify-content: center; gap: 6px;
    width: 100%; padding: 10px 16px !important;
    background: #0f172a !important; color: #f1f5f9 !important;
    border-radius: 0 0 8px 8px !important;
    font-size: 12px !important; font-weight: 500 !important;
    letter-spacing: 0.3px !important;
    text-decoration: none !important;
    border: 1px solid #0f172a !important; border-top: none !important;
    transition: background .15s !important;
}
[data-testid="stPageLink"] a:hover { background: #1e293b !important; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(120, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;padding:4rem 0 2.5rem;">
  {logo(170)}
  <div style="font-size:10.5px;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;
              font-weight:500;margin-top:1.4rem;">Ejerskifteforsikring · Praksisdatabase</div>
</div>
""", unsafe_allow_html=True)

# ── Modulkort ─────────────────────────────────────────────────────────────────
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown(f"""
<div style="background:#ffffff;border-radius:8px 8px 0 0;padding:2rem 2rem 1.6rem;
            border:1px solid #eef1f6;border-bottom:none;display:flex;flex-direction:column;height:100%;">
  <div style="font-size:0.95rem;font-weight:700;color:#0f172a;letter-spacing:-0.3px;margin-bottom:0.3rem;">
    Ankenævnet for Forsikring – Ejerskifteforsikring
  </div>
  <div style="font-size:11px;color:#94a3b8;font-weight:500;
              margin-bottom:1rem;padding-bottom:0.9rem;border-bottom:1px solid #f1f5f9;">
    AKF · Ejerskifte
  </div>
  <div style="font-size:13px;color:#64748b;line-height:1.65;margin-bottom:1.2rem;flex:1;">
    Kendelser om ejerskifteforsikring efter lov om forbrugerbeskyttelse ved
    erhvervelse af fast ejendom mv. — skimmel og fugt, tag og tagdækning, kloak,
    installationer, fundament, råd og insektangreb mv. Søg, filtrer på mangeltype
    og analysér nævnets praksis med AI.
  </div>
  <div style="font-size:10.5px;font-weight:500;color:#94a3b8;letter-spacing:0.3px;">
    {_antal:,} kendelser
  </div>
</div>""", unsafe_allow_html=True)
    st.page_link("pages/ejnar.py", label="Åbn praksisdatabasen", use_container_width=True)

sidebar_log_ud()

# ── Udfaldsterminologi-legende ──────────────────────────────────────────────
st.markdown("""
<div style="margin-top:2.5rem;padding:1.2rem 1.6rem;background:#f8fafc;border-radius:8px;border:1px solid #eef1f6;">
  <div style="font-size:10px;font-weight:600;color:#94a3b8;
              text-transform:uppercase;letter-spacing:1px;margin-bottom:0.6rem;">Udfaldsterminologi</div>
  <div style="display:flex;flex-wrap:wrap;gap:8px 20px;font-size:12px;color:#64748b;line-height:1.7;">
    <span><strong style="color:#15803d;">Medhold</strong> — klager får ret</span>
    <span><strong style="color:#15803d;">Delvis medhold</strong> — klager får delvis ret</span>
    <span><strong style="color:#b91c1c;">Ikke medhold</strong> — selskabet får ret</span>
    <span><strong style="color:#a16207;">Afvist</strong> — behandles ikke</span>
  </div>
</div>
""", unsafe_allow_html=True)

st.markdown(f"""
<div style="text-align:center;padding-top:2rem;margin-top:1.5rem;margin-bottom:1rem;">
  <span style="font-size:10px;color:#cbd5e1;letter-spacing:0.4px;font-weight:400;">
    Data opdateret {_senest_opdateret}
  </span>
</div>
""", unsafe_allow_html=True)

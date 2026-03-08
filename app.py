import streamlit as st
import pandas as pd
import re
import csv
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="Harald – PKN Vidensbase",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ──────────────────────────────────────────────────────────────────
_CSS_HTML = """
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #f0f4f9; font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stMain"] .block-container { padding-top: 1.8rem; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0c1a32 !important; border-right: 1px solid #1c3058; }
[data-testid="stSidebar"] * { color: #b8c9e0 !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: #142241 !important; border: 1px solid #244070 !important;
    color: #dce6f5 !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div { background: #142241 !important; border-color: #244070 !important; }
[data-testid="stSidebar"] hr { border-color: #1c3058 !important; }
[data-testid="stSidebar"] .stSlider [data-testid="stThumbValue"] { color: #c49a3c !important; }
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #c49a3c !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a { color: #c49a3c !important; }

/* ── Sidebar branding ── */
.h-brand-wrap { text-align: center; padding: 1.6rem 0 1.4rem; border-bottom: 1px solid #1c3058; margin-bottom: 1.4rem; }
.h-brand  { font-family: 'Cinzel', Georgia, serif !important; font-size: 26px; font-weight: 900;
            letter-spacing: 7px; color: #c49a3c !important; display: block; }
.h-sub    { font-size: 10px; color: #5a7a9e !important; letter-spacing: 2px;
            text-transform: uppercase; margin-top: 5px; display: block; }

/* ── Sidebar section labels ── */
.h-filter-label { font-size: 10px !important; font-weight: 700 !important; color: #c49a3c !important;
                  text-transform: uppercase; letter-spacing: 2px; margin: 1.2rem 0 0.3rem;
                  display: block; }

/* ── Page header ── */
.h-page-header { margin-bottom: 1.6rem; padding-bottom: 1rem; border-bottom: 2px solid #dce4ef; }
.h-page-title  { font-family: 'Cinzel', Georgia, serif; font-size: 1.9rem; font-weight: 900;
                 color: #0c1a32; letter-spacing: 5px; margin: 0 0 4px; }
.h-page-meta   { font-size: 13px; color: #7a8faa; margin: 0; }
.h-gold-line   { height: 3px; width: 48px; background: linear-gradient(90deg,#c49a3c,#e8c97a);
                 border-radius: 2px; margin: 6px 0; }

/* ── Cards ── */
.pkn-card {
    background: #ffffff; border-radius: 8px; padding: 16px 20px; margin-bottom: 10px;
    border-left: 4px solid #c49a3c;
    box-shadow: 0 1px 6px rgba(12,26,50,.07), 0 0 0 1px rgba(12,26,50,.04);
    transition: box-shadow .15s, transform .15s;
}
.pkn-card:hover { box-shadow: 0 4px 18px rgba(12,26,50,.12), 0 0 0 1px rgba(196,154,60,.2); }
.pkn-card-title   { font-size: 14.5px; font-weight: 600; color: #0c1a32; margin: 5px 0 8px; line-height: 1.45; }
.pkn-card-meta    { font-size: 11.5px; color: #8a9db8; margin-bottom: 7px; }
.pkn-card-excerpt { font-size: 13px; color: #3d5070; line-height: 1.55; }

/* ── Badges ── */
.pkn-badge { display: inline-block; padding: 2px 9px; border-radius: 4px;
             font-size: 10.5px; font-weight: 700; margin-right: 5px; letter-spacing: .3px; }
.badge-medhold      { background: #d1fae5; color: #065f46; }
.badge-ikke-medhold { background: #fee2e2; color: #991b1b; }
.badge-ophaevet      { background: #ede9fe; color: #5b21b6; }
.badge-afvist       { background: #fef3c7; color: #92400e; }
.badge-ukendt       { background: #e8ecf2; color: #4a5568; }

/* ── Stat cards ── */
.stat-card   { background: #fff; border-radius: 8px; padding: 22px 20px; text-align: center;
               box-shadow: 0 1px 6px rgba(12,26,50,.07); border-top: 3px solid #c49a3c; }
.stat-number { font-family: 'Cinzel', Georgia, serif; font-size: 34px; font-weight: 700; color: #0c1a32; }
.stat-label  { font-size: 11px; color: #8a9db8; margin-top: 6px;
               text-transform: uppercase; letter-spacing: 1.2px; }

/* ── Chat ── */
.chat-user      { background: #1a3060; color: #fff; border-radius: 16px 16px 4px 16px;
                  padding: 12px 16px; margin: 8px 0; max-width: 76%; margin-left: auto; }
.chat-assistant { background: #fff; color: #0c1a32; border-radius: 16px 16px 16px 4px;
                  padding: 12px 16px; margin: 8px 0; max-width: 86%;
                  box-shadow: 0 1px 6px rgba(12,26,50,.08); border-left: 3px solid #c49a3c; }
.source-chip    { display: inline-block; padding: 3px 10px; border-radius: 4px;
                  background: #f0f4f9; color: #1a3060; font-size: 11px; margin: 3px;
                  text-decoration: none; border: 1px solid #cfd8e8; }

/* ── Tabs (cosmetic) ── */
[data-testid="stTabs"] [role="tab"]          { font-size: 14px; font-weight: 500; color: #6b7f99; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"]
    { color: #0c1a32 !important; border-bottom-color: #c49a3c !important; }
</style>
"""
try:
    st.html(_CSS_HTML)
except AttributeError:
    st.markdown(_CSS_HTML, unsafe_allow_html=True)

# ── Logo SVG (embedded – no file needed) ─────────────────────────────────────
LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 222">
  <defs>
    <linearGradient id="sG" x1="25%" y1="0%" x2="75%" y2="100%">
      <stop offset="0%" stop-color="#2044a8"/>
      <stop offset="100%" stop-color="#0b1840"/>
    </linearGradient>
    <linearGradient id="gG" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#e0b84e"/>
      <stop offset="100%" stop-color="#9c6810"/>
    </linearGradient>
    <!-- shield clip so knotwork stays inside -->
    <clipPath id="sc">
      <path d="M100,14 C68,14 26,28 24,66 L24,124 C24,170 100,212 100,212
               C100,212 176,170 176,124 L176,66 C174,28 132,14 100,14 Z"/>
    </clipPath>
  </defs>

  <!-- ── Shield shadow ── -->
  <path d="M100,14 C68,14 26,28 24,66 L24,124 C24,170 100,212 100,212
           C100,212 176,170 176,124 L176,66 C174,28 132,14 100,14 Z"
        fill="#04091a" opacity="0.35" transform="translate(3,4)"/>

  <!-- ── Shield body ── -->
  <path d="M100,14 C68,14 26,28 24,66 L24,124 C24,170 100,212 100,212
           C100,212 176,170 176,124 L176,66 C174,28 132,14 100,14 Z"
        fill="url(#sG)"/>

  <!-- ── Gold outer border ── -->
  <path d="M100,14 C68,14 26,28 24,66 L24,124 C24,170 100,212 100,212
           C100,212 176,170 176,124 L176,66 C174,28 132,14 100,14 Z"
        fill="none" stroke="url(#gG)" stroke-width="4.5"/>

  <!-- ── Inner shield border ── -->
  <path d="M100,28 C74,28 38,40 36,70 L36,120 C36,158 100,196 100,196
           C100,196 164,158 164,120 L164,70 C162,40 126,28 100,28 Z"
        fill="none" stroke="#c49a3c" stroke-width="1.8" opacity="0.65"/>

  <!-- ════ KNOTWORK ════ -->
  <!-- Each strand: gold outer glow → dark navy fill → bright edge -->
  <!-- Strand A: upper-left → lower-right S-curve -->
  <!-- Strand B: upper-right → lower-left S-curve (mirror) -->

  <!-- Gold glow (widest, drawn first) -->
  <path d="M 64,42 C 110,42 114,90 100,112 C 86,134 90,174 136,178"
        fill="none" stroke="#c49a3c" stroke-width="22" stroke-linecap="round"
        clip-path="url(#sc)" opacity="0.35"/>
  <path d="M 136,42 C 90,42 86,90 100,112 C 114,134 110,174 64,178"
        fill="none" stroke="#c49a3c" stroke-width="22" stroke-linecap="round"
        clip-path="url(#sc)" opacity="0.35"/>

  <!-- Navy strand bodies -->
  <path d="M 64,42 C 110,42 114,90 100,112 C 86,134 90,174 136,178"
        fill="none" stroke="#18368a" stroke-width="15" stroke-linecap="round"
        clip-path="url(#sc)"/>
  <path d="M 136,42 C 90,42 86,90 100,112 C 114,134 110,174 64,178"
        fill="none" stroke="#18368a" stroke-width="15" stroke-linecap="round"
        clip-path="url(#sc)"/>

  <!-- Bright centre highlight on strands -->
  <path d="M 64,42 C 110,42 114,90 100,112 C 86,134 90,174 136,178"
        fill="none" stroke="#2e58d0" stroke-width="7" stroke-linecap="round"
        clip-path="url(#sc)"/>
  <path d="M 136,42 C 90,42 86,90 100,112 C 114,134 110,174 64,178"
        fill="none" stroke="#2e58d0" stroke-width="7" stroke-linecap="round"
        clip-path="url(#sc)"/>

  <!-- Over/under at UPPER crossing (~100,88): strand A goes over -->
  <!-- Shield-colour patch to cut strand B -->
  <ellipse cx="100" cy="88" rx="10" ry="9" fill="#1530789" opacity="0"/>
  <path d="M 88,80 C 96,86 104,90 112,88"
        fill="none" stroke="#0e1e50" stroke-width="16" stroke-linecap="round"/>
  <!-- Re-draw strand A segment on top -->
  <path d="M 82,74 C 94,82 106,90 112,100"
        fill="none" stroke="#18368a" stroke-width="15" stroke-linecap="round"/>
  <path d="M 82,74 C 94,82 106,90 112,100"
        fill="none" stroke="#2e58d0" stroke-width="7" stroke-linecap="round"/>

  <!-- Over/under at LOWER crossing (~100,132): strand B goes over -->
  <path d="M 88,124 C 96,130 104,136 112,132"
        fill="none" stroke="#0e1e50" stroke-width="16" stroke-linecap="round"/>
  <path d="M 112,124 C 104,130 96,136 88,132"
        fill="none" stroke="#18368a" stroke-width="15" stroke-linecap="round"/>
  <path d="M 112,124 C 104,130 96,136 88,132"
        fill="none" stroke="#2e58d0" stroke-width="7" stroke-linecap="round"/>

  <!-- Gold trim lines on strand edges (fine parallel lines) -->
  <path d="M 64,42 C 110,42 114,90 100,112 C 86,134 90,174 136,178"
        fill="none" stroke="#c49a3c" stroke-width="1.5" stroke-linecap="round"
        clip-path="url(#sc)" opacity="0.7"/>
  <path d="M 136,42 C 90,42 86,90 100,112 C 114,134 110,174 64,178"
        fill="none" stroke="#c49a3c" stroke-width="1.5" stroke-linecap="round"
        clip-path="url(#sc)" opacity="0.7"/>

  <!-- ════ SCALES OF JUSTICE ════ -->
  <!-- Pivot circle -->
  <circle cx="100" cy="68" r="6" fill="url(#gG)"/>
  <!-- Center post -->
  <rect x="97.5" y="68" width="5" height="74" rx="2.5" fill="url(#gG)"/>
  <!-- Base platform -->
  <rect x="82" y="138" width="36" height="6" rx="3" fill="url(#gG)"/>
  <!-- Beam -->
  <rect x="46" y="87" width="108" height="5" rx="2.5" fill="url(#gG)"/>
  <!-- Left V-chain -->
  <line x1="61" y1="92" x2="55" y2="114" stroke="#d4a040" stroke-width="2.2"/>
  <line x1="61" y1="92" x2="70" y2="114" stroke="#d4a040" stroke-width="2.2"/>
  <!-- Right V-chain -->
  <line x1="139" y1="92" x2="130" y2="114" stroke="#d4a040" stroke-width="2.2"/>
  <line x1="139" y1="92" x2="145" y2="114" stroke="#d4a040" stroke-width="2.2"/>
  <!-- Left pan (bowl arc) -->
  <path d="M 48,114 Q 62,130 76,114"
        stroke="url(#gG)" stroke-width="3" fill="rgba(196,154,60,0.22)" stroke-linejoin="round"/>
  <!-- Right pan -->
  <path d="M 124,114 Q 138,130 152,114"
        stroke="url(#gG)" stroke-width="3" fill="rgba(196,154,60,0.22)" stroke-linejoin="round"/>
</svg>"""

# Base64-encode so it works as <img src="data:..."> in st.markdown (Streamlit strips inline SVG)
import base64 as _b64
LOGO_IMG = f'<img src="data:image/svg+xml;base64,{_b64.b64encode(LOGO_SVG.encode()).decode()}" width="{{w}}" style="display:block;margin:0 auto"/>'

def logo(w: int) -> str:
    return LOGO_IMG.replace("{w}", str(w))

# ── API ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

def _llm(prompt: str) -> str:
    if not GEMINI_API_KEY:
        return "Tilføj GEMINI_API_KEY i Streamlit secrets (Settings → Secrets)."
    r = requests.post(
        f"{_GEMINI_URL}?key={GEMINI_API_KEY}",
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 2000},
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"]

# ── Hjælpefunktioner ──────────────────────────────────────────────────────────
def strip_html(text: str) -> str:
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
        "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
        "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
        "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
    }
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in entities.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def detect_plantype(titel: str) -> list:
    t = titel.lower()
    types = []
    if "kommuneplantillæg" in t:
        types.append("Kommuneplantillæg")
    if re.search(r"kommuneplan(?!tillæg)", t):
        types.append("Kommuneplan")
    if "lokalplan" in t:
        types.append("Lokalplan")
    return types if types else ["Andet"]


def kategoriser(titel: str) -> str:
    t = titel.lower()
    # Miljø-kategorier har højeste prioritet
    if "screeningsafgørelse" in t or "screeningen" in t:
        return "Screening"
    if "miljøvurdering" in t or "miljørapport" in t or "vvm" in t:
        return "Miljøvurdering"
    if "lokalplan" in t:
        if "dispensation" in t:        return "Dispensation"
        if "overensstemmelse" in t:    return "Overensstemmelse"
        if "vedtagelse" in t:          return "Vedtagelse"
        return "Andet"
    if "kommuneplantillæg" in t or "kommuneplan" in t:
        if "vedtagelse" in t:          return "Vedtagelse"
        return "Andet"
    if "landzone" in t:             return "Landzone"
    if "strandbeskyttelse" in t:    return "Strandbeskyttelse"
    if "skovloven" in t or " skov " in t: return "Skovloven"
    if "fredning" in t:             return "Fredning"
    if "opsættende virkning" in t:  return "Opsættende virkning"
    return "Andet"


def _strip_html(t: str) -> str:
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", " ", str(t)))


def detect_udfald(titel: str, tekst: str = "") -> str:
    t = titel.lower()
    if any(k in t for k in ("ophævet", "ugyldig", "ugyldigt", "annulleret",
                             "hjemvisning", "hjemvises")):       return "Ophævet"
    if "medhold" in t:                                           return "Medhold"
    if "stadfæst" in t or "ikke medhold" in t:                  return "Ikke medhold"
    if "afvisning" in t or "afvises" in t:                       return "Afvist"

    # Slå op i brødteksten – brug SIDSTE "Afsluttende bemærkninger"-sektion
    tx = _strip_html(tekst).lower()
    positions = [m.start() for m in re.finditer(r"afsluttende bem[æa]rkninger", tx)]
    conc = tx[positions[-1]:positions[-1] + 500] if positions else tx[-800:]

    if any(k in conc for k in ("ophæver", "hjemviser", "hjemvisning")):
        return "Ophævet"
    if "kan ikke give medhold" in conc or "ikke medhold" in conc:
        return "Ikke medhold"
    if "afviser" in conc and ("klagen" in conc or "klager" in conc):
        return "Afvist"
    if "medhold" in conc:
        return "Medhold"
    return "Ukendt"


def extract_kommune(titel: str) -> str:
    m = re.search(r"([A-ZÆØÅ][a-zæøå]+-?[A-ZÆØÅ]?[a-zæøå]*)\s+Kommunes?", titel)
    return m.group(1) if m else None


def detect_sagsgruppe(titel: str, tekst: str) -> str:
    t = (titel + " " + tekst[:500]).lower()
    if "genoptagelse" in t:    return "Genoptagelse"
    if "opsættende virkning" in t or "afslag på opsættende" in t: return "Opsættende virkning"
    if "afvisning" in t or "afvises" in t or "klageberettiget" in t: return "Afvisning"
    return "Realitetsbehandling"


BADGE = {"Medhold": "badge-medhold", "Ikke medhold": "badge-ikke-medhold",
         "Ophævet": "badge-ophaevet", "Afvist": "badge-afvist", "Ukendt": "badge-ukendt"}

# ── Data-loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser 4.780 afgørelser…", ttl=None, hash_funcs=None)
def load_data(version: int = 4):  # bump version to bust cache
    import os, zipfile
    if not os.path.exists("pkn_vidensbase_fuld_tekst.csv"):
        with zipfile.ZipFile("pkn_vidensbase_fuld_tekst.csv.zip") as z:
            z.extractall(".")
    csv.field_size_limit(10_000_000)
    rows = []
    with open("pkn_vidensbase_fuld_tekst.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tekst = strip_html(row["Tekst"])
            rows.append({
                "Dato":    row["Dato"],
                "Titel":   row["Titel"],
                "Link":    row["Link"],
                "Tekst":   tekst,
                "Excerpt": tekst[:280],
            })
    df = pd.DataFrame(rows)
    df["Dato"]     = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"]       = df["Dato"].dt.year.astype("Int64")
    df["Kategori"]   = df["Titel"].apply(kategoriser)
    df["Plantype"]   = df["Titel"].apply(detect_plantype)
    df["Udfald"]     = df.apply(lambda r: detect_udfald(r["Titel"], r.get("Tekst", "")), axis=1)
    df["Kommune"]    = df["Titel"].apply(extract_kommune)
    df["Sagsgruppe"] = df.apply(lambda r: detect_sagsgruppe(r["Titel"], r["Tekst"]), axis=1)
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_data(3)
    texts = (df2["Titel"] + " " + df2["Tekst"]).tolist()
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2),
                          min_df=2, sublinear_tf=True)
    mat = vec.fit_transform(texts)
    return vec, mat


def tfidf_søg(query: str, df, vec, mat, sub_idx=None, top_n: int = 30):
    from sklearn.metrics.pairwise import cosine_similarity
    qv = vec.transform([query])
    if sub_idx is not None:
        scores_sub = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local  = scores_sub.argsort()[-top_n:][::-1]
        top_global = [sub_idx[i] for i in top_local if scores_sub[i] > 0.01]
        result     = df.loc[top_global].copy()
        result["_score"] = [scores_sub[i] for i in top_local if scores_sub[i] > 0.01]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top    = scores.argsort()[-top_n:][::-1]
        result = df.iloc[top].copy()
        result["_score"] = scores[top]
        result = result[result["_score"] > 0.01]
    return result.reset_index(drop=True)


def gemini_svar(spørgsmål: str, docs: list) -> str:
    if not GEMINI_API_KEY:
        return "Tilføj GEMINI_API_KEY i Streamlit secrets."
    kontekst = "\n\n".join(
        f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}\n{d['Tekst'][:1200]}"
        for i, d in enumerate(docs)
    )
    prompt = f"""Du er en juridisk assistent specialiseret i dansk planlovgivning og PKN-praksis.
Besvar følgende spørgsmål KUN baseret på de vedlagte PKN-afgørelser.
Henvis til [Kilde X] når du bruger information fra en bestemt afgørelse.
Svar på dansk, præcist og struktureret med afsnit hvis relevant.

SPØRGSMÅL: {spørgsmål}

AFGØRELSER:
{kontekst}

SVAR:"""
    return _llm(prompt)


def gemini_resumé(titel: str, tekst: str) -> str:
    if not GEMINI_API_KEY:
        return "Ingen API-nøgle."
    prompt = f"""Lav et kort, struktureret resumé af denne PKN-afgørelse på dansk.
Inkluder: Sagens kerne, Klagenævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {tekst[:3000]}

RESUMÉ:"""
    return _llm(prompt)


# ── Session state ─────────────────────────────────────────────────────────────
if "chat_historik"   not in st.session_state: st.session_state.chat_historik   = []
if "valgt_afgørelse" not in st.session_state: st.session_state.valgt_afgørelse = None

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_data(3)
vec, mat = build_index(len(df))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div style="margin:0 auto 8px">{logo(72)}</div>
  <span class="h-brand">HARALD</span>
  <span class="h-sub">Planklagenævnets Vidensbase</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Søgning</span>', unsafe_allow_html=True)
    søg_input   = st.text_input("", placeholder="f.eks. terrasse lokalplan…", label_visibility="collapsed")

    st.markdown('<span class="h-filter-label">Kategori</span>', unsafe_allow_html=True)
    valgte_kats    = st.multiselect("", sorted(df["Kategori"].unique()), label_visibility="collapsed", key="kat")

    st.markdown('<span class="h-filter-label">Plantype</span>', unsafe_allow_html=True)
    plantype_valg  = st.multiselect("", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"], label_visibility="collapsed", key="pt")

    st.markdown('<span class="h-filter-label">Sagsgruppe</span>', unsafe_allow_html=True)
    sagsgruppe_valg = st.multiselect("", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"], label_visibility="collapsed", key="sg")

    st.markdown('<span class="h-filter-label">Årsinterval</span>', unsafe_allow_html=True)
    år_min, år_max = int(df["År"].min()), int(df["År"].max())
    år_range       = st.slider("", år_min, år_max, (år_min, år_max), label_visibility="collapsed")

    st.markdown('<span class="h-filter-label">Udfald</span>', unsafe_allow_html=True)
    udfald_valg    = st.multiselect("", ["Medhold", "Ikke medhold", "Ophævet", "Afvist", "Ukendt"], label_visibility="collapsed", key="ud")

    st.markdown("---")
    st.markdown(f"<span style='font-size:12px;color:#5a7a9e'>**{len(df):,}** afgørelser &nbsp;·&nbsp; {år_min}–{år_max}</span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:11px;color:#3d5878'>Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>", unsafe_allow_html=True)


mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if valgte_kats:     mask &= df["Kategori"].isin(valgte_kats)
if plantype_valg:   mask &= df["Plantype"].apply(lambda pts: any(pt in pts for pt in plantype_valg))
if sagsgruppe_valg: mask &= df["Sagsgruppe"].isin(sagsgruppe_valg)
if udfald_valg:     mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx   = df[mask].index.tolist()

if søg_input.strip():
    df_vis = tfidf_søg(søg_input, df, vec, mat, sub_idx=sub_idx, top_n=25)
else:
    df_vis = df_filter.sort_values("Dato", ascending=False).head(25)


def build_download_text(data: pd.DataFrame) -> str:
    """Bygger en struktureret tekstfil med alle afgørelser – optimeret til LLM-upload."""
    lines = [
        "PLANKLAGENÆVNETS AFGØRELSER – EKSPORT",
        f"Antal afgørelser: {len(data)}",
        f"Genereret: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
        "=" * 72,
        "",
    ]
    for _, row in data.iterrows():
        dato = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
        lines += [
            f"AFGØRELSE: {row['Titel']}",
            f"DATO:       {dato}",
            f"KATEGORI:   {row['Kategori']}  |  PLANTYPE: {', '.join(row.get('Plantype', ['–']))}",
            f"UDFALD:     {row['Udfald']}  |  SAGSGRUPPE: {row.get('Sagsgruppe', '–')}",
            f"KOMMUNE:    {row['Kommune'] or '–'}",
            f"KILDE:      {row['Link']}",
            "-" * 72,
            row["Tekst"].strip(),
            "",
            "=" * 72,
            "",
        ]
    return "\n".join(lines)


with st.sidebar:
    n = len(df_filter)
    st.markdown("---")
    if n == 0:
        st.caption("Ingen afgørelser matcher filtrene.")
    elif n > 500:
        st.caption(f"⚠️ {n:,} afgørelser valgt – filen kan blive stor.")
        dl_bytes = build_download_text(df_filter).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download alle {n:,} afgørelser (.txt)",
            data=dl_bytes,
            file_name="pkn_afgørelser.txt",
            mime="text/plain",
        )
    else:
        dl_bytes = build_download_text(df_filter).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download {n:,} afgørelser (.txt)",
            data=dl_bytes,
            file_name="pkn_afgørelser.txt",
            mime="text/plain",
        )


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header" style="display:flex;align-items:center;gap:18px">
  <div style="flex-shrink:0">{logo(62)}</div>
  <div>
    <h1 class="h-page-title">HARALD</h1>
    <div class="h-gold-line"></div>
    <p class="h-page-meta">Planklagenævnets afgørelsesdatabase &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {int(df['År'].min())}–{int(df['År'].max())}</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – AFGØRELSER
# ════════════════════════════════════════════════════════════════════════════
tab_søg, tab_stat, tab_ai = st.tabs(["  Afgørelser  ", "  Statistik  ", "  AI Assistent  "])

with tab_søg:

    # Detaljevisning
    if st.session_state.valgt_afgørelse is not None:
        row = st.session_state.valgt_afgørelse
        if st.button("← Tilbage"):
            st.session_state.valgt_afgørelse = None
            st.rerun()

        badge_cls = BADGE.get(row["Udfald"], "badge-ukendt")
        dato_str  = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y")
        st.markdown(f"# {row['Titel']}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Dato",       dato_str)
        c2.metric("Kategori",   row["Kategori"])
        c3.metric("Sagsgruppe", row.get("Sagsgruppe", "–"))
        c4.metric("Udfald",     row["Udfald"])
        c5.metric("Kommune",    row["Kommune"] or "–")
        st.markdown(f"[🔗 Åbn original afgørelse på PKN's hjemmeside]({row['Link']})")
        st.divider()

        col_tekst, col_ai = st.columns([3, 2])
        with col_tekst:
            with st.expander("📄 Fuld afgørelsestekst", expanded=True):
                st.markdown(row["Tekst"])
        with col_ai:
            st.markdown("### ✨ AI-resumé")
            if st.button("Generer AI-resumé"):
                with st.spinner("Resumerer…"):
                    try:
                        st.session_state._resumé = gemini_resumé(row["Titel"], row["Tekst"])
                    except Exception as e:
                        st.session_state._resumé = f"Fejl: {e}"
            if "_resumé" in st.session_state:
                st.info(st.session_state._resumé)

    else:
        total_filtreret = len(df_filter)
        hits  = len(df_vis)
        if søg_input:
            label = f"**{hits}** resultater for \"{søg_input}\" (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {hits} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            st.warning("Ingen resultater – prøv andre søgeord eller filtre.")
        else:
            for _, row in df_vis.iterrows():
                badge_cls = BADGE.get(row["Udfald"], "badge-ukendt")
                dato_str  = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                st.markdown(f"""
<div class="pkn-card">
  <div class="pkn-card-meta">{dato_str} &nbsp;·&nbsp; {row['Kategori']} &nbsp;·&nbsp; {row['Sagsgruppe']}
    &nbsp;<span class="pkn-badge {badge_cls}">{row['Udfald']}</span>
  </div>
  <div class="pkn-card-title">{row['Titel']}</div>
  <div class="pkn-card-excerpt">{row['Excerpt']}…</div>
</div>""", unsafe_allow_html=True)

                c1, c2 = st.columns([1, 6])
                with c1:
                    if st.button("Læs mere", key=f"btn_{row['Link'][-20:]}"):
                        st.session_state.valgt_afgørelse = row.to_dict()
                        if "_resumé" in st.session_state:
                            del st.session_state["_resumé"]
                        st.rerun()
                with c2:
                    st.markdown(f"[Åbn original ↗]({row['Link']})")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 – STATISTIK
# ════════════════════════════════════════════════════════════════════════════
with tab_stat:
    d = df_filter

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(d):,}</div>'
                    f'<div class="stat-label">Afgørelser</div></div>', unsafe_allow_html=True)
    with k2:
        pct = (d["Udfald"] == "Medhold").mean() * 100
        st.markdown(f'<div class="stat-card"><div class="stat-number">{pct:.0f}%</div>'
                    f'<div class="stat-label">Medhold-rate</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kommune"].nunique()}</div>'
                    f'<div class="stat-label">Kommuner</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kategori"].nunique()}</div>'
                    f'<div class="stat-label">Kategorier</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Afgørelser per år")
        år_df = d.groupby("År").size().reset_index(name="Antal")
        fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#c49a3c"])
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Fordeling på kategori")
        kat_df = d.groupby("Kategori").size().reset_index(name="Antal")
        fig2 = px.pie(kat_df, values="Antal", names="Kategori",
                      color_discrete_sequence=px.colors.qualitative.Set3, hole=0.4)
        fig2.update_layout(margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig2, use_container_width=True)

    col_ll, col_rr = st.columns(2)

    with col_ll:
        st.markdown("#### Udfald over tid")
        udfald_år = d.groupby(["År","Udfald"]).size().reset_index(name="Antal")
        farver = {"Medhold":"#10b981","Ikke medhold":"#ef4444","Ophævet":"#8b5cf6","Afvist":"#f59e0b","Ukendt":"#94a3b8"}
        fig3 = px.bar(udfald_år, x="År", y="Antal", color="Udfald",
                      color_discrete_map=farver, barmode="stack")
        fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig3, use_container_width=True)

    with col_rr:
        st.markdown("#### Top 15 kommuner")
        kom_df = (d.dropna(subset=["Kommune"]).groupby("Kommune").size()
                   .reset_index(name="Sager").sort_values("Sager",ascending=True).tail(15))
        fig4 = px.bar(kom_df, x="Sager", y="Kommune", orientation="h",
                      color_discrete_sequence=["#1a3060"])
        fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### Medhold-rate per kategori")
    if d.empty:
        st.info("Ingen data at vise med de valgte filtre.")
    else:
        mr = (d.groupby("Kategori")
               .apply(lambda x: pd.Series({
                   "Sager": len(x),
                   "Medhold_%": round((x["Udfald"]=="Medhold").mean()*100, 1)
               }), include_groups=False)
               .reset_index()
               .sort_values("Medhold_%", ascending=True))
        fig5 = px.bar(mr, x="Medhold_%", y="Kategori", orientation="h",
                      color="Medhold_%", color_continuous_scale=["#fee2e2","#10b981"],
                      hover_data={"Sager": True},
                      labels={"Medhold_%": "Medhold (%)"})
        fig5.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           coloraxis_showscale=False, margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig5, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.markdown("### 🤖 Spørg til PKN-praksis")
    st.markdown("AI'en søger i alle **4.780 afgørelser** og svarer med kildehenvisninger – ingen embedding-API nødvendig.")

    if not GEMINI_API_KEY:
        st.error("Tilføj `GEMINI_API_KEY` i Streamlit secrets.")
    else:
        # Forslagsknapper
        forslag = [
            "Hvad lægger PKN vægt på ved vurdering af terrasse?",
            "Hvornår gives der medhold i landzonesager?",
            "Hvilken praksis er der for strandbeskyttelseslinjen?",
            "Hvad kræves for dispensation fra lokalplan?",
        ]
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"fs_{i}"):
                st.session_state.chat_historik.append({"rolle": "bruger", "tekst": f})
                with st.spinner("Søger og genererer svar…"):
                    hits_ai = tfidf_søg(f, df, vec, mat, top_n=8)
                    try:
                        svar = gemini_svar(f, hits_ai.to_dict("records"))
                    except Exception as e:
                        svar = f"Fejl ved Gemini API: {e}"
                st.session_state.chat_historik.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
                st.rerun()

        st.divider()

        # Historik
        for msg in st.session_state.chat_historik:
            if msg["rolle"] == "bruger":
                st.markdown(f'<div class="chat-user">{msg["tekst"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-assistant">{msg["tekst"]}</div>', unsafe_allow_html=True)
                if msg.get("kilder"):
                    chips = " ".join(
                        f'<a class="source-chip" href="{k["Link"]}" target="_blank">[{i+1}] {k["Titel"][:55]}…</a>'
                        for i, k in enumerate(msg["kilder"][:5])
                    )
                    st.markdown(f"**Kilder:** {chips}", unsafe_allow_html=True)

        # Input-form
        with st.form("chat_form", clear_on_submit=True):
            spørgsmål = st.text_area("Dit spørgsmål", height=80,
                                      placeholder="Hvad er PKN's praksis for…?")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send ➤", use_container_width=True, type="primary")
            ryd  = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.chat_historik = []
            st.rerun()

        if send and spørgsmål.strip():
            st.session_state.chat_historik.append({"rolle": "bruger", "tekst": spørgsmål})
            with st.spinner("Søger og genererer svar…"):
                hits_ai = tfidf_søg(spørgsmål, df, vec, mat, top_n=8)
                try:
                    svar = gemini_svar(spørgsmål, hits_ai.to_dict("records"))
                except Exception as e:
                    svar = f"Fejl ved Gemini API: {e}"
            st.session_state.chat_historik.append(
                {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
            st.rerun()

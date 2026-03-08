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
[data-testid="stAppViewContainer"] { background: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stMain"] .block-container { padding-top: 2rem; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0f172a !important; border-right: none; }
[data-testid="stSidebar"] * { color: #94a3b8 !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: #1e293b !important; border: 1px solid #334155 !important;
    color: #e2e8f0 !important; border-radius: 5px !important; font-size: 13px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #1e293b !important; border-color: #334155 !important; border-radius: 5px !important;
}
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #c49a3c !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a { color: #c49a3c !important; }
[data-testid="stSidebar"] .stCheckbox label { font-size: 11px !important; color: #64748b !important; }

/* ── Sidebar branding ── */
.h-brand-wrap {
    text-align: center; padding: 1.6rem 0 1.4rem;
    border-bottom: 1px solid #1e293b; margin-bottom: 1.6rem;
}
.h-logo-box {
    display: inline-block;
    padding: 6px 10px;
    margin-bottom: 4px;
    filter: drop-shadow(0 3px 12px rgba(196,154,60,0.22));
}
.h-sub   { font-size: 9px; color: #3d5270 !important; letter-spacing: 2.5px;
           text-transform: uppercase; margin-top: 2px; display: block; }

/* ── Sidebar section labels ── */
.h-filter-label { font-size: 9px !important; font-weight: 600 !important; color: #475569 !important;
                  text-transform: uppercase; letter-spacing: 1.5px; margin: 1.4rem 0 0.35rem;
                  display: block; }

/* ── Page header ── */
.h-page-header { margin-bottom: 1.8rem; padding-bottom: 1.2rem; border-bottom: 1px solid #e2e8f0; }
.h-page-title  { font-family: 'Cinzel', Georgia, serif; font-size: 1.65rem; font-weight: 900;
                 color: #0f172a; letter-spacing: 5px; margin: 0 0 4px; }
.h-page-meta   { font-size: 12.5px; color: #94a3b8; margin: 0; }
.h-gold-line   { height: 2px; width: 32px; background: #c49a3c;
                 border-radius: 1px; margin: 6px 0 8px; }

/* ── Cards ── */
.pkn-card {
    background: #ffffff; border-radius: 6px; padding: 18px 22px; margin-bottom: 6px;
    border: 1px solid #e2e8f0;
    transition: border-color .12s, box-shadow .12s;
}
.pkn-card:hover {
    border-color: #c49a3c;
    box-shadow: 0 2px 12px rgba(15,23,42,.06);
}
.pkn-card-title   { font-size: 13.5px; font-weight: 600; color: #0f172a; margin: 4px 0 8px; line-height: 1.5; }
.pkn-card-meta    { font-size: 11px; color: #94a3b8; margin-bottom: 5px; letter-spacing: .1px; }
.pkn-card-excerpt { font-size: 12.5px; color: #475569; line-height: 1.6; }

/* ── Badges ── */
.pkn-badge { display: inline-block; padding: 2px 8px; border-radius: 20px;
             font-size: 10px; font-weight: 600; margin-right: 4px; letter-spacing: .1px; }
.badge-medhold      { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.badge-ikke-medhold { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.badge-ophaevet     { background: #f5f3ff; color: #5b21b6; border: 1px solid #ddd6fe; }
.badge-afvist       { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.badge-ukendt       { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }

/* ── Stat cards ── */
.stat-card   { background: #fff; border-radius: 6px; padding: 22px 18px; text-align: center;
               border: 1px solid #e2e8f0; }
.stat-number { font-family: 'Cinzel', Georgia, serif; font-size: 28px; font-weight: 700; color: #0f172a; }
.stat-label  { font-size: 10px; color: #94a3b8; margin-top: 5px;
               text-transform: uppercase; letter-spacing: 1px; }

/* ── Chat ── */
.chat-user      { background: #0f172a; color: #f1f5f9; border-radius: 12px 12px 2px 12px;
                  padding: 10px 14px; margin: 6px 0; max-width: 74%; margin-left: auto;
                  font-size: 13px; line-height: 1.5; }
.chat-assistant { background: #fff; color: #0f172a; border-radius: 12px 12px 12px 2px;
                  padding: 10px 14px; margin: 6px 0; max-width: 84%;
                  border: 1px solid #e2e8f0; font-size: 13px; line-height: 1.5; }
.source-chip    { display: inline-block; padding: 3px 9px; border-radius: 4px;
                  background: #f8fafc; color: #475569; font-size: 11px; margin: 3px;
                  text-decoration: none; border: 1px solid #e2e8f0; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-size: 13px; font-weight: 500; color: #94a3b8; padding: 8px 18px; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"]
    { color: #0f172a !important; border-bottom-color: #c49a3c !important; font-weight: 600; }

/* ── Buttons ── */
[data-testid="stBaseButton-secondary"] { border-color: #e2e8f0 !important; color: #475569 !important;
    font-size: 12px !important; border-radius: 5px !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: #c49a3c !important; color: #0f172a !important; }
</style>
"""
try:
    st.html(_CSS_HTML)
except AttributeError:
    st.markdown(_CSS_HTML, unsafe_allow_html=True)

# ── Logo SVG ──────────────────────────────────────────────────────────────────
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 248" width="{w}" style="display:block;margin:0 auto">
  <defs>
    <linearGradient id="lgG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8c86a"/>
      <stop offset="100%" stop-color="#b8882e"/>
    </linearGradient>
    <linearGradient id="shFill" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0%" stop-color="#192340"/>
      <stop offset="100%" stop-color="#0d1628"/>
    </linearGradient>
  </defs>

  <!-- Shield -->
  <path d="M36,14 L164,14 C174,14 176,24 176,50
           L176,108 C176,152 100,194 100,194
           C100,194 24,152 24,108 L24,50
           C24,24 26,14 36,14 Z"
        fill="url(#shFill)" stroke="url(#lgG)" stroke-width="3"/>
  <!-- Inner shield line -->
  <path d="M44,24 L156,24 C163,24 165,32 165,54
           L165,106 C165,144 100,182 100,182
           C100,182 35,144 35,106 L35,54
           C35,32 37,24 44,24 Z"
        fill="none" stroke="#c49a3c" stroke-width="0.9" opacity="0.35"/>

  <!-- Scales pivot -->
  <circle cx="100" cy="55" r="4.5" fill="#c49a3c"/>
  <!-- Vertical post -->
  <rect x="98" y="55" width="4" height="70" rx="2" fill="url(#lgG)"/>
  <!-- Base platform -->
  <rect x="78" y="121" width="44" height="5" rx="2.5" fill="url(#lgG)"/>
  <!-- Horizontal beam -->
  <rect x="42" y="68" width="116" height="4.5" rx="2.25" fill="url(#lgG)"/>

  <!-- Left V-chain -->
  <line x1="57" y1="72.5" x2="46" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="57" y1="72.5" x2="71" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Left pan -->
  <path d="M40,97 Q58,119 76,97" stroke="url(#lgG)" stroke-width="3" fill="rgba(196,154,60,0.13)" stroke-linecap="round"/>

  <!-- Right V-chain -->
  <line x1="143" y1="72.5" x2="129" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="143" y1="72.5" x2="154" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <!-- Right pan -->
  <path d="M124,97 Q142,119 160,97" stroke="url(#lgG)" stroke-width="3" fill="rgba(196,154,60,0.13)" stroke-linecap="round"/>

  <!-- HARALD -->
  <text x="100" y="224" text-anchor="middle"
        font-family="Cinzel,Georgia,serif" font-size="22" font-weight="700"
        fill="url(#lgG)" letter-spacing="6">HARALD</text>

  <!-- Divider -->
  <line x1="48" y1="231" x2="152" y2="231" stroke="#c49a3c" stroke-width="0.7" opacity="0.4"/>

  <!-- Tagline -->
  <text x="100" y="244" text-anchor="middle"
        font-family="Inter,system-ui,sans-serif" font-size="7.5" font-weight="500"
        fill="#4a6a8a" letter-spacing="2.8">LEGAL TECH AI</text>
</svg>"""

import base64 as _b64

def logo(w: int) -> str:
    svg = _LOGO_SVG.replace("{w}", str(w))
    b64 = _b64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" style="display:block;margin:0 auto"/>'


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


def kategoriser(titel: str) -> list:
    """Returnerer liste af kategorier – en sag kan have flere (fx Vedtagelse + Miljøvurdering)."""
    t = titel.lower()
    # 1. Vedtagelse af plan — bilag (miljørapport/screening) tilføjes som ekstra kategori
    is_vedtagelse = bool(re.search(r"vedtagelse af\b.{0,80}?(lokalplan|kommuneplantillæg|kommuneplan)", t))
    if is_vedtagelse:
        if "dispensation" in t:
            kats = ["Dispensation"]
        elif "overensstemmelse" in t:
            kats = ["Overensstemmelse"]
        else:
            kats = ["Vedtagelse"]
        if "screeningsafgørelse" in t:
            kats.append("Screening")
        if "miljørapport" in t or "miljøvurdering" in t or "vvm" in t:
            kats.append("Miljøvurdering")
        return kats
    # 2. Screening = screeningsafgørelse (beslutning om IKKE at udarbejde miljørapport)
    if "screeningsafgørelse" in t or "screeningen" in t:
        return ["Screening"]
    # 3. Miljøvurdering = faktisk miljørapport udarbejdet
    if "miljøvurdering" in t or "miljørapport" in t or "vvm" in t:
        return ["Miljøvurdering"]
    # 4. Øvrige plan-sager
    if "lokalplan" in t:
        if "dispensation" in t:        return ["Dispensation"]
        if "overensstemmelse" in t:    return ["Overensstemmelse"]
        return ["Andet"]
    if "kommuneplantillæg" in t or re.search(r"kommuneplan(?!tillæg)", t):
        return ["Andet"]
    if "landzone" in t:             return ["Landzone"]
    if "strandbeskyttelse" in t:    return ["Strandbeskyttelse"]
    if "skovloven" in t or " skov " in t: return ["Skovloven"]
    if "fredning" in t:             return ["Fredning"]
    if "opsættende virkning" in t:  return ["Opsættende virkning"]
    return ["Andet"]


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
def load_data(version: int = 7):  # bump version to bust cache
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
    df["Kategori"]        = df["Titel"].apply(kategoriser)
    df["Kategori_primær"] = df["Kategori"].apply(lambda x: x[0])
    df["Plantype"]        = df["Titel"].apply(detect_plantype)
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
  <div class="h-logo-box">{logo(152)}</div>
  <span class="h-sub">Planklagenævnets Vidensbase</span>
</div>""", unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Søgning</span>', unsafe_allow_html=True)
    søg_input   = st.text_input("", placeholder="f.eks. terrasse lokalplan…", label_visibility="collapsed")

    st.markdown('<span class="h-filter-label">Kategori</span>', unsafe_allow_html=True)
    _alle_kats  = sorted({k for kats in df["Kategori"] for k in kats})
    valgte_kats = st.multiselect("", _alle_kats, label_visibility="collapsed", key="kat")
    isoler_kat  = st.checkbox("Isoler (kun rene sager)", key="iso_kat") if valgte_kats else False

    st.markdown('<span class="h-filter-label">Plantype</span>', unsafe_allow_html=True)
    plantype_valg = st.multiselect("", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"], label_visibility="collapsed", key="pt")
    isoler_pt     = st.checkbox("Isoler (kun rene sager)", key="iso_pt") if plantype_valg else False

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
if valgte_kats:
    if isoler_kat:
        mask &= df["Kategori"].apply(lambda kats: set(kats).issubset(set(valgte_kats)))
    else:
        mask &= df["Kategori"].apply(lambda kats: any(k in kats for k in valgte_kats))
if plantype_valg:
    if isoler_pt:
        mask &= df["Plantype"].apply(lambda pts: set(pts).issubset(set(plantype_valg)))
    else:
        mask &= df["Plantype"].apply(lambda pts: any(pt in pts for pt in plantype_valg))
if sagsgruppe_valg: mask &= df["Sagsgruppe"].isin(sagsgruppe_valg)
if udfald_valg:     mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx   = df[mask].index.tolist()

# Nulstil side-tæller når filteret ændrer sig
_filter_sig = (len(df_filter), df_filter["Link"].iloc[0] if len(df_filter) > 0 else "")
if st.session_state.get("_filter_sig") != _filter_sig:
    st.session_state["vis_antal"] = 25
    st.session_state["_filter_sig"] = _filter_sig

_vis_antal = st.session_state.get("vis_antal", 25)

if søg_input.strip():
    df_vis = tfidf_søg(søg_input, df, vec, mat, sub_idx=sub_idx, top_n=25)
else:
    df_vis = df_filter.sort_values("Dato", ascending=False).head(_vis_antal)


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
            f"KATEGORI:   {' / '.join(row.get('Kategori', ['–']))}  |  PLANTYPE: {', '.join(row.get('Plantype', ['–']))}",
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
<div class="h-page-header">
  <h1 class="h-page-title">HARALD</h1>
  <div class="h-gold-line"></div>
  <p class="h-page-meta">Planklagenævnets afgørelsesdatabase &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {int(df['År'].min())}–{int(df['År'].max())}</p>
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
        c2.metric("Kategori",   " / ".join(row["Kategori"]))
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
  <div class="pkn-card-meta">{dato_str} &nbsp;·&nbsp; {" / ".join(row['Kategori'])} &nbsp;·&nbsp; {row['Sagsgruppe']}
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

            if not søg_input.strip() and _vis_antal < total_filtreret:
                tilbage = total_filtreret - _vis_antal
                if st.button(f"Vis 25 mere ({tilbage} tilbage)", use_container_width=True):
                    st.session_state["vis_antal"] = _vis_antal + 25
                    st.rerun()

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
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kategori_primær"].nunique()}</div>'
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
        kat_df = d.groupby("Kategori_primær").size().reset_index(name="Antal").rename(columns={"Kategori_primær": "Kategori"})
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
        mr = (d.groupby("Kategori_primær")
               .apply(lambda x: pd.Series({
                   "Sager": len(x),
                   "Medhold_%": round((x["Udfald"]=="Medhold").mean()*100, 1)
               }), include_groups=False)
               .reset_index()
               .rename(columns={"Kategori_primær": "Kategori"})
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

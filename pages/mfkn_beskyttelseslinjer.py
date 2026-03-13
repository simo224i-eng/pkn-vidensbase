import streamlit as st
import pandas as pd
import re
import csv
import zipfile
import os
import numpy as np
import plotly.express as px
import requests
from shared import logo, _llm, strip_html, extract_kommune, BADGE, format_afgørelse_tekst, render_detail_header

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── MFKN farveaccent (grøn i stedet for guld) ─────────────────────────────────
_MFKN_CSS = """<style>
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #2d6a4f !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a { color: #52b788 !important; }
[data-testid="collapsedControl"]::after { color: #52b788 !important; }
.pkn-card:hover { border-color: #2d6a4f !important; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { border-bottom-color: #2d6a4f !important; }
.h-gold-line { background: #2d6a4f !important; }
.detail-gold-line { background: #2d6a4f !important; }
.detail-ai-title { color: #52b788 !important; }
.detail-source-link:hover { border-color: #2d6a4f !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: #2d6a4f !important; }
</style>"""
try:
    st.html(_MFKN_CSS)
except AttributeError:
    st.markdown(_MFKN_CSS, unsafe_allow_html=True)

# ── MFKN-specifikke hjælpefunktioner ─────────────────────────────────────────

def kategoriser_mfkn(titel: str, tekst: str = "") -> str:
    t = (titel + " " + tekst[:800]).lower()
    if "strandbeskyttelseslinje" in t or "havstokken" in t or "§ 15, stk. 1" in t or "§ 15 a" in t:
        return "Strandbeskyttelseslinje"
    if "fortidsmindebeskyttelseslinje" in t:
        return "Fortidsmindebeskyttelseslinje"
    if "åbeskyttelseslinje" in t:
        return "Åbeskyttelseslinje"
    if "søbeskyttelseslinje" in t:
        return "Søbeskyttelseslinje"
    if "skovbyggelinje" in t:
        return "Skovbyggelinje"
    if "klitfredning" in t or "klitfredede" in t:
        return "Klitfredning"
    if "kirkebeskyttelseslinje" in t:
        return "Kirkebeskyttelseslinje"
    return "Andet"


def detect_udfald_mfkn(titel: str) -> str:
    t = titel.lower()
    if "hjemvisning" in t or "hjemvises" in t or "hjemvist" in t:
        return "Hjemvist"
    if "ophævelse" in t or "ophævet" in t:
        return "Ophævet"
    if "ændring" in t:
        return "Ændring"
    if "afvisning" in t or "afvises" in t:
        return "Afvist"
    if "stadfæstelse" in t or "stadfæstes" in t:
        return "Stadfæstelse"
    return "Ukendt"


def detect_sagsgruppe_mfkn(titel: str) -> str:
    t = titel.lower()
    if "genoptagelse" in t:
        return "Genoptagelse"
    if "opsættende virkning" in t or "afslag på opsættende" in t:
        return "Opsættende virkning"
    if "afvisning" in t or "afvises" in t:
        return "Afvisning"
    return "Realitetsbehandling"


BADGE_MFKN = {
    "Stadfæstelse": "badge-ikke-medhold",
    "Ophævet":      "badge-ophaevet",
    "Hjemvist":     "badge-ophaevet",
    "Ændring":      "badge-medhold",
    "Afvist":       "badge-afvist",
    "Ukendt":       "badge-ukendt",
}

# ── Data-loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser afgørelser…", ttl=None)
def _læs_mfkn_csv(sti: str) -> list:
    rows = []
    with open(sti, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tekst = strip_html(row["Tekst"], preserve_headings=True)
            excerpt_clean = re.sub(r'^#{2,3} ', '', tekst, flags=re.M).replace('\n', ' ')
            excerpt_clean = re.sub(r'\s+', ' ', excerpt_clean).strip()
            rows.append({
                "Dato":    row["Dato"],
                "Titel":   row["Titel"],
                "Link":    row["Link"],
                "Tekst":   tekst,
                "Excerpt": excerpt_clean[:280],
            })
    return rows


def load_mfkn_data(version: int = 4):
    csv_sti = "mfkn_nbl_beskyttelseslinier.csv"
    zip_sti = csv_sti + ".zip"
    if not os.path.exists(csv_sti) and os.path.exists(zip_sti):
        with zipfile.ZipFile(zip_sti) as z:
            z.extract("mfkn_nbl_beskyttelseslinier.csv", ".")
    csv.field_size_limit(10_000_000)
    rows = _læs_mfkn_csv(csv_sti)
    df = pd.DataFrame(rows)
    df["Dato"]      = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"]        = df["Dato"].dt.year.astype("Int64")
    df["Kategori"]  = df.apply(lambda r: kategoriser_mfkn(r["Titel"], r["Tekst"]), axis=1)
    df["Udfald"]    = df["Titel"].apply(detect_udfald_mfkn)
    df["Sagsgruppe"] = df["Titel"].apply(detect_sagsgruppe_mfkn)
    df["Kommune"]   = df["Titel"].apply(extract_kommune)
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_mfkn_index(n_rows: int):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_mfkn_data(1)
    texts = (df2["Titel"] + " " + df2["Tekst"]).tolist()
    vec = TfidfVectorizer(max_features=40_000, ngram_range=(1, 2), min_df=2, sublinear_tf=True)
    mat = vec.fit_transform(texts)
    return vec, mat


def tfidf_søg_mfkn(query: str, df, vec, mat, sub_idx=None, top_n: int = 30):
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


def mfkn_svar(spørgsmål: str, docs: list, historik: list = None) -> str:
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    kontekst = "\n\n".join(
        f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}\n{d['Tekst']}"
        for i, d in enumerate(docs)
    )
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    prompt = f"""Du er en juridisk assistent specialiseret i dansk naturbeskyttelseslovgivning og MFKN's praksis for beskyttelseslinjer.
Besvar følgende spørgsmål KUN baseret på de vedlagte MFKN-afgørelser.
Brug ALTID referencerne i formatet [Kilde X] efter hvert udsagn – f.eks. [Kilde 3] eller [Kilde 1, 2].
Svar på dansk, præcist og struktureret med overskrifter og afsnit.
Hvis spørgsmålet er et opfølgningsspørgsmål, brug den tidligere samtale som kontekst.
{samtale_blok}
SPØRGSMÅL: {spørgsmål}

AFGØRELSER:
{kontekst}

SVAR:"""
    return _llm(prompt)


def mfkn_resumé(titel: str, tekst: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Ingen API-nøgle."
    prompt = f"""Lav et kort, struktureret resumé af denne MFKN-afgørelse om beskyttelseslinjer på dansk.
Inkluder: Sagens kerne (hvilken beskyttelseslinje, hvad søges der dispensation til),
Nævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {tekst[:3000]}

RESUMÉ:"""
    return _llm(prompt)


def erstat_kilde_refs_mfkn(tekst: str, kilder: list) -> str:
    def repl(m):
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
        refs = []
        for n in nums:
            if 1 <= n <= len(kilder):
                k = kilder[n - 1]
                kom = extract_kommune(k.get("Titel", "")) or "Kilde"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = "–"
                refs.append(f"*{kom} {år}*")
        return "[" + ", ".join(refs) + "]" if refs else m.group(0)
    return re.sub(r"\[Kilde\s+([\d,\s]+)\]", repl, tekst)


# ── Session state ─────────────────────────────────────────────────────────────
if "mfkn_chat"     not in st.session_state: st.session_state.mfkn_chat     = []
if "mfkn_valgt"    not in st.session_state: st.session_state.mfkn_valgt    = None
if "mfkn_ai_adg"   not in st.session_state: st.session_state.mfkn_ai_adg   = False
if "mfkn_res_adg"  not in st.session_state: st.session_state.mfkn_res_adg  = False

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_mfkn_data(1)
vec, mat = build_mfkn_index(len(df))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(152)}</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Søgeord</span>', unsafe_allow_html=True)
    søg_input = st.text_input("", placeholder="f.eks. terrasse strandbeskyttelse…", label_visibility="collapsed")
    søge_type = st.radio("", ["Præcis", "Semantisk"], horizontal=True, label_visibility="collapsed", key="mfkn_søgetype")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Beskyttelseslinje</span>', unsafe_allow_html=True)
    _alle_kats = sorted(df["Kategori"].unique())
    valgte_kats = st.multiselect("", _alle_kats, label_visibility="collapsed", key="mfkn_kat")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Sagsgruppe</span>', unsafe_allow_html=True)
    sagsgruppe_valg = st.multiselect("", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"],
                                     label_visibility="collapsed", key="mfkn_sg")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Årsinterval</span>', unsafe_allow_html=True)
    år_min, år_max  = int(df["År"].min()), int(df["År"].max())
    _default_start  = max(2017, år_min)
    år_range = st.slider("", år_min, år_max, (_default_start, år_max), label_visibility="collapsed", key="mfkn_yr")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Udfald</span>', unsafe_allow_html=True)
    udfald_valg = st.multiselect("", ["Stadfæstelse", "Ophævet", "Ændring", "Afvist", "Hjemvist", "Ukendt"],
                                 label_visibility="collapsed", key="mfkn_ud")

    st.markdown("---")
    st.markdown(f"<span style='font-size:12px;color:#5a7a9e'>**{len(df):,}** afgørelser &nbsp;·&nbsp; {år_min}–{år_max}</span>",
                unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:11px;color:#3d5878'>Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>",
                unsafe_allow_html=True)


# ── Filtrering ────────────────────────────────────────────────────────────────
mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if valgte_kats:     mask &= df["Kategori"].isin(valgte_kats)
if sagsgruppe_valg: mask &= df["Sagsgruppe"].isin(sagsgruppe_valg)
if udfald_valg:     mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx   = df[mask].index.tolist()

_filter_sig = (len(df_filter), df_filter["Link"].iloc[0] if len(df_filter) > 0 else "", søg_input.strip(), søge_type)
if st.session_state.get("mfkn_filter_sig") != _filter_sig:
    st.session_state["mfkn_vis_antal"] = 25
    st.session_state["mfkn_filter_sig"] = _filter_sig

_vis_antal = st.session_state.get("mfkn_vis_antal", 25)

if søg_input.strip() and søge_type == "Semantisk":
    df_vis     = tfidf_søg_mfkn(søg_input.strip(), df, vec, mat, sub_idx=sub_idx)
    ai_sub_idx = sub_idx
elif søg_input.strip():
    _text_mask = (
        df_filter["Titel"].str.contains(søg_input.strip(), case=False, na=False, regex=False) |
        df_filter["Tekst"].str.contains(søg_input.strip(), case=False, na=False, regex=False)
    )
    df_vis     = df_filter[_text_mask].sort_values("Dato", ascending=False).reset_index(drop=True)
    ai_sub_idx = [sub_idx[i] for i in df_filter.index[_text_mask].tolist()] if _text_mask.any() else sub_idx
else:
    df_vis = df_filter.sort_values("Dato", ascending=False)
    ai_sub_idx = sub_idx

# Download
with st.sidebar:
    n = len(df_filter)
    st.markdown("---")
    if n == 0:
        st.caption("Ingen afgørelser matcher filtrene.")
    else:
        def _dl_tekst(data: pd.DataFrame) -> str:
            lines = [
                "MFKN BESKYTTELSESLINJER – EKSPORT",
                f"Antal: {len(data)}",
                f"Genereret: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
                "=" * 72, "",
            ]
            for _, row in data.iterrows():
                dato = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                lines += [
                    f"AFGØRELSE:  {row['Titel']}",
                    f"DATO:       {dato}",
                    f"KATEGORI:   {row['Kategori']}  |  SAGSGRUPPE: {row['Sagsgruppe']}",
                    f"UDFALD:     {row['Udfald']}  |  KOMMUNE: {row['Kommune'] or '–'}",
                    f"KILDE:      {row['Link']}",
                    "-" * 72,
                    row["Tekst"].strip(), "", "=" * 72, "",
                ]
            return "\n".join(lines)

        st.download_button(
            label=f"⬇️ Download {n:,} afgørelser (.txt)",
            data=_dl_tekst(df_filter).encode("utf-8"),
            file_name="mfkn_beskyttelseslinjer.txt",
            mime="text/plain",
        )

# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header">
  <h1 class="h-page-title">HARALD</h1>
  <div class="h-gold-line"></div>
  <p class="h-page-meta">MFKN · Beskyttelseslinjer &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {år_min}–{år_max}</p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_søg, tab_stat, tab_ai = st.tabs(["  Afgørelser  ", "  Statistik  ", "  AI Assistent  "])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – AFGØRELSER
# ════════════════════════════════════════════════════════════════════════════
with tab_søg:

    if st.session_state.mfkn_valgt is not None:
        row = st.session_state.mfkn_valgt

        if st.button("← Alle afgørelser"):
            st.session_state.mfkn_valgt = None
            st.rerun()

        badge_cls = BADGE_MFKN.get(row.get("Udfald", ""), "badge-ukendt")
        dato_str  = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y")
        sagsgruppe = row.get("Sagsgruppe") or "–"
        kommune    = row.get("Kommune") or "–"
        udfald     = row.get("Udfald") or "Ukendt"
        kategori   = row.get("Kategori") or "–"

        chip_styles = {
            "Stadfæstelse": "background:#fef2f2;color:#991b1b;border-color:#fecaca",
            "Ophævet":      "background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe",
            "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe",
            "Ændring":      "background:#f0fdf4;color:#166534;border-color:#bbf7d0",
            "Afvist":       "background:#fffbeb;color:#92400e;border-color:#fde68a",
        }
        chip_s = chip_styles.get(udfald, "background:#f8fafc;color:#64748b;border-color:#e2e8f0")

        st.markdown(
            render_detail_header(
                titel=row["Titel"],
                udfald=udfald,
                chip_style=chip_s,
                dato_str=dato_str,
                meta_extra=[("Beskyttelseslinje", kategori), ("Sagsgruppe", sagsgruppe), ("Kommune", kommune)],
                link=row["Link"],
                link_label="Åbn original på MFKN's hjemmeside",
                accent="#2d6a4f",
            ),
            unsafe_allow_html=True,
        )

        col_tekst, col_ai = st.columns([3, 2], gap="large")
        with col_tekst:
            st.markdown(format_afgørelse_tekst(row["Tekst"]), unsafe_allow_html=True)

        with col_ai:
            st.markdown(
                '<div class="detail-ai-panel">'
                '<div class="detail-ai-title">✦ &nbsp;AI-Resumé</div>',
                unsafe_allow_html=True
            )
            if st.button("Generer resumé →", key="mfkn_gen_res"):
                with st.spinner("Analyserer…"):
                    try:
                        st.session_state.mfkn_resumé = mfkn_resumé(row["Titel"], row["Tekst"])
                    except Exception as e:
                        st.session_state.mfkn_resumé = f"Fejl: {e}"
            if "mfkn_resumé" in st.session_state:
                    st.markdown(
                        f'<div class="detail-ai-resume">{st.session_state.mfkn_resumé}</div>',
                        unsafe_allow_html=True
                    )
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        total_filtreret = len(df_filter)
        hits = len(df_vis)
        if søg_input:
            label = f"**{hits}** resultater for \"{søg_input}\" (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {min(_vis_antal, hits)} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            st.warning("Ingen resultater – prøv andre søgeord eller filtre.")
        else:
            _BADGE_STYLE_MFKN = {
                "Medhold":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Ikke medhold": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Ophævet":      "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
                "Afvist":       "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
                "Stadfæstelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Ændring":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
            }
            _BADGE_DEFAULT_MFKN = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"
            for _, row in df_vis.head(_vis_antal).iterrows():
                badge_style = _BADGE_STYLE_MFKN.get(row["Udfald"], _BADGE_DEFAULT_MFKN)
                dato_str  = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:.2px;">{dato_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.1px;{badge_style}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{row['Titel']}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{row['Kategori']}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{row['Sagsgruppe']}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{row['Excerpt']}…</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn afgørelse på portalen ↗</a>
  </div>
</div>""", unsafe_allow_html=True)
                if st.button("Læs afgørelse →", key=f"mfkn_btn_{row['Link'][-20:]}"):
                    st.session_state.mfkn_valgt = row.to_dict()
                    if "mfkn_resumé" in st.session_state:
                        del st.session_state["mfkn_resumé"]
                    st.rerun()

            if _vis_antal < hits:
                tilbage = hits - _vis_antal
                if st.button(f"Vis 25 mere ({tilbage} tilbage)", use_container_width=True):
                    st.session_state["mfkn_vis_antal"] = _vis_antal + 25
                    st.rerun()

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 – STATISTIK
# ════════════════════════════════════════════════════════════════════════════
with tab_stat:
    d = df_filter

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(d):,}</div>'
                    f'<div class="stat-label">Afgørelser</div></div>', unsafe_allow_html=True)
    with k2:
        pct = (d["Udfald"] == "Ophævet").mean() * 100
        st.markdown(f'<div class="stat-card"><div class="stat-number">{pct:.0f}%</div>'
                    f'<div class="stat-label">Ophævet-rate</div></div>', unsafe_allow_html=True)
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
        fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#2d6a4f"])
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Fordeling på beskyttelseslinje")
        kat_df = d.groupby("Kategori").size().reset_index(name="Antal")
        fig2 = px.pie(kat_df, values="Antal", names="Kategori",
                      color_discrete_sequence=px.colors.sequential.Greens_r, hole=0.4)
        fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig2, use_container_width=True)

    col_ll, col_rr = st.columns(2)

    with col_ll:
        st.markdown("#### Udfald over tid")
        udfald_år = d.groupby(["År", "Udfald"]).size().reset_index(name="Antal")
        farver = {
            "Stadfæstelse": "#ef4444", "Ophævet": "#8b5cf6",
            "Ændring": "#10b981", "Afvist": "#f59e0b",
            "Hjemvist": "#6366f1", "Ukendt": "#94a3b8",
        }
        fig3 = px.bar(udfald_år, x="År", y="Antal", color="Udfald",
                      color_discrete_map=farver, barmode="stack")
        fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig3, use_container_width=True)

    with col_rr:
        st.markdown("#### Top 15 kommuner")
        kom_df = (d.dropna(subset=["Kommune"]).groupby("Kommune").size()
                   .reset_index(name="Sager").sort_values("Sager", ascending=True).tail(15))
        fig4 = px.bar(kom_df, x="Sager", y="Kommune", orientation="h",
                      color_discrete_sequence=["#2d6a4f"])
        fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### Udfald per beskyttelseslinje")
    if d.empty:
        st.info("Ingen data med de valgte filtre.")
    else:
        mr = (d.groupby("Kategori")
               .apply(lambda x: pd.Series({
                   "Sager": len(x),
                   "Ophævet_%": round((x["Udfald"] == "Ophævet").mean() * 100, 1),
               }), include_groups=False)
               .reset_index()
               .sort_values("Ophævet_%", ascending=True))
        fig5 = px.bar(mr, x="Ophævet_%", y="Kategori", orientation="h",
                      color="Ophævet_%", color_continuous_scale=["#fee2e2", "#10b981"],
                      hover_data={"Sager": True},
                      labels={"Ophævet_%": "Ophævet (%)"})
        fig5.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                           coloraxis_showscale=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig5, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.markdown("### 🤖 Spørg til MFKN-praksis")

    n_ai = len(ai_sub_idx)
    filter_tekst = f"alle **{len(df):,}** afgørelser" if n_ai == len(df) else f"**{n_ai:,}** afgørelser (filtreret)"
    st.markdown(f"AI'en søger i {filter_tekst} og svarer med kildehenvisninger.")

    if not ANTHROPIC_API_KEY:
        st.error("Tilføj `ANTHROPIC_API_KEY` i Streamlit secrets.")
    else:
        forslag = [
            "Hvornår gives der dispensation fra strandbeskyttelseslinjen?",
            "Hvad er praksis for fortidsmindebeskyttelseslinjen?",
            "Hvornår ophæver MFKN kommunens afgørelse?",
            "Hvilke hensyn vægtes ved skovbyggelinjen?",
        ]
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"mfkn_fs_{i}"):
                st.session_state.mfkn_chat.append({"rolle": "bruger", "tekst": f})
                with st.spinner("Søger og genererer svar…"):
                    hits_ai = tfidf_søg_mfkn(f, df, vec, mat, sub_idx=ai_sub_idx, top_n=8)
                    try:
                        svar = mfkn_svar(f, hits_ai.to_dict("records"), historik=st.session_state.mfkn_chat)
                    except Exception as e:
                        svar = f"Fejl: {e}"
                st.session_state.mfkn_chat.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
                st.rerun()

        for msg_idx, msg in enumerate(st.session_state.mfkn_chat):
            if msg["rolle"] == "bruger":
                st.markdown(f'<div class="chat-user">{msg["tekst"]}</div>', unsafe_allow_html=True)
            else:
                kilder = msg.get("kilder", [])
                vist_tekst = erstat_kilde_refs_mfkn(msg["tekst"], kilder) if kilder else msg["tekst"]

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    st.markdown(f'<div class="chat-assistant">{vist_tekst}</div>', unsafe_allow_html=True)
                with col_kld:
                    if kilder:
                        st.markdown(
                            '<div style="font-size:11px;font-weight:700;color:#475569;'
                            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                            'Kilder</div>', unsafe_allow_html=True
                        )
                        kilde_søg = st.text_input(
                            "", placeholder="Søg i kilder…",
                            key=f"kilde_søg_{msg_idx}",
                            label_visibility="collapsed",
                        )
                        filtrerede_kilder = [
                            k for k in kilder[:8]
                            if not kilde_søg.strip() or
                            kilde_søg.lower() in k.get("Titel", "").lower() or
                            kilde_søg.lower() in k.get("Tekst", "").lower()
                        ]
                        if kilde_søg.strip() and not filtrerede_kilder:
                            st.caption("Ingen kilder matcher søgningen.")
                        for i, k in enumerate(filtrerede_kilder):
                            try:
                                dato_str = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
                                år_str   = str(pd.Timestamp(k["Dato"]).year)
                            except Exception:
                                dato_str = "–"
                                år_str   = "–"
                            kommune  = extract_kommune(k.get("Titel", "")) or "Ukendt"
                            udfald   = k.get("Udfald", "")
                            badge_cls = BADGE_MFKN.get(udfald, "badge-ukendt")
                            badge_html = f'<span class="pkn-badge {badge_cls}">{udfald}</span>' if udfald else ""

                            with st.expander(f"[{i+1}] {kommune} · {år_str}"):
                                if st.button(f"▶ Åbn afgørelsen", key=f"mfkn_kilde_{msg_idx}_{i}",
                                             use_container_width=True, type="primary"):
                                    st.session_state.mfkn_valgt = k
                                    if "mfkn_resumé" in st.session_state:
                                        del st.session_state["mfkn_resumé"]
                                    st.rerun()
                                st.markdown(
                                    f'<div style="font-size:13px;font-weight:600;color:#1e3a5f;'
                                    f'margin:8px 0 4px;line-height:1.4">{k["Titel"]}</div>',
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f'<div style="font-size:11px;color:#64748b;margin-bottom:10px">'
                                    f'{dato_str} &nbsp;·&nbsp; {k.get("Sagsgruppe","")}'
                                    f'&nbsp;&nbsp;{badge_html}</div>',
                                    unsafe_allow_html=True
                                )
                                tekst_fmt = re.sub(r'\. ([A-ZÆØÅ])', r'.</p><p>\1', k.get("Tekst",""))
                                st.markdown(
                                    f'<div style="font-size:13px;line-height:1.7;color:#1e293b;'
                                    f'max-height:420px;overflow-y:auto;padding:12px 14px;'
                                    f'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;'
                                    f'margin-bottom:8px"><p>{tekst_fmt}</p></div>',
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f'<a href="{k["Link"]}" target="_blank" '
                                    f'style="font-size:12px;color:#2563eb;text-decoration:none">'
                                    f'Åbn original afgørelse på MFKN\'s hjemmeside ↗</a>',
                                    unsafe_allow_html=True
                                )

        with st.form("mfkn_chat_form", clear_on_submit=True):
            spørgsmål = st.text_area("Dit spørgsmål", height=80,
                                      placeholder="Hvad er MFKN's praksis for…?")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send ➤", use_container_width=True, type="primary")
            ryd  = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.mfkn_chat = []
            st.rerun()

        if send and spørgsmål.strip():
            st.session_state.mfkn_chat.append({"rolle": "bruger", "tekst": spørgsmål})
            with st.spinner("Søger og genererer svar…"):
                hits_ai = tfidf_søg_mfkn(spørgsmål, df, vec, mat, sub_idx=ai_sub_idx, top_n=8)
                try:
                    svar = mfkn_svar(spørgsmål, hits_ai.to_dict("records"),
                                     historik=st.session_state.mfkn_chat)
                except Exception as e:
                    svar = f"Fejl ved API: {e}"
            st.session_state.mfkn_chat.append(
                {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
            st.rerun()

import streamlit as st
import pandas as pd
import re
import csv
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from shared import logo, _llm, strip_html, extract_kommune, BADGE

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── PKN-specifikke hjælpefunktioner ─────────────────────────────────────────

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
    is_plan = bool(re.search(r"lokalplan|kommuneplantillæg|kommuneplan|byplanvedtægt", t))
    is_vedtagelse = bool(re.search(r"vedtagelse af\b.{0,80}?(lokalplan|kommuneplantillæg|kommuneplan|byplanvedtægt)", t))
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
    # 2. Screening = screeningsafgørelse
    if "screeningsafgørelse" in t or "screeningen" in t:
        return ["Screening"]
    # 3. Miljøvurdering = faktisk miljørapport udarbejdet
    if "miljøvurdering" in t or "miljørapport" in t or re.search(r"\bvvm\b", t):
        return ["Miljøvurdering"]
    # 4. Dispensation – lokalplan, kommuneplan eller byplanvedtægt
    if "dispensation" in t and is_plan:
        return ["Dispensation"]
    if "dispensation" in t and any(k in t for k in ("byplanvedtægt", "planlovens", "planlov", "servitut")):
        return ["Dispensation"]
    # 5. Overensstemmelse
    if "overensstemmelse" in t and is_plan:
        return ["Overensstemmelse"]
    # 6. Planvedtagelse uden "vedtagelse af" (f.eks. "endelig vedtagelse")
    if re.search(r"endelig vedtagelse", t) and is_plan:
        return ["Vedtagelse"]
    # 7. Øvrige plan-sager der nævner en plantype
    if "lokalplan" in t or "byplanvedtægt" in t:
        return ["Andet"]
    if "kommuneplantillæg" in t or re.search(r"kommuneplan(?!tillæg)", t):
        return ["Andet"]
    # 8. Temabaserede kategorier
    if "landzone" in t: return ["Landzone"]
    return ["Andet"]


def _strip_html(t: str) -> str:
    import html as _html
    return _html.unescape(re.sub(r"<[^>]+>", " ", str(t)))


def detect_udfald(titel: str, tekst: str = "") -> str:
    titel = titel or ""
    tekst = tekst or ""
    t = titel.lower()

    # ── Procedurelle sager – detektér direkte fra titel ──────────────────────
    if "planklagenævnet orienterer" in t:               return "Orientering"
    if re.search(r"afslag på gen[p]?tagelse", t):       return "Afvist"
    if "afslag på opsættende virkning" in t:            return "Afvist"
    if "meddelelse af opsættende virkning" in t:        return "Medhold"

    # ── Realitetsafgørelser – titel ───────────────────────────────────────────
    if any(k in t for k in ("ophævet", "ugyldig", "ugyldigt", "annulleret",
                             "hjemvisning", "hjemvises")):       return "Ophævet"
    if "medhold" in t:                                           return "Medhold"
    if "stadfæst" in t or "ikke medhold" in t:                  return "Ikke medhold"
    if "afvisning" in t or "afvises" in t:                       return "Afvist"

    # ── Brødtekst – brug SIDSTE "Afsluttende bemærkninger"-sektion ───────────
    tx = _strip_html(tekst).lower()
    positions = [m.start() for m in re.finditer(r"afsluttende bem[æa]rkninger", tx)]
    conc = tx[positions[-1]:positions[-1] + 600] if positions else tx[-1000:]

    if any(k in conc for k in ("ophæver", "hjemviser", "hjemvisning", "ugyldiggør")):
        return "Ophævet"
    if "kan ikke give medhold" in conc or "ikke medhold" in conc or "stadfæst" in conc:
        return "Ikke medhold"
    if "afviser" in conc and ("klagen" in conc or "klager" in conc):
        return "Afvist"
    if "medhold" in conc:
        return "Medhold"

    # ── Bredere søgning i hele teksten ───────────────────────────────────────
    if "klagen tages til følge" in tx:                           return "Medhold"
    if "klagen tages ikke til følge" in tx:                      return "Ikke medhold"
    if "nævnet ophæver" in tx or "ophæves hermed" in tx:        return "Ophævet"
    if "nævnet stadfæster" in tx or "stadfæstes hermed" in tx:  return "Ikke medhold"

    return "Ukendt"

def detect_sagsgruppe(titel: str, tekst: str) -> str:
    t = (titel + " " + tekst[:500]).lower()
    if "genoptagelse" in t:    return "Genoptagelse"
    if "opsættende virkning" in t or "afslag på opsættende" in t: return "Opsættende virkning"
    if "afvisning" in t or "afvises" in t or "klageberettiget" in t: return "Afvisning"
    return "Realitetsbehandling"



# ── Data-loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser 4.780 afgørelser…", ttl=None, hash_funcs=None)
def _læs_csv(sti: str) -> list:
    """Læser én CSV og returnerer en liste af rækker med renset tekst."""
    rows = []
    with open(sti, newline="", encoding="utf-8") as f:
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
    return rows


def load_data(version: int = 12):  # bump version to bust cache
    import os, zipfile
    # --- primær fil (zip → csv) ---
    if not os.path.exists("pkn_vidensbase_fuld_tekst.csv"):
        with zipfile.ZipFile("pkn_vidensbase_fuld_tekst.csv.zip") as z:
            z.extractall(".")
    csv.field_size_limit(10_000_000)
    rows = _læs_csv("pkn_vidensbase_fuld_tekst.csv")

    # --- supplerende fil (miljøvurderingsloven) ---
    ekstra_sti = "pkn_miljoevurderingsloven_fuld_tekst.csv"
    ekstra_zip = ekstra_sti + ".zip"
    if not os.path.exists(ekstra_sti) and os.path.exists(ekstra_zip):
        with zipfile.ZipFile(ekstra_zip) as z:
            z.extractall(".")
    if os.path.exists(ekstra_sti):
        ekstra = _læs_csv(ekstra_sti)
        eksisterende_links = {r["Link"] for r in rows}
        tilføjet = sum(
            1 for r in ekstra
            if r["Link"] not in eksisterende_links
            and not rows.append(r)  # append returnerer None → tæl
        )
        _ = tilføjet  # brugt til evt. logging

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
    df2 = load_data(11)
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


def gemini_svar(spørgsmål: str, docs: list, historik: list = None) -> str:
    if not ANTHROPIC_API_KEY:
        return "Tilføj GEMINI_API_KEY i Streamlit secrets."
    kontekst = "\n\n".join(
        f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}\n{d['Tekst']}"
        for i, d in enumerate(docs)
    )
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:  # ekskluder det aktuelle spørgsmål
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    prompt = f"""Du er en juridisk assistent specialiseret i dansk planlovgivning og PKN-praksis.
Besvar følgende spørgsmål KUN baseret på de vedlagte PKN-afgørelser.
Brug ALTID referencerne i formatet [Kilde X] efter hvert udsagn der stammer fra en afgørelse – f.eks. [Kilde 3] eller [Kilde 1, 2].
Svar på dansk, præcist og struktureret med overskrifter og afsnit.
Hvis spørgsmålet er et opfølgningsspørgsmål, brug den tidligere samtale som kontekst.
{samtale_blok}
SPØRGSMÅL: {spørgsmål}

AFGØRELSER:
{kontekst}

SVAR:"""
    return _llm(prompt)


def gemini_resumé(titel: str, tekst: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Ingen API-nøgle."
    prompt = f"""Lav et kort, struktureret resumé af denne PKN-afgørelse på dansk.
Inkluder: Sagens kerne, Klagenævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {tekst[:3000]}

RESUMÉ:"""
    return _llm(prompt)


def erstat_kilde_refs(tekst: str, kilder: list) -> str:
    """Erstat [Kilde X] / [Kilde X, Y] i AI-svaret med KommuneNavn · År."""
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
if "chat_historik"   not in st.session_state: st.session_state.chat_historik   = []
if "valgt_afgørelse" not in st.session_state: st.session_state.valgt_afgørelse = None
if "ai_adgang"       not in st.session_state: st.session_state.ai_adgang       = False
if "resumé_adgang"   not in st.session_state: st.session_state.resumé_adgang   = False

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_data(11)
vec, mat = build_index(len(df))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(152)}</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Søgeord (f.eks. planlovens § 15)</span>', unsafe_allow_html=True)
    søg_input   = st.text_input("", placeholder="f.eks. terrasse lokalplan…", label_visibility="collapsed")

    st.markdown('<span class="h-filter-label">Kategori</span>', unsafe_allow_html=True)
    _alle_kats  = sorted({k for kats in df["Kategori"] for k in kats})
    valgte_kats = st.multiselect("", _alle_kats, label_visibility="collapsed", key="kat")
    _isoler_relevant = bool(valgte_kats and set(valgte_kats) & {"Vedtagelse", "Screening", "Miljøvurdering"})
    isoler_kat  = st.checkbox("Isoler (kun rene sager)", key="iso_kat") if _isoler_relevant else False

    st.markdown('<span class="h-filter-label">Plantype</span>', unsafe_allow_html=True)
    plantype_valg = st.multiselect("", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"], label_visibility="collapsed", key="pt")
    isoler_pt     = st.checkbox("Isoler (kun rene sager)", key="iso_pt") if plantype_valg else False

    st.markdown('<span class="h-filter-label">Sagsgruppe</span>', unsafe_allow_html=True)
    sagsgruppe_valg = st.multiselect("", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"], label_visibility="collapsed", key="sg")

    st.markdown('<span class="h-filter-label">Årsinterval</span>', unsafe_allow_html=True)
    år_min, år_max   = int(df["År"].min()), int(df["År"].max())
    _default_start   = max(2017, år_min)
    år_range         = st.slider("", år_min, år_max, (_default_start, år_max), label_visibility="collapsed")

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

# Nulstil side-tæller når filteret eller søgeordet ændrer sig
_filter_sig = (len(df_filter), df_filter["Link"].iloc[0] if len(df_filter) > 0 else "", søg_input.strip())
if st.session_state.get("_filter_sig") != _filter_sig:
    st.session_state["vis_antal"] = 25
    st.session_state["_filter_sig"] = _filter_sig

_vis_antal = st.session_state.get("vis_antal", 25)

if søg_input.strip():
    _q = søg_input.strip()
    _text_mask = (
        df_filter["Titel"].str.contains(_q, case=False, na=False, regex=False) |
        df_filter["Tekst"].str.contains(_q, case=False, na=False, regex=False)
    )
    df_vis     = df_filter[_text_mask].sort_values("Dato", ascending=False).reset_index(drop=True)
    _matched   = df_filter.index[_text_mask].tolist()
    ai_sub_idx = [sub_idx[i] for i in _matched] if _matched else sub_idx
else:
    df_vis = df_filter.sort_values("Dato", ascending=False)
    ai_sub_idx = sub_idx


def build_download_text(data: pd.DataFrame, søgeord: str = "") -> str:
    """Bygger en struktureret tekstfil med alle afgørelser – optimeret til LLM-upload."""
    lines = [
        "PLANKLAGENÆVNETS AFGØRELSER – EKSPORT",
        f"Antal afgørelser: {len(data)}",
        f"Søgeord: {søgeord if søgeord.strip() else '(ingen – kun filteret på kategori/plantype/udfald mv.)'}",
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
        dl_bytes = build_download_text(df_filter, søgeord=søg_input).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download alle {n:,} afgørelser (.txt)",
            data=dl_bytes,
            file_name="pkn_afgørelser.txt",
            mime="text/plain",
        )
    else:
        dl_bytes = build_download_text(df_filter, søgeord=søg_input).encode("utf-8")
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

        # ── Tilbage-knap ────────────────────────────────────────────────────
        if st.button("← Alle afgørelser"):
            st.session_state.valgt_afgørelse = None
            st.rerun()

        # ── Hero-header ──────────────────────────────────────────────────────
        badge_cls = BADGE.get(row["Udfald"], "badge-ukendt")
        dato_str  = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y")
        kategori  = " / ".join(row["Kategori"]) if isinstance(row["Kategori"], list) else row["Kategori"]
        sagsgruppe = row.get("Sagsgruppe") or "–"
        kommune    = row.get("Kommune") or "–"
        udfald     = row.get("Udfald") or "Ukendt"

        # Farver til udfald-chip
        chip_styles = {
            "Medhold":       "background:#f0fdf4;color:#166534;border-color:#bbf7d0",
            "Ikke medhold":  "background:#fef2f2;color:#991b1b;border-color:#fecaca",
            "Ophævet":       "background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe",
            "Afvist":        "background:#fffbeb;color:#92400e;border-color:#fde68a",
        }
        chip_s = chip_styles.get(udfald, "background:#f8fafc;color:#64748b;border-color:#e2e8f0")

        st.markdown(f"""
<div class="detail-hero">
  <div class="detail-udfald-row">
    <span class="detail-udfald-chip" style="{chip_s}">{udfald}</span>
  </div>
  <h1 class="detail-title">{row['Titel']}</h1>
  <div class="detail-gold-line"></div>
  <div class="detail-meta-strip">
    <div class="detail-meta-cell">
      <span class="detail-meta-lbl">Dato</span>
      <span class="detail-meta-val">{dato_str}</span>
    </div>
    <div class="detail-meta-cell">
      <span class="detail-meta-lbl">Kategori</span>
      <span class="detail-meta-val">{kategori}</span>
    </div>
    <div class="detail-meta-cell">
      <span class="detail-meta-lbl">Sagsgruppe</span>
      <span class="detail-meta-val">{sagsgruppe}</span>
    </div>
    <div class="detail-meta-cell">
      <span class="detail-meta-lbl">Kommune</span>
      <span class="detail-meta-val">{kommune}</span>
    </div>
  </div>
  <a class="detail-source-link" href="{row['Link']}" target="_blank">
    Åbn original på PKN's hjemmeside &nbsp;↗
  </a>
</div>
""", unsafe_allow_html=True)

        # ── Indhold: tekst + AI ──────────────────────────────────────────────
        col_tekst, col_ai = st.columns([3, 2], gap="large")
        with col_tekst:
            tekst_rå  = row["Tekst"]
            tekst_fmt = re.sub(r'\.(\s+)([A-ZÆØÅ])', r'.</p><p>\2', tekst_rå)
            tekst_fmt = re.sub(r'(\s)(\d+\.\s+)([A-ZÆØÅ])', r'</p><p>\2\3', tekst_fmt)
            st.markdown(
                f'<div class="detail-reader"><p>{tekst_fmt}</p></div>',
                unsafe_allow_html=True
            )

        with col_ai:
            st.markdown(
                '<div class="detail-ai-panel">'
                '<div class="detail-ai-title">✦ &nbsp;AI-Resumé</div>',
                unsafe_allow_html=True
            )
            if not st.session_state.resumé_adgang:
                pw = st.text_input("Adgangskode", type="password", key="resumé_pw_input",
                                   placeholder="Indtast adgangskode…", label_visibility="collapsed")
                if st.button("Lås op →", key="resumé_pw_btn"):
                    if pw == "B465545":
                        st.session_state.resumé_adgang = True
                        st.rerun()
                    else:
                        st.error("Forkert adgangskode.")
            else:
                if st.button("Generer resumé →", key="gen_resume_btn"):
                    with st.spinner("Analyserer…"):
                        try:
                            st.session_state._resumé = gemini_resumé(row["Titel"], row["Tekst"])
                        except Exception as e:
                            st.session_state._resumé = f"Fejl: {e}"
                if "_resumé" in st.session_state:
                    st.markdown(
                        f'<div class="detail-ai-resume">{st.session_state._resumé}</div>',
                        unsafe_allow_html=True
                    )
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        total_filtreret = len(df_filter)
        hits  = len(df_vis)
        if søg_input:
            label = f"**{hits}** resultater for \"{søg_input}\" (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {min(_vis_antal, hits)} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            st.warning("Ingen resultater – prøv andre søgeord eller filtre.")
        else:
            for _, row in df_vis.head(_vis_antal).iterrows():
                badge_cls   = BADGE.get(row["Udfald"], "badge-ukendt")
                dato_str    = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                kat_str     = " / ".join(row["Kategori"]) if isinstance(row["Kategori"], list) else row["Kategori"]
                st.markdown(f"""
<div class="pkn-card">
  <div class="pkn-card-toprow">
    <span class="pkn-card-dato">{dato_str}</span>
    <span class="pkn-badge {badge_cls}">{row['Udfald']}</span>
  </div>
  <div class="pkn-card-title">{row['Titel']}</div>
  <div class="pkn-card-tags">
    <span class="pkn-tag">{kat_str}</span>
    <span class="pkn-tag">{row['Sagsgruppe']}</span>
  </div>
  <div class="pkn-card-excerpt">{row['Excerpt']}…</div>
</div>""", unsafe_allow_html=True)
                if st.button("Læs afgørelse →", key=f"btn_{row['Link'][-20:]}"):
                    st.session_state.valgt_afgørelse = row.to_dict()
                    if "_resumé" in st.session_state:
                        del st.session_state["_resumé"]
                    st.rerun()

            if _vis_antal < hits:
                tilbage = hits - _vis_antal
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

    if not st.session_state.ai_adgang:
        st.markdown("Denne funktion kræver adgangskode.")
        pwd_input = st.text_input("Adgangskode", type="password", key="pwd_input")
        if st.button("Log ind", key="pwd_btn"):
            if pwd_input == "B465545":
                st.session_state.ai_adgang = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
        st.stop()

    n_ai = len(ai_sub_idx)
    filter_tekst = f"alle **{len(df):,}** afgørelser" if n_ai == len(df) else f"**{n_ai:,}** afgørelser (filtreret)"
    st.markdown(f"AI'en søger i {filter_tekst} og svarer med kildehenvisninger – ingen embedding-API nødvendig.")

    if not ANTHROPIC_API_KEY:
        st.error("Tilføj `ANTHROPIC_API_KEY` i Streamlit secrets.")
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
                    hits_ai = tfidf_søg(f, df, vec, mat, sub_idx=ai_sub_idx, top_n=8)
                    try:
                        svar = gemini_svar(f, hits_ai.to_dict("records"), historik=st.session_state.chat_historik)
                    except Exception as e:
                        svar = f"Fejl ved Gemini API: {e}"
                st.session_state.chat_historik.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
                st.rerun()

        st.divider()

        # Historik
        for msg_idx, msg in enumerate(st.session_state.chat_historik):
            if msg["rolle"] == "bruger":
                st.markdown(f'<div class="chat-user">{msg["tekst"]}</div>', unsafe_allow_html=True)
            else:
                # Erstat [Kilde X] i AI-teksten med kommune-navne
                kilder = msg.get("kilder", [])
                vist_tekst = erstat_kilde_refs(msg["tekst"], kilder) if kilder else msg["tekst"]

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    st.markdown(f'<div class="chat-assistant">{vist_tekst}</div>', unsafe_allow_html=True)
                with col_kld:
                    if kilder:
                        st.markdown(
                            '<div style="font-size:11px;font-weight:700;color:#475569;'
                            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                            'Kilder</div>',
                            unsafe_allow_html=True
                        )
                        for i, k in enumerate(kilder[:8]):
                            try:
                                ts       = pd.Timestamp(k["Dato"])
                                dato_str = ts.strftime("%d.%m.%Y")
                                år_str   = str(ts.year)
                            except Exception:
                                dato_str = "–"
                                år_str   = "–"
                            kommune   = extract_kommune(k.get("Titel", "")) or "Ukendt kommune"
                            udfald    = k.get("Udfald", "")
                            badge_cls = BADGE.get(udfald, "badge-ukendt")
                            badge_html = f'<span class="pkn-badge {badge_cls}">{udfald}</span>' if udfald else ""

                            with st.expander(f"[{i+1}] {kommune} · {år_str}"):
                                # Åbn-knap øverst – mest fremtrædende handling
                                if st.button(
                                    f"▶ Åbn afgørelsen i Harald",
                                    key=f"kilde_open_{msg_idx}_{i}",
                                    use_container_width=True,
                                    type="primary",
                                ):
                                    st.session_state.valgt_afgørelse = k
                                    if "_resumé" in st.session_state:
                                        del st.session_state["_resumé"]
                                    st.rerun()

                                # Titel + metadata
                                st.markdown(
                                    f'<div style="font-size:13px;font-weight:600;color:#1e3a5f;'
                                    f'margin:8px 0 4px 0;line-height:1.4">{k["Titel"]}</div>',
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f'<div style="font-size:11px;color:#64748b;margin-bottom:10px">'
                                    f'{dato_str} &nbsp;·&nbsp; {k.get("Sagsgruppe", "")}'
                                    f'&nbsp;&nbsp;{badge_html}</div>',
                                    unsafe_allow_html=True
                                )

                                # Fuld tekst i scrollbar boks
                                tekst_rå = k.get("Tekst", "")
                                # Opdel i afsnit ved sætningsskift foran stort bogstav
                                tekst_fmt = re.sub(r'\. ([A-ZÆØÅ])', r'.</p><p>\1', tekst_rå)
                                tekst_html = (
                                    '<div style="font-size:13px;line-height:1.7;color:#1e293b;'
                                    'max-height:420px;overflow-y:auto;padding:12px 14px;'
                                    'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;'
                                    'margin-bottom:8px">'
                                    f'<p>{tekst_fmt}</p>'
                                    '</div>'
                                )
                                st.markdown(tekst_html, unsafe_allow_html=True)

                                # Link til original
                                st.markdown(
                                    f'<a href="{k["Link"]}" target="_blank" '
                                    f'style="font-size:12px;color:#2563eb;text-decoration:none">'
                                    f'Åbn original afgørelse på PKN\'s hjemmeside ↗</a>',
                                    unsafe_allow_html=True
                                )

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
                hits_ai = tfidf_søg(spørgsmål, df, vec, mat, sub_idx=ai_sub_idx, top_n=8)
                try:
                    svar = gemini_svar(spørgsmål, hits_ai.to_dict("records"), historik=st.session_state.chat_historik)
                except Exception as e:
                    svar = f"Fejl ved Gemini API: {e}"
            st.session_state.chat_historik.append(
                {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
            st.rerun()

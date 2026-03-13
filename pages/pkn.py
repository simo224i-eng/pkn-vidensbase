import streamlit as st
import pandas as pd
import re
import csv
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as cos_sim
from shared import logo, _llm, strip_html, extract_kommune, BADGE, format_afgørelse_tekst, render_detail_header

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── TF-IDF søgning ───────────────────────────────────────────────────────────

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
    """Returnerer liste af kategorier – en sag kan have flere (fx Planvedtagelse + Miljøvurdering)."""
    t = titel.lower()
    # 1. Planvedtagelse af plan — bilag (miljørapport/screening) tilføjes som ekstra kategori
    is_plan = bool(re.search(r"lokalplan|kommuneplantillæg|kommuneplan|byplanvedtægt", t))
    is_vedtagelse = bool(re.search(r"vedtagelse af\b.{0,80}?(lokalplan|kommuneplantillæg|kommuneplan|byplanvedtægt)", t))
    if is_vedtagelse:
        if "dispensation" in t:
            kats = ["Dispensation"]
        elif "overensstemmelse" in t:
            kats = ["Overensstemmelse"]
        else:
            kats = ["Planvedtagelse"]
        if "screeningsafgørelse" in t:
            kats.append("Miljøvurderingsloven")
        if "miljørapport" in t or "miljøvurdering" in t or "vvm" in t:
            kats.append("Miljøvurderingsloven")
        return kats
    # 2. Screeningsafgørelse under miljøvurderingsloven
    if "screeningsafgørelse" in t or "screeningen" in t:
        return ["Miljøvurderingsloven"]
    # 3. Miljørapport under miljøvurderingsloven
    if "miljøvurdering" in t or "miljørapport" in t or re.search(r"\bvvm\b", t):
        return ["Miljøvurderingsloven"]
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
        return ["Planvedtagelse"]
    # 7. Øvrige plan-sager der nævner en plantype
    if "lokalplan" in t or "byplanvedtægt" in t:
        return ["Andet"]
    if "kommuneplantillæg" in t or re.search(r"kommuneplan(?!tillæg)", t):
        return ["Andet"]
    # 8. Temabaserede kategorier
    if "landzone" in t: return ["Landzone"]
    return ["Andet"]


def detect_dokumenttype(titel: str) -> str | None:
    """Returnerer 'Screeningsafgørelse', 'Miljørapport' eller None for sager under miljøvurderingsloven."""
    t = titel.lower()
    if "screeningsafgørelse" in t or "screeningen" in t:
        return "Screeningsafgørelse"
    if "miljørapport" in t or "miljøvurdering" in t or re.search(r"\bvvm\b", t):
        return "Miljørapport"
    return None


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
                             "hjemvisning", "hjemvises", "hjemvist",
                             "delvist ophæv", "ændret af nævnet")):  return "Ophævet"
    if "medhold" in t:                                               return "Medhold"
    if any(k in t for k in ("stadfæst", "ikke medhold", "stadfæstelse")):
                                                                     return "Ikke medhold"
    if any(k in t for k in ("afvisning", "afvises", "afvist")):      return "Afvist"

    # ── Brødtekst – brug SIDSTE "Afsluttende bemærkninger"-sektion ───────────
    tx = _strip_html(tekst).lower()
    positions = [m.start() for m in re.finditer(r"afsluttende bem[æa]rkninger", tx)]
    conc = tx[positions[-1]:positions[-1] + 800] if positions else tx[-1200:]

    if any(k in conc for k in ("ophæver", "hjemviser", "hjemvisning", "ugyldiggør",
                                "ophæves", "hjemvises", "ændrer den påklagede",
                                "ændres hermed", "påklagede afgørelse ændres")):
        return "Ophævet"
    if any(k in conc for k in ("kan ikke give medhold", "ikke medhold", "stadfæst",
                                "ikke grundlag for at ændre", "ingen anledning til at ændre",
                                "ikke anledning til at", "nævnet finder ikke grundlag",
                                "klagen ikke tages til følge", "tages ikke til følge")):
        return "Ikke medhold"
    if any(k in conc for k in ("afviser klagen", "afvises som", "afviser hermed",
                                "klagen afvises")):
        return "Afvist"
    if any(k in conc for k in ("giver medhold", "gives medhold", "medhold i klagen",
                                "tager klagen til følge", "klagen tages til følge",
                                "medhold")):
        return "Medhold"

    # ── Bredere søgning i hele teksten ───────────────────────────────────────
    if any(k in tx for k in ("klagen tages til følge", "giver klageren medhold",
                              "nævnet giver medhold")):             return "Medhold"
    if any(k in tx for k in ("klagen tages ikke til følge", "nævnet stadfæster",
                              "stadfæstes hermed", "ikke grundlag for at")):
                                                                    return "Ikke medhold"
    if any(k in tx for k in ("nævnet ophæver", "ophæves hermed", "nævnet hjemviser",
                              "hjemvises hermed")):                 return "Ophævet"
    if any(k in tx for k in ("klagen afvises", "afvises som åbenbart",
                              "afvises som for sent")):             return "Afvist"

    return "Ukendt"

def detect_sagsgruppe(titel: str, tekst: str) -> str:
    t = (titel + " " + tekst[:500]).lower()
    if "genoptagelse" in t:    return "Genoptagelse"
    if "opsættende virkning" in t or "afslag på opsættende" in t: return "Opsættende virkning"
    if "afvisning" in t or "afvises" in t or "klageberettiget" in t: return "Afvisning"
    return "Realitetsbehandling"



# ── Retsområde-mapping for gamle CSV-filer uden Retsomraade-kolonne ───────────
_LEGACY_RETSOMRAADE = {
    "pkn_vidensbase_fuld_tekst.csv":           "Planloven, retlig (efter 1. februar 2017)",
    "pkn_miljoevurderingsloven_fuld_tekst.csv": "Miljøvurderingsloven",
}

# ── Data-loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser afgørelser…", ttl=None, hash_funcs=None)
def _læs_csv(sti: str, fallback_retsomraade: str = "") -> list:
    """Læser én CSV og returnerer en liste af rækker med renset tekst."""
    rows = []
    with open(sti, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tekst = strip_html(row["Tekst"], preserve_headings=True)
            excerpt_clean = re.sub(r'^#{2,3} ', '', tekst, flags=re.M).replace('\n', ' ')
            excerpt_clean = re.sub(r'\s+', ' ', excerpt_clean).strip()
            rows.append({
                "Dato":        row["Dato"],
                "Titel":       row["Titel"],
                "Link":        row["Link"],
                "Tekst":       tekst,
                "Excerpt":     excerpt_clean[:280],
                "Retsomraade": row.get("Retsomraade", fallback_retsomraade),
            })
    return rows


def load_data(version: int = 18):  # bump version to bust cache
    import os, zipfile, glob as _glob
    csv.field_size_limit(10_000_000)

    rows = []
    seen_links: set[str] = set()

    def _indlæs(sti: str, fallback: str = "") -> None:
        for r in _læs_csv(sti, fallback):
            if r["Link"] not in seen_links:
                seen_links.add(r["Link"])
                rows.append(r)

    # --- primær fil (zip → csv) ---
    if not os.path.exists("pkn_vidensbase_fuld_tekst.csv"):
        with zipfile.ZipFile("pkn_vidensbase_fuld_tekst.csv.zip") as z:
            z.extractall(".")
    _indlæs("pkn_vidensbase_fuld_tekst.csv",
            _LEGACY_RETSOMRAADE["pkn_vidensbase_fuld_tekst.csv"])

    # --- supplerende filer: alle pkn_*.csv (og pkn_*.csv.zip) undtagen vidensbasen ---
    kandidater = set(_glob.glob("pkn_*.csv")) | {z[:-4] for z in _glob.glob("pkn_*.csv.zip")}
    for sti in sorted(kandidater):
        if sti == "pkn_vidensbase_fuld_tekst.csv":
            continue
        zip_sti = sti + ".zip"
        if not os.path.exists(sti) and os.path.exists(zip_sti):
            with zipfile.ZipFile(zip_sti) as z:
                z.extractall(".")
        if os.path.exists(sti):
            _indlæs(sti, _LEGACY_RETSOMRAADE.get(sti, ""))

    df = pd.DataFrame(rows)
    df["Dato"]        = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"]          = df["Dato"].dt.year.astype("Int64")
    df["Retsomraade"] = df["Retsomraade"].fillna("").astype(str)
    df["Kategori"]        = df["Titel"].apply(kategoriser)
    df["Kategori_primær"] = df["Kategori"].apply(lambda x: x[0])
    df["Plantype"]        = df["Titel"].apply(detect_plantype)
    df["Dokumenttype"]    = df["Titel"].apply(detect_dokumenttype)
    df["Udfald"]     = df.apply(lambda r: detect_udfald(r["Titel"], r.get("Tekst", "")), axis=1)
    df["Kommune"]    = df["Titel"].apply(extract_kommune)
    df["Sagsgruppe"] = df.apply(lambda r: detect_sagsgruppe(r["Titel"], r["Tekst"]), axis=1)
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_data(17)
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


def _saml_kilder(historik: list, nye_hits, max_total: int = 12) -> list:
    """Merge nye søgeresultater med alle tidligere viste kilder (dedupliceret på Link).
    Sikrer at AI'en har kildekontinuitet på tværs af samtalens ture."""
    seen = set()
    merged = []
    for rec in (nye_hits.to_dict("records") if hasattr(nye_hits, "to_dict") else nye_hits):
        lnk = rec.get("Link", "")
        if lnk not in seen:
            seen.add(lnk)
            merged.append(rec)
    for msg in reversed(historik or []):
        if msg.get("rolle") == "assistent":
            for k in msg.get("kilder", []):
                lnk = k.get("Link", "")
                if lnk not in seen and len(merged) < max_total:
                    seen.add(lnk)
                    merged.append(k)
    return merged[:max_total]


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
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel'][:80]}"
        for i, d in enumerate(docs)
    )
    prompt = f"""Du er en juridisk assistent specialiseret i dansk planlovgivning og PKN-praksis.

VIGTIGE REGLER:
1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte afgørelser.
2. Brug UDELUKKENDE referencerne i formatet [Kilde X] – ALDRIG kommunenavne eller årstal som reference. Eks: [Kilde 3] eller [Kilde 1, 2].
3. Svar på dansk med overskrifter og afsnit.
4. Er det et opfølgningsspørgsmål, brug den tidligere samtale – kilderne er de samme numre.

KILDEREGISTER (brug disse numre i dine referencer):
{kilde_liste}
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


def erstat_kilde_refs(tekst: str, kilder: list) -> tuple[str, list]:
    """Erstat [Kilde X] med blå navne-chips i teksten.
    Returnér (html_tekst, liste af unikke referencer som (label, kilde_dict))."""
    unique: dict[int, tuple[str, dict]] = {}  # idx → (label, kilde)

    def repl(m):
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
        spans = []
        for n in nums:
            if 1 <= n <= len(kilder):
                k = kilder[n - 1]
                kom = extract_kommune(k.get("Titel", "")) or "Kilde"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = "–"
                label = f"{kom} {år}"
                unique[n - 1] = (label, k)
                spans.append(
                    f'<span style="color:#a0692a;font-weight:600;white-space:nowrap;">[{label}]</span>'
                )
        return " ".join(spans) if spans else m.group(0)

    html = re.sub(r"\[Kilde\s+([\d,\s]+)\]", repl, tekst)
    ordered = [v for _, v in sorted(unique.items())]
    return html, ordered


# ── Session state ─────────────────────────────────────────────────────────────
if "chat_historik"   not in st.session_state: st.session_state.chat_historik   = []
if "valgt_afgørelse" not in st.session_state: st.session_state.valgt_afgørelse = None
if "ai_adgang"       not in st.session_state: st.session_state.ai_adgang       = False
if "resumé_adgang"   not in st.session_state: st.session_state.resumé_adgang   = False

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_data(16)
vec, mat = build_index(len(df))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(152)}</div>
</div>""", unsafe_allow_html=True)

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Søgeord</span>', unsafe_allow_html=True)
    søg_input = st.text_input("", placeholder="f.eks. planlovens § 15 a, terrasse, lokalplan…", label_visibility="collapsed")
    søge_type = st.radio("", ["Præcis", "Semantisk"], horizontal=True, label_visibility="collapsed", key="søge_type")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Kategori</span>', unsafe_allow_html=True)
    _alle_kats  = sorted({k for kats in df["Kategori"] for k in kats})
    valgte_kats = st.multiselect("", _alle_kats, label_visibility="collapsed", key="kat")
    _isoler_relevant = bool(valgte_kats and set(valgte_kats) & {"Planvedtagelse", "Miljøvurderingsloven"})
    isoler_kat  = st.checkbox("Isoler (kun rene sager)", key="iso_kat") if _isoler_relevant else False

    _mvu_valgt = "Miljøvurderingsloven" in (valgte_kats or [])
    if _mvu_valgt:
        st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Dokumenttype</span>', unsafe_allow_html=True)
        dokumenttype_valg = st.multiselect("", ["Screeningsafgørelse", "Miljørapport"], label_visibility="collapsed", key="dt")
    else:
        dokumenttype_valg = []

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Plantype</span>', unsafe_allow_html=True)
    plantype_valg = st.multiselect("", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"], label_visibility="collapsed", key="pt")
    isoler_pt     = st.checkbox("Isoler (kun rene sager)", key="iso_pt") if plantype_valg else False

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Sagsgruppe</span>', unsafe_allow_html=True)
    sagsgruppe_valg = st.multiselect("", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"], label_visibility="collapsed", key="sg")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Årsinterval</span>', unsafe_allow_html=True)
    år_min, år_max   = 2017, int(df["År"].max())
    år_range         = st.slider("", år_min, år_max, (år_min, år_max), label_visibility="collapsed")

    st.markdown('<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;display:block;">Udfald</span>', unsafe_allow_html=True)
    udfald_valg    = st.multiselect("", ["Medhold", "Ikke medhold", "Ophævet", "Afvist", "Ukendt"], label_visibility="collapsed", key="ud")

    st.markdown("---")
    st.markdown(f"<span style='font-size:12px;color:#5a7a9e'>**{len(df):,}** afgørelser &nbsp;·&nbsp; 2017–{år_max}</span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:11px;color:#3d5878'>Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>", unsafe_allow_html=True)


mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if valgte_kats:
    if isoler_kat:
        mask &= df["Kategori"].apply(lambda kats: set(kats).issubset(set(valgte_kats)))
    else:
        mask &= df["Kategori"].apply(lambda kats: any(k in kats for k in valgte_kats))
if dokumenttype_valg:
    mask &= df["Dokumenttype"].isin(dokumenttype_valg)
if plantype_valg:
    if isoler_pt:
        mask &= df["Plantype"].apply(lambda pts: set(pts).issubset(set(plantype_valg)))
    else:
        mask &= df["Plantype"].apply(lambda pts: any(pt in pts for pt in plantype_valg))
if sagsgruppe_valg: mask &= df["Sagsgruppe"].isin(sagsgruppe_valg)
if udfald_valg:     mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx   = df[mask].index.tolist()

# Nulstil side-tæller når filteret, søgeordet eller søgetypen ændrer sig
_filter_sig = (len(df_filter), df_filter["Link"].iloc[0] if len(df_filter) > 0 else "", søg_input.strip(), søge_type)
if st.session_state.get("_filter_sig") != _filter_sig:
    st.session_state["vis_antal"] = 25
    st.session_state["_filter_sig"] = _filter_sig

_vis_antal = st.session_state.get("vis_antal", 25)

if søg_input.strip() and søge_type == "Semantisk":
    df_vis     = tfidf_søg(søg_input.strip(), df, vec, mat, sub_idx=sub_idx)
    ai_sub_idx = sub_idx
elif søg_input.strip():
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
<div style="margin-bottom:2rem;padding-bottom:1.2rem;border-bottom:1px solid #e8e0d4;display:flex;align-items:center;gap:0;flex-wrap:wrap;">
  <h1 style="font-family:'Cinzel',Georgia,serif;font-size:2rem;font-weight:900;color:#1a0a0e;letter-spacing:6px;margin:0;line-height:1;flex-shrink:0;">HARALD</h1>
  <span style="font-size:12px;color:#b09070;margin-left:22px;padding-left:22px;border-left:1px solid #d4c8b8;line-height:1.6;">
    Planklagenævnets afgørelsesdatabase &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {int(df['År'].min())}–{int(df['År'].max())}
  </span>
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

        st.markdown(
            render_detail_header(
                titel=row["Titel"],
                udfald=udfald,
                chip_style=chip_s,
                dato_str=dato_str,
                meta_extra=[("Kategori", kategori), ("Sagsgruppe", sagsgruppe), ("Kommune", kommune)],
                link=row["Link"],
                link_label="Åbn original på PKN's hjemmeside",
            ),
            unsafe_allow_html=True,
        )

        # ── Indhold: tekst + AI ──────────────────────────────────────────────
        col_tekst, col_ai = st.columns([3, 2], gap="large")
        with col_tekst:
            st.markdown(format_afgørelse_tekst(row["Tekst"]), unsafe_allow_html=True)

        with col_ai:
            st.markdown(
                '<div class="detail-ai-panel">'
                '<div class="detail-ai-title">✦ &nbsp;AI-Resumé</div>',
                unsafe_allow_html=True
            )
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
            _type_label = "semantisk" if søge_type == "Semantisk" else "præcis"
            label = f"**{hits}** resultater for \"{søg_input}\" · {_type_label} søgning (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {min(_vis_antal, hits)} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            st.warning("Ingen resultater – prøv andre søgeord eller filtre.")
        else:
            _BADGE_STYLE = {
                "Medhold":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Ikke medhold": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Ophævet":      "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
                "Afvist":       "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
                "Stadfæstelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Ændring":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
            }
            _BADGE_DEFAULT = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"
            for _, row in df_vis.head(_vis_antal).iterrows():
                badge_style = _BADGE_STYLE.get(row["Udfald"], _BADGE_DEFAULT)
                dato_str    = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                kat_str     = " / ".join(row["Kategori"]) if isinstance(row["Kategori"], list) else row["Kategori"]
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:.2px;">{dato_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.1px;{badge_style}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{row['Titel']}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{kat_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{row['Sagsgruppe']}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{row['Excerpt']}…</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn afgørelse på portalen ↗</a>
  </div>
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

    _CHART_LAYOUT = dict(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#334155"),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    _UDFALD_FARVER = {
        "Medhold": "#10b981", "Ikke medhold": "#ef4444",
        "Ophævet": "#8b5cf6", "Afvist": "#f59e0b", "Ukendt": "#94a3b8",
    }

    if d.empty:
        st.info("Ingen data at vise med de valgte filtre.")
    else:
        # ── KPI-kort ──────────────────────────────────────────────────────
        k1, k2, k3, k4 = st.columns(4)
        pct_medhold = (d["Udfald"] == "Medhold").mean() * 100
        år_span = f"{int(d['År'].min())}–{int(d['År'].max())}" if len(d) else "–"
        for col, tal, label in [
            (k1, f"{len(d):,}",               "Afgørelser"),
            (k2, f"{pct_medhold:.0f}%",        "Medhold-rate"),
            (k3, f"{d['Kommune'].nunique()}",  "Kommuner"),
            (k4, år_span,                      "Årsinterval"),
        ]:
            col.markdown(
                f'<div class="stat-card"><div class="stat-number">{tal}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Række 1: Afgørelser per år + Udfald over tid ──────────────────
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Afgørelser per år")
            år_df = d.groupby("År").size().reset_index(name="Antal")
            fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#c49a3c"])
            fig.update_layout(**_CHART_LAYOUT)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("#### Udfald over tid")
            udfald_år = d.groupby(["År", "Udfald"]).size().reset_index(name="Antal")
            fig2 = px.bar(udfald_år, x="År", y="Antal", color="Udfald",
                          color_discrete_map=_UDFALD_FARVER, barmode="stack")
            fig2.update_layout(**_CHART_LAYOUT)
            fig2.update_traces(marker_line_width=0)
            st.plotly_chart(fig2, use_container_width=True)

        # ── Række 2: Kategori + Sagsgruppe ────────────────────────────────
        col_ll, col_rr = st.columns(2)
        with col_ll:
            st.markdown("#### Fordeling på kategori")
            kat_df = (d.groupby("Kategori_primær").size()
                       .reset_index(name="Antal")
                       .rename(columns={"Kategori_primær": "Kategori"})
                       .sort_values("Antal", ascending=True))
            fig3 = px.bar(kat_df, x="Antal", y="Kategori", orientation="h",
                          color_discrete_sequence=["#1a3060"])
            fig3.update_layout(**_CHART_LAYOUT)
            fig3.update_traces(marker_line_width=0)
            st.plotly_chart(fig3, use_container_width=True)

        with col_rr:
            st.markdown("#### Fordeling på sagsgruppe")
            sg_df = (d.dropna(subset=["Sagsgruppe"])
                      .groupby("Sagsgruppe").size()
                      .reset_index(name="Antal")
                      .sort_values("Antal", ascending=True)
                      .tail(15))
            fig4 = px.bar(sg_df, x="Antal", y="Sagsgruppe", orientation="h",
                          color_discrete_sequence=["#c49a3c"])
            fig4.update_layout(**_CHART_LAYOUT)
            fig4.update_traces(marker_line_width=0)
            st.plotly_chart(fig4, use_container_width=True)

        # ── Række 3: Top kommuner + Medhold-rate per kategori ─────────────
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Top 15 kommuner")
            kom_df = (d.dropna(subset=["Kommune"]).groupby("Kommune").size()
                       .reset_index(name="Sager").sort_values("Sager", ascending=True).tail(15))
            fig5 = px.bar(kom_df, x="Sager", y="Kommune", orientation="h",
                          color_discrete_sequence=["#1a3060"])
            fig5.update_layout(**_CHART_LAYOUT)
            fig5.update_traces(marker_line_width=0)
            st.plotly_chart(fig5, use_container_width=True)

        with col_b:
            st.markdown("#### Medhold-rate per kategori")
            mr = (d.groupby("Kategori_primær")
                   .apply(lambda x: pd.Series({
                       "Sager": len(x),
                       "Medhold_%": round((x["Udfald"] == "Medhold").mean() * 100, 1),
                   }), include_groups=False)
                   .reset_index()
                   .rename(columns={"Kategori_primær": "Kategori"})
                   .sort_values("Medhold_%", ascending=True))
            fig6 = px.bar(mr, x="Medhold_%", y="Kategori", orientation="h",
                          color="Medhold_%", color_continuous_scale=["#fee2e2", "#10b981"],
                          hover_data={"Sager": True},
                          labels={"Medhold_%": "Medhold (%)"})
            fig6.update_layout(**_CHART_LAYOUT, coloraxis_showscale=False)
            fig6.update_traces(marker_line_width=0)
            st.plotly_chart(fig6, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    n_ai = len(ai_sub_idx)
    filtreret = n_ai != len(df)
    antal_tekst = f"{n_ai:,}" if filtreret else f"{len(df):,}"
    filtreret_label = " (filtreret)" if filtreret else ""

    st.markdown(f"""
<div style="display:flex;align-items:center;gap:16px;background:linear-gradient(to right,#fdf8f2,#fff);border-left:3px solid #c49a3c;border-radius:0 10px 10px 0;padding:16px 22px;margin-bottom:18px;">
  <span style="font-size:24px;flex-shrink:0;opacity:0.7;line-height:1;">⚖</span>
  <div>
    <div style="font-family:'Cinzel',Georgia,serif;font-size:13px;font-weight:700;color:#1a0a0e;letter-spacing:2.5px;text-transform:uppercase;margin-bottom:4px;">Spørg til PKN-praksis</div>
    <div style="font-size:12.5px;color:#7a6050;line-height:1.6;">
      Søger i <strong style="color:#1a0a0e;">{antal_tekst} afgørelser{filtreret_label}</strong>
      og svarer med kildehenvisninger.
      Opfølgningsspørgsmål husker kontekst.
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

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
        # Anchor element so CSS sibling selector kan styre knappernes udseende
        st.markdown('<div id="ai-forslag-anchor"></div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"fs_{i}"):
                st.session_state.chat_historik.append({"rolle": "bruger", "tekst": f})
                with st.spinner("Søger og genererer svar…"):
                    hits_ai = tfidf_søg(f, df, vec, mat, sub_idx=ai_sub_idx, top_n=12)
                    alle_kilder = _saml_kilder(st.session_state.chat_historik, hits_ai)
                    try:
                        svar = gemini_svar(f, alle_kilder, historik=st.session_state.chat_historik)
                    except Exception as e:
                        svar = f"Fejl ved Gemini API: {e}"
                st.session_state.chat_historik.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder})
                st.rerun()

        st.divider()

        # Historik
        for msg_idx, msg in enumerate(st.session_state.chat_historik):
            if msg["rolle"] == "bruger":
                st.markdown(
                    '<div style="display:flex;justify-content:flex-end;margin:1rem 0 0.2rem;">'
                    '<span style="font-size:10px;font-weight:700;color:#64748b;'
                    'text-transform:uppercase;letter-spacing:1.2px;">Du</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="display:flex;justify-content:flex-end;">'
                    f'<div class="chat-user">{msg["tekst"]}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                # Label: Harald
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:6px;margin:1rem 0 0.2rem;">'
                    '<span style="font-size:10px;font-weight:700;color:#c49a3c;'
                    'text-transform:uppercase;letter-spacing:1.2px;">⚖ Harald</span></div>',
                    unsafe_allow_html=True,
                )
                # Erstat [Kilde X] i AI-teksten med blå navne-chips
                kilder = msg.get("kilder", [])
                if kilder:
                    vist_tekst, ref_kilder = erstat_kilde_refs(msg["tekst"], kilder)
                else:
                    vist_tekst, ref_kilder = msg["tekst"], []

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    st.markdown(f'<div class="chat-assistant">{vist_tekst}</div>', unsafe_allow_html=True)
                    # Klikbare kilde-knapper under AI-svaret
                    if ref_kilder:
                        st.markdown(
                            '<div style="font-size:10px;color:#94a3b8;margin:6px 0 4px;'
                            'text-transform:uppercase;letter-spacing:1px;font-weight:600;">Åbn afgørelse:</div>',
                            unsafe_allow_html=True,
                        )
                        btn_cols = st.columns(min(len(ref_kilder), 3))
                        for ci, (label, k) in enumerate(ref_kilder):
                            with btn_cols[ci % 3]:
                                if st.button(
                                    f"↗ {label}",
                                    key=f"ref_{msg_idx}_{ci}",
                                    use_container_width=True,
                                ):
                                    st.session_state.valgt_afgørelse = k
                                    if "_resumé" in st.session_state:
                                        del st.session_state["_resumé"]
                                    st.rerun()
                with col_kld:
                    if kilder:
                        st.markdown(
                            '<div style="font-size:11px;font-weight:700;color:#475569;'
                            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                            'Kilder</div>',
                            unsafe_allow_html=True
                        )
                        for i, k in enumerate(kilder):
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
                hits_ai = tfidf_søg(spørgsmål, df, vec, mat, sub_idx=ai_sub_idx, top_n=12)
                alle_kilder = _saml_kilder(st.session_state.chat_historik, hits_ai)
                try:
                    svar = gemini_svar(spørgsmål, alle_kilder, historik=st.session_state.chat_historik)
                except Exception as e:
                    svar = f"Fejl ved Gemini API: {e}"
            st.session_state.chat_historik.append(
                {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder})
            st.rerun()

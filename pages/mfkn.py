import streamlit as st

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

import pandas as pd
import re
import csv
import zipfile
import os
import glob as _glob
import numpy as np
import plotly.express as px
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from shared import (
    logo, _llm, _llm_stream, strip_html, extract_kommune, BADGE,
    format_afgørelse_tekst, render_detail_header,
    udtræk_kerneafsnit, sidebar_log_ud,
    byg_indeks_tekst, udvid_query, omformuler_opfoelgning, llm_rerank, saml_kilder,
    byg_embeddings_indeks, hybrid_retrieval, embeddings_tilgængelige,
    valider_citationer, dansk_tokenizer, chunk_tekst, byg_fokuseret_kontekst,
    klassificer_query, highlight_query, copy_button, get_embed_error,
    auto_filter_query, apply_auto_filters,
    init_sagsmapper, gem_fra_row, hent_alle_gemte_links, fjern_afgørelse,
    find_mappe_for_link, opret_mappe,
    skeleton_cards, empty_state, callout, typing_indicator,
)
try:
    from shared import sync_embeddings_to_github, ensure_embeddings_on_disk
except ImportError:
    def sync_embeddings_to_github(): return 0
    def ensure_embeddings_on_disk(*a, **k): pass


def _tilfoej_citat_advarsel(svar: str, alle_kilder: list) -> str:
    """Verificér citater i AI-svar og tilføj en kort advarsel ved hallucineret tekst."""
    try:
        suspekte = valider_citationer(svar, alle_kilder)
    except Exception:
        return svar
    if not suspekte:
        return svar
    punkter = "".join(f"<li>«{c[:140]}…»</li>" if len(c) > 140 else f"<li>«{c}»</li>" for c in suspekte[:3])
    return svar + (
        "\n\n<div style=\"margin-top:1rem;padding:0.9rem 1.1rem;background:#fef2f2;"
        "border:1px solid #fecaca;border-radius:6px;font-size:12.5px;color:#991b1b;\">"
        "<strong>Bemærk – citatverifikation:</strong> følgende citat(er) kunne ikke genfindes "
        f"ordret i kilderne og bør dobbelttjekkes:<ul style=\"margin:0.4rem 0 0 1.1rem;padding:0;\">{punkter}</ul>"
        "</div>"
    )

def _log_feedback(modul: str, svar_tekst: str, rating: str):
    """Log bruger-feedback (thumbs up/down) til CSV for kvalitetsopfølgning."""
    import datetime
    log_dir = "/tmp/pkn_data"
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "feedback.csv")
    exists = os.path.exists(log_path)
    with open(log_path, "a", encoding="utf-8") as f:
        if not exists:
            f.write("tidspunkt,modul,rating,svar_uddrag\n")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe = svar_tekst.replace('"', "'").replace("\n", " ")
        f.write(f'{ts},{modul},{rating},"{safe}"\n')


ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMP  = "/tmp/pkn_data"
os.makedirs(_TMP, exist_ok=True)

# ── Kategori-register ────────────────────────────────────────────────────────
_KATEGORI_REGISTER = {
    # ── Naturbeskyttelse ──
    "mfkn_nbl_beskyttelseslinier":    {"navn": "Beskyttelseslinjer",       "farve": "#2d6a4f", "gruppe": "Naturbeskyttelse"},
    "mfkn_nbl_beskyttede_naturtyper": {"navn": "Beskyttede naturtyper",    "farve": "#0e7490", "gruppe": "Naturbeskyttelse"},
    "mfkn_nbl_fredningsomraadet":     {"navn": "Fredningsområdet",         "farve": "#14532d", "gruppe": "Naturbeskyttelse"},
    "mfkn_nbl_oevrige":               {"navn": "NBL øvrige",               "farve": "#365314", "gruppe": "Naturbeskyttelse"},
    "mfkn_fredning_mv":               {"navn": "Fredning mv.",             "farve": "#1e3a5f", "gruppe": "Naturbeskyttelse"},
    "mfkn_skovloven":                 {"navn": "Skovloven",                "farve": "#3f6212", "gruppe": "Naturbeskyttelse"},
    "mfkn_museumsloven":              {"navn": "Museumsloven",             "farve": "#7e22ce", "gruppe": "Naturbeskyttelse"},
    # ── Miljø & Klima ──
    "mfkn_miljoebeskyttelsesloven":   {"navn": "Miljøbeskyttelsesloven",   "farve": "#166534", "gruppe": "Miljø & Klima"},
    "mfkn_jordforureningsloven":      {"navn": "Jordforureningsloven",     "farve": "#78350f", "gruppe": "Miljø & Klima"},
    "mfkn_miljoevurdering_af_konkrete_projekter": {"navn": "Miljøvurdering (projekter)", "farve": "#065f46", "gruppe": "Miljø & Klima"},
    "mfkn_miljoevurdering_af_planer_og_programmer": {"navn": "Miljøvurdering (planer)", "farve": "#047857", "gruppe": "Miljø & Klima"},
    "mfkn_miljoemaalsloven_og_vandplanlaegningsloven": {"navn": "Miljømålsloven",       "farve": "#0c4a6e", "gruppe": "Miljø & Klima"},
    "mfkn_havmiljoeloven":            {"navn": "Havmiljøloven",            "farve": "#0e7490", "gruppe": "Miljø & Klima"},
    "mfkn_raastofloven":              {"navn": "Råstofloven",              "farve": "#713f12", "gruppe": "Miljø & Klima"},
    # ── Vand & Kyst ──
    "mfkn_vandforsyningsloven":       {"navn": "Vandforsyningsloven",      "farve": "#1e40af", "gruppe": "Vand & Kyst"},
    "mfkn_vandloebsloven":            {"navn": "Vandløbsloven",            "farve": "#0369a1", "gruppe": "Vand & Kyst"},
    "mfkn_kystbeskyttelsesloven":     {"navn": "Kystbeskyttelsesloven",    "farve": "#155e75", "gruppe": "Vand & Kyst"},
    # ── Landbrug & Fødevarer ──
    "mfkn_husdyrbrugloven":           {"navn": "Husdyrbrugloven",          "farve": "#92400e", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_foedevarer":                {"navn": "Fødevarer",                "farve": "#7c3aed", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_landbrugsloven":            {"navn": "Landbrugsloven",           "farve": "#a16207", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_landbrugsstoette":          {"navn": "Landbrugsstøtte",          "farve": "#854d0e", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_foder":                     {"navn": "Foder",                    "farve": "#b45309", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_planter":                   {"navn": "Planter",                  "farve": "#4d7c0f", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_oekologi":                  {"navn": "Økologi",                  "farve": "#15803d", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_fiskeri":                   {"navn": "Fiskeri",                  "farve": "#1d4ed8", "gruppe": "Landbrug & Fødevarer"},
    "mfkn_krydsoverensstemmelse_og_konditionalitet": {"navn": "Krydsoverensstemmelse", "farve": "#64748b", "gruppe": "Landbrug & Fødevarer"},
    # ── Dyr & Dyrlæge ──
    "mfkn_dyresundhed_og_velfaerd":   {"navn": "Dyresundhed og -velfærd",  "farve": "#9f1239", "gruppe": "Dyr & Dyrlæge"},
    "mfkn_dyrlaegelov":               {"navn": "Dyrlægeloven",             "farve": "#be123c", "gruppe": "Dyr & Dyrlæge"},
    # ── Støtte & Tilskud ──
    "mfkn_projektstoette":            {"navn": "Projektstøtte",            "farve": "#6b21a8", "gruppe": "Støtte & Tilskud"},
    # ── Øvrige ──
    "mfkn_aktindsigt":                {"navn": "Aktindsigt",               "farve": "#475569", "gruppe": "Øvrige"},
    "mfkn_oevrige_lovomraader":       {"navn": "Øvrige lovområder",        "farve": "#6b7280", "gruppe": "Øvrige"},
}

# Grupperede labels til selectbox (med antal afgørelser)
_GRUPPE_ORDEN = ["Naturbeskyttelse", "Miljø & Klima", "Vand & Kyst", "Landbrug & Fødevarer", "Dyr & Dyrlæge", "Støtte & Tilskud", "Øvrige"]

def _find_kategorier():
    """Scan repo root for mfkn_*.csv and mfkn_*.csv.zip files."""
    filer = _glob.glob(os.path.join(_ROOT, "mfkn_*.csv")) + _glob.glob(os.path.join(_ROOT, "mfkn_*.csv.zip"))
    kats = {}
    for f in sorted(set(filer)):
        stem = os.path.basename(f).replace(".csv.zip", "").replace(".csv", "")
        if stem in kats:
            continue
        reg = _KATEGORI_REGISTER.get(stem, {})
        navn = reg.get("navn", stem.replace("mfkn_", "").replace("_", " ").title())
        farve = reg.get("farve", "#2d6a4f")
        gruppe = reg.get("gruppe", "Øvrige")
        kats[stem] = {"navn": navn, "farve": farve, "stem": stem, "gruppe": gruppe}
    return kats


def _byg_grupperet_liste(alle_kats):
    """Byg en sorteret liste af kategori-navne, grupperet efter tema."""
    grupper = {}
    for stem, info in alle_kats.items():
        g = info.get("gruppe", "Øvrige")
        grupper.setdefault(g, []).append(info["navn"])
    # Sorter inden for hver gruppe
    for g in grupper:
        grupper[g].sort()
    # Byg flad liste i gruppe-orden
    resultat = []
    for g in _GRUPPE_ORDEN:
        if g in grupper:
            for navn in grupper[g]:
                resultat.append(f"{navn}")
    # Kategorier uden gruppe
    for g, navne in grupper.items():
        if g not in _GRUPPE_ORDEN:
            for navn in sorted(navne):
                resultat.append(f"{navn}")
    return resultat


# ── Hjelpefunktioner ─────────────────────────────────────────────────────────
def detect_udfald(titel, tekst=""):
    t = (titel or "").lower()
    if any(k in t for k in ("hjemvisning","hjemvises","hjemvist")): return "Hjemvist"
    if any(k in t for k in ("ophaevelse","ophævelse","ophævet","ophæves")): return "Ophævet"
    if "aendring" in t or "ændring" in t or "ændres" in t: return "Ændring"
    if "ikke medhold" in t: return "Stadfæstelse"
    if any(k in t for k in ("afvisning","afvises","afvist","klagefristen overskredet")): return "Afvist"
    if any(k in t for k in ("stadfaestelse","stadfæstes","stadfæstelse")): return "Stadfæstelse"
    if "afslag" in t: return "Afslag"

    # ── Brødtekst-fallback: kun for at overskrive "Ukendt" ────────────────────
    tx = (tekst or "").strip().lower()
    if tx:
        m = re.search(r"(afgørelse|konklusion)", tx)
        conc = tx[m.start():] if m else tx[-1500:]
        nm = re.search(r"miljø-?\s*og\s*fødevareklagenævnet", conc)
        seg = conc[nm.start():nm.start() + 400] if nm else conc[-1500:]
        if "ophæver" in seg: return "Ophævet"
        if "stadfæster" in seg: return "Stadfæstelse"
        if "hjemviser" in seg: return "Hjemvist"
        if "ændrer" in seg: return "Ændret"
        if "afviser" in seg: return "Afvist"
        if "ikke medhold" in seg: return "Ikke medhold"
        if "giver medhold" in seg: return "Medhold"
    return "Ukendt"

def detect_sagstype(titel):
    t = titel.lower()
    if "genoptagelse" in t: return "Genoptagelse"
    if "opsaettende virkning" in t or "opsættende virkning" in t: return "Opsættende virkning"
    if any(k in t for k in ("afvisning","afvises")): return "Afvisning"
    if "registrering" in t: return "Registrering"
    if "dispensation" in t: return "Dispensation"
    if "lovliggoerelse" in t or "lovliggørelse" in t: return "Lovliggørelse"
    if "godkendelse" in t: return "Godkendelse"
    if "tilladelse" in t: return "Tilladelse"
    if "anmeldelse" in t: return "Anmeldelse"
    if "vedtagelse" in t: return "Vedtagelse"
    if "paabud" in t or "påbud" in t: return "Påbud"
    if "forbud" in t: return "Forbud"
    if "aktindsigt" in t: return "Aktindsigt"
    return "Realitetsbehandling"

def _underkat_beskyttelseslinje(titel, tekst=""):
    t = (titel + " " + tekst[:400]).lower()
    if "strandbeskyttelseslinje" in t or "havstokken" in t: return "Strandbeskyttelseslinje"
    if "fortidsmindebeskyttelseslinje" in t: return "Fortidsmindebeskyttelseslinje"
    if "aabeskyttelseslinje" in t or "åbeskyttelseslinje" in t: return "Åbeskyttelseslinje"
    if "soebeskyttelseslinje" in t or "søbeskyttelseslinje" in t: return "Søbeskyttelseslinje"
    if "skovbyggelinje" in t: return "Skovbyggelinje"
    if "klitfredning" in t: return "Klitfredning"
    if "kirkebeskyttelseslinje" in t: return "Kirkebeskyttelseslinje"
    return "Andet"

def _underkat_naturtype(titel):
    t = titel.lower()
    if "strandeng" in t: return "Strandeng"
    if "eng" in t: return "Eng"
    if "hede" in t: return "Hede"
    if "mose" in t: return "Mose"
    if "overdrev" in t: return "Overdrev"
    if "vandloeb" in t or "vandløb" in t: return "Vandløb"
    if "skov" in t: return "Skov"
    if "soe" in t or "sø" in t or "søen" in t: return "Sø"
    if "klit" in t: return "Klitter"
    return "Andet"


# ── Data-loading ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser afgørelser…", ttl=None)
def _laes_csv(sti):
    csv.field_size_limit(10_000_000)
    rows = []
    with open(sti, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tekst = strip_html(row.get("Tekst",""), preserve_headings=True)
            excerpt = re.sub(r'^#{2,3} ', '', tekst, flags=re.M).replace('\n', ' ')
            excerpt = re.sub(r'\s+', ' ', excerpt).strip()[:280]
            rows.append({
                "Dato": row.get("Dato",""),
                "Titel": row.get("Titel",""),
                "Link": row.get("Link",""),
                "Tekst": tekst,
                "Excerpt": excerpt,
                "Retsomraade": row.get("Retsomraade", row.get("Retsområde","")),
            })
    return rows

@st.cache_data(show_spinner="Indlæser afgørelser…", ttl=None)
def load_kategori(stem, version=1):
    csv_navn = stem + ".csv"
    csv_sti = os.path.join(_ROOT, csv_navn)
    if not os.path.exists(csv_sti):
        zip_sti = csv_sti + ".zip"
        dest = os.path.join(_TMP, csv_navn)
        if os.path.exists(zip_sti) and not os.path.exists(dest):
            with zipfile.ZipFile(zip_sti) as z:
                for member in z.namelist():
                    if member.endswith(".csv"):
                        with z.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        break
        csv_sti = dest
    if not os.path.exists(csv_sti):
        return pd.DataFrame()
    rows = _laes_csv(csv_sti)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    df["Aar"] = df["Dato"].dt.year.astype("Int64")
    df["Udfald"] = df.apply(lambda r: detect_udfald(r["Titel"], r.get("Tekst", "")), axis=1)
    df["Sagstype"] = df["Titel"].apply(detect_sagstype)
    df["Kommune"] = df["Titel"].apply(extract_kommune)
    # Underkategori
    if stem == "mfkn_nbl_beskyttelseslinier":
        df["Underkategori"] = df.apply(lambda r: _underkat_beskyttelseslinje(r["Titel"], r["Tekst"]), axis=1)
    elif stem in ("mfkn_beskyttede_naturtyper", "mfkn_nbl_beskyttede_naturtyper"):
        df["Underkategori"] = df["Titel"].apply(_underkat_naturtype)
    else:
        df["Underkategori"] = df["Retsomraade"].str.strip()
    return df

@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(stem, n_rows, version: int = 4):
    """TF-IDF over titel×3 + kerneafsnit med dansk stemming.
    version 4: udtræk_kerneafsnit understøtter nu HTML-headings (PKN/MFKN-format),
    hvor v3 faldt igennem til tekst[-N:] for 100% af korpus."""
    df2 = load_kategori(stem, 1)
    texts = [byg_indeks_tekst(t, tx) for t, tx in zip(df2["Titel"].astype(str), df2["Tekst"].astype(str))]
    vec = TfidfVectorizer(max_features=40_000, ngram_range=(1,2), min_df=2, sublinear_tf=True,
                          tokenizer=dansk_tokenizer, token_pattern=None)
    mat = vec.fit_transform(texts)
    return vec, mat


@st.cache_resource(show_spinner=False)
def build_embeddings_mfkn(stem, n_rows, version: int = 1):
    """Persistent semantisk indeks pr. MFKN-kategori. None hvis ingen embedding-nøgle."""
    if not embeddings_tilgængelige():
        return None
    df2 = load_kategori(stem, 1)
    return byg_embeddings_indeks(df2, cache_key=f"mfkn_{stem}")


@st.cache_resource(show_spinner=False)
def _prebuild_all_mfkn_embeddings(_kat_stems: tuple):
    """Byg embeddings for ALLE MFKN-kategorier på én gang, så brugeren
    ikke skal klikke ind på hver enkelt."""
    if not embeddings_tilgængelige():
        return True
    placeholder = st.empty()
    total = len(_kat_stems)
    for i, stem in enumerate(_kat_stems):
        try:
            df2 = load_kategori(stem, 1)
            if df2 is None or df2.empty:
                continue
            placeholder.progress((i) / total,
                text=f"Bygger MFKN-embeddings… {i+1}/{total}")
            byg_embeddings_indeks(df2, cache_key=f"mfkn_{stem}")
        except Exception:
            pass
    placeholder.empty()
    return True

def tfidf_soeg(query, df, vec, mat, sub_idx=None, top_n=30, ekspander: bool = False):
    """TF-IDF med valgfri query expansion og tids-decay boost (nyere sager prioriteres let)."""
    effektiv_query = udvid_query(query) if ekspander else query
    qv = vec.transform([effektiv_query])

    def _boost(global_idx, base):
        try:
            aar = int(df.at[global_idx, "Aar"])
            decay = 1.0 + max(0, min(0.15, (aar - 2017) * 0.02))
            return float(base) * decay
        except Exception:
            return float(base)

    if sub_idx is not None and len(sub_idx) > 0:
        scores_sub = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local = scores_sub.argsort()[-top_n * 2:][::-1]
        kandidater = [(sub_idx[i], scores_sub[i]) for i in top_local if scores_sub[i] > 0.01]
        kandidater = [(g, _boost(g, s)) for g, s in kandidater]
        kandidater.sort(key=lambda x: x[1], reverse=True)
        kandidater = kandidater[:top_n]
        if not kandidater:
            return df.iloc[0:0].copy()
        top_global = [g for g, _ in kandidater]
        result = df.loc[top_global].copy()
        result["_score"] = [s for _, s in kandidater]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top = scores.argsort()[-top_n * 2:][::-1]
        kandidater = [(int(i), scores[i]) for i in top if scores[i] > 0.01]
        kandidater = [(g, _boost(g, s)) for g, s in kandidater]
        kandidater.sort(key=lambda x: x[1], reverse=True)
        kandidater = kandidater[:top_n]
        if not kandidater:
            return df.iloc[0:0].copy()
        top_idx = [g for g, _ in kandidater]
        result = df.iloc[top_idx].copy()
        result["_score"] = [s for _, s in kandidater]
    return result.reset_index(drop=True)


def smart_retrieval_mfkn(spoergsmaal, df, vec, mat, ai_sub_idx, historik,
                          top_retrieve: int = 40, top_final: int = 8, embeds=None,
                          filter_options=None):
    """RAG-pipeline med auto-filtering + hybrid search + adaptiv retrieval.
    auto-filter: Haiku analyserer spørgsmålet og foreslår filtre der indsnævrer korpus.
    Falder tilbage til ren TF-IDF hvis embeds er None."""
    from concurrent.futures import ThreadPoolExecutor

    n_workers = 3 if filter_options else 2
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        fut_classify = pool.submit(klassificer_query, spoergsmaal)
        fut_rewrite = pool.submit(omformuler_opfoelgning, spoergsmaal, historik or [])
        fut_autofilter = pool.submit(auto_filter_query, spoergsmaal, filter_options) if filter_options else None
        qtype = fut_classify.result()
        standalone = fut_rewrite.result()
        auto_filters = fut_autofilter.result() if fut_autofilter else {}

    top_retrieve = qtype["top_retrieve"]
    top_final = qtype["top_final"]

    # Adaptive scaling for large corpora
    corpus_size = len(ai_sub_idx) if ai_sub_idx else len(df)
    if corpus_size > 500:
        top_retrieve = max(top_retrieve, 100)
        top_final = max(top_final, 15)
    elif corpus_size > 200:
        top_retrieve = max(top_retrieve, 70)
        top_final = max(top_final, 12)

    # Apply auto-detected filters
    effective_sub, prefiltered = apply_auto_filters(df, ai_sub_idx, auto_filters)
    st.session_state["_mfkn_last_auto_filters"] = {
        "suggested": auto_filters,
        "applied": prefiltered,
        "before": len(ai_sub_idx) if ai_sub_idx else len(df),
        "after": len(effective_sub) if effective_sub else 0,
    }

    # Prepare expanded query once
    udvidet = udvid_query(standalone)
    tfidf_query = udvidet if udvidet else standalone

    def _do_retrieval(sub):
        if embeds is not None:
            fused = hybrid_retrieval(tfidf_query, df, vec, mat, embeds, sub_idx=sub,
                                     top_retrieve=top_retrieve, top_final=top_retrieve)
            if fused:
                h = df.iloc[fused].copy()
                h["_score"] = [1.0] * len(h)
                return h.reset_index(drop=True)
            return df.iloc[0:0].copy()
        return tfidf_soeg(tfidf_query, df, vec, mat, sub_idx=sub,
                          top_n=top_retrieve, ekspander=False)

    hits = _do_retrieval(effective_sub)
    kandidater = hits.to_dict("records") if len(hits) > 0 else []
    rerankede = llm_rerank(standalone, kandidater, top_n=top_final)

    # Fallback if auto-filter was too aggressive
    if len(rerankede) < 3 and prefiltered:
        hits = _do_retrieval(ai_sub_idx)
        kandidater = hits.to_dict("records") if len(hits) > 0 else []
        rerankede = llm_rerank(standalone, kandidater, top_n=top_final)

    alle_kilder = saml_kilder(historik or [], rerankede, max_total=max(12, top_final + 4))
    return standalone, alle_kilder


# ── AI-funktioner ────────────────────────────────────────────────────────────
def mfkn_svar(spoergsmaal, docs, historik=None, kat_navn=""):
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    kontekst = byg_fokuseret_kontekst(spoergsmaal, docs, max_chunks_per_doc=3)
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel'][:80]}"
        for i, d in enumerate(docs)
    )
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    blocks = [
        {
            "type": "text",
            "text": (
                f"Du er en juridisk assistent specialiseret i dansk forvaltningsret og Miljø- og Fødevareklagenævnets (MFKN) praksis for {kat_navn}. "
                f"Dine brugere er professionelle jurister der kender lovgivningen – giv præcise, faktabaserede svar.\n\n"
                f"REGLER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte afgørelser. Opfind ikke fakta.\n"
                f"2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG kommunenavne eller datoer som reference.\n"
                f"3. Svar på dansk. Strukturér med overskrifter og afsnit.\n"
                f"4. Understøt juridiske påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                f"Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
                f"5. Identificér mønstre på tværs af afgørelserne: er der en fast praksis, eller varierer udfaldet? "
                f"Angiv evt. fordelingen (fx \"4 af 6 afgørelser stadfæster\").\n"
                f"6. Nævn relevant lovhjemmel (§-reference) når den fremgår af afgørelserne.\n"
                f"7. Hvis kilderne ikke besvarer spørgsmålet, skriv det eksplicit. Gæt aldrig.\n"
                f"8. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering.\n\n"
                f"KILDEREGISTER:\n{kilde_liste}"
            ),
        },
        {
            "type": "text",
            "text": f"\nAFGØRELSER:\n{kontekst}\n",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"{samtale_blok}SPØRGSMÅL: {spoergsmaal}\n\nSVAR:",
        },
    ]
    return _llm(blocks)

def mfkn_svar_stream(spoergsmaal, docs, historik=None, kat_navn="", placeholder=None):
    """Streaming-version af mfkn_svar – viser svaret ord-for-ord."""
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    kontekst = byg_fokuseret_kontekst(spoergsmaal, docs, max_chunks_per_doc=3)
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel'][:80]}"
        for i, d in enumerate(docs)
    )
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    blocks = [
        {
            "type": "text",
            "text": (
                f"Du er en juridisk assistent specialiseret i dansk forvaltningsret og Miljø- og Fødevareklagenævnets (MFKN) praksis for {kat_navn}. "
                f"Dine brugere er professionelle jurister der kender lovgivningen – giv præcise, faktabaserede svar.\n\n"
                f"REGLER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte afgørelser. Opfind ikke fakta.\n"
                f"2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG kommunenavne eller datoer som reference.\n"
                f"3. Svar på dansk. Strukturér med overskrifter og afsnit.\n"
                f"4. Understøt juridiske påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                f"Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
                f"5. Identificér mønstre på tværs af afgørelserne: er der en fast praksis, eller varierer udfaldet? "
                f"Angiv evt. fordelingen (fx \"4 af 6 afgørelser stadfæster\").\n"
                f"6. Nævn relevant lovhjemmel (§-reference) når den fremgår af afgørelserne.\n"
                f"7. Hvis kilderne ikke besvarer spørgsmålet, skriv det eksplicit. Gæt aldrig.\n"
                f"8. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering.\n\n"
                f"KILDEREGISTER:\n{kilde_liste}"
            ),
        },
        {
            "type": "text",
            "text": f"\nAFGØRELSER:\n{kontekst}\n",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"{samtale_blok}SPØRGSMÅL: {spoergsmaal}\n\nSVAR:",
        },
    ]
    return _llm_stream(blocks, placeholder=placeholder)

def mfkn_resume(titel, tekst, kat_navn=""):
    if not ANTHROPIC_API_KEY:
        return "Ingen API-nøgle."
    prompt = f"""Lav et kort, struktureret resumé af denne MFKN-afgørelse ({kat_navn}) på dansk.
Inkluder: Sagens kerne, Nævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {udtræk_kerneafsnit(tekst, max_tegn=6000)}

RESUME:"""
    return _llm(prompt)

def erstat_kilde_refs(tekst, kilder):
    def repl(m):
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
        refs = []
        for n in nums:
            if 1 <= n <= len(kilder):
                k = kilder[n - 1]
                kom = extract_kommune(k.get("Titel", "")) or "Kilde"
                try:
                    aar = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    aar = "-"
                refs.append(f"*{kom} {aar}*")
        return "[" + ", ".join(refs) + "]" if refs else m.group(0)
    return re.sub(r"\[Kilde\s+([\d,\s]+)\]", repl, tekst)


# ── Badge-styles ─────────────────────────────────────────────────────────────
_BADGE_STYLE = {
    "Stadfaestelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "Stadfæstelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "Afslag":       "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "Ophævet":      "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
    "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
    "Ændring":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
    "Afvist":       "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
}
_BADGE_DEFAULT = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"

_CHIP_STYLES = {
    "Stadfæstelse": "background:#fef2f2;color:#991b1b;border-color:#fecaca",
    "Afslag":       "background:#fef2f2;color:#991b1b;border-color:#fecaca",
    "Ophævet":      "background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe",
    "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border-color:#ddd6fe",
    "Ændring":      "background:#f0fdf4;color:#166534;border-color:#bbf7d0",
    "Afvist":       "background:#fffbeb;color:#92400e;border-color:#fde68a",
}

BADGE_CLS = {
    "Stadfæstelse": "badge-ikke-medhold",
    "Afslag":       "badge-ikke-medhold",
    "Ophævet":      "badge-ophaevet",
    "Hjemvist":     "badge-ophaevet",
    "Ændring":      "badge-medhold",
    "Afvist":       "badge-afvist",
    "Ukendt":       "badge-ukendt",
}


# ══════════════════════════════════════════════════════════════════════════════
# PAGE START
# ══════════════════════════════════════════════════════════════════════════════

# ── Find tilgaengelige kategorier ────────────────────────────────────────────
alle_kats = _find_kategorier()
if not alle_kats:
    st.warning("Ingen MFKN CSV-filer fundet. Upload mfkn_*.csv eller mfkn_*.csv.zip filer til repo-roden.")
    st.stop()

# Prebuild embeddings for alle kategorier (kører kun én gang)
_prebuild_all_mfkn_embeddings(tuple(sorted(alle_kats.keys())))


kat_navne = {v["navn"]: k for k, v in alle_kats.items()}
kat_liste = _byg_grupperet_liste(alle_kats)

# ── Kategori-vaelger (placeres i sidebar nedenfor) ──────────────────────────
if "mfkn_valgt_kat" not in st.session_state or st.session_state.mfkn_valgt_kat not in kat_liste:
    st.session_state.mfkn_valgt_kat = kat_liste[0]

# Variablen saettes efter sidebar er bygget — se nedenfor
valgt_navn = st.session_state.mfkn_valgt_kat

valgt_stem = kat_navne[valgt_navn]
valgt_info = alle_kats[valgt_stem]
accent = valgt_info["farve"]

# ── CSS accent ───────────────────────────────────────────────────────────────
_CSS = f"""<style>
[data-testid="stSidebar"] .stSlider [role="slider"] {{ background: {accent} !important; }}
[data-testid="collapsedControl"]::after {{ color: {accent} !important; }}
.pkn-card:hover {{ border-color: {accent} !important; }}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {{ border-bottom-color: {accent} !important; }}
.detail-ai-title {{ color: {accent} !important; }}
[data-testid="stBaseButton-secondary"]:hover {{ border-color: {accent} !important; }}
</style>"""
try:
    st.html(_CSS)
except AttributeError:
    st.markdown(_CSS, unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────────────
for key in ["mfkn_valgt", "mfkn_chat"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "mfkn_chat" else None
init_sagsmapper()

# ── Indlaes data ─────────────────────────────────────────────────────────────
df = load_kategori(valgt_stem, 1)
if df.empty:
    st.error(f"Ingen data fundet for {valgt_navn}.")
    st.stop()
vec, mat = build_index(valgt_stem, len(df))
embeds = build_embeddings_mfkn(valgt_stem, len(df))
if embeds is None and embeddings_tilgængelige():
    # Tving genopbygning for KUN denne kategori via version-bump (rydder ikke
    # cachen for andre kategorier).
    _bust_key = f"_mfkn_embed_ver_{valgt_stem}"
    st.session_state[_bust_key] = st.session_state.get(_bust_key, 1) + 1
    embeds = build_embeddings_mfkn(valgt_stem, len(df), st.session_state[_bust_key])

# Auto-filter options for AI retrieval
_mfkn_filter_options = {
    "Underkategori": sorted(df["Underkategori"].dropna().unique().tolist()),
    "Sagstype": sorted(df["Sagstype"].unique().tolist()),
}

_voyage_key_sat = bool(st.secrets.get("VOYAGE_API_KEY", "") or st.secrets.get("OPENAI_API_KEY", ""))
_embeds_ok = embeds is not None

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(150, dark=True)}</div></div>', unsafe_allow_html=True)

    # ── To-trins kategori-vaelger ──
    # Byg gruppe → kategorier mapping (kun tilgaengelige)
    _grupper = {}
    for stem, info in alle_kats.items():
        g = info.get("gruppe", "Øvrige")
        _grupper.setdefault(g, []).append(info["navn"])
    for g in _grupper:
        _grupper[g].sort()
    _tilg_grupper = [g for g in _GRUPPE_ORDEN if g in _grupper]

    # Find aktuel gruppe ud fra valgt kategori
    _aktuel_gruppe = "Øvrige"
    for stem, info in alle_kats.items():
        if info["navn"] == st.session_state.mfkn_valgt_kat:
            _aktuel_gruppe = info.get("gruppe", "Øvrige")
            break

    st.markdown('<span class="h-filter-label">Tema</span>', unsafe_allow_html=True)
    valgt_gruppe = st.selectbox(
        "Tema",
        _tilg_grupper,
        index=_tilg_grupper.index(_aktuel_gruppe) if _aktuel_gruppe in _tilg_grupper else 0,
        key="_mfkn_gruppe_select",
        label_visibility="collapsed",
    )

    _kats_i_gruppe = _grupper.get(valgt_gruppe, kat_liste[:1])
    st.markdown('<span class="h-filter-label">Retsområde</span>', unsafe_allow_html=True)
    _default_idx = 0
    if st.session_state.mfkn_valgt_kat in _kats_i_gruppe:
        _default_idx = _kats_i_gruppe.index(st.session_state.mfkn_valgt_kat)
    valgt_navn = st.selectbox(
        "Retsomraade",
        _kats_i_gruppe,
        index=_default_idx,
        key="_mfkn_kat_select",
        label_visibility="collapsed",
    )
    # Reset state on category change
    if valgt_navn != st.session_state.get("mfkn_valgt_kat"):
        st.session_state.mfkn_valgt_kat = valgt_navn
        st.session_state.mfkn_valgt = None
        st.session_state.mfkn_chat = []
        if "mfkn_resume_txt" in st.session_state:
            del st.session_state["mfkn_resume_txt"]
        st.session_state["mfkn_vis_antal"] = 25
        st.rerun()

    st.markdown("---")

    st.markdown('<span class="h-filter-label">Søgeord</span>', unsafe_allow_html=True)
    soeg_input = st.text_input("", placeholder="f.eks. dispensation terrasse...", label_visibility="collapsed", key="mfkn_soeg")
    soege_type = st.radio("", ["Ordret", "Intelligent"], horizontal=True, label_visibility="collapsed", key="mfkn_soegetype")
    st.markdown('<span style="font-size:10px;color:#64748b;line-height:1.4;display:block;margin-top:-8px;">'
                'Ordret = nøjagtig tekstmatch &nbsp;·&nbsp; Intelligent = AI finder relevante sager</span>',
                unsafe_allow_html=True)

    # Underkategori filter (kun hvis der er mere end 1)
    _alle_underkat = sorted(df["Underkategori"].dropna().unique())
    if len(_alle_underkat) > 1:
        st.markdown('<span class="h-filter-label">Underkategori</span>', unsafe_allow_html=True)
        valgte_underkat = st.multiselect("", _alle_underkat, label_visibility="collapsed", key="mfkn_underkat")
    else:
        valgte_underkat = []

    st.markdown('<span class="h-filter-label">Sagstype</span>', unsafe_allow_html=True)
    _alle_sagstyper = sorted(df["Sagstype"].unique())
    sagstype_valg = st.multiselect("", _alle_sagstyper, label_visibility="collapsed", key="mfkn_sg")

    st.markdown('<span class="h-filter-label">Årsinterval</span>', unsafe_allow_html=True)
    _aar_min_raw, _aar_max_raw = df["Aar"].min(), df["Aar"].max()
    aar_min = int(_aar_min_raw) if pd.notna(_aar_min_raw) else 2017
    aar_max = int(_aar_max_raw) if pd.notna(_aar_max_raw) else 2026
    if aar_max < aar_min:
        aar_max = 2026
    _default_start = max(2017, aar_min)
    aar_range = st.slider("", aar_min, aar_max, (_default_start, aar_max), label_visibility="collapsed", key="mfkn_yr")

    st.markdown('<span class="h-filter-label">Udfald</span>', unsafe_allow_html=True)
    udfald_valg = st.multiselect("", sorted(df["Udfald"].unique()), label_visibility="collapsed", key="mfkn_ud")

    st.markdown("---")
    st.markdown(f"<span style='font-size:12px;color:#5a7a9e'>**{len(df):,}** afgørelser &nbsp;·&nbsp; {aar_min}-{aar_max}</span>", unsafe_allow_html=True)

    # Nulstil filtre
    _har_filtre = bool(valgte_underkat or sagstype_valg or udfald_valg or soeg_input.strip()
                       or aar_range != (_default_start, aar_max))
    if _har_filtre:
        if st.button("Nulstil filtre", use_container_width=True, key="_mfkn_reset"):
            for k in ["mfkn_underkat", "mfkn_sg", "mfkn_ud", "mfkn_soeg", "mfkn_yr"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

# ── Filtrering ───────────────────────────────────────────────────────────────
mask = df["Aar"].isna() | ((df["Aar"] >= aar_range[0]) & (df["Aar"] <= aar_range[1]))
if valgte_underkat:  mask &= df["Underkategori"].isin(valgte_underkat)
if sagstype_valg:    mask &= df["Sagstype"].isin(sagstype_valg)
if udfald_valg:      mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx = df[mask].index.tolist()

_filter_sig = (valgt_stem, len(df_filter), soeg_input.strip(), soege_type)
if st.session_state.get("mfkn_filter_sig") != _filter_sig:
    st.session_state["mfkn_vis_antal"] = 25
    st.session_state["mfkn_filter_sig"] = _filter_sig
_vis_antal = st.session_state.get("mfkn_vis_antal", 25)

if soeg_input.strip() and soege_type == "Intelligent":
    df_vis = tfidf_soeg(soeg_input.strip(), df, vec, mat, sub_idx=sub_idx)
    ai_sub_idx = sub_idx
elif soeg_input.strip():
    _text_mask = (
        df_filter["Titel"].str.contains(soeg_input.strip(), case=False, na=False, regex=False) |
        df_filter["Tekst"].str.contains(soeg_input.strip(), case=False, na=False, regex=False)
    )
    df_vis = df_filter[_text_mask].sort_values("Dato", ascending=False).reset_index(drop=True)
    ai_sub_idx = [sub_idx[i] for i in df_filter.index[_text_mask].tolist()] if _text_mask.any() else sub_idx
else:
    df_vis = df_filter.sort_values("Dato", ascending=False)
    ai_sub_idx = sub_idx

# Download
with st.sidebar:
    n = len(df_filter)
    st.markdown("---")
    if n > 0:
        def _dl_tekst(data):
            lines = [f"MFKN {valgt_navn.upper()} - EKSPORT", f"Antal: {len(data)}", "=" * 72, ""]
            for _, row in data.iterrows():
                dato = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "-"
                lines += [
                    f"AFGØRELSE:  {row['Titel']}", f"DATO:       {dato}",
                    f"SAGSTYPE:   {row['Sagstype']}  |  UDFALD: {row['Udfald']}  |  KOMMUNE: {row['Kommune'] or '-'}",
                    f"KILDE:      {row['Link']}", "-" * 72, row["Tekst"].strip(), "", "=" * 72, "",
                ]
            return "\n".join(lines)
        st.download_button(
            label=f"Download {n:,} afgørelser (.txt)",
            data=_dl_tekst(df_filter).encode("utf-8"),
            file_name=f"mfkn_{valgt_stem}.txt", mime="text/plain",
        )
    sidebar_log_ud()

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header">
  <h1 class="h-page-title">Miljø- og Fødevareklagenævnet</h1>
  <p class="h-page-meta">{valgt_navn} &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {aar_min}–{aar_max}</p>
</div>
""", unsafe_allow_html=True)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_soeg, tab_stat, tab_ai, tab_vejl = st.tabs(["  Afgørelser  ", "  Statistik  ", "  AI Assistent  ", "  Vejledninger  "])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 - AFGOERELSER
# ══════════════════════════════════════════════════════════════════════════════
with tab_soeg:

    # Navigation fra sagsmappe
    _nav = st.session_state.pop("_navigate_to_decision", None)
    if _nav and _nav.get("kilde") == "mfkn":
        _match = df[df["Link"] == _nav["link"]]
        if not _match.empty:
            st.session_state.mfkn_valgt = _match.iloc[0].to_dict()

    if st.session_state.mfkn_valgt is not None:
        row = st.session_state.mfkn_valgt

        if st.button("← Alle afgørelser"):
            st.session_state.mfkn_valgt = None
            st.rerun()

        udfald = row.get("Udfald", "Ukendt")
        chip_s = _CHIP_STYLES.get(udfald, "background:#f8fafc;color:#64748b;border-color:#e2e8f0")
        dato_str = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(pd.Timestamp(row["Dato"])) else "-"
        sagstype = row.get("Sagstype") or "-"
        kommune = row.get("Kommune") or "-"
        underkat = row.get("Underkategori") or "-"

        st.markdown(
            render_detail_header(
                titel=row["Titel"], udfald=udfald, chip_style=chip_s, dato_str=dato_str,
                meta_extra=[("Underkategori", underkat), ("Sagstype", sagstype), ("Kommune", kommune)],
                link=row["Link"], link_label="Åbn original på MFKN's hjemmeside", accent=accent,
            ), unsafe_allow_html=True,
        )

        # ── Gem i sagsmappe ─────────────────────────────────────────────────
        _gemte = hent_alle_gemte_links()
        _er_gemt = row["Link"] in _gemte
        _save_c1, _save_c2 = st.columns([2, 6])
        with _save_c1:
            if _er_gemt:
                _mid_d = find_mappe_for_link(row["Link"])
                _mname_d = st.session_state["sagsmapper"]["mapper"].get(_mid_d, {}).get("navn", "")
                with st.popover(f"★ Gemt i {_mname_d}", use_container_width=True):
                    if st.button("Fjern fra sagsmappe", key="_mfkn_detail_rm", type="primary"):
                        fjern_afgørelse(_mid_d, row["Link"])
                        st.toast("Fjernet fra sagsmappe", icon="✓")
                        st.rerun()
            else:
                _mapper_d = st.session_state["sagsmapper"]["mapper"]
                if not _mapper_d:
                    if st.button("☆ Gem i sagsmappe", key="_mfkn_detail_save", use_container_width=True):
                        gem_fra_row(row, "mfkn")
                        st.toast("Gemt i 'Mine afgørelser'", icon="📁")
                        st.rerun()
                else:
                    with st.popover("☆ Gem i sagsmappe", use_container_width=True):
                        st.caption("Gem i mappe:")
                        for _midd, _md in _mapper_d.items():
                            if st.button(_md["navn"], key=f"_mfkn_d_sv_{_midd}", use_container_width=True):
                                gem_fra_row(row, "mfkn", mappe_id=_midd)
                                st.toast(f"Gemt i '{_md['navn']}'", icon="📁")
                                st.rerun()
                        st.markdown("---")
                        _nyd = st.text_input("Ny mappe", placeholder="Mappenavn…",
                                             label_visibility="collapsed", key="_mfkn_d_nm")
                        if st.button("＋ Opret og gem", key="_mfkn_d_nb",
                                     use_container_width=True, type="primary"):
                            if _nyd.strip():
                                _newm = opret_mappe(_nyd.strip())
                                gem_fra_row(row, "mfkn", mappe_id=_newm)
                                st.toast(f"Gemt i ny mappe '{_nyd.strip()}'", icon="📁")
                                st.rerun()

        col_tekst, col_ai = st.columns([3, 2], gap="large")
        with col_tekst:
            st.markdown(format_afgørelse_tekst(row["Tekst"]), unsafe_allow_html=True)
        with col_ai:
            st.markdown('<div class="detail-ai-panel"><div class="detail-ai-title">AI-Resume</div>', unsafe_allow_html=True)
            if st.button("Generer resume ->", key="mfkn_gen_res"):
                with st.spinner("Analyserer..."):
                    try:
                        st.session_state.mfkn_resume_txt = mfkn_resume(row["Titel"], row["Tekst"], valgt_navn)
                    except Exception as e:
                        st.session_state.mfkn_resume_txt = f"Fejl: {e}"
            if "mfkn_resume_txt" in st.session_state:
                st.markdown(f'<div class="detail-ai-resume">{st.session_state.mfkn_resume_txt}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        total_filtreret = len(df_filter)
        hits = len(df_vis)
        if soeg_input:
            label = f"**{hits}** resultater for \"{soeg_input}\" (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {min(_vis_antal, hits)} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            empty_state(
                "Ingen afgørelser matcher din søgning",
                "Prøv at udvide filtrene eller ændre søgeordene.",
                icon="search_off",
            )
            if _har_filtre:
                if st.button("Nulstil filtre", key="_mfkn_reset_empty", use_container_width=False):
                    for k in ["mfkn_underkat", "mfkn_sg", "mfkn_ud", "mfkn_soeg", "mfkn_soegetype"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
        else:
            _hl_q = soeg_input.strip() if soeg_input.strip() else ""
            _gemte_links = hent_alle_gemte_links()
            for _, row in df_vis.head(_vis_antal).iterrows():
                badge_style = _BADGE_STYLE.get(row["Udfald"], _BADGE_DEFAULT)
                dato_str = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "-"
                underkat_tag = row.get("Underkategori", "")
                sagstype_tag = row.get("Sagstype", "")
                _hl_titel   = highlight_query(row["Titel"], _hl_q) if _hl_q else row["Titel"]
                _hl_excerpt = highlight_query(row["Excerpt"], _hl_q, max_len=300) if _hl_q else (row["Excerpt"] + "...")
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;">{dato_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;{badge_style}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{_hl_titel}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{underkat_tag}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{sagstype_tag}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{_hl_excerpt}</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn afgørelse på portalen</a>
  </div>
</div>""", unsafe_allow_html=True)
                _link_hash = hash(row['Link'])
                _c_read, _c_save = st.columns([4, 1.2])
                with _c_read:
                    if st.button("Læs afgørelse →", key=f"mfkn_btn_{_link_hash}"):
                        st.session_state.mfkn_valgt = row.to_dict()
                        if "mfkn_resume_txt" in st.session_state:
                            del st.session_state["mfkn_resume_txt"]
                        st.rerun()
                with _c_save:
                    _mlink = row["Link"]
                    if _mlink in _gemte_links:
                        _mid = find_mappe_for_link(_mlink)
                        _mname = st.session_state["sagsmapper"]["mapper"].get(_mid, {}).get("navn", "")
                        with st.popover("★ Gemt", use_container_width=True):
                            st.caption(f"Gemt i: **{_mname}**")
                            if st.button("Fjern fra sagsmappe", key=f"mfkn_rm_{_link_hash}", type="primary"):
                                fjern_afgørelse(_mid, _mlink)
                                st.toast("Fjernet fra sagsmappe", icon="✓")
                                st.rerun()
                    else:
                        _mapper = st.session_state["sagsmapper"]["mapper"]
                        if not _mapper:
                            if st.button("☆ Gem", key=f"mfkn_save_{_link_hash}", use_container_width=True):
                                gem_fra_row(row.to_dict(), "mfkn")
                                st.toast("Gemt i 'Mine afgørelser'", icon="📁")
                                st.rerun()
                        else:
                            with st.popover("☆ Gem", use_container_width=True):
                                st.caption("Gem i mappe:")
                                for _mid, _m in _mapper.items():
                                    if st.button(_m["navn"], key=f"mfkn_sv_{_link_hash}_{_mid}", use_container_width=True):
                                        gem_fra_row(row.to_dict(), "mfkn", mappe_id=_mid)
                                        st.toast(f"Gemt i '{_m['navn']}'", icon="📁")
                                        st.rerun()
                                st.markdown("---")
                                _ny = st.text_input("Ny mappe", placeholder="Mappenavn…",
                                                    label_visibility="collapsed",
                                                    key=f"mfkn_nm_{_link_hash}")
                                if st.button("＋ Opret og gem", key=f"mfkn_nb_{_link_hash}",
                                             use_container_width=True, type="primary"):
                                    if _ny.strip():
                                        _new_mid = opret_mappe(_ny.strip())
                                        gem_fra_row(row.to_dict(), "mfkn", mappe_id=_new_mid)
                                        st.toast(f"Gemt i ny mappe '{_ny.strip()}'", icon="📁")
                                        st.rerun()

            if _vis_antal < hits:
                tilbage = hits - _vis_antal
                if st.button(f"Vis 25 mere ({tilbage} tilbage)", use_container_width=True):
                    st.session_state["mfkn_vis_antal"] = _vis_antal + 25
                    st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 - STATISTIK
# ══════════════════════════════════════════════════════════════════════════════
with tab_stat:
    d = df_filter

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(d):,}</div>'
                    f'<div class="stat-label">Afgørelser</div></div>', unsafe_allow_html=True)
    with k2:
        pct = d["Udfald"].isin(["Ophævet","Hjemvist","Ændring"]).mean() * 100 if len(d) > 0 else 0
        st.markdown(f'<div class="stat-card"><div class="stat-number">{pct:.0f}%</div>'
                    f'<div class="stat-label">Medhold-rate</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kommune"].nunique()}</div>'
                    f'<div class="stat-label">Kommuner</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Underkategori"].nunique()}</div>'
                    f'<div class="stat-label">Underkategorier</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Afgørelser per år")
        if not d.empty:
            aar_df = d.groupby("Aar").size().reset_index(name="Antal")
            fig = px.bar(aar_df, x="Aar", y="Antal", color_discrete_sequence=[accent])
            fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Fordeling på underkategori")
        if not d.empty:
            kat_df = d.groupby("Underkategori").size().reset_index(name="Antal")
            fig2 = px.pie(kat_df, values="Antal", names="Underkategori",
                          color_discrete_sequence=px.colors.sequential.Greens_r, hole=0.4)
            fig2.update_layout(margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig2, use_container_width=True)

    col_ll, col_rr = st.columns(2)

    with col_ll:
        st.markdown("#### Udfald over tid")
        if not d.empty:
            udfald_aar = d.groupby(["Aar", "Udfald"]).size().reset_index(name="Antal")
            farver = {
                "Stadfæstelse": "#ef4444", "Afslag": "#f97316",
                "Ophævet": "#8b5cf6", "Ændring": "#10b981",
                "Afvist": "#f59e0b", "Hjemvist": "#6366f1", "Ukendt": "#94a3b8",
            }
            fig3 = px.bar(udfald_aar, x="Aar", y="Antal", color="Udfald",
                          color_discrete_map=farver, barmode="stack")
            fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig3, use_container_width=True)

    with col_rr:
        st.markdown("#### Top 15 kommuner")
        if not d.empty:
            kom_df = (d.dropna(subset=["Kommune"]).groupby("Kommune").size()
                       .reset_index(name="Sager").sort_values("Sager", ascending=True).tail(15))
            fig4 = px.bar(kom_df, x="Sager", y="Kommune", orientation="h",
                          color_discrete_sequence=[accent])
            fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10, b=10, l=10, r=10))
            st.plotly_chart(fig4, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 - AI ASSISTENT
# ══════════════════════════════════════════════════════════════════════════════
with tab_ai:
    n_ai = len(ai_sub_idx)
    filter_tekst = f"alle <strong>{len(df):,}</strong> afgørelser" if n_ai == len(df) else f"<strong>{n_ai:,}</strong> afgørelser (filtreret)"
    _søge_mode = "Hybrid (TF-IDF + semantisk)" if embeds is not None else "TF-IDF"
    st.markdown(f"""
<div class="ai-hero">
  <span class="material-symbols-rounded ai-hero-icon">smart_toy</span>
  <div>
    <div class="ai-hero-title">Spørg til MFKN-praksis</div>
    <div class="ai-hero-sub">
      Søger i {filter_tekst} og svarer med kildehenvisninger.
      Opfølgningsspørgsmål husker kontekst.
    </div>
    <div style="font-size:10.5px;color:#94a3b8;margin-top:4px;">Søgemetode: {_søge_mode}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    if not _embeds_ok:
        _debug = bool(st.secrets.get("DEBUG", False))
        if _debug:
            try:
                _secret_keys = sorted([k for k in st.secrets.keys()])
            except Exception:
                _secret_keys = []
            _key_liste = ", ".join(f"`{k}`" for k in _secret_keys) if _secret_keys else "(ingen)"
            if _voyage_key_sat:
                st.warning(
                    "**[debug] Intelligent søgning ikke aktiv.**\n\n"
                    f"**API-fejl:** `{get_embed_error() or 'ukendt'}`\n\n"
                    f"Fundne secrets: {_key_liste}", icon="⚠️",
                )
            else:
                st.info(f"**[debug]** TF-IDF aktiv. Fundne secrets: {_key_liste}", icon="ℹ️")
    if not ANTHROPIC_API_KEY:
        st.error("Tilføj `ANTHROPIC_API_KEY` i Streamlit secrets.")
    else:
        # Kontekstuelle forslag baseret på aktive filtre
        _kat_lav = valgt_navn.lower()
        if sagstype_valg and len(sagstype_valg) == 1:
            _sg_ctx = sagstype_valg[0].lower()
            forslag = [
                f"Hvad er MFKN's praksis for {_sg_ctx} i {_kat_lav}-sager?",
                f"Hvornår giver MFKN medhold i {_sg_ctx}-sager?",
                f"Hvilke hensyn vægtes ved {_sg_ctx} ({_kat_lav})?",
                f"Hvornår afviser MFKN klager over {_sg_ctx}?",
            ]
        elif udfald_valg and len(udfald_valg) == 1:
            _ud_ctx = udfald_valg[0].lower()
            forslag = [
                f"Hvornår ender {_kat_lav}-sager med {_ud_ctx}?",
                f"Hvilke argumenter fører til {_ud_ctx} i {_kat_lav}?",
                f"Hvad er MFKN's praksis for {_kat_lav}?",
                f"Hvilke hensyn vægtes i {_kat_lav}-sager?",
            ]
        else:
            forslag = [
                f"Hvad er MFKN's praksis for {_kat_lav}?",
                f"Hvornår ophæver MFKN kommunens afgørelse?",
                f"Hvilke hensyn vægtes i {_kat_lav}-sager?",
                f"Hvornår gives der dispensation?",
            ]
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"mfkn_fs_{i}"):
                st.session_state.mfkn_chat.append({"rolle": "bruger", "tekst": f})
                st.markdown(f'<div class="chat-user">{f}</div>', unsafe_allow_html=True)
                svar_placeholder = st.empty()
                try:
                    _, alle_kilder = smart_retrieval_mfkn(
                        f, df, vec, mat, ai_sub_idx,
                        st.session_state.mfkn_chat, top_retrieve=40, top_final=8,
                        embeds=embeds, filter_options=_mfkn_filter_options,
                    )
                except Exception:
                    alle_kilder = []
                if not alle_kilder:
                    st.error("Kunne ikke hente kilder — prøv igen eller justér filtre.")
                    st.stop()
                try:
                    svar = mfkn_svar_stream(f, alle_kilder,
                                            historik=st.session_state.mfkn_chat,
                                            kat_navn=valgt_navn, placeholder=svar_placeholder)
                    svar = _tilfoej_citat_advarsel(svar, alle_kilder)
                    try:
                        svar_placeholder.markdown(svar, unsafe_allow_html=True)
                    except Exception:
                        pass
                except Exception as e:
                    alle_kilder = []
                    svar = f"Fejl: {e}"
                    svar_placeholder.error(svar)
                _af_info = st.session_state.pop("_mfkn_last_auto_filters", None)
                st.session_state.mfkn_chat.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder,
                     "auto_filters": _af_info})
                st.rerun()

        # Input-form (øverst)
        with st.form("mfkn_chat_form", clear_on_submit=True):
            spoergsmaal = st.text_area("Dit spørgsmål", height=80,
                                       placeholder="Hvad er MFKN's praksis for…?")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send", use_container_width=True, type="primary")
            ryd = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.mfkn_chat = []
            st.rerun()

        if send and spoergsmaal.strip():
            st.session_state.mfkn_chat.append({"rolle": "bruger", "tekst": spoergsmaal})
            st.markdown(f'<div class="chat-user">{spoergsmaal}</div>', unsafe_allow_html=True)
            svar_placeholder = st.empty()
            try:
                _, alle_kilder = smart_retrieval_mfkn(
                    spoergsmaal, df, vec, mat, ai_sub_idx,
                    st.session_state.mfkn_chat, top_retrieve=40, top_final=8,
                    embeds=embeds, filter_options=_mfkn_filter_options,
                )
            except Exception:
                alle_kilder = []
            if not alle_kilder:
                st.error("Kunne ikke hente kilder — prøv igen eller justér filtre.")
                st.stop()
            try:
                svar = mfkn_svar_stream(spoergsmaal, alle_kilder,
                                        historik=st.session_state.mfkn_chat,
                                        kat_navn=valgt_navn, placeholder=svar_placeholder)
                svar = _tilfoej_citat_advarsel(svar, alle_kilder)
                try:
                    svar_placeholder.markdown(svar, unsafe_allow_html=True)
                except Exception:
                    pass
            except Exception as e:
                alle_kilder = []
                svar = f"Fejl ved API: {e}"
                svar_placeholder.error(svar)
            _af_info = st.session_state.pop("_mfkn_last_auto_filters", None)
            st.session_state.mfkn_chat.append(
                {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder,
                 "auto_filters": _af_info})
            st.rerun()

        st.divider()

        for msg_idx, msg in enumerate(st.session_state.mfkn_chat):
            if msg["rolle"] == "bruger":
                st.markdown(f'<div class="chat-user">{msg["tekst"]}</div>', unsafe_allow_html=True)
            else:
                kilder = msg.get("kilder", [])
                vist_tekst = erstat_kilde_refs(msg["tekst"], kilder) if kilder else msg["tekst"]

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    _af = msg.get("auto_filters")
                    if _af and _af.get("suggested"):
                        _chips = " · ".join(
                            f"<strong>{k}:</strong> {', '.join(str(v) for v in vs)}"
                            for k, vs in _af["suggested"].items()
                        )
                        _status = (
                            f'Indsnævret til {_af["after"]} afgørelser'
                            if _af.get("applied") else "Foreslået (ikke anvendt — for få hits)"
                        )
                        st.markdown(
                            f'<div style="margin:0 0 0.6rem;padding:6px 10px;background:#f8fafc;'
                            f'border:1px solid #eef1f6;border-radius:4px;font-size:11px;color:#64748b;">'
                            f'<span style="color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;'
                            f'font-weight:600;font-size:9.5px;">Auto-filter</span> &nbsp;{_chips} '
                            f'<span style="color:#94a3b8;">— {_status}</span></div>',
                            unsafe_allow_html=True,
                        )
                    st.markdown(f'<div class="chat-assistant">{vist_tekst}</div>', unsafe_allow_html=True)
                    # Feedback + copy knapper
                    fb_key = f"mfkn_fb_{msg_idx}"
                    fb_state = st.session_state.get(fb_key)
                    fb1, fb2, fb3 = st.columns([1, 1, 2])
                    with fb1:
                        if st.button("👍" if fb_state != "up" else "✅",
                                     key=f"{fb_key}_up", disabled=fb_state is not None,
                                     help="Godt svar"):
                            st.session_state[fb_key] = "up"
                            _log_feedback("mfkn", msg.get("tekst", "")[:200], "up")
                            st.rerun()
                    with fb2:
                        if st.button("👎" if fb_state != "down" else "❌",
                                     key=f"{fb_key}_down", disabled=fb_state is not None,
                                     help="Dårligt svar"):
                            st.session_state[fb_key] = "down"
                            _log_feedback("mfkn", msg.get("tekst", "")[:200], "down")
                            st.rerun()
                    with fb3:
                        _ren_tekst = strip_html(msg.get("tekst", ""))
                        copy_button(_ren_tekst, label="Kopiér svar", key=f"mfkn_cp_{msg_idx}")
                with col_kld:
                    if kilder:
                        st.markdown(
                            '<div style="font-size:11px;font-weight:700;color:#475569;'
                            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                            'Kilder</div>', unsafe_allow_html=True
                        )
                        for i, k in enumerate(kilder[:8]):
                            try:
                                dato_str = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
                                aar_str = str(pd.Timestamp(k["Dato"]).year)
                            except Exception:
                                dato_str = "-"
                                aar_str = "-"
                            kommune = extract_kommune(k.get("Titel", "")) or "Ukendt"
                            udfald = k.get("Udfald", "")
                            badge_cls = BADGE_CLS.get(udfald, "badge-ukendt")
                            badge_html = f'<span class="pkn-badge {badge_cls}">{udfald}</span>' if udfald else ""

                            with st.expander(f"[{i+1}] {kommune} - {aar_str}"):
                                if st.button(f"Åbn afgørelsen", key=f"mfkn_kilde_{msg_idx}_{i}",
                                             use_container_width=True, type="primary"):
                                    st.session_state.mfkn_valgt = k
                                    if "mfkn_resume_txt" in st.session_state:
                                        del st.session_state["mfkn_resume_txt"]
                                    st.rerun()
                                st.markdown(
                                    f'<div style="font-size:13px;font-weight:600;color:#1e3a5f;'
                                    f'margin:8px 0 4px;line-height:1.4">{k["Titel"]}</div>',
                                    unsafe_allow_html=True
                                )
                                st.markdown(
                                    f'<div style="font-size:11px;color:#64748b;margin-bottom:10px">'
                                    f'{dato_str} &nbsp;·&nbsp; {k.get("Sagstype","")}'
                                    f'&nbsp;&nbsp;{badge_html}</div>',
                                    unsafe_allow_html=True
                                )
                                tekst_fmt = re.sub(r'\. ([A-Z])', r'.</p><p>\1', k.get("Tekst","")[:1500])
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
                                    f'Åbn original afgørelse på MFKN hjemmeside</a>',
                                    unsafe_allow_html=True
                                )

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 – VEJLEDNINGER
# ════════════════════════════════════════════════════════════════════════════
with tab_vejl:
    import os as _os, json as _json

    _vejl_root = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "vejledninger")

    @st.cache_data(show_spinner=False)
    def _load_vejledninger_mfkn(kat_stem):
        _meta_file = _os.path.join(_vejl_root, f"mfkn_{kat_stem}_vejledninger.json")
        if _os.path.exists(_meta_file):
            with open(_meta_file, "r", encoding="utf-8") as f:
                return _json.load(f)
        _general = _os.path.join(_vejl_root, "mfkn_vejledninger.json")
        if _os.path.exists(_general):
            with open(_general, "r", encoding="utf-8") as f:
                return _json.load(f)
        return []

    _vejl_liste = _load_vejledninger_mfkn(valgt_stem)

    if not _vejl_liste:
        st.markdown(
            '<div style="text-align:center;padding:4rem 1rem;background:#f8fafc;'
            'border:1px dashed #cbd5e1;border-radius:10px;">'
            f'<span class="material-symbols-rounded" style="font-size:40px;color:#94a3b8;'
            f'display:block;margin-bottom:1rem;">menu_book</span>'
            '<div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:0.5rem;">'
            'Vejledninger er under opbygning</div>'
            '<div style="font-size:13px;color:#94a3b8;line-height:1.7;max-width:440px;margin:0 auto;">'
            'Vi kortlægger og indsamler de vigtigste myndighedsvejledninger for '
            f'{valgt_navn.lower()}. '
            'Snart kan du vælge en vejledning og stille spørgsmål direkte til indholdet.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # ── Vælg vejledning ──────────────────────────────────────────────
        _vejl_titler = {v["id"]: v["titel"] for v in _vejl_liste}
        _sel_col, _info_col = st.columns([3, 2])
        with _sel_col:
            st.markdown(f'<span class="h-filter-label" style="color:{accent};">Vælg vejledning</span>',
                        unsafe_allow_html=True)
            _valgt_vejl_id = st.selectbox(
                "", list(_vejl_titler.keys()),
                format_func=lambda x: _vejl_titler[x],
                label_visibility="collapsed", key="_mfkn_vejl_select",
            )

        _valgt_vejl = next((v for v in _vejl_liste if v["id"] == _valgt_vejl_id), None)

        if _valgt_vejl:
            with _info_col:
                st.markdown(
                    f'<div style="padding-top:1.6rem;">'
                    f'<div style="font-size:11px;color:#94a3b8;">'
                    f'{_valgt_vejl.get("udgiver", "")} · {_valgt_vejl.get("aar", "")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── To kolonner: indhold + AI ────────────────────────────────
            _col_tekst, _col_ai = st.columns([3, 2], gap="large")

            with _col_tekst:
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.8rem;">'
                    f'<span class="material-symbols-rounded" style="font-size:20px;color:{accent};">description</span>'
                    f'<span style="font-size:14px;font-weight:600;color:#0f172a;">Indhold</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                _tekst = _valgt_vejl.get("tekst") or ""
                if _tekst:
                    _vejl_søg = st.text_input("Søg i vejledningen", placeholder="Fx: dispensation, §35…",
                                              label_visibility="collapsed", key="_mfkn_vejl_tsøg")
                    _display_tekst = _tekst
                    if _vejl_søg:
                        _display_tekst = highlight_query(_tekst, _vejl_søg, max_len=len(_tekst))
                    st.markdown(
                        f'<div style="font-size:13.5px;line-height:1.8;color:#1e293b;'
                        f'max-height:600px;overflow-y:auto;padding:16px 20px;'
                        f'background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">'
                        f'{_display_tekst}</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    _ro = ", ".join(_valgt_vejl.get("retsomraade", []))
                    _cit = _valgt_vejl.get("citationer", 0)
                    st.markdown(
                        f'<div style="background:#fffbeb;border:1px solid #fde68a;border-radius:8px;'
                        f'padding:16px 20px;margin-bottom:1rem;">'
                        f'<div style="font-size:13px;font-weight:600;color:#92400e;margin-bottom:8px;">'
                        f'Vejledningstekst ikke hentet endnu</div>'
                        f'<div style="font-size:12px;color:#78350f;line-height:1.7;">'
                        f'Kør <code>python fetch_vejledninger.py</code> for at hente teksten fra retsinformation.dk.'
                        f'</div></div>'
                        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
                        f'padding:16px 20px;">'
                        f'<div style="font-size:12px;color:#64748b;line-height:1.8;">'
                        f'<strong>Udgiver:</strong> {_valgt_vejl.get("udgiver", "–")}<br>'
                        f'<strong>År:</strong> {_valgt_vejl.get("aar", "–")}<br>'
                        f'<strong>Retsområde:</strong> {_ro or "–"}<br>'
                        f'<strong>Citeret i afgørelser:</strong> {_cit}x'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )

                if _valgt_vejl.get("url"):
                    st.markdown(
                        f'<a href="{_valgt_vejl["url"]}" target="_blank" '
                        f'style="font-size:12px;color:#94a3b8;text-decoration:none;font-weight:500;'
                        f'margin-top:8px;display:inline-block;">Åbn original vejledning ↗</a>',
                        unsafe_allow_html=True,
                    )

            with _col_ai:
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:8px;margin-bottom:0.8rem;">'
                    f'<span class="material-symbols-rounded" style="font-size:20px;color:{accent};">smart_toy</span>'
                    f'<span style="font-size:14px;font-weight:600;color:#0f172a;">Spørg om vejledningen</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                _chat_key = f"mfkn_vejl_chat_{_valgt_vejl_id}"
                if _chat_key not in st.session_state:
                    st.session_state[_chat_key] = []

                _historik = st.session_state[_chat_key]

                if not _historik:
                    st.markdown(
                        f'<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;'
                        f'padding:16px;margin-bottom:1rem;">'
                        f'<div style="font-size:12.5px;color:#64748b;line-height:1.7;">'
                        f'Stil et spørgsmål om <strong>{_valgt_vejl["titel"]}</strong> '
                        f'— Harald svarer udelukkende baseret på vejledningens indhold.</div></div>',
                        unsafe_allow_html=True,
                    )

                for msg in _historik:
                    if msg["rolle"] == "bruger":
                        st.markdown(
                            f'<div style="background:#f1f5f9;border-radius:8px;padding:12px 16px;'
                            f'margin-bottom:8px;font-size:13px;color:#0f172a;">'
                            f'<strong>Dig:</strong> {msg["tekst"]}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;'
                            f'padding:12px 16px;margin-bottom:8px;font-size:13px;color:#1e293b;'
                            f'line-height:1.7;">{msg["tekst"]}</div>',
                            unsafe_allow_html=True,
                        )

                _vejl_q = st.chat_input(f"Spørg om {_valgt_vejl['titel'][:50]}… ({valgt_navn})", key="_mfkn_vejl_q")
                if _vejl_q and _tekst:
                    _historik.append({"rolle": "bruger", "tekst": _vejl_q})
                    # Byg kontekst fra vejledningen
                    _vejl_chunks = chunk_tekst(_tekst, max_tokens=800)
                    _relevante = []
                    _q_lower = _vejl_q.lower()
                    for ch in _vejl_chunks:
                        if any(t in ch.lower() for t in _q_lower.split() if len(t) >= 3):
                            _relevante.append(ch)
                    if not _relevante:
                        _relevante = _vejl_chunks[:5]
                    _relevante = _relevante[:8]
                    _kontekst = "\n---\n".join(_relevante)
                    _prompt = [
                        {"type": "text", "text": (
                            f"Du er en juridisk assistent der svarer på spørgsmål om en specifik vejledning.\n\n"
                            f"REGLER:\n"
                            f"1. Svar KUN baseret på vejledningsteksten herunder. Opfind ikke fakta.\n"
                            f"2. Citér relevant tekst i anførselstegn når du henviser til vejledningen.\n"
                            f"3. Svar på dansk. Vær præcis og konkret.\n"
                            f"4. Hvis vejledningen ikke besvarer spørgsmålet, sig det eksplicit.\n\n"
                            f"VEJLEDNING: {_valgt_vejl['titel']}\n"
                            f"UDGIVER: {_valgt_vejl.get('udgiver', '')}\n"
                        )},
                        {"type": "text", "text": f"\nVEJLEDNINGSTEKST:\n{_kontekst}\n",
                         "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": f"SPØRGSMÅL: {_vejl_q}\n\nSVAR:"},
                    ]
                    with st.spinner("Analyserer vejledningen…"):
                        try:
                            _svar = _llm(_prompt)
                        except Exception as e:
                            _svar = f"Fejl: {e}"
                    _historik.append({"rolle": "assistent", "tekst": _svar})
                    st.rerun()
                elif _vejl_q and not _tekst:
                    _historik.append({"rolle": "bruger", "tekst": _vejl_q})
                    _historik.append({"rolle": "assistent", "tekst": "Vejledningsteksten er ikke indlæst endnu — AI-chat kræver at vejledningens tekst er tilgængelig."})
                    st.rerun()

                if _historik:
                    if st.button("Ryd samtale", key="_mfkn_vejl_ryd"):
                        st.session_state[_chat_key] = []
                        st.rerun()

import streamlit as st

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

import pandas as pd
import re
import csv
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as cos_sim
from shared import (
    logo, _llm, _llm_stream, strip_html, extract_kommune, BADGE,
    format_afgørelse_tekst, render_detail_header,
    udtræk_kerneafsnit, sidebar_log_ud,
    byg_indeks_tekst, udvid_query, omformuler_opfoelgning, llm_rerank,
    byg_embeddings_indeks, hybrid_retrieval, embeddings_tilgængelige,
    valider_citationer, dansk_tokenizer, chunk_tekst, byg_fokuseret_kontekst,
    klassificer_query, highlight_query, copy_button, render_filter_chips, get_embed_error,
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


def _log_feedback(modul: str, svar_tekst: str, rating: str):
    """Log bruger-feedback (thumbs up/down) til CSV-fil for kvalitetsopfølgning."""
    import os, datetime
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


def _tilfoej_citat_advarsel(svar: str, alle_kilder: list) -> str:
    """Verificér citater i AI-svar og tilføj en kort advarsel ved hallucineret tekst."""
    try:
        suspekte = valider_citationer(svar, alle_kilder)
    except Exception:
        return svar
    if not suspekte:
        return svar
    punkter = "".join(f"<li>«{c[:140]}…»</li>" if len(c) > 140 else f"<li>«{c}»</li>" for c in suspekte[:3])
    advarsel = (
        "<div style=\"margin-top:1rem;padding:0.9rem 1.1rem;background:#fef2f2;"
        "border:1px solid #fecaca;border-radius:6px;font-size:12.5px;color:#991b1b;\">"
        "<strong>Bemærk – citatverifikation:</strong> følgende citat(er) kunne ikke genfindes "
        f"ordret i kilderne og bør dobbelttjekkes:<ul style=\"margin:0.4rem 0 0 1.1rem;padding:0;\">{punkter}</ul>"
        "</div>"
    )
    return svar + "\n\n" + advarsel

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
    # 6b. Lovliggørelse / påbud — distinkt håndhævelses-sagstype der ellers
    # forsvandt i "Andet" (~30% af Andet-bucket). Additiv; rører ikke
    # plan-/dispensation-/miljøvurderingslogikken ovenfor.
    if re.search(r"lovliggør|\bpåbud\b|påbud om|forbud mod|"
                 r"ophøre? med at anvende|standsning af", t):
        return ["Lovliggørelse/Påbud"]
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
    # Opsættende virkning er en interim-procedureafgørelse, ikke et realitetsudfald
    if "afslag på opsættende virkning" in t:            return "Ukendt"
    if "meddelelse af opsættende virkning" in t:        return "Ukendt"

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
                                "tager klagen til følge", "klagen tages til følge")):
        return "Medhold"
    for _m in re.finditer(r"medhold", conc):
        _pre = conc[max(0, _m.start() - 15):_m.start()]
        if "ikke" not in _pre and "delvist" not in _pre:
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


@st.cache_data(show_spinner="Indlæser afgørelser…", ttl=None)
def load_data(version: int = 22):  # bump version to bust cache
    import os, zipfile, glob as _glob
    csv.field_size_limit(10_000_000)

    # Repo-rod (read-only på Streamlit Cloud) og skrivbar tmp-mappe
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _tmp  = "/tmp/pkn_data"
    os.makedirs(_tmp, exist_ok=True)

    def _udpak(zip_navn: str) -> str:
        """Udpak zip fra repo til /tmp og returner stien til den udpakkede CSV."""
        zip_sti = os.path.join(_root, zip_navn)
        csv_navn = zip_navn[:-4]  # fjern .zip
        dest = os.path.join(_tmp, csv_navn)
        if not os.path.exists(dest) and os.path.exists(zip_sti):
            with zipfile.ZipFile(zip_sti) as z:
                for member in z.namelist():
                    if member.endswith(".csv"):
                        with z.open(member) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        break
        return dest if os.path.exists(dest) else ""

    def _find(navn: str) -> str:
        """Returner CSV-sti: brug repo hvis den findes, ellers udpak zip til /tmp."""
        repo_csv = os.path.join(_root, navn)
        if os.path.exists(repo_csv):
            return repo_csv
        return _udpak(navn + ".zip")

    rows = []
    seen_links: set[str] = set()

    def _indlæs(sti: str, fallback: str = "") -> None:
        if not sti:
            return
        for r in _læs_csv(sti, fallback):
            if r["Link"] not in seen_links:
                seen_links.add(r["Link"])
                rows.append(r)

    # --- primær fil ---
    _indlæs(_find("pkn_vidensbase_fuld_tekst.csv"),
            _LEGACY_RETSOMRAADE["pkn_vidensbase_fuld_tekst.csv"])

    # --- supplerende filer: alle pkn_*.csv / pkn_*.csv.zip undtagen vidensbasen ---
    navne = (
        {os.path.basename(p) for p in _glob.glob(os.path.join(_root, "pkn_*.csv"))} |
        {os.path.basename(p)[:-4] for p in _glob.glob(os.path.join(_root, "pkn_*.csv.zip"))}
    )
    for navn in sorted(navne):
        if navn == "pkn_vidensbase_fuld_tekst.csv":
            continue
        sti = _find(navn)
        if sti:
            _indlæs(sti, _LEGACY_RETSOMRAADE.get(navn, ""))

    df = pd.DataFrame(rows)
    df["Dato"]        = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"]          = df["Dato"].dt.year.astype("Int64")
    df["Retsomraade"] = df["Retsomraade"].fillna("").astype(str)

    # Patch: sager der optræder i landzone-CSV'en tagges som Landzone
    _lz_sti = _find("pkn_planloven_landzone.csv")
    if _lz_sti:
        with open(_lz_sti, newline="", encoding="utf-8") as _f:
            _lz_links = {r["Link"] for r in csv.DictReader(_f)}
        _lz_mask = df["Link"].isin(_lz_links)
        df.loc[_lz_mask, "Retsomraade"] = "Planloven, landzone (efter 1. februar 2017)"

    df["Kategori"]        = df.apply(
        lambda r: ["Landzone"] if "landzone" in r["Retsomraade"].lower() else kategoriser(r["Titel"]),
        axis=1,
    )
    df["Kategori_primær"] = df["Kategori"].apply(lambda x: x[0])
    df["Plantype"]        = df["Titel"].apply(detect_plantype)
    df["Dokumenttype"]    = df["Titel"].apply(detect_dokumenttype)
    df["Udfald"]     = df.apply(lambda r: detect_udfald(r["Titel"], r.get("Tekst", "")), axis=1)
    df["Kommune"]    = df["Titel"].apply(extract_kommune)
    df["Sagsgruppe"] = df.apply(lambda r: detect_sagsgruppe(r["Titel"], r["Tekst"]), axis=1)
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int, version: int = 4):
    """TF-IDF over titel×3 + kerneafsnit med dansk stemming.
    version 4: udtræk_kerneafsnit understøtter nu HTML-headings (PKN/MFKN-format),
    hvor v3 faldt igennem til tekst[-N:] for 100% af korpus."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_data()
    texts = [byg_indeks_tekst(t, tx) for t, tx in zip(df2["Titel"].astype(str), df2["Tekst"].astype(str))]
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2),
                          min_df=2, sublinear_tf=True, tokenizer=dansk_tokenizer,
                          token_pattern=None)
    mat = vec.fit_transform(texts)
    return vec, mat


@st.cache_resource(show_spinner=False)
def build_embeddings(n_rows: int, version: int = 1):
    """Persistent semantisk indeks (Voyage/OpenAI embeddings) med disk-cache.
    Returnerer None hvis ingen embedding-API-nøgle er konfigureret."""
    if not embeddings_tilgængelige():
        return None
    df2 = load_data()
    return byg_embeddings_indeks(df2, cache_key="pkn")


def tfidf_søg(query: str, df, vec, mat, sub_idx=None, top_n: int = 30, ekspander: bool = False):
    """TF-IDF søgning med valgfri query expansion og tids-decay boost.
    tids-decay: nyere afgørelser får et lille boost (op til +15% for 2024+)."""
    from sklearn.metrics.pairwise import cosine_similarity
    effektiv_query = udvid_query(query) if ekspander else query
    qv = vec.transform([effektiv_query])

    def _boost(global_idx, base):
        try:
            aar = int(df.at[global_idx, "År"])
            # Lineær decay fra 2017 (1.00) til 2024+ (1.15)
            decay = 1.0 + max(0, min(0.15, (aar - 2017) * 0.02))
            return float(base) * decay
        except Exception:
            return float(base)

    if sub_idx is not None:
        scores_sub = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local  = scores_sub.argsort()[-top_n * 2:][::-1]
        kandidater = [(sub_idx[i], scores_sub[i]) for i in top_local if scores_sub[i] > 0.01]
        kandidater = [(g, _boost(g, s)) for g, s in kandidater]
        kandidater.sort(key=lambda x: x[1], reverse=True)
        kandidater = kandidater[:top_n]
        if not kandidater:
            return df.iloc[0:0].copy()
        top_global = [g for g, _ in kandidater]
        result     = df.loc[top_global].copy()
        result["_score"] = [s for _, s in kandidater]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top    = scores.argsort()[-top_n * 2:][::-1]
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


_udtræk_kerneafsnit = udtræk_kerneafsnit  # alias til shared.py


def smart_retrieval(spørgsmål: str, df, vec, mat, ai_sub_idx, historik,
                    top_retrieve: int = 40, top_final: int = 8, embeds=None,
                    filter_options=None) -> tuple:
    """Forbedret RAG-pipeline med auto-filtering + hybrid search + adaptiv retrieval:
    (classify ∥ rewrite ∥ auto-filter) → expand → pre-filter → retrieval → rerank → merge.

    auto-filter: Haiku analyserer spørgsmålet og foreslår filtre (fx Plantype: Kommuneplan)
    der indsnævrer korpus, så retrieval fokuserer på de mest relevante afgørelser.
    Falder tilbage til ren TF-IDF hvis embeds er None."""
    from concurrent.futures import ThreadPoolExecutor

    # 0. Parallelisér klassificering, rewriting og auto-filtrering
    n_workers = 3 if filter_options else 2
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        fut_classify = pool.submit(klassificer_query, spørgsmål)
        fut_rewrite = pool.submit(omformuler_opfoelgning, spørgsmål, historik or [])
        fut_autofilter = pool.submit(auto_filter_query, spørgsmål, filter_options) if filter_options else None
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

    # Apply auto-detected filters to narrow corpus
    effective_sub, prefiltered = apply_auto_filters(df, ai_sub_idx, auto_filters)
    st.session_state["_pkn_last_auto_filters"] = {
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
        return tfidf_søg(tfidf_query, df, vec, mat, sub_idx=sub,
                         top_n=top_retrieve, ekspander=False)

    hits = _do_retrieval(effective_sub)
    kandidater = hits.to_dict("records") if len(hits) > 0 else []
    rerankede = llm_rerank(standalone, kandidater, top_n=top_final)

    # Fallback: if auto-filter was too aggressive, retry on full filtered set
    if len(rerankede) < 3 and prefiltered:
        hits = _do_retrieval(ai_sub_idx)
        kandidater = hits.to_dict("records") if len(hits) > 0 else []
        rerankede = llm_rerank(standalone, kandidater, top_n=top_final)

    alle_kilder = _saml_kilder(historik or [], rerankede, max_total=max(12, top_final + 4))
    return standalone, alle_kilder


def _byg_pkn_prompt(spørgsmål: str, docs: list, historik: list = None) -> list:
    """Byg prompt-blokke til PKN AI-svar (bruges af både streaming og blokerende)."""
    kontekst = byg_fokuseret_kontekst(spørgsmål, docs, max_chunks_per_doc=3)
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel'][:80]}"
        for i, d in enumerate(docs)
    )
    return [
        {
            "type": "text",
            "text": (
                f"Du er en juridisk assistent specialiseret i dansk planlovgivning og Planklagenævnets (PKN) praksis. "
                f"Dine brugere er professionelle jurister der kender lovgivningen – giv præcise, faktabaserede svar.\n\n"
                f"REGLER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte afgørelser. Opfind ikke fakta.\n"
                f"2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG kommunenavne eller datoer som reference.\n"
                f"3. Svar på dansk. Strukturér med overskrifter og afsnit.\n"
                f"4. Understøt juridiske påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                f"Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
                f"5. Identificér mønstre på tværs af afgørelserne: er der en fast praksis, eller varierer udfaldet? "
                f"Angiv evt. fordelingen (fx \"3 af 5 afgørelser giver medhold\").\n"
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
            "text": f"{samtale_blok}SPØRGSMÅL: {spørgsmål}\n\nSVAR:",
        },
    ]


def claude_svar(spørgsmål: str, docs: list, historik: list = None) -> str:
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    blocks = _byg_pkn_prompt(spørgsmål, docs, historik)
    return _llm(blocks)


def claude_svar_stream(spørgsmål: str, docs: list, historik: list = None, placeholder=None) -> str:
    """Streaming-version: viser svaret ord-for-ord i placeholderen."""
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    blocks = _byg_pkn_prompt(spørgsmål, docs, historik)
    return _llm_stream(blocks, placeholder=placeholder)


def claude_resumé(titel: str, tekst: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Ingen API-nøgle."
    kerneafsnit = _udtræk_kerneafsnit(tekst, max_tegn=6000)
    prompt = f"""Lav et kort, struktureret resumé af denne PKN-afgørelse på dansk.
Inkluder: Sagens kerne, Klagenævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {kerneafsnit}

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
init_sagsmapper()

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_data()
vec, mat = build_index(len(df))
embeds   = build_embeddings(len(df))
# Bust cache hvis nøgle blev tilføjet efter første kørsel
if embeds is None and embeddings_tilgængelige():
    build_embeddings.clear()
    embeds = build_embeddings(len(df))


# Auto-filter options for AI retrieval
_pkn_filter_options = {
    "Kategori": sorted({k for kats in df["Kategori"] for k in kats}),
    "Plantype": ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"],
    "Dokumenttype": ["Screeningsafgørelse", "Miljørapport"],
    "Sagsgruppe": ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"],
}

# Diagnostik: vis hvad der sker med embeddings (kun synlig for debug)
_voyage_key_sat = bool(st.secrets.get("VOYAGE_API_KEY", "") or st.secrets.get("OPENAI_API_KEY", ""))
_embeds_ok = embeds is not None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(150, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<span class="h-filter-label">Søgeord</span>', unsafe_allow_html=True)
    if st.session_state.get("_pkn_clear_soeg"):
        st.session_state.pop("pkn_soeg", None)
        st.session_state.pop("_pkn_clear_soeg", None)
    søg_input = st.text_input("", placeholder="f.eks. planlovens § 15 a, terrasse, lokalplan…", label_visibility="collapsed", key="pkn_soeg")
    søge_type = st.radio("", ["Ordret", "Intelligent"], horizontal=True, label_visibility="collapsed", key="søge_type")
    st.markdown('<span style="font-size:10.5px;color:#64748b;line-height:1.4;display:block;margin-top:-6px;">'
                'Ordret = nøjagtig tekstmatch &nbsp;·&nbsp; Intelligent = AI finder relevante sager</span>',
                unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Kategori</span>', unsafe_allow_html=True)
    _alle_kats  = sorted({k for kats in df["Kategori"] for k in kats})
    valgte_kats = st.multiselect("", _alle_kats, label_visibility="collapsed", key="kat")
    _isoler_relevant = bool(valgte_kats and set(valgte_kats) & {"Planvedtagelse", "Miljøvurderingsloven"})
    isoler_kat  = st.checkbox("Kun sager der udelukkende handler om valgte", key="iso_kat", help="Ekskluderer sager som også berører andre kategorier") if _isoler_relevant else False

    _mvu_valgt = "Miljøvurderingsloven" in (valgte_kats or [])
    if _mvu_valgt:
        st.markdown('<span class="h-filter-label">Dokumenttype</span>', unsafe_allow_html=True)
        dokumenttype_valg = st.multiselect("", ["Screeningsafgørelse", "Miljørapport"], label_visibility="collapsed", key="dt")
    else:
        dokumenttype_valg = []

    st.markdown('<span class="h-filter-label">Plantype</span>', unsafe_allow_html=True)
    plantype_valg = st.multiselect("", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Andet"], label_visibility="collapsed", key="pt")
    isoler_pt     = st.checkbox("Kun sager der udelukkende handler om valgte", key="iso_pt", help="Ekskluderer sager som også berører andre plantyper") if plantype_valg else False

    st.markdown('<span class="h-filter-label">Årsinterval</span>', unsafe_allow_html=True)
    _aar_max_raw = df["År"].max()
    år_min, år_max   = 2017, (int(_aar_max_raw) if pd.notna(_aar_max_raw) else 2026)
    if år_max < år_min:
        år_max = 2026
    år_range         = st.slider("", år_min, år_max, (år_min, år_max), label_visibility="collapsed", key="pkn_aar")

    with st.expander("Flere filtre"):
        st.markdown('<span class="h-filter-label">Sagsgruppe</span>', unsafe_allow_html=True)
        sagsgruppe_valg = st.multiselect("", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"], label_visibility="collapsed", key="sg")

        st.markdown('<span class="h-filter-label">Udfald</span>', unsafe_allow_html=True)
        udfald_valg    = st.multiselect("", ["Medhold", "Ikke medhold", "Ophævet", "Afvist", "Ukendt"], label_visibility="collapsed", key="ud")

    st.markdown("---")
    st.markdown(f"<span style='font-size:12px;color:#cbd5e1;font-weight:500;'>**{len(df):,}** afgørelser &nbsp;·&nbsp; 2017–{år_max}</span>", unsafe_allow_html=True)
    st.markdown(f"<span style='font-size:11px;color:#94a3b8;'>Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>", unsafe_allow_html=True)

    # Nulstil filtre
    _har_filtre = bool(valgte_kats or dokumenttype_valg or plantype_valg or sagsgruppe_valg
                       or udfald_valg or søg_input.strip() or år_range != (år_min, år_max))
    if _har_filtre:
        if st.button("Nulstil filtre", use_container_width=True, key="_pkn_reset"):
            for k in ["kat", "iso_kat", "dt", "pt", "iso_pt", "sg", "ud", "søge_type", "pkn_aar"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state["_pkn_clear_soeg"] = True
            st.rerun()


mask = df["År"].isna() | ((df["År"] >= år_range[0]) & (df["År"] <= år_range[1]))
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

if søg_input.strip() and søge_type == "Intelligent":
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
    sidebar_log_ud()


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header">
  <h1 class="h-page-title">Planklagenævnet</h1>
  <p class="h-page-meta">
    Afgørelsesdatabase &nbsp;·&nbsp; {len(df):,} afgørelser &nbsp;·&nbsp; {int(df['År'].min())}–{int(df['År'].max())}
  </p>
</div>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – AFGØRELSER
# ════════════════════════════════════════════════════════════════════════════
tab_søg, tab_stat, tab_ai, tab_vejl = st.tabs(["  Afgørelser  ", "  Statistik  ", "  AI Assistent  ", "  Vejledninger  "])

with tab_søg:

    # Navigation fra sagsmappe
    _nav = st.session_state.pop("_navigate_to_decision", None)
    if _nav and _nav.get("kilde") == "pkn":
        _match = df[df["Link"] == _nav["link"]]
        if not _match.empty:
            st.session_state.valgt_afgørelse = _match.iloc[0].to_dict()

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

        # ── Gem i sagsmappe ─────────────────────────────────────────────────
        _gemte = hent_alle_gemte_links()
        _er_gemt = row["Link"] in _gemte
        _save_c1, _save_c2 = st.columns([2, 6])
        with _save_c1:
            if _er_gemt:
                _mid_d = find_mappe_for_link(row["Link"])
                _mname_d = st.session_state["sagsmapper"]["mapper"].get(_mid_d, {}).get("navn", "")
                with st.popover(f"★ Gemt i {_mname_d}", use_container_width=True):
                    if st.button("Fjern fra sagsmappe", key="_pkn_detail_rm", type="primary"):
                        fjern_afgørelse(_mid_d, row["Link"])
                        st.toast("Fjernet fra sagsmappe", icon="✓")
                        st.rerun()
            else:
                _mapper_d = st.session_state["sagsmapper"]["mapper"]
                if not _mapper_d:
                    if st.button("☆ Gem i sagsmappe", key="_pkn_detail_save", use_container_width=True):
                        gem_fra_row(row, "pkn")
                        st.toast("Gemt i 'Mine afgørelser'", icon="📁")
                        st.rerun()
                else:
                    with st.popover("☆ Gem i sagsmappe", use_container_width=True):
                        st.caption("Gem i mappe:")
                        for _midd, _md in _mapper_d.items():
                            if st.button(_md["navn"], key=f"_pkn_d_sv_{_midd}", use_container_width=True):
                                gem_fra_row(row, "pkn", mappe_id=_midd)
                                st.toast(f"Gemt i '{_md['navn']}'", icon="📁")
                                st.rerun()
                        st.markdown("---")
                        _nyd = st.text_input("Ny mappe", placeholder="Mappenavn…",
                                             label_visibility="collapsed", key="_pkn_d_nm")
                        if st.button("＋ Opret og gem", key="_pkn_d_nb",
                                     use_container_width=True, type="primary"):
                            if _nyd.strip():
                                _newm = opret_mappe(_nyd.strip())
                                gem_fra_row(row, "pkn", mappe_id=_newm)
                                st.toast(f"Gemt i ny mappe '{_nyd.strip()}'", icon="📁")
                                st.rerun()

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
                        st.session_state._resumé = claude_resumé(row["Titel"], row["Tekst"])
                    except Exception as e:
                        st.session_state._resumé = f"Fejl: {e}"
            if "_resumé" in st.session_state:
                    st.markdown(
                        f'<div class="detail-ai-resume">{st.session_state._resumé}</div>',
                        unsafe_allow_html=True
                    )
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        # ── Aktive filter-chips (klikbare) ──
        _chips = []
        if søg_input.strip():
            def _clr_søg():
                # text_input har ingen session-key; vi bruger en nulstil-flag
                st.session_state["_pkn_clear_soeg"] = True
            _chips.append((f"Søgeord: {søg_input.strip()[:30]}", _clr_søg))
        for _k in valgte_kats:
            def _clr_kat(_val=_k):
                st.session_state["kat"] = [x for x in st.session_state.get("kat", []) if x != _val]
            _chips.append((f"Kat: {_k}", _clr_kat))
        for _p in plantype_valg:
            def _clr_pt(_val=_p):
                st.session_state["pt"] = [x for x in st.session_state.get("pt", []) if x != _val]
            _chips.append((f"Plantype: {_p}", _clr_pt))
        for _dt in dokumenttype_valg:
            def _clr_dt(_val=_dt):
                st.session_state["dt"] = [x for x in st.session_state.get("dt", []) if x != _val]
            _chips.append((f"Dok: {_dt}", _clr_dt))
        for _sg in sagsgruppe_valg:
            def _clr_sg(_val=_sg):
                st.session_state["sg"] = [x for x in st.session_state.get("sg", []) if x != _val]
            _chips.append((f"Gruppe: {_sg}", _clr_sg))
        for _u in udfald_valg:
            def _clr_ud(_val=_u):
                st.session_state["ud"] = [x for x in st.session_state.get("ud", []) if x != _val]
            _chips.append((f"Udfald: {_u}", _clr_ud))
        if år_range != (år_min, år_max):
            def _clr_aar():
                st.session_state.pop("pkn_aar", None)
            _chips.append((f"År: {år_range[0]}–{år_range[1]}", _clr_aar))
        if _chips:
            def _clr_all():
                for k in ["kat", "iso_kat", "dt", "pt", "iso_pt", "sg", "ud", "søge_type", "pkn_aar"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state["_pkn_clear_soeg"] = True
            _chips.append(("Ryd alle", _clr_all))
            render_filter_chips(_chips, key_prefix="pkn_chip")

        total_filtreret = len(df_filter)
        hits  = len(df_vis)
        if søg_input:
            _type_label = "intelligent" if søge_type == "Intelligent" else "ordret"
            label = f"**{hits}** resultater for \"{søg_input}\" · {_type_label} søgning (ud af {total_filtreret:,} filtrerede)"
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
                if st.button("Nulstil filtre", key="_pkn_reset_empty", use_container_width=False):
                    for k in ["kat", "iso_kat", "dt", "pt", "iso_pt", "sg", "ud", "søge_type"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()
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
            _hl_q = søg_input.strip() if søg_input.strip() else ""
            _gemte_links = hent_alle_gemte_links()
            for _, row in df_vis.head(_vis_antal).iterrows():
                badge_style = _BADGE_STYLE.get(row["Udfald"], _BADGE_DEFAULT)
                dato_str    = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                kat_str     = " / ".join(row["Kategori"]) if isinstance(row["Kategori"], list) else row["Kategori"]
                _hl_titel   = highlight_query(row["Titel"], _hl_q) if _hl_q else row["Titel"]
                _hl_excerpt = highlight_query(row["Excerpt"], _hl_q, max_len=300) if _hl_q else (row["Excerpt"] + "…")
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:.2px;">{dato_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.1px;{badge_style}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{_hl_titel}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{kat_str}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{row['Sagsgruppe']}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{_hl_excerpt}</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn afgørelse på portalen ↗</a>
  </div>
</div>""", unsafe_allow_html=True)
                _c_read, _c_save = st.columns([4, 1.2])
                with _c_read:
                    if st.button("Læs afgørelse →", key=f"btn_{row['Link'][-20:]}"):
                        st.session_state.valgt_afgørelse = row.to_dict()
                        if "_resumé" in st.session_state:
                            del st.session_state["_resumé"]
                        st.rerun()
                with _c_save:
                    _link = row["Link"]
                    _link_key = _link[-20:]
                    if _link in _gemte_links:
                        _mid = find_mappe_for_link(_link)
                        _mname = st.session_state["sagsmapper"]["mapper"].get(_mid, {}).get("navn", "")
                        with st.popover(f"★ Gemt", use_container_width=True):
                            st.caption(f"Gemt i: **{_mname}**")
                            if st.button("Fjern fra sagsmappe", key=f"rm_{_link_key}", type="primary"):
                                fjern_afgørelse(_mid, _link)
                                st.toast("Fjernet fra sagsmappe", icon="✓")
                                st.rerun()
                    else:
                        _mapper = st.session_state["sagsmapper"]["mapper"]
                        if not _mapper:
                            if st.button("☆ Gem", key=f"save_{_link_key}", use_container_width=True):
                                gem_fra_row(row.to_dict(), "pkn")
                                st.toast("Gemt i 'Mine afgørelser'", icon="📁")
                                st.rerun()
                        else:
                            with st.popover("☆ Gem", use_container_width=True):
                                st.caption("Gem i mappe:")
                                for _mid, _m in _mapper.items():
                                    if st.button(_m["navn"], key=f"sv_{_link_key}_{_mid}", use_container_width=True):
                                        gem_fra_row(row.to_dict(), "pkn", mappe_id=_mid)
                                        st.toast(f"Gemt i '{_m['navn']}'", icon="📁")
                                        st.rerun()
                                st.markdown("---")
                                _ny = st.text_input("Ny mappe", placeholder="Mappenavn…",
                                                    label_visibility="collapsed",
                                                    key=f"nm_{_link_key}")
                                if st.button("＋ Opret og gem", key=f"nb_{_link_key}",
                                             use_container_width=True, type="primary"):
                                    if _ny.strip():
                                        _new_mid = opret_mappe(_ny.strip())
                                        gem_fra_row(row.to_dict(), "pkn", mappe_id=_new_mid)
                                        st.toast(f"Gemt i ny mappe '{_ny.strip()}'", icon="📁")
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
            fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#8C1C2E"])
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
                          color_discrete_sequence=["#8C1C2E"])
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

    _søge_mode = "Hybrid (TF-IDF + semantisk)" if embeds is not None else "TF-IDF"
    st.markdown(f"""
<div class="ai-hero">
  <span class="material-symbols-rounded ai-hero-icon">smart_toy</span>
  <div>
    <div class="ai-hero-title">Spørg til PKN-praksis</div>
    <div class="ai-hero-sub">
      Søger i <strong>{antal_tekst} afgørelser{filtreret_label}</strong>
      og svarer med kildehenvisninger.
      Opfølgningsspørgsmål husker kontekst.
    </div>
    <div style="font-size:10.5px;color:#94a3b8;margin-top:4px;">Søgemetode: {_søge_mode}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    # Diagnostik: detaljer kun bag DEBUG-flag (læk ikke secret-navne til
    # slutbrugere i et juristvendt produkt).
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
        # Kontekstuelle forslagsknapper baseret på aktive filtre
        if valgte_kats and len(valgte_kats) == 1:
            _kat_ctx = valgte_kats[0].lower()
            forslag = [
                f"Hvad er PKN's praksis for {_kat_ctx}?",
                f"Hvornår giver PKN medhold i {_kat_ctx}-sager?",
                f"Hvilke hensyn vægtes ved {_kat_ctx}?",
                f"Hvornår afviser PKN klager over {_kat_ctx}?",
            ]
        elif søg_input.strip():
            _q = søg_input.strip()
            forslag = [
                f"Hvad er PKN's praksis vedrørende {_q}?",
                f"Hvornår giver PKN medhold i sager om {_q}?",
                f"Hvilke argumenter er afgørende for {_q}?",
                f"Er der en klar tendens i PKN's afgørelser om {_q}?",
            ]
        else:
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
                st.markdown(f'<div class="chat-user">{f}</div>', unsafe_allow_html=True)
                svar_placeholder = st.empty()
                with st.spinner("Søger i afgørelser…"):
                    try:
                        _, alle_kilder = smart_retrieval(
                            f, df, vec, mat, ai_sub_idx,
                            st.session_state.chat_historik, top_retrieve=40, top_final=8,
                            embeds=embeds, filter_options=_pkn_filter_options,
                        )
                    except Exception as e:
                        alle_kilder = []
                if not alle_kilder:
                    st.error("Kunne ikke hente kilder — prøv igen eller justér filtre.")
                    st.stop()
                try:
                    svar = claude_svar_stream(f, alle_kilder,
                                             historik=st.session_state.chat_historik,
                                             placeholder=svar_placeholder)
                    svar = _tilfoej_citat_advarsel(svar, alle_kilder)
                    try:
                        svar_placeholder.markdown(svar, unsafe_allow_html=True)
                    except Exception:
                        pass
                except Exception as e:
                    alle_kilder = []
                    svar = f"Fejl ved AI Assistent: {e}"
                    svar_placeholder.error(svar)
                _af_info = st.session_state.pop("_pkn_last_auto_filters", None)
                st.session_state.chat_historik.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder,
                     "auto_filters": _af_info})
                st.rerun()

        # Input-form (øverst, så bruger ikke skal scrolle)
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
            st.markdown(f'<div class="chat-user">{spørgsmål}</div>', unsafe_allow_html=True)
            svar_placeholder = st.empty()
            with st.spinner("Søger i afgørelser…"):
                try:
                    _, alle_kilder = smart_retrieval(
                        spørgsmål, df, vec, mat, ai_sub_idx,
                        st.session_state.chat_historik, top_retrieve=40, top_final=8,
                        embeds=embeds, filter_options=_pkn_filter_options,
                    )
                except Exception as e:
                    alle_kilder = []
            if not alle_kilder:
                st.error("Kunne ikke hente kilder — prøv igen eller justér filtre.")
                st.stop()
            try:
                svar = claude_svar_stream(spørgsmål, alle_kilder,
                                         historik=st.session_state.chat_historik,
                                         placeholder=svar_placeholder)
                svar = _tilfoej_citat_advarsel(svar, alle_kilder)
                try:
                    svar_placeholder.markdown(svar, unsafe_allow_html=True)
                except Exception:
                    pass
            except Exception as e:
                alle_kilder = []
                svar = f"Fejl ved AI Assistent: {e}"
                svar_placeholder.error(svar)
            _af_info = st.session_state.pop("_pkn_last_auto_filters", None)
            st.session_state.chat_historik.append(
                {"rolle": "assistent", "tekst": svar, "kilder": alle_kilder,
                 "auto_filters": _af_info})
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
                    '<span style="font-size:10px;font-weight:600;color:#8C1C2E;'
                    'text-transform:uppercase;letter-spacing:0.6px;">Harald</span></div>',
                    unsafe_allow_html=True,
                )
                # Auto-filter badge (vis hvilke filtre AI'en selv lagde på)
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
                # Erstat [Kilde X] i AI-teksten med blå navne-chips
                kilder = msg.get("kilder", [])
                if kilder:
                    vist_tekst, ref_kilder = erstat_kilde_refs(msg["tekst"], kilder)
                else:
                    vist_tekst, ref_kilder = msg["tekst"], []

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    st.markdown(f'<div class="chat-assistant">{vist_tekst}</div>', unsafe_allow_html=True)
                    # Feedback + copy knapper
                    fb_key = f"fb_{msg_idx}"
                    fb_state = st.session_state.get(fb_key)
                    fb1, fb2, fb3 = st.columns([1, 1, 2])
                    with fb1:
                        if st.button("👍" if fb_state != "up" else "✅",
                                     key=f"{fb_key}_up", disabled=fb_state is not None,
                                     help="Godt svar"):
                            st.session_state[fb_key] = "up"
                            _log_feedback("pkn", msg.get("tekst", "")[:200], "up")
                            st.rerun()
                    with fb2:
                        if st.button("👎" if fb_state != "down" else "❌",
                                     key=f"{fb_key}_down", disabled=fb_state is not None,
                                     help="Dårligt svar"):
                            st.session_state[fb_key] = "down"
                            _log_feedback("pkn", msg.get("tekst", "")[:200], "down")
                            st.rerun()
                    with fb3:
                        # Strip HTML-tags for ren tekst til clipboard
                        _ren_tekst = strip_html(msg.get("tekst", ""))
                        copy_button(_ren_tekst, label="Kopiér svar", key=f"cp_{msg_idx}")
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

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 – PLANLOVEN
# ════════════════════════════════════════════════════════════════════════════

_PLANLOVEN_TEKST = """Kapitel 1
Formål
§ 1. Loven skal sikre en sammenhængende planlægning, der forener de samfundsmæssige interesser i arealanvendelsen, medvirker til at værne om landets natur og miljø samt klima og skaber gode rammer for vækst og udvikling i hele landet, så samfundsudviklingen kan ske på et bæredygtigt grundlag med respekt for menneskets livsvilkår, bevarelse af dyre- og planteliv og øget økonomisk velstand.
Stk. 2. Loven tilsigter særlig,
1) at der ud fra en planmæssig og samfundsøkonomisk helhedsvurdering sker en hensigtsmæssig udvikling i hele landet og i de enkelte kommuner og lokalsamfund,
2) at der skabes og bevares værdifulde bebyggelser, bymiljøer og landskaber,
3) at skabe gode rammer for erhvervsudvikling og vækst,
4) at de åbne kyster fortsat skal udgøre en væsentlig naturværdi og landskabelig værdi,
5) at biodiversiteten understøttes, og at udledning af drivhusgasser, forurening af luft, vand og jord samt støjulemper forebygges,
6) at offentligheden i videst muligt omfang inddrages i planlægningsarbejdet, og
7) at alsidighed i boligsammensætningen fremmes gennem mulighed for planlægning for almene boliger i byerne.
Kapitel 2
Landsplanlægning
§ 2. Ministeren for byer og landdistrikter er ansvarlig for den sammenfattende fysiske landsplanlægning og for, at der foretages de undersøgelser, som er nødvendige herfor.
§ 2 a. Ministeren for byer og landdistrikter offentliggør hvert fjerde år en oversigt over nationale interesser i kommuneplanlægningen, herunder de interesser, der er fastlagt i medfør af denne lov og lovgivningen i øvrigt. Offentliggørelse kan ske udelukkende digitalt.
§ 3. Ministeren for byer og landdistrikter kan til varetagelse af landsplanmæssige interesser, herunder sikring af kvalitet i planlægningen, fastsætte regler for anvendelsen af lovens beføjelser og for indholdet af planlægningen efter loven.
Stk. 2. Ministeren for byer og landdistrikter kan tillægge regler efter stk. 1 retsvirkning som kommuneplaner. Ministeren kan endvidere i særlige tilfælde bestemme, at bygge- og anlægsarbejder, der er forudsat i en regel efter stk. 1, kan iværksættes uden kommune- og lokalplan og uden tilladelse efter § 35, stk. 1.
Stk. 3. Ministeren for byer og landdistrikter fastsætter med henblik på gennemførelse af De Europæiske Fællesskabers direktiver og beslutninger på naturbeskyttelsesområdet regler om, i hvilke tilfælde og på hvilke vilkår tilladelser efter §§ 5 u og 35 og dispensationer fra bestemmelser i en lokalplan, jf. §§ 5 u og 19, kan meddeles, samt regler om indholdet af planlægning efter loven.
Stk. 4. Ministeren for byer og landdistrikter kan i særlige tilfælde pålægge kommunalbestyrelser at bringe lovens bestemmelser i anvendelse, herunder tilvejebringe en plan med et nærmere bestemt indhold.
Stk. 5. Ministeren for byer og landdistrikter kan i særlige tilfælde beslutte at overtage kommunalbestyrelsers beføjelser efter loven i sager, der berører andre myndigheders lovbestemte opgaver eller har større betydning.
§ 3 a. (Ophævet)
§ 4. I forbindelse med forsøg, der tilsigter at fremme lovens formål, kan ministeren for byer og landdistrikter yde økonomisk støtte og fritage kommunalbestyrelser for at overholde lovens regler.
Stk. 2. Når et forsøg, der indebærer en fravigelse fra lovens regler, er godkendt, bekendtgøres der i Lovtidende en meddelelse herom. I meddelelsen gives der oplysning om, hvor borgerne kan gøre sig bekendt med forsøgstilladelsen.
§ 4 a. Ministeren for byer og landdistrikter kan efter ansøgning fra kommunalbestyrelser meddele mellem 0 og 15 tilladelser til planlægning og meddelelse af landzonetilladelser til innovative og miljømæssigt bæredygtige turismeprojekter uanset § 5 b, stk. 1, nr. 1, 3 og 4, og § 35, stk. 3.
§ 5. Ministeren for byer og landdistrikter kan efter ansøgning fra kommunalbestyrelser meddele op til ti tilladelser til planlægning af og til meddelelse af landzonetilladelser til konkrete fysiske projekter uanset § 5 b, stk. 1, nr. 1 og 4, og § 35, stk. 3.
Kapitel 2 a
Planlægning i kystområderne
§ 5 a. Kystnærhedszonen uden for udviklingsområder, jf. § 5 b, stk. 2, skal søges friholdt for bebyggelse og anlæg, som ikke er afhængige af kystnærhed.
Stk. 2. Ministeren for byer og landdistrikter skal følge udviklingen og anvende beføjelserne i §§ 3, 29 og 59 til at sikre, at nationale planlægningsinteresser i kystområderne varetages efter denne lov.
Stk. 3. Kystnærhedszonen, der omfatter landzonerne og sommerhusområderne i kystområderne, fremgår af kortbilaget til loven. I kystnærhedszonen gælder bestemmelserne i § 5 b, § 11 a, stk. 1, nr. 21, § 11 e, stk. 1, nr. 11, og stk. 2, § 11 f, § 16, stk. 4, § 29 og § 35, stk. 3.
§ 5 b. For planlægningen i kystnærhedszonen gælder,
1) at der kun må inddrages nye arealer i byzone og planlægges for anlæg i landzone, såfremt der er en særlig planlægningsmæssig eller funktionel begrundelse for kystnær lokalisering,
2) at der bortset fra trafikhavneanlæg og andre overordnede infrastrukturanlæg kun i ganske særlige tilfælde kan planlægges for bebyggelse og anlæg på land, som forudsætter inddragelse af arealer på søterritoriet eller særlig kystbeskyttelse,
3) at nye sommerhusområder ikke må udlægges, og at eksisterende sommerhusområder skal fastholdes til ferieformål,
4) at ferie- og fritidsanlæg skal lokaliseres efter sammenhængende turistpolitiske overvejelser og kun i forbindelse med eksisterende bysamfund eller større ferie- og fritidsbebyggelser, og
5) at offentlighedens adgang til kysten skal sikres og udbygges.
§ 5 c. Kommuneplanlægningen skal under hensyn til lokale forhold indeholde en strategisk planlægning, der sammenhængende tager stilling til muligheder for udvikling af landsbyer, jf. § 5 d.
§ 5 d. Kommuneplanlægningen for landsbyer skal
1) understøtte en udvikling af levedygtige lokalsamfund i landsbyer,
2) fremme en differentieret og målrettet udvikling af landsbyer og
3) angive overordnede målsætninger og virkemidler for udviklingen af landsbyer.
§ 5 e. Kommuneplanlægningen skal under hensyn til lokale forhold indeholde en helhedsorienteret, strategisk planlægning for bymidter i mindre og mellemstore byer.
§ 5 f. Den strategiske planlægning for bymidter skal
1) understøtte en udvikling af levende bymidter i kommunens mindre og mellemstore byer,
2) udarbejdes i dialog med byens private og civile aktører,
3) angive overordnede målsætninger og virkemidler for udviklingen af bymidterne og
4) tage stilling til placering af offentlige funktioner og bevaring af kulturmiljøer og bygninger i bymidterne.
§ 5 g. (Ophævet)
Kapitel 2 c
Planlægning i hovedstadsområdet
§ 5 h. Hovedstadsområdet omfatter i denne lov kommunerne i Region Hovedstaden, bortset fra Bornholms Regionskommune, samt Greve, Køge, Lejre, Roskilde, Solrød og Stevns kommuner.
§ 5 i. Kommuneplanlægningen i hovedstadsområdet skal udføres på grundlag af en vurdering af udviklingen i området som helhed og sikre, at hovedprincipperne i den overordnede fingerbystruktur videreføres.
§ 5 j. Kommuneplanlægningen i hovedstadsområdet skal sikre,
1) at byudvikling og byomdannelse i det indre storbyområde sker inden for eksisterende byzone og med hensyntagen til mulighederne for at styrke den kollektive trafikbetjening,
2) at byudvikling og nye byfunktioner i det ydre storbyområde (fingerbyen) placeres under hensyntagen til den eksisterende og besluttede infrastruktur og til mulighederne for at styrke den kollektive trafik,
3) at de grønne kiler ikke inddrages til byzone eller anvendes til bymæssige fritidsanlæg og
4) at byudvikling i det øvrige hovedstadsområde er af lokal karakter og sker i tilknytning til kommunecentre eller som afrunding af andre bysamfund.
Kapitel 2 d
Planlægning til butiksformål
§ 5 l. Planlægningen skal
1) fremme et varieret butiksudbud i mindre og mellemstore byer samt i de enkelte bydele i de større byer,
2) sikre, at arealer til butiksformål udlægges, hvor der er god tilgængelighed for alle trafikarter, og så transportafstandene i forbindelse med indkøb er begrænsede, og
3) skabe gode rammer for velfungerende markeder med en effektiv butiksstruktur.
§ 5 m. Arealer til butiksformål skal udlægges i den centrale del af en by (bymidten). I byer med 20.000 indbyggere og derover kan der udlægges arealer til butiksformål i den centrale del af en bydel (bydelscenter).
§ 5 n. Ud over bymidter og bydelscentre kan der
1) udlægges arealer til aflastningsområder i byer, hvor der er et tilstrækkeligt kundegrundlag,
2) udlægges arealer til butiksformål i et lokalcenter eller placeres enkeltstående butikker, som alene tjener til lokalområdets daglige forsyning,
3) udlægges arealer til butikker, der alene forhandler særlig pladskrævende varer, og
4) udlægges arealer til mindre butikker til salg af egne produkter i tilknytning til en virksomheds produktionslokaler.
§ 5 o. I tilknytning til tankstationer, togstationer, lufthavne, stadioner, fritliggende turistattraktioner og lign. kan der udlægges arealer til butikker til brug for de kunder, der i øvrigt benytter anlægget.
§ 5 p. I byer med mere end 20.000 indbyggere fastsætter kommunalbestyrelsen det maksimale bruttoetageareal til butiksformål for det enkelte bydelscenter.
Stk. 2. I et lokalcenter må bruttoetagearealet til butiksformål ikke overstige 3.000 m2.
§ 5 q. For dagligvarebutikker i bymidter og bydelscentre må der ikke fastsættes butiksstørrelser, der overstiger 5.000 m2 bruttoetageareal.
Stk. 2. For dagligvarebutikker i lokalcentre og for enkeltstående dagligvarebutikker til lokalområdets forsyning må der ikke fastsættes butiksstørrelser, der overstiger 1.200 m2 bruttoetageareal.
Stk. 3. For dagligvarebutikker i aflastningsområder må der ikke fastsættes butiksstørrelser, der overstiger 3.900 m2 bruttoetageareal.
§ 5 r. Nye butikker, der etableres på baggrund af lokalplaner offentliggjort før den 1. juli 2007, og hvor der i lokalplanen ikke er angivet butiksstørrelser, må for dagligvarebutikker ikke overstige de i § 5 q nævnte bruttoetagearealer.
§ 5 s. Ministeren for byer og landdistrikter afgiver hvert fjerde år en redegørelse til et af Folketinget nedsat udvalg om udviklingen i kommune- og lokalplanlægningen for detailhandelsstrukturen.
§ 5 t. Beregning af bruttoetagearealet til butiksformål sker efter bygningsreglementets bestemmelser om beregning af bebyggelsens etageareal.
Kapitel 2 e
Midlertidige opholdssteder til flygtninge
§ 5 u. For arealer i byzone og landzone kan kommunalbestyrelsen meddele dispensation fra bestemmelser i en lokalplan til ændret anvendelse af eksisterende bebyggelse og til bygge- eller anlægsarbejder med henblik på etablering af midlertidige opholdssteder til nyankomne flygtninge, jf. integrationslovens § 12, stk. 1.
Kapitel 4
Kommuneplanlægning
§ 11. For hver kommune skal der foreligge en kommuneplan. Kommuneplanen skal omfatte en periode på 12 år.
Stk. 2. Kommuneplanen fastlægger på grundlag af en samlet vurdering af udviklingen i kommunen
1) en hovedstruktur, som angiver de overordnede mål for udviklingen og arealanvendelsen i kommunen,
2) retningslinjer for arealanvendelsen m.v., jf. § 11 a, stk. 1, og
3) rammer for lokalplanernes indhold for de enkelte dele af kommunen, jf. § 11 b.
§ 11 a. Kommuneplanen skal indeholde retningslinjer for
1) udlægning af arealer til byzoner og sommerhusområder,
2) beliggenheden af områder til forskellige byformål,
3) den kommunale detailhandelsstruktur,
4) beliggenheden af trafikanlæg,
5) beliggenheden af tekniske anlæg,
6) beliggenheden af områder til virksomheder med særlige beliggenhedskrav,
7) sikring af, at støjbelastede arealer ikke udlægges til støjfølsom anvendelse,
8) sikring af, at arealer, der er belastet af lugt, støv og anden luftforurening, ikke udlægges til boliger m.v.,
9) beliggenheden af arealer til fritidsformål,
10) varetagelsen af de jordbrugsmæssige interesser,
11) beliggenheden af arealer til lokalisering af driftsbygninger og driftsanlæg på store husdyrbrug,
12) beliggenheden af skovrejsningsområder og områder, hvor skovtilplantning er uønsket,
13) lavbundsarealer, herunder beliggenheden af lavbundsarealer, der kan genoprettes som vådområder,
14) varetagelse af naturbeskyttelsesinteresserne og for prioritering af kommunalbestyrelsens naturindsats inden for Grønt Danmarkskort,
15) sikring af kulturhistoriske bevaringsværdier,
16) sikring af landskabelige bevaringsværdier,
17) sikring af geologiske bevaringsværdier,
18) udpegning af områder, der kan blive udsat for oversvømmelse eller erosion,
19) friholdelse af arealer for ny bebyggelse, når arealet er i væsentlig risiko for oversvømmelse,
20) anvendelsen af vandløb, søer og kystvande,
21) arealanvendelsen i kystnærhedszonen,
22) realisering af regler eller beslutninger efter lovens §§ 3 og 5 j,
23) udviklingen af landsbyer,
24) beliggenheden af omdannelseslandsbyer,
25) udviklingen af bymidter,
26) beliggenheden af erhvervsområder, herunder erhvervshavne, som skal være forbeholdt produktionsvirksomheder,
27) beliggenheden af konsekvensområder omkring erhvervsområder,
28) udpegning af op til to transformationsområder hvert fjerde år inden for konsekvensområder, og
29) udpegning af op til to lugtbelastede arealer hvert fjerde år inden for konsekvensområder.
§ 11 b. Rammer for indholdet af lokalplaner fastsættes for de enkelte dele af kommunen.
§ 11 c. Kommunalbestyrelsen skal tilvejebringe rammer for indholdet af lokalplaner, som sikrer, at der er udlagt bynære arealer til kolonihaver.
§ 11 d. Et byomdannelsesområde skal afgrænses således, at det kun omfatter et område, hvor anvendelsen til miljøbelastende erhvervsformål, havneformål eller lignende aktiviteter i den langt overvejende del af området er ophørt eller under afvikling.
§ 11 e. Kommuneplanen skal ledsages af en redegørelse for planens forudsætninger.
§ 11 f. Kommunalbestyrelsen skal ved revision af kommuneplanen foretage de nødvendige ændringer af planen i overensstemmelse med bestemmelserne i § 5 a, stk. 1, og § 5 b.
§ 12. Kommunalbestyrelsen skal virke for kommuneplanens gennemførelse, herunder ved udøvelse af beføjelser i medfør af lovgivningen.
Stk. 2. Inden for byzoner kan kommunalbestyrelsen modsætte sig udstykning og bebyggelse, som er i strid med kommuneplanens rækkefølgebestemmelser.
Stk. 3. Inden for byzoner og sommerhusområder kan kommunalbestyrelsen modsætte sig opførelse af bebyggelse eller ændret anvendelse af bebyggelse eller ubebyggede arealer, når bebyggelsen eller anvendelsen er i strid med bestemmelser i kommuneplanens rammedel.
Kapitel 5
Lokalplanlægning
§ 13. Kommunalbestyrelsen kan tilvejebringe lokalplaner efter reglerne i kapitel 6. En lokalplan må ikke stride mod kommuneplanen.
Stk. 2. En lokalplan skal tilvejebringes, før der gennemføres større udstykninger eller større bygge- eller anlægsarbejder, herunder nedrivninger af bebyggelse, og i øvrigt når det er nødvendigt for at sikre kommuneplanens virkeliggørelse.
§ 14. Kommunalbestyrelsen kan nedlægge forbud mod, at der retligt eller faktisk etableres forhold, som kan hindres ved en lokalplan. Forbuddet kan højst nedlægges for et år.
§ 15. En lokalplan skal indeholde oplysninger om planens formål og retsvirkninger.
Stk. 2. I en lokalplan kan der optages bestemmelser om:
1) overførsel til byzone eller sommerhusområde af arealer, som planen omfatter,
2) områdets anvendelse,
3) ejendommes størrelse og afgrænsning,
4) vej- og stiforhold og andre forhold af færdselsmæssig betydning,
5) beliggenhed af spor- og ledningsanlæg,
6) bebyggelsers beliggenhed på grundene,
7) bebyggelsers omfang og udformning,
8) anvendelse af de enkelte bygninger,
9) beliggenhed af bygninger til religiøse formål,
10) parkeringsforhold,
11) krav om, at op til 25 pct. af boligmassen skal være almene boliger,
12) udformning, anvendelse og vedligeholdelse af ubebyggede arealer,
13) bevaring af landskabstræk,
14) tilvejebringelse af fællesanlæg,
21) bevaring af eksisterende bebyggelse,
25) sammenlægning af lejligheder i eksisterende boligbebyggelse,
26) isolering af eksisterende boligbebyggelse mod støj, og
32) installation af anlæg til opsamling af regnvand.
§ 15 a. En lokalplan må kun udlægge støjbelastede arealer til støjfølsom anvendelse, hvis planen med bestemmelser om etablering af afskærmningsforanstaltninger m.v. kan sikre den fremtidige anvendelse mod støjgener.
§ 15 b. En lokalplan må kun udlægge arealer, der er belastet af lugt, støv eller anden luftforurening fra produktionsvirksomheder, transport- og logistikvirksomheder og husdyrbrug til boliger, institutioner, kontorer, rekreative formål m.v., hvis lokalplanen med bestemmelser om bebyggelsens højde og placering kan sikre den fremtidige anvendelse mod en sådan forurening.
§ 16. En lokalplan skal ledsages af en redegørelse for, hvorledes planen forholder sig til kommuneplanen og øvrig planlægning for området.
§ 17. Når et forslag til lokalplan er offentliggjort, må ejendomme, der er omfattet af forslaget, ikke bebygges eller i øvrigt udnyttes på en måde, der skaber risiko for en foregribelse af den endelige plans indhold.
§ 18. Når der er foretaget offentlig bekendtgørelse af en lokalplan, må der ikke retligt eller faktisk etableres forhold i strid med planens bestemmelser, medmindre dispensation meddeles efter reglerne i §§ 5 u, 19 eller 40.
§ 19. Kommunalbestyrelsen kan dispensere fra bestemmelser i en lokalplan eller en plan m.v., der er opretholdt efter § 68, stk. 2, hvis dispensationen ikke er i strid med principperne i planen, eller tidsbegrænses til maksimalt 3 år, dog 10 år for studieboliger og byhaver.
Stk. 2. Videregående afvigelser end omhandlet i stk. 1 kan kun foretages ved tilvejebringelse af en ny lokalplan.
§ 20. Dispensationer efter § 19 kan først meddeles, når der er forløbet 2 uger, efter at kommunalbestyrelsen har givet skriftlig orientering om ansøgningen til ejere og brugere i det område, der er omfattet af planen, naboerne og berørte foreninger.
§ 21. Kommunalbestyrelsen kan bemyndige en grundejerforening eller beboerforening til at meddele dispensationer som omhandlet i § 19, stk. 1.
§ 21 a. Ved lavenergibebyggelse forstås bebyggelse, der på tidspunktet for ansøgningen om byggetilladelsen opfylder de energirammer for energiforbrug for lavenergibygninger, der er fastsat i bygningsreglementet.
§ 21 b. På opfordring fra en grundejer kan kommunalbestyrelsen indgå en udbygningsaftale med grundejeren for områder, der i kommuneplanen er udlagt til byzone eller sommerhusområde.
§ 21 c. På opfordring fra en grundejer kan kommunalbestyrelsen indgå aftale med grundejeren om, at omkostningerne til udarbejdelse af kommuneplantillæg og lokalplan afholdes af grundejeren.
Kapitel 6
Planers tilvejebringelse og ophævelse
§ 22 a. Forud for ministeren for byer og landdistrikters fastsættelse af bindende regler eller retningslinjer efter § 3, stk. 1, eller § 5 j, stk. 2 og 4, skal et forslag offentliggøres og sendes til de berørte regionsråd og kommunalbestyrelser.
§ 22 b. Kommune- og lokalplaner tilvejebringes og ændres efter reglerne i dette kapitel.
§ 23 a. Kommunalbestyrelsen skal inden udgangen af den første halvdel af den kommunale valgperiode offentliggøre en strategi for kommuneplanlægningen.
§ 23 b. Når der er foretaget offentlig bekendtgørelse efter § 23 a, stk. 7, kan kommunalbestyrelsen udarbejde sådanne forslag til kommuneplan eller ændringer hertil, der er truffet beslutning om i strategien.
§ 23 c. Kommunalbestyrelsen kan tilvejebringe forslag til ændringer af kommuneplanen, der ikke er truffet beslutning om i en strategi.
§ 23 d. Kommunalbestyrelsen skal ved forslag til revision af kommuneplanen forestå en oplysningsvirksomhed med henblik på at fremkalde en offentlig debat om planrevisionens målsætning og nærmere indhold.
§ 24. Efter kommunalbestyrelsens vedtagelse af et planforslag offentliggøres dette. Kommunalbestyrelsen fastsætter en frist på mindst 8 uger for fremsættelse af indsigelser m.v. mod planforslaget.
§ 25. Samtidig med offentliggørelsen efter § 24 sendes planforslaget til ministeren for byer og landdistrikter og øvrige statslige, regionale og kommunale myndigheder.
§ 26. Samtidig med offentliggørelsen af et forslag til lokalplan skal kommunalbestyrelsen give skriftlig underretning herom til ejerne af de ejendomme, der er omfattet af forslaget.
§ 27. Efter udløbet af fristen kan kommunalbestyrelsen vedtage forslaget endeligt. Hvis der rettidigt er fremsat indsigelser mod et lokalplanforslag, kan vedtagelsen tidligst ske 4 uger efter udløbet af indsigelsesfristen.
§ 28. Et planforslag kan ikke vedtages endeligt, hvis en myndighed efter reglerne i §§ 29, 29 a, 29 b eller 29 c har modsat sig dette skriftligt over for kommunalbestyrelsen inden udløbet af fristen.
§ 29. Ministeren for byer og landdistrikter skal fremsætte indsigelse over for et forslag til kommuneplan og ændringer til en kommuneplan, der ikke er i overensstemmelse med nationale interesser.
§ 29 a. Regionsrådet kan gøre indsigelse over for forslag til kommuneplaner, hvis planforslaget er i strid med den regionale råstofplan.
§ 29 b. En kommunalbestyrelse kan fremsætte indsigelse mod en nabokommunes planforslag, hvis forslaget har væsentlig betydning for kommunens udvikling.
§ 29 c. Den berørte nationalparkfond kan fremsætte indsigelse over for et planforslag, hvis forslaget har væsentlig betydning for nationalparkens udvikling.
§ 30. Kommunalbestyrelsen foretager offentlig bekendtgørelse om den endelige vedtagelse af planen.
§ 31. Samtidig med offentliggørelsen af en lokalplan sender kommunalbestyrelsen et eksemplar af den offentliggjorte bekendtgørelse til ejere af ejendomme, der er omfattet af planen.
§ 32. Et forslag til lokalplan bortfalder, hvis det ikke er vedtaget inden 3 år efter offentliggørelsen.
§ 33. Kommunalbestyrelsen kan beslutte at ophæve byplanvedtægter og lokalplaner.
Kapitel 7
Zoneinddelingen og landzoneadministrationen
§ 34. Hele landet er opdelt i byzoner, sommerhusområder og landzoner.
§ 35. I landzoner må der ikke uden tilladelse fra kommunalbestyrelsen foretages udstykning, opføres ny bebyggelse eller ske ændring i anvendelsen af bestående bebyggelse og ubebyggede arealer.
Stk. 2. Tilladelse efter stk. 1 til udstykning, bebyggelse eller ændret anvendelse, som er omfattet af reglen om lokalplanpligt i § 13, stk. 2, kan først meddeles, når de fornødne bestemmelser i kommuneplanen er endeligt vedtaget og den fornødne lokalplan er offentligt bekendtgjort.
Stk. 3. For arealer i kystnærhedszonen uden for udviklingsområder må tilladelse efter stk. 1 kun meddeles, hvis det ansøgte har helt underordnet betydning i forhold til de nationale planlægningsinteresser i kystområderne.
Stk. 4. Tilladelser efter stk. 1 kan først meddeles, når der er forløbet 2 uger efter, at kommunalbestyrelsen har givet skriftlig orientering om ansøgningen til naboerne til den omhandlede ejendom.
§ 35 a. Kommunalbestyrelsen kan i særlige tilfælde meddele tilladelse efter § 35 til udvidelse eller ændring af eksisterende vognmandsvirksomheder, der før den 15. juni 2017 har ligget på stedet i en længere årrække.
§ 36. Tilladelse efter § 35, stk. 1, kræves ikke til:
1) Udstykning efter § 10, stk. 1 og 3, i lov om landbrugsejendomme, til samdrift med en bestående landbrugsejendom.
2) Udstykning af en skovejendom efter § 6, stk. 1, nr. 6 og 7, i lov om landbrugsejendomme.
3) Byggeri, der er erhvervsmæssigt nødvendigt for driften af den pågældende landbrugsejendom, landbrugsbedrift eller skovbrugsejendom eller for udøvelse af fiskerierhvervet.
4) Mindre byggeri, der er erhvervsmæssigt nødvendigt for driften af eksisterende dambrug på en landbrugsejendom.
5) Ibrugtagen af bebyggelse eller arealer til landbrug eller skovbrug eller til brug for udøvelse af fiskerierhvervet.
6) Udstykning, byggeri eller ændret anvendelse i det omfang, dette er påbudt i en afgørelse eller udtrykkeligt er tilladt i en lokalplan.
7) Indvinding af råstoffer i jorden.
8) Opførelse af garager, carporte, udhuse, drivhuse og lignende bygninger på højst 50 m2, når disse opføres i tilknytning til enfamiliehuse eller sommerhuse.
9) Byggeri, der i bygningsreglement er fritaget for krav om byggetilladelse, og som etableres til brug for offentlige trafik-, forsynings- eller varslingsanlæg.
10) Til- og ombygning af helårshus, hvorved husets samlede bruttoetageareal ikke overstiger 500 m2.
11) Helårsboligs overgang til anvendelse som fritidsbolig.
14) Opførelse eller indretning i eksisterende bebyggelse af en bolig på en landbrugsejendom, hvis areal overstiger 30 ha, når den nye bolig skal benyttes i forbindelse med et generationsskifte eller til en medhjælper.
18) En pensionists personlige ret til at benytte en fritidsbolig til helårsbeboelse, når pensionisten har ejet ejendommen i 1 år.
§ 37. Bygninger, der ikke længere er nødvendige for driften af en landbrugsejendom, kan uden tilladelse efter § 35, stk. 1, tages i brug til håndværks- og industrivirksomhed, mindre butikker, liberale erhverv, forenings- og fritidsformål og en bolig samt lager- og kontorformål m.v.
§ 38. Anvendelse af bygninger til den virksomhed, der er nævnt i § 37, må kun ske efter forudgående anmeldelse til kommunalbestyrelsen.
Kapitel 8
Sommerhusområder
§ 38 a. En ejendom i et sommerhusområde må ikke benyttes til anden anvendelse end boligformål.
§ 39. I sommerhusområder må der ikke uden kommunalbestyrelsens tilladelse opføres eller indrettes mere end én bolig på en selvstændigt matrikuleret ejendom.
§ 40. En bolig i et sommerhusområde må bortset fra kortvarige ferieophold m.v. ikke anvendes til overnatning i perioden fra den 1. november til udgangen af februar.
§ 41. En pensionist, der ejer en bolig i et sommerhusområde, har en personlig ret til at benytte boligen til helårsbeboelse, når pensionisten har ejet ejendommen i 1 år.
Kapitel 9
Servitutter
§ 42. En ejer af fast ejendom kan kun med forudgående samtykke fra kommunalbestyrelsen gyldigt pålægge ejendommen servitutbestemmelser om forhold, hvorom der kan optages bestemmelser i en lokalplan.
§ 43. Kommunalbestyrelsen kan ved påbud eller forbud sikre overholdelsen af servitutbestemmelser om forhold, hvorom der kan optages bestemmelser i en lokalplan.
Kapitel 10
Tilbageførsel
§ 45. Kommunalbestyrelsen kan beslutte at tilbageføre arealer fra byzone eller sommerhusområde til landzone i overensstemmelse med kommuneplanen.
§ 46. Ved tilbageførsel af privat ejede arealer til landzone efter § 45 kan der ydes erstatning for udgifter, ejeren har afholdt med henblik på ejendommens udnyttelse i byzone.
Kapitel 11
Ekspropriation, overtagelse m.v.
§ 47. Kommunalbestyrelsen kan ekspropriere fast ejendom, der tilhører private, eller private rettigheder over fast ejendom, når ekspropriationen vil være af væsentlig betydning for virkeliggørelsen af en lokalplan eller en byplanvedtægt og for varetagelsen af almene samfundsinteresser.
§ 47 a. En ejer af en fast ejendom, der benyttes til landbrug, gartneri, planteskole eller frugtplantage, kan, hvis ejendommen helt eller delvis overføres fra landzone til byzone eller sommerhusområde, inden 4 år efter overførslen forlange ejendommen overtaget af kommunen.
§ 48. Når en lokalplan eller en byplanvedtægt har forbeholdt en ejendom til et offentligt formål, kan ejeren forlange ejendommen overtaget af kommunen mod erstatning.
§ 49. Når det i en lokalplan eller en byplanvedtægt er bestemt, at en bebyggelse ikke må nedrives uden tilladelse fra kommunalbestyrelsen, og tilladelsen nægtes, kan ejeren forlange ejendommen overtaget af kommunen mod erstatning.
§ 50. Taksationsmyndighederne efter lov om offentlige veje fastsætter erstatning for ekspropriation.
Kapitel 12
Tilsyn
§ 51. Kommunalbestyrelsen påser overholdelsen af denne lov og de regler, der er fastsat med hjemmel i loven, samt af bestemmelserne i lokalplaner.
Stk. 3. Kommunalbestyrelsen skal foranledige et ulovligt forhold lovliggjort, medmindre forholdet har underordnet betydning.
§ 51 a. Kommunalbestyrelsen skal hvert år pr. 1. november påbyde enhver, som er registreret i CPR med bopæl i en bolig i et sommerhusområde, som den pågældende ikke lovligt kan anvende til helårsbeboelse, inden 14 dage at fraflytte boligen.
Kapitel 14
Klage og søgsmål
§ 58. Til Planklagenævnet kan påklages:
1) Kommunalbestyrelsens afgørelser efter § 35, stk. 1.
2) Kommunalbestyrelsens afgørelser efter § 47, stk. 1.
3) Kommunalbestyrelsens afgørelser om andre forhold, der er omfattet af denne lov og regler udstedt i medfør af loven, for så vidt angår retlige spørgsmål.
§ 59. Klageberettiget efter § 58 er ministeren for byer og landdistrikter og i øvrigt enhver med retlig interesse i sagens udfald.
Stk. 2. Klageberettiget efter § 58, stk. 1, nr. 1 og 3, er endvidere landsdækkende foreninger og organisationer, der som hovedformål har beskyttelsen af natur og miljø eller varetagelsen af væsentlige brugerinteresser inden for arealanvendelsen.
§ 60. Klage over afgørelser, der er nævnt i § 58, stk. 1, og § 58 a, skal være indgivet skriftligt, inden 4 uger efter at afgørelsen er meddelt.
§ 60 a. En tilladelse efter § 35, stk. 1, må ikke udnyttes før klagefristens udløb.
Stk. 2. Rettidig klage efter § 58, stk. 1, nr. 1 og 2, har opsættende virkning, medmindre Planklagenævnet bestemmer andet.
§ 61. Planklagenævnet kan i forbindelse med afgørelse af en klagesag se bort fra reglerne om tilladelse efter § 35, stk. 1, lokalplaner og dispensationer, når klagen vedrører en foranstaltning, der er udført.
§ 62. Søgsmål til prøvelse af afgørelser om forhold, der er omfattet af denne lov, skal være anlagt inden 6 måneder efter, at afgørelsen er meddelt.
Kapitel 15
Lovliggørelse og straf
§ 63. Det påhviler den til enhver tid værende ejer af en ejendom at berigtige et ulovligt forhold.
§ 64. Medmindre højere straf er forskyldt efter den øvrige lovgivning, straffes med bøde den, der overtræder bestemmelser i en lokalplan, overtræder § 35, stk. 1, § 39 og § 40, stk. 1, tilsidesætter vilkår for en tilladelse eller dispensation, undlader at efterkomme et påbud eller forbud, eller afgiver urigtige eller vildledende oplysninger."""


@st.cache_data(show_spinner=False)
def _parse_planloven():
    """Parser lovteksten til en liste af paragraffer med metadata."""
    paragraphs = []
    current_chapter = ""
    current_chapter_title = ""

    lines = _PLANLOVEN_TEKST.strip().split("\n")
    i = 0
    current_para = None

    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue

        # Kapitel-header
        chap_match = re.match(r"^(Kapitel \d+\w*)\s*$", line)
        if chap_match:
            current_chapter = chap_match.group(1)
            # Næste linje er kapiteltitel
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and not re.match(r"^§", lines[j].strip()):
                current_chapter_title = lines[j].strip()
                i = j + 1
            else:
                current_chapter_title = ""
                i += 1
            continue

        # Ny paragraf
        para_match = re.match(r"^(§\s*[\d]+\s*\w*)\.\s*(.*)", line)
        if para_match:
            if current_para:
                paragraphs.append(current_para)
            para_num = re.sub(r"\s+", " ", para_match.group(1)).strip()
            para_text = para_match.group(2)
            current_para = {
                "para": para_num,
                "chapter": current_chapter,
                "chapter_title": current_chapter_title,
                "text": para_text,
            }
            i += 1
            continue

        # Tilføj til nuværende paragraf
        if current_para:
            current_para["text"] += "\n" + line
        i += 1

    if current_para:
        paragraphs.append(current_para)

    return paragraphs


def _søg_planloven(query: str, paragraphs: list) -> list:
    """Søg i paragraffer — understøtter § X og fritekst."""
    q = query.strip()
    if not q:
        return paragraphs

    # Direkte §-søgning, fx "§ 35" eller "35"
    para_q = re.match(r"^§?\s*(\d+\s*\w*)\s*$", q)
    if para_q:
        nr = "§ " + para_q.group(1).strip()
        return [p for p in paragraphs if p["para"].lower() == nr.lower()]

    # Fritekst
    ql = q.lower()
    results = []
    for p in paragraphs:
        haystack = (p["para"] + " " + p["chapter"] + " " + p["chapter_title"] + " " + p["text"]).lower()
        if ql in haystack:
            results.append(p)
    return results


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 – VEJLEDNINGER
# ════════════════════════════════════════════════════════════════════════════
with tab_vejl:
    import os as _os, json as _json

    _vejl_root = _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "vejledninger")

    @st.cache_data(show_spinner=False)
    def _load_vejledninger_pkn():
        _meta = _os.path.join(_vejl_root, "pkn_vejledninger.json")
        if not _os.path.exists(_meta):
            return []
        with open(_meta, "r", encoding="utf-8") as f:
            return _json.load(f)

    _vejl_liste = _load_vejledninger_pkn()

    if not _vejl_liste:
        st.markdown(
            '<div style="text-align:center;padding:4rem 1rem;background:#f8fafc;'
            'border:1px dashed #cbd5e1;border-radius:10px;">'
            '<span class="material-symbols-rounded" style="font-size:40px;color:#94a3b8;'
            'display:block;margin-bottom:1rem;">menu_book</span>'
            '<div style="font-size:16px;font-weight:700;color:#0f172a;margin-bottom:0.5rem;">'
            'Vejledninger er under opbygning</div>'
            '<div style="font-size:13px;color:#94a3b8;line-height:1.7;max-width:440px;margin:0 auto;">'
            'Vi kortlægger og indsamler de vigtigste myndighedsvejledninger for planret. '
            'Snart kan du vælge en vejledning og stille spørgsmål direkte til indholdet.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
    else:
        # ── Vælg vejledning ──────────────────────────────────────────────
        _vejl_titler = {v["id"]: v["titel"] for v in _vejl_liste}
        _sel_col, _info_col = st.columns([3, 2])
        with _sel_col:
            st.markdown('<span class="h-filter-label" style="color:#0f172a;">Vælg vejledning</span>',
                        unsafe_allow_html=True)
            _valgt_vejl_id = st.selectbox(
                "", list(_vejl_titler.keys()),
                format_func=lambda x: _vejl_titler[x],
                label_visibility="collapsed", key="_pkn_vejl_select",
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
                    '<span class="material-symbols-rounded" style="font-size:20px;color:#0f172a;">description</span>'
                    '<span style="font-size:14px;font-weight:600;color:#0f172a;">Indhold</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                _tekst = _valgt_vejl.get("tekst") or ""
                if _tekst:
                    _vejl_søg = st.text_input("Søg i vejledningen", placeholder="Fx: dispensation, §35…",
                                              label_visibility="collapsed", key="_pkn_vejl_tsøg")
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
                    '<span class="material-symbols-rounded" style="font-size:20px;color:#0f172a;">smart_toy</span>'
                    '<span style="font-size:14px;font-weight:600;color:#0f172a;">Spørg om vejledningen</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

                _chat_key = f"pkn_vejl_chat_{_valgt_vejl_id}"
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

                _vejl_q = st.chat_input(f"Spørg om {_valgt_vejl['titel'][:50]}…", key="_pkn_vejl_q")
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
                    if st.button("Ryd samtale", key="_pkn_vejl_ryd"):
                        st.session_state[_chat_key] = []
                        st.rerun()


# ── Planloven opslagsværk (separat sektion under tabs) ─────────────────────
st.markdown("---")
with st.expander("Planloven — opslagsværk", expanded=False):
    st.markdown(
        '<p class="h-page-meta" style="margin-bottom:1rem;">Bekendtgørelse nr. 223 af 1. marts 2024</p>',
        unsafe_allow_html=True,
    )

    _paragraphs = _parse_planloven()

    # ── Søgefelt ──────────────────────────────────────────────────────────────
    col_s, col_clr = st.columns([5, 1])
    with col_s:
        lov_query = st.text_input(
            "",
            placeholder="Søg på § nummer (fx 35) eller fritekst (fx landzone, dispensation)…",
            label_visibility="collapsed",
            key="lov_søg",
        )
    with col_clr:
        if st.button("Ryd", key="lov_ryd", use_container_width=True):
            st.session_state["lov_søg"] = ""
            st.rerun()

    hits = _søg_planloven(lov_query, _paragraphs)

    # ── Resultatinfo ──────────────────────────────────────────────────────────
    if lov_query:
        st.markdown(
            f'<p style="font-size:12px;color:#94a3b8;margin-bottom:.5rem;">'
            f'{len(hits)} resultat{"er" if len(hits) != 1 else ""} for <em>"{lov_query}"</em></p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<p style="font-size:12px;color:#94a3b8;margin-bottom:.5rem;">'
            f'Planloven indeholder {len(_paragraphs)} paragraffer — søg ovenfor eller gennemse herunder.</p>',
            unsafe_allow_html=True,
        )

    if not hits:
        st.info("Ingen paragraffer matcher søgningen.")
    else:
        for p in hits:
            chap_label = f"{p['chapter']}" + (f" · {p['chapter_title']}" if p["chapter_title"] else "")
            with st.expander(f"**{p['para']}**  —  {p['text'][:80].rstrip()}{'…' if len(p['text']) > 80 else ''}"):
                st.markdown(
                    f'<div style="font-size:10px;color:#94a3b8;text-transform:uppercase;'
                    f'letter-spacing:1px;margin-bottom:.6rem;">{chap_label}</div>',
                    unsafe_allow_html=True,
                )
                # Formater teksten: Stk. X highlightes
                tekst = p["text"]
                tekst_html = re.sub(
                    r"(Stk\.\s*\d+\.)",
                    r'<span style="font-weight:700;color:#0f172a;">\1</span>',
                    tekst,
                )
                # Nummererede punkter
                tekst_html = re.sub(r"(\d+\))", r'<span style="font-weight:600;">\1</span>', tekst_html)
                tekst_html = tekst_html.replace("\n", "<br>")
                st.markdown(
                    f'<div style="font-size:14px;line-height:1.8;color:#1e293b;'
                    f'padding:10px 14px;background:#f8fafc;border-radius:6px;'
                    f'border:1px solid #e2e8f0;">{p["para"]}. {tekst_html}</div>',
                    unsafe_allow_html=True,
                )

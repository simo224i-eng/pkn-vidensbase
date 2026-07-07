import streamlit as st

if not st.session_state.get("_autentificeret_ejnar"):
    st.switch_page("app.py")
    st.stop()

import os
import re
import csv
import zipfile
import io
import glob as _glob
import pandas as pd
import numpy as np
import plotly.express as px
import requests

from shared import (
    logo, _llm, _llm_stream, strip_html, BADGE,
    render_detail_header,
    udtræk_kerneafsnit, sidebar_log_ud,
    byg_indeks_tekst, udvid_query, omformuler_opfoelgning, llm_rerank,
    byg_embeddings_indeks, hybrid_retrieval, embeddings_tilgængelige,
    valider_citationer, dansk_tokenizer, byg_fokuseret_kontekst,
    klassificer_query, highlight_query, copy_button, render_filter_chips, get_embed_error,
    auto_filter_query, apply_auto_filters,
    md_til_html, byg_lækker_afgørelse, citater_for_kilde, byg_notat_html, hent_nøgle,
    init_sagsmapper, opret_mappe, slet_mappe, omdøb_mappe,
    gem_afgørelse, fjern_afgørelse, opdater_note, find_mappe_for_link,
)


ANTHROPIC_API_KEY = hent_nøgle("ANTHROPIC_API_KEY")


# ── Mangeltype-detektion (samme liste som scrape_ejnar.py) ───────────────────
MANGELTYPER = {
    "Skimmel/fugt":         ["skimmel", "fugt", "fugtskade", "fugtindtrængning"],
    "Tag/tagdækning":       ["tag", "tagdækning", "tagsten", "undertag", "tagrende"],
    "Kloak/dræn":           ["kloak", "dræn", "afløb", "spildevand", "faldstamme"],
    "Installationer":       ["el-install", "el install", "vand-install", "varmeinstal",
                             "installationsskade", "stikledning"],
    "Fundament":            ["fundament", "sokkel", "sætningsskade"],
    "Vinduer/døre":         ["vindue", "døre", "vinduesparti"],
    "Murværk/facade":       ["murværk", "mursten", "facade", "puds"],
    "Råd/svamp/insekt":     ["råd", "trænedbrydende", "svamp", "ægte hussvamp",
                             "insektangreb", "borebille"],
    "Konstruktion/bærende": ["bjælke", "bærende konstruktion", "spær",
                             "trækonstruktion", "etageadskillelse"],
    "Badeværelse/vådrum":   ["badeværelse", "vådrum", "vådrumsmembran"],
    "Gulv":                 ["gulv", "trægulv", "klinkegulv", "parketgulv"],
}


def detect_mangeltyper(titel: str, tekst: str) -> list[str]:
    """Returnér liste af identificerede mangeltyper fra titel + tekst."""
    blob = (titel + " " + (tekst or "")[:6000]).lower()
    fundet = [label for label, ord in MANGELTYPER.items()
              if any(s in blob for s in ord)]
    return fundet or ["Andet"]


# Mønstre for husets opførelsesår i kendelsesteksten ("ejendommen er opført i 1962",
# "et parcelhus fra 1970", "byggeår: 1965" …). Måling på fuld korpus: 81 % hit-rate.
_OPFØRT_PATS = [
    re.compile(r"(?:er |var |blev )?opført (?:i |omkring |ca\.? |år )?(1[89]\d{2}|20[0-2]\d)"),
    re.compile(r"opførelsesår(?:et)?(?: er| var)?[:\s]+(1[89]\d{2}|20[0-2]\d)"),
    re.compile(r"byggeår[:\s]+(1[89]\d{2}|20[0-2]\d)"),
    re.compile(r"(?:hus|ejendom|villa|parcelhus|sommerhus)(?:et|men)? (?:er )?fra (1[89]\d{2}|20[0-2]\d)"),
]


def detect_opførelsesår(tekst: str):
    """Udtræk husets opførelsesår fra kendelsesteksten. None hvis ikke fundet."""
    blob = (tekst or "")[:15000].lower()
    for p in _OPFØRT_PATS:
        m = p.search(blob)
        if m:
            år = int(m.group(1))
            if 1800 <= år <= 2026:
                return år
    return None


def detect_udfald_ejnar(titel: str, tekst: str) -> str:
    """Klassificér AKF-kendelser. Forsøger først titel, derefter tekstkonklusion."""
    t = (titel or "").lower()
    if "afvis" in t:
        return "Afvist"
    if "delvis" in t and "medhold" in t:
        return "Delvis medhold"
    if "ikke medhold" in t or "frifind" in t:
        return "Ikke medhold"
    if "medhold" in t:
        return "Medhold"

    tx = (tekst or "").lower()
    halen = tx[-3000:]
    if any(p in halen for p in (
        "klageren får ikke medhold", "klagerens påstand tages ikke til følge",
        "selskabet frifindes", "den indklagede tilpligtes ikke",
    )):
        return "Ikke medhold"
    if any(p in halen for p in (
        "klageren får delvist medhold", "klageren får delvis medhold",
        "delvist medhold", "delvis medhold",
    )):
        return "Delvis medhold"
    if any(p in halen for p in (
        "klageren får medhold", "klagerens påstand tages til følge",
        "den indklagede tilpligtes", "selskabet skal anerkende",
        "selskabet skal betale",
    )):
        return "Medhold"
    if any(p in halen for p in (
        "klagen afvises", "afvises som åbenbart", "kan ikke realitetsbehandles",
    )):
        return "Afvist"
    return "Ukendt"


# ── Data loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser kendelser…", ttl=None)
def _læs_csv(sti: str) -> list:
    rows = []
    csv.field_size_limit(10_000_000)
    with open(sti, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tekst = strip_html(row.get("Tekst", ""), preserve_headings=True)
            excerpt = re.sub(r'^#{2,3} ', '', tekst, flags=re.M).replace('\n', ' ')
            excerpt = re.sub(r'\s+', ' ', excerpt).strip()
            mangeltype = row.get("Mangeltype", "")
            mangeltype_list = [m.strip() for m in mangeltype.split(",") if m.strip()] \
                              if mangeltype else []
            rows.append({
                "Dato":            row.get("Dato", ""),
                "Titel":           row.get("Titel", ""),
                "Link":            row.get("Link", ""),
                "Tekst":           tekst,
                "Excerpt":         excerpt[:280],
                "Sagsnummer":      row.get("Sagsnummer", ""),
                "Selskab":         row.get("Selskab", ""),
                "Udfald":          row.get("Udfald", ""),
                "Mangeltype":      mangeltype_list,
                "Forsikringstype": row.get("Forsikringstype", "Ejerskifteforsikring"),
            })
    return rows


# cache_resource (ikke cache_data): deler ÉT df-objekt i stedet for at deep-copy'e
# de ~170MB tekst ved hvert kald. df muteres aldrig in-place efter load → sikkert,
# og sparer 1-2 fulde kopier i RAM ved opstart (afgørende for Streamlit Clouds 1GB).
@st.cache_resource(show_spinner="Indlæser kendelser…")
def load_data(version: int = 1):
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _tmp = "/tmp/ejnar_data"
    os.makedirs(_tmp, exist_ok=True)
    csv.field_size_limit(10_000_000)

    def _udpak(zip_navn: str) -> str:
        zip_sti = os.path.join(_root, zip_navn)
        csv_navn = zip_navn[:-4]
        dest = os.path.join(_tmp, csv_navn)
        if not os.path.exists(dest) and os.path.exists(zip_sti):
            with zipfile.ZipFile(zip_sti) as z:
                for m in z.namelist():
                    if m.endswith(".csv"):
                        with z.open(m) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        break
        return dest if os.path.exists(dest) else ""

    def _find(navn: str) -> str:
        repo_csv = os.path.join(_root, navn)
        if os.path.exists(repo_csv):
            return repo_csv
        return _udpak(navn + ".zip")

    rows: list = []
    seen: set = set()
    navne = (
        {os.path.basename(p) for p in _glob.glob(os.path.join(_root, "ejnar_*.csv"))} |
        {os.path.basename(p)[:-4] for p in _glob.glob(os.path.join(_root, "ejnar_*.csv.zip"))}
    )
    for navn in sorted(navne):
        sti = _find(navn)
        if not sti:
            continue
        for r in _læs_csv(sti):
            if r["Link"] in seen:
                continue
            seen.add(r["Link"])
            rows.append(r)

    df = pd.DataFrame(rows)
    if df.empty:
        # Tom skelet-DataFrame så UI'en ikke crasher
        df = pd.DataFrame(columns=[
            "Dato", "Titel", "Link", "Tekst", "Excerpt", "Sagsnummer",
            "Selskab", "Udfald", "Mangeltype", "Forsikringstype", "År",
            "Opførelsesår",
        ])
        df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
        df["År"] = pd.Series(dtype="Int64")
        df["Opførelsesår"] = pd.Series(dtype="Int64")
        return df

    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"] = df["Dato"].dt.year.astype("Int64")

    # Auto-detect mangeltyper/udfald hvis CSV-felterne er tomme
    needs_mt = df["Mangeltype"].apply(lambda x: not x)
    if needs_mt.any():
        df.loc[needs_mt, "Mangeltype"] = df.loc[needs_mt].apply(
            lambda r: detect_mangeltyper(r["Titel"], r["Tekst"]), axis=1)
    needs_ud = df["Udfald"].fillna("").eq("") | df["Udfald"].eq("Ukendt")
    if needs_ud.any():
        df.loc[needs_ud, "Udfald"] = df.loc[needs_ud].apply(
            lambda r: detect_udfald_ejnar(r["Titel"], r["Tekst"]), axis=1)

    df["Selskab"] = df["Selskab"].fillna("").astype(str)
    df["Opførelsesår"] = df["Tekst"].apply(detect_opførelsesår).astype("Int64")
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int, version: int = 1):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_data()
    if df2.empty:
        return None, None
    # generator (ikke liste): undgår at materialisere en hel ekstra kopi af
    # teksten i RAM — TfidfVectorizer itererer alligevel kun én gang.
    texts = (byg_indeks_tekst(t, tx) for t, tx in
             zip(df2["Titel"].astype(str), df2["Tekst"].astype(str)))
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2),
                          min_df=2, sublinear_tf=True, tokenizer=dansk_tokenizer,
                          token_pattern=None)
    mat = vec.fit_transform(texts)
    return vec, mat


@st.cache_resource(show_spinner=False)
def build_embeddings(n_rows: int, version: int = 1):
    if not embeddings_tilgængelige():
        return None
    df2 = load_data()
    if df2.empty:
        return None
    return byg_embeddings_indeks(df2, cache_key="ejnar_ejerskifteforsikring")


def tfidf_søg(query, df, vec, mat, sub_idx=None, top_n=30, ekspander=False):
    from sklearn.metrics.pairwise import cosine_similarity
    if vec is None or mat is None:
        return df.iloc[0:0].copy()
    eff = udvid_query(query) if ekspander else query
    qv = vec.transform([eff])

    def _boost(idx, base):
        try:
            aar = int(df.at[idx, "År"])
            decay = 1.0 + max(0, min(0.15, (aar - 2017) * 0.02))
            return float(base) * decay
        except Exception:
            return float(base)

    if sub_idx is not None:
        scores = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local = scores.argsort()[-top_n * 2:][::-1]
        kand = [(sub_idx[i], scores[i]) for i in top_local if scores[i] > 0.01]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top = scores.argsort()[-top_n * 2:][::-1]
        kand = [(int(i), scores[i]) for i in top if scores[i] > 0.01]
    kand = [(g, _boost(g, s)) for g, s in kand]
    kand.sort(key=lambda x: x[1], reverse=True)
    kand = kand[:top_n]
    if not kand:
        return df.iloc[0:0].copy()
    idxs = [g for g, _ in kand]
    res = df.loc[idxs].copy() if sub_idx is not None else df.iloc[idxs].copy()
    res["_score"] = [s for _, s in kand]
    return res.reset_index(drop=True)


def _hist_kilder(historik, seen, max_n=10):
    """Kilder fra tidligere svar (nyeste først, dedup på Link). De føjes til
    kandidat-puljen FØR rerank, så rerankeren vurderer dem mod det NYE spørgsmål —
    tidligere blev de appendet efter reranken og forurenede opfølgningssvar."""
    out = []
    for msg in reversed(historik or []):
        if msg.get("rolle") == "assistent":
            for k in msg.get("kilder", []) or []:
                lnk = k.get("Link", "")
                if lnk and lnk not in seen:
                    seen.add(lnk)
                    out.append(k)
                    if len(out) >= max_n:
                        return out
    return out


def smart_retrieval(spørgsmål, df, vec, mat, ai_sub_idx, historik,
                    top_retrieve=40, top_final=8, embeds=None, filter_options=None):
    from concurrent.futures import ThreadPoolExecutor

    n_workers = 3 if filter_options else 2
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        f1 = pool.submit(klassificer_query, spørgsmål)
        f2 = pool.submit(omformuler_opfoelgning, spørgsmål, historik or [])
        f3 = pool.submit(auto_filter_query, spørgsmål, filter_options) if filter_options else None
        qtype = f1.result()
        standalone = f2.result()
        auto_filters = f3.result() if f3 else {}

    top_retrieve = qtype["top_retrieve"]
    top_final = qtype["top_final"]
    corpus_size = len(ai_sub_idx) if ai_sub_idx else len(df)
    if corpus_size > 500:
        top_retrieve, top_final = max(top_retrieve, 100), max(top_final, 15)
    elif corpus_size > 200:
        top_retrieve, top_final = max(top_retrieve, 70), max(top_final, 12)

    eff_sub, prefiltered = apply_auto_filters(df, ai_sub_idx, auto_filters)
    st.session_state["_ejnar_last_auto_filters"] = {
        "suggested": auto_filters,
        "applied": prefiltered,
        "before": len(ai_sub_idx) if ai_sub_idx else len(df),
        "after": len(eff_sub) if eff_sub else 0,
    }

    udvidet = udvid_query(standalone)
    tfidf_query = udvidet if udvidet else standalone

    def _do(sub):
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

    hits = _do(eff_sub)
    kand = hits.to_dict("records") if len(hits) > 0 else []
    seen = {r.get("Link", "") for r in kand}
    kand = kand + _hist_kilder(historik, seen)
    rerankede = llm_rerank(standalone, kand, top_n=top_final)
    if len(rerankede) < 3 and prefiltered:
        hits = _do(ai_sub_idx)
        kand = hits.to_dict("records") if len(hits) > 0 else []
        seen = {r.get("Link", "") for r in kand}
        kand = kand + _hist_kilder(historik, seen)
        rerankede = llm_rerank(standalone, kand, top_n=top_final)
    return standalone, rerankede


def _byg_prompt(spørgsmål, docs, historik=None):
    # Større kontekst-budget (60k tegn ≈ 17k tokens) + semantisk chunk-udvælgelse
    # via chunk-indekset — modellen så tidligere kun ~24k tegn valgt med ord-overlap.
    kontekst = byg_fokuseret_kontekst(
        spørgsmål, docs, max_chunks_per_doc=5, max_total_chars=60_000,
        embeds=globals().get("embeds"), link_til_idx=globals().get("_LINK_TIL_IDX"))
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
                # Holdes i sync med ejnar-web/backend/app/core/rag.py::SYSTEM_PROMPT
                "Du er Ejnar, juridisk assistent specialiseret i dansk forsikringsret og "
                "Ankenævnet for Forsikrings praksis om ejerskifteforsikring. Dine brugere "
                "er professionelle jurister og forsikringsfolk – giv præcise, faktabaserede "
                "svar i professionelt juridisk sprog. Svar på dansk, strukturér med "
                "overskrifter og afsnit.\n\n"
                "KILDER OG CITATER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte kendelser. "
                "Opfind aldrig fakta, praksis eller lovhenvisninger.\n"
                "2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG sagsnumre eller datoer som reference.\n"
                "3. Understøt centrale påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                "Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
                "4. Nævn lovhjemmel når den fremgår af kilderne (lov om forbrugerbeskyttelse ved erhvervelse "
                "af fast ejendom m.v. §§ 2 og 5, forsikringsaftaleloven, bekendtgørelsen om dækningsomfanget "
                "for ejerskifteforsikringer) – og kun da.\n\n"
                "JURIDISK METODE:\n"
                "5. Skeln skarpt mellem Medhold, Delvis medhold, Ikke medhold og Afvist – omtal aldrig "
                "delvist medhold som medhold uden forbehold. Angiv fordelingen når du generaliserer "
                "(fx \"3 af 5 kendelser giver klager medhold\").\n"
                "6. Væg nyere praksis højere end ældre: nævn kendelsernes år når du beskriver et mønster, "
                "og markér udtrykkeligt hvis mønstret hviler på ældre kendelser.\n"
                "7. Hvor det er relevant, strukturér vurderingen efter ejerskifteforsikringens kerneprøvelse: "
                "(a) forelå forholdet ved købers overtagelse, (b) var det nævnt eller burde det være opdaget "
                "via tilstandsrapport/elinstallationsrapport, og (c) er forholdet en dækningsberettiget "
                "skade/nedsat funktion – eller alene forventeligt vedligehold, æstetik eller alderssvarende stand?\n"
                "8. Aldersfradrag og restlevetid: gengiv nævnets konkrete tilgang i kilderne – generalisér "
                "ikke fradragspraksis på tværs af bygningsdele uden kildebelæg.\n\n"
                "ÆRLIGHED:\n"
                "9. Er praksis ikke entydig, så skriv det eksplicit (\"Praksis er ikke entydig: ...\") og "
                "vis begge linjer med kilder – vælg ikke side uden belæg.\n"
                "10. Hvis kilderne ikke besvarer spørgsmålet, skriv det klart og foreslå en mere målrettet "
                "søgning (andre søgeord/filtre). Gæt aldrig.\n"
                "11. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering.\n\n"
                f"KILDEREGISTER:\n{kilde_liste}"
            ),
        },
        {
            "type": "text",
            "text": f"\nKENDELSER:\n{kontekst}\n",
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": f"{samtale_blok}SPØRGSMÅL: {spørgsmål}\n\nSVAR:",
        },
    ]


def claude_svar(spørgsmål, docs, historik=None):
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    return _llm(_byg_prompt(spørgsmål, docs, historik), max_tokens=3000)


def claude_svar_stream(spørgsmål, docs, historik=None, placeholder=None):
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."
    return _llm_stream(_byg_prompt(spørgsmål, docs, historik), max_tokens=3000,
                       placeholder=placeholder)


def claude_resumé(titel, tekst):
    if not ANTHROPIC_API_KEY:
        return "Ingen API-nøgle."
    kerne = udtræk_kerneafsnit(tekst, max_tegn=6000)
    prompt = f"""Lav et kort, struktureret resumé af denne kendelse fra Ankenævnet for Forsikring
om ejerskifteforsikring. Inkluder: Sagens kerne, Klagerens påstand, Selskabets påstand,
Nævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {kerne}

RESUMÉ:"""
    return _llm(prompt)


def erstat_kilde_refs(tekst, kilder):
    unique: dict = {}

    def repl(m):
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
        spans = []
        for n in nums:
            if 1 <= n <= len(kilder):
                k = kilder[n - 1]
                sag = k.get("Sagsnummer", "") or "Kilde"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = "–"
                label = f"{sag} {år}".strip()
                unique[n - 1] = (label, k)
                spans.append(
                    f'<span style="color:#2563eb;font-weight:600;white-space:nowrap;">[{label}]</span>'
                )
        return " ".join(spans) if spans else m.group(0)

    out = re.sub(r"\[Kilde\s+([\d,\s]+)\]", repl, tekst)
    ordered = [(idx, label, k) for idx, (label, k) in sorted(unique.items())]
    return out, ordered


def _behandl_spørgsmål(spørgsmål):
    """Kør ét spørgsmål gennem RAG + Claude og gem i historikken.

    Én kilde til sandhed for både forslags-knapper og send-formularen (afløser ~40
    linjers dubleret kode). Citatkontrollen gemmes separat (ikke længere klistret
    ind i svarteksten som en rød alarm-boks)."""
    spørgsmål = (spørgsmål or "").strip()
    if not spørgsmål:
        return
    st.session_state.chat_historik.append({"rolle": "bruger", "tekst": spørgsmål})
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;">'
        f'<div class="chat-user">{spørgsmål}</div></div>',
        unsafe_allow_html=True,
    )
    ph = st.empty()
    with st.spinner("Søger i kendelser…"):
        try:
            _, kilder = smart_retrieval(
                spørgsmål, df, vec, mat, ai_sub_idx,
                st.session_state.chat_historik, embeds=embeds,
                filter_options=_filter_options,
            )
        except Exception:
            kilder = []
    suspekte = []
    try:
        svar = claude_svar_stream(spørgsmål, kilder,
                                  historik=st.session_state.chat_historik, placeholder=ph)
        try:
            suspekte = valider_citationer(svar, kilder)
        except Exception:
            suspekte = []
    except Exception as e:
        svar = f"Fejl ved AI Assistent: {e}"
        ph.error(svar)
        kilder = []
    af = st.session_state.pop("_ejnar_last_auto_filters", None)
    st.session_state.chat_historik.append({
        "rolle": "assistent", "tekst": svar, "kilder": kilder,
        "auto_filters": af, "suspekte": suspekte,
    })
    st.session_state.pop("_ejnar_open", None)
    st.rerun()


def _render_kildeliste(msg_idx, kilder):
    """Højre kolonne (standard): scanbar, søgbar liste over de fundne afgørelser."""
    st.markdown(f'<div class="src-list-h">Fundne afgørelser ({len(kilder)})</div>',
                unsafe_allow_html=True)
    q = ""
    if len(kilder) > 4:
        q = st.text_input(
            "Søg i fundne afgørelser", key=f"src_q_{msg_idx}",
            placeholder="Filtrér på titel, selskab, sagsnr, udfald…",
            label_visibility="collapsed").strip().lower()
    vist = []
    for i, k in enumerate(kilder):
        if q:
            blob = " ".join(str(k.get(f, "") or "") for f in
                            ("Titel", "Selskab", "Sagsnummer", "Udfald")).lower()
            blob += " " + " ".join(k.get("Mangeltype") or []).lower()
            if q not in blob:
                continue
        vist.append((i, k))
    if not vist:
        st.caption("Ingen af de fundne afgørelser matcher filteret.")
    for i, k in vist:
        try:
            ds = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            ds = "–"
        udf = k.get("Udfald") or "–"
        sel = k.get("Selskab") or "–"
        titel = (k.get("Titel") or "")[:90]
        st.markdown(
            f'<div class="src-card">'
            f'<div class="src-card-top"><span class="src-card-num">{i+1}</span>'
            f'<span class="src-card-meta">{ds} &nbsp;·&nbsp; {udf} &nbsp;·&nbsp; {sel}</span></div>'
            f'<div class="src-card-title">{titel}</div></div>',
            unsafe_allow_html=True,
        )
        if st.button("Læs & find citat →", key=f"open_src_{msg_idx}_{i}",
                     use_container_width=True):
            st.session_state["_ejnar_open"] = (msg_idx, i)
            st.rerun()


def _render_læserude(msg_idx, k, svar_tekst):
    """Højre kolonne (åben): kendelsen formateret lækkert med indholdsfortegnelse
    og det citat Ejnar brugte fremhævet i teksten."""
    if st.button("← Luk", key=f"close_src_{msg_idx}"):
        st.session_state.pop("_ejnar_open", None)
        st.rerun()
    try:
        ds = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
    except Exception:
        ds = "–"
    sag = k.get("Sagsnummer") or "–"
    udf = k.get("Udfald") or "–"
    sel = k.get("Selskab") or "–"
    try:
        quotes = citater_for_kilde(svar_tekst, k)
    except Exception:
        quotes = []
    toc_html, body_html = byg_lækker_afgørelse(
        k.get("Tekst", ""), highlight_quotes=quotes, anchor_prefix=f"s{msg_idx}")
    callout = ""
    if quotes:
        qs = "".join(f'<div class="cite-callout-q">»{strip_html(q)}«</div>' for q in quotes[:4])
        callout = ('<div class="cite-callout"><div class="cite-callout-h">'
                   f'✦ Citat brugt i svaret — fremhævet nedenfor</div>{qs}</div>')
    st.markdown(
        f'<div class="rd-pane">'
        f'<div class="rd-pane-head"><div class="rd-pane-title">{k.get("Titel","")}</div>'
        f'<div class="rd-pane-meta">{ds} &nbsp;·&nbsp; {udf} &nbsp;·&nbsp; {sel} &nbsp;·&nbsp; sag {sag}</div></div>'
        f'{callout}'
        f'<div class="rd-body-scroll">{toc_html}{body_html}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<a href="{k.get("Link","#")}" target="_blank" '
        f'style="font-size:11.5px;color:#2563eb;text-decoration:none;font-weight:500;">'
        f'Åbn original på ankeforsikring.dk ↗</a>',
        unsafe_allow_html=True,
    )


def _render_bruger(msg):
    st.markdown(
        '<div style="display:flex;justify-content:flex-end;margin:1.1rem 0 0.2rem;">'
        '<span style="font-size:10px;font-weight:700;color:#64748b;'
        'text-transform:uppercase;letter-spacing:1.2px;">Du</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="display:flex;justify-content:flex-end;">'
        f'<div class="chat-user">{msg["tekst"]}</div></div>',
        unsafe_allow_html=True,
    )


def _render_assistent_svar(msg_idx, msg):
    """Render ét Ejnar-svar: markdown-formateret svar + klikbare citat-chips +
    rolig citatkontrol, og enten kilde-liste eller åben læserude til højre."""
    st.markdown(
        '<div style="display:flex;align-items:center;gap:6px;margin:0.4rem 0 0.3rem;">'
        '<span style="font-size:10px;font-weight:700;color:#2563eb;'
        'text-transform:uppercase;letter-spacing:0.8px;">Ejnar</span></div>',
        unsafe_allow_html=True,
    )
    af = msg.get("auto_filters")
    if af and af.get("suggested"):
        chips = " · ".join(
            f"<strong>{k}:</strong> {', '.join(str(v) for v in vs)}"
            for k, vs in af["suggested"].items()
        )
        status = (f'Indsnævret til {af["after"]} kendelser'
                  if af.get("applied") else "Foreslået (ikke anvendt — for få hits)")
        st.markdown(
            f'<div style="margin:0 0 0.6rem;padding:6px 10px;background:#f8fafc;'
            f'border:1px solid #eef1f6;border-radius:6px;font-size:11px;color:#64748b;">'
            f'<span style="color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;'
            f'font-weight:600;font-size:9.5px;">Auto-filter</span> &nbsp;{chips} '
            f'<span style="color:#94a3b8;">— {status}</span></div>',
            unsafe_allow_html=True,
        )

    kilder = msg.get("kilder", [])
    html_svar = md_til_html(msg.get("tekst", ""))
    if kilder:
        vist, ref_kilder = erstat_kilde_refs(html_svar, kilder)
    else:
        vist, ref_kilder = html_svar, []

    col_svar, col_kld = st.columns([3, 2], gap="large")
    with col_svar:
        st.markdown(f'<div class="chat-assistant">{vist}</div>', unsafe_allow_html=True)
        ren = strip_html(msg.get("tekst", ""))
        ac1, ac2 = st.columns([1, 1.4])
        with ac1:
            copy_button(ren, label="Kopiér svar", key=f"cp_{msg_idx}")
        with ac2:
            # find det spørgsmål der udløste svaret (nærmeste bruger-besked før)
            _sp = ""
            for _m in reversed(st.session_state.chat_historik[:msg_idx]):
                if _m.get("rolle") == "bruger":
                    _sp = _m.get("tekst", "")
                    break
            try:
                _notat = byg_notat_html(_sp, msg.get("tekst", ""), kilder)
                st.download_button(
                    "📄 Download som notat", data=_notat.encode("utf-8"),
                    file_name=f"ejnar-notat-{pd.Timestamp.now().strftime('%Y%m%d')}.html",
                    mime="text/html", key=f"notat_{msg_idx}",
                    help="Åbn filen og tryk Ctrl+P → 'Gem som PDF' for et printklart praksisnotat med kilder.",
                )
            except Exception:
                pass

        # Klikbare citat-chips → åbn kilden i ruden til højre m. fremhævet citat
        if ref_kilder:
            st.markdown(
                '<div class="cite-chips-label">Citater — klik for at se i kendelsen</div>',
                unsafe_allow_html=True,
            )
            ccols = st.columns(min(len(ref_kilder), 3))
            for ci, (src_idx, label, k) in enumerate(ref_kilder):
                with ccols[ci % 3]:
                    if st.button(f"⟶ {label}", key=f"cite_{msg_idx}_{ci}",
                                 use_container_width=True):
                        st.session_state["_ejnar_open"] = (msg_idx, src_idx)
                        st.rerun()

        # Rolig citatkontrol (afløser den røde alarm-boks)
        suspekte = msg.get("suspekte") or []
        if suspekte:
            with st.expander(f"⚠ Citatkontrol — {len(suspekte)} citat(er) bør dobbelttjekkes"):
                st.markdown('<span class="cite-note-anchor"></span>', unsafe_allow_html=True)
                punkter = "".join(
                    f'<div class="cite-note" style="margin-bottom:6px;">'
                    f'<span class="q">»{(c[:160] + "…") if len(c) > 160 else c}«</span></div>'
                    for c in suspekte[:5]
                )
                st.markdown(
                    '<div class="cite-note">Følgende citater kunne ikke genfindes ordret '
                    'i kilderne. Det skyldes oftest små sproglige forskelle, men bør '
                    f'dobbelttjekkes mod originalen:</div><div style="margin-top:6px;">{punkter}</div>',
                    unsafe_allow_html=True,
                )

    with col_kld:
        if not kilder:
            st.caption("Ingen kilder fundet til dette svar.")
        else:
            open_state = st.session_state.get("_ejnar_open")
            if (open_state and open_state[0] == msg_idx
                    and 0 <= open_state[1] < len(kilder)):
                _render_læserude(msg_idx, kilder[open_state[1]], msg.get("tekst", ""))
            else:
                _render_kildeliste(msg_idx, kilder)


# ── Tilstand ──────────────────────────────────────────────────────────────────
if "chat_historik"     not in st.session_state: st.session_state.chat_historik = []
if "valgt_kendelse"    not in st.session_state: st.session_state.valgt_kendelse = None

# ── Indlæs ────────────────────────────────────────────────────────────────────
df = load_data()
vec, mat = build_index(len(df))
embeds = build_embeddings(len(df))
if embeds is None and embeddings_tilgængelige():
    build_embeddings.clear()
    embeds = build_embeddings(len(df))

# Link → df-rækkeindeks (bruges af semantisk chunk-udvælgelse i _byg_prompt)
_LINK_TIL_IDX = ({str(l): i for i, l in enumerate(df["Link"])} if not df.empty else {})


# ── Permalinks (?sag=…) ───────────────────────────────────────────────────────
def _kendelse_id(row) -> str:
    """Stabilt, URL-venligt id: sagsnummer hvis muligt, ellers halen af linket."""
    sag = str(row.get("Sagsnummer") or "").strip()
    if sag:
        return sag
    return str(row.get("Link") or "").rstrip("/").rsplit("/", 1)[-1][-40:]


def _sæt_permalink(row):
    try:
        st.query_params["sag"] = _kendelse_id(row)
    except Exception:
        pass


def _ryd_permalink():
    try:
        st.query_params.pop("sag", None)
    except Exception:
        pass


# Konsumér deeplink én gang pr. session (så "← Alle kendelser" ikke genåbner den)
if not st.session_state.get("_ejnar_deeplink_done"):
    st.session_state["_ejnar_deeplink_done"] = True
    try:
        _dl = str(st.query_params.get("sag", "") or "").strip()
    except Exception:
        _dl = ""
    if _dl and not df.empty and st.session_state.valgt_kendelse is None:
        _hit = df[df["Sagsnummer"].astype(str).str.strip() == _dl]
        if _hit.empty:
            _hit = df[df["Link"].astype(str).str.rstrip("/").str.endswith(_dl)]
        if not _hit.empty:
            st.session_state.valgt_kendelse = _hit.iloc[0].to_dict()

_alle_mangeltyper = sorted({m for ms in df.get("Mangeltype", []) for m in ms}) \
                    if not df.empty else []
_alle_udfald      = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]
_alle_selskaber   = sorted({s for s in df.get("Selskab", []) if s}) if not df.empty else []

_filter_options = {
    "Mangeltype": _alle_mangeltyper,
    "Selskab":    _alle_selskaber,
}

_voyage_key_sat = bool(hent_nøgle("VOYAGE_API_KEY") or hent_nøgle("OPENAI_API_KEY"))
_embeds_ok = embeds is not None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(150, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<span class="h-filter-label">Søgeord</span>', unsafe_allow_html=True)
    # Ryd søgefeltet hvis en chip eller "Ryd alle" har anmodet om det (skal ske
    # før widget'en instantieres, ellers ignorerer Streamlit værdiændringen).
    if st.session_state.pop("_ejnar_clear_soeg", False):
        st.session_state["ejnar_soeg"] = ""
    søg_input = st.text_input("", placeholder="f.eks. skimmel, tag, selvrisiko, levetid…",
                              label_visibility="collapsed", key="ejnar_soeg")
    søge_type = st.radio("", ["Ordret", "Intelligent"], horizontal=True,
                         label_visibility="collapsed", key="søge_type")
    st.markdown('<span style="font-size:10.5px;color:#64748b;line-height:1.4;display:block;margin-top:-6px;">'
                'Ordret = nøjagtig tekstmatch &nbsp;·&nbsp; Intelligent = AI finder relevante kendelser</span>',
                unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Mangeltype</span>', unsafe_allow_html=True)
    mangel_valg = st.multiselect("", _alle_mangeltyper,
                                  label_visibility="collapsed", key="mt")

    st.markdown('<span class="h-filter-label">Forsikringsselskab</span>', unsafe_allow_html=True)
    selskab_valg = st.multiselect("", _alle_selskaber,
                                   label_visibility="collapsed", key="sel")

    if not df.empty and df["År"].notna().any():
        år_min, år_max = int(df["År"].min()), int(df["År"].max())
    else:
        år_min, år_max = 2000, 2026
    st.markdown('<span class="h-filter-label">Husets opførelsesår</span>', unsafe_allow_html=True)
    if not df.empty and df["Opførelsesår"].notna().any():
        opf_min, opf_max = int(df["Opførelsesår"].min()), int(df["Opførelsesår"].max())
    else:
        opf_min, opf_max = 1850, 2026
    opf_range = st.slider("", opf_min, opf_max, (opf_min, opf_max),
                          label_visibility="collapsed", key="opf_aar")
    if not df.empty:
        _n_ukendt_opf = int(df["Opførelsesår"].isna().sum())
        if opf_range != (opf_min, opf_max) and _n_ukendt_opf:
            st.markdown(
                f'<span style="font-size:10px;color:#64748b;line-height:1.4;display:block;'
                f'margin-top:-6px;">{_n_ukendt_opf} kendelser uden kendt opførelsesår skjules</span>',
                unsafe_allow_html=True,
            )

    st.markdown('<span class="h-filter-label">Afgørelsesår</span>', unsafe_allow_html=True)
    år_range = st.slider("", år_min, år_max, (år_min, år_max),
                         label_visibility="collapsed", key="afg_aar")

    with st.expander("Flere filtre"):
        st.markdown('<span class="h-filter-label">Udfald</span>', unsafe_allow_html=True)
        udfald_valg = st.multiselect("", _alle_udfald,
                                      label_visibility="collapsed", key="ud")

    st.markdown("---")
    st.markdown(
        f"<span style='font-size:12px;color:#cbd5e1;font-weight:500;'>"
        f"**{len(df):,}** kendelser &nbsp;·&nbsp; {år_min}–{år_max}</span>",
        unsafe_allow_html=True,
    )
    if not df.empty and df["Dato"].notna().any():
        st.markdown(
            f"<span style='font-size:11px;color:#94a3b8;'>"
            f"Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>",
            unsafe_allow_html=True,
        )

    _har_filtre = bool(mangel_valg or selskab_valg or udfald_valg
                       or søg_input.strip() or år_range != (år_min, år_max)
                       or opf_range != (opf_min, opf_max))
    if _har_filtre:
        if st.button("Nulstil filtre", use_container_width=True, key="_ejnar_reset"):
            for k in ["mt", "sel", "ud", "søge_type", "afg_aar", "opf_aar"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state["_ejnar_clear_soeg"] = True
            st.rerun()


# ── Filtrering ────────────────────────────────────────────────────────────────
if df.empty:
    st.warning(
        "Ingen kendelser indlæst. Læg en `ejnar_ejerskifteforsikring.csv` i `ejnar/`-mappen "
        "(kør `python3 ejnar/scrape_ejnar.py` for at hente data fra ankeforsikring.dk).",
        icon="📁",
    )
    sidebar_log_ud()
    st.stop()


mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if opf_range != (opf_min, opf_max):
    # Ukendt opførelsesår → False: aktivt filter betyder "vis kun huse jeg VED er
    # fra perioden" (sidebar viser antallet der skjules)
    mask &= df["Opførelsesår"].between(opf_range[0], opf_range[1]).fillna(False).astype(bool)
if mangel_valg:
    mask &= df["Mangeltype"].apply(lambda mts: any(m in mts for m in mangel_valg))
if selskab_valg:
    mask &= df["Selskab"].isin(selskab_valg)
if udfald_valg:
    mask &= df["Udfald"].isin(udfald_valg)

df_filter = df[mask].reset_index(drop=True)
sub_idx = df[mask].index.tolist()

_filter_sig = (len(df_filter),
               df_filter["Link"].iloc[0] if len(df_filter) > 0 else "",
               søg_input.strip(), søge_type)
if st.session_state.get("_filter_sig") != _filter_sig:
    st.session_state["vis_antal"] = 25
    st.session_state["_filter_sig"] = _filter_sig
_vis_antal = st.session_state.get("vis_antal", 25)

if søg_input.strip() and søge_type == "Intelligent":
    df_vis = tfidf_søg(søg_input.strip(), df, vec, mat, sub_idx=sub_idx)
    ai_sub_idx = sub_idx
elif søg_input.strip():
    _q = søg_input.strip()
    _text_mask = (
        df_filter["Titel"].str.contains(_q, case=False, na=False, regex=False) |
        df_filter["Tekst"].str.contains(_q, case=False, na=False, regex=False)
    )
    df_vis = df_filter[_text_mask].sort_values("Dato", ascending=False).reset_index(drop=True)
    _matched = df_filter.index[_text_mask].tolist()
    ai_sub_idx = [sub_idx[i] for i in _matched] if _matched else sub_idx
else:
    df_vis = df_filter.sort_values("Dato", ascending=False)
    ai_sub_idx = sub_idx


def build_download_text(data, søgeord=""):
    lines = [
        "ANKENÆVNET FOR FORSIKRING — EJERSKIFTEFORSIKRING — EKSPORT",
        f"Antal kendelser: {len(data)}",
        f"Søgeord: {søgeord if søgeord.strip() else '(ingen — kun filteret på mangeltype/selskab/udfald)'}",
        f"Genereret: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
        "=" * 72, "",
    ]
    for _, row in data.iterrows():
        dato = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
        mt = ", ".join(row.get("Mangeltype") or []) or "–"
        lines += [
            f"KENDELSE:    {row['Titel']}",
            f"DATO:        {dato}",
            f"SAGSNR:      {row.get('Sagsnummer') or '–'}",
            f"SELSKAB:     {row.get('Selskab') or '–'}",
            f"UDFALD:      {row.get('Udfald') or '–'}",
            f"MANGELTYPE:  {mt}",
            f"KILDE:       {row['Link']}",
            "-" * 72,
            (row.get("Tekst") or "").strip(),
            "", "=" * 72, "",
        ]
    return "\n".join(lines)


with st.sidebar:
    n = len(df_filter)
    st.markdown("---")
    if n == 0:
        st.caption("Ingen kendelser matcher filtrene.")
    else:
        dl = build_download_text(df_filter, søgeord=søg_input).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download {n:,} kendelser (.txt)",
            data=dl,
            file_name="ejnar_kendelser.txt",
            mime="text/plain",
        )
    sidebar_log_ud()


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header">
  <h1 class="h-page-title">Ejerskifteforsikring</h1>
  <p class="h-page-meta">
    Ankenævnet for Forsikring &nbsp;·&nbsp; {len(df):,} kendelser
    &nbsp;·&nbsp; {år_min}–{år_max}
  </p>
</div>
""", unsafe_allow_html=True)


init_sagsmapper()
_n_gemte = sum(len(m["afgørelser"]) for m in st.session_state["sagsmapper"]["mapper"].values())
_mappe_label = f"  Sagsmapper ({_n_gemte})  " if _n_gemte else "  Sagsmapper  "
tab_søg, tab_stat, tab_ai, tab_mapper = st.tabs(
    ["  Kendelser  ", "  Statistik  ", "  AI Assistent  ", _mappe_label])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – KENDELSER
# ════════════════════════════════════════════════════════════════════════════
with tab_søg:
    if st.session_state.valgt_kendelse is not None:
        row = st.session_state.valgt_kendelse
        if st.button("← Alle kendelser"):
            st.session_state.valgt_kendelse = None
            _ryd_permalink()
            st.rerun()
        _sæt_permalink(row)

        dato_str = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
        udfald = row.get("Udfald") or "Ukendt"
        chip_styles = {
            "Medhold":        "background:#f0fdf4;color:#166534;border-color:#bbf7d0",
            "Delvis medhold": "background:#ecfeff;color:#155e75;border-color:#a5f3fc",
            "Ikke medhold":   "background:#fef2f2;color:#991b1b;border-color:#fecaca",
            "Afvist":         "background:#fffbeb;color:#92400e;border-color:#fde68a",
        }
        chip_s = chip_styles.get(udfald, "background:#f8fafc;color:#64748b;border-color:#e2e8f0")
        mt_str = " / ".join(row.get("Mangeltype") or []) or "–"

        st.markdown(
            render_detail_header(
                titel=row["Titel"],
                udfald=udfald,
                chip_style=chip_s,
                dato_str=dato_str,
                meta_extra=[
                    ("Sagsnr.", row.get("Sagsnummer") or "–"),
                    ("Selskab", row.get("Selskab") or "–"),
                    ("Mangeltype", mt_str),
                    ("Opført", str(int(row["Opførelsesår"]))
                     if pd.notna(row.get("Opførelsesår")) else "–"),
                ],
                link=row["Link"],
                link_label="Åbn original på ankeforsikring.dk",
            ),
            unsafe_allow_html=True,
        )

        # Handlingsrække: delbart link + sagsmappe
        init_sagsmapper()
        _i_mappe = find_mappe_for_link(row["Link"])
        hc1, hc2, _sp = st.columns([1.1, 1.3, 3])
        with hc1:
            try:
                _base = str(st.context.url).split("?")[0]
            except Exception:
                _base = ""
            copy_button(f"{_base}?sag={_kendelse_id(row)}",
                        label="🔗 Kopiér link", key="perma_cp")
        with hc2:
            if _i_mappe:
                if st.button("✓ Gemt i sagsmappe — fjern", key="sm_fjern"):
                    fjern_afgørelse(_i_mappe, row["Link"])
                    st.rerun()
            else:
                if st.button("📁 Gem i sagsmappe", key="sm_gem"):
                    _mapper = st.session_state["sagsmapper"]["mapper"]
                    _mid = st.session_state["sagsmapper"]["standard_mappe"]
                    if not _mapper:
                        _mid = opret_mappe("Min sagsmappe")
                    gem_afgørelse(
                        _mid, row["Link"], row["Titel"],
                        str(row.get("Dato") or ""), row.get("Udfald") or "",
                        "AKF", " / ".join(row.get("Mangeltype") or []),
                        row.get("Selskab") or "", row.get("Excerpt") or "",
                    )
                    st.rerun()

        toc_html, body_html = byg_lækker_afgørelse(row["Tekst"], anchor_prefix="detail")
        if toc_html:
            col_toc, col_tekst, col_ai = st.columns([1.1, 3, 1.6], gap="large")
            with col_toc:
                st.markdown(toc_html, unsafe_allow_html=True)
        else:
            col_tekst, col_ai = st.columns([3, 1.6], gap="large")
        with col_tekst:
            st.markdown(f'<div style="max-width:74ch;">{body_html}</div>',
                        unsafe_allow_html=True)
        with col_ai:
            st.markdown(
                '<div class="detail-ai-panel">'
                '<div class="detail-ai-title">✦ &nbsp;AI-Resumé</div>',
                unsafe_allow_html=True,
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
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        # Aktive filter-chips
        _chips = []
        if søg_input.strip():
            def _clr_søg(): st.session_state["_ejnar_clear_soeg"] = True
            _chips.append((f"Søgeord: {søg_input.strip()[:30]}", _clr_søg))
        for _m in mangel_valg:
            def _c(_v=_m): st.session_state["mt"] = [x for x in st.session_state.get("mt", []) if x != _v]
            _chips.append((f"Mangel: {_m}", _c))
        for _s in selskab_valg:
            def _c(_v=_s): st.session_state["sel"] = [x for x in st.session_state.get("sel", []) if x != _v]
            _chips.append((f"Selskab: {_s}", _c))
        for _u in udfald_valg:
            def _c(_v=_u): st.session_state["ud"] = [x for x in st.session_state.get("ud", []) if x != _v]
            _chips.append((f"Udfald: {_u}", _c))
        if år_range != (år_min, år_max):
            def _c():
                st.session_state.pop("afg_aar", None)
            _chips.append((f"Afgørelsesår: {år_range[0]}–{år_range[1]}", _c))
        if opf_range != (opf_min, opf_max):
            def _c():
                st.session_state.pop("opf_aar", None)
            _chips.append((f"Opført: {opf_range[0]}–{opf_range[1]}", _c))
        if _chips:
            def _clr_all():
                for k in ["mt", "sel", "ud", "søge_type", "afg_aar", "opf_aar"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state["_ejnar_clear_soeg"] = True
            _chips.append(("Ryd alle", _clr_all))
            render_filter_chips(_chips, key_prefix="ejnar_chip")

        total = len(df_filter)
        hits = len(df_vis)
        if søg_input:
            tag = "intelligent" if søge_type == "Intelligent" else "ordret"
            st.markdown(f"**{hits}** resultater for \"{søg_input}\" · {tag} søgning "
                        f"(ud af {total:,} filtrerede)")
        else:
            st.markdown(f"Viser {min(_vis_antal, hits)} af **{total:,}** kendelser (nyeste først)")

        if hits == 0:
            st.markdown(
                '<div style="text-align:center;padding:3rem 1rem;color:#94a3b8;">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">🔍</div>'
                '<div style="font-size:15px;font-weight:600;color:#475569;margin-bottom:0.4rem;">'
                'Ingen kendelser matcher din søgning</div>'
                '<div style="font-size:13px;">Prøv at udvide filtrene eller ændre søgeordene.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            _BADGE = {
                "Medhold":        "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Delvis medhold": "background:#ecfeff;color:#155e75;border:1px solid #a5f3fc",
                "Ikke medhold":   "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Afvist":         "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
            }
            _BADGE_DEF = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"
            _hl = søg_input.strip()
            for _, row in df_vis.head(_vis_antal).iterrows():
                bs = _BADGE.get(row["Udfald"], _BADGE_DEF)
                ds = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                mt_label = " / ".join(row.get("Mangeltype") or []) or "–"
                sel = row.get("Selskab") or "–"
                opf_tag = (f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
                           f'font-size:10.5px;font-weight:500;color:#1d4ed8;background:#eff6ff;'
                           f'border:1px solid #dbeafe;">Opført {int(row["Opførelsesår"])}</span>'
                           if pd.notna(row.get("Opførelsesår")) else "")
                titel_h = highlight_query(row["Titel"], _hl) if _hl else row["Titel"]
                exc_h = highlight_query(row["Excerpt"], _hl, max_len=300) if _hl \
                        else (row["Excerpt"] + "…")
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:.2px;">{ds}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.1px;{bs}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{titel_h}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{mt_label}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{sel}</span>
    {opf_tag}
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{exc_h}</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn kendelse på ankeforsikring.dk ↗</a>
  </div>
</div>""", unsafe_allow_html=True)
                if st.button("Læs kendelse →", key=f"btn_{row['Link'][-20:]}"):
                    st.session_state.valgt_kendelse = row.to_dict()
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
    _LAYOUT = dict(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#334155"),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    _UDFALD_FARVER = {
        "Medhold":        "#10b981",
        "Delvis medhold": "#06b6d4",
        "Ikke medhold":   "#ef4444",
        "Afvist":         "#f59e0b",
        "Ukendt":         "#94a3b8",
    }

    if d.empty:
        st.info("Ingen data at vise med de valgte filtre.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        pct_medhold = (d["Udfald"].isin(["Medhold", "Delvis medhold"])).mean() * 100
        år_span = f"{int(d['År'].min())}–{int(d['År'].max())}" if d["År"].notna().any() else "–"
        for col, tal, label in [
            (k1, f"{len(d):,}", "Kendelser"),
            (k2, f"{pct_medhold:.0f}%", "Medhold-rate"),
            (k3, f"{d['Selskab'].replace('', np.nan).dropna().nunique()}", "Selskaber"),
            (k4, år_span, "Årsinterval"),
        ]:
            col.markdown(
                f'<div class="stat-card"><div class="stat-number">{tal}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Kendelser per år")
            år_df = d.dropna(subset=["År"]).groupby("År").size().reset_index(name="Antal")
            fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#2563eb"])
            fig.update_layout(**_LAYOUT)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("#### Udfald over tid")
            udf_år = d.dropna(subset=["År"]).groupby(["År", "Udfald"]).size().reset_index(name="Antal")
            fig2 = px.bar(udf_år, x="År", y="Antal", color="Udfald",
                          color_discrete_map=_UDFALD_FARVER, barmode="stack")
            fig2.update_layout(**_LAYOUT)
            fig2.update_traces(marker_line_width=0)
            st.plotly_chart(fig2, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Top mangeltyper")
            mt_rows = []
            for ms in d["Mangeltype"]:
                for m in ms:
                    mt_rows.append(m)
            if mt_rows:
                mt_df = pd.Series(mt_rows).value_counts().rename_axis("Mangeltype") \
                          .reset_index(name="Antal").sort_values("Antal", ascending=True).tail(15)
                fig3 = px.bar(mt_df, x="Antal", y="Mangeltype", orientation="h",
                              color_discrete_sequence=["#1e293b"])
                fig3.update_layout(**_LAYOUT)
                fig3.update_traces(marker_line_width=0)
                st.plotly_chart(fig3, use_container_width=True)

        with col_b:
            st.markdown("#### Top forsikringsselskaber")
            sel_df = (d[d["Selskab"] != ""].groupby("Selskab").size()
                       .reset_index(name="Sager").sort_values("Sager", ascending=True).tail(15))
            if not sel_df.empty:
                fig4 = px.bar(sel_df, x="Sager", y="Selskab", orientation="h",
                              color_discrete_sequence=["#2563eb"])
                fig4.update_layout(**_LAYOUT)
                fig4.update_traces(marker_line_width=0)
                st.plotly_chart(fig4, use_container_width=True)

        st.markdown("#### Medhold-rate per mangeltype")
        rate_rows = []
        for mt in sorted({m for ms in d["Mangeltype"] for m in ms}):
            sub = d[d["Mangeltype"].apply(lambda ms: mt in ms)]
            if len(sub) >= 3:
                rate_rows.append({
                    "Mangeltype": mt,
                    "Sager": len(sub),
                    "Medhold_%": round(sub["Udfald"].isin(["Medhold", "Delvis medhold"]).mean() * 100, 1),
                })
        if rate_rows:
            mr = pd.DataFrame(rate_rows).sort_values("Medhold_%", ascending=True)
            fig5 = px.bar(mr, x="Medhold_%", y="Mangeltype", orientation="h",
                          color="Medhold_%", color_continuous_scale=["#fee2e2", "#10b981"],
                          hover_data={"Sager": True}, labels={"Medhold_%": "Medhold (%)"})
            fig5.update_layout(**_LAYOUT, coloraxis_showscale=False)
            fig5.update_traces(marker_line_width=0)
            st.plotly_chart(fig5, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    n_ai = len(ai_sub_idx)
    filtreret = n_ai != len(df)
    antal_tekst = f"{n_ai:,}" if filtreret else f"{len(df):,}"
    filtreret_label = " (filtreret)" if filtreret else ""
    søge_mode = "Hybrid (TF-IDF + semantisk)" if embeds is not None else "TF-IDF"
    if isinstance(embeds, dict) and embeds.get("dækning"):
        _dk, _dn = embeds["dækning"]
        if _dk < _dn:
            søge_mode += (f" · semantisk indeks dækker {_dk:,} af {_dn:,} kendelser "
                          f"(kør build_embeddings.py for fuld dækning)")

    st.markdown(f"""
<div class="ai-hero">
  <span class="material-symbols-rounded ai-hero-icon">smart_toy</span>
  <div>
    <div class="ai-hero-title">Spørg til praksis om ejerskifteforsikring</div>
    <div class="ai-hero-sub">
      Søger i <strong>{antal_tekst} kendelser{filtreret_label}</strong>
      og svarer med kildehenvisninger. Opfølgningsspørgsmål husker kontekst.
    </div>
    <div style="font-size:10.5px;color:#94a3b8;margin-top:4px;">Søgemetode: {søge_mode}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    if not _embeds_ok:
        try:
            keys = sorted([k for k in st.secrets.keys()])
        except Exception:
            keys = []
        keylist = ", ".join(f"`{k}`" for k in keys) if keys else "(ingen)"
        if _voyage_key_sat:
            err = get_embed_error() or "Ukendt fejl"
            st.warning(
                "**Intelligent søgning ikke aktiv.** Embedding-indekset kunne ikke bygges.\n\n"
                f"**API-fejl:** `{err}`\n\nFundne secrets: {keylist}",
                icon="⚠️",
            )
        else:
            st.info(
                "**TF-IDF-søgning er aktiv** (ordbaseret). For hybrid semantisk søgning: "
                "tilføj `VOYAGE_API_KEY` i Streamlit Cloud secrets og genstart appen. "
                f"Fundne secrets: {keylist}.",
                icon="ℹ️",
            )

    if not ANTHROPIC_API_KEY:
        st.error("Tilføj `ANTHROPIC_API_KEY` i Streamlit secrets.")
    else:
        if mangel_valg and len(mangel_valg) == 1:
            ctx = mangel_valg[0].lower()
            forslag = [
                f"Hvad er Ankenævnets praksis ved {ctx}?",
                f"Hvornår får klager medhold i {ctx}-sager?",
                f"Hvilke argumenter er afgørende ved {ctx}?",
                f"Hvornår nægter selskabet dækning for {ctx}?",
            ]
        elif søg_input.strip():
            q = søg_input.strip()
            forslag = [
                f"Hvad er Ankenævnets praksis vedrørende {q}?",
                f"Hvornår får klager medhold i sager om {q}?",
                f"Hvilke argumenter er afgørende for {q}?",
                f"Er der en klar tendens i kendelserne om {q}?",
            ]
        else:
            forslag = [
                "Hvornår dækker ejerskifteforsikringen skimmelsvamp?",
                "Hvilken praksis har Ankenævnet for utætheder i tag?",
                "Hvordan bedømmes restlevetid på installationer?",
                "Hvornår er en mangel undtaget pga. tilstandsrapporten?",
            ]
        st.markdown('<div id="ai-forslag-anchor"></div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"fs_{i}"):
                _behandl_spørgsmål(f)

        with st.form("chat_form", clear_on_submit=True):
            spørgsmål = st.text_area(
                "Dit spørgsmål", height=80, label_visibility="collapsed",
                placeholder="Spørg om Ankenævnets praksis — fx »Hvornår dækkes skjult skimmel?«")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send ➤", use_container_width=True, type="primary")
            ryd = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.chat_historik = []
            st.session_state.pop("_ejnar_open", None)
            st.rerun()

        if send and spørgsmål.strip():
            _behandl_spørgsmål(spørgsmål)

        st.divider()

        # Gruppér i ture (spørgsmål → svar) og vis NYESTE øverst, så det seneste
        # svar altid står lige under inputfeltet (ingen scroll-jagt nedad).
        ture, cur = [], None
        for idx, m in enumerate(st.session_state.chat_historik):
            if m["rolle"] == "bruger":
                cur = [(idx, m), None]
                ture.append(cur)
            elif cur is not None and cur[1] is None:
                cur[1] = (idx, m)
                cur = None
            else:
                ture.append([None, (idx, m)])
                cur = None

        if not ture:
            st.markdown(
                '<div style="text-align:center;padding:2.4rem 1rem;color:#94a3b8;">'
                '<div style="font-size:1.7rem;margin-bottom:.4rem;">💬</div>'
                '<div style="font-size:14px;font-weight:600;color:#475569;">Stil dit første spørgsmål</div>'
                '<div style="font-size:12.5px;margin-top:.3rem;line-height:1.6;">Skriv ovenfor eller '
                'vælg et forslag — svaret kommer her med kildehenvisninger du kan klikke på.</div></div>',
                unsafe_allow_html=True,
            )

        for bruger, assistent in reversed(ture):
            if bruger is not None:
                _render_bruger(bruger[1])
            if assistent is not None:
                _render_assistent_svar(assistent[0], assistent[1])


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 – SAGSMAPPER
# ════════════════════════════════════════════════════════════════════════════
with tab_mapper:
    _mapper = st.session_state["sagsmapper"]["mapper"]

    st.markdown(
        '<div style="font-size:12px;color:#64748b;margin-bottom:14px;">'
        'Saml kendelser til en konkret sag, skriv noter og download det hele som én fil. '
        '<strong>Bemærk:</strong> mapper gemmes kun i denne browser-session — download inden du lukker.</div>',
        unsafe_allow_html=True,
    )

    nc1, nc2 = st.columns([2, 1])
    with nc1:
        _nyt_navn = st.text_input("Ny mappe", placeholder="Navn på ny sagsmappe — fx »Skimmelsag, Fyrrevej 12«",
                                  label_visibility="collapsed", key="sm_nyt_navn")
    with nc2:
        if st.button("＋ Opret mappe", use_container_width=True, key="sm_opret"):
            if _nyt_navn.strip():
                opret_mappe(_nyt_navn.strip())
                st.rerun()

    if not _mapper:
        st.markdown(
            '<div style="text-align:center;padding:2.6rem 1rem;color:#94a3b8;">'
            '<div style="font-size:1.7rem;margin-bottom:.4rem;">📁</div>'
            '<div style="font-size:14px;font-weight:600;color:#475569;">Ingen sagsmapper endnu</div>'
            '<div style="font-size:12.5px;margin-top:.3rem;line-height:1.6;">Opret en mappe ovenfor, '
            'eller tryk »Gem i sagsmappe« inde på en kendelse.</div></div>',
            unsafe_allow_html=True,
        )
    else:
        for _mid, _mappe in list(_mapper.items()):
            _afg = _mappe["afgørelser"]
            with st.expander(f"📁 {_mappe['navn']} · {len(_afg)} kendelse{'r' if len(_afg) != 1 else ''}",
                             expanded=len(_mapper) == 1):
                mc1, mc2, mc3 = st.columns([2, 1, 1])
                with mc1:
                    _omdøb = st.text_input("Omdøb", value=_mappe["navn"],
                                           label_visibility="collapsed", key=f"sm_navn_{_mid}")
                    if _omdøb != _mappe["navn"] and _omdøb.strip():
                        omdøb_mappe(_mid, _omdøb.strip())
                with mc2:
                    if _afg:
                        _links = {a["link"] for a in _afg}
                        _rows = df[df["Link"].isin(_links)]
                        _noter = {a["link"]: (a.get("note") or "") for a in _afg}
                        _tekst = build_download_text(_rows, søgeord=f"Sagsmappe: {_mappe['navn']}")
                        _note_blok = "\n".join(
                            f"NOTE ({l[-30:]}): {n}" for l, n in _noter.items() if n.strip())
                        if _note_blok:
                            _tekst += "\n\nEGNE NOTER\n" + "=" * 72 + "\n" + _note_blok
                        st.download_button("⬇️ Download mappe", data=_tekst.encode("utf-8"),
                                           file_name=f"sagsmappe_{_mappe['navn'][:30]}.txt",
                                           mime="text/plain", key=f"sm_dl_{_mid}",
                                           use_container_width=True)
                with mc3:
                    if st.button("🗑 Slet mappe", key=f"sm_slet_{_mid}", use_container_width=True):
                        slet_mappe(_mid)
                        st.rerun()

                if not _afg:
                    st.caption("Mappen er tom — gem kendelser fra detaljevisningen.")
                for _a in list(_afg):
                    st.markdown(
                        f'<div style="border-top:1px solid #eef1f6;padding-top:10px;margin-top:10px;">'
                        f'<div style="font-size:13px;font-weight:600;color:#0f172a;line-height:1.45;">{_a["titel"]}</div>'
                        f'<div style="font-size:11px;color:#64748b;margin:2px 0 6px;">'
                        f'{_a.get("udfald") or "–"} &nbsp;·&nbsp; {_a.get("kommune") or "–"} &nbsp;·&nbsp; '
                        f'{_a.get("kategori") or "–"}</div></div>',
                        unsafe_allow_html=True,
                    )
                    ac1, ac2 = st.columns([4, 1])
                    with ac1:
                        _ny_note = st.text_area(
                            "Note", value=_a.get("note") or "", height=68,
                            placeholder="Egne noter til denne kendelse…",
                            label_visibility="collapsed", key=f"sm_note_{_mid}_{_a['link'][-20:]}")
                        if _ny_note != (_a.get("note") or ""):
                            opdater_note(_mid, _a["link"], _ny_note)
                    with ac2:
                        _row_hit = df[df["Link"] == _a["link"]]
                        if not _row_hit.empty and st.button(
                                "Åbn →", key=f"sm_open_{_mid}_{_a['link'][-20:]}",
                                use_container_width=True):
                            st.session_state.valgt_kendelse = _row_hit.iloc[0].to_dict()
                            if "_resumé" in st.session_state:
                                del st.session_state["_resumé"]
                            st.rerun()
                        if st.button("Fjern", key=f"sm_rm_{_mid}_{_a['link'][-20:]}",
                                     use_container_width=True):
                            fjern_afgørelse(_mid, _a["link"])
                            st.rerun()

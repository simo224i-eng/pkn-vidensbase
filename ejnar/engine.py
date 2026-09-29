"""Ejnars søge- og svarmotor uden Streamlit-UI.

Bruges både af Streamlit-siden (``pages/ejnar.py``) og af REST-API'et
(``api.py``). Retrieval-forbedringerne i ``*_runtime.py`` patcher funktioner på
``shared``-modulet. Derfor slås de altid op som ``shared.<navn>`` på kaldstidspunktet
og importeres aldrig direkte.
"""
from __future__ import annotations

import csv
import glob as _glob
import hashlib
import os
import re
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import pandas as pd

import shared

EJNAR_DIR = os.path.dirname(os.path.abspath(__file__))
EMBED_CACHE_KEY = "ejnar_ejerskifteforsikring"
UDFALD = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]

_RUNTIME_LOCK = threading.Lock()


def ensure_runtimes() -> None:
    """Installér retrieval-/grounding-runtimes på ``shared`` (idempotent).

    Rækkefølgen matcher ``app.py`` og har betydning, fordi hver runtime pakker
    den forrige ind."""
    with _RUNTIME_LOCK:
        if getattr(shared, "_EJNAR_ENGINE_RUNTIMES_INSTALLED", False):
            return
        from citation_runtime import install_citation_runtime
        from decision_grounding_runtime import install_decision_grounding_runtime
        from deterministic_retrieval_runtime import install_deterministic_retrieval_runtime
        from metadata_runtime import install_metadata_runtime
        from paragraph_runtime import install_paragraph_runtime
        from practice_synthesis_runtime import install_practice_synthesis_runtime
        from query_feature_runtime import install_query_feature_runtime
        from query_planner_runtime import install_query_planner_runtime
        from retrieval_runtime import install_retrieval_runtime
        from specific_decision_runtime import install_specific_decision_runtime

        install_deterministic_retrieval_runtime()
        install_retrieval_runtime()
        install_query_planner_runtime()
        install_paragraph_runtime()
        install_metadata_runtime()
        install_query_feature_runtime()
        install_specific_decision_runtime()
        install_citation_runtime()
        install_decision_grounding_runtime()
        install_practice_synthesis_runtime()
        shared._EJNAR_ENGINE_RUNTIMES_INSTALLED = True


# ── Klassifikation ────────────────────────────────────────────────────────────
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
    "Ulovlige forhold":     ["ulovlig", "ulovlighedsdækning", "byggetilladelse"],
}

# Ordgrænse-regex pr. mangeltype. Ren delstrengsmatch gav tidligere "tag" i
# 100 % af kendelserne ("tage til følge", "foretaget"), og "råd" ramte "rådgiver".
_MANGEL_RX = {
    "Skimmel/fugt": r"\bskimmel\w*|\bfugt\w*|\b\w+fugt\w*|\bkondens\w*",
    "Tag/tagdækning": (
        r"\btag\b|\btag(?:ene|dækning|sten|rende|konstruktion|værk|beklædning|pap|udhæng|fod|"
        r"flade|rum|vindue|belægning|ryg|hætte|renovering|utæthed|nedløb|folie|plade)\w*|"
        r"\b(?:i|på|af|under|over|fra|ved|hele|nyt|nye|gamle) taget\b|"
        r"\bundertag\w*|\b(?:strå|eternit|sadel|pult|valm|mansard|tegl|skifer|bølge|fladt?\s|papp?)tag\w*|"
        r"\bskotrende\w*|\btagrender\b|\binddækning\w*|\bskorsten\w*"
    ),
    "Kloak/dræn": r"\bkloak\w*|\bdræn\w*|\bafløb\w*|\bspildevand\w*|\bfaldstamme\w*|\bfaskine\w*|\bstikledning\w*|\brottespær\w*",
    "Installationer": (
        r"\bel-?install\w*|\belinstall\w*|\bvvs\w*|\bvandinstall\w*|\bvarmeinstall\w*|\bvarmeanlæg\w*|"
        r"\bfyr(?:et|anlæg|rum)?\b|\bgasfyr\w*|\boliefyr\w*|\bvarmepumpe\w*|\bgulvvarme\w*|\bradiator\w*|"
        r"\bvandrør\w*|\bvarmerør\w*|\bvandstik\w*|\bstikkontakt\w*|\beltavle\w*|\bventilation\w*|\bcirkulationspumpe\w*|"
        r"\bvarmtvandsbeholder\w*|\bbrændeovn\w*|\bpejs\w*|\binstallation(?:er|en|erne)?\b"
    ),
    "Fundament": r"\bfundament\w*|\bsokkel\w*|\bsætning(?:er|en|erne|sskade\w*)?\b|\bkælder\w*|\bkrybekælder\w*|\bterrændæk\w*",
    "Vinduer/døre": r"\bvindue\w*|\bdør(?:e|en|ene|parti\w*)?\b|\b\w+dør(?:e|en|ene)?\b|\btermorude\w*|\brude(?:r|n|rne)?\b|\bovenlys\w*|\bvelux\w*",
    "Murværk/facade": r"\bmurværk\w*|\bmursten\w*|\bfacade\w*|\bpuds\w*|\bhulmur\w*|\bgavl\w*|\bmurbinder\w*|\bbindere?\b|\bfuge(?:r|rne|n)?\b|\bydervæg\w*|\bmurrevne\w*",
    "Råd/svamp/insekt": (
        r"\bråd(?:skade\w*|dannelse\w*|ne|nede|angreb\w*)?\b|\btrænedbrydende\b|\b\w*svamp\w*(?<!skimmelsvamp)(?<!skimmelsvampen)|"
        r"\binsekt\w*|\bborebille\w*|\bhusbuk\w*|\bskadedyr\w*|\bmyre(?:r|rne|angreb\w*|tue\w*)?\b|\brotte(?:r|rne|angreb\w*)?\b"
    ),
    "Konstruktion/bærende": (
        r"\bbjælke\w*|\bbærende\b|\bspær\w*|\btrækonstruktion\w*|\betageadskillelse\w*|"
        r"\bkonstruktion(?:en|er|erne|sfejl\w*)?\b|\bstatik\w*|\bbindingsværk\w*|\bloftrum\w*|\bloft(?:et|er)?\b|\bisolering\w*"
    ),
    "Badeværelse/vådrum": r"\bbadeværelse\w*|\bvådrum\w*|\bbruse\w*|\bmembran\w*|\bgulvafløb\w*|\btoilet\w*|\bbad(?:et)?\b",
    "Gulv": r"\bgulv(?:e|et|ene|konstruktion\w*|belægning\w*|brædder)?\b|\b(?:træ|klinke|parket|plank|beton|terrazzo|trægulv)gulv\w*|\bparket\w*|\bstrøer\b",
    "Ulovlige forhold": r"\bulovlig\w*|\bbyggetilladelse\w*|\bbygningsreglement\w*|\blovliggør\w*|\bbyggeloven\b|\blokalplan\w*",
}
_MANGEL_RX = {k: re.compile(v) for k, v in _MANGEL_RX.items()}


def detect_mangeltyper(titel: str, tekst: str) -> list[str]:
    """Returnér de mangeltyper, sagen handler om.

    Titlen er AKF's resumé af klagen og er den mest præcise kilde. Kun hvis den
    intet siger (fx "AnkeforsikringDBECT_1.aspx"), bruges kendelsens indledning."""
    for blob in ((titel or "").lower(), (tekst or "")[:2000].lower()):
        fundet = [label for label, rx in _MANGEL_RX.items() if rx.search(blob)]
        if fundet:
            return fundet
    return ["Andet"]


# Udfald ses fra klagers side. AKF-titler slutter næsten altid med resultatet
# ("Selskab medhold." / "Klager delvis medhold." / "Sag afvist."), så titlens
# hale er den mest pålidelige kilde. Rækkefølgen er vigtig: "delvis" før "medhold".
_MEDHOLD = r"me?d?hold"  # fanger også tastefejl som "mehold"
_TITEL_REGLER = [
    ("Delvis medhold", re.compile(rf"\bdelvis(?:t|e)?\s+{_MEDHOLD}\b")),
    ("Medhold", re.compile(rf"\bklager(?:en|ne)?\s+{_MEDHOLD}\b")),
    ("Ikke medhold", re.compile(rf"\bselskab(?:et)?\s+{_MEDHOLD}\b")),
    ("Afvist", re.compile(
        r"\bsag(?:en)?\s+afvist|\bafvisning\b|\bklagen\s+afvis|"
        r"(?:kunne|kan)\s+(?:derfor\s+)?ikke\s+(?:afgøre|behandle|viderebehandle)\s+sagen|"
        r"afstå\s+fra\s+at\s+(?:vide)?(?:re)?behandle|afvise\s+(?:at\s+afgøre\s+)?sagen"
    )),
]
_TEKST_REGLER = [
    ("Afvist", re.compile(
        r"nævnet\s+kan\s+ikke\s+(?:afgøre|behandle|viderebehandle)\s+sagen|klagen\s+afvises|"
        r"afvises\s+som\s+åbenbart|kan\s+ikke\s+realitetsbehandles"
    )),
    ("Delvis medhold", re.compile(
        r"i\s+øvrigt\s+ikke\s+medhold|delvis(?:t)?\s+medhold|"
        r"i\s+øvrigt\s+ikke\s+tages\s+til\s+følge"
    )),
    ("Ikke medhold", re.compile(
        r"ikke\s+tages\s+til\s+følge|får\s+ikke\s+medhold|selskabet\s+frifindes|"
        r"tilpligtes\s+ikke"
    )),
    ("Medhold", re.compile(
        r"klageren\s+får\s+medhold|tages\s+til\s+følge|tilpligtes|"
        r"selskabet\s+skal\s+(?:anerkende|betale|dække|yde)|skal\s+dække\s+de"
    )),
]


def _normaliser(tekst: str) -> str:
    # Nogle ældre kendelser har orddeling fra PDF ("viderebe- handle", "b e s t e m m e s")
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", (tekst or "").lower())
    return re.sub(r"\s+", " ", t)


def detect_udfald_ejnar(titel: str, tekst: str, csv_udfald: str = "") -> str:
    """Klassificér en AKF-kendelse som Medhold / Delvis medhold / Ikke medhold /
    Afvist / Ukendt (set fra klagers side).

    1. Titlens sidste sætninger (AKF's egen resultatlinje).
    2. Kendelsens konklusion ("... bestemmes: ...").
    3. CSV-feltet fra scraperen, hvis det er kendt."""
    hale = _normaliser(titel)[-220:]
    for label, rx in _TITEL_REGLER:
        if rx.search(hale):
            return label
    tx = _normaliser(tekst)
    idx = tx.rfind("b e s t e m m e s")
    idx = idx if idx >= 0 else tx.rfind("bestemmes")
    konklusion = tx[idx:] if idx >= 0 else tx[-1500:]
    for label, rx in _TEKST_REGLER:
        if rx.search(konklusion):
            return label
    if csv_udfald in UDFALD and csv_udfald != "Ukendt":
        return csv_udfald
    return "Ukendt"


# ── Data ──────────────────────────────────────────────────────────────────────
COLUMNS = [
    "Id", "Dato", "Titel", "Link", "Tekst", "Excerpt", "Sagsnummer",
    "Selskab", "Udfald", "Mangeltype", "Forsikringstype", "År",
]


def read_csv_rows(sti: str) -> list:
    rows = []
    csv.field_size_limit(10_000_000)
    with open(sti, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            tekst = shared.strip_html(row.get("Tekst", ""), preserve_headings=True)
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


def _data_files(root: str, tmp: str) -> list[str]:
    os.makedirs(tmp, exist_ok=True)

    def _udpak(zip_navn: str) -> str:
        zip_sti = os.path.join(root, zip_navn)
        dest = os.path.join(tmp, zip_navn[:-4])
        if not os.path.exists(dest) and os.path.exists(zip_sti):
            with zipfile.ZipFile(zip_sti) as z:
                for m in z.namelist():
                    if m.endswith(".csv"):
                        with z.open(m) as src, open(dest, "wb") as dst:
                            dst.write(src.read())
                        break
        return dest if os.path.exists(dest) else ""

    navne = (
        {os.path.basename(p) for p in _glob.glob(os.path.join(root, "ejnar_*.csv"))} |
        {os.path.basename(p)[:-4] for p in _glob.glob(os.path.join(root, "ejnar_*.csv.zip"))}
    )
    stier = []
    for navn in sorted(navne):
        repo_csv = os.path.join(root, navn)
        sti = repo_csv if os.path.exists(repo_csv) else _udpak(navn + ".zip")
        if sti:
            stier.append(sti)
    return stier


def load_data(root: str = EJNAR_DIR, tmp: str = "/tmp/ejnar_data", reader=read_csv_rows) -> pd.DataFrame:
    rows: list = []
    seen: set = set()
    for sti in _data_files(root, tmp):
        for r in reader(sti):
            if r["Link"] in seen:
                continue
            seen.add(r["Link"])
            rows.append(r)
    return prepare_frame(rows)


def prepare_frame(rows: list) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        # Tom skelet-DataFrame så UI/API ikke crasher
        df = pd.DataFrame(columns=COLUMNS)
        df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
        df["År"] = pd.Series(dtype="Int64")
        return df

    df["Id"] = [decision_id(link, i) for i, link in enumerate(df["Link"])]
    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"] = df["Dato"].dt.year.astype("Int64")

    # Klassifikation genberegnes altid ud fra titel/tekst: scraperens felter
    # er upålidelige (mangeltype = "Tag/tagdækning" på 100 % af kendelserne).
    df["Mangeltype"] = [detect_mangeltyper(t, tx) for t, tx in zip(df["Titel"], df["Tekst"])]
    df["Udfald"] = [
        detect_udfald_ejnar(t, tx, str(u or ""))
        for t, tx, u in zip(df["Titel"], df["Tekst"], df["Udfald"])
    ]

    df["Selskab"] = df["Selskab"].fillna("").astype(str)
    return df


def decision_id(link: str, fallback: int = 0) -> str:
    """Stabilt, URL-venligt ID afledt af kendelsens link."""
    base = (link or "").strip() or f"row-{fallback}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def build_index(df: pd.DataFrame):
    if df.empty:
        return None, None
    # generator (ikke liste): undgår at materialisere en hel ekstra kopi af teksten i RAM
    texts = (shared.byg_indeks_tekst(t, tx) for t, tx in
             zip(df["Titel"].astype(str), df["Tekst"].astype(str)))
    vec = shared.DeterministicTfidfVectorizer(max_features=60_000, ngram_range=(1, 2),
                          min_df=2, sublinear_tf=True, tokenizer=shared.dansk_tokenizer,
                          token_pattern=None)
    return vec, vec.fit_transform(texts)


def build_embeddings(df: pd.DataFrame):
    if df.empty or not shared.embeddings_tilgængelige():
        return None
    return shared.byg_embeddings_indeks(df, cache_key=EMBED_CACHE_KEY)


def filter_options(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"Mangeltype": [], "Selskab": []}
    return {
        "Mangeltype": sorted({m for ms in df["Mangeltype"] for m in ms}),
        "Selskab": sorted({s for s in df["Selskab"] if s}),
    }


def filter_mask(df: pd.DataFrame, år_fra=None, år_til=None, mangeltyper=None,
                selskaber=None, udfald=None) -> pd.Series:
    mask = pd.Series(True, index=df.index)
    if år_fra is not None:
        mask &= df["År"].fillna(0) >= int(år_fra)
    if år_til is not None:
        mask &= df["År"].fillna(9999) <= int(år_til)
    if mangeltyper:
        wanted = set(mangeltyper)
        mask &= df["Mangeltype"].apply(lambda mts: bool(wanted.intersection(mts)))
    if selskaber:
        mask &= df["Selskab"].isin(list(selskaber))
    if udfald:
        mask &= df["Udfald"].isin(list(udfald))
    return mask


# ── Søgning ───────────────────────────────────────────────────────────────────
def tfidf_søg(query, df, vec, mat, sub_idx=None, top_n=30, ekspander=False):
    from sklearn.metrics.pairwise import cosine_similarity
    if vec is None or mat is None:
        return df.iloc[0:0].copy()
    eff = shared.udvid_query(query) if ekspander else query
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


def relevans_søg(query: str, df: pd.DataFrame, vec, mat, embeds=None, sub_idx=None,
                 top_n: int = 200) -> list[int]:
    """Hurtig relevanssøgning uden LLM-kald (til søgefelter og API).

    Bruger den samme deterministiske hybrid-kæde som RAG-retrieval (TF-IDF,
    paragraf-BM25, metadata- og sagsnummer-routing) og fusionerer med en
    embedding-søgning *uden* HyDE, når embeddings er tilgængelige.
    På bootstrap-qrels v2 giver det nDCG@10 0,76 mod 0,59 for ren TF-IDF."""
    if vec is None or mat is None or not (query or "").strip():
        return []
    sub = sub_idx if sub_idx is not None else list(range(len(df)))
    lex = shared.hybrid_retrieval(query, df, vec, mat, None, sub_idx=sub,
                                  top_retrieve=max(60, top_n), top_final=top_n)
    if embeds is None:
        return list(lex)
    try:
        emb = [g for g, _ in shared.embedding_soeg(query, df, embeds, sub_idx=sub,
                                                   top_n=min(top_n, 100), use_hyde=False)]
    except Exception:
        emb = []
    if not emb:
        return list(lex)
    fused = shared.rrf_merge([list(lex), emb], k=60)
    return [i for i, _ in sorted(fused.items(), key=lambda x: -x[1])][:top_n]


def ordret_søg(query: str, df: pd.DataFrame, sub_idx=None) -> pd.DataFrame:
    """Ordret (case-insensitiv) frasesøgning i titel og tekst, nyeste først."""
    base = df.loc[sub_idx] if sub_idx is not None else df
    q = (query or "").strip()
    if not q:
        return base.sort_values("Dato", ascending=False)
    hit = (base["Titel"].str.contains(q, case=False, na=False, regex=False) |
           base["Tekst"].str.contains(q, case=False, na=False, regex=False))
    return base[hit].sort_values("Dato", ascending=False)


def snippet(text: str, query: str = "", width: int = 320) -> str:
    """Uddrag af ``text`` centreret om første forekomst af søgningen (eller dens ord)."""
    text = re.sub(r"\s+", " ", re.sub(r"^#{2,3} ", "", text or "", flags=re.M)).strip()
    if not text:
        return ""
    pos = -1
    if query:
        low = text.lower()
        terms = sorted(set(re.findall(r"\w{4,}", query.lower())), key=len, reverse=True)
        for t in [query.lower().strip()] + terms:
            pos = low.find(t)
            if pos >= 0:
                break
    if pos < 0:
        return text[:width] + ("…" if len(text) > width else "")
    start = max(0, pos - width // 3)
    end = min(len(text), start + width)
    return ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")


def sagsnummer_hits(query: str, df: pd.DataFrame) -> pd.DataFrame:
    """Kendelser hvis sagsnummer matcher et søgeord som "93497" eller "846/10"."""
    q = (query or "").strip()
    if not re.fullmatch(r"\d{3,6}(?:\s*\(\d+/\d+\))?|\d+/\d{2,4}", q):
        return df.iloc[0:0]
    sag = df["Sagsnummer"].astype(str)
    return df[sag.str.fullmatch(re.escape(q)) | sag.str.startswith(q + " ") | sag.str.contains(f"({q})", regex=False)]


def saml_kilder(historik, nye_hits, max_total=12):
    seen, merged = set(), []
    for rec in (nye_hits.to_dict("records") if hasattr(nye_hits, "to_dict") else nye_hits):
        lnk = rec.get("Link", "")
        if lnk and lnk not in seen:
            seen.add(lnk)
            merged.append(rec)
    for msg in reversed(historik or []):
        if msg.get("rolle") == "assistent":
            for k in msg.get("kilder", []) or []:
                lnk = k.get("Link", "")
                if lnk and lnk not in seen and len(merged) < max_total:
                    seen.add(lnk)
                    merged.append(k)
    return merged[:max_total]


def fuse_rankings(rankings: list[list[dict]], limit: int, k: int = 60) -> list[dict]:
    """Reciprocal Rank Fusion af flere resultatlister (nøgle: Link)."""
    score: dict[str, float] = {}
    first: dict[str, dict] = {}
    for ranking in rankings:
        for rank, rec in enumerate(ranking):
            key = rec.get("Link") or str(id(rec))
            score[key] = score.get(key, 0.0) + 1.0 / (k + rank + 1)
            first.setdefault(key, rec)
    order = sorted(score, key=lambda x: score[x], reverse=True)
    return [first[x] for x in order[:limit]]


def smart_retrieval(spørgsmål, df, vec, mat, ai_sub_idx, historik,
                    top_retrieve=40, top_final=8, embeds=None, filter_options=None,
                    debug: dict | None = None):
    """Fuld RAG-retrieval. Returnerer (selvstændigt spørgsmål, kilder).

    ``debug`` udfyldes med de automatisk foreslåede/anvendte metadatafiltre."""
    n_workers = 3 if filter_options else 2
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        f1 = pool.submit(shared.klassificer_query, spørgsmål)
        f2 = pool.submit(shared.omformuler_opfoelgning, spørgsmål, historik or [])
        f3 = pool.submit(shared.auto_filter_query, spørgsmål, filter_options) if filter_options else None
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

    eff_sub, prefiltered = shared.apply_auto_filters(df, ai_sub_idx, auto_filters)
    if debug is not None:
        debug.update({
            "suggested": auto_filters,
            "applied": prefiltered,
            "before": len(ai_sub_idx) if ai_sub_idx else len(df),
            "after": len(eff_sub) if eff_sub else 0,
            "query_type": qtype.get("type", ""),
            "standalone": standalone,
        })

    udvidet = shared.udvid_query(standalone)
    tfidf_query = udvidet if udvidet else standalone

    def _do(sub):
        if embeds is not None:
            fused = shared.hybrid_retrieval(tfidf_query, df, vec, mat, embeds, sub_idx=sub,
                                            top_retrieve=top_retrieve, top_final=top_retrieve)
            if fused:
                h = df.iloc[fused].copy()
                h["_score"] = [1.0] * len(h)
                return h.reset_index(drop=True)
            return df.iloc[0:0].copy()
        return tfidf_søg(tfidf_query, df, vec, mat, sub_idx=sub,
                         top_n=top_retrieve, ekspander=False)

    # Automatiske metadatafiltre er et boost, ikke et hårdt filter: vi henter både
    # i det filtrerede og det ufiltrerede korpus og fusionerer med RRF. Kendelser
    # der matcher filtret får et forspring, men fejlklassificerede kendelser
    # (fx en fugtsag med en generisk titel) kan stadig komme med.
    alle_hits = _do(ai_sub_idx)
    kand = alle_hits.to_dict("records") if len(alle_hits) > 0 else []
    if prefiltered:
        filt_hits = _do(eff_sub)
        kand = fuse_rankings([filt_hits.to_dict("records") if len(filt_hits) else [], kand],
                             limit=top_retrieve)
    rerankede = shared.llm_rerank(standalone, kand, top_n=top_final)

    alle = saml_kilder(historik or [], rerankede, max_total=max(12, top_final + 4))
    return standalone, alle


# ── Svar ──────────────────────────────────────────────────────────────────────
def _fmt_dato(value) -> str:
    try:
        return pd.Timestamp(value).strftime('%d.%m.%Y')
    except Exception:
        return "–"


def byg_prompt(spørgsmål, docs, historik=None):
    kontekst = shared.byg_fokuseret_kontekst(spørgsmål, docs, max_chunks_per_doc=3)
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {_fmt_dato(d.get('Dato'))} – {str(d.get('Titel', ''))[:80]}"
        for i, d in enumerate(docs)
    )
    return [
        {
            "type": "text",
            "text": (
                "Du er en juridisk assistent specialiseret i dansk forsikringsret og "
                "Ankenævnet for Forsikrings praksis om ejerskifteforsikring. "
                "Dine brugere er professionelle jurister og forsikringsfolk – giv "
                "præcise, faktabaserede svar.\n\n"
                "REGLER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte kendelser. Opfind ikke fakta.\n"
                "2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG sagsnumre eller datoer som reference.\n"
                "3. Svar på dansk. Begynd med afsnittet '## Kort svar' på 2–4 sætninger, der direkte "
                "besvarer spørgsmålet (ved en konkret sag: sandsynligt udfald og det afgørende moment). "
                "Uddyb derefter under overskrifter. Hold svaret fokuseret – typisk 350–750 ord; "
                "skriv hellere præcist end udtømmende.\n"
                "4. Understøt påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                "Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
                "5. Identificér mønstre på tværs af kendelserne — fast praksis vs. variation. "
                "Angiv evt. fordelingen (fx \"3 af 5 kendelser giver klager medhold\"), men tæl kun "
                "kendelser med samme juridiske spørgsmål og sammenlignelige forsikringsvilkår/dækning "
                "(fx basis vs. udvidet dækning) i samme nævner, og angiv årsspændet. Bygger en "
                "praksislinje overvejende på kendelser, der er mere end 10 år gamle, så sig det.\n"
                "6. Nævn relevant lovhjemmel (lov om forbrugerbeskyttelse §§, forsikringsaftaleloven mv.) når det fremgår.\n"
                "7. Hvis kilderne ikke besvarer spørgsmålet, skriv det eksplicit. Gæt aldrig.\n"
                "8. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering.\n"
                "9. Indeholder spørgsmålet flere led (fx dækning, følgeskader, fradrag, hvem betaler "
                "undersøgelser), så besvar hvert led for sig med egen konklusion og kilder; sig tydeligt, "
                "hvis kilderne ikke dækker et led.\n"
                "10. Handler spørgsmålet om en konkret sag eller en afgørelse, selskabet har truffet eller "
                "overvejer, så slut med '## Anbefaling': om afgørelsen efter praksis holder, bør justeres "
                "eller ændres, og hvilke oplysninger/dokumentation der evt. mangler for at afgøre det.\n\n"
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


def resumé_prompt(titel: str, tekst: str) -> str:
    kerne = shared.udtræk_kerneafsnit(tekst, max_tegn=6000)
    return f"""Lav et kort, struktureret resumé af denne kendelse fra Ankenævnet for Forsikring
om ejerskifteforsikring. Inkluder: Sagens kerne, Klagerens påstand, Selskabets påstand,
Nævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {kerne}

RESUMÉ:"""


def mistænkelige_citater(svar: str, kilder: list, spørgsmål: str = "") -> list:
    """Citater i svaret, der ikke findes i kilderne (eller i brugerens eget spørgsmål)."""
    docs = list(kilder) + ([{"Titel": "", "Tekst": spørgsmål}] if spørgsmål else [])
    try:
        return shared.valider_citationer(svar, docs)
    except Exception:
        return []


def citerede_kilder(svar: str, antal: int) -> list[int]:
    """1-baserede kildenumre, som svaret faktisk henviser til, i rækkefølge."""
    set_: list[int] = []
    for grp in re.findall(r"\[Kilde\s+([\d,\s]+)\]", svar or "", flags=re.IGNORECASE):
        for n in re.findall(r"\d+", grp):
            i = int(n)
            if 1 <= i <= antal and i not in set_:
                set_.append(i)
    return set_


# ── Samlet korpus (til API og scripts) ───────────────────────────────────────
@dataclass
class Corpus:
    df: pd.DataFrame
    vec: object = None
    mat: object = None
    embeds: object = None
    options: dict = field(default_factory=dict)

    @classmethod
    def load(cls, with_embeddings: bool = True) -> "Corpus":
        ensure_runtimes()
        df = load_data()
        vec, mat = build_index(df)
        embeds = build_embeddings(df) if with_embeddings else None
        return cls(df=df, vec=vec, mat=mat, embeds=embeds, options=filter_options(df))

    @property
    def search_mode(self) -> str:
        return "hybrid" if self.embeds is not None else "tfidf"

    def sub_idx(self, **filters) -> list | None:
        if not any(v not in (None, [], ()) for v in filters.values()):
            return None
        return self.df[filter_mask(self.df, **filters)].index.tolist()

    def find(self, key: str):
        """Slå en kendelse op på ID eller sagsnummer. Returnerer række-dict eller None."""
        key = (key or "").strip()
        if not key or self.df.empty:
            return None
        hit = self.df[self.df["Id"] == key]
        if hit.empty:
            sag = self.df["Sagsnummer"].astype(str).str.strip()
            hit = self.df[(sag == key) | sag.str.startswith(key + " ")]
        return hit.iloc[0].to_dict() if not hit.empty else None

    def retrieve(self, spørgsmål: str, historik: list | None = None, sub_idx=None):
        """Retrieval-delen af RAG-kæden. Returnerer (kilder, historik, debug)."""
        historik = list(historik or [])
        historik.append({"rolle": "bruger", "tekst": spørgsmål})
        debug: dict = {}
        _, kilder = smart_retrieval(
            spørgsmål, self.df, self.vec, self.mat,
            sub_idx if sub_idx is not None else self.df.index.tolist(),
            historik, embeds=self.embeds, filter_options=self.options, debug=debug,
        )
        return kilder, historik, debug

    @staticmethod
    def generate(spørgsmål: str, kilder: list, historik: list, on_text=None) -> dict:
        """LLM-delen: skriv svaret ud fra kilderne og kontrollér citaterne."""
        prompt = byg_prompt(spørgsmål, kilder, historik)
        if on_text is not None:
            svar = shared._llm_stream(prompt, placeholder=_CallbackPlaceholder(on_text))
        else:
            svar = shared._llm(prompt)
        return {
            "svar": svar,
            "citerede": citerede_kilder(svar, len(kilder)),
            "mistænkelige_citater": mistænkelige_citater(svar, kilder, spørgsmål),
        }

    def answer(self, spørgsmål: str, historik: list | None = None, sub_idx=None,
               on_text=None) -> dict:
        """Kør hele RAG-kæden: retrieval → LLM → citatkontrol."""
        kilder, historik, debug = self.retrieve(spørgsmål, historik, sub_idx)
        result = self.generate(spørgsmål, kilder, historik, on_text=on_text)
        result.update({"kilder": kilder, "debug": debug})
        return result


class _CallbackPlaceholder:
    """Minimal stand-in for ``st.empty()`` så streaming virker uden Streamlit."""

    def __init__(self, on_text):
        self._on_text = on_text

    def markdown(self, text, **_kwargs):
        self._on_text(text[:-1] if text.endswith("▌") else text)

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


# Dækningstype: basis vs. udvidet ejerskifteforsikring. Negationer ("uden udvidet
# dækning", "ikke tegnet udvidet") vurderes før positive formuleringer.
DAEKNING = ["Udvidet", "Basis", "Ikke angivet"]
_DAEKNING_NEG = re.compile(
    r"ikke\s+(?:har\s+|havde\s+)?(?:tegnet|købt|valgt)\s+(?:en\s+|den\s+)?(?:udvidet|tillægs)|"
    r"uden\s+(?:den\s+)?udvidet\w*\s+(?:dækning|ejerskifte|forsikring)|"
    r"(?:kun|alene)\s+(?:havde\s+)?(?:tegnet\s+)?(?:en\s+)?basis",
    re.IGNORECASE,
)
_DAEKNING_POS = re.compile(
    r"(?:har|havde|var)\s+(?:også\s+)?(?:tegnet|købt|valgt)\s+(?:en\s+|den\s+)?(?:udvidet|tillægs)|"
    r"(?:med|omfattet\s+af)\s+(?:den\s+|en\s+)?udvidet\w*\s+(?:dækning|ejerskifte|forsikring)|"
    r"udvidet\s+(?:ejerskifte)?(?:forsikring|dækning)\w*\s+(?:var|er)\s+tegnet|"
    r"udvidede\s+dækning|udvidet\s+dækning\s+(?:omfatter|dækker)",
    re.IGNORECASE,
)


# Nævnets faste sagsfremstilling: "Forsikringstageren har (tegnet) 5-årig basis
# ejerskifteforsikring" / "… ejerskifteforsikring med udvidet dækning". Den første
# sådanne oplysning om policen vejer tungest; senere omtale af "udvidet dækning" er
# ofte klagers argument eller en gengivelse af betingelserne.
# Tolerér PDF-mellemrum inde i ordet ("ejerskift eforsikri ng")
_EJF = "".join(ch + r"\s?-?\s?" for ch in "ejerskifteforsikri") + r"n\s?g\w*"
_NIVEAU_UDV = r"(?:udvide(?:t|de)|ekstrasikring)"
_NIVEAU_BAS = r"(?:basis|standard|grund)"
_DAEKNING_STÆRK = re.compile(
    rf"(?:har|havde|tegnede|tegner|tegnet|med)\s+(?:tegnet\s+|købt\s+)?(?:en\s+|den\s+)?(?:\d+\s*-?\s*årig\s+)?"
    rf"(?P<a>{_NIVEAU_UDV}|{_NIVEAU_BAS})\s*-?\s*{_EJF}|"
    rf"{_EJF}\s+(?:\(\w+\)\s+)?med\s+(?:en\s+)?(?:\d+\s*-?\s*årig\s+)?(?P<b>{_NIVEAU_UDV}|{_NIVEAU_BAS})\s*-?\s*(?:dækning)?\b|"
    rf"forsikringen\s+er\s+tegnet\s+som\s+en\s+(?P<c>{_NIVEAU_UDV}|{_NIVEAU_BAS})|"
    rf"(?:tegnet|tegnede)\s+(?:forsikringen|policen)\s+med\s+(?:en\s+)?(?P<d>{_NIVEAU_UDV}|{_NIVEAU_BAS})",
    re.IGNORECASE,
)


def detect_daekning(tekst: str, titel: str = "") -> str:
    # AKF-resuméet (titlen) først: det gengiver policens niveau kort og præcist
    t = re.sub(r"-\s*\n\s*", "", f"{titel or ''}\n{(tekst or '')[:20000]}")
    t = re.sub(r"\s+", " ", t)
    m = _DAEKNING_STÆRK.search(t)
    if m:
        niveau = (m.group("a") or m.group("b") or m.group("c") or m.group("d") or "").lower()
        # "klager ikke har tegnet en udvidet …" / "… uden udvidet dækning"
        nægtet = re.search(r"\b(?:ikke|uden)\b", t[max(0, m.start() - 30):m.start()] + m.group(0), re.I)
        return "Udvidet" if niveau.startswith(("udvide", "ekstra")) and not nægtet else "Basis"
    # Svage signaler: en nægtelse ("ikke tegnet udvidet") vejer tungere end omtale
    # af den udvidede dæknings betingelser
    if _DAEKNING_NEG.search(t):
        return "Basis"
    return "Udvidet" if _DAEKNING_POS.search(t) else "Ikke angivet"


# ── Data ──────────────────────────────────────────────────────────────────────
COLUMNS = [
    "Id", "Dato", "Titel", "Link", "Tekst", "Excerpt", "Sagsnummer",
    "Selskab", "Udfald", "Mangeltype", "Forsikringstype", "År", "Dækning",
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


_MÅNEDER = {m: i for i, m in enumerate(
    ["januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
     "september", "oktober", "november", "december"], start=1)}
_TEKSTDATO_RX = re.compile(
    r"\b(\d{1,2})\.\s*(?:(\d{1,2})\.|(" + "|".join(_MÅNEDER) + r"))\s*((?:19|20)\d{2})\b",
    re.IGNORECASE)


def _tekstdatoer(tekst: str) -> list:
    out = []
    for d, mnr, mnavn, år in _TEKSTDATO_RX.findall(str(tekst or "")):
        try:
            out.append(pd.Timestamp(int(år), int(mnr) if mnr else _MÅNEDER[mnavn.lower()], int(d)))
        except (ValueError, KeyError):
            continue
    return out


def repair_dates(datoer: pd.Series, tekster: pd.Series, sagsnumre: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Erstat scraperens fallback-datoer med et skøn.

    Nævnet træffer afgørelser på hverdage; en weekenddato, som mange kendelser
    deler, er scrapingdatoen – ikke afgørelsesdatoen. Skønnet er den seneste dato
    i kendelsens tekst (afgørelsen ligger efter alt, den omtaler) og ellers
    datoen for sagen med nærmeste sagsnummer.
    """
    datoer = datoer.copy()
    estimeret = pd.Series(False, index=datoer.index)
    antal = datoer.value_counts()
    mistænkt = datoer.notna() & (datoer.dt.dayofweek >= 5) & datoer.map(antal).fillna(0).ge(3)
    # Sagsnumre stiger over tid: nærmeste troværdige nabosag giver et skøn
    nr = pd.to_numeric(sagsnumre.astype(str).str.extract(r"^\s*(\d{4,6})")[0], errors="coerce")
    ok = datoer.notna() & ~mistænkt & nr.notna()
    ref = pd.DataFrame({"nr": nr[ok], "dato": datoer[ok]}).sort_values("nr")
    naboer = {}
    if not ref.empty:
        for i in datoer.index[mistænkt & nr.notna()]:
            pos = int(ref["nr"].searchsorted(nr[i]))
            cand = [p for p in (pos - 1, pos) if 0 <= p < len(ref)]
            best = min(cand, key=lambda p: abs(ref["nr"].iloc[p] - nr[i]))
            naboer[i] = ref["dato"].iloc[best]
    for i in datoer.index[mistænkt]:
        kandidater = [d for d in _tekstdatoer(tekster.get(i)) if pd.Timestamp(1990, 1, 1) <= d < datoer[i]]
        ny = max(kandidater) if kandidater else naboer.get(i, pd.NaT)
        datoer[i] = ny
        estimeret[i] = True
    return datoer, estimeret


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
    df["Dato"], df["DatoEstimeret"] = repair_dates(df["Dato"], df["Tekst"], df["Sagsnummer"])
    df["År"] = df["Dato"].dt.year.astype("Int64")

    # Klassifikation genberegnes altid ud fra titel/tekst: scraperens felter
    # er upålidelige (mangeltype = "Tag/tagdækning" på 100 % af kendelserne).
    df["Mangeltype"] = [detect_mangeltyper(t, tx) for t, tx in zip(df["Titel"], df["Tekst"])]
    df["Udfald"] = [
        detect_udfald_ejnar(t, tx, str(u or ""))
        for t, tx, u in zip(df["Titel"], df["Tekst"], df["Udfald"])
    ]

    df["Dækning"] = [detect_daekning(tx, t) for t, tx in zip(df["Titel"], df["Tekst"])]
    df["Selskab"] = df["Selskab"].fillna("").astype(str)
    return df


# ── Diskcache: forberedt korpus + TF-IDF-indeks ──────────────────────────────
# Tekstrensning (~25 s) og TF-IDF (~40 s) er deterministiske. De caches på disk,
# så en genstart af API'et/Streamlit tager sekunder. Nøglen dækker datafilerne, den
# kode der former resultatet og sklearn-versionen – ændres noget, bygges der nyt.
CACHE_DIR = os.environ.get("EJNAR_CACHE_DIR", "/tmp/ejnar_cache")
_CORPUS_MEMO: dict[str, tuple] = {}


def _corpus_cache_key(root: str) -> str:
    import sklearn

    h = hashlib.sha256()
    for path in sorted(_glob.glob(os.path.join(root, "ejnar_*.csv")) + _glob.glob(os.path.join(root, "ejnar_*.csv.zip"))):
        st = os.stat(path)
        h.update(f"{os.path.basename(path)}:{st.st_size}".encode())
        with open(path, "rb") as f:
            h.update(hashlib.sha256(f.read()).digest())
    for code in ("engine.py", "shared.py"):
        with open(os.path.join(EJNAR_DIR, code), "rb") as f:
            h.update(f.read())
    h.update(f"sklearn={sklearn.__version__};pandas={pd.__version__}".encode())
    return h.hexdigest()[:24]


def load_corpus_cached(root: str = EJNAR_DIR):
    """(df, vec, mat) fra hukommelse, diskcache eller – første gang – fuld opbygning."""
    import pickle

    key = _corpus_cache_key(root)
    if key in _CORPUS_MEMO:
        return _CORPUS_MEMO[key]
    path = os.path.join(CACHE_DIR, f"corpus-{key}.pkl")
    result = None
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                result = pickle.load(f)
        except Exception:
            result = None
    if result is None:
        df = load_data(root)
        vec, mat = build_index(df)
        result = (df, vec, mat)
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = path + f".{os.getpid()}.tmp"
            with open(tmp, "wb") as f:
                pickle.dump(result, f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, path)          # atomisk: ingen halve cachefiler
            for old in _glob.glob(os.path.join(CACHE_DIR, "corpus-*.pkl")):
                if old != path:
                    os.remove(old)
        except Exception:
            pass                           # cache er en optimering, aldrig et krav
    _CORPUS_MEMO.clear()
    _CORPUS_MEMO[key] = result
    return result


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
                selskaber=None, udfald=None, daekning=None) -> pd.Series:
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
    if daekning and "Dækning" in df.columns:
        mask &= df["Dækning"].isin(list(daekning))
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
    query = shared.udvid_fagtermer(query)
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


def del_spørgsmål(spørgsmål: str, max_dele: int = 3) -> list[str]:
    """Del et langt spørgsmål med flere led op i selvstændige søgeforespørgsler.

    Med konfigureret LLM bruges et billigt hjælpekald; ellers deles der på
    spørgsmålstegn. Korte spørgsmål returneres uopdelt (tom liste)."""
    q = (spørgsmål or "").strip()
    if len(q) < 140:
        return []
    svar = shared._llm_haiku(
        "Del dette spørgsmål fra en skadesbehandler om ejerskifteforsikring op i de "
        f"selvstændige juridiske delspørgsmål, det indeholder (højst {max_dele}). Hvert "
        "delspørgsmål skal være en kort, selvstændig søgeforespørgsel med sagens relevante "
        "faktum (bygningsdel, skadetype). Har spørgsmålet kun ét led, skriv: ET LED\n\n"
        f"SPØRGSMÅL: {q}\n\nDELSPØRGSMÅL (ét pr. linje, ingen nummerering):",
        max_tokens=200,
    )
    if svar and "ET LED" not in svar.upper():
        dele = [re.sub(r"^[\s\-\*\d\.\)]+", "", linje).strip() for linje in svar.splitlines()]
    else:
        # Uden LLM: del på spørgsmålstegn og på et nyt spørgsmålsled ("… – og hvilken
        # betydning har …"), så hvert led får sin egen søgning
        led = re.split(r"\?|\s[–—-]\s(?:og\s+)?(?=(?:hvilk\w*|hvad|hvordan|hvornår|hvem|om|er|kan)\b)|"
                       r";\s+(?:og\s+)?", q, flags=re.I)
        dele = [d.strip(" ,.–—-") + "?" for d in led if len(d.strip()) > 25]
        if len(dele) < 2:
            return []
    dele = [d for d in dele if 10 <= len(d) <= 400]
    return dele[:max_dele] if len(dele) >= 2 else []


def smart_retrieval(spørgsmål, df, vec, mat, ai_sub_idx, historik,
                    top_retrieve=40, top_final=8, embeds=None, filter_options=None,
                    debug: dict | None = None):
    """Fuld RAG-retrieval. Returnerer (selvstændigt spørgsmål, kilder).

    ``debug`` udfyldes med de automatisk foreslåede/anvendte metadatafiltre."""
    # Første spørgsmål i en samtale kræver ingen omskrivning, så query-udvidelse og
    # opdeling i delspørgsmål kan køre parallelt med de øvrige hjælpekald i stedet
    # for bagefter (hvert hjælpekald er en separat LLM-rundtur).
    første = not any(m.get("rolle") == "assistent" for m in (historik or []))
    with ThreadPoolExecutor(max_workers=5) as pool:
        f1 = pool.submit(shared.klassificer_query, spørgsmål)
        f2 = pool.submit(shared.omformuler_opfoelgning, spørgsmål, historik or [])
        f3 = pool.submit(shared.auto_filter_query, spørgsmål, filter_options) if filter_options else None
        f4 = pool.submit(shared.udvid_query, spørgsmål) if første else None
        f5 = pool.submit(del_spørgsmål, spørgsmål) if første else None
        qtype = f1.result()
        standalone = f2.result()
        auto_filters = f3.result() if f3 else {}
        forhånd_udvidet = f4.result() if f4 else None
        forhånd_dele = f5.result() if f5 else None
    if standalone.strip() != spørgsmål.strip():
        forhånd_udvidet = forhånd_dele = None       # omskrevet: beregn på den nye tekst

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

    udvidet = forhånd_udvidet if forhånd_udvidet is not None else shared.udvid_query(standalone)
    tfidf_query = udvidet if udvidet else standalone

    def _do(sub):
        if embeds is not None:
            fused = shared.hybrid_retrieval(shared.udvid_fagtermer(tfidf_query), df, vec, mat, embeds, sub_idx=sub,
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
    # Spørgsmål med flere led: søg også på hvert led, så kilderne dækker alle led
    # og ikke kun det, der dominerer den samlede forespørgsel.
    dele = forhånd_dele if forhånd_dele is not None else del_spørgsmål(standalone)
    if dele:
        del_rangeringer = []
        for del_q in dele:
            idx = shared.hybrid_retrieval(shared.udvid_fagtermer(del_q), df, vec, mat, embeds, sub_idx=ai_sub_idx,
                                          top_retrieve=max(20, top_retrieve // 2),
                                          top_final=max(10, top_retrieve // 3))
            if idx:
                del_rangeringer.append(df.iloc[idx].to_dict("records"))
        if del_rangeringer:
            kand = fuse_rankings([kand] + del_rangeringer, limit=top_retrieve)
        if debug is not None:
            debug["sub_questions"] = dele
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


def kilderegister(docs: list) -> str:
    """Kildeliste med dato, udfald og dækning pr. kilde og en færdig optælling.

    Modellen talte forkert, når den selv skulle opgøre udfald på tværs af 15–18
    kilder ("13 kendelser", hvor der var 12). Optællingen her er deterministisk."""
    linjer = []
    grupper: dict[str, list[int]] = {}
    for i, d in enumerate(docs, start=1):
        udfald = str(d.get("Udfald") or "").strip() or "Ukendt"
        dk = str(d.get("Dækning") or "").strip()
        tags = [f"udfald: {udfald}"] + ([f"dækning: {dk.lower()}"] if dk in ("Udvidet", "Basis") else [])
        dato = ("ca. " if d.get("DatoEstimeret") is True else "") + _fmt_dato(d.get("Dato"))
        linjer.append(f"[Kilde {i}] = {dato} – {str(d.get('Titel', ''))[:80]} ({' · '.join(tags)})")
        grupper.setdefault(udfald, []).append(i)
    if docs:
        rækkefølge = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]
        dele = [f"{label} {len(grupper[label])} ({', '.join(map(str, grupper[label]))})"
                for label in rækkefølge + sorted(set(grupper) - set(rækkefølge)) if label in grupper]
        linjer.append(f"Udfald blandt alle {len(docs)} kilder: " + "; ".join(dele) +
                      ". Brug tallene som kontrol; en praksisfordeling skal kun tælle de sammenlignelige kilder.")
    return "\n".join(linjer)


def byg_prompt(spørgsmål, docs, historik=None):
    kontekst = shared.byg_fokuseret_kontekst(spørgsmål, docs, max_chunks_per_doc=3)
    historik_tekst = ""
    if historik:
        for msg in historik[:-1]:
            rolle = "Bruger" if msg["rolle"] == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg['tekst']}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    kilde_liste = kilderegister(docs)
    return [
        {
            "type": "text",
            "text": (
                "Du er et praksisværktøj for Ankenævnet for Forsikrings kendelser om "
                "ejerskifteforsikring. Dine brugere er jurister og skadesbehandlere, der undersøger, "
                "hvordan nævnet har afgjort sager. Din opgave er at beskrive og analysere praksis "
                "præcist – ikke at afgøre brugerens konkrete sag.\n\n"
                "REGLER:\n"
                f"1. Besvar spørgsmålet KUN baseret på de {len(docs)} vedlagte kendelser. Opfind ikke fakta.\n"
                "2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG sagsnumre eller datoer som reference.\n"
                "3. Svar på dansk. Begynd med afsnittet '## Kort svar' på 2–4 sætninger om, hvor nævnet har "
                "trukket grænsen: hvad der konkret har ført til medhold, og hvad der har ført til afslag. "
                "Uddyb derefter under overskrifter. Hold svaret fokuseret – typisk 350–750 ord; "
                "skriv hellere præcist end udtømmende.\n"
                "3b. Brugerne er erfarne skadesbehandlere og jurister, der kender de almindelige principper "
                "(fx at klager bærer bevisbyrden, at der skal foreligge en skade, og at alder, slid eller en "
                "karakter i tilstandsrapporten ikke i sig selv er afgørende). Nævn sådanne principper kort – "
                "højst én sætning – og brug pladsen på skillelinjerne i netop denne type sag: hvilke konkrete "
                "forhold (fx omfang, målinger og undersøgelser, byggeår og alder, tilstandsrapportens ordlyd, "
                "årsag, dækningsniveau, beløb og fradrag) der har fået nævnet til at give medhold eller afslag, "
                "med konkrete eksempler fra kendelserne i begge retninger.\n"
                "4. Understøt påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
                "Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat. Gengiv hver "
                "kendelses udfald præcis som angivet i kildeoverskriften.\n"
                "4b. Passager mærket '(Sagsfremstilling og parternes synspunkter)' gengiver klagers eller "
                "selskabets synspunkter – tilskriv dem aldrig nævnet. Hvad nævnet lagde vægt på, fremgår af "
                "passager mærket '(Nævnets begrundelse og afgørelse)'. Nævn kun dækningsniveau (basis/udvidet), "
                "når det fremgår af kilden.\n"
                "5. Identificér mønstre på tværs af kendelserne — fast praksis vs. variation. "
                "Angiv evt. fordelingen (fx \"3 af 5 kendelser giver klager medhold\"), men tæl kun "
                "kendelser med samme juridiske spørgsmål og sammenlignelige forsikringsvilkår/dækning "
                "(fx basis vs. udvidet dækning) i samme nævner, og angiv årsspændet. Bygger en "
                "praksislinje overvejende på kendelser, der er mere end 10 år gamle, så sig det. "
                "Fremhæv kendelser, der går imod hovedlinjen, og hvad der adskilte dem. Byg kun en generel "
                "regel på flere kendelser; hviler et synspunkt på én kendelse, så skriv det (\"i én kendelse "
                "[Kilde n] …\").\n"
                "6. Nævn relevant lovhjemmel (lov om forbrugerbeskyttelse §§, forsikringsaftaleloven mv.) når det fremgår.\n"
                "7. Hvis kilderne ikke besvarer spørgsmålet, skriv det eksplicit. Gæt aldrig. Kendelserne "
                "er vedlagt som uddrag; skriv derfor \"uddragene nævner ikke …\" frem for \"kendelserne "
                "nævner ikke …\", og brug kun \"kun\"/\"ingen\" om kilderne, når det gælder alle uddrag.\n"
                "8. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering.\n"
                "9. Indeholder spørgsmålet flere led (fx dækning, følgeskader, fradrag, hvem betaler "
                "undersøgelser), så beskriv praksis for hvert led for sig med kilder; sig tydeligt, "
                "hvis kilderne ikke dækker et led.\n"
                "10. Beskriver brugeren en konkret sag, så afgør den ikke og forudsig ikke udfaldet. "
                "Slut i stedet med '## Praksis holdt op mod sagen': hvilke kendelser der ligner mest, "
                "hvilke momenter nævnet har lagt vægt på i dem, hvilke forskelle i faktum der kan få "
                "betydning, og hvilke oplysninger der er relevante at få belyst for at sammenligne "
                "med praksis.\n\n"
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


# Udsagn om en bestemt kendelses udfald (datid: "fik", "gav", "blev" – ikke generelle "får typisk")
_PARTER = r"(?:klage(?:r|ren|rne)|forsikringstage(?:r|ren)|købe(?:r|ren|rne)|kunde(?:n|rne))"
_PÅSTAND_RX = [
    ("Delvis medhold", re.compile(r"\b(?:fik|gav)\b[^.\[\]\n]{0,30}?\bdelvis(?:t)?\s+medhold\b", re.I)),
    ("Ikke medhold", re.compile(
        rf"\b{_PARTER}\s+fik\s+ikke\s+medhold|\bfik\s+{_PARTER}\s+ikke\s+medhold|\bgav\s+ikke\s+(?:\d+\s+|en\s+)?{_PARTER}\s+medhold|"
        r"\bselskabet\s+fik\s+medhold|\bgav\s+selskabet\s+medhold|\bgav\s+ikke\s+medhold|"
        r"\bgav\s+medhold\s+til\s+selskabet|"
        r"\bklagen\s+blev\s+ikke\s+taget\s+til\s+følge|\bselskabet\s+blev\s+frifundet", re.I)),
    ("Medhold", re.compile(
        rf"\b{_PARTER}\s+fik\s+(?:fuldt\s+|fuld\s+|helt\s+)?medhold|\bfik\s+{_PARTER}\s+(?:fuldt\s+|helt\s+)?medhold|\bgav\s+(?:\d+\s+|en\s+)?{_PARTER}\s+(?:fuldt\s+|helt\s+)?medhold|"
        r"\bklagen\s+blev\s+taget\s+til\s+følge|\bgav\s+(?:fuldt\s+|helt\s+)?medhold\b(?!\s+til\s+selskab)", re.I)),
]
_KLAUSUL_RX = re.compile(r"(?<=[.!?;:])\s+|\n+|,\s+(?=(?:men|mens|hvorimod|hvor|og\s+i)\b)|\s+(?=(?:mens|hvorimod)\b)")
# Påstand → faktiske udfald, der er uforenelige med den. "Delvis medhold" i kilden er
# foreneligt med alt, fordi svaret kan tale om ét af sagens led.
_ETIKET_RX = re.compile(
    r"\[Kilde\s+(\d+)\]\s*(?:\(\s*|:\s*)(delvis(?:t)?\s+medhold|ikke\s+medhold|medhold)\b(?!\s+til\s+selskab)\)?", re.I)
_UFORENELIG = {"Medhold": {"Ikke medhold"}, "Ikke medhold": {"Medhold"}, "Delvis medhold": {"Ikke medhold", "Medhold"}}


def udfaldskonflikter(svar: str, kilder: list) -> list[dict]:
    """Udsagn i svaret om en kildes udfald, der strider mod kendelsens faktiske udfald.

    Den alvorligste fejl i et praksisværktøj er at gengive forkert, hvad nævnet afgjorde.
    Kun udsagn i datid om de kilder, der citeres i samme sætningsled, kontrolleres.
    """
    konflikter, set_ = [], set()

    def tjek(n: int, påstand: str, tekst: str) -> None:
        if not 1 <= n <= len(kilder) or (n, påstand) in set_:
            return
        faktisk = str(kilder[n - 1].get("Udfald") or "")
        if faktisk in _UFORENELIG[påstand]:
            set_.add((n, påstand))
            konflikter.append({"kilde": n, "påstand": påstand, "faktisk": faktisk,
                               "tekst": re.sub(r"\s+", " ", tekst).strip()[:240]})

    # Eksplicitte etiketter: "[Kilde 8] (Medhold)" / "[Kilde 8]: ikke medhold"
    for m in _ETIKET_RX.finditer(svar or ""):
        label = m.group(2).lower()
        påstand = "Delvis medhold" if label.startswith("delvis") else (
            "Ikke medhold" if label.startswith("ikke") else "Medhold")
        tjek(int(m.group(1)), påstand, m.group(0))
    rest = _ETIKET_RX.sub(" ", svar or "")
    for klausul in _KLAUSUL_RX.split(rest):
        påstande = sorted((m.start(), label) for label, rx in _PÅSTAND_RX for m in rx.finditer(klausul))
        # "delvis medhold" indeholder "medhold": behold kun det længste match pr. position
        påstande = [p for i, p in enumerate(påstande) if i == 0 or p[0] != påstande[i - 1][0]]
        if not påstande:
            continue
        for ref in KILDE_REF_RX.finditer(klausul):
            # Henvisningen hører til den nærmeste påstand før den (ellers den første efter)
            før = [label for pos, label in påstande if pos < ref.start()]
            påstand = før[-1] if før else påstande[0][1]
            for n in kildenumre(ref.group(1)):
                tjek(n, påstand, klausul)
    return konflikter


KILDE_REF_RX = re.compile(r"\[Kilde[r]?\s+(\d[^\]]{0,80})\]", re.IGNORECASE)


def kildenumre(henvisning: str) -> list[int]:
    """Numrene i en henvisning: "3", "3, 5 og 7", "2–8" og "14, basisdækning"."""
    out: list[int] = []
    for a, b, enkelt in re.findall(r"(\d+)\s*[–—-]\s*(\d+)|(\d+)", henvisning or ""):
        start, slut = (int(a), int(b)) if a else (int(enkelt), int(enkelt))
        for n in range(start, min(slut, start + 30) + 1):
            if n not in out:
                out.append(n)
    return out


def citerede_kilder(svar: str, antal: int) -> list[int]:
    """1-baserede kildenumre, som svaret faktisk henviser til, i rækkefølge."""
    set_: list[int] = []
    for grp in KILDE_REF_RX.findall(svar or ""):
        for i in kildenumre(grp):
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
        df, vec, mat = load_corpus_cached()
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
            "udfaldskonflikter": udfaldskonflikter(svar, kilder),
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

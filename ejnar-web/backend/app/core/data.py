"""Indlæsning og berigelse af kendelses-data + TF-IDF-indeks.

Samme logik/dedup som Streamlit-appens load_data() (dedup på Link, ikke titel —
det er den fejl der i sin tid gjorde embedding-indekset ubrugeligt, se Ejnars
øvrige commit-historik). In-process cache i stedet for st.cache_resource:
data indlæses én gang ved opstart og holdes i hukommelsen i processens levetid."""
from __future__ import annotations

import csv
import glob
import os
import re
import threading
import zipfile
from dataclasses import dataclass, field

import pandas as pd

from ..config import get_settings
from .detect import detect_mangeltyper, detect_opførelsesår, detect_udfald_ejnar
from .search import byg_tfidf_index
from .text import strip_html

csv.field_size_limit(10_000_000)

_lock = threading.Lock()
_cache: "Store | None" = None


@dataclass
class Store:
    df: pd.DataFrame
    vec: object
    mat: object
    mangeltyper: list = field(default_factory=list)
    selskaber: list = field(default_factory=list)
    udfald: list = field(default_factory=list)
    # Link → række-position i df. Bruges til at re-hydrere kilder der har været
    # en tur i browseren (chat-historik, notat-eksport): frontenden ser den
    # slanke Kendelse-form (uden Tekst), men den porterede RAG/notat-logik skal
    # bruge den fulde række med Tekst — vi slår den op igen på Link.
    link_index: dict = field(default_factory=dict)


def _find_csv(data_dir: str) -> str:
    navn = "ejnar_ejerskifteforsikring.csv"
    sti = os.path.join(data_dir, navn)
    if os.path.exists(sti):
        return sti
    zsti = sti + ".zip"
    if os.path.exists(zsti):
        tmp_dir = "/tmp/ejnar_web_data"
        os.makedirs(tmp_dir, exist_ok=True)
        dest = os.path.join(tmp_dir, navn)
        if not os.path.exists(dest):
            with zipfile.ZipFile(zsti) as z:
                m = next(n for n in z.namelist() if n.endswith(".csv"))
                with z.open(m) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
        return dest
    raise FileNotFoundError(
        f"Fandt hverken {navn} eller {navn}.zip i {data_dir}. "
        "Sæt EJNAR_DATA_DIR til mappen med Ejnars CSV-data."
    )


def _load_rows(sti: str) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    with open(sti, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            link = row.get("Link", "")
            if link in seen:
                continue
            seen.add(link)
            tekst = strip_html(row.get("Tekst", ""), preserve_headings=True)
            excerpt = re.sub(r"^#{2,3} ", "", tekst, flags=re.M).replace("\n", " ")
            excerpt = re.sub(r"\s+", " ", excerpt).strip()
            mangeltype = row.get("Mangeltype", "")
            mangeltype_list = [m.strip() for m in mangeltype.split(",") if m.strip()] \
                if mangeltype else []
            rows.append({
                "Dato": row.get("Dato", ""),
                "Titel": row.get("Titel", ""),
                "Link": link,
                "Tekst": tekst,
                "Excerpt": excerpt[:280],
                "Sagsnummer": row.get("Sagsnummer", ""),
                "Selskab": row.get("Selskab", ""),
                "Udfald": row.get("Udfald", ""),
                "Mangeltype": mangeltype_list,
                "Forsikringstype": row.get("Forsikringstype", "Ejerskifteforsikring"),
            })
    return rows


def _build() -> Store:
    settings = get_settings()
    csv_glob = glob.glob(os.path.join(settings.data_dir, "ejnar_*.csv")) + \
        glob.glob(os.path.join(settings.data_dir, "ejnar_*.csv.zip"))
    if not csv_glob:
        raise FileNotFoundError(f"Ingen ejnar_*.csv(.zip) fundet i {settings.data_dir}")

    sti = _find_csv(settings.data_dir)
    rows = _load_rows(sti)
    df = pd.DataFrame(rows)
    if df.empty:
        raise RuntimeError("CSV-data er tom.")

    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"] = df["Dato"].dt.year.astype("Int64")
    df["Opførelsesår"] = df["Tekst"].apply(detect_opførelsesår).astype("Int64")

    needs_mt = df["Mangeltype"].apply(lambda x: not x)
    if needs_mt.any():
        df.loc[needs_mt, "Mangeltype"] = df.loc[needs_mt].apply(
            lambda r: detect_mangeltyper(r["Titel"], r["Tekst"]), axis=1)
    needs_ud = df["Udfald"].fillna("").eq("") | df["Udfald"].eq("Ukendt")
    if needs_ud.any():
        df.loc[needs_ud, "Udfald"] = df.loc[needs_ud].apply(
            lambda r: detect_udfald_ejnar(r["Titel"], r["Tekst"]), axis=1)

    df["Selskab"] = df["Selskab"].fillna("").astype(str)
    df = df.reset_index(drop=True)

    vec, mat = byg_tfidf_index(df)

    mangeltyper = sorted({m for ms in df["Mangeltype"] for m in ms})
    selskaber = sorted({s for s in df["Selskab"] if s})
    udfald = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]

    # df er reset_index(drop=True), så positionen == label-index. Sidste vinder
    # ved dublet-links (skulle ikke ske efter Link-dedup i _load_rows).
    link_index = {lnk: i for i, lnk in enumerate(df["Link"]) if lnk}

    return Store(df=df, vec=vec, mat=mat, mangeltyper=mangeltyper,
                 selskaber=selskaber, udfald=udfald, link_index=link_index)


def get_store() -> Store:
    """Hent (og cache) det indlæste datasæt. Trådsikker første-kald-init —
    matcher Streamlit-appens @st.cache_resource-adfærd uden Streamlit."""
    global _cache
    if _cache is None:
        with _lock:
            if _cache is None:
                _cache = _build()
    return _cache


def reload_store() -> Store:
    """Tving genindlæsning — kald efter opdateret CSV uden at genstarte processen."""
    global _cache
    with _lock:
        _cache = _build()
    return _cache

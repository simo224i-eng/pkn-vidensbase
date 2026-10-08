"""Nævnspraksis til screeningstjekket: underkendte sager med kontrollerede citater.

Data bygges af `byg_tjekliste.py` til data/praksis.json ud fra trin 2-analysen
(analyser/miljoevurdering/v2/deep_v2.jsonl). Kun citater, der er fundet ordret i
afgørelsen, kommer med. Søgningen kan udelukke bestemte afgørelser (bruges i test,
så en sag ikke kan finde sin egen afgørelse).

Lighed beregnes ud fra tre ting (revisionen i runde 1 viste, at fejlbeskrivelsen alene
gav eksempler fra helt andre slags projekter):
- fejlen: BM25 mellem svagheden og nævnets fejlbeskrivelse/citat,
- sagen: BM25 mellem dokumentets indledning og sagens titel/resumé,
- samme dokumenttype og samme projekttype giver et tillæg.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .bm25 import BM25

DATA = Path(__file__).resolve().parent / "data"

# Projekttyper (samme værdier som trin 2) genkendt ud fra dokumentets tekst
PROJEKTTYPER = [
    ("vindmoeller", r"vindmølle|vindenergi|møllepark"),
    ("solceller", r"solcelle|solenergi|solpark|PV-anlæg"),
    ("husdyr_landbrug", r"husdyrbrug|stald|dyreenheder|gylle|svineproduktion|kvæg"),
    ("raastof", r"råstof|grusgrav|sandgrav|indvinding af (sand|grus|ler)"),
    ("vej_infrastruktur", r"\bvej(anlæg|projekt|en)\b|cykelsti|omfartsvej|bro\b|jernbane|parkeringsplads|havn"),
    ("vand_natur_klima", r"vandløb|vådområde|klimatilpasning|regnvandsbassin|spildevand|kystbeskyttelse|skovrejsning|vandindvinding|sø\b|dambrug"),
    ("energi_oevrig", r"biogas|fjernvarme|varmepumpe|elkabel|transformer|energianlæg|PtX|brint"),
    ("erhverv_industri", r"virksomhed|erhvervsområde|industri|lager|produktion|fabrik|logistik"),
    ("fritid_turisme", r"ferie|camping|hotel|golf|motorsport|motocross|forlystelse|padel|tennis|stadion|koncert|naturlegeplads|sommerhus"),
    ("bolig_byudvikling", r"bolig|etagebyggeri|rækkehus|parcelhus|byudvikling|lokalplan for .*bolig"),
]


def projekttype(tekst: str) -> str | None:
    t = (tekst or "")[:6000]
    tal = [(len(re.findall(rx, t, re.I)), navn) for navn, rx in PROJEKTTYPER]
    n, navn = max(tal)
    return navn if n else None


@lru_cache(maxsize=1)
def sager() -> list[dict]:
    p = DATA / "praksis.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@lru_cache(maxsize=1)
def originaler() -> dict[str, list[dict]]:
    """Links til kommunernes oprindelige dokumenter pr. sag (tools/originaler/byg_indeks.py)."""
    p = DATA / "originaler.json"
    if not p.exists():
        return {}
    alle = json.loads(p.read_text(encoding="utf-8"))
    return {k: [l for l in v if l["sikkerhed"] in ("høj", "middel", "kontrolleret")] for k, v in alle.items()}


def sag(sid: str) -> dict | None:
    s = next((x for x in sager() if x["id"] == sid), None)
    if s is None:
        return None
    return {**s, "originaler": originaler().get(sid, [])}


@lru_cache(maxsize=1)
def _fejl() -> list[tuple[dict, dict]]:
    """(sag, fejl) for alle fejl med kontrolleret nævnscitat."""
    return [(s, f) for s in sager() for f in s["fejl"]]


@lru_cache(maxsize=1)
def _idx() -> BM25:
    return BM25([f"{f['fejl']} {f.get('tjekpunkt', '')} {f['citat_naevn']}" for s, f in _fejl()])


@lru_cache(maxsize=1)
def _sag_idx() -> BM25:
    return BM25([f"{s['titel']} {s.get('resume', '')}" for s, f in _fejl()])


def lignende(q: str, kategorier: list[str] | None = None, dokumenttype: str | None = None,
             k: int = 3, udeluk: set[str] | None = None, kontekst: str = "",
             ptype: str | None = None) -> list[dict]:
    """Lignende underkendte sager for en svaghed.

    q: svagheden (fx punktets søgetekst + citatet), kontekst: dokumentets indledning."""
    par = _fejl()
    udeluk = udeluk or set()

    def ok(i: int) -> bool:
        s, f = par[i]
        if s["id"] in udeluk:
            return False
        if kategorier and f["fejlkategori"] not in kategorier:
            return False
        return True

    fejl_sc = dict(_idx().search(q, k=200, filt=ok))
    if not fejl_sc:
        return []
    sag_sc = dict(_sag_idx().search(kontekst, k=400, filt=ok)) if kontekst else {}
    mf = max(fejl_sc.values()) or 1
    ms = max(sag_sc.values()) if sag_sc else 1
    ptype = ptype or (projekttype(kontekst) if kontekst else None)
    samlet = []
    for i, sc in fejl_sc.items():
        s, f = par[i]
        v = sc / mf + 0.6 * (sag_sc.get(i, 0) / ms if ms else 0)
        v += 0.35 * (s.get("dokumenttype") == dokumenttype) + 0.35 * (bool(ptype) and s.get("projekttype") == ptype)
        v += 0.1 * bool(f.get("afgoerende"))
        samlet.append((i, v))
    samlet.sort(key=lambda x: -x[1])
    ud, set_ = [], set()
    for i, sc in samlet:
        s, f = par[i]
        if s["id"] in set_:
            continue
        set_.add(s["id"])
        ud.append({"id": s["id"], "naevn": s["naevn"], "dato": s["dato"], "titel": s["titel"],
                   "link": s["link"], "fejl": f["fejl"], "citat": f["citat_naevn"],
                   "regel": f.get("regel", ""), "kategori": f["fejlkategori"], "score": round(sc, 2),
                   "projekttype": s.get("projekttype"), "dokumenttype": s.get("dokumenttype"),
                   "originaler": originaler().get(s["id"], [])[:2]})
        if len(ud) >= k:
            break
    return ud


def hyppighed() -> dict[str, dict]:
    """Antal sager pr. fejlkategori og dokumenttype (til tjeklisten og prioritering)."""
    ud: dict[str, dict] = {}
    for s in sager():
        for kat in {f["fejlkategori"] for f in s["fejl"]}:
            d = ud.setdefault(kat, {"i_alt": 0})
            d["i_alt"] += 1
            d[s.get("dokumenttype") or "andet"] = d.get(s.get("dokumenttype") or "andet", 0) + 1
    return ud

"""Nævnspraksis til screeningstjekket: underkendte sager med kontrollerede citater.

Data bygges af `byg_tjekliste.py` til data/praksis.json ud fra trin 2-analysen
(analyser/miljoevurdering/v2/deep_v2.jsonl). Kun citater, der er fundet ordret i
afgørelsen, kommer med. Søgningen kan udelukke bestemte afgørelser (bruges i test,
så en sag ikke kan finde sin egen afgørelse).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .bm25 import BM25

DATA = Path(__file__).resolve().parent / "data"


@lru_cache(maxsize=1)
def sager() -> list[dict]:
    p = DATA / "praksis.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


@lru_cache(maxsize=1)
def _fejl() -> list[tuple[dict, dict]]:
    """(sag, fejl) for alle fejl med kontrolleret nævnscitat."""
    return [(s, f) for s in sager() for f in s["fejl"]]


@lru_cache(maxsize=1)
def _idx() -> BM25:
    return BM25([f"{s['titel']} {f['fejl']} {f.get('tjekpunkt', '')} {f['citat_naevn']}" for s, f in _fejl()])


def lignende(q: str, kategorier: list[str] | None = None, dokumenttype: str | None = None,
             k: int = 3, udeluk: set[str] | None = None) -> list[dict]:
    """Lignende underkendte sager for en svaghed: søg i fejlbeskrivelser og nævnets citater."""
    par = _fejl()
    udeluk = udeluk or set()

    def ok(i: int) -> bool:
        s, f = par[i]
        if s["id"] in udeluk:
            return False
        if kategorier and f["fejlkategori"] not in kategorier:
            return False
        return True

    res = _idx().search(q, k=60, filt=ok)
    # Foretræk samme dokumenttype, men tag andre med, hvis der ikke er nok
    res.sort(key=lambda r: (-(par[r[0]][0].get("dokumenttype") == dokumenttype), -r[1]))
    ud, set_ = [], set()
    for i, sc in res:
        s, f = par[i]
        if s["id"] in set_:
            continue
        set_.add(s["id"])
        ud.append({"id": s["id"], "naevn": s["naevn"], "dato": s["dato"], "titel": s["titel"],
                   "link": s["link"], "fejl": f["fejl"], "citat": f["citat_naevn"],
                   "regel": f.get("regel", ""), "kategori": f["fejlkategori"], "score": round(sc, 2)})
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

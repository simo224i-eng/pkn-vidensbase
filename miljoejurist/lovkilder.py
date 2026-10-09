"""Lov, vejledning og EU-domme som opslagbare og søgbare tekststykker.

Kilderne ligger i lovgrundlag/ (fetch_lovgrundlag.py) og eu_domme/ (fetch_eu_domme.py).
Hvert stykke har en henvisning, som kan vises i rapporten ("Miljøvurderingsloven § 21,
stk. 2"), et link og den ordrette tekst, så citater kan kontrolleres.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .bm25 import BM25

REPO = Path(__file__).resolve().parents[1]
LOV_DIR = REPO / "lovgrundlag"
EU_DIR = REPO / "eu_domme"

# Kort navn i rapporten og ord, som henvisninger i afgørelser bruger
NAVNE = {
    "mvl": ("Miljøvurderingsloven", r"miljøvurderingslov\w*|VVM-lov\w*"),
    "mvb": ("Miljøvurderingsbekendtgørelsen", r"miljøvurderingsbekendtgørelse\w*"),
    "habitatbek": ("Habitatbekendtgørelsen", r"habitatbekendtgørelse\w*"),
    "planlov": ("Planloven", r"planlov\w*"),
    "planlov_habitat_bek": ("Planhabitatbekendtgørelsen", r"planhabitatbekendtgørelse\w*"),
    "nbl": ("Naturbeskyttelsesloven", r"naturbeskyttelseslov\w*"),
    "husdyrlov": ("Husdyrbrugloven", r"husdyrbrug(s)?lov\w*"),
}
LOVE = set(NAVNE) | {"mvl_bilag2_aendring_2025"}


@dataclass
class Stykke:
    kilde: str      # kode, fx "mvl", "vejl_mv_projekter", "C-127/02"
    ref: str        # læsbar henvisning
    url: str
    tekst: str
    type: str       # lov | vejledning | eu


def _index() -> list[dict]:
    p = LOV_DIR / "index.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _lov_stykker(kode: str, navn: str, url: str, tekst: str) -> list[Stykke]:
    """Én post pr. paragraf (med alle stykker) og én pr. bilag."""
    ud = []
    bilag_start = re.search(r"(?m)^## Bilag", tekst)
    hoved = tekst[: bilag_start.start()] if bilag_start else tekst
    for m in re.finditer(r"(?ms)^(§ \d+ ?[a-z]?)\. (.*?)(?=^§ \d+ ?[a-z]?\. |^## |\Z)", hoved):
        nr = m.group(1).replace("  ", " ")
        ud.append(Stykke(kode, f"{navn} {nr}", url, f"{nr}. {m.group(2).strip()}", "lov"))
    if bilag_start:
        for m in re.finditer(r"(?ms)^## (Bilag \d+[a-z]?)[^\n]*\n(.*?)(?=^## Bilag|\Z)", tekst[bilag_start.start():]):
            ud.append(Stykke(kode, f"{navn} {m.group(1).lower()}", url, m.group(0).strip(), "lov"))
    return ud


def _vejl_stykker(kode: str, navn: str, url: str, tekst: str, maks: int = 1800) -> list[Stykke]:
    """Afsnit efter "## "-overskrifter; lange afsnit deles ved afsnitsskift."""
    ud = []
    tekst = tekst.split("\n## Noter\n")[0]
    dele = re.split(r"(?m)^## (.*)$", tekst)
    sidste_nr = ""
    for i in range(1, len(dele) - 1, 2):
        overskrift, krop = dele[i].strip(), dele[i + 1].strip()
        if re.match(r"^\d+(\.\d+)+\.", overskrift):
            sidste_nr = overskrift
        if len(krop) < 60:          # indholdsfortegnelse og tomme overskrifter
            continue
        ref = f"{navn}, afsnit {sidste_nr or overskrift}"
        if sidste_nr and overskrift != sidste_nr:
            ref += f" ({overskrift})"
        buf = ""
        for afsnit in krop.split("\n\n"):
            if buf and len(buf) + len(afsnit) > maks:
                ud.append(Stykke(kode, ref, url, buf.strip(), "vejledning"))
                buf = ""
            buf += afsnit + "\n\n"
        if buf.strip():
            ud.append(Stykke(kode, ref, url, buf.strip(), "vejledning"))
    return ud


def _eu_stykker() -> list[Stykke]:
    p = EU_DIR / "index.json"
    if not p.exists():
        return []
    ud = []
    for d in json.loads(p.read_text(encoding="utf-8")):
        tekst = (EU_DIR / d["fil"]).read_text(encoding="utf-8")
        # Præmisserne er linjer med et nummer alene. Tal midt i en sætning (fx "stk.\n1, litra d)")
        # ligner også præmisnumre, så kun fortløbende numre, der efterfølges af stort bogstav, tælles.
        starter, næste = [], 1
        for m in re.finditer(r"(?m)^(\d{1,3})\n(?=[A-ZÆØÅ»\"(])", tekst):
            n = int(m.group(1))
            if næste <= n <= næste + 4:
                starter.append((n, m.start(), m.end()))
                næste = n + 1
        for j, (n, s0, e0) in enumerate(starter):
            slut = starter[j + 1][1] if j + 1 < len(starter) else len(tekst)
            ud.append(Stykke(d["sag"], f"EU-Domstolens dom i sag {d['sag']}, præmis {n}",
                             d["url"], tekst[e0:slut].strip()[:2500], "eu"))
        if not any(s.kilde == d["sag"] for s in ud):
            for j in range(0, len(tekst), 1500):
                ud.append(Stykke(d["sag"], f"EU-Domstolens dom i sag {d['sag']}", d["url"], tekst[j:j + 1500], "eu"))
    return ud


@lru_cache(maxsize=1)
def alle() -> list[Stykke]:
    ud = []
    for d in _index():
        f = LOV_DIR / f"{d['kode']}.txt"
        if not f.exists():
            continue
        tekst = f.read_text(encoding="utf-8")
        navn = NAVNE.get(d["kode"], (d["navn"], ""))[0]
        if d["kode"] in LOVE:
            ud += _lov_stykker(d["kode"], navn, d["url"], tekst)
        else:
            ud += _vejl_stykker(d["kode"], d["navn"], d["url"], tekst)
    ud += _eu_stykker()
    return ud


@lru_cache(maxsize=1)
def _bm25() -> BM25:
    return BM25([f"{s.ref}\n{s.tekst}" for s in alle()])


def søg(q: str, k: int = 5, typer: tuple[str, ...] = ("lov", "vejledning", "eu"),
        kilder: tuple[str, ...] | None = None) -> list[Stykke]:
    st = alle()
    res = _bm25().search(q, k=k, filt=lambda i: st[i].type in typer and (not kilder or st[i].kilde in kilder))
    return [st[i] for i, _ in res]


def slå_op(kode: str, nr: str) -> Stykke | None:
    """slå_op("mvl", "§ 21") eller slå_op("mvl", "bilag 6")."""
    nr = nr.strip().lower().replace("§", "§ ").replace("  ", " ")
    for s in alle():
        if s.kilde != kode:
            continue
        if s.ref.lower().endswith(" " + nr) or s.ref.lower().endswith(nr):
            return s
    return None


_REF_RE = re.compile(
    r"(?P<lov>" + "|".join(f"(?:{v[1]})" for v in NAVNE.values()) + r")\s+"
    r"(?:(?P<para>§\s*\d+\s?[a-z]?)(?:,\s*stk\.\s*(?P<stk>\d+))?|(?P<bilag>bilag\s+\d+))", re.I)
_PRE_RE = re.compile(r"(?P<para>§\s*\d+\s?[a-z]?)(?:,\s*stk\.\s*(?P<stk>\d+))?(?:,\s*nr\.\s*\d+)?,?\s+i\s+(?P<lov>"
                     + "|".join(f"(?:{v[1]})" for v in NAVNE.values()) + r")", re.I)


def find_henvisninger(tekst: str) -> list[tuple[str, str]]:
    """Lovhenvisninger i fri tekst -> [(kode, "§ 21" | "bilag 6")]."""
    ud = []
    for rx in (_REF_RE, _PRE_RE):
        for m in rx.finditer(tekst or ""):
            lov = m.group("lov").lower()
            kode = next((k for k, v in NAVNE.items() if re.fullmatch(v[1], lov, re.I)), None)
            if not kode:
                continue
            nr = (m.groupdict().get("para") or m.groupdict().get("bilag") or "").lower()
            nr = re.sub(r"§\s*", "§ ", nr).strip()
            if (kode, nr) not in ud:
                ud.append((kode, nr))
    return ud

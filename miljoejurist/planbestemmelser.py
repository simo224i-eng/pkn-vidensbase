"""Planens rammer: hvad lokalplanen/planforslaget faktisk muliggør.

En screening eller miljørapport skal vurdere det, planen muliggør (anvendelser, omfang, højder, hele
planområdet), ikke kun det projekt, kommunen forventer. Modulet henter planens tekst (uploadet af brugeren
eller hentet fra plandata.dk via planens doklink), finder bestemmelserne og trækker nøgletal ud med ordrette
sætninger, så modellen kan sammenligne dem med dokumentet.

Planerne gemmes kun i en lokal cache (miljoejurist/cache/, gitignoreret).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import requests

from .dokument import læs

CACHE = Path(__file__).resolve().parent / "cache" / "planer"
UA = {"User-Agent": "Miljoejuristen/1.0 (screeningstjek; kontakt via projektets repo)"}
MAKS_UDDRAG = 24000

_START = re.compile(r"(?im)^\s*§\s*1\.?\s*(lokalplanens\s+|planens\s+)?formål\b")
_BESTEMMELSER = re.compile(r"(?im)^\s*(lokalplan)?bestemmelser\s*$|^\s*lokalplanens bestemmelser\b")
_SLUT = re.compile(r"(?im)^\s*(vedtagelses(påtegning)?|vedtagelse\b|forslag til lokalplan .{0,80} er vedtaget|"
                   r"vedtaget af .{0,40}byråd|endelig vedtagelse)")

NØGLE = [
    ("bebyggelsesprocent", r"bebyggelsesprocent"),
    ("etager", r"\b(\d+|én|en|to|tre|fire|fem|seks|syv|otte|ni|ti)\s*(½\s*)?etager?\b"),
    ("højde", r"(bygnings|facade|total)?højde[^.]{0,80}?\d+(?:[,.]\d+)?\s*m\b"),
    ("etageareal", r"\d[\d.]*\s*(etagemeter|etage-?m2|m2 etageareal|m² etageareal|m2 bruttoetageareal)"),
    ("boliger", r"\b\d+\s+(boliger|boligenheder)\b"),
    ("areal", r"\b\d+(?:[,.]\d+)?\s*(ha|hektar)\b"),
    ("anvendelse", r"(må kun anvendes til|anvendelse(n)? fastlægges til|udlægges til)"),
    ("byggefelt", r"byggefelt"),
]


@dataclass
class Plan:
    titel: str
    kilde: str                  # upload | plandata
    url: str | None
    tekst: str                  # hele planens tekst (bruges til citatkontrol)
    uddrag: str                 # bestemmelserne (eller de relevante afsnit)
    nøgletal: list[dict] = field(default_factory=list)  # [{"emne", "sætning"}], sætningerne står ordret i teksten

    def til_json(self) -> dict:
        return {"titel": self.titel, "kilde": self.kilde, "url": self.url, "tegn": len(self.tekst),
                "uddrag_tegn": len(self.uddrag), "nøgletal": self.nøgletal}


def uddrag(tekst: str) -> str:
    """Planens bestemmelser (fra § 1 Formål til vedtagelsespåtegningen). Ellers afsnit med nøgleord."""
    starter = list(_START.finditer(tekst))
    if starter:
        # Første § 1 efter overskriften "Bestemmelser", ellers den sidste § 1 (redegørelsen står først)
        b = _BESTEMMELSER.search(tekst)
        s = next((m for m in starter if b and m.start() > b.start()), starter[-1] if len(starter) > 1 else starter[0])
        slut = _SLUT.search(tekst, s.start() + 50)
        return tekst[s.start(): slut.start() if slut else s.start() + MAKS_UDDRAG][:MAKS_UDDRAG]
    rx = re.compile("|".join(r for _, r in NØGLE), re.I)
    afsnit = [a for a in re.split(r"\n\s*\n", tekst) if rx.search(a)]
    return "\n\n".join(afsnit)[:MAKS_UDDRAG // 2]


def nøgletal(tekst: str, maks: int = 14) -> list[dict]:
    from .dokument import sætninger
    ud, set_ = [], set()
    for s in sætninger(tekst):
        for emne, rx in NØGLE:
            if re.search(rx, s.tekst, re.I) and s.tekst not in set_ and len(s.tekst) < 400:
                set_.add(s.tekst)
                ud.append({"emne": emne, "sætning": s.tekst.strip()})
                break
        if len(ud) >= maks:
            break
    return ud


def fra_tekst(tekst: str, titel: str, kilde: str = "upload", url: str | None = None) -> Plan:
    u = uddrag(tekst)
    return Plan(titel=titel, kilde=kilde, url=url, tekst=tekst, uddrag=u, nøgletal=nøgletal(u or tekst))


def hent(doklink: str, titel: str) -> Plan | None:
    """Hent planens PDF fra plandata.dk (cache på disk)."""
    if not doklink or not doklink.startswith("http"):
        return None
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / (hashlib.sha1(doklink.encode()).hexdigest()[:16] + ".pdf")
    if not p.exists():
        try:
            r = requests.get(doklink, headers=UA, timeout=90)
        except requests.RequestException:
            return None
        if r.status_code != 200 or not r.content.startswith(b"%PDF"):
            return None
        p.write_bytes(r.content)
    try:
        d = læs(p.name, p.read_bytes())
    except Exception:
        return None
    if len(d.tekst) < 1000:
        return None
    return fra_tekst(d.tekst, titel, "plandata", doklink)

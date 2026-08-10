"""Auto-detektion af mangeltype, udfald og husets opførelsesår ud fra
kendelsesteksten. 1:1 porteret fra ejnar/pages/ejnar.py — hold i sync."""
from __future__ import annotations

import re

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


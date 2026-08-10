"""Deterministisk dansk query-udvidelse for ejerskifteforsikring — GRATIS
alternativ til Haiku-baseret udvid_query(): jurister og lægfolk bruger andre
ord end kendelsesteksterne, og TF-IDF kan ikke bygge bro selv (stemmeren
klarer bøjninger, ikke synonymer: "mug" ≠ "skimmel").

Kurateret ud fra det faktiske korpus (5.641 AKF-kendelser). Bevidst
konservativ: kun udvidelser der peger mod nævnets egen terminologi —
for brede lister fortynder originaltermerne og skader præcisionen."""
from __future__ import annotations

import re

# nøgle (matches på ordgrænse, lowercase) → termer der føjes til søgningen
SYNONYMER: dict[str, str] = {
    # Hverdagssprog → nævnets terminologi
    "mug": "skimmel skimmelsvamp",
    "mugnet": "skimmel skimmelsvamp",
    "råddent": "råd trænedbrydende svamp",
    "vandskade": "fugtskade vandindtrængning opfugtning",
    "hussvamp": "ægte hussvamp trænedbrydende svamp",
    "svamp": "trænedbrydende svamp råd",
    "skimmel": "skimmelsvamp skimmelvækst fugt",
    "fugt": "fugtskade fugtindtrængning opfugtning",
    "grundfugt": "opstigende grundfugt kapillarsugning",

    # Bygningsdele og konstruktioner
    "tag": "tagdækning tagkonstruktion undertag",
    "stråtag": "tagdækning tækket",
    "utæt": "utæthed vandindtrængning",
    "termoruder": "punkterede termoruder",
    "punkterede": "termoruder dugruder",
    "vinduer": "vinduespartier termoruder",
    "kælder": "kælderydervæg kældergulv",
    "krybekælder": "krybekælderen ventilation strøer",
    "terrændæk": "betondæk gulvkonstruktion",
    "gulv": "gulvkonstruktion strøer terrændæk",
    "fundament": "sokkel sætningsskade understøbning",
    "sætningsskader": "sætningsrevner revnedannelser fundament",
    "revner": "revnedannelser sætningsrevner svindrevner",
    "bindingsværk": "tavl fodrem stolper",
    "skorsten": "skorstenspibe lipper ildsted",
    "badeværelse": "vådrum vådrumsmembran vådrumssikring",
    "vådrum": "badeværelse vådrumsmembran",
    "membran": "vådrumsmembran fugtspærre",
    "kapillarbrydende": "kapillarbrydende lag fugtspærre singels",

    # Installationer
    "kloak": "kloakledning afløbsinstallation faldstamme brønd",
    "afløb": "afløbsinstallation kloakledning faldstamme",
    "faldstamme": "afløbsinstallation tæret",
    "dræn": "omfangsdræn drænledning",
    "el": "el-installation elinstallationer ulovlige",
    "gulvvarme": "varmeinstallation varmeslanger",
    "varmepumpe": "jordvarme varmeanlæg jordvarmeanlæg",
    "jordvarme": "varmepumpe jordvarmeanlæg varmeanlæg",
    "olietank": "villaolietank nedgravet tank olieudskiller",

    # Skadedyr og materialer
    "rotter": "rotteangreb skadedyr kloakbrud",
    "borebiller": "insektangreb borebilleangreb kemisk bekæmpelse",
    "husbukke": "insektangreb trænedbrydende insekter",
    "asbest": "asbestholdig eternitplader",
    "eternit": "eternitplader asbestholdig bølgeplader",
    "mgo": "mgo-plader magnesiumoxid vindspærreplader",

    # Jura/proces
    "tilstandsrapporten": "tilstandsrapport huseftersyn bygningssagkyndig",
    "k3": "tilstandsrapport karakteren k3",
    "levetid": "restlevetid forventet levetid",
    "aldersfradrag": "afskrivning restlevetid levetidstabel",
    "forældet": "forældelse reklamation anmeldelsesfrist",
    "ulovlig": "ulovlige forskriftsmæssig bygningsreglement",
}

# Én kompileret alternation — nøgler sorteret længste-først så
# "opstigende grundfugt"-agtige flerordsnøgler ville vinde over delord.
_MØNSTER = re.compile(
    r"(?<![a-zæøå0-9])(" +
    "|".join(re.escape(k) for k in sorted(SYNONYMER, key=len, reverse=True)) +
    r")(?![a-zæøå0-9])",
    re.IGNORECASE,
)

_MAX_EKSTRA_TERMER = 14  # værn mod fortynding af originaltermerne


def udvid_query_dansk(query: str) -> str:
    """Returnér query + kuraterede fagtermer for de nøgleord der optræder.
    Deterministisk, offline, gratis. Uændret query hvis intet matcher."""
    if not query:
        return query
    lavt = query.lower()
    ekstra: list[str] = []
    set_allerede = set(re.findall(r"[a-zæøå0-9\-]+", lavt))
    for m in _MØNSTER.finditer(query):
        for term in SYNONYMER[m.group(1).lower()].split():
            t = term.lower()
            if t not in set_allerede:
                set_allerede.add(t)
                ekstra.append(term)
                if len(ekstra) >= _MAX_EKSTRA_TERMER:
                    return f"{query} {' '.join(ekstra)}"
    return f"{query} {' '.join(ekstra)}" if ekstra else query

"""Normaliseret metadata til Ejnars kendelser.

Udtrækket er deterministisk og konservativt. Ord og fraser skal stå som selvstændige
begreber, byggeår kræver konstruktionskontekst, og love genkendes kun gennem afgrænsede
navne eller nummerhenvisninger. Modulet må hellere returnere tomme felter end opfinde
metadata. Senere LLM-udtræk kan skrive til samme schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
import re
from typing import Iterable


@dataclass(frozen=True)
class DecisionMetadata:
    building_parts: tuple[str, ...] = ()
    causes: tuple[str, ...] = ()
    consequences: tuple[str, ...] = ()
    coverage_outcomes: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    construction_years: tuple[int, ...] = ()
    materials: tuple[str, ...] = ()
    remedies: tuple[str, ...] = ()
    depreciation: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


_TERMS = {
    "building_parts": {
        "tag": (
            "tag",
            "tagdækning",
            "tagsten",
            "tagkonstruktion",
            "tagkonstruktionen",
            "tagrum",
            "tagrummet",
            "tagflade",
            "tagflader",
            "tagbeklædning",
            "tagplade",
            "tagplader",
        ),
        "undertag": ("undertag", "undertaget"),
        "tagrende": ("tagrende", "tagrender", "tagrenden"),
        "vindue": ("vindue", "vinduer", "vinduet", "vinduerne"),
        "gulv": ("gulv", "gulvet", "parketgulv", "trægulv", "klinkegulv"),
        "fundament/sokkel": ("fundament", "fundamentet", "sokkel", "soklen"),
        "badeværelse/vådrum": (
            "badeværelse",
            "badeværelset",
            "vådrum",
            "bruseniche",
            "brusenichen",
        ),
        "kloak/afløb": (
            "kloak",
            "kloakken",
            "afløb",
            "afløbet",
            "faldstamme",
            "dræn",
        ),
        "murværk/facade": (
            "murværk",
            "facade",
            "facaden",
            "mursten",
            "puds",
        ),
    },
    "causes": {
        "slid og ælde": ("slid og ælde", "sædvanligt slid", "almindeligt slid"),
        "udløbet levetid": ("udløbet levetid", "udtjent levetid", "restlevetid"),
        "manglende vedligeholdelse": (
            "manglende vedligeholdelse",
            "vedligeholdelsesmangel",
        ),
        "fejludførelse": (
            "fejludført",
            "fejludførelse",
            "forkert udført",
            "mangelfuldt udført",
        ),
        "fugt/vand": (
            "fugt",
            "fugtskade",
            "fugtskader",
            "vandindtrængning",
            "utæthed",
            "utætheder",
            "opfugtning",
        ),
    },
    "consequences": {
        "skimmel": ("skimmel", "skimmelsvamp"),
        "råd": (
            "råd",
            "rådskade",
            "rådskader",
            "rådskadet",
            "rådskadede",
        ),
        "utæthed": ("utæthed", "utætheder", "utæt", "utætte"),
        "funktionsnedsættelse": (
            "nedsat funktion",
            "funktionssvigt",
            "ikke funktionsdygtig",
        ),
        "kosmetisk": ("kosmetisk", "æstetisk"),
    },
    "coverage_outcomes": {
        "dækket": ("dækningsberettiget", "er dækket", "skal anerkende dækning"),
        "ikke dækket": ("ikke dækket", "ikke er dækket", "afvisning af dækning"),
        "delvist dækket": ("delvist dækket", "delvis dækning"),
    },
    "exclusions": {
        "slid/vedligeholdelse": ("sædvanligt slid", "manglende vedligeholdelse"),
        "udløb af levetid": ("udløb af levetid", "udløbet levetid"),
        "kendt forhold": ("kendt forhold", "var bekendt med"),
        "anden forsikring": ("anden forsikring", "dobbeltforsikring"),
    },
    "materials": {
        "zink": ("zink",),
        "aluminium": ("aluminium", "aluminiumtape"),
        "beton": ("beton",),
        "træ": (
            "træ",
            "trækonstruktion",
            "træværk",
            "trævindue",
            "trævinduer",
        ),
        "vinyl": ("vinyl",),
        "klinker": ("klinker", "klinkegulv"),
        "tagpap": ("tagpap",),
    },
    "remedies": {
        "udskiftning": ("udskiftning", "udskiftes"),
        "reparation": ("reparation", "repareres", "udbedring"),
        "tætning": ("tætning", "tætnes", "fugemasse"),
        "affugtning": ("affugtning", "udtørring"),
    },
    "depreciation": {
        "afskrivning": ("afskrivning", "afskrives"),
        "restlevetid": ("restlevetid",),
        "nyværdi": ("nyværdi",),
    },
}

_YEAR = r"(?P<year>(?:18|19|20)\d{2})"
_CONSTRUCTION_YEAR_PATTERNS = (
    re.compile(rf"\b(?:opført|bygget)\s+(?:i\s+)?{_YEAR}\b", re.I),
    re.compile(
        rf"\b(?:opførelsesår(?:et)?|byggeår(?:et)?)\s*(?:er|var|:)?\s*{_YEAR}\b",
        re.I,
    ),
    re.compile(rf"\b(?:stammer|daterer\s+sig)\s+fra\s+{_YEAR}\b", re.I),
    re.compile(
        rf"\b(?:huset|ejendommen|bygningen|gulvet|taget|undertaget|vinduerne?|"
        rf"badeværelset|tilbygningen|carporten)\b[^.;:]{{0,55}}?"
        rf"\b(?:fra|opført\s+i|bygget\s+i)\s+{_YEAR}\b",
        re.I,
    ),
)

_KNOWN_LAW_PATTERNS = (
    (
        "forsikringsaftaleloven",
        re.compile(r"\bforsikringsaftaleloven\b|\bfal\b", re.I),
    ),
    (
        "lov om forbrugerbeskyttelse ved erhvervelse af fast ejendom",
        re.compile(
            r"\blov\s+om\s+forbrugerbeskyttelse\s+ved\s+erhvervelse\s+af\s+fast\s+ejendom\b",
            re.I,
        ),
    ),
)
_NUMBERED_LAW_RE = re.compile(
    r"\b(?:lov|bekendtgørelse)\s+nr\.?\s*\d+[a-z]?\b",
    re.I,
)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


@lru_cache(maxsize=1024)
def _term_pattern(needle: str) -> re.Pattern[str]:
    normalised = _normalise(needle)
    tokens = [re.escape(token) for token in normalised.split() if token]
    body = r"\s+".join(tokens)
    return re.compile(rf"(?<!\w){body}(?!\w)", re.I)


def _contains_term(text: str, needle: str) -> bool:
    normalised = _normalise(needle)
    return bool(normalised and _term_pattern(normalised).search(text))


def _match_labels(text: str, mapping: dict[str, Iterable[str]]) -> tuple[str, ...]:
    found = []
    for label, needles in mapping.items():
        if any(_contains_term(text, needle) for needle in needles):
            found.append(label)
    return tuple(found)


def _extract_construction_years(text: str) -> tuple[int, ...]:
    positioned: list[tuple[int, int]] = []
    for pattern in _CONSTRUCTION_YEAR_PATTERNS:
        for match in pattern.finditer(text):
            positioned.append((match.start("year"), int(match.group("year"))))
    positioned.sort()
    return tuple(dict.fromkeys(year for _, year in positioned))


def _extract_laws(text: str) -> tuple[str, ...]:
    found: list[tuple[int, str]] = []
    for label, pattern in _KNOWN_LAW_PATTERNS:
        match = pattern.search(text)
        if match:
            found.append((match.start(), label))
    for match in _NUMBERED_LAW_RE.finditer(text):
        found.append((match.start(), _normalise(match.group(0))))
    found.sort(key=lambda item: (item[0], item[1]))
    return tuple(dict.fromkeys(label for _, label in found))


def extract_metadata(text: str) -> DecisionMetadata:
    blob = _normalise(text)
    values = {
        field: _match_labels(blob, mapping)
        for field, mapping in _TERMS.items()
    }
    return DecisionMetadata(
        building_parts=values["building_parts"],
        causes=values["causes"],
        consequences=values["consequences"],
        coverage_outcomes=values["coverage_outcomes"],
        exclusions=values["exclusions"],
        laws=_extract_laws(text or ""),
        construction_years=_extract_construction_years(blob),
        materials=values["materials"],
        remedies=values["remedies"],
        depreciation=values["depreciation"],
    )

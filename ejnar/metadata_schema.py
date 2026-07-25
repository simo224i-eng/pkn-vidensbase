"""Normaliseret metadata til Ejnars kendelser.

Første version er deterministisk og konservativ. Den må hellere returnere tomme felter
end opfinde metadata. Senere LLM-udtræk kan skrive til samme schema.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
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
        "tag": ("tag", "tagdækning", "tagsten"),
        "undertag": ("undertag",),
        "tagrende": ("tagrende",),
        "vindue": ("vindue", "vinduer"),
        "gulv": ("gulv", "parketgulv", "trægulv", "klinkegulv"),
        "fundament/sokkel": ("fundament", "sokkel"),
        "badeværelse/vådrum": ("badeværelse", "vådrum", "bruseniche"),
        "kloak/afløb": ("kloak", "afløb", "faldstamme", "dræn"),
        "murværk/facade": ("murværk", "facade", "mursten", "puds"),
    },
    "causes": {
        "slid og ælde": ("slid og ælde", "sædvanligt slid", "almindeligt slid"),
        "udløbet levetid": ("udløbet levetid", "udtjent levetid", "restlevetid"),
        "manglende vedligeholdelse": ("manglende vedligeholdelse", "vedligeholdelsesmangel"),
        "fejludførelse": ("fejludført", "fejludførelse", "forkert udført", "mangelfuldt udført"),
        "fugt/vand": ("fugt", "vandindtrængning", "utæthed", "opfugtning"),
    },
    "consequences": {
        "skimmel": ("skimmel",),
        "råd": ("råd", "rådskade"),
        "utæthed": ("utæthed", "utæt"),
        "funktionsnedsættelse": ("nedsat funktion", "funktionssvigt", "ikke funktionsdygtig"),
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
        "træ": ("træ", "trækonstruktion"),
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

_YEAR_RE = re.compile(r"\b(?:18|19|20)\d{2}\b")
_LAW_RE = re.compile(r"\b(?:lov|bekendtgørelse|forsikringsaftaleloven|fal)\s*(?:nr\.?\s*)?\d*[a-zæøå-]*", re.I)


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _match_labels(text: str, mapping: dict[str, Iterable[str]]) -> tuple[str, ...]:
    found = []
    for label, needles in mapping.items():
        if any(_normalise(needle) in text for needle in needles):
            found.append(label)
    return tuple(found)


def extract_metadata(text: str) -> DecisionMetadata:
    blob = _normalise(text)
    values = {
        field: _match_labels(blob, mapping)
        for field, mapping in _TERMS.items()
    }
    years = tuple(dict.fromkeys(int(value) for value in _YEAR_RE.findall(blob)))
    laws = tuple(dict.fromkeys(match.group(0).strip() for match in _LAW_RE.finditer(blob)))
    return DecisionMetadata(
        building_parts=values["building_parts"],
        causes=values["causes"],
        consequences=values["consequences"],
        coverage_outcomes=values["coverage_outcomes"],
        exclusions=values["exclusions"],
        laws=laws,
        construction_years=years,
        materials=values["materials"],
        remedies=values["remedies"],
        depreciation=values["depreciation"],
    )

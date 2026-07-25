"""Deterministisk routing af forespørgsler i Ejnar.

Modulet er bevidst uafhængigt af Streamlit og LLM-kald, så routing kan testes
hurtigt og reproducerbart. Det ændrer ikke retrieval-pipelinen i sig selv;
det beskriver den retrieval-politik, som næste integrationstrin skal anvende.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Iterable


class QueryIntent(str, Enum):
    """De seks brugerbehov Ejnar skal kunne skelne mellem."""

    EXACT_CONTENT_SEARCH = "exact_content_search"
    SPECIFIC_DECISION_SEARCH = "specific_decision_search"
    PRACTICE_OVERVIEW = "practice_overview"
    CONCRETE_CASE_ASSESSMENT = "concrete_case_assessment"
    FACTUAL_LOOKUP = "factual_lookup"
    EXPLORATORY_RESEARCH = "exploratory_research"


@dataclass(frozen=True)
class RetrievalPlan:
    """Retrieval-indstillinger afledt af forespørgslens hensigt."""

    intent: QueryIntent
    confidence: float
    exact_phrases: tuple[str, ...]
    decision_identifiers: tuple[str, ...]
    use_hyde: bool
    expand_query: bool
    use_auto_filters: bool
    prioritize_lexical: bool
    top_retrieve: int
    top_final: int
    reasons: tuple[str, ...]


_QUOTED_PHRASE_RE = re.compile(
    r'["“”„«»](.{3,250}?)["“”„«»]',
    flags=re.DOTALL,
)

_DECISION_ID_PATTERNS = (
    re.compile(
        r"\b(?:sag(?:snummer)?|kendelse|afgørelse)\s*"
        r"(?:(?:nr\.?|nummer)\s*)?[:#]?\s*"
        r"([A-ZÆØÅ0-9][A-ZÆØÅ0-9./_-]{3,})\b",
        flags=re.IGNORECASE,
    ),
    re.compile(r"\b(?:ankeforsikring\.dk|ankenaevnet\.dk)/\S+", flags=re.IGNORECASE),
)

_FIND_WORDS = (
    "find", "fremfind", "søg", "vis", "lokalis", "giv mig afgørelser",
    "find kendelser", "find afgørelser",
)
_EXACT_CONTENT_CUES = (
    "hvor der står", "som indeholder", "der indeholder", "med formuleringen",
    "ordret", "den præcise formulering", "nævner", "omtaler", "bruger ordet",
    "med både", "hvor både", "specifikt indhold", "tekststed",
)
_PRACTICE_CUES = (
    "praksis", "praksislinje", "tendens", "mønster", "på tværs",
    "typisk", "generelt", "hvornår får", "hvornår dækker",
    "hvilke momenter", "hvilke forhold", "hvad lægger nævnet vægt på",
    "sammenlign", "fordeling",
)
_CASE_CUES = (
    "min sag", "denne sag", "konkret sag", "konkrete sag", "min anmeldelse",
    "vil dette være dækket", "er dette dækket", "er forholdet dækket",
    "vurder sagen", "vurder dette", "hvordan står jeg", "kan jeg få dækning",
    "bør selskabet dække", "sandsynligvis dækket",
)
_FACTUAL_CUES = (
    "hvad er", "hvad betyder", "hvilken frist", "hvor lang frist",
    "hvem har", "kan nævnet", "skal selskabet", "må selskabet",
    "hvilken bestemmelse", "hvad siger betingelserne",
)


def _normalise(query: str) -> str:
    return re.sub(r"\s+", " ", (query or "").strip()).lower()


def _contains_any(text: str, phrases: Iterable[str]) -> bool:
    return any(phrase in text for phrase in phrases)


def extract_quoted_phrases(query: str) -> tuple[str, ...]:
    """Udtræk ordrette fraser i danske og almindelige citationstegn."""

    found: list[str] = []
    for match in _QUOTED_PHRASE_RE.finditer(query or ""):
        phrase = re.sub(r"\s+", " ", match.group(1)).strip()
        if phrase and phrase not in found:
            found.append(phrase)
    return tuple(found)


def extract_decision_identifiers(query: str) -> tuple[str, ...]:
    """Udtræk sags-/kendelsesnumre og direkte kendelseslinks."""

    found: list[str] = []
    for pattern in _DECISION_ID_PATTERNS:
        for match in pattern.finditer(query or ""):
            value = match.group(1) if match.lastindex else match.group(0)
            value = value.rstrip(".,;)")
            if value not in found:
                found.append(value)
    return tuple(found)


def classify_query(query: str) -> RetrievalPlan:
    """Klassificér en dansk juridisk forespørgsel uden LLM-kald.

    Routing er med vilje konservativ:
    - Identificerbare kendelser slår alt andet.
    - Ordrette fraser og eksplicitte "find afgørelser hvor..."-ønsker prioriterer
      lexical retrieval og deaktiverer HyDE/query expansion.
    - Konkrete sager holdes adskilt fra brede praksisoversigter.
    """

    raw = (query or "").strip()
    text = _normalise(raw)
    phrases = extract_quoted_phrases(raw)
    identifiers = extract_decision_identifiers(raw)
    reasons: list[str] = []

    if identifiers:
        reasons.append("Forespørgslen indeholder et kendelses-/sags-ID eller direkte link.")
        return RetrievalPlan(
            intent=QueryIntent.SPECIFIC_DECISION_SEARCH,
            confidence=0.99,
            exact_phrases=phrases,
            decision_identifiers=identifiers,
            use_hyde=False,
            expand_query=False,
            use_auto_filters=False,
            prioritize_lexical=True,
            top_retrieve=80,
            top_final=10,
            reasons=tuple(reasons),
        )

    find_request = _contains_any(text, _FIND_WORDS)
    exact_cue = _contains_any(text, _EXACT_CONTENT_CUES)
    combined_fact_search = (
        find_request
        and ("afgørelse" in text or "kendelse" in text)
        and (" hvor " in f" {text} " or " med " in f" {text} ")
    )

    if phrases or exact_cue or combined_fact_search:
        if phrases:
            reasons.append("Forespørgslen indeholder en ordret frase.")
        if exact_cue:
            reasons.append("Forespørgslen efterspørger bestemt tekst eller bestemte fakta.")
        if combined_fact_search:
            reasons.append("Forespørgslen beder om afgørelser med angivne kendetegn.")
        return RetrievalPlan(
            intent=QueryIntent.EXACT_CONTENT_SEARCH,
            confidence=0.95 if (phrases or exact_cue) else 0.86,
            exact_phrases=phrases,
            decision_identifiers=identifiers,
            use_hyde=False,
            expand_query=False,
            use_auto_filters=False,
            prioritize_lexical=True,
            top_retrieve=120,
            top_final=20,
            reasons=tuple(reasons),
        )

    case_score = sum(cue in text for cue in _CASE_CUES)
    looks_like_fact_pattern = (
        len(text.split()) >= 20
        and any(word in text for word in ("hus", "tag", "gulv", "fugt", "skimmel", "forsikring"))
        and any(word in text for word in ("dækk", "afvis", "anmeld", "skade"))
    )
    if case_score or looks_like_fact_pattern:
        reasons.append("Forespørgslen beskriver eller beder om vurdering af en konkret sag.")
        return RetrievalPlan(
            intent=QueryIntent.CONCRETE_CASE_ASSESSMENT,
            confidence=0.93 if case_score else 0.76,
            exact_phrases=phrases,
            decision_identifiers=identifiers,
            use_hyde=True,
            expand_query=True,
            use_auto_filters=False,
            prioritize_lexical=False,
            top_retrieve=100,
            top_final=15,
            reasons=tuple(reasons),
        )

    practice_score = sum(cue in text for cue in _PRACTICE_CUES)
    if practice_score:
        reasons.append("Forespørgslen efterspørger mønstre eller et overblik over praksis.")
        return RetrievalPlan(
            intent=QueryIntent.PRACTICE_OVERVIEW,
            confidence=min(0.98, 0.78 + practice_score * 0.05),
            exact_phrases=phrases,
            decision_identifiers=identifiers,
            use_hyde=True,
            expand_query=True,
            use_auto_filters=True,
            prioritize_lexical=False,
            top_retrieve=120,
            top_final=18,
            reasons=tuple(reasons),
        )

    factual_score = sum(cue in text for cue in _FACTUAL_CUES)
    if factual_score or (len(text.split()) <= 14 and text.endswith("?")):
        reasons.append("Forespørgslen er et afgrænset faktuelt eller juridisk opslag.")
        return RetrievalPlan(
            intent=QueryIntent.FACTUAL_LOOKUP,
            confidence=0.84 if factual_score else 0.62,
            exact_phrases=phrases,
            decision_identifiers=identifiers,
            use_hyde=False,
            expand_query=True,
            use_auto_filters=True,
            prioritize_lexical=False,
            top_retrieve=60,
            top_final=8,
            reasons=tuple(reasons),
        )

    reasons.append("Ingen stærk specialindikator; brug bred eksplorativ retrieval.")
    return RetrievalPlan(
        intent=QueryIntent.EXPLORATORY_RESEARCH,
        confidence=0.55,
        exact_phrases=phrases,
        decision_identifiers=identifiers,
        use_hyde=True,
        expand_query=True,
        use_auto_filters=True,
        prioritize_lexical=False,
        top_retrieve=100,
        top_final=15,
        reasons=tuple(reasons),
    )

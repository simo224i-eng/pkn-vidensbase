"""Konservativ, deterministisk query planning til Ejnars praksissøgning.

Planneren erstatter ikke brugerens forespørgsel og foretager ingen juridisk
vurdering. Den tilføjer alene få, på forhånd godkendte søgetermer, når et
domænebegreb kan genkendes sikkert. Præcise indholdssøgninger og opslag af en
bestemt kendelse ændres aldrig.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

try:
    from query_intent import QueryIntent, classify_query
except ImportError:  # package-import i tests/værktøjer
    from ejnar.query_intent import QueryIntent, classify_query


@dataclass(frozen=True)
class QueryConcept:
    """En lille, auditerbar gruppe af nært beslægtede søgetermer."""

    name: str
    triggers: tuple[str, ...]
    expansions: tuple[str, ...]


@dataclass(frozen=True)
class QueryPlan:
    """Resultatet af query planning uden sideeffekter eller modelkald."""

    original_query: str
    intent: QueryIntent
    expanded_query: str
    added_terms: tuple[str, ...]
    matched_concepts: tuple[str, ...]
    applied: bool
    skipped_reason: str | None = None


# Grupperne er bevidst små. De beskriver sproglige eller meget nære faglige
# relationer, ikke antagelser om årsag, dækning eller udfald.
_CONCEPTS: tuple[QueryConcept, ...] = (
    QueryConcept(
        "parketgulv",
        ("parket", "parketgulv"),
        ("parketgulv", "trægulv", "gulv"),
    ),
    QueryConcept(
        "gulvdeformation",
        ("opbulnet", "opbulning", "hævet gulv", "gulvet hæver", "buler i gulvet"),
        ("opbulning", "hævet gulv", "deformation"),
    ),
    QueryConcept(
        "vedhæftning",
        ("vedhæftningssvigt", "sluppet vedhæftning", "manglende vedhæftning"),
        ("vedhæftningssvigt", "sluppet vedhæftning", "manglende vedhæftning"),
    ),
    QueryConcept(
        "fugt",
        ("fugt", "fugtskade", "opfugtning", "vandindtrængning"),
        ("fugt", "fugtskade", "opfugtning", "vandindtrængning"),
    ),
    QueryConcept(
        "skimmel",
        ("skimmel", "skimmelsvamp"),
        ("skimmel", "skimmelsvamp"),
    ),
    QueryConcept(
        "råd",
        ("råd", "rådskade", "rådskadet"),
        ("råd", "rådskade", "rådskadet"),
    ),
    QueryConcept(
        "utæthed",
        ("utæt", "utæthed", "utætheder"),
        ("utæt", "utæthed", "vandindtrængning"),
    ),
    QueryConcept(
        "ventilation",
        ("ventilation", "udluftning", "luftskifte"),
        ("ventilation", "udluftning", "luftskifte"),
    ),
    QueryConcept(
        "vådrumsmembran",
        ("vådrumsmembran", "vandtætningsmembran", "membran i vådrum"),
        ("vådrumsmembran", "vandtætningsmembran", "membran i vådrum"),
    ),
    QueryConcept(
        "følgeskade",
        ("følgeskade", "følgeskader", "skadefølge"),
        ("følgeskade", "følgeskader", "skadefølge"),
    ),
    QueryConcept(
        "funktion",
        ("funktionstab", "funktionssvigt", "nedsat funktion", "fortsat funktion"),
        ("funktionstab", "funktionssvigt", "nedsat funktion", "fortsat funktion"),
    ),
    QueryConcept(
        "kosmetisk",
        ("kosmetisk", "æstetisk"),
        ("kosmetisk", "æstetisk"),
    ),
    QueryConcept(
        "levetid",
        ("restlevetid", "udløbet levetid", "udtjent", "forventet levetid"),
        ("restlevetid", "udløbet levetid", "udtjent", "forventet levetid"),
    ),
    QueryConcept(
        "slid",
        ("slid", "slitage", "slid og ælde", "sædvanligt slid"),
        ("slid", "slitage", "slid og ælde", "sædvanligt slid"),
    ),
    QueryConcept(
        "reparation",
        ("reparation", "repareret", "udbedring", "udbedret"),
        ("reparation", "repareret", "udbedring", "udbedret"),
    ),
    QueryConcept(
        "udskiftning",
        ("udskiftning", "udskiftet", "fornyelse"),
        ("udskiftning", "udskiftet", "fornyelse"),
    ),
    QueryConcept(
        "kendt_forhold",
        ("kendt forhold", "bekendt med forholdet", "oplyst om forholdet"),
        ("kendt forhold", "bekendt med forholdet", "oplyst om forholdet"),
    ),
    QueryConcept(
        "tilstandsrapport",
        ("tilstandsrapport", "k3", "un"),
        ("tilstandsrapport", "k3", "un"),
    ),
    QueryConcept(
        "anden_forsikring",
        ("dobbeltforsikring", "anden forsikring", "husforsikring"),
        ("dobbeltforsikring", "anden forsikring", "husforsikring"),
    ),
    QueryConcept(
        "afskrivning",
        ("afskrivning", "afskrevet", "erstatningsopgørelse"),
        ("afskrivning", "afskrevet", "erstatningsopgørelse", "restlevetid"),
    ),
    QueryConcept(
        "overtagelse",
        ("overtagelse", "overtagelsen", "overtagelsestidspunkt"),
        ("overtagelse", "overtagelsestidspunkt"),
    ),
)

_SKIPPED_INTENTS = {
    QueryIntent.EXACT_CONTENT_SEARCH,
    QueryIntent.SPECIFIC_DECISION_SEARCH,
}
_TOKEN_RE = re.compile(r"[a-zæøå0-9]+", re.IGNORECASE)
_OUTCOME_TERMS = {
    "dækket",
    "ikke dækket",
    "medhold",
    "afvisning",
    "dækningsberettiget",
}
MAX_ADDED_TERMS = 10
MAX_QUERY_CHARS = 800
MAX_PLANNABLE_TOKENS = 5


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().casefold())


def _term_pattern(term: str) -> re.Pattern[str]:
    tokens = _TOKEN_RE.findall(_normalise(term))
    if not tokens:
        return re.compile(r"(?!x)x")
    return re.compile(
        r"(?<![a-zæøå0-9])"
        + r"[\s\-_]+".join(re.escape(token) for token in tokens)
        + r"(?![a-zæøå0-9])",
        flags=re.IGNORECASE,
    )


def _contains(text: str, term: str) -> bool:
    return bool(_term_pattern(term).search(text))


def _unique_missing_terms(
    query: str,
    terms: Iterable[str],
    *,
    limit: int,
) -> tuple[str, ...]:
    found: list[str] = []
    seen = {_normalise(value) for value in _OUTCOME_TERMS}
    for term in terms:
        normalised = _normalise(term)
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        if _contains(query, term):
            continue
        found.append(term)
        if len(found) >= limit:
            break
    return tuple(found)


def plan_query(query: str, *, max_added_terms: int = MAX_ADDED_TERMS) -> QueryPlan:
    """Planlæg få, kontrollerede søgetermer til praksis-retrieval.

    Ukendte eller meget lange forespørgsler returneres uændret, så den eksisterende
    fallback kan håndtere dem. Der genereres aldrig konklusioner om dækning.
    """

    original = (query or "").strip()
    retrieval_plan = classify_query(original)
    intent = retrieval_plan.intent

    if not original:
        return QueryPlan(original, intent, original, (), (), False, "empty_query")
    if intent in _SKIPPED_INTENTS:
        return QueryPlan(
            original,
            intent,
            original,
            (),
            (),
            False,
            "precision_sensitive_intent",
        )
    if len(original) > MAX_QUERY_CHARS:
        return QueryPlan(original, intent, original, (), (), False, "query_too_long")
    if len(_TOKEN_RE.findall(original)) > MAX_PLANNABLE_TOKENS:
        return QueryPlan(
            original,
            intent,
            original,
            (),
            (),
            False,
            "informative_query_preserved",
        )

    matched: list[QueryConcept] = []
    for concept in _CONCEPTS:
        if any(_contains(original, trigger) for trigger in concept.triggers):
            matched.append(concept)

    added_terms = _unique_missing_terms(
        original,
        (
            expansion
            for concept in matched
            for expansion in concept.expansions
        ),
        limit=max(0, int(max_added_terms)),
    )
    if not added_terms:
        reason = "no_known_concepts" if not matched else "no_missing_terms"
        return QueryPlan(
            original,
            intent,
            original,
            (),
            tuple(concept.name for concept in matched),
            False,
            reason,
        )

    expanded = f"{original} {' '.join(added_terms)}"
    return QueryPlan(
        original_query=original,
        intent=intent,
        expanded_query=expanded,
        added_terms=added_terms,
        matched_concepts=tuple(concept.name for concept in matched),
        applied=True,
    )

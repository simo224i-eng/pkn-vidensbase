"""Rarity-aware ranking af relaterede kendelser i Ejnars juridiske graf.

Almindelige features som ``reparation`` og ``dækket`` skal ikke dominere en relation.
Modulet beregner derfor en forklarlig IDF-vægt oven på grafens eksisterende
feltvægte. Det ændrer ikke grafdata eller produktionsretrieval.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any

try:
    from legal_graph import DecisionGraph
except ImportError:  # package-import i tests/værktøjer
    from ejnar.legal_graph import DecisionGraph


@dataclass(frozen=True)
class RankedRelatedDecision:
    decision_id: str
    score: float
    shared_features: tuple[str, ...]
    feature_contributions: tuple[tuple[str, float], ...]
    case_number: str
    title: str
    link: str


def feature_document_frequencies(graph: DecisionGraph) -> dict[str, int]:
    """Antal kendelser pr. feature-key."""
    frequencies: dict[str, int] = {}
    for features in graph.decision_features.values():
        for feature_key in features:
            frequencies[feature_key] = frequencies.get(feature_key, 0) + 1
    return frequencies


def feature_idf(total_decisions: int, document_frequency: int) -> float:
    """Udglattet IDF, altid mindst 1,0."""
    if total_decisions <= 0 or document_frequency <= 0:
        return 1.0
    return 1.0 + math.log((total_decisions + 1.0) / (document_frequency + 1.0))


def _weighted_features(
    graph: DecisionGraph,
    decision_id: str,
    frequencies: dict[str, int],
) -> dict[str, tuple[str, float]]:
    total = len(graph.decision_features)
    output: dict[str, tuple[str, float]] = {}
    for key, (label, base_weight) in graph.decision_features.get(decision_id, {}).items():
        weight = float(base_weight) * feature_idf(total, frequencies.get(key, 0))
        output[key] = (label, weight)
    return output


def related_by_rarity(
    graph: DecisionGraph,
    decision_id: str,
    *,
    limit: int = 10,
    min_score: float = 0.05,
) -> list[RankedRelatedDecision]:
    """Rangér relaterede kendelser med rarity-vægtet Jaccard.

    Resultatet forklarer hvert hit med de fælles features og deres bidrag. Sjældne
    features får højere bidrag, men grafens juridiske feltvægte bevares.
    """
    if limit <= 0:
        return []
    frequencies = feature_document_frequencies(graph)
    target = _weighted_features(graph, decision_id, frequencies)
    if not target:
        return []

    target_total = sum(weight for _, weight in target.values())
    ranked: list[RankedRelatedDecision] = []
    for candidate_id in graph.decision_features:
        if candidate_id == decision_id:
            continue
        candidate = _weighted_features(graph, candidate_id, frequencies)
        common = sorted(set(target) & set(candidate))
        if not common:
            continue
        contributions = sorted(
            ((target[key][0], target[key][1]) for key in common),
            key=lambda item: (-item[1], item[0]),
        )
        shared_weight = sum(weight for _, weight in contributions)
        candidate_total = sum(weight for _, weight in candidate.values())
        denominator = target_total + candidate_total - shared_weight
        score = shared_weight / denominator if denominator else 0.0
        if score < min_score:
            continue
        payload: dict[str, Any] = graph.decision_payloads.get(candidate_id, {})
        ranked.append(
            RankedRelatedDecision(
                decision_id=candidate_id,
                score=round(score, 6),
                shared_features=tuple(label for label, _ in contributions),
                feature_contributions=tuple(
                    (label, round(weight, 6)) for label, weight in contributions
                ),
                case_number=str(payload.get("case_number") or ""),
                title=str(payload.get("title") or ""),
                link=str(payload.get("link") or ""),
            )
        )

    ranked.sort(
        key=lambda item: (
            -item.score,
            -sum(weight for _, weight in item.feature_contributions),
            item.case_number,
            item.decision_id,
        )
    )
    return ranked[:limit]

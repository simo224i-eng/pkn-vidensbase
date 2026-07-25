"""Konservativ metadata-reranking af allerede fundne Ejnar-kandidater.

Modulet erstatter ikke retrieval. Det flytter kun kandidater inden for den eksisterende
candidate pool, når forespørgslen og kendelsen deler udtrukne juridiske features.
Sjældne features vægter højere, mens den oprindelige rang bevares som hovedsignal.
"""
from __future__ import annotations

from dataclasses import fields
import math
from typing import Any, Callable, Iterable, Sequence

try:
    from metadata_schema import DecisionMetadata, extract_metadata
except ImportError:
    from ejnar.metadata_schema import DecisionMetadata, extract_metadata


_FIELD_WEIGHTS = {
    "building_parts": 3.0,
    "causes": 2.5,
    "consequences": 2.0,
    "coverage_outcomes": 1.5,
    "exclusions": 2.0,
    "laws": 1.5,
    "construction_years": 1.0,
    "materials": 2.0,
    "remedies": 1.0,
    "depreciation": 1.5,
}


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _feature_map(metadata: DecisionMetadata) -> dict[str, tuple[str, float]]:
    output: dict[str, tuple[str, float]] = {}
    for field in fields(metadata):
        base_weight = float(_FIELD_WEIGHTS.get(field.name, 1.0))
        for value in getattr(metadata, field.name):
            key = f"{field.name}:{_normalise(value)}"
            output[key] = (f"{field.name}: {value}", base_weight)
    return output


def _document_text(document: dict[str, Any]) -> str:
    return "\n".join(
        str(document.get(key, "") or "")
        for key in ("Titel", "Excerpt", "Tekst")
    )


def _idf(total_documents: int, document_frequency: int) -> float:
    return 1.0 + math.log((total_documents + 1.0) / (document_frequency + 1.0))


def rerank_by_query_features(
    query: str,
    candidates: Sequence[dict[str, Any]],
    *,
    metadata_extractor: Callable[[str], DecisionMetadata] = extract_metadata,
    strength: float = 0.12,
) -> list[dict[str, Any]]:
    """Rerankér kandidater uden at lade metadata overtage basisrankingen.

    ``strength`` angiver det maksimale metadata-bidrag. Ved 0 returneres den
    oprindelige rækkefølge. Kandidater uden fælles features beholder deres relative
    rækkefølge.
    """
    if not candidates or strength <= 0:
        return list(candidates)

    query_features = _feature_map(metadata_extractor(query))
    if not query_features:
        return list(candidates)

    candidate_features = [
        _feature_map(metadata_extractor(_document_text(candidate)))
        for candidate in candidates
    ]
    frequencies: dict[str, int] = {}
    for features_for_document in candidate_features:
        for key in features_for_document:
            frequencies[key] = frequencies.get(key, 0) + 1

    total = len(candidates)
    scored: list[tuple[float, int, dict[str, Any]]] = []
    for index, (candidate, features_for_document) in enumerate(
        zip(candidates, candidate_features)
    ):
        common = set(query_features) & set(features_for_document)
        metadata_score = sum(
            query_features[key][1] * _idf(total, frequencies.get(key, 0))
            for key in common
        )
        # Reciprocal-rank-lignende basisscore holder retrieval som hovedsignal.
        base_score = 1.0 / (index + 1.0)
        combined = base_score + float(strength) * metadata_score
        enriched = dict(candidate)
        enriched["_query_feature_score"] = round(metadata_score, 6)
        enriched["_query_feature_matches"] = tuple(
            query_features[key][0]
            for key in sorted(
                common,
                key=lambda key: (
                    -query_features[key][1] * _idf(total, frequencies.get(key, 0)),
                    key,
                ),
            )
        )
        scored.append((combined, index, enriched))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [candidate for _, _, candidate in scored]

"""Konservativ metadata-boost oven på Ejnars eksisterende retrieval.

Laget filtrerer aldrig resultater væk. Det kan kun flytte allerede fundne kandidater en
smule, når både forespørgsel og kendelse har deterministisk udtrukket metadata til fælles.
Ved fejl returneres den oprindelige rangering uændret.
"""
from __future__ import annotations

from dataclasses import fields
import logging
import threading
from typing import Any

try:
    from metadata_schema import DecisionMetadata, extract_metadata
    from query_intent import QueryIntent, classify_query
except ImportError:  # package-import i tests/værktøjer
    from ejnar.metadata_schema import DecisionMetadata, extract_metadata
    from ejnar.query_intent import QueryIntent, classify_query

_LOG = logging.getLogger("ejnar.metadata")
_CACHE_LOCK = threading.Lock()
_METADATA_CACHE: dict[tuple[int, int], list[DecisionMetadata]] = {}

# Bygningsdel, årsag og materiale er stærkere faktuelle signaler end fx generelle
# ord om udbedring. Vægtene er bevidst små og bruges kun som tie-break/let boost.
_FIELD_WEIGHTS = {
    "building_parts": 3.0,
    "causes": 2.5,
    "consequences": 2.0,
    "coverage_outcomes": 1.0,
    "exclusions": 2.0,
    "laws": 1.5,
    "construction_years": 2.0,
    "materials": 2.5,
    "remedies": 1.0,
    "depreciation": 1.5,
}


def _metadata_has_signal(metadata: DecisionMetadata) -> bool:
    return any(getattr(metadata, field.name) for field in fields(metadata))


def metadata_overlap_score(query_meta: DecisionMetadata, document_meta: DecisionMetadata) -> float:
    """Beregn forklarlig overlapscore mellem forespørgsel og kendelse."""
    score = 0.0
    for field_name, weight in _FIELD_WEIGHTS.items():
        query_values = set(getattr(query_meta, field_name))
        if not query_values:
            continue
        document_values = set(getattr(document_meta, field_name))
        score += weight * len(query_values & document_values)
    return score


def _row_text(row: Any) -> str:
    return "\n".join(
        str(row.get(key, "") or "")
        for key in ("Titel", "Tekst", "Mangeltype", "Udfald", "Selskab")
    )


def _metadata_for_df(df: Any) -> list[DecisionMetadata]:
    key = (id(df), len(df))
    with _CACHE_LOCK:
        cached = _METADATA_CACHE.get(key)
    if cached is not None:
        return cached

    built = [extract_metadata(_row_text(df.iloc[idx])) for idx in range(len(df))]
    with _CACHE_LOCK:
        # Hold cachen begrænset; Streamlit genbruger normalt samme DataFrame-instans.
        if len(_METADATA_CACHE) >= 4:
            _METADATA_CACHE.clear()
        _METADATA_CACHE[key] = built
    return built


def rerank_with_metadata(query: str, ranked_indices: list[int], df: Any) -> list[int]:
    """Flyt kun eksisterende kandidater; bevar stabil rækkefølge ved samme score."""
    query_meta = extract_metadata(query)
    if not _metadata_has_signal(query_meta) or len(ranked_indices) < 2:
        return list(ranked_indices)

    metadata = _metadata_for_df(df)
    scored: list[tuple[float, int, int]] = []
    for original_rank, idx in enumerate(ranked_indices):
        try:
            overlap = metadata_overlap_score(query_meta, metadata[int(idx)])
        except (IndexError, TypeError, ValueError):
            overlap = 0.0
        # Den oprindelige rangering er fortsat hovedsignalet. Metadata må højst
        # overvinde få pladser, ikke vende en hel resultatliste på hovedet.
        rank_score = 1.0 / (20.0 + original_rank)
        combined = rank_score + min(overlap, 10.0) * 0.004
        scored.append((combined, original_rank, int(idx)))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [idx for _, _, idx in scored]


def install_metadata_runtime(shared_module: Any | None = None) -> bool:
    """Installér metadata-boost efter intent- og paragraph-runtime."""
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_METADATA_RUNTIME_INSTALLED", False):
        return False

    original_hybrid = shared_module.hybrid_retrieval

    def metadata_hybrid(
        query: str,
        df: Any,
        vec: Any,
        mat: Any,
        embeds: Any,
        sub_idx: Any = None,
        top_retrieve: int = 40,
        top_final: int = 20,
    ) -> list[int]:
        base = original_hybrid(
            query,
            df,
            vec,
            mat,
            embeds,
            sub_idx=sub_idx,
            top_retrieve=top_retrieve,
            top_final=top_final,
        )
        try:
            plan = classify_query(query)
            if plan.intent == QueryIntent.SPECIFIC_DECISION_SEARCH:
                return base
            reranked = rerank_with_metadata(query, list(base), df)
            if reranked != list(base):
                recorder = getattr(shared_module, "_record", None)
                if callable(recorder):
                    recorder("metadata_boost", query, plan, candidates=len(base))
            return reranked[:top_final]
        except Exception:  # pragma: no cover - fail-open sikkerhedsnet
            _LOG.exception("Metadata-boost fejlede; bruger eksisterende rangering")
            return base

    shared_module.hybrid_retrieval = metadata_hybrid
    shared_module._EJNAR_METADATA_RUNTIME_ORIGINAL = original_hybrid
    shared_module._EJNAR_METADATA_RUNTIME_INSTALLED = True
    return True

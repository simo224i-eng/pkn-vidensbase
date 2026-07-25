"""Præcisionslag til direkte opslag af en bestemt kendelse.

Når routeren identificerer et specifikt kendelsesopslag, beholdes kun resultater
som matcher det efterspurgte sagsnummer eller link. Hvis intet direkte match er
fundet, returneres den eksisterende retrieval uændret som fail-open fallback.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from query_intent import QueryIntent, classify_query
except ImportError:
    from ejnar.query_intent import QueryIntent, classify_query

_LOG = logging.getLogger("ejnar.specific_decision")


def _normalise(value: Any) -> str:
    return str(value or "").strip().casefold().rstrip(".,;)")


def _row_matches_identifiers(row: Any, identifiers: tuple[str, ...]) -> bool:
    case_number = _normalise(row.get("Sagsnummer", ""))
    link = _normalise(row.get("Link", ""))
    title = _normalise(row.get("Titel", ""))
    return any(
        identifier == case_number
        or identifier in case_number
        or identifier in link
        or identifier in title
        for identifier in identifiers
    )


def filter_specific_decision_results(
    query: str,
    ranked_indices: list[int],
    df: Any,
) -> list[int]:
    plan = classify_query(query)
    if plan.intent != QueryIntent.SPECIFIC_DECISION_SEARCH:
        return list(ranked_indices)

    identifiers = tuple(
        value
        for value in (_normalise(item) for item in plan.decision_identifiers)
        if value
    )
    if not identifiers:
        return list(ranked_indices)

    matches: list[int] = []
    for idx in ranked_indices:
        try:
            row = df.iloc[int(idx)]
        except (IndexError, TypeError, ValueError, AttributeError):
            continue
        if _row_matches_identifiers(row, identifiers):
            matches.append(int(idx))

    return matches if matches else list(ranked_indices)


def install_specific_decision_runtime(shared_module: Any | None = None) -> bool:
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_SPECIFIC_DECISION_RUNTIME_INSTALLED", False):
        return False

    original_hybrid = shared_module.hybrid_retrieval

    def specific_decision_hybrid(
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
            filtered = filter_specific_decision_results(query, list(base), df)
            return filtered[:top_final]
        except Exception:  # pragma: no cover - fail-open sikkerhedsnet
            _LOG.exception("Filtrering af specifikt kendelsesopslag fejlede")
            return base

    shared_module.hybrid_retrieval = specific_decision_hybrid
    shared_module._EJNAR_SPECIFIC_DECISION_RUNTIME_ORIGINAL = original_hybrid
    shared_module._EJNAR_SPECIFIC_DECISION_RUNTIME_INSTALLED = True
    return True

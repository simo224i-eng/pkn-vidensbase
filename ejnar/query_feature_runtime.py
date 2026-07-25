"""Produktionslag for konservativ query-feature-reranking.

Laget omrangerer kun den eksisterende candidate pool og er fail-open. Strength 0.12
blev valgt på frozen qrels v2 efter forbedring i NDCG, recall og judged precision.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from query_feature_rerank import rerank_by_query_features
except ImportError:
    from ejnar.query_feature_rerank import rerank_by_query_features

_LOG = logging.getLogger("ejnar.query_feature_runtime")
DEFAULT_STRENGTH = 0.12


def rerank_indices_by_query_features(
    query: str,
    ranked_indices: list[int],
    df: Any,
    *,
    strength: float = DEFAULT_STRENGTH,
) -> list[int]:
    if not ranked_indices or strength <= 0:
        return list(ranked_indices)

    candidates: list[dict[str, Any]] = []
    index_by_marker: dict[int, int] = {}
    for position, idx in enumerate(ranked_indices):
        try:
            row = dict(df.iloc[int(idx)])
        except (IndexError, TypeError, ValueError, AttributeError):
            continue
        row["_runtime_original_index"] = int(idx)
        row["_runtime_original_position"] = position
        candidates.append(row)
        index_by_marker[int(idx)] = int(idx)

    if not candidates:
        return list(ranked_indices)

    reranked = rerank_by_query_features(query, candidates, strength=strength)
    output = [
        int(item["_runtime_original_index"])
        for item in reranked
        if item.get("_runtime_original_index") in index_by_marker
    ]
    seen = set(output)
    output.extend(int(idx) for idx in ranked_indices if int(idx) not in seen)
    return output


def install_query_feature_runtime(
    shared_module: Any | None = None,
    *,
    strength: float = DEFAULT_STRENGTH,
) -> bool:
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_QUERY_FEATURE_RUNTIME_INSTALLED", False):
        return False

    original_hybrid = shared_module.hybrid_retrieval

    def query_feature_hybrid(
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
            return rerank_indices_by_query_features(
                query,
                list(base),
                df,
                strength=strength,
            )[:top_final]
        except Exception:  # pragma: no cover
            _LOG.exception("Query-feature-reranking fejlede")
            return base

    shared_module.hybrid_retrieval = query_feature_hybrid
    shared_module._EJNAR_QUERY_FEATURE_RUNTIME_ORIGINAL = original_hybrid
    shared_module._EJNAR_QUERY_FEATURE_RUNTIME_STRENGTH = float(strength)
    shared_module._EJNAR_QUERY_FEATURE_RUNTIME_INSTALLED = True
    return True

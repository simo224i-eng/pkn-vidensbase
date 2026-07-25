"""Runtime-lag for paragraph-BM25 ved præcise indholdssøgninger."""
from __future__ import annotations

import threading
from typing import Any

try:
    from paragraph_bm25 import ParagraphBM25Index, aggregate_decisions, decision_order_for_dataframe
    from paragraph_retrieval import build_corpus
    from query_intent import QueryIntent, classify_query
except ImportError:
    from ejnar.paragraph_bm25 import ParagraphBM25Index, aggregate_decisions, decision_order_for_dataframe
    from ejnar.paragraph_retrieval import build_corpus
    from ejnar.query_intent import QueryIntent, classify_query

_CACHE_LOCK = threading.Lock()
_CACHE: dict[tuple[int, int], ParagraphBM25Index] = {}


def _index_for_dataframe(df: Any) -> ParagraphBM25Index:
    key = (id(df), len(df))
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached is not None:
            return cached
    documents = df.to_dict("records")
    index = ParagraphBM25Index(build_corpus(documents))
    with _CACHE_LOCK:
        _CACHE.clear()
        _CACHE[key] = index
    return index


def clear_paragraph_index_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def install_paragraph_runtime(shared_module: Any | None = None) -> bool:
    """Tilføj paragraph-BM25 som ekstra RRF-stemme for exact-content-søgninger."""
    if shared_module is None:
        import shared as shared_module  # type: ignore
    if getattr(shared_module, "_EJNAR_PARAGRAPH_RUNTIME_INSTALLED", False):
        return False

    original_hybrid = shared_module.hybrid_retrieval

    def paragraph_hybrid(
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
        plan = classify_query(query)
        if plan.intent != QueryIntent.EXACT_CONTENT_SEARCH:
            return base

        try:
            index = _index_for_dataframe(df)
            paragraph_hits = index.search(query, limit=max(80, top_retrieve * 3))
            decision_hits = aggregate_decisions(
                paragraph_hits,
                limit=max(top_retrieve, top_final),
            )
            paragraph_order = decision_order_for_dataframe(decision_hits, df)
            if sub_idx is not None:
                allowed = {int(i) for i in sub_idx}
                paragraph_order = [idx for idx in paragraph_order if idx in allowed]
            if not paragraph_order:
                return base

            # Paragraph-rangeringen får to stemmer; eksisterende hybrid retrieval
            # forbliver recall-sikkerhedsnet og afgør stadig resultater uden BM25-hit.
            fused = shared_module.rrf_merge(
                [paragraph_order, paragraph_order, base],
                k=20,
            )
            ranked = [idx for idx, _ in sorted(fused.items(), key=lambda item: -item[1])]
            return ranked[:top_final]
        except Exception:
            # Paragraph-laget må aldrig gøre den eksisterende søgning utilgængelig.
            return base

    shared_module.hybrid_retrieval = paragraph_hybrid
    shared_module.clear_paragraph_index_cache = clear_paragraph_index_cache
    shared_module._EJNAR_PARAGRAPH_RUNTIME_ORIGINAL = original_hybrid
    shared_module._EJNAR_PARAGRAPH_RUNTIME_INSTALLED = True
    return True

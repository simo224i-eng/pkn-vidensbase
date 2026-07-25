"""Runtime-lag for hurtig paragraph-BM25 ved præcise indholdssøgninger.

Paragraph-rangeringen bygges kun over de kandidater, som den eksisterende hybrid-
retrieval allerede har fundet. Det fjerner den dyre cold-start på hele korpusset og
bevarer den eksisterende retrieval som recall-sikkerhedsnet.
"""
from __future__ import annotations

from typing import Any

try:
    from paragraph_bm25 import ParagraphBM25Index, aggregate_decisions
    from paragraph_retrieval import build_corpus
    from query_intent import QueryIntent, classify_query
except ImportError:
    from ejnar.paragraph_bm25 import ParagraphBM25Index, aggregate_decisions
    from ejnar.paragraph_retrieval import build_corpus
    from ejnar.query_intent import QueryIntent, classify_query


def clear_paragraph_index_cache() -> None:
    """Behold kompatibilitet med tidligere runtime; der er ikke længere en global cache."""
    return None


def _candidate_documents(df: Any, indices: list[int]) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for idx in indices:
        try:
            documents.append(dict(df.iloc[int(idx)]))
        except (IndexError, TypeError, ValueError):
            continue
    return documents


def _decision_order_for_candidates(decision_hits: Any, documents: list[dict[str, Any]], indices: list[int]) -> list[int]:
    by_case: dict[str, int] = {}
    by_link: dict[str, int] = {}
    for original_idx, document in zip(indices, documents):
        case_number = str(document.get("Sagsnummer", "") or "").strip().lower()
        link = str(document.get("Link", "") or "").strip().lower()
        if case_number:
            by_case.setdefault(case_number, int(original_idx))
        if link:
            by_link.setdefault(link, int(original_idx))

    ordered: list[int] = []
    seen: set[int] = set()
    for hit in decision_hits:
        idx = None
        case_key = str(hit.case_number or "").strip().lower()
        link_key = str(hit.link or "").strip().lower()
        if case_key:
            idx = by_case.get(case_key)
        if idx is None and link_key:
            idx = by_link.get(link_key)
        if idx is not None and idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ordered


def install_paragraph_runtime(shared_module: Any | None = None) -> bool:
    """Tilføj kandidatbaseret paragraph-BM25 ved exact-content-søgninger."""
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
        if plan.intent != QueryIntent.EXACT_CONTENT_SEARCH or not base:
            return base

        try:
            # Den underliggende exact/TF-IDF/hybrid-søgning leverer kandidatfeltet.
            # Paragraph-BM25 raffinerer kun dette felt og bygger derfor på højst de
            # kandidater, som allerede er returneret — ikke alle 5.000+ kendelser.
            candidate_indices = [int(idx) for idx in base]
            documents = _candidate_documents(df, candidate_indices)
            if not documents:
                return base

            index = ParagraphBM25Index(build_corpus(documents))
            paragraph_hits = index.search(query, limit=max(40, len(documents) * 3))
            decision_hits = aggregate_decisions(
                paragraph_hits,
                limit=len(documents),
            )
            paragraph_order = _decision_order_for_candidates(
                decision_hits,
                documents,
                candidate_indices,
            )
            if not paragraph_order:
                return base

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

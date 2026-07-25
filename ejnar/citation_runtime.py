"""Runtime-integration af paragraph-citater i Ejnars AI-kontekst.

Kun præcise indholdssøgninger bruger den nye kontekst. Brede praksissøgninger og alle
fejltilfælde falder tilbage til den eksisterende chunk-baserede kontekstbygger.
"""
from __future__ import annotations

import logging
from typing import Any

try:
    from paragraph_bm25 import ParagraphBM25Index
    from paragraph_retrieval import build_corpus, decision_identity
    from query_intent import QueryIntent, classify_query
except ImportError:  # package-import i tests/værktøjer
    from ejnar.paragraph_bm25 import ParagraphBM25Index
    from ejnar.paragraph_retrieval import build_corpus, decision_identity
    from ejnar.query_intent import QueryIntent, classify_query

_LOG = logging.getLogger("ejnar.citations")


def build_exact_citation_context(
    query: str,
    documents: list[dict[str, Any]],
    *,
    max_chunks_per_doc: int = 3,
    char_budget: int = 14_000,
) -> str:
    """Byg paragraph-kontekst med samme [Kilde X]-numre som dokumentlisten.

    Nummereringen er kritisk, fordi Ejnars promptregister og efterfølgende link-rendering
    forventer, at [Kilde 1] peger på documents[0], [Kilde 2] på documents[1] osv.
    """
    if not query.strip() or not documents or char_budget <= 0:
        return ""

    records = build_corpus(documents)
    if not records:
        return ""
    index = ParagraphBM25Index(records)
    hits = index.search(query, limit=max(40, len(documents) * max_chunks_per_doc * 4))
    if not hits:
        return ""

    source_number = {
        decision_identity(document): position
        for position, document in enumerate(documents, start=1)
    }
    counts: dict[str, int] = {}
    seen: set[str] = set()
    blocks: list[str] = []
    used = 0

    for hit in hits:
        record = hit.record
        number = source_number.get(record.decision_id)
        if number is None or record.paragraph_id in seen:
            continue
        count = counts.get(record.decision_id, 0)
        if count >= max_chunks_per_doc:
            continue

        label = record.case_number or record.title or f"Kilde {number}"
        block = f"[Kilde {number}] {label} — {record.section_title}\n{record.text}"
        separator = "\n\n" if blocks else ""
        required = len(separator) + len(block)
        if used + required > char_budget:
            break

        blocks.append(block)
        used += required
        seen.add(record.paragraph_id)
        counts[record.decision_id] = count + 1

    return "\n\n".join(blocks)


def install_citation_runtime(shared_module: Any | None = None) -> bool:
    """Erstat kontekstbyggeren med paragraph-citater ved exact-content-søgninger."""
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_CITATION_RUNTIME_INSTALLED", False):
        return False

    original_builder = shared_module.byg_fokuseret_kontekst

    def citation_aware_builder(
        query: str,
        documents: list[dict[str, Any]],
        max_chunks_per_doc: int = 3,
        *args: Any,
        **kwargs: Any,
    ) -> str:
        try:
            plan = classify_query(query)
            if plan.intent == QueryIntent.EXACT_CONTENT_SEARCH:
                context = build_exact_citation_context(
                    query,
                    documents,
                    max_chunks_per_doc=max_chunks_per_doc,
                )
                if context:
                    return context
        except Exception:  # pragma: no cover - fail-open sikkerhedsnet
            _LOG.exception("Citation-context fejlede; bruger eksisterende chunk-kontekst")

        return original_builder(
            query,
            documents,
            max_chunks_per_doc=max_chunks_per_doc,
            *args,
            **kwargs,
        )

    shared_module.byg_fokuseret_kontekst = citation_aware_builder
    shared_module._EJNAR_CITATION_RUNTIME_ORIGINAL = original_builder
    shared_module._EJNAR_CITATION_RUNTIME_INSTALLED = True
    return True

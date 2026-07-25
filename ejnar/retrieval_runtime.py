"""Runtime-integration mellem Ejnars query-router og den eksisterende RAG-pipeline.

Modulet holder integrationen isoleret fra ``shared.py``. Det installeres én gang fra
``app.py`` før Streamlit indlæser sidefilerne. Dermed kan den nuværende pipeline
forbedres trinvist uden endnu en stor blok logik i ``shared.py``.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict
import logging
import re
import threading
import time
from typing import Any

try:
    from query_intent import QueryIntent, RetrievalPlan, classify_query
except ImportError:  # package-import i tests/værktøjer
    from ejnar.query_intent import QueryIntent, RetrievalPlan, classify_query

_LOG = logging.getLogger("ejnar.retrieval")
_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)
_EVENTS_LOCK = threading.Lock()
_EXACT_INTENTS = {
    QueryIntent.EXACT_CONTENT_SEARCH,
    QueryIntent.SPECIFIC_DECISION_SEARCH,
}


def _plan_payload(plan: RetrievalPlan) -> dict[str, Any]:
    payload = asdict(plan)
    payload["intent"] = plan.intent.value
    return payload


def _record(stage: str, query: str, plan: RetrievalPlan, **details: Any) -> None:
    event = {
        "timestamp": time.time(),
        "stage": stage,
        "query": (query or "")[:300],
        "plan": _plan_payload(plan),
        "details": details,
    }
    with _EVENTS_LOCK:
        _EVENTS.append(event)
    _LOG.debug("Ejnar retrieval %s: %s", stage, event)


def get_retrieval_debug_events(*, clear: bool = False) -> list[dict[str, Any]]:
    """Returnér de seneste strukturerede routing-/retrievalhændelser."""
    with _EVENTS_LOCK:
        events = list(_EVENTS)
        if clear:
            _EVENTS.clear()
    return events


def _candidate_indices(df: Any, sub_idx: Any) -> list[int]:
    if sub_idx is not None and len(sub_idx) > 0:
        return [int(i) for i in sub_idx]
    return list(range(len(df)))


def _normalise_exact(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip()).lower()


def _exact_match_ranking(query: str, df: Any, sub_idx: Any, limit: int) -> list[int]:
    """Rangér dokumenter med direkte frase-/ID-match før den normale hybridrangering."""
    plan = classify_query(query)
    needles = [*plan.exact_phrases, *plan.decision_identifiers]
    needles = [_normalise_exact(str(n)) for n in needles if _normalise_exact(str(n))]
    if not needles:
        return []

    scored: list[tuple[float, int]] = []
    for idx in _candidate_indices(df, sub_idx):
        try:
            row = df.iloc[idx]
        except Exception:
            continue
        fields = [
            row.get("Sagsnummer", ""),
            row.get("Titel", ""),
            row.get("Tekst", ""),
            row.get("Link", ""),
        ]
        blob = _normalise_exact("\n".join(str(v or "") for v in fields))
        score = 0.0
        for needle in needles:
            occurrences = blob.count(needle)
            if occurrences:
                score += 100.0 + min(occurrences, 10)
                if _normalise_exact(str(row.get("Sagsnummer", ""))) == needle:
                    score += 200.0
        if score:
            scored.append((score, idx))
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [idx for _, idx in scored[:limit]]


def install_retrieval_runtime(shared_module: Any | None = None) -> bool:
    """Installér routeren oven på den eksisterende ``shared``-pipeline.

    Funktionen er idempotent, fordi Streamlit genkører ``app.py`` ved interaktioner.
    Returnerer ``True`` ved første installation og ``False`` ved senere kald.
    """
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_RETRIEVAL_RUNTIME_INSTALLED", False):
        return False

    original_classify = shared_module.klassificer_query
    original_expand = shared_module.udvid_query
    original_auto_filter = shared_module.auto_filter_query
    original_embedding_search = shared_module.embedding_soeg
    original_hybrid = shared_module.hybrid_retrieval

    def routed_classify(query: str) -> dict[str, Any]:
        plan = classify_query(query)
        _record("intent", query, plan)
        return {
            "type": plan.intent.value,
            "top_retrieve": plan.top_retrieve,
            "top_final": plan.top_final,
            "retrieval_plan": _plan_payload(plan),
        }

    def routed_expand(query: str) -> str:
        plan = classify_query(query)
        if not plan.expand_query:
            _record("query_expansion_skipped", query, plan)
            return query
        expanded = original_expand(query)
        _record("query_expansion", query, plan, changed=expanded != query)
        return expanded

    def routed_auto_filter(query: str, filter_options: dict) -> dict:
        plan = classify_query(query)
        if not plan.use_auto_filters:
            _record("auto_filters_skipped", query, plan)
            return {}
        result = original_auto_filter(query, filter_options)
        _record("auto_filters", query, plan, filters=result)
        return result

    def routed_embedding_search(
        query: str,
        df: Any,
        embeds: Any,
        sub_idx: Any = None,
        top_n: int = 30,
        use_hyde: bool = True,
    ) -> list:
        plan = classify_query(query)
        effective_hyde = bool(use_hyde and plan.intent not in _EXACT_INTENTS)
        if use_hyde and not effective_hyde:
            _record("hyde_disabled", query, plan)
        return original_embedding_search(
            query,
            df,
            embeds,
            sub_idx=sub_idx,
            top_n=top_n,
            use_hyde=effective_hyde,
        )

    def routed_hybrid(
        query: str,
        df: Any,
        vec: Any,
        mat: Any,
        embeds: Any,
        sub_idx: Any = None,
        top_retrieve: int = 40,
        top_final: int = 20,
    ) -> list[int]:
        plan = classify_query(query)
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
        if plan.intent not in _EXACT_INTENTS:
            return base

        direct = _exact_match_ranking(query, df, sub_idx, max(top_retrieve, top_final))
        if not direct:
            return base

        # Direkte tekst-/ID-match får to stemmer i RRF; den normale hybridrangering
        # bevares som recall-sikkerhedsnet.
        fused = shared_module.rrf_merge([direct, direct, base], k=20)
        ranked = [idx for idx, _ in sorted(fused.items(), key=lambda item: -item[1])]
        _record(
            "exact_match_boost",
            query,
            plan,
            direct_matches=len(direct),
            base_candidates=len(base),
        )
        return ranked[:top_final]

    shared_module.klassificer_query = routed_classify
    shared_module.udvid_query = routed_expand
    shared_module.auto_filter_query = routed_auto_filter
    shared_module.embedding_soeg = routed_embedding_search
    shared_module.hybrid_retrieval = routed_hybrid
    shared_module.get_retrieval_debug_events = get_retrieval_debug_events
    shared_module._EJNAR_RETRIEVAL_RUNTIME_ORIGINALS = {
        "klassificer_query": original_classify,
        "udvid_query": original_expand,
        "auto_filter_query": original_auto_filter,
        "embedding_soeg": original_embedding_search,
        "hybrid_retrieval": original_hybrid,
    }
    shared_module._EJNAR_RETRIEVAL_RUNTIME_INSTALLED = True
    _LOG.info("Ejnars intent-aware retrieval runtime er installeret")
    return True

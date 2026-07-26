"""Fail-open runtime-integration for Ejnars konservative query planner."""
from __future__ import annotations

from collections import deque
from dataclasses import asdict
import logging
import threading
import time
from typing import Any

try:
    from query_planner import QueryPlan, plan_query
except ImportError:  # package-import i tests/værktøjer
    from ejnar.query_planner import QueryPlan, plan_query


_LOG = logging.getLogger("ejnar.query_planner")
_EVENTS: deque[dict[str, Any]] = deque(maxlen=200)
_EVENTS_LOCK = threading.Lock()


def _record(plan: QueryPlan, *, fallback_used: bool) -> None:
    payload = asdict(plan)
    payload["intent"] = plan.intent.value
    event = {
        "timestamp": time.time(),
        "stage": "query_planner",
        "query": plan.original_query[:300],
        "plan": payload,
        "fallback_used": fallback_used,
    }
    with _EVENTS_LOCK:
        _EVENTS.append(event)
    _LOG.debug("Ejnar query planner: %s", event)


def get_query_planner_debug_events(*, clear: bool = False) -> list[dict[str, Any]]:
    with _EVENTS_LOCK:
        events = list(_EVENTS)
        if clear:
            _EVENTS.clear()
    return events


def install_query_planner_runtime(shared_module: Any | None = None) -> bool:
    """Installér planneren oven på Ejnars intent-aware query expansion.

    Genkendte domænebegreber bruger den deterministiske plan. Ukendte spørgsmål
    falder tilbage til den eksisterende query expansion, så usædvanlige skader
    ikke mister den nuværende recall. Enhver fejl er fail-open.
    """

    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_QUERY_PLANNER_RUNTIME_INSTALLED", False):
        return False

    original_expand = shared_module.udvid_query

    def planned_expand(query: str) -> str:
        try:
            plan = plan_query(query)
            if plan.applied:
                _record(plan, fallback_used=False)
                return plan.expanded_query

            fallback = original_expand(query)
            _record(plan, fallback_used=fallback != query)
            return fallback
        except Exception:  # pragma: no cover - fail-open sikkerhedsnet
            _LOG.exception("Query planning fejlede; bruger eksisterende expansion")
            return original_expand(query)

    shared_module.udvid_query = planned_expand
    shared_module.get_query_planner_debug_events = get_query_planner_debug_events
    shared_module._EJNAR_QUERY_PLANNER_RUNTIME_ORIGINAL = original_expand
    shared_module._EJNAR_QUERY_PLANNER_RUNTIME_INSTALLED = True
    return True

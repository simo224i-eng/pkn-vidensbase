"""Runtime layer that grounds Ejnar answers in the Board's actual reasoning."""
from __future__ import annotations

import logging
from typing import Any

try:
    from decision_grounding import build_decision_grounding_context, inject_grounding_policy
except ImportError:  # package import in tests/tools
    from ejnar.decision_grounding import build_decision_grounding_context, inject_grounding_policy


_LOG = logging.getLogger("ejnar.decision_grounding")


def install_decision_grounding_runtime(shared_module: Any | None = None) -> bool:
    """Wrap final context building and Ejnar answer prompts, fail-open.

    Install this after citation_runtime so exact-content and normal practice questions both
    receive a decision-core.  Retrieval rankings are not changed.
    """

    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_DECISION_GROUNDING_RUNTIME_INSTALLED", False):
        return False

    original_builder = shared_module.byg_fokuseret_kontekst
    original_llm = shared_module._llm
    original_stream = shared_module._llm_stream

    def grounded_context_builder(
        query: str,
        documents: list[dict[str, Any]],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        base = original_builder(query, documents, *args, **kwargs)
        try:
            grounding = build_decision_grounding_context(documents)
            if not grounding:
                return base
            if base:
                return f"{grounding}\n\nSPØRGSMÅLSRELEVANTE UDDRAG:\n{base}"
            return grounding
        except Exception:  # pragma: no cover - fail-open safety net
            _LOG.exception("Decision grounding context failed; using existing context")
            return base

    def grounded_llm(
        prompt: Any,
        max_tokens: int = 2000,
        model: str = "claude-sonnet-4-6",
    ) -> str:
        try:
            prompt = inject_grounding_policy(prompt)
        except Exception:  # pragma: no cover
            _LOG.exception("Decision grounding policy injection failed")
        return original_llm(prompt, max_tokens=max_tokens, model=model)

    def grounded_stream(
        prompt: Any,
        max_tokens: int = 2000,
        placeholder: Any = None,
    ) -> str:
        try:
            prompt = inject_grounding_policy(prompt)
        except Exception:  # pragma: no cover
            _LOG.exception("Decision grounding stream policy injection failed")
        return original_stream(prompt, max_tokens=max_tokens, placeholder=placeholder)

    shared_module.byg_fokuseret_kontekst = grounded_context_builder
    shared_module._llm = grounded_llm
    shared_module._llm_stream = grounded_stream
    shared_module._EJNAR_DECISION_GROUNDING_RUNTIME_ORIGINALS = {
        "byg_fokuseret_kontekst": original_builder,
        "_llm": original_llm,
        "_llm_stream": original_stream,
    }
    shared_module._EJNAR_DECISION_GROUNDING_RUNTIME_INSTALLED = True
    return True

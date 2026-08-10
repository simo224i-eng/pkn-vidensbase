"""Runtime injection of Ejnar's conservative practice-synthesis policy."""
from __future__ import annotations

import logging
from typing import Any

try:
    from practice_synthesis import inject_practice_synthesis_policy
except ImportError:  # package import in tests/tools
    from ejnar.practice_synthesis import inject_practice_synthesis_policy


_LOG = logging.getLogger("ejnar.practice_synthesis")


def install_practice_synthesis_runtime(shared_module: Any | None = None) -> bool:
    """Wrap final LLM calls after decision grounding, fail-open and idempotent."""
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_PRACTICE_SYNTHESIS_RUNTIME_INSTALLED", False):
        return False

    original_llm = shared_module._llm
    original_stream = shared_module._llm_stream

    def synthesis_llm(
        prompt: Any,
        max_tokens: int = 2000,
        model: str = "claude-sonnet-4-6",
    ) -> str:
        try:
            prompt = inject_practice_synthesis_policy(prompt)
        except Exception:  # pragma: no cover - fail-open safety net
            _LOG.exception("Practice synthesis policy injection failed")
        return original_llm(prompt, max_tokens=max_tokens, model=model)

    def synthesis_stream(
        prompt: Any,
        max_tokens: int = 2000,
        placeholder: Any = None,
    ) -> str:
        try:
            prompt = inject_practice_synthesis_policy(prompt)
        except Exception:  # pragma: no cover
            _LOG.exception("Practice synthesis stream policy injection failed")
        return original_stream(prompt, max_tokens=max_tokens, placeholder=placeholder)

    shared_module._llm = synthesis_llm
    shared_module._llm_stream = synthesis_stream
    shared_module._EJNAR_PRACTICE_SYNTHESIS_RUNTIME_ORIGINALS = {
        "_llm": original_llm,
        "_llm_stream": original_stream,
    }
    shared_module._EJNAR_PRACTICE_SYNTHESIS_RUNTIME_INSTALLED = True
    return True

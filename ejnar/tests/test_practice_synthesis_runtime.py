from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ejnar.decision_grounding_runtime import install_decision_grounding_runtime
from ejnar.practice_synthesis_runtime import install_practice_synthesis_runtime


class PracticeSynthesisRuntimeTests(unittest.TestCase):
    def _shared(self):
        def builder(query, documents, *args, **kwargs):
            return "BASE CONTEXT"

        def llm(prompt, max_tokens=2000, model="claude-sonnet-4-6"):
            return prompt

        def stream(prompt, max_tokens=2000, placeholder=None):
            return prompt

        return SimpleNamespace(
            byg_fokuseret_kontekst=builder,
            _llm=llm,
            _llm_stream=stream,
        )

    def _prompt(self):
        return [{
            "type": "text",
            "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
        }]

    def test_install_is_idempotent(self):
        shared = self._shared()
        self.assertTrue(install_practice_synthesis_runtime(shared))
        self.assertFalse(install_practice_synthesis_runtime(shared))

    def test_llm_and_stream_receive_synthesis_policy(self):
        shared = self._shared()
        install_practice_synthesis_runtime(shared)
        self.assertIn(
            "PRAKSISSYNTESE (OBLIGATORISK)",
            shared._llm(self._prompt())[0]["text"],
        )
        self.assertIn(
            "PRAKSISSYNTESE (OBLIGATORISK)",
            shared._llm_stream(self._prompt(), placeholder=object())[0]["text"],
        )

    def test_composes_with_decision_grounding_policy(self):
        shared = self._shared()
        install_decision_grounding_runtime(shared)
        install_practice_synthesis_runtime(shared)

        forwarded = shared._llm(self._prompt())
        text = forwarded[0]["text"]

        self.assertIn("AFGØRELSESGRUND (OBLIGATORISK)", text)
        self.assertIn("PRAKSISSYNTESE (OBLIGATORISK)", text)

    def test_runtime_is_fail_open(self):
        shared = self._shared()
        install_practice_synthesis_runtime(shared)
        with patch(
            "ejnar.practice_synthesis_runtime.inject_practice_synthesis_policy",
            side_effect=RuntimeError("boom"),
        ):
            forwarded = shared._llm(self._prompt())
        self.assertNotIn("PRAKSISSYNTESE (OBLIGATORISK)", forwarded[0]["text"])


if __name__ == "__main__":
    unittest.main()

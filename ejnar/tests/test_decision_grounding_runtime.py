from types import SimpleNamespace
import unittest
from unittest.mock import patch

from ejnar.decision_grounding_runtime import install_decision_grounding_runtime


class DecisionGroundingRuntimeTests(unittest.TestCase):
    def _shared(self, base_context="BASE CONTEXT"):
        def builder(query, documents, *args, **kwargs):
            return base_context

        def llm(prompt, max_tokens=2000, model="claude-sonnet-4-6"):
            return prompt

        def stream(prompt, max_tokens=2000, placeholder=None):
            return prompt

        return SimpleNamespace(
            byg_fokuseret_kontekst=builder,
            _llm=llm,
            _llm_stream=stream,
        )

    def test_install_is_idempotent(self):
        shared = self._shared()
        self.assertTrue(install_decision_grounding_runtime(shared))
        self.assertFalse(install_decision_grounding_runtime(shared))

    def test_context_prepends_board_reasoning_without_removing_existing_context(self):
        shared = self._shared()
        install_decision_grounding_runtime(shared)
        docs = [{
            "Sagsnummer": "1",
            "Titel": "Bjælke",
            "Tekst": """
## Nævnets bemærkninger
Forholdet var anmærket i tilstandsrapporten. Klageren får derfor ikke medhold.
""",
        }]

        context = shared.byg_fokuseret_kontekst("nedbrydning bjælke", docs)

        self.assertIn("AFGØRELSESKERNE", context)
        self.assertIn("tilstandsrapporten", context)
        self.assertIn("SPØRGSMÅLSRELEVANTE UDDRAG", context)
        self.assertIn("BASE CONTEXT", context)

    def test_lower_ranked_source_in_answer_context_is_also_grounded(self):
        shared = self._shared(base_context="[Kilde 8] relevant udsagn om bæreevne")
        install_decision_grounding_runtime(shared)
        docs = [
            {
                "Sagsnummer": str(number),
                "Titel": f"Kendelse {number}",
                "Tekst": (
                    "## Nævnets bemærkninger\n"
                    f"Nævnet finder grundlag {number}. Klageren får ikke medhold."
                ),
            }
            for number in range(1, 9)
        ]

        context = shared.byg_fokuseret_kontekst("bæreevne", docs)

        self.assertIn("[AFGØRELSESKERNE Kilde 8]", context)
        self.assertIn("grundlag 8", context)
        self.assertIn("[Kilde 8] relevant udsagn om bæreevne", context)

    def test_llm_wrapper_injects_decision_basis_policy(self):
        shared = self._shared()
        install_decision_grounding_runtime(shared)
        prompt = [{
            "type": "text",
            "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
        }]

        forwarded = shared._llm(prompt)

        self.assertIn("AFGØRELSESGRUND (OBLIGATORISK)", forwarded[0]["text"])

    def test_stream_wrapper_injects_same_policy(self):
        shared = self._shared()
        install_decision_grounding_runtime(shared)
        prompt = [{
            "type": "text",
            "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
        }]

        forwarded = shared._llm_stream(prompt, placeholder=object())

        self.assertIn("AFGØRELSESGRUND (OBLIGATORISK)", forwarded[0]["text"])

    def test_context_layer_is_fail_open(self):
        shared = self._shared()
        install_decision_grounding_runtime(shared)
        with patch(
            "ejnar.decision_grounding_runtime.build_decision_grounding_context",
            side_effect=RuntimeError("boom"),
        ):
            context = shared.byg_fokuseret_kontekst("query", [])
        self.assertEqual(context, "BASE CONTEXT")


if __name__ == "__main__":
    unittest.main()

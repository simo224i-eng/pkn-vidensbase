import unittest

from ejnar.practice_synthesis import inject_practice_synthesis_policy


class PracticeSynthesisPolicyTests(unittest.TestCase):
    def _prompt(self):
        return [
            {
                "type": "text",
                "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
            },
            {"type": "text", "text": "KENDELSER"},
        ]

    def test_policy_separates_direct_practice_from_indirect_support(self):
        grounded = inject_practice_synthesis_policy(self._prompt())
        text = grounded[0]["text"]
        self.assertIn("PRAKSISSYNTESE (OBLIGATORISK)", text)
        self.assertIn("har forrang", text)
        self.assertIn("DIREKTE PRAKSIS", text)
        self.assertIn("INDIREKTE STØTTE", text)
        self.assertIn("andet grundlag", text)

    def test_policy_forbids_raw_outcome_counting(self):
        grounded = inject_practice_synthesis_policy(self._prompt())
        text = grounded[0]["text"]
        self.assertIn("medhold/ikke medhold", text)
        self.assertIn("samme juridiske spørgsmål", text)
        self.assertIn("2 af 3 direkte relevante kendelser", text)

    def test_policy_does_not_call_one_or_two_cases_fast_practice(self):
        grounded = inject_practice_synthesis_policy(self._prompt())
        text = grounded[0]["text"]
        self.assertIn("Én direkte kendelse er et eksempel", text)
        self.assertIn("To direkte kendelser", text)
        self.assertIn("ikke i sig selv 'fast praksis'", text)

    def test_policy_is_idempotent_and_does_not_mutate_input(self):
        original = self._prompt()
        once = inject_practice_synthesis_policy(original)
        twice = inject_practice_synthesis_policy(once)
        self.assertNotEqual(original[0]["text"], once[0]["text"])
        self.assertEqual(
            once[0]["text"].count("PRAKSISSYNTESE (OBLIGATORISK)"),
            1,
        )
        self.assertEqual(twice, once)

    def test_non_ejnar_prompt_passes_through(self):
        prompt = [{"type": "text", "text": "Lav et resumé."}]
        self.assertEqual(inject_practice_synthesis_policy(prompt), prompt)


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.decision_grounding import extract_decision_grounding


class DecisionGroundingLocalWindowTests(unittest.TestCase):
    def test_concluded_issue_does_not_pull_later_issue_with_shared_generic_term(self):
        document = {
            "Tekst": """
## Nævnets bemærkninger og afgørelse
For ventilationen i tagrummet finder nævnet, at der er normale fugtværdier og ingen usædvanlig skimmel. Ventilationsforholdet udgør derfor ikke skade.

For vinduet finder nævnet, at der ses fugt og råd i bundstykket. Selskabet skal derfor anerkende vinduesforholdet.
""",
        }

        grounding = extract_decision_grounding(
            document,
            query="manglende ventilation tagrum normale fugtværdier skimmel",
        )

        self.assertIn("ventilationen i tagrummet", grounding.text)
        self.assertIn("udgør derfor ikke skade", grounding.text)
        self.assertNotIn("vinduet", grounding.text)
        self.assertNotIn("råd i bundstykket", grounding.text)
        self.assertEqual(grounding.paragraph_count, 1)


if __name__ == "__main__":
    unittest.main()

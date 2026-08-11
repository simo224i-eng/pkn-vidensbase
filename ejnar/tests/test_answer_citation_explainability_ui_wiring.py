from pathlib import Path
import unittest


PAGE = Path(__file__).resolve().parents[1] / "pages" / "ejnar.py"


class AnswerCitationExplainabilityUIWiringTests(unittest.TestCase):
    def test_page_wires_answer_claims_to_each_source_card(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn(
            "from answer_citation_explainability import render_source_claims_html",
            text,
        )
        self.assertIn(
            'claim_html = render_source_claims_html(\n'
            '                                    msg.get("tekst", ""), i + 1, source_count=len(kilder)',
            text,
        )

    def test_claim_card_precedes_decision_core_and_full_text(self):
        text = PAGE.read_text(encoding="utf-8")
        claim_pos = text.index("claim_html = render_source_claims_html(")
        core_pos = text.index(
            "core_html = render_source_decision_core_html(k, source_query)",
            claim_pos,
        )
        raw_pos = text.index('rå = k.get("Tekst", "")', core_pos)
        self.assertLess(claim_pos, core_pos)
        self.assertLess(core_pos, raw_pos)


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


PAGE = Path(__file__).resolve().parents[1] / "pages" / "ejnar.py"


class SourceExplainabilityUIWiringTests(unittest.TestCase):
    def test_page_wires_query_specific_source_core(self):
        text = PAGE.read_text(encoding="utf-8")
        self.assertIn(
            "from source_explainability import render_source_decision_core_html",
            text,
        )
        self.assertIn('"spørgsmål": f', text)
        self.assertIn('"spørgsmål": spørgsmål.strip()', text)
        self.assertIn('source_query = str(msg.get("spørgsmål") or "").strip()', text)
        self.assertIn(
            "core_html = render_source_decision_core_html(k, source_query)",
            text,
        )

    def test_source_core_is_rendered_before_full_decision_text(self):
        text = PAGE.read_text(encoding="utf-8")
        core_pos = text.index("core_html = render_source_decision_core_html(k, source_query)")
        raw_pos = text.index('rå = k.get("Tekst", "")', core_pos)
        self.assertLess(core_pos, raw_pos)


if __name__ == "__main__":
    unittest.main()

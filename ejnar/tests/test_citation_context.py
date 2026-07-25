import unittest

from ejnar.citation_context import build_citation_context
from ejnar.paragraph_bm25 import ParagraphBM25Index
from ejnar.paragraph_retrieval import build_corpus


class _ILoc:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, index):
        return self.rows[index]


class _Frame:
    def __init__(self, rows):
        self.rows = rows
        self.iloc = _ILoc(rows)

    def __len__(self):
        return len(self.rows)


class CitationContextTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {
                "Sagsnummer": "1001",
                "Titel": "Undertag ved kip",
                "Link": "https://example/1001",
                "Tekst": "## Faktiske forhold\nUndertaget er ikke ført sammen over kip.\n\nDer ses lidt skimmel.",
            },
            {
                "Sagsnummer": "1002",
                "Titel": "Gulv",
                "Link": "https://example/1002",
                "Tekst": "## Gulv\nGulvet er lokalt hævet, men fortsat fast og stabilt.",
            },
        ]
        self.df = _Frame(self.rows)
        self.index = ParagraphBM25Index(build_corpus(self.rows, min_chars=5))

    def test_context_only_uses_ranked_decisions(self):
        context = build_citation_context("undertag kip", self.df, [0], self.index)
        self.assertIn("Undertaget er ikke ført sammen over kip", context.text)
        self.assertNotIn("Gulvet er lokalt hævet", context.text)
        self.assertEqual(context.citations[0]["case_number"], "1001")

    def test_context_contains_stable_citation_ids(self):
        context = build_citation_context("gulv hævet", self.df, [1], self.index)
        citation = context.citations[0]
        self.assertTrue(citation["decision_id"].startswith("dec-"))
        self.assertTrue(citation["section_id"].startswith("sec-"))
        self.assertTrue(citation["paragraph_id"].startswith("par-"))

    def test_character_budget_is_respected(self):
        context = build_citation_context(
            "undertag kip skimmel",
            self.df,
            [0],
            self.index,
            char_budget=20,
        )
        self.assertLessEqual(context.used_characters, 20)
        self.assertTrue(context.truncated)

    def test_empty_ranked_list_returns_empty_context(self):
        context = build_citation_context("undertag", self.df, [], self.index)
        self.assertEqual(context.text, "")
        self.assertEqual(context.citations, ())

    def test_limits_paragraphs_per_decision(self):
        context = build_citation_context(
            "undertag kip skimmel",
            self.df,
            [0],
            self.index,
            max_paragraphs_per_decision=1,
            max_total_paragraphs=10,
        )
        self.assertLessEqual(len(context.citations), 1)


if __name__ == "__main__":
    unittest.main()

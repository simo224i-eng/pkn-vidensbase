import types
import unittest

from ejnar.citation_runtime import build_exact_citation_context, install_citation_runtime


class CitationRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.docs = [
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

    def test_source_numbers_follow_document_order(self):
        context = build_exact_citation_context(
            'Find kendelser hvor der står "undertaget er ikke ført sammen over kip"',
            self.docs,
        )
        self.assertIn("[Kilde 1]", context)
        self.assertIn("Undertaget er ikke ført sammen over kip", context)
        self.assertNotIn("[Kilde 2] 1001", context)

    def test_irrelevant_document_is_not_forced_into_context(self):
        context = build_exact_citation_context("undertag kip", self.docs)
        self.assertIn("Undertag", context)
        self.assertNotIn("Gulvet er lokalt hævet", context)

    def test_budget_is_respected(self):
        context = build_exact_citation_context("undertag kip", self.docs, char_budget=25)
        self.assertLessEqual(len(context), 25)

    def test_runtime_uses_original_for_broad_practice_question(self):
        shared = types.SimpleNamespace(
            byg_fokuseret_kontekst=lambda query, docs, max_chunks_per_doc=3: "ORIGINAL"
        )
        self.assertTrue(install_citation_runtime(shared))
        result = shared.byg_fokuseret_kontekst(
            "Hvad er Ankenævnets praksis om ventilation i tagrum?",
            self.docs,
        )
        self.assertEqual(result, "ORIGINAL")

    def test_runtime_uses_paragraph_context_for_exact_search(self):
        shared = types.SimpleNamespace(
            byg_fokuseret_kontekst=lambda query, docs, max_chunks_per_doc=3: "ORIGINAL"
        )
        install_citation_runtime(shared)
        result = shared.byg_fokuseret_kontekst(
            'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"',
            self.docs,
        )
        self.assertNotEqual(result, "ORIGINAL")
        self.assertIn("[Kilde 1]", result)

    def test_installation_is_idempotent(self):
        shared = types.SimpleNamespace(
            byg_fokuseret_kontekst=lambda query, docs, max_chunks_per_doc=3: "ORIGINAL"
        )
        self.assertTrue(install_citation_runtime(shared))
        self.assertFalse(install_citation_runtime(shared))


if __name__ == "__main__":
    unittest.main()

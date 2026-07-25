import unittest
from types import SimpleNamespace

from ejnar.paragraph_runtime import install_paragraph_runtime, clear_paragraph_index_cache


class FakeFrame:
    def __init__(self, rows):
        self._rows = rows
        self.iloc = self

    def __len__(self):
        return len(self._rows)

    def __getitem__(self, idx):
        return self._rows[idx]

    def to_dict(self, orient):
        self.assert_orient = orient
        return list(self._rows)


class ParagraphRuntimeTests(unittest.TestCase):
    def tearDown(self):
        clear_paragraph_index_cache()

    def _shared(self):
        def base(query, df, vec, mat, embeds, sub_idx=None, top_retrieve=40, top_final=20):
            return [1, 0]

        def rrf(rankings, k=20):
            scores = {}
            for ranking in rankings:
                for rank, idx in enumerate(ranking, start=1):
                    scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
            return scores

        return SimpleNamespace(hybrid_retrieval=base, rrf_merge=rrf)

    def test_install_is_idempotent(self):
        shared = self._shared()
        self.assertTrue(install_paragraph_runtime(shared))
        self.assertFalse(install_paragraph_runtime(shared))

    def test_exact_content_search_boosts_matching_decision(self):
        shared = self._shared()
        install_paragraph_runtime(shared)
        df = FakeFrame([
            {"Sagsnummer": "100", "Titel": "A", "Tekst": "Undertaget er ikke ført sammen over kip.", "Link": "a"},
            {"Sagsnummer": "200", "Titel": "B", "Tekst": "Almindelig ventilation i tagrum.", "Link": "b"},
        ])
        result = shared.hybrid_retrieval(
            'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"',
            df, None, None, None, top_final=2,
        )
        self.assertEqual(result[0], 0)

    def test_practice_search_keeps_base_order(self):
        shared = self._shared()
        install_paragraph_runtime(shared)
        df = FakeFrame([
            {"Sagsnummer": "100", "Titel": "A", "Tekst": "Undertag ved kip.", "Link": "a"},
            {"Sagsnummer": "200", "Titel": "B", "Tekst": "Ventilation i tagrum.", "Link": "b"},
        ])
        result = shared.hybrid_retrieval(
            "Hvad er praksis om ventilation i tagrum?",
            df, None, None, None, top_final=2,
        )
        self.assertEqual(result, [1, 0])

    def test_failure_falls_back_to_base(self):
        shared = self._shared()
        install_paragraph_runtime(shared)
        result = shared.hybrid_retrieval(
            'Find afgørelser hvor der står "kip"',
            object(), None, None, None, top_final=2,
        )
        self.assertEqual(result, [1, 0])


if __name__ == "__main__":
    unittest.main()

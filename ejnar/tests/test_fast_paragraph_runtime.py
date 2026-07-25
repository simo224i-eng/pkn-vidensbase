import unittest
from types import SimpleNamespace

from ejnar.paragraph_runtime import install_paragraph_runtime


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows
        self.iloc = self

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, idx):
        return self.rows[idx]


class FastParagraphRuntimeTests(unittest.TestCase):
    def test_paragraph_layer_cannot_introduce_non_candidate_decision(self):
        def base(query, df, vec, mat, embeds, sub_idx=None, top_retrieve=40, top_final=20):
            return [1, 0]

        def rrf(rankings, k=20):
            scores = {}
            for ranking in rankings:
                for rank, idx in enumerate(ranking, start=1):
                    scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank)
            return scores

        shared = SimpleNamespace(hybrid_retrieval=base, rrf_merge=rrf)
        install_paragraph_runtime(shared)
        df = FakeFrame([
            {"Sagsnummer": "100", "Titel": "A", "Tekst": "Undertag ved kip", "Link": "a"},
            {"Sagsnummer": "200", "Titel": "B", "Tekst": "Ventilation ved kip", "Link": "b"},
            {
                "Sagsnummer": "300",
                "Titel": "Ikke kandidat",
                "Tekst": "Undertaget er ikke ført sammen over kip",
                "Link": "c",
            },
        ])
        result = shared.hybrid_retrieval(
            'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"',
            df,
            None,
            None,
            None,
            top_final=2,
        )
        self.assertEqual(set(result), {0, 1})
        self.assertNotIn(2, result)


if __name__ == "__main__":
    unittest.main()

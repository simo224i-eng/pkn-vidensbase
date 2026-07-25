import types
import unittest
from unittest.mock import Mock

import pandas as pd

from ejnar.retrieval_runtime import install_retrieval_runtime, get_retrieval_debug_events


class RetrievalRuntimeTests(unittest.TestCase):
    def setUp(self):
        get_retrieval_debug_events(clear=True)
        self.original_expand = Mock(return_value="udvidet query")
        self.original_auto_filter = Mock(return_value={"Mangeltype": ["Tag"]})
        self.original_embedding = Mock(return_value=[(0, 0.9)])
        self.original_hybrid = Mock(return_value=[1, 0])
        self.shared = types.SimpleNamespace(
            klassificer_query=Mock(return_value={}),
            udvid_query=self.original_expand,
            auto_filter_query=self.original_auto_filter,
            embedding_soeg=self.original_embedding,
            hybrid_retrieval=self.original_hybrid,
            rrf_merge=lambda rankings, k=60: {
                idx: sum(1.0 / (k + rank + 1)
                         for ranking in rankings
                         for rank, candidate in enumerate(ranking)
                         if candidate == idx)
                for ranking in rankings for idx in ranking
            },
        )
        self.assertTrue(install_retrieval_runtime(self.shared))

    def test_installation_is_idempotent(self):
        self.assertFalse(install_retrieval_runtime(self.shared))

    def test_exact_search_skips_expansion_and_auto_filters(self):
        query = 'Find kendelser hvor der står "undertaget er ikke ført sammen over kip"'
        self.assertEqual(self.shared.udvid_query(query), query)
        self.assertEqual(self.shared.auto_filter_query(query, {"Mangeltype": ["Tag"]}), {})
        self.original_expand.assert_not_called()
        self.original_auto_filter.assert_not_called()

    def test_exact_search_disables_hyde(self):
        query = 'Find kendelser hvor der står "undertaget er ikke ført sammen over kip"'
        self.shared.embedding_soeg(query, None, object(), top_n=5, use_hyde=True)
        self.assertFalse(self.original_embedding.call_args.kwargs["use_hyde"])

    def test_practice_search_preserves_broad_tools(self):
        query = "Hvad siger praksis generelt om utætte tage?"
        self.assertEqual(self.shared.udvid_query(query), "udvidet query")
        self.assertEqual(
            self.shared.auto_filter_query(query, {"Mangeltype": ["Tag"]}),
            {"Mangeltype": ["Tag"]},
        )
        self.shared.embedding_soeg(query, None, object(), use_hyde=True)
        self.assertTrue(self.original_embedding.call_args.kwargs["use_hyde"])

    def test_exact_phrase_is_boosted_ahead_of_base_ranking(self):
        query = 'Find kendelser hvor der står "ikke ført sammen over kip"'
        df = pd.DataFrame([
            {"Sagsnummer": "1", "Titel": "Anden sag", "Tekst": "Intet match", "Link": "a"},
            {"Sagsnummer": "2", "Titel": "Tag", "Tekst": "Undertaget er ikke ført sammen over kip.", "Link": "b"},
        ])
        result = self.shared.hybrid_retrieval(
            query, df, object(), object(), object(), top_retrieve=10, top_final=2
        )
        self.assertEqual(result[0], 1)
        self.assertTrue(any(e["stage"] == "exact_match_boost" for e in get_retrieval_debug_events()))


if __name__ == "__main__":
    unittest.main()

from types import SimpleNamespace
import unittest

import pandas as pd

from ejnar.query_feature_runtime import (
    install_query_feature_runtime,
    rerank_indices_by_query_features,
)


class QueryFeatureRuntimeTests(unittest.TestCase):
    def test_zero_strength_preserves_order(self):
        frame = pd.DataFrame([{"Titel": "Tag"}, {"Titel": "Gulv"}])
        self.assertEqual(
            rerank_indices_by_query_features("tag", [1, 0], frame, strength=0),
            [1, 0],
        )

    def test_matching_candidate_can_move_up(self):
        frame = pd.DataFrame([
            {"Titel": "Gulv", "Excerpt": "", "Tekst": "Kosmetisk gulv"},
            {"Titel": "Tag", "Excerpt": "", "Tekst": "Utæt tag med fugt"},
        ])
        result = rerank_indices_by_query_features("utæt tag med fugt", [0, 1], frame, strength=0.12)
        self.assertEqual(result[0], 1)

    def test_install_is_idempotent(self):
        shared = SimpleNamespace(hybrid_retrieval=lambda *args, **kwargs: [0])
        self.assertTrue(install_query_feature_runtime(shared))
        self.assertFalse(install_query_feature_runtime(shared))

    def test_runtime_is_fail_open(self):
        shared = SimpleNamespace(hybrid_retrieval=lambda *args, **kwargs: [0, 1])
        install_query_feature_runtime(shared)
        result = shared.hybrid_retrieval("tag", object(), None, None, None)
        self.assertEqual(result, [0, 1])


if __name__ == "__main__":
    unittest.main()

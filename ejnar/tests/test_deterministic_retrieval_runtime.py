from types import SimpleNamespace
import unittest

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from ejnar.deterministic_retrieval_runtime import (
    DEFAULT_WEIGHT_SCALE,
    fixed_point_tfidf_ranking,
    install_deterministic_retrieval_runtime,
    stable_embedding_ranking,
    stable_rrf_order,
    stable_score_ranking,
)


class _Vectorizer:
    def __init__(self, vector):
        self.vector = vector

    def transform(self, values):
        return self.vector


class _BrokenVectorizer:
    def transform(self, values):
        raise RuntimeError("boom")


class DeterministicRetrievalRuntimeTests(unittest.TestCase):
    def test_sub_epsilon_score_drift_collapses_to_stable_index_order(self):
        first = stable_score_ranking(
            [0.300000000001, 0.300000000002],
            [9, 4],
            top_n=2,
            min_score=0.01,
            decimals=10,
        )
        second = stable_score_ranking(
            [0.300000000002, 0.300000000001],
            [9, 4],
            top_n=2,
            min_score=0.01,
            decimals=10,
        )
        self.assertEqual(first, [4, 9])
        self.assertEqual(second, [4, 9])

    def test_material_score_difference_is_preserved(self):
        ranked = stable_score_ranking(
            [0.31, 0.30], [9, 4], top_n=2, min_score=0.01
        )
        self.assertEqual(ranked, [9, 4])

    def test_threshold_uses_quantised_score(self):
        ranked = stable_score_ranking(
            [0.010000000001, 0.01000001],
            [1, 2],
            top_n=2,
            min_score=0.01,
            decimals=10,
        )
        self.assertEqual(ranked, [2])

    def test_fixed_point_tfidf_collapses_sub_scale_feature_drift(self):
        query = csr_matrix([[1.0]])
        # Both feature weights quantise to exactly 3,000,000 at scale 1e7.
        documents = csr_matrix([[0.30000000001], [0.30000000002]])
        fixed_documents = documents.copy()
        fixed_documents.data = np.rint(
            fixed_documents.data * DEFAULT_WEIGHT_SCALE
        ).astype(np.int32)
        ranked = fixed_point_tfidf_ranking(
            query,
            fixed_documents,
            [9, 4],
            top_n=2,
        )
        self.assertEqual(ranked, [4, 9])

    def test_fixed_point_tfidf_preserves_material_gap(self):
        query = csr_matrix([[1.0]])
        documents = csr_matrix([[0.31], [0.30]])
        fixed_documents = documents.copy()
        fixed_documents.data = np.rint(
            fixed_documents.data * DEFAULT_WEIGHT_SCALE
        ).astype(np.int32)
        ranked = fixed_point_tfidf_ranking(
            query,
            fixed_documents,
            [9, 4],
            top_n=2,
        )
        self.assertEqual(ranked, [9, 4])

    def test_fixed_point_threshold_is_applied_in_integer_space(self):
        query = csr_matrix([[1.0]])
        documents = csr_matrix([[0.010000001], [0.0100001]])
        fixed_documents = documents.copy()
        fixed_documents.data = np.rint(
            fixed_documents.data * DEFAULT_WEIGHT_SCALE
        ).astype(np.int32)
        ranked = fixed_point_tfidf_ranking(
            query,
            fixed_documents,
            [1, 2],
            top_n=2,
        )
        # 0.010000001 rounds to the exact 0.01 threshold and is excluded.
        self.assertEqual(ranked, [2])

    def test_embedding_and_rrf_ties_use_global_index(self):
        self.assertEqual(
            stable_embedding_ranking([(9, 0.5), (4, 0.5)], top_n=2),
            [4, 9],
        )
        self.assertEqual(stable_rrf_order({9: 1.0, 4: 1.0}, top_n=2), [4, 9])

    def test_install_is_idempotent(self):
        shared = SimpleNamespace(hybrid_retrieval=lambda *args, **kwargs: [0])
        self.assertTrue(install_deterministic_retrieval_runtime(shared))
        self.assertFalse(install_deterministic_retrieval_runtime(shared))

    def test_lexical_runtime_uses_fixed_point_and_global_index_tie_break(self):
        shared = SimpleNamespace(
            hybrid_retrieval=lambda *args, **kwargs: [99],
            embedding_soeg=lambda *args, **kwargs: [],
            rrf_merge=lambda rankings, k=60: {
                idx: sum(
                    1.0 / (k + rank + 1)
                    for ranking in rankings
                    for rank, value in enumerate(ranking)
                    if value == idx
                )
                for idx in {value for ranking in rankings for value in ranking}
            },
        )
        install_deterministic_retrieval_runtime(shared)
        frame = pd.DataFrame([{"Titel": "A"}, {"Titel": "B"}])
        matrix = csr_matrix([[0.30000000001], [0.30000000002]])
        vectorizer = _Vectorizer(csr_matrix([[1.0]]))

        # Reverse the candidate universe. Equal fixed-point scores must still use the
        # stable *global* index, not candidate input order.
        result = shared.hybrid_retrieval(
            "q",
            frame,
            vectorizer,
            matrix,
            None,
            sub_idx=[1, 0],
            top_retrieve=2,
            top_final=2,
        )
        self.assertEqual(result, [0, 1])

    def test_runtime_is_fail_open(self):
        shared = SimpleNamespace(
            hybrid_retrieval=lambda *args, **kwargs: [7, 8],
            embedding_soeg=lambda *args, **kwargs: [],
            rrf_merge=lambda *args, **kwargs: {},
        )
        install_deterministic_retrieval_runtime(shared)
        result = shared.hybrid_retrieval(
            "q",
            object(),
            _BrokenVectorizer(),
            object(),
            None,
        )
        self.assertEqual(result, [7, 8])


if __name__ == "__main__":
    unittest.main()

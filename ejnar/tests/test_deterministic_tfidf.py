import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shared


class DeterministicTfidfTests(unittest.TestCase):
    DOCS = ["alfa beta gamma delta", "alfa beta epsilon zeta", "alfa eta theta iota"]

    def test_ties_at_limit_break_alphabetically(self):
        # "alfa" forekommer 3 gange, "beta" 2, resten 1 gang: ved grænsen på 4
        # er der uafgjort mellem 7 termer med hyppighed 1 → de alfabetisk første.
        vec = shared.DeterministicTfidfVectorizer(max_features=4)
        vec.fit(self.DOCS)
        self.assertEqual(sorted(vec.vocabulary_), ["alfa", "beta", "delta", "epsilon"])

    def test_matches_sklearn_without_limit(self):
        from sklearn.feature_extraction.text import TfidfVectorizer

        a = shared.DeterministicTfidfVectorizer(ngram_range=(1, 2)).fit_transform(self.DOCS)
        b = TfidfVectorizer(ngram_range=(1, 2)).fit_transform(self.DOCS)
        self.assertEqual((a != b).nnz, 0)

    def test_transform_uses_limited_vocabulary(self):
        vec = shared.DeterministicTfidfVectorizer(max_features=4)
        mat = vec.fit_transform(self.DOCS)
        self.assertEqual(mat.shape, (3, 4))
        self.assertEqual(vec.transform(["zeta theta"]).nnz, 0)
        self.assertEqual(vec.transform(["delta"]).nnz, 1)


if __name__ == "__main__":
    unittest.main()

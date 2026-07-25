from types import SimpleNamespace
import unittest

from ejnar.specific_decision_runtime import (
    filter_specific_decision_results,
    install_specific_decision_runtime,
)


class FakeFrame:
    def __init__(self, rows):
        self.rows = rows
        self.iloc = self

    def __getitem__(self, idx):
        return self.rows[idx]


class SpecificDecisionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.df = FakeFrame([
            {"Sagsnummer": "98097", "Titel": "Den efterspurgte kendelse", "Link": "https://example/98097"},
            {"Sagsnummer": "74011 (806/08)", "Titel": "Anden kendelse", "Link": "https://example/74011"},
            {"Sagsnummer": "72700 (798/08)", "Titel": "Kendelse", "Link": "https://example/72700"},
        ])

    def test_specific_lookup_keeps_only_matching_case(self):
        result = filter_specific_decision_results(
            "Find kendelse nr. 98097",
            [0, 1, 2],
            self.df,
        )
        self.assertEqual(result, [0])

    def test_identifier_matches_formatted_case_number(self):
        result = filter_specific_decision_results(
            "Find kendelse nr. 72700",
            [1, 2, 0],
            self.df,
        )
        self.assertEqual(result, [2])

    def test_missing_identifier_match_preserves_fallback_results(self):
        result = filter_specific_decision_results(
            "Find kendelse nr. 100123",
            [1, 0, 2],
            self.df,
        )
        self.assertEqual(result, [1, 0, 2])

    def test_non_specific_query_preserves_order(self):
        result = filter_specific_decision_results(
            "Hvad er praksis om råd i vinduer?",
            [2, 0, 1],
            self.df,
        )
        self.assertEqual(result, [2, 0, 1])

    def test_installed_runtime_filters_and_is_idempotent(self):
        def base(*args, **kwargs):
            return [1, 0, 2]

        shared = SimpleNamespace(hybrid_retrieval=base)
        self.assertTrue(install_specific_decision_runtime(shared))
        self.assertFalse(install_specific_decision_runtime(shared))
        result = shared.hybrid_retrieval(
            "Find kendelse nr. 98097",
            self.df,
            None,
            None,
            None,
        )
        self.assertEqual(result, [0])


if __name__ == "__main__":
    unittest.main()

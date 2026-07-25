import json
import tempfile
import unittest
from pathlib import Path

from ejnar.evaluation.metrics import (
    EvaluationCase,
    aggregate,
    evaluate_case,
    load_results,
)


class EvaluationMetricsTests(unittest.TestCase):
    def case(self, **overrides):
        values = {
            "question_id": "EJ-001",
            "query": "Find kendelsen",
            "intent": "specific_decision_search",
            "expected_decision_ids": ("100123",),
            "expected_terms": ("undertag", "kip"),
            "expected_phrase": "ikke ført sammen over kip",
            "notes": "",
        }
        values.update(overrides)
        return EvaluationCase(**values)

    def test_recall_mrr_and_ndcg(self):
        results = [
            {"Sagsnummer": "999", "Tekst": "andet"},
            {"Sagsnummer": "100123", "Tekst": "undertag ikke ført sammen over kip"},
        ]
        metrics = evaluate_case(self.case(), results)
        self.assertEqual(metrics.recall_at_5, 1.0)
        self.assertEqual(metrics.reciprocal_rank, 0.5)
        self.assertGreater(metrics.ndcg_at_10, 0.0)
        self.assertEqual(metrics.first_relevant_rank, 2)

    def test_missing_expected_result_is_zero_not_none(self):
        metrics = evaluate_case(self.case(), [{"Sagsnummer": "999", "Tekst": "andet"}])
        self.assertEqual(metrics.recall_at_5, 0.0)
        self.assertEqual(metrics.reciprocal_rank, 0.0)
        self.assertEqual(metrics.ndcg_at_10, 0.0)

    def test_no_ground_truth_is_excluded_from_recall(self):
        metrics = evaluate_case(
            self.case(expected_decision_ids=()),
            [{"Sagsnummer": "999", "Tekst": "undertag ved kip"}],
        )
        self.assertIsNone(metrics.recall_at_5)
        self.assertIsNone(metrics.reciprocal_rank)
        self.assertIsNone(metrics.ndcg_at_10)

    def test_term_coverage_and_exact_phrase(self):
        metrics = evaluate_case(
            self.case(),
            [{"Sagsnummer": "100123", "Tekst": "Undertag er ikke ført sammen over kip"}],
        )
        self.assertEqual(metrics.expected_term_coverage, 1.0)
        self.assertTrue(metrics.exact_phrase_hit)

    def test_unique_decisions_deduplicates(self):
        metrics = evaluate_case(
            self.case(expected_decision_ids=()),
            [
                {"Sagsnummer": "100123", "Tekst": "a"},
                {"Sagsnummer": "100123", "Tekst": "b"},
                {"Sagsnummer": "100124", "Tekst": "c"},
            ],
        )
        self.assertEqual(metrics.unique_decisions, 2)

    def test_jsonl_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "results.jsonl"
            path.write_text(json.dumps({"question_id": "EJ-001", "results": []}) + "\n")
            self.assertEqual(load_results(path), {"EJ-001": []})

    def test_aggregate_ignores_missing_ground_truth(self):
        with_gt = evaluate_case(self.case(), [{"Sagsnummer": "100123", "Tekst": "undertag kip"}])
        without_gt = evaluate_case(self.case(question_id="EJ-002", expected_decision_ids=()), [])
        summary = aggregate([with_gt, without_gt])
        self.assertEqual(summary["questions"], 2)
        self.assertEqual(summary["questions_with_expected_ids"], 1)
        self.assertEqual(summary["mean_recall_at_5"], 1.0)


if __name__ == "__main__":
    unittest.main()

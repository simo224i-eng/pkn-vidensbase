import csv
from pathlib import Path
import tempfile
import unittest

from ejnar.evaluation.qrels_metrics import Qrel, evaluate, evaluate_case, load_qrels


class QrelsMetricsTests(unittest.TestCase):
    def test_load_qrels_excludes_uncertain_and_low_confidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qrels.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["question_id", "case_number", "relevance", "confidence", "source", "link"],
                )
                writer.writeheader()
                writer.writerow({"question_id": "Q1", "case_number": "1", "relevance": 2, "confidence": 0.9})
                writer.writerow({"question_id": "Q1", "case_number": "2", "relevance": -1, "confidence": 0.9})
                writer.writerow({"question_id": "Q1", "case_number": "3", "relevance": 1, "confidence": 0.4})
            loaded = load_qrels(path, min_confidence=0.5)
        self.assertEqual([item.case_number for item in loaded], ["1"])

    def test_case_metrics_use_graded_relevance(self):
        qrels = [
            Qrel("Q1", "A", 2, 0.9),
            Qrel("Q1", "B", 1, 0.9),
            Qrel("Q1", "C", 0, 0.9),
        ]
        metrics = evaluate_case(
            "Q1",
            qrels,
            [
                {"Sagsnummer": "C"},
                {"Sagsnummer": "A"},
                {"Sagsnummer": "X"},
                {"Sagsnummer": "B"},
            ],
        )
        self.assertEqual(metrics.first_relevant_rank, 2)
        self.assertEqual(metrics.reciprocal_rank, 0.5)
        self.assertEqual(metrics.recall_at_5, 1.0)
        self.assertGreater(metrics.ndcg_at_10, 0.0)
        self.assertLess(metrics.ndcg_at_10, 1.0)

    def test_unjudged_results_lower_coverage_not_judged_precision(self):
        qrels = [Qrel("Q1", "A", 1, 0.9), Qrel("Q1", "B", 0, 0.9)]
        metrics = evaluate_case(
            "Q1",
            qrels,
            [{"Sagsnummer": "X"}, {"Sagsnummer": "A"}, {"Sagsnummer": "Y"}],
        )
        self.assertAlmostEqual(metrics.judged_coverage_at_5, 1 / 3)
        self.assertEqual(metrics.judged_precision_at_5, 1.0)

    def test_evaluate_aggregates_multiple_questions(self):
        report = evaluate(
            [Qrel("Q1", "A", 1, 0.9), Qrel("Q2", "B", 2, 0.9)],
            {"Q1": [{"Sagsnummer": "A"}], "Q2": [{"Sagsnummer": "B"}]},
        )
        self.assertEqual(report["summary"]["questions"], 2)
        self.assertEqual(report["summary"]["mrr"], 1.0)
        self.assertEqual(report["summary"]["mean_recall_at_5"], 1.0)

    def test_link_can_match_when_case_number_differs(self):
        metrics = evaluate_case(
            "Q1",
            [Qrel("Q1", "A", 2, 0.9, link="https://example/doc")],
            [{"Sagsnummer": "formatted A", "Link": "https://example/doc"}],
        )
        self.assertEqual(metrics.first_relevant_rank, 1)


if __name__ == "__main__":
    unittest.main()

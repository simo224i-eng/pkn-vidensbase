import unittest

from ejnar.evaluation.retrieval_reproducibility import compare_runs, run_digest


class RetrievalReproducibilityTests(unittest.TestCase):
    def _run(self, q1=("1", "2"), q2=("3",)):
        return [
            {
                "question_id": "Q1",
                "latency_ms": 123.4,
                "results": [
                    {"Sagsnummer": value, "Titel": f"Sag {value}"}
                    for value in q1
                ],
            },
            {
                "question_id": "Q2",
                "latency_ms": 999.9,
                "results": [
                    {"Sagsnummer": value, "Titel": f"Sag {value}"}
                    for value in q2
                ],
            },
        ]

    def test_identical_results_ignore_latency(self):
        left = self._run()
        right = self._run()
        right[0]["latency_ms"] = 0.1
        report = compare_runs([("seed1", left), ("seed2", right)])
        self.assertTrue(report["exact_reproducibility"])
        self.assertEqual(report["summary"]["affected_unique_questions"], 0)
        self.assertEqual(report["runs"][0]["sha256"], report["runs"][1]["sha256"])

    def test_order_only_difference_is_reported_separately(self):
        report = compare_runs([
            ("seed1", self._run(q1=("1", "2"))),
            ("seed2", self._run(q1=("2", "1"))),
        ])
        self.assertFalse(report["exact_reproducibility"])
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["ordered_result_mismatches"], 1)
        self.assertEqual(comparison["set_mismatches"], 0)
        self.assertTrue(comparison["questions"][0]["set_match"])
        self.assertEqual(comparison["questions"][0]["first_different_rank"], 1)

    def test_candidate_set_difference_is_reported(self):
        report = compare_runs([
            ("seed1", self._run(q1=("1", "2"))),
            ("seed2", self._run(q1=("1", "9"))),
        ])
        comparison = report["comparisons"][0]
        self.assertEqual(comparison["set_mismatches"], 1)
        row = comparison["questions"][0]
        self.assertEqual(row["baseline_only"], ["case:2"])
        self.assertEqual(row["other_only"], ["case:9"])

    def test_missing_question_breaks_reproducibility(self):
        report = compare_runs([
            ("seed1", self._run()),
            ("seed2", self._run()[:1]),
        ])
        self.assertFalse(report["exact_reproducibility"])
        self.assertEqual(report["comparisons"][0]["missing_questions"], ["Q2"])

    def test_digest_depends_on_ordered_decisions_not_input_row_order(self):
        run = self._run()
        from ejnar.evaluation.retrieval_reproducibility import canonical_run
        self.assertEqual(run_digest(canonical_run(run)), run_digest(canonical_run(list(reversed(run)))))

    def test_duplicate_decision_identity_is_rejected(self):
        bad = self._run(q1=("1", "1"))
        with self.assertRaises(ValueError):
            compare_runs([("a", bad), ("b", self._run())])


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.evaluation.compare_reports import compare_reports, render_markdown


class CompareReportsTests(unittest.TestCase):
    def report(self, recall=0.8, mrr=0.7, latency=100):
        return {
            "summary": {
                "mean_recall_at_5": recall,
                "mean_recall_at_10": recall,
                "mean_recall_at_20": recall,
                "mrr": mrr,
                "mean_ndcg_at_10": mrr,
                "exact_phrase_hit_rate": recall,
                "mean_expected_term_coverage": recall,
            },
            "run": {"mean_latency_ms": latency},
        }

    def test_improvement_passes(self):
        result = compare_reports(self.report(), self.report(recall=0.85, mrr=0.75))
        self.assertTrue(result["passed"])
        self.assertEqual(result["regressions"], [])

    def test_material_recall_drop_fails(self):
        result = compare_reports(self.report(), self.report(recall=0.70))
        self.assertFalse(result["passed"])
        self.assertIn("mean_recall_at_5", result["regressions"])

    def test_small_drop_within_threshold_passes(self):
        result = compare_reports(self.report(), self.report(recall=0.78, mrr=0.68))
        self.assertTrue(result["passed"])

    def test_missing_ground_truth_metric_is_not_regression(self):
        baseline = self.report()
        candidate = self.report()
        baseline["summary"]["mrr"] = None
        candidate["summary"]["mrr"] = None
        result = compare_reports(baseline, candidate)
        self.assertTrue(result["passed"])

    def test_latency_ratio_is_reported_but_not_blocking(self):
        result = compare_reports(self.report(latency=100), self.report(latency=250))
        self.assertEqual(result["latency"]["ratio"], 2.5)
        self.assertTrue(result["passed"])

    def test_markdown_marks_regression(self):
        result = compare_reports(self.report(), self.report(recall=0.60))
        markdown = render_markdown(result)
        self.assertIn("Regression fundet", markdown)
        self.assertIn("⚠️", markdown)


if __name__ == "__main__":
    unittest.main()

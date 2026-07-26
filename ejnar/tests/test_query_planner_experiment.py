import unittest

from ejnar.evaluation.run_query_planner_experiment import (
    MAX_LATENCY_RATIO,
    PLANNER_REGRESSION_THRESHOLDS,
    apply_planner_policy,
    evaluate_payloads,
)


class QueryPlannerExperimentTests(unittest.TestCase):
    def test_thresholds_are_stricter_than_general_regression_gate(self):
        self.assertTrue(PLANNER_REGRESSION_THRESHOLDS)
        self.assertTrue(
            all(value <= 0.01 for value in PLANNER_REGRESSION_THRESHOLDS.values())
        )
        self.assertIn(
            "mean_judged_precision_at_5",
            PLANNER_REGRESSION_THRESHOLDS,
        )

    def test_evaluate_payloads_adds_pipeline_metadata(self):
        payloads = [
            {
                "question_id": "Q1",
                "latency_ms": 10.0,
                "results": [{"Sagsnummer": "123"}],
            }
        ]

        # Et tomt qrels-sæt er tilstrækkeligt til at teste rapportformen.
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "qrels.csv"
            path.write_text(
                "question_id,case_number,relevance,confidence,source,link\n",
                encoding="utf-8",
            )
            report = evaluate_payloads(
                payloads,
                qrels_path=path,
                pipeline="test",
                documents=2,
                top_k=20,
            )

        self.assertEqual(report["run"]["pipeline"], "test")
        self.assertEqual(report["run"]["mean_latency_ms"], 10.0)
        self.assertEqual(report["run"]["documents"], 2)

    def test_material_latency_regression_fails_policy(self):
        comparison = {
            "passed": True,
            "regressions": [],
            "latency": {"ratio": MAX_LATENCY_RATIO + 0.01},
        }

        result = apply_planner_policy(comparison)

        self.assertFalse(result["passed"])
        self.assertIn("mean_latency_ms", result["regressions"])


if __name__ == "__main__":
    unittest.main()

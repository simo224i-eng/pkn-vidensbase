import unittest

from ejnar.evaluation.run_query_planner_experiment import (
    MAX_LATENCY_RATIO,
    PLANNER_REGRESSION_THRESHOLDS,
    apply_planner_policy,
    evaluate_payloads,
    summarise_planner_effect,
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

    def test_effect_summary_exposes_noop_and_protected_result_changes(self):
        baseline = [
            {
                "question_id": "Q1",
                "detected_intent": "exploratory_research",
                "effective_query": "skimmel",
                "results": [{"Sagsnummer": "1"}],
            },
            {
                "question_id": "Q2",
                "detected_intent": "exact_content_search",
                "effective_query": '"ordret frase"',
                "results": [{"Sagsnummer": "2"}],
            },
        ]
        candidate = [
            {
                "question_id": "Q1",
                "detected_intent": "exploratory_research",
                "effective_query": "skimmel skimmelsvamp",
                "results": [{"Sagsnummer": "1"}],
            },
            {
                "question_id": "Q2",
                "detected_intent": "exact_content_search",
                "effective_query": '"ordret frase"',
                "results": [{"Sagsnummer": "3"}],
            },
        ]

        effect = summarise_planner_effect(baseline, candidate)

        self.assertEqual(effect["treated_queries"], 1)
        self.assertEqual(effect["changed_result_lists"], 1)
        self.assertEqual(effect["precision_guardrail_violations"], ["Q2"])

    def test_protected_query_rewrite_is_a_violation_even_when_results_match(self):
        baseline = [
            {
                "question_id": "Q1",
                "detected_intent": "exact_content_search",
                "effective_query": '"ordret frase"',
                "results": [{"Sagsnummer": "1"}],
            }
        ]
        candidate = [
            {
                "question_id": "Q1",
                "detected_intent": "exact_content_search",
                "effective_query": '"ordret frase" synonym',
                "results": [{"Sagsnummer": "1"}],
            }
        ]

        effect = summarise_planner_effect(baseline, candidate)

        self.assertEqual(effect["precision_guardrail_violations"], ["Q1"])

    def test_policy_can_reject_noop_experiment(self):
        comparison = {
            "passed": True,
            "regressions": [],
            "metrics": [
                {
                    "metric": "mean_ndcg_at_10",
                    "delta": 0.0,
                }
            ],
            "latency": {"ratio": 1.0},
        }

        result = apply_planner_policy(
            comparison,
            planner_effect={
                "treated_queries": 0,
                "changed_result_lists": 0,
                "precision_guardrail_violations": [],
            },
            min_treated_queries=1,
            min_result_list_changes=1,
            min_ndcg_gain=0.01,
        )

        self.assertFalse(result["passed"])
        self.assertIn("planner_treated_queries", result["regressions"])
        self.assertIn("planner_result_list_changes", result["regressions"])
        self.assertIn("mean_ndcg_at_10_gain", result["regressions"])


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.evaluation.qrels_metrics import Qrel
from ejnar.evaluation.short_query_benchmark import ShortQuerySpec
from ejnar.evaluation.short_query_metrics import (
    compare_short_query_reports,
    evaluate_short_queries,
    paired_bootstrap_lower_bound,
)


def _spec(question_id: str, topic_id: str, variant: str) -> ShortQuerySpec:
    return ShortQuerySpec(
        question_id=question_id,
        topic_id=topic_id,
        variant=variant,
        query="ventilation tagrum",
        intent="exploratory_research",
        category="common",
        cohort="treated",
        split="development",
        information_need="Find praksis om ventilation i tagrum.",
        inclusion_criteria="Relevant ventilation.",
        exclusion_criteria="Uvedkommende ventilation.",
        planner_policy="eligible",
    )


class ShortQueryMetricsTests(unittest.TestCase):
    def test_topic_report_averages_two_variants(self):
        specs = [_spec("Q1A", "T1", "A"), _spec("Q1B", "T1", "B")]
        qrels = [
            Qrel("Q1A", "1", 2, 1.0),
            Qrel("Q1B", "1", 2, 1.0),
        ]
        payloads = [
            {
                "question_id": "Q1A",
                "results": [{"Sagsnummer": "1"}],
            },
            {
                "question_id": "Q1B",
                "results": [{"Sagsnummer": "1"}],
            },
        ]

        report = evaluate_short_queries(specs, qrels, payloads)

        self.assertEqual(report["summary"]["treated_topics"], 1)
        self.assertEqual(report["summary"]["macro_topic_ndcg_at_10"], 1.0)
        self.assertEqual(report["coverage_violations_top_10"], [])

    def test_bootstrap_is_deterministic(self):
        baseline = {
            "topics": [
                {"topic_id": "T1", "ndcg_at_10": 0.5},
                {"topic_id": "T2", "ndcg_at_10": 0.7},
            ]
        }
        candidate = {
            "topics": [
                {"topic_id": "T1", "ndcg_at_10": 0.6},
                {"topic_id": "T2", "ndcg_at_10": 0.8},
            ]
        }

        first = paired_bootstrap_lower_bound(baseline, candidate, samples=100)
        second = paired_bootstrap_lower_bound(baseline, candidate, samples=100)

        self.assertEqual(first, second)
        self.assertAlmostEqual(first, 0.1)

    def test_gate_rejects_noop_even_when_secondary_metrics_are_stable(self):
        summary = {
            "macro_topic_ndcg_at_10": 0.8,
            "macro_topic_recall_at_20": 0.7,
            "macro_topic_mrr": 0.9,
            "macro_topic_judged_precision_at_5": 0.95,
        }
        report = {
            "summary": summary,
            "topics": [{"topic_id": "T1", "ndcg_at_10": 0.8}],
            "categories": {
                "common": {"ndcg_at_10": 0.8},
            },
            "coverage_violations_top_10": [],
        }

        comparison = compare_short_query_reports(
            report,
            report,
            planner_effect={
                "treated_queries": 0,
                "treated_by_split": {
                    "holdout": {
                        "planner_applications": 0,
                        "active_topics": 0,
                    }
                },
                "precision_guardrail_violations": [],
            },
            minimum_planner_applications=1,
            minimum_evaluation_split_applications=1,
            minimum_evaluation_split_topics=1,
        )

        self.assertFalse(comparison["passed"])
        self.assertIn("minimum_planner_applications", comparison["failures"])
        self.assertIn("macro_topic_ndcg_at_10", comparison["failures"])

    def test_category_gate_uses_holdout_not_development_average(self):
        baseline = {
            "summary": {},
            "splits": {
                "holdout": {
                    "macro_topic_ndcg_at_10": 0.5,
                    "macro_topic_recall_at_20": 0.8,
                    "macro_topic_mrr": 0.8,
                    "macro_topic_judged_precision_at_5": 0.8,
                }
            },
            "topics": [
                {
                    "topic_id": "H1",
                    "split": "holdout",
                    "category": "rare",
                    "ndcg_at_10": 0.8,
                },
                {
                    "topic_id": "H2",
                    "split": "holdout",
                    "category": "common",
                    "ndcg_at_10": 0.2,
                },
                {
                    "topic_id": "D1",
                    "split": "development",
                    "category": "rare",
                    "ndcg_at_10": 0.0,
                },
            ],
            "coverage_violations_top_10": [],
        }
        candidate = {
            **baseline,
            "splits": {
                "holdout": {
                    "macro_topic_ndcg_at_10": 0.525,
                    "macro_topic_recall_at_20": 0.8,
                    "macro_topic_mrr": 0.8,
                    "macro_topic_judged_precision_at_5": 0.8,
                }
            },
            "topics": [
                {
                    "topic_id": "H1",
                    "split": "holdout",
                    "category": "rare",
                    "ndcg_at_10": 0.75,
                },
                {
                    "topic_id": "H2",
                    "split": "holdout",
                    "category": "common",
                    "ndcg_at_10": 0.3,
                },
                {
                    "topic_id": "D1",
                    "split": "development",
                    "category": "rare",
                    "ndcg_at_10": 1.0,
                },
            ],
        }

        comparison = compare_short_query_reports(
            baseline,
            candidate,
            planner_effect={
                "treated_queries": 1,
                "treated_by_split": {
                    "holdout": {
                        "planner_applications": 1,
                        "active_topics": 1,
                    }
                },
                "precision_guardrail_violations": [],
                "fallback_violations": [],
            },
            minimum_planner_applications=1,
            minimum_evaluation_split_applications=1,
            minimum_evaluation_split_topics=1,
            minimum_bootstrap_lower_bound=-1.0,
        )

        self.assertIn("category_ndcg:rare", comparison["failures"])

    def test_gate_rejects_global_activation_without_holdout_activation(self):
        summary = {
            "macro_topic_ndcg_at_10": 0.8,
            "macro_topic_recall_at_20": 0.8,
            "macro_topic_mrr": 0.8,
            "macro_topic_judged_precision_at_5": 0.8,
        }
        report = {
            "summary": summary,
            "splits": {"holdout": summary},
            "topics": [
                {
                    "topic_id": "H1",
                    "split": "holdout",
                    "category": "common",
                    "ndcg_at_10": 0.8,
                }
            ],
            "coverage_violations_top_10": [],
        }

        comparison = compare_short_query_reports(
            report,
            report,
            planner_effect={
                "treated_queries": 12,
                "treated_by_split": {
                    "development": {
                        "planner_applications": 12,
                        "active_topics": 6,
                    },
                    "holdout": {
                        "planner_applications": 0,
                        "active_topics": 0,
                    },
                },
                "precision_guardrail_violations": [],
                "fallback_violations": [],
            },
            minimum_planner_applications=12,
            minimum_evaluation_split_applications=1,
            minimum_evaluation_split_topics=1,
            minimum_ndcg_gain=0.0,
            minimum_bootstrap_lower_bound=-1.0,
        )

        self.assertFalse(comparison["passed"])
        self.assertIn(
            "minimum_evaluation_split_applications",
            comparison["failures"],
        )
        self.assertIn(
            "minimum_evaluation_split_topics",
            comparison["failures"],
        )


if __name__ == "__main__":
    unittest.main()

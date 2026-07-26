import unittest

from ejnar.evaluation.run_short_query_experiment import _cohort_effect
from ejnar.evaluation.short_query_benchmark import ShortQuerySpec


def _spec(
    question_id: str,
    cohort: str,
    *,
    split: str | None = None,
    topic_id: str | None = None,
) -> ShortQuerySpec:
    return ShortQuerySpec(
        question_id=question_id,
        topic_id=topic_id or question_id,
        variant="single",
        query="test",
        intent="exploratory_research",
        category="test",
        cohort=cohort,
        split=split or ("guardrail" if cohort == "guardrail" else "development"),
        information_need="Test",
        inclusion_criteria="Test",
        exclusion_criteria="Test",
        planner_policy=(
            "eligible"
            if cohort == "treated"
            else ("forbidden" if cohort == "guardrail" else "fallback")
        ),
    )


class RunShortQueryExperimentTests(unittest.TestCase):
    def test_cohort_effect_counts_treatment_and_all_guardrail_changes(self):
        effect = {
            "cases": [
                {
                    "question_id": "T",
                    "effective_query_changed": True,
                    "result_list_changed": True,
                },
                {
                    "question_id": "G",
                    "effective_query_changed": False,
                    "result_list_changed": True,
                },
                {
                    "question_id": "F",
                    "effective_query_changed": True,
                    "result_list_changed": False,
                },
            ],
            "precision_guardrail_violations": [],
        }

        result = _cohort_effect(
            effect,
            [
                _spec("T", "treated"),
                _spec("G", "guardrail"),
                _spec("F", "fallback"),
            ],
        )

        self.assertEqual(result["treated_queries"], 1)
        self.assertEqual(result["treated_result_list_changes"], 1)
        self.assertEqual(result["precision_guardrail_violations"], ["G"])
        self.assertEqual(result["fallback_violations"], ["F"])
        self.assertEqual(
            result["treated_by_split"]["development"],
            {
                "queries": 1,
                "planner_applications": 1,
                "active_topics": 1,
                "changed_result_lists": 1,
            },
        )

    def test_cohort_effect_counts_active_topics_per_split(self):
        effect = {
            "cases": [
                {
                    "question_id": "H1A",
                    "effective_query_changed": True,
                    "result_list_changed": True,
                },
                {
                    "question_id": "H1B",
                    "effective_query_changed": True,
                    "result_list_changed": False,
                },
                {
                    "question_id": "H2A",
                    "effective_query_changed": False,
                    "result_list_changed": False,
                },
            ],
        }

        result = _cohort_effect(
            effect,
            [
                _spec("H1A", "treated", split="holdout", topic_id="H1"),
                _spec("H1B", "treated", split="holdout", topic_id="H1"),
                _spec("H2A", "treated", split="holdout", topic_id="H2"),
            ],
        )

        self.assertEqual(
            result["treated_by_split"]["holdout"],
            {
                "queries": 3,
                "planner_applications": 2,
                "active_topics": 1,
                "changed_result_lists": 1,
            },
        )


if __name__ == "__main__":
    unittest.main()

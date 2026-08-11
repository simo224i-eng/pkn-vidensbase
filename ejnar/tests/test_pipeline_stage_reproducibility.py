import unittest

from ejnar.evaluation.pipeline_stage_reproducibility import compare_stage_traces
from ejnar.evaluation.run_pipeline_stage_trace import STAGE_ORDER


def _row(question_id: str, overrides=None):
    stages = {stage: ["case:1", "case:2"] for stage in STAGE_ORDER}
    stages.update(overrides or {})
    return {
        question_id: {
            "question_id": question_id,
            "query": "test",
            "stages": stages,
        }
    }


class PipelineStageReproducibilityTests(unittest.TestCase):
    def test_reports_first_divergent_layer_only(self):
        runs = {
            "host1": _row("EJ-X"),
            "host2": _row(
                "EJ-X",
                {
                    "paragraph": ["case:2", "case:1"],
                    "metadata": ["case:2", "case:1"],
                    "query_feature": ["case:2", "case:1"],
                    "specific_decision": ["case:2", "case:1"],
                },
            ),
            "host3": _row("EJ-X"),
        }
        report = compare_stage_traces(runs)
        self.assertFalse(report["exact_reproducibility"])
        self.assertEqual(report["affected_questions"], 1)
        self.assertEqual(report["first_divergent_stage_counts"], {"paragraph": 1})
        self.assertEqual(report["details"][0]["first_divergent_stage"], "paragraph")
        self.assertTrue(report["details"][0]["stage_matches"]["deterministic_base"])
        self.assertTrue(report["details"][0]["stage_matches"]["intent"])
        self.assertFalse(report["details"][0]["stage_matches"]["paragraph"])

    def test_identical_traces_are_exact(self):
        row = _row("EJ-X")
        runs = {"host1": row, "host2": _row("EJ-X"), "host3": _row("EJ-X")}
        report = compare_stage_traces(runs)
        self.assertTrue(report["exact_reproducibility"])
        self.assertEqual(report["affected_questions"], 0)
        self.assertEqual(report["first_divergent_stage_counts"], {})


if __name__ == "__main__":
    unittest.main()

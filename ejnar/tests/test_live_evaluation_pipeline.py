import sys
import types
import unittest
from unittest.mock import patch

from ejnar.evaluation.run_live_retrieval import install_live_retrieval_pipeline


class LiveEvaluationPipelineTests(unittest.TestCase):
    def _modules(self, calls, with_shared=True):
        deterministic = types.ModuleType("deterministic_retrieval_runtime")
        retrieval = types.ModuleType("retrieval_runtime")
        query_planner = types.ModuleType("query_planner_runtime")
        paragraph = types.ModuleType("paragraph_runtime")
        metadata = types.ModuleType("metadata_runtime")
        query_feature = types.ModuleType("query_feature_runtime")
        specific = types.ModuleType("specific_decision_runtime")

        if with_shared:
            deterministic.install_deterministic_retrieval_runtime = lambda shared: calls.append(
                ("deterministic", shared)
            )
            retrieval.install_retrieval_runtime = lambda shared: calls.append(("intent", shared))
            query_planner.install_query_planner_runtime = lambda shared: calls.append(
                ("query_planner", shared)
            )
            paragraph.install_paragraph_runtime = lambda shared: calls.append(("paragraph", shared))
            metadata.install_metadata_runtime = lambda shared: calls.append(("metadata", shared))
            query_feature.install_query_feature_runtime = lambda shared: calls.append(
                ("query_feature", shared)
            )
            specific.install_specific_decision_runtime = lambda shared: calls.append(("specific", shared))
        else:
            deterministic.install_deterministic_retrieval_runtime = lambda shared: calls.append(
                "deterministic"
            )
            retrieval.install_retrieval_runtime = lambda shared: calls.append("intent")
            query_planner.install_query_planner_runtime = lambda shared: calls.append("query_planner")
            paragraph.install_paragraph_runtime = lambda shared: calls.append("paragraph")
            metadata.install_metadata_runtime = lambda shared: calls.append("metadata")
            query_feature.install_query_feature_runtime = lambda shared: calls.append("query_feature")
            specific.install_specific_decision_runtime = lambda shared: calls.append("specific")

        return {
            "deterministic_retrieval_runtime": deterministic,
            "retrieval_runtime": retrieval,
            "query_planner_runtime": query_planner,
            "paragraph_runtime": paragraph,
            "metadata_runtime": metadata,
            "query_feature_runtime": query_feature,
            "specific_decision_runtime": specific,
        }

    def test_installs_same_runtime_order_as_app(self):
        calls = []
        shared = object()
        with patch.dict(sys.modules, self._modules(calls, with_shared=True)):
            install_live_retrieval_pipeline(shared)

        self.assertEqual(
            [name for name, _ in calls],
            [
                "deterministic",
                "intent",
                "query_planner",
                "paragraph",
                "metadata",
                "query_feature",
                "specific",
            ],
        )
        self.assertTrue(all(value is shared for _, value in calls))

    def test_query_planner_can_be_excluded_for_control_benchmark(self):
        calls = []
        with patch.dict(sys.modules, self._modules(calls, with_shared=False)):
            install_live_retrieval_pipeline(
                object(),
                include_query_planner=False,
            )

        self.assertEqual(
            calls,
            ["deterministic", "intent", "paragraph", "metadata", "query_feature", "specific"],
        )


if __name__ == "__main__":
    unittest.main()

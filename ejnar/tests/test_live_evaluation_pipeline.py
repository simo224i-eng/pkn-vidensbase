import sys
import types
import unittest
from unittest.mock import patch

from ejnar.evaluation.run_live_retrieval import install_live_retrieval_pipeline


class LiveEvaluationPipelineTests(unittest.TestCase):
    def test_installs_same_runtime_order_as_app(self):
        calls = []
        retrieval = types.ModuleType("retrieval_runtime")
        paragraph = types.ModuleType("paragraph_runtime")
        metadata = types.ModuleType("metadata_runtime")
        specific = types.ModuleType("specific_decision_runtime")
        retrieval.install_retrieval_runtime = lambda shared: calls.append(("intent", shared))
        paragraph.install_paragraph_runtime = lambda shared: calls.append(("paragraph", shared))
        metadata.install_metadata_runtime = lambda shared: calls.append(("metadata", shared))
        specific.install_specific_decision_runtime = lambda shared: calls.append(("specific", shared))
        shared = object()

        with patch.dict(
            sys.modules,
            {
                "retrieval_runtime": retrieval,
                "paragraph_runtime": paragraph,
                "metadata_runtime": metadata,
                "specific_decision_runtime": specific,
            },
        ):
            install_live_retrieval_pipeline(shared)

        self.assertEqual(
            [name for name, _ in calls],
            ["intent", "paragraph", "metadata", "specific"],
        )
        self.assertTrue(all(value is shared for _, value in calls))


if __name__ == "__main__":
    unittest.main()

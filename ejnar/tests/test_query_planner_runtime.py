from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ejnar.query_planner_runtime import (
    get_query_planner_debug_events,
    install_query_planner_runtime,
)


class QueryPlannerRuntimeTests(unittest.TestCase):
    def setUp(self):
        get_query_planner_debug_events(clear=True)

    def test_known_concept_uses_deterministic_plan_without_llm_fallback(self):
        original = Mock(return_value="llm expansion")
        shared = SimpleNamespace(udvid_query=original)
        install_query_planner_runtime(shared)

        expanded = shared.udvid_query("opbulnet parket")

        self.assertIn("parketgulv", expanded)
        self.assertIn("opbulning", expanded)
        original.assert_not_called()

    def test_unknown_concept_preserves_existing_fallback(self):
        original = Mock(return_value="eksisterende expansion")
        shared = SimpleNamespace(udvid_query=original)
        install_query_planner_runtime(shared)

        self.assertEqual(
            shared.udvid_query("Praksis om korroderede specialbeslag"),
            "eksisterende expansion",
        )
        original.assert_called_once()

    def test_exact_search_delegates_to_intent_aware_runtime(self):
        query = 'Find kendelser hvor der står "opbulnet parket"'
        original = Mock(return_value=query)
        shared = SimpleNamespace(udvid_query=original)
        install_query_planner_runtime(shared)

        self.assertEqual(shared.udvid_query(query), query)
        original.assert_called_once_with(query)

    def test_installation_is_idempotent_and_events_are_inspectable(self):
        shared = SimpleNamespace(udvid_query=lambda query: query)
        self.assertTrue(install_query_planner_runtime(shared))
        self.assertFalse(install_query_planner_runtime(shared))

        shared.udvid_query("Praksis om råd i vinduer")
        events = get_query_planner_debug_events()
        self.assertEqual(events[-1]["stage"], "query_planner")
        self.assertIn("råd", events[-1]["plan"]["matched_concepts"])

    def test_runtime_is_fail_open(self):
        original = Mock(return_value="fallback")
        shared = SimpleNamespace(udvid_query=original)
        install_query_planner_runtime(shared)

        with patch("ejnar.query_planner_runtime.plan_query", side_effect=RuntimeError):
            self.assertEqual(shared.udvid_query("fugt"), "fallback")


if __name__ == "__main__":
    unittest.main()

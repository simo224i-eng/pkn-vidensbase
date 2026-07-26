import unittest

from ejnar.query_intent import QueryIntent
from ejnar.query_planner import MAX_ADDED_TERMS, plan_query


class QueryPlannerTests(unittest.TestCase):
    def test_known_concepts_add_only_bounded_terms(self):
        plan = plan_query("opbulnet parket")

        self.assertTrue(plan.applied)
        self.assertEqual(plan.intent, QueryIntent.EXPLORATORY_RESEARCH)
        self.assertTrue(plan.expanded_query.startswith(plan.original_query))
        self.assertIn("parketgulv", plan.added_terms)
        self.assertIn("trægulv", plan.added_terms)
        self.assertIn("opbulning", plan.added_terms)
        self.assertLessEqual(len(plan.added_terms), MAX_ADDED_TERMS)

    def test_exact_content_search_is_never_expanded(self):
        query = 'Find kendelser hvor der står "opbulnet parket"'
        plan = plan_query(query)

        self.assertFalse(plan.applied)
        self.assertEqual(plan.intent, QueryIntent.EXACT_CONTENT_SEARCH)
        self.assertEqual(plan.expanded_query, query)
        self.assertEqual(plan.skipped_reason, "precision_sensitive_intent")

    def test_specific_decision_search_is_never_expanded(self):
        query = "Find kendelse nr. 98097"
        plan = plan_query(query)

        self.assertFalse(plan.applied)
        self.assertEqual(plan.intent, QueryIntent.SPECIFIC_DECISION_SEARCH)
        self.assertEqual(plan.expanded_query, query)

    def test_unknown_damage_is_left_for_existing_fallback(self):
        query = "korroderede specialbeslag"
        plan = plan_query(query)

        self.assertFalse(plan.applied)
        self.assertEqual(plan.expanded_query, query)
        self.assertEqual(plan.skipped_reason, "no_known_concepts")

    def test_planner_does_not_invent_coverage_outcomes(self):
        plan = plan_query("Praksis om opbulnet parket")
        forbidden = {
            "dækket",
            "ikke dækket",
            "medhold",
            "afvisning",
            "dækningsberettiget",
        }

        self.assertTrue(plan.applied)
        self.assertFalse(forbidden & set(plan.added_terms))

    def test_informative_sentence_is_preserved_for_existing_fallback(self):
        query = "Hvilke momenter lægger nævnet typisk vægt på ved skimmel?"
        plan = plan_query(query)

        self.assertFalse(plan.applied)
        self.assertEqual(plan.expanded_query, query)
        self.assertEqual(plan.skipped_reason, "informative_query_preserved")

    def test_word_boundaries_prevent_substring_matches(self):
        plan = plan_query("Undersøg overtagelsesdagen og betagende arkitektur")

        self.assertFalse(plan.applied)
        self.assertNotIn("tag", plan.matched_concepts)

    def test_terms_are_deduplicated_and_query_is_deterministic(self):
        first = plan_query("Skimmel og skimmelsvamp ved fugt")
        second = plan_query("Skimmel og skimmelsvamp ved fugt")

        self.assertEqual(first, second)
        self.assertEqual(len(first.added_terms), len(set(first.added_terms)))

    def test_long_query_is_not_expanded(self):
        query = "fugt " * 250
        plan = plan_query(query)

        self.assertFalse(plan.applied)
        self.assertEqual(plan.skipped_reason, "query_too_long")


if __name__ == "__main__":
    unittest.main()

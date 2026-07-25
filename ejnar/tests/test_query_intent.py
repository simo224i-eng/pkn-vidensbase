import unittest

from ejnar.query_intent import QueryIntent, classify_query, extract_quoted_phrases


class QueryIntentTests(unittest.TestCase):
    def assertIntent(self, query: str, expected: QueryIntent):
        plan = classify_query(query)
        self.assertEqual(plan.intent, expected, msg=f"{query!r} blev {plan}")

    def test_quoted_phrase_is_exact_content(self):
        plan = classify_query(
            'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"'
        )
        self.assertEqual(plan.intent, QueryIntent.EXACT_CONTENT_SEARCH)
        self.assertFalse(plan.use_hyde)
        self.assertFalse(plan.expand_query)
        self.assertTrue(plan.prioritize_lexical)
        self.assertEqual(
            plan.exact_phrases,
            ("undertaget er ikke ført sammen over kip",),
        )

    def test_specific_facts_are_exact_content(self):
        self.assertIntent(
            "Find afgørelser, hvor der både var skimmel på undertaget og manglende ventilation ved kip",
            QueryIntent.EXACT_CONTENT_SEARCH,
        )

    def test_specific_decision_by_case_number(self):
        plan = classify_query("Find kendelse nr. 100123")
        self.assertEqual(plan.intent, QueryIntent.SPECIFIC_DECISION_SEARCH)
        self.assertIn("100123", plan.decision_identifiers)
        self.assertFalse(plan.use_hyde)

    def test_specific_decision_by_url(self):
        self.assertIntent(
            "Åbn https://ankeforsikring.dk/kendelser/100123",
            QueryIntent.SPECIFIC_DECISION_SEARCH,
        )

    def test_practice_overview(self):
        plan = classify_query(
            "Hvad er Ankenævnets praksis om manglende ventilation i tagrum?"
        )
        self.assertEqual(plan.intent, QueryIntent.PRACTICE_OVERVIEW)
        self.assertTrue(plan.use_hyde)
        self.assertTrue(plan.expand_query)

    def test_practice_moments(self):
        self.assertIntent(
            "Hvilke momenter lægger nævnet typisk vægt på ved skimmel?",
            QueryIntent.PRACTICE_OVERVIEW,
        )

    def test_concrete_case(self):
        self.assertIntent(
            "I min sag er gulvet fra 1974 lokalt hævet, men fortsat fast. Vil dette være dækket?",
            QueryIntent.CONCRETE_CASE_ASSESSMENT,
        )

    def test_long_concrete_fact_pattern(self):
        self.assertIntent(
            "Huset er fra 1980 og tagrenden har flere huller, som er lappet med tape. "
            "Der er ikke målt fugt eller konstateret følgeskade. Kan forsikringen afvise skaden?",
            QueryIntent.CONCRETE_CASE_ASSESSMENT,
        )

    def test_factual_lookup(self):
        self.assertIntent(
            "Hvilken frist gælder for at klage til Ankenævnet?",
            QueryIntent.FACTUAL_LOOKUP,
        )

    def test_exploratory(self):
        self.assertIntent(
            "Vis mig noget interessant om udviklingen inden for ejerskifteforsikring",
            QueryIntent.EXPLORATORY_RESEARCH,
        )

    def test_danish_quote_styles(self):
        self.assertEqual(
            extract_quoted_phrases("Find «manglende vedhæftning» og “lokal opbulning”"),
            ("manglende vedhæftning", "lokal opbulning"),
        )

    def test_empty_query_falls_back_safely(self):
        plan = classify_query("")
        self.assertEqual(plan.intent, QueryIntent.EXPLORATORY_RESEARCH)
        self.assertGreater(plan.top_retrieve, plan.top_final)


if __name__ == "__main__":
    unittest.main()

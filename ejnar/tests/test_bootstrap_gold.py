import unittest

from ejnar.evaluation.bootstrap_gold import bootstrap_judgments, judge_result


class BootstrapGoldTests(unittest.TestCase):
    def test_exact_requested_case_is_highly_relevant(self):
        judgment = judge_result(
            {"question_id": "Q1", "query": "Find kendelse nr. 100123"},
            {"rank": 4, "Sagsnummer": "100123", "Titel": "Kendelse", "Tekst": ""},
        )
        self.assertEqual(judgment.relevance, 2)
        self.assertIn("requested_case_exact", judgment.signals)

    def test_wrong_case_for_specific_lookup_is_irrelevant(self):
        judgment = judge_result(
            {"question_id": "Q1", "query": "Find kendelse nr. 100123"},
            {"rank": 1, "Sagsnummer": "74011", "Titel": "Anden kendelse", "Tekst": ""},
        )
        self.assertEqual(judgment.relevance, 0)

    def test_exact_quote_is_highly_relevant(self):
        judgment = judge_result(
            {"question_id": "Q2", "query": 'Find hvor der står "undertaget er ikke ført sammen over kip"'},
            {"rank": 8, "Sagsnummer": "89310", "Titel": "Undertag", "Tekst": "Undertaget er ikke ført sammen over kip."},
        )
        self.assertEqual(judgment.relevance, 2)
        self.assertIn("exact_phrase", judgment.signals)

    def test_topic_overlap_can_be_relevant(self):
        judgment = judge_result(
            {"question_id": "Q3", "query": "Hvornår får klager medhold i sager om råd i vinduer?", "expected_terms": "råd|vinduer|medhold"},
            {"rank": 2, "Sagsnummer": "72700", "Titel": "Råd i vinduer", "Tekst": "Klager fik medhold for rådskader i vinduer."},
        )
        self.assertGreaterEqual(judgment.relevance, 1)

    def test_bootstrap_preserves_question_mapping(self):
        judgments = bootstrap_judgments(
            [{"question_id": "Q1", "query": "tag"}],
            {"Q1": [{"rank": 1, "Sagsnummer": "1", "Titel": "Tag", "Tekst": "tag"}]},
        )
        self.assertEqual(len(judgments), 1)
        self.assertEqual(judgments[0].question_id, "Q1")


if __name__ == "__main__":
    unittest.main()

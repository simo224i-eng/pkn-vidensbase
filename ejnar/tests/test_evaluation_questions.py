import csv
from collections import Counter
from pathlib import Path
import unittest


QUESTIONS_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "eval_questions.csv"
VALID_INTENTS = {
    "exact_content_search",
    "specific_decision_search",
    "practice_overview",
    "concrete_case_assessment",
    "factual_lookup",
    "exploratory_research",
}


class EvaluationQuestionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with QUESTIONS_PATH.open(newline="", encoding="utf-8-sig") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_has_at_least_thirty_unique_questions(self):
        ids = [row["question_id"].strip() for row in self.rows]
        self.assertGreaterEqual(len(ids), 30)
        self.assertEqual(len(ids), len(set(ids)))

    def test_all_rows_have_valid_intent_and_query(self):
        for row in self.rows:
            self.assertTrue(row["query"].strip(), row.get("question_id"))
            self.assertIn(row["intent"].strip(), VALID_INTENTS)

    def test_distribution_covers_required_workflows(self):
        counts = Counter(row["intent"].strip() for row in self.rows)
        self.assertGreaterEqual(counts["exact_content_search"], 10)
        self.assertGreaterEqual(counts["specific_decision_search"], 5)
        self.assertGreaterEqual(counts["practice_overview"], 5)
        self.assertGreaterEqual(counts["concrete_case_assessment"], 5)
        self.assertGreaterEqual(
            counts["factual_lookup"] + counts["exploratory_research"],
            5,
        )

    def test_specific_decision_searches_have_expected_ids(self):
        for row in self.rows:
            if row["intent"].strip() == "specific_decision_search":
                expected = row["expected_decision_ids"].strip()
                self.assertTrue(expected, row["question_id"])
                self.assertNotEqual(expected, "100123")

    def test_exact_questions_have_phrase_or_terms(self):
        for row in self.rows:
            if row["intent"].strip() == "exact_content_search":
                self.assertTrue(
                    row["expected_terms"].strip() or row["expected_phrase"].strip(),
                    row["question_id"],
                )


if __name__ == "__main__":
    unittest.main()

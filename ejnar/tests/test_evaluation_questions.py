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
FROZEN_V1_QUERIES = {
    "EJ-001": 'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"',
    "EJ-002": "Find afgørelser hvor der både var skimmel på undertaget og manglende ventilation ved kip",
    "EJ-003": "Find kendelse nr. 100123",
    "EJ-004": "Hvad er Ankenævnets praksis om manglende ventilation i tagrum?",
    "EJ-005": "Hvilke momenter lægger nævnet typisk vægt på ved skimmel?",
    "EJ-006": "I min sag er et gulv fra 1974 lokalt hævet men fortsat fast. Vil forholdet være dækket?",
    "EJ-007": "Hvilken frist gælder for at klage til Ankenævnet?",
    "EJ-008": "Find afgørelser der omtaler aluminiumtape på tagrender",
    "EJ-009": "Hvornår får klager medhold i sager om råd i vinduer?",
    "EJ-010": "Undersøg relationen mellem restlevetid og sædvanligt slid",
}


class EvaluationQuestionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with QUESTIONS_PATH.open(newline="", encoding="utf-8-sig") as handle:
            cls.rows = list(csv.DictReader(handle))
        cls.by_id = {row["question_id"].strip(): row for row in cls.rows}

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
        self.assertGreaterEqual(counts["specific_decision_search"], 6)
        self.assertGreaterEqual(counts["practice_overview"], 5)
        self.assertGreaterEqual(counts["concrete_case_assessment"], 5)
        self.assertGreaterEqual(
            counts["factual_lookup"] + counts["exploratory_research"],
            5,
        )

    def test_frozen_v1_question_ids_cannot_change_meaning(self):
        for question_id, query in FROZEN_V1_QUERIES.items():
            self.assertIn(question_id, self.by_id)
            self.assertEqual(self.by_id[question_id]["query"].strip(), query)

    def test_new_specific_decision_searches_have_real_expected_ids(self):
        specific_rows = [
            row
            for row in self.rows
            if row["intent"].strip() == "specific_decision_search"
            and row["question_id"].strip() != "EJ-003"
        ]
        self.assertGreaterEqual(len(specific_rows), 5)
        for row in specific_rows:
            expected = row["expected_decision_ids"].strip()
            self.assertTrue(expected, row["question_id"])
            self.assertNotEqual(expected, "100123")

    def test_legacy_placeholder_is_explicitly_quarantined(self):
        legacy = self.by_id["EJ-003"]
        self.assertEqual(legacy["query"].strip(), "Find kendelse nr. 100123")
        self.assertIn("Legacy benchmark", legacy["notes"])

    def test_exact_questions_have_phrase_or_terms(self):
        for row in self.rows:
            if row["intent"].strip() == "exact_content_search":
                self.assertTrue(
                    row["expected_terms"].strip() or row["expected_phrase"].strip(),
                    row["question_id"],
                )


if __name__ == "__main__":
    unittest.main()

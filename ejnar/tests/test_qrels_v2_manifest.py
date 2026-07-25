import csv
from collections import Counter
import hashlib
import json
from pathlib import Path
import unittest


EJNAR_DIR = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = EJNAR_DIR / "evaluation" / "eval_questions.csv"
QRELS_PATH = EJNAR_DIR / "evaluation" / "bootstrap_qrels_v2.csv"
META_PATH = EJNAR_DIR / "evaluation" / "bootstrap_qrels_v2.meta.json"


class QrelsV2ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with QUESTIONS_PATH.open(newline="", encoding="utf-8-sig") as handle:
            cls.questions = list(csv.DictReader(handle))
        with QRELS_PATH.open(newline="", encoding="utf-8-sig") as handle:
            cls.qrels = list(csv.DictReader(handle))
        cls.meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    def test_manifest_hashes_lock_all_current_queries(self):
        hashes = self.meta["query_hashes"]
        self.assertEqual(len(hashes), len(self.questions))
        for row in self.questions:
            question_id = row["question_id"].strip()
            digest = hashlib.sha256(row["query"].strip().encode("utf-8")).hexdigest()
            self.assertEqual(hashes.get(question_id), digest, question_id)

    def test_stored_judgment_count_and_distribution_match(self):
        self.assertEqual(len(self.qrels), self.meta["stored_judgments"])
        counts = Counter(int(row["relevance"]) for row in self.qrels)
        self.assertEqual(counts, Counter({0: 142, 1: 275, 2: 12}))
        self.assertEqual(
            self.meta["judgments"],
            self.meta["stored_judgments"] + self.meta["excluded_uncertain"],
        )

    def test_uncertain_labels_are_not_stored_as_ground_truth(self):
        self.assertNotIn(-1, {int(row["relevance"]) for row in self.qrels})
        self.assertEqual(self.meta["excluded_uncertain"], 191)

    def test_qrels_reference_known_questions(self):
        known = {row["question_id"].strip() for row in self.questions}
        judged = {row["question_id"].strip() for row in self.qrels}
        self.assertTrue(judged <= known)
        self.assertEqual(len(judged), 30)
        self.assertNotIn("EJ-006", judged)

    def test_confidence_and_relevance_values_are_valid(self):
        for row in self.qrels:
            self.assertIn(int(row["relevance"]), {0, 1, 2})
            self.assertGreaterEqual(float(row["confidence"]), 0.0)
            self.assertLessEqual(float(row["confidence"]), 1.0)


if __name__ == "__main__":
    unittest.main()

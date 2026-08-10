import csv
import json
from pathlib import Path
import tempfile
import unittest

from ejnar.evaluation.grounding_review import (
    REVIEW_LABELS,
    freeze_human_labels,
    prepare_review_rows,
    read_review_csv,
    review_manifest,
    source_digest,
    validate_review,
    write_review_csv,
)


class GroundingReviewTests(unittest.TestCase):
    def _source(self):
        return [
            {
                "audit_id": "ga-b",
                "question_id": "EJ-2",
                "query": "hvornår er nedbrydning skade",
                "case_number": "222",
                "title": "Bjælke",
                "date": "2025-02-01",
                "link": "https://example.test/222",
                "query_excerpt_section": "Sagens oplysninger",
                "query_excerpt": "Bjælkens bæreevne var væsentligt nedsat.",
                "decision_core_section": "Nævnets bemærkninger",
                "decision_core": "Forholdet var anmærket i tilstandsrapporten.",
                "review_label": "",
                "review_notes": "",
            },
            {
                "audit_id": "ga-a",
                "question_id": "EJ-1",
                "query": "fugt ved overtagelsen",
                "case_number": "111",
                "title": "Fugt",
                "date": "2024-01-01",
                "link": "https://example.test/111",
                "query_excerpt_section": "Nævnets bemærkninger",
                "query_excerpt": "Nævnet omtaler fugtforholdet.",
                "decision_core_section": "Nævnets bemærkninger",
                "decision_core": "Nævnet finder, at forholdet var til stede ved overtagelsen.",
                "review_label": "",
                "review_notes": "",
            },
        ]

    def test_prepare_is_deterministic_and_blind(self):
        source = self._source()
        first = prepare_review_rows(source)
        second = prepare_review_rows(list(reversed(source)))
        self.assertEqual(first, second)
        self.assertEqual([row["review_order"] for row in first], ["1", "2"])
        for row in first:
            self.assertNotIn("retrieval_rank", row)
            self.assertNotIn("priority", row)
            self.assertNotIn("contrast_score", row)
            self.assertEqual(row["review_label"], "")

    def test_prepare_rejects_diagnostic_leakage(self):
        source = self._source()
        source[0]["retrieval_rank"] = 1
        with self.assertRaises(ValueError):
            prepare_review_rows(source)

    def test_manifest_locks_source_hash_and_labels(self):
        manifest = review_manifest(self._source())
        self.assertEqual(manifest["rows"], 2)
        self.assertEqual(manifest["source_sha256"], source_digest(self._source()))
        self.assertEqual(set(manifest["labels"]), set(REVIEW_LABELS))
        self.assertIn("retrieval-rank", manifest["blinding"])

    def test_validation_requires_label_and_reviewer(self):
        rows = prepare_review_rows(self._source())
        report = validate_review(rows, source_rows=self._source(), require_complete=True)
        self.assertFalse(report["valid"])
        self.assertTrue(any("missing review_label" in error for error in report["errors"]))

        rows[0]["review_label"] = "direct_practice"
        rows[0]["reviewer"] = "Jurist A"
        rows[1]["review_label"] = "indirect_support"
        rows[1]["reviewer"] = "Jurist A"
        rows[1]["review_notes"] = "Afgjort på tilstandsrapporten."
        report = validate_review(rows, source_rows=self._source())
        self.assertTrue(report["valid"])
        self.assertEqual(report["label_counts"]["direct_practice"], 1)
        self.assertEqual(report["label_counts"]["indirect_support"], 1)
        self.assertEqual(report["reviewers"], ["Jurist A"])

    def test_uncertain_requires_notes(self):
        rows = prepare_review_rows(self._source())
        for row in rows:
            row["review_label"] = "not_useful"
            row["reviewer"] = "Jurist A"
        rows[0]["review_label"] = "uncertain"
        report = validate_review(rows, source_rows=self._source())
        self.assertFalse(report["valid"])
        self.assertTrue(any("uncertain requires review_notes" in error for error in report["errors"]))

    def test_freeze_maps_only_reviewed_labels_to_relevance(self):
        rows = prepare_review_rows(self._source())
        labels = ["direct_practice", "uncertain"]
        for row, label in zip(rows, labels):
            row["review_label"] = label
            row["reviewer"] = "Jurist A"
            row["review_notes"] = "Kræver originalkontrol." if label == "uncertain" else ""

        frozen, manifest = freeze_human_labels(rows, self._source())
        by_label = {row["label"]: row for row in frozen}
        self.assertEqual(by_label["direct_practice"]["benchmark_relevance"], 2)
        self.assertIsNone(by_label["uncertain"]["benchmark_relevance"])
        self.assertEqual(manifest["benchmarkable_rows"], 1)
        self.assertEqual(manifest["uncertain_rows"], 1)
        self.assertEqual(manifest["reviewers"], ["Jurist A"])

    def test_csv_roundtrip_keeps_review_fields(self):
        rows = prepare_review_rows(self._source())
        rows[0]["review_label"] = "not_useful"
        rows[0]["reviewer"] = "Jurist A"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "review.csv"
            write_review_csv(path, rows)
            loaded = read_review_csv(path)
        self.assertEqual(loaded[0]["audit_id"], rows[0]["audit_id"])
        self.assertEqual(loaded[0]["review_label"], "not_useful")
        self.assertEqual(loaded[0]["reviewer"], "Jurist A")


if __name__ == "__main__":
    unittest.main()

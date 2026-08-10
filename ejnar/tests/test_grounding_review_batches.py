from pathlib import Path
import tempfile
import unittest

from ejnar.evaluation.grounding_review import read_review_csv, write_review_csv
from ejnar.evaluation.grounding_review_batches import (
    combine_batches,
    split_batches,
    write_batches,
)


class GroundingReviewBatchTests(unittest.TestCase):
    def _rows(self, count=7):
        rows = []
        for index in range(1, count + 1):
            rows.append({
                "review_order": str(index),
                "audit_id": f"ga-{index}",
                "query": f"spørgsmål {index}",
                "case_number": str(100 + index),
                "title": f"Sag {index}",
                "date": "2026-01-01",
                "link": f"https://example.test/{index}",
                "query_excerpt_section": "Sagens oplysninger",
                "query_excerpt": f"Relevant uddrag {index}",
                "decision_core_section": "Nævnets bemærkninger",
                "decision_core": f"Afgørelseskerne {index}",
                "review_label": "",
                "reviewer": "",
                "review_notes": "",
            })
        return rows

    def test_split_preserves_master_order_and_full_coverage(self):
        batches = split_batches(self._rows(), batch_size=3)
        self.assertEqual([len(batch) for batch in batches], [3, 3, 1])
        self.assertEqual(
            [row["audit_id"] for batch in batches for row in batch],
            [f"ga-{i}" for i in range(1, 8)],
        )

    def test_split_rejects_duplicate_audit_ids(self):
        rows = self._rows(2)
        rows[1]["audit_id"] = rows[0]["audit_id"]
        with self.assertRaises(ValueError):
            split_batches(rows, batch_size=2)

    def test_written_batches_roundtrip_without_diagnostic_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            entries = write_batches(Path(tmp), split_batches(self._rows(4), batch_size=2))
            self.assertEqual(len(entries), 2)
            loaded = read_review_csv(Path(tmp) / entries[0]["file"])
        self.assertEqual(len(loaded), 2)
        self.assertNotIn("retrieval_rank", loaded[0])
        self.assertNotIn("priority", loaded[0])
        self.assertTrue(entries[0]["file_sha256"])

    def test_combine_preserves_completed_labels_and_master_order(self):
        master = self._rows(4)
        reviewed = [dict(row) for row in reversed(master)]
        for row in reviewed:
            row["review_label"] = "direct_practice"
            row["reviewer"] = "Jurist A"
        combined, report = combine_batches(master, reviewed)
        self.assertTrue(report["valid"])
        self.assertEqual([row["audit_id"] for row in combined], [f"ga-{i}" for i in range(1, 5)])
        self.assertTrue(all(row["review_label"] == "direct_practice" for row in combined))

    def test_combine_rejects_duplicate_across_batches(self):
        master = self._rows(2)
        reviewed = [dict(master[0]), dict(master[0]), dict(master[1])]
        combined, report = combine_batches(master, reviewed)
        self.assertFalse(report["valid"])
        self.assertEqual(combined, [])
        self.assertEqual(report["duplicate_rows"], 1)

    def test_combine_rejects_missing_master_case(self):
        master = self._rows(3)
        combined, report = combine_batches(master, [dict(master[0]), dict(master[1])])
        self.assertFalse(report["valid"])
        self.assertEqual(combined, [])
        self.assertEqual(report["missing_rows"], 1)

    def test_combine_rejects_edited_evidence_but_allows_review_fields(self):
        master = self._rows(2)
        reviewed = [dict(row) for row in master]
        reviewed[0]["review_label"] = "indirect_support"
        reviewed[0]["reviewer"] = "Jurist A"
        reviewed[0]["review_notes"] = "Afgjort på andet grundlag."
        reviewed[1]["decision_core"] = "Manipuleret afgørelseskerne"
        combined, report = combine_batches(master, reviewed)
        self.assertFalse(report["valid"])
        self.assertEqual(combined, [])
        self.assertEqual(report["edited_evidence_rows"], 1)

    def test_csv_batches_can_be_completed_and_combined(self):
        master = self._rows(5)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            master_path = root / "master.csv"
            batch_dir = root / "batches"
            write_review_csv(master_path, master)
            entries = write_batches(batch_dir, split_batches(master, batch_size=2))
            completed = []
            for entry in entries:
                rows = read_review_csv(batch_dir / entry["file"])
                for row in rows:
                    row["review_label"] = "not_useful"
                    row["reviewer"] = "Jurist A"
                completed.extend(rows)
            combined, report = combine_batches(read_review_csv(master_path), completed)
        self.assertTrue(report["valid"])
        self.assertEqual(len(combined), 5)


if __name__ == "__main__":
    unittest.main()

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ejnar.evaluation.grounding_audit_reproducibility import (
    build_fingerprint,
    compare_fingerprints,
)
from ejnar.evaluation.grounding_review import (
    prepare_review_rows,
    review_manifest,
    write_jsonl,
    write_review_csv,
)
from ejnar.evaluation.grounding_review_batches import (
    batch_manifest,
    split_batches,
    write_batches,
)


def _source_rows():
    return [
        {
            "audit_id": "ga-001",
            "question_id": "EJ-001",
            "query": "Hvornår er en bjælke en skade?",
            "case_number": "10001",
            "title": "Bjælke",
            "date": "2025-01-01",
            "link": "https://example.test/1",
            "query_excerpt_section": "Sagkyndig",
            "query_excerpt": "Bæreevnen er væsentligt nedsat.",
            "decision_core_section": "Nævnets vurdering",
            "decision_core": "Forholdet var anmærket i tilstandsrapporten.",
            "review_label": "",
            "review_notes": "",
        },
        {
            "audit_id": "ga-002",
            "question_id": "EJ-002",
            "query": "Hvornår dækkes fugt?",
            "case_number": "10002",
            "title": "Fugt",
            "date": "2025-02-01",
            "link": "https://example.test/2",
            "query_excerpt_section": "Klagen",
            "query_excerpt": "Der blev konstateret fugt.",
            "decision_core_section": "Nævnets vurdering",
            "decision_core": "Det er ikke godtgjort, at forholdet var til stede ved overtagelsen.",
            "review_label": "",
            "review_notes": "",
        },
    ]


def _write_package(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    source = _source_rows()
    blind = root / "blind-pool.jsonl"
    review_csv = root / "grounding-review.csv"
    write_jsonl(blind, source)
    prepared = prepare_review_rows(source)
    write_review_csv(review_csv, prepared)
    (root / "review-manifest.json").write_text(
        json.dumps(review_manifest(source), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    batches = split_batches(prepared, batch_size=1)
    entries = write_batches(root / "review-batches", batches)
    (root / "review-batches-manifest.json").write_text(
        json.dumps(
            batch_manifest(review_csv, prepared, entries, batch_size=1),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "REVIEW_PROTOCOL.md").write_text("# Neutral review protocol\n", encoding="utf-8")


class GroundingAuditReproducibilityTests(unittest.TestCase):
    def test_independent_identical_packages_have_same_fingerprint(self):
        with TemporaryDirectory() as tmp:
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            _write_package(first)
            _write_package(second)
            fp1 = build_fingerprint(first)
            fp2 = build_fingerprint(second)
            self.assertEqual(fp1, fp2)
            report = compare_fingerprints({"host1": fp1, "host2": fp2})
            self.assertTrue(report["exact_reproducibility"])
            self.assertEqual(report["differing_fields"], [])

    def test_fingerprint_rejects_batch_file_that_no_longer_matches_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "package"
            _write_package(root)
            batch = root / "review-batches" / "grounding-review-batch-01.csv"
            batch.write_text(batch.read_text(encoding="utf-8-sig") + "\n", encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError, "batch file hashes"):
                build_fingerprint(root)

    def test_compare_reports_exact_differing_component(self):
        first = {"schema_version": 1, "rows": 68, "blind_source_sha256": "aaa"}
        second = {"schema_version": 1, "rows": 69, "blind_source_sha256": "bbb"}
        report = compare_fingerprints({"host1": first, "host2": second})
        self.assertFalse(report["exact_reproducibility"])
        self.assertEqual(
            report["differing_fields"],
            ["blind_source_sha256", "rows"],
        )

    def test_compare_requires_multiple_runs(self):
        with self.assertRaisesRegex(ValueError, "at least two"):
            compare_fingerprints({"only": {"rows": 1}})


if __name__ == "__main__":
    unittest.main()

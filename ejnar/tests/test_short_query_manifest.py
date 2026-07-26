from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import unittest

from ejnar.evaluation.short_query_benchmark import (
    load_specs,
    specs_sha256,
    validate_specs,
)
from ejnar.query_planner import plan_query


EJNAR_DIR = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = EJNAR_DIR / "evaluation" / "short_query_questions_v1.csv"
META_PATH = EJNAR_DIR / "evaluation" / "short_query_questions_v1.meta.json"


class ShortQueryManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.specs = load_specs(QUESTIONS_PATH)
        cls.meta = json.loads(META_PATH.read_text(encoding="utf-8"))

    def test_dataset_is_frozen_before_retrieval_judgment(self):
        self.assertEqual(
            specs_sha256(self.specs),
            self.meta["hashes"]["canonical_specs_sha256"],
        )
        self.assertEqual(
            hashlib.sha256(QUESTIONS_PATH.read_bytes()).hexdigest(),
            self.meta["hashes"]["csv_bytes_sha256"],
        )
        self.assertEqual(self.meta["quality_status"], "unjudged_pool")

    def test_declared_counts_match_data(self):
        summary = validate_specs(
            self.specs,
            minimum_treated_cohort_size=60,
        )
        counts = self.meta["counts"]
        self.assertEqual(summary["questions"], counts["questions"])
        self.assertEqual(summary["topics"], counts["topics"])
        self.assertEqual(summary["treated_topics"], counts["treated_topics"])
        self.assertEqual(summary["cohorts"]["treated"], counts["treated_queries"])
        self.assertEqual(summary["cohorts"]["fallback"], counts["fallback_queries"])
        self.assertEqual(summary["cohorts"]["guardrail"], counts["guardrail_queries"])

    def test_topic_variants_do_not_cross_splits_or_categories(self):
        grouped = defaultdict(list)
        for spec in self.specs:
            if spec.cohort == "treated":
                grouped[spec.topic_id].append(spec)

        for topic_id, variants in grouped.items():
            self.assertEqual({item.variant for item in variants}, {"A", "B"}, topic_id)
            self.assertEqual(len({item.split for item in variants}), 1, topic_id)
            self.assertEqual(len({item.category for item in variants}), 1, topic_id)
            self.assertEqual(len({item.information_need for item in variants}), 1, topic_id)
            self.assertEqual(len({item.inclusion_criteria for item in variants}), 1, topic_id)
            self.assertEqual(len({item.exclusion_criteria for item in variants}), 1, topic_id)

    def test_dev_validation_holdout_distribution_is_frozen(self):
        distribution = Counter(
            item.split for item in self.specs if item.cohort == "treated"
        )
        self.assertEqual(
            dict(distribution),
            self.meta["treated_splits"],
        )
        topic_distribution = Counter(
            next(
                item.split
                for item in self.specs
                if item.topic_id == topic_id
            )
            for topic_id in {
                item.topic_id
                for item in self.specs
                if item.cohort == "treated"
            }
        )
        self.assertEqual(
            dict(topic_distribution),
            self.meta["treated_topic_splits"],
        )

    def test_planner_activation_is_frozen_overall_and_by_split(self):
        active = [
            item
            for item in self.specs
            if item.cohort == "treated" and plan_query(item.query).applied
        ]
        expected = self.meta["planner_activation"]

        self.assertEqual(len(active), expected["queries"])
        self.assertEqual(
            len({item.topic_id for item in active}),
            expected["topics"],
        )
        for split, split_expected in expected["by_split"].items():
            split_rows = [item for item in active if item.split == split]
            self.assertEqual(len(split_rows), split_expected["queries"])
            self.assertEqual(
                len({item.topic_id for item in split_rows}),
                split_expected["topics"],
            )

    def test_scope_forbids_claim_decisions(self):
        self.assertIn(
            "never decide a concrete insurance claim",
            self.meta["policy"]["scope"],
        )


if __name__ == "__main__":
    unittest.main()

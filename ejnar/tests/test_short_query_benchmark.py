import tempfile
from pathlib import Path
import unittest

from ejnar.evaluation.short_query_benchmark import (
    ShortQuerySpec,
    build_blind_pool,
    query_hashes,
    specs_sha256,
    validate_specs,
)


def _spec(
    question_id: str,
    topic_id: str,
    variant: str,
    query: str,
    *,
    cohort: str = "treated",
    planner_policy: str = "eligible",
) -> ShortQuerySpec:
    return ShortQuerySpec(
        question_id=question_id,
        topic_id=topic_id,
        variant=variant,
        query=query,
        intent="exploratory_research",
        category="common",
        cohort=cohort,
        split="development",
        information_need="Find praksis om ventilation i tagrum.",
        inclusion_criteria="Kendelsen behandler ventilation i tagrum.",
        exclusion_criteria="Rent uvedkommende omtale.",
        planner_policy=planner_policy,
    )


class ShortQueryBenchmarkTests(unittest.TestCase):
    def test_valid_treated_topic_requires_two_runtime_active_variants(self):
        specs = [
            _spec("SQ-001A", "SQ-001", "A", "ventilation tagrum"),
            _spec("SQ-001B", "SQ-001", "B", "tagrum udluftning"),
        ]

        summary = validate_specs(specs, minimum_treated_cohort_size=2)

        self.assertEqual(summary["treated_topics"], 1)
        self.assertEqual(summary["planner_applications"], 2)

    def test_treated_queries_may_be_oov_without_changing_frozen_dataset(self):
        specs = [
            _spec("SQ-001A", "SQ-001", "A", "sjælden konstruktion"),
            _spec("SQ-001B", "SQ-001", "B", "usædvanligt beslag"),
        ]

        summary = validate_specs(specs, minimum_treated_cohort_size=2)

        self.assertEqual(summary["planner_applications"], 0)

    def test_fallback_query_must_remain_a_runtime_noop(self):
        specs = [
            _spec(
                "SQ-F01",
                "SQ-F01",
                "single",
                "ventilation tagrum",
                cohort="fallback",
                planner_policy="fallback",
            ),
        ]

        with self.assertRaisesRegex(ValueError, "kontrol-query aktiverede"):
            validate_specs(specs, minimum_treated_cohort_size=0)

    def test_declared_intent_must_match_runtime(self):
        spec = _spec(
            "SQ-001A",
            "SQ-001",
            "A",
            "ventilation tagrum",
        )
        mismatched = ShortQuerySpec(
            **{
                **spec.__dict__,
                "intent": "specific_decision_search",
            }
        )

        with self.assertRaisesRegex(ValueError, "declared intent"):
            validate_specs(
                [mismatched],
                minimum_treated_cohort_size=0,
            )

    def test_hash_is_stable_and_query_hashes_are_per_case(self):
        specs = [
            _spec("SQ-001A", "SQ-001", "A", "ventilation tagrum"),
            _spec("SQ-001B", "SQ-001", "B", "tagrum udluftning"),
        ]

        self.assertEqual(specs_sha256(specs), specs_sha256(list(reversed(specs))))
        self.assertEqual(set(query_hashes(specs)), {"SQ-001A", "SQ-001B"})

    def test_blind_pool_deduplicates_and_hides_system_and_rank(self):
        specs = [
            _spec("SQ-001A", "SQ-001", "A", "ventilation tagrum"),
            _spec("SQ-001B", "SQ-001", "B", "tagrum udluftning"),
        ]
        baseline = [
            {
                "question_id": "SQ-001A",
                "results": [
                    {"Sagsnummer": "1", "Titel": "A", "Tekst": "tekst"}
                ],
            }
        ]
        candidate = [
            {
                "question_id": "SQ-001A",
                "results": [
                    {"Sagsnummer": "1", "Titel": "A", "Tekst": "tekst"},
                    {"Sagsnummer": "2", "Titel": "B", "Tekst": "andet"},
                ],
            }
        ]

        blind, provenance = build_blind_pool(
            specs,
            {"baseline": baseline, "candidate": candidate},
        )

        self.assertEqual(len(blind), 2)
        self.assertTrue(all("system" not in row and "rank" not in row for row in blind))
        hidden_fields = {"topic_id", "variant", "category", "cohort", "split"}
        self.assertTrue(
            all(hidden_fields.isdisjoint(row) for row in blind)
        )
        sources = {
            source["system"]
            for row in provenance
            for source in row["sources"]
        }
        self.assertEqual(sources, {"baseline", "candidate"})


if __name__ == "__main__":
    unittest.main()

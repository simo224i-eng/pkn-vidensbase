import tempfile
from pathlib import Path
import unittest

from ejnar.evaluation.decision_grounding_metrics import (
    DEFAULT_CASES,
    evaluate,
    evaluate_case,
    load_cases,
    write_report,
)


class DecisionGroundingMetricsTests(unittest.TestCase):
    def test_frozen_v1_has_unique_cases_and_broad_failure_modes(self):
        cases = load_cases(DEFAULT_CASES)
        ids = [case["case_id"] for case in cases]
        categories = {case["category"] for case in cases}

        self.assertEqual(len(cases), 18)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids, [f"DG-{number:03d}" for number in range(1, 19)])
        self.assertTrue({
            "condition_report",
            "known_condition",
            "takeover_proof",
            "amount_threshold",
            "limitation",
            "exclusion",
            "party_attribution",
            "expert_attribution",
            "direct_merits_positive",
            "direct_merits_negative",
            "multiple_grounds",
            "pure_procedural_dismissal",
        }.issubset(categories))

    def test_all_v1_adversarial_cases_pass_current_grounding_contract(self):
        report = evaluate(load_cases(DEFAULT_CASES))
        self.assertEqual(report["summary"]["failed_cases"], 0)
        self.assertEqual(report["summary"]["case_pass_rate"], 1.0)
        self.assertEqual(report["summary"]["expected_term_recall"], 1.0)
        self.assertEqual(report["summary"]["forbidden_term_leakage_rate"], 0.0)
        self.assertEqual(report["summary"]["section_accuracy"], 1.0)
        self.assertEqual(report["summary"]["fallback_accuracy"], 1.0)

    def test_missing_decisive_term_fails_case(self):
        result = evaluate_case({
            "case_id": "X",
            "category": "test",
            "text": "## Nævnets vurdering\nNævnet finder, at fristen er udløbet.",
            "expected_section_contains": "nævnets vurdering",
            "expected_grounding_terms": ["tilstandsrapport"],
            "forbidden_grounding_terms": [],
            "expected_fallback": False,
        })
        self.assertFalse(result["passed"])
        self.assertEqual(result["missing_expected_terms"], ["tilstandsrapport"])

    def test_party_only_distractor_counts_as_leak_if_extractor_includes_it(self):
        result = evaluate_case({
            "case_id": "X",
            "category": "test",
            "text": "## Nævnets vurdering\nNævnet finder, at forholdet er dækket.",
            "expected_section_contains": "nævnets vurdering",
            "expected_grounding_terms": ["forholdet er dækket"],
            "forbidden_grounding_terms": ["forholdet er dækket"],
            "expected_fallback": False,
        })
        self.assertFalse(result["passed"])
        self.assertEqual(result["leaked_forbidden_terms"], ["forholdet er dækket"])

    def test_report_roundtrip_is_utf8_json(self):
        report = evaluate(load_cases(DEFAULT_CASES)[:1])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            write_report(report, path)
            text = path.read_text(encoding="utf-8")
        self.assertIn("decision_grounding_adversarial_v1", text)
        self.assertIn("tilstandsrapport", text)

    def test_scope_does_not_claim_gold_or_claim_decision_accuracy(self):
        report = evaluate(load_cases(DEFAULT_CASES)[:1])
        scope = report["scope"].casefold()
        self.assertIn("synthetic/adversarial", scope)
        self.assertIn("not a gold benchmark", scope)
        self.assertIn("not a claim-decision evaluator", scope)


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.evaluation.practice_synthesis_metrics import (
    evaluate,
    prediction_template,
    validate_human_labels,
    validate_predictions,
)


class PracticeSynthesisMetricsTests(unittest.TestCase):
    def _labels(self):
        return [
            {
                "audit_id": "a1", "question_id": "Q1", "query": "bjælke",
                "case_number": "1", "link": "u1", "label": "direct_practice",
                "benchmark_relevance": 2,
            },
            {
                "audit_id": "a2", "question_id": "Q1", "query": "bjælke",
                "case_number": "2", "link": "u2", "label": "direct_practice",
                "benchmark_relevance": 2,
            },
            {
                "audit_id": "a3", "question_id": "Q1", "query": "bjælke",
                "case_number": "3", "link": "u3", "label": "indirect_support",
                "benchmark_relevance": 1,
            },
            {
                "audit_id": "a4", "question_id": "Q1", "query": "bjælke",
                "case_number": "4", "link": "u4", "label": "not_useful",
                "benchmark_relevance": 0,
            },
            {
                "audit_id": "b1", "question_id": "Q2", "query": "fugt",
                "case_number": "5", "link": "u5", "label": "uncertain",
                "benchmark_relevance": None,
            },
        ]

    def test_human_labels_require_consistent_relevance_mapping(self):
        rows = self._labels()
        rows[0]["benchmark_relevance"] = 1
        with self.assertRaises(ValueError):
            validate_human_labels(rows)

    def test_template_contains_no_human_label_or_ranking_signal(self):
        source = [
            {"audit_id": "a1", "question_id": "Q1", "query": "bjælke"},
            {"audit_id": "a3", "question_id": "Q1", "query": "bjælke"},
        ]
        rows = prediction_template(source)
        self.assertEqual(len(rows), 1)
        self.assertEqual(set(rows[0]["source_roles"]), {"a1", "a3"})
        self.assertEqual(set(rows[0]["source_roles"].values()), {""})
        self.assertNotIn("human_label", rows[0])
        self.assertNotIn("retrieval_rank", rows[0])

    def test_predictions_cannot_move_source_between_questions(self):
        labels = validate_human_labels(self._labels())
        with self.assertRaises(ValueError):
            validate_predictions([
                {
                    "question_id": "Q2",
                    "source_roles": {"a1": "direct_practice"},
                }
            ], labels)

    def test_role_accuracy_excludes_uncertain_human_rows(self):
        predictions = [
            {
                "question_id": "Q1",
                "source_roles": {
                    "a1": "direct_practice",
                    "a2": "direct_practice",
                    "a3": "indirect_support",
                    "a4": "not_useful",
                },
            },
            {
                "question_id": "Q2",
                "source_roles": {"b1": "not_useful"},
            },
        ]
        report = evaluate(self._labels(), predictions)
        self.assertEqual(report["summary"]["benchmarkable_human_rows"], 4)
        self.assertEqual(report["summary"]["uncertain_human_rows"], 1)
        self.assertEqual(report["summary"]["role_accuracy"], 1.0)

    def test_indirect_source_in_distribution_is_structural_violation(self):
        predictions = [{
            "question_id": "Q1",
            "source_roles": {
                "a1": "direct_practice", "a2": "direct_practice",
                "a3": "indirect_support", "a4": "not_useful",
            },
            "distribution_denominator_audit_ids": ["a1", "a3"],
        }]
        report = evaluate(self._labels(), predictions)
        self.assertEqual(report["summary"]["distribution_denominator_entries"], 2)
        self.assertEqual(report["summary"]["distribution_direct_precision"], 0.5)
        leaks = report["violations"]["distribution_denominator_leaks"]
        self.assertEqual(leaks[0]["audit_id"], "a3")
        self.assertEqual(leaks[0]["human_label"], "indirect_support")

    def test_single_source_distribution_is_rejected_even_if_direct(self):
        predictions = [{
            "question_id": "Q1",
            "source_roles": {"a1": "direct_practice"},
            "distribution_denominator_audit_ids": ["a1"],
        }]
        report = evaluate(self._labels(), predictions)
        self.assertEqual(
            report["violations"]["distribution_minimum_evidence"],
            ["Q1"],
        )

    def test_practice_line_and_fixed_practice_need_three_direct_sources_minimum(self):
        predictions = [{
            "question_id": "Q1",
            "source_roles": {"a1": "direct_practice", "a2": "direct_practice"},
            "states_practice_line": True,
            "states_fixed_practice": True,
        }]
        report = evaluate(self._labels(), predictions)
        self.assertEqual(report["violations"]["practice_line_minimum_evidence"], ["Q1"])
        self.assertEqual(report["violations"]["fixed_practice_minimum_evidence"], ["Q1"])

    def test_metric_does_not_claim_three_direct_cases_prove_fixed_practice(self):
        labels = self._labels()
        labels.append({
            "audit_id": "a5", "question_id": "Q1", "query": "bjælke",
            "case_number": "6", "link": "u6", "label": "direct_practice",
            "benchmark_relevance": 2,
        })
        predictions = [{
            "question_id": "Q1",
            "source_roles": {
                "a1": "direct_practice", "a2": "direct_practice", "a5": "direct_practice"
            },
            "states_fixed_practice": True,
        }]
        report = evaluate(labels, predictions)
        self.assertEqual(report["violations"]["fixed_practice_minimum_evidence"], [])
        guardrail = report["interpretation"]["fixed_practice_guardrail"]
        self.assertIn("At least three", guardrail)
        self.assertIn("does not test", guardrail)
        self.assertIn("substantively consistent", guardrail)
        self.assertIn("does not determine substantive consistency", report["scope"])


if __name__ == "__main__":
    unittest.main()

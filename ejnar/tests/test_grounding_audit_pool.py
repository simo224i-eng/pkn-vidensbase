import unittest

from ejnar.evaluation.grounding_audit_pool import (
    blind_rows,
    build_candidates,
    detect_ground_tags,
    select_pool,
    summary_payload,
)


class GroundingAuditPoolTests(unittest.TestCase):
    def _beam_payload(self):
        return {
            "question_id": "EJ-X",
            "query": "Hvornår udgør nedbrydning af en bjælke en skade?",
            "detected_intent": "factual_lookup",
            "results": [{
                "rank": 2,
                "Sagsnummer": "102106",
                "Titel": "Nedbrydning i bjælke",
                "Dato": "2025-01-01",
                "Link": "https://example.test/102106",
                "Excerpt": "",
                "Tekst": """
## Selskabets opfattelse
Selskabet anfører, at bæreevnen ikke var væsentligt nedsat.

## Nævnets bemærkninger og afgørelse
Nævnet bemærker, at der er konstateret nedbrydning i den bærende bjælke, som kan have betydning for bæreevnen.

Det fremgår imidlertid af tilstandsrapporten, at nedbrydningen var anmærket før købet. Nævnet finder på den baggrund, at selskabet er berettiget til at afvise forholdet.
""",
            }],
        }

    def test_detects_common_dispositive_ground_tags(self):
        tags = detect_ground_tags(
            "Forholdet var anmærket i tilstandsrapporten, og kravet var desuden forældet."
        )
        self.assertIn("condition_report", tags)
        self.assertIn("deadline_or_limitation", tags)

    def test_beam_pattern_becomes_contrast_candidate(self):
        candidates = build_candidates([self._beam_payload()])
        self.assertEqual(len(candidates), 1)
        item = candidates[0]
        self.assertIn("condition_report", item["core_ground_tags"])
        self.assertIn("condition_report", item["exclusive_ground_tags"])
        self.assertGreaterEqual(item["contrast_score"], 2.0)
        self.assertIn("tilstandsrapporten", item["decision_core"])
        self.assertIn("nedbrydning", item["query_excerpt"].casefold())

    def test_specific_and_exact_searches_are_excluded_by_default(self):
        payload = self._beam_payload()
        for intent in ("specific_decision_search", "exact_content_search"):
            guarded = dict(payload)
            guarded["detected_intent"] = intent
            self.assertEqual(build_candidates([guarded]), [])

    def test_blind_pool_hides_rank_scores_and_heuristic_labels(self):
        selected = select_pool(build_candidates([self._beam_payload()]))
        rows = blind_rows(selected)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for forbidden_key in (
            "retrieval_rank",
            "contrast_score",
            "priority",
            "core_ground_tags",
            "exclusive_ground_tags",
            "query_excerpt_score",
        ):
            self.assertNotIn(forbidden_key, row)
        self.assertEqual(row["review_label"], "")
        self.assertEqual(row["review_notes"], "")

    def test_selection_prefers_high_contrast_and_respects_limit(self):
        candidates = [
            {"audit_id": "a", "contrast_score": 2.0, "retrieval_rank": 1, "question_id": "q"},
            {"audit_id": "b", "contrast_score": 6.0, "retrieval_rank": 8, "question_id": "q"},
            {"audit_id": "c", "contrast_score": 0.5, "retrieval_rank": 1, "question_id": "q"},
        ]
        selected = select_pool(candidates, min_contrast=2.0, max_pool=1)
        self.assertEqual([item["audit_id"] for item in selected], ["b"])

    def test_summary_clearly_marks_pool_as_heuristic_not_gold(self):
        payloads = [self._beam_payload()]
        candidates = build_candidates(payloads)
        selected = select_pool(candidates)
        summary = summary_payload(candidates, selected, payloads)
        self.assertEqual(summary["selected_pairs"], 1)
        self.assertIn("Not legal labels", summary["scope"])
        self.assertIn("not a gold benchmark", summary["scope"])


if __name__ == "__main__":
    unittest.main()

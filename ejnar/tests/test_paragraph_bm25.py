import unittest

from ejnar.paragraph_bm25 import ParagraphBM25Index, aggregate_decisions
from ejnar.paragraph_retrieval import ParagraphRecord


def rec(decision: str, paragraph: str, text: str) -> ParagraphRecord:
    return ParagraphRecord(
        decision_id=decision,
        section_id=f"sec-{decision}",
        paragraph_id=paragraph,
        section_title="Nævnets begrundelse",
        paragraph_index=0,
        text=text,
        char_start=0,
        char_end=len(text),
        title=f"Kendelse {decision}",
        case_number=decision,
        link=f"https://example.test/{decision}",
    )


class ParagraphBM25Tests(unittest.TestCase):
    def setUp(self):
        self.records = [
            rec("100", "p1", "Undertaget er ikke ført sammen over kip."),
            rec("200", "p2", "Der er almindelig ventilation i tagrummet."),
            rec("300", "p3", "Skørtet er ikke ført ned over soklen."),
            rec("100", "p4", "Der blev konstateret skimmel på undertaget."),
        ]
        self.index = ParagraphBM25Index(self.records)

    def test_exact_terms_rank_matching_paragraph_first(self):
        hits = self.index.search("undertaget ikke ført sammen kip")
        self.assertTrue(hits)
        self.assertEqual(hits[0].record.paragraph_id, "p1")

    def test_multiple_query_terms_receive_coverage_boost(self):
        hits = self.index.search("skimmel undertag")
        self.assertEqual(hits[0].record.paragraph_id, "p4")
        self.assertIn("skimmel", hits[0].matched_terms)

    def test_allowed_decisions_limit_search_space(self):
        hits = self.index.search("undertag", allowed_decision_ids={"200"})
        self.assertEqual(hits, [])

    def test_empty_query_is_safe(self):
        self.assertEqual(self.index.search(""), [])

    def test_aggregate_limits_long_decisions(self):
        hits = self.index.search("undertag skimmel kip", limit=10)
        decisions = aggregate_decisions(hits, max_paragraphs_per_decision=2)
        self.assertEqual(decisions[0].decision_id, "100")
        self.assertLessEqual(len(decisions[0].paragraph_hits), 2)

    def test_decision_metadata_is_preserved(self):
        hits = self.index.search("soklen")
        decisions = aggregate_decisions(hits)
        self.assertEqual(decisions[0].case_number, "300")
        self.assertEqual(decisions[0].link, "https://example.test/300")


if __name__ == "__main__":
    unittest.main()

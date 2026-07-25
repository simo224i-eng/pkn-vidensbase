from dataclasses import dataclass
import unittest

from ejnar.graph_ranking import (
    feature_document_frequencies,
    feature_idf,
    related_by_rarity,
)
from ejnar.legal_graph import build_decision_graph


@dataclass(frozen=True)
class FakeMetadata:
    building_parts: tuple[str, ...] = ()
    causes: tuple[str, ...] = ()
    consequences: tuple[str, ...] = ()
    coverage_outcomes: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()
    laws: tuple[str, ...] = ()
    construction_years: tuple[int, ...] = ()
    materials: tuple[str, ...] = ()
    remedies: tuple[str, ...] = ()
    depreciation: tuple[str, ...] = ()


def fake_extract(text: str) -> FakeMetadata:
    blob = text.lower()
    return FakeMetadata(
        building_parts=("vindue",) if "vindue" in blob else (("gulv",) if "gulv" in blob else ()),
        consequences=("råd",) if "råd" in blob else (),
        remedies=("reparation",) if "reparation" in blob else (),
        materials=("zink",) if "zink" in blob else (),
    )


class GraphRankingTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_decision_graph(
            [
                {"Sagsnummer": "1", "Titel": "Vindue", "Tekst": "vindue råd zink reparation"},
                {"Sagsnummer": "2", "Titel": "Nært hit", "Tekst": "vindue råd zink reparation"},
                {"Sagsnummer": "3", "Titel": "Boilerplate", "Tekst": "vindue reparation"},
                {"Sagsnummer": "4", "Titel": "Andet", "Tekst": "gulv reparation"},
            ],
            metadata_extractor=fake_extract,
        )
        self.target_id = next(
            key for key, payload in self.graph.decision_payloads.items()
            if payload["case_number"] == "1"
        )

    def test_document_frequencies_count_each_decision_once(self):
        frequencies = feature_document_frequencies(self.graph)
        self.assertEqual(frequencies["remedies:reparation"], 4)
        self.assertEqual(frequencies["materials:zink"], 2)

    def test_rare_feature_gets_higher_idf(self):
        self.assertGreater(feature_idf(10, 1), feature_idf(10, 9))
        self.assertGreaterEqual(feature_idf(10, 9), 1.0)

    def test_near_hit_ranks_before_boilerplate_hit(self):
        related = related_by_rarity(self.graph, self.target_id)
        self.assertEqual(related[0].case_number, "2")
        self.assertGreater(related[0].score, related[1].score)

    def test_contributions_are_explainable_and_sorted(self):
        related = related_by_rarity(self.graph, self.target_id)
        contributions = related[0].feature_contributions
        self.assertTrue(contributions)
        self.assertEqual(
            [weight for _, weight in contributions],
            sorted((weight for _, weight in contributions), reverse=True),
        )
        labels = {label for label, _ in contributions}
        self.assertIn("materials: zink", labels)

    def test_limit_and_missing_decision_are_safe(self):
        self.assertEqual(related_by_rarity(self.graph, "missing"), [])
        self.assertEqual(related_by_rarity(self.graph, self.target_id, limit=0), [])
        self.assertEqual(len(related_by_rarity(self.graph, self.target_id, limit=1)), 1)


if __name__ == "__main__":
    unittest.main()

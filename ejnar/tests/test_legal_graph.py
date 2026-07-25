from dataclasses import dataclass
import unittest

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
    building_parts = (
        ("tag",)
        if "tag" in blob
        else (("vindue",) if "vindue" in blob else (("gulv",) if "gulv" in blob else ()))
    )
    return FakeMetadata(
        building_parts=building_parts,
        causes=("fugt/vand",) if "fugt" in blob else (),
        consequences=(
            ("råd",)
            if "råd" in blob
            else (("kosmetisk",) if "kosmetisk" in blob else ())
        ),
        remedies=("udskiftning",) if "udskiftning" in blob else (),
    )


class LegalGraphTests(unittest.TestCase):
    def setUp(self):
        self.documents = [
            {
                "Sagsnummer": "100",
                "Titel": "Råd i trævinduer",
                "Link": "a",
                "Tekst": "Der var råd i trævinduer som følge af fugt og utætte fuger.",
                "Udfald": "Medhold",
            },
            {
                "Sagsnummer": "200",
                "Titel": "Råd i vinduer",
                "Link": "b",
                "Tekst": "Vinduerne havde råd og fugt. Udbedring krævede udskiftning.",
                "Udfald": "Delvis medhold",
            },
            {
                "Sagsnummer": "300",
                "Titel": "Gulv",
                "Link": "c",
                "Tekst": "Et parketgulv var kosmetisk hævet, men fortsat fast.",
                "Udfald": "Ikke medhold",
            },
        ]
        self.graph = build_decision_graph(
            self.documents,
            metadata_extractor=fake_extract,
        )

    def test_builds_decision_and_feature_nodes(self):
        decision_nodes = [
            node for node in self.graph.nodes.values() if node.kind == "decision"
        ]
        self.assertEqual(len(decision_nodes), 3)
        self.assertTrue(
            any(node.kind == "building_parts" for node in self.graph.nodes.values())
        )
        self.assertGreater(len(self.graph.edges), 0)

    def test_derived_mangeltype_does_not_create_graph_features(self):
        graph = build_decision_graph(
            [{
                "Sagsnummer": "400",
                "Titel": "Gulv",
                "Tekst": "Gulvet var ujævnt.",
                "Mangeltype": "Tag/tagdækning, Skimmel/fugt, Gulv",
                "Link": "d",
            }],
            metadata_extractor=fake_extract,
        )
        feature_labels = {
            node.label
            for node in graph.nodes.values()
            if node.kind != "decision"
        }
        self.assertIn("gulv", feature_labels)
        self.assertNotIn("tag", feature_labels)

    def test_related_decisions_share_explainable_features(self):
        decision_id = next(
            node_id
            for node_id, payload in self.graph.decision_payloads.items()
            if payload["case_number"] == "100"
        )
        related = self.graph.related(decision_id)
        self.assertEqual(related[0].case_number, "200")
        self.assertTrue(
            any(
                "building_parts" in value or "consequences" in value
                for value in related[0].shared_features
            )
        )

    def test_unrelated_decision_is_not_returned_by_default(self):
        decision_id = next(
            node_id
            for node_id, payload in self.graph.decision_payloads.items()
            if payload["case_number"] == "100"
        )
        related = self.graph.related(decision_id)
        self.assertNotIn("300", {item.case_number for item in related})

    def test_duplicate_documents_do_not_duplicate_edges(self):
        graph = build_decision_graph(
            [self.documents[0], self.documents[0]],
            metadata_extractor=fake_extract,
        )
        keys = {(edge.source, edge.relation, edge.target) for edge in graph.edges}
        self.assertEqual(len(keys), len(graph.edges))
        self.assertEqual(len(graph.decision_payloads), 1)

    def test_serialisation_is_stable(self):
        first = self.graph.to_dict()
        second = build_decision_graph(
            reversed(self.documents),
            metadata_extractor=fake_extract,
        ).to_dict()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()

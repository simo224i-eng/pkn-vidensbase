from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
import unittest

from ejnar.build_legal_graph import EJNAR_DIR, graph_payload, graph_statistics, write_graph
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
        building_parts=("tag",) if "tag" in blob else (),
        causes=("fugt/vand",) if "fugt" in blob else (),
    )


class BuildLegalGraphTests(unittest.TestCase):
    def setUp(self):
        self.graph = build_decision_graph(
            [
                {"Sagsnummer": "1", "Titel": "Tag med fugt", "Tekst": "Tag og fugt", "Link": "a"},
                {"Sagsnummer": "2", "Titel": "Tom kendelse", "Tekst": "Ingen metadata", "Link": "b"},
            ],
            metadata_extractor=fake_extract,
        )

    def test_cli_resolves_ejnar_directory_after_move(self):
        self.assertEqual(EJNAR_DIR.name, "ejnar")
        self.assertTrue((EJNAR_DIR / "evaluation").is_dir())

    def test_statistics_count_decisions_features_and_isolated(self):
        stats = graph_statistics(self.graph)
        self.assertEqual(stats["decisions"], 2)
        self.assertEqual(stats["feature_nodes"], 2)
        self.assertEqual(stats["edges"], 2)
        self.assertEqual(stats["isolated_decisions"], 1)

    def test_payload_has_schema_and_graph(self):
        payload = graph_payload(self.graph)
        self.assertEqual(payload["schema_version"], "ejnar-legal-graph-v1")
        self.assertIn("statistics", payload)
        self.assertIn("nodes", payload["graph"])
        self.assertIn("edges", payload["graph"])

    def test_write_graph_creates_parent_and_valid_json(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "graph.json"
            write_graph(target, self.graph)
            payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(payload["statistics"]["decisions"], 2)

    def test_compact_output_is_smaller(self):
        with tempfile.TemporaryDirectory() as directory:
            normal = Path(directory) / "normal.json"
            compact = Path(directory) / "compact.json"
            write_graph(normal, self.graph)
            write_graph(compact, self.graph, compact=True)
            self.assertLess(compact.stat().st_size, normal.stat().st_size)

    def test_repeated_exports_are_byte_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.json"
            second = Path(directory) / "second.json"
            write_graph(first, self.graph)
            write_graph(second, self.graph)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()

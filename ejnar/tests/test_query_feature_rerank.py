from dataclasses import dataclass
import unittest

from ejnar.query_feature_rerank import rerank_by_query_features


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
        building_parts=("gulv",) if "gulv" in blob else (("tag",) if "tag" in blob else ()),
        consequences=("kosmetisk",) if "kosmetisk" in blob else (),
        causes=("fugt/vand",) if "fugt" in blob else (),
    )


class QueryFeatureRerankTests(unittest.TestCase):
    def test_matching_candidate_can_move_up(self):
        candidates = [
            {"Sagsnummer": "1", "Titel": "Tag", "Tekst": "Skade på tag"},
            {"Sagsnummer": "2", "Titel": "Gulv", "Tekst": "Kosmetisk skade på gulv"},
        ]
        reranked = rerank_by_query_features(
            "kosmetisk gulv",
            candidates,
            metadata_extractor=fake_extract,
            strength=0.5,
        )
        self.assertEqual(reranked[0]["Sagsnummer"], "2")
        self.assertIn("building_parts: gulv", reranked[0]["_query_feature_matches"])

    def test_zero_strength_preserves_original_objects_and_order(self):
        candidates = [{"Sagsnummer": "1"}, {"Sagsnummer": "2"}]
        self.assertEqual(
            rerank_by_query_features(
                "gulv", candidates, metadata_extractor=fake_extract, strength=0
            ),
            candidates,
        )

    def test_query_without_features_preserves_order(self):
        candidates = [{"Sagsnummer": "1"}, {"Sagsnummer": "2"}]
        result = rerank_by_query_features(
            "ukendt spørgsmål", candidates, metadata_extractor=fake_extract
        )
        self.assertEqual(result, candidates)

    def test_derived_mangeltype_is_not_used(self):
        candidates = [
            {
                "Sagsnummer": "1",
                "Titel": "Tag",
                "Tekst": "Skade på tag",
                "Mangeltype": "Gulv, kosmetisk",
            },
            {"Sagsnummer": "2", "Titel": "Gulv", "Tekst": "Kosmetisk skade på gulv"},
        ]
        result = rerank_by_query_features(
            "kosmetisk gulv",
            candidates,
            metadata_extractor=fake_extract,
            strength=0.5,
        )
        self.assertEqual(result[0]["Sagsnummer"], "2")

    def test_common_features_are_weaker_than_rare_features(self):
        candidates = [
            {"Sagsnummer": "1", "Titel": "Gulv", "Tekst": "Gulv"},
            {"Sagsnummer": "2", "Titel": "Gulv", "Tekst": "Kosmetisk gulv"},
            {"Sagsnummer": "3", "Titel": "Gulv", "Tekst": "Gulv"},
        ]
        result = rerank_by_query_features(
            "kosmetisk gulv",
            candidates,
            metadata_extractor=fake_extract,
            strength=0.5,
        )
        self.assertEqual(result[0]["Sagsnummer"], "2")
        self.assertGreater(
            result[0]["_query_feature_score"], result[1]["_query_feature_score"]
        )


if __name__ == "__main__":
    unittest.main()

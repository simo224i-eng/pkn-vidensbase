import unittest

from ejnar.metadata_runtime import metadata_overlap_score, rerank_with_metadata
from ejnar.metadata_schema import DecisionMetadata


class _Row(dict):
    pass


class _ILoc:
    def __init__(self, rows):
        self.rows = rows

    def __getitem__(self, index):
        return self.rows[index]


class _Frame:
    def __init__(self, rows):
        self.rows = rows
        self.iloc = _ILoc(rows)

    def __len__(self):
        return len(self.rows)


class MetadataRuntimeTests(unittest.TestCase):
    def test_overlap_uses_weighted_fields(self):
        query = DecisionMetadata(building_parts=("tagrende",), materials=("aluminium",))
        doc = DecisionMetadata(building_parts=("tagrende",), materials=("aluminium",))
        self.assertEqual(metadata_overlap_score(query, doc), 5.5)

    def test_non_matching_metadata_scores_zero(self):
        query = DecisionMetadata(building_parts=("gulv",))
        doc = DecisionMetadata(building_parts=("tag",))
        self.assertEqual(metadata_overlap_score(query, doc), 0.0)

    def test_matching_candidate_can_move_up_slightly(self):
        df = _Frame([
            _Row(Titel="Generel kendelse", Tekst="Et andet forhold"),
            _Row(Titel="Tagrende", Tekst="Aluminiumtape på tagrenden"),
            _Row(Titel="Vindue", Tekst="Råd i vindue"),
        ])
        ranked = rerank_with_metadata("aluminiumtape på tagrende", [0, 1, 2], df)
        self.assertEqual(ranked[0], 1)
        self.assertEqual(set(ranked), {0, 1, 2})

    def test_no_signal_preserves_order(self):
        df = _Frame([
            _Row(Titel="A", Tekst="tekst"),
            _Row(Titel="B", Tekst="tekst"),
        ])
        self.assertEqual(rerank_with_metadata("fortæl mere", [1, 0], df), [1, 0])

    def test_ties_preserve_original_order(self):
        df = _Frame([
            _Row(Titel="Tag", Tekst="tag"),
            _Row(Titel="Tag", Tekst="tag"),
        ])
        self.assertEqual(rerank_with_metadata("tag", [1, 0], df), [1, 0])


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.metadata_runtime import rerank_with_metadata


class _Row(dict):
    pass


class _ILoc:
    def __init__(self, rows):
        self.rows = rows
        self.accessed = []

    def __getitem__(self, index):
        self.accessed.append(index)
        return self.rows[index]


class _Frame:
    def __init__(self, rows):
        self.iloc = _ILoc(rows)
        self.rows = rows

    def __len__(self):
        return len(self.rows)


class FastMetadataRuntimeTests(unittest.TestCase):
    def test_only_ranked_candidates_are_read(self):
        frame = _Frame([
            _Row(Titel="Tagrende", Tekst="Aluminiumtape på tagrenden"),
            _Row(Titel="Gulv", Tekst="Hævet gulv"),
            _Row(Titel="Ikke kandidat", Tekst="Aluminiumtape på tagrenden"),
        ])
        result = rerank_with_metadata("aluminiumtape på tagrende", [1, 0], frame)
        self.assertEqual(set(result), {0, 1})
        self.assertEqual(set(frame.iloc.accessed), {0, 1})
        self.assertNotIn(2, frame.iloc.accessed)

    def test_no_metadata_signal_reads_no_rows(self):
        frame = _Frame([
            _Row(Titel="A", Tekst="tekst"),
            _Row(Titel="B", Tekst="tekst"),
        ])
        result = rerank_with_metadata("fortæl mere", [1, 0], frame)
        self.assertEqual(result, [1, 0])
        self.assertEqual(frame.iloc.accessed, [])


if __name__ == "__main__":
    unittest.main()

import csv
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine


def _write_csv(path, n):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Dato", "Titel", "Link", "Tekst", "Sagsnummer", "Selskab", "Udfald", "Mangeltype"])
        w.writeheader()
        for i in range(n):
            w.writerow({"Dato": f"2020-01-0{i + 1}", "Titel": f"Skimmel i kælder nr {i}. Selskab medhold.",
                        "Link": f"https://x/{i}", "Tekst": "Skimmel i kælder. Klagen kan ikke tages til følge.",
                        "Sagsnummer": str(90000 + i), "Selskab": "Tryg", "Udfald": "", "Mangeltype": ""})


class CorpusCacheTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.cache = tempfile.mkdtemp()
        _write_csv(os.path.join(self.root, "ejnar_test.csv"), 3)
        engine._CORPUS_MEMO.clear()

    def test_second_load_comes_from_disk(self):
        with mock.patch.object(engine, "CACHE_DIR", self.cache):
            df, vec, mat = engine.load_corpus_cached(self.root)
            self.assertEqual(len(os.listdir(self.cache)), 1)
            engine._CORPUS_MEMO.clear()
            with mock.patch.object(engine, "load_data", side_effect=AssertionError("ikke cachet")):
                df2, vec2, mat2 = engine.load_corpus_cached(self.root)
        self.assertEqual(list(df2["Id"]), list(df["Id"]))
        self.assertEqual(vec2.vocabulary_, vec.vocabulary_)

    def test_data_change_invalidates_cache(self):
        with mock.patch.object(engine, "CACHE_DIR", self.cache):
            k1 = engine._corpus_cache_key(self.root)
            _write_csv(os.path.join(self.root, "ejnar_test.csv"), 4)
            k2 = engine._corpus_cache_key(self.root)
            self.assertNotEqual(k1, k2)
            df, _, _ = engine.load_corpus_cached(self.root)
        self.assertEqual(len(df), 4)
        self.assertEqual(len(os.listdir(self.cache)), 1)  # gamle cachefiler ryddes op


if __name__ == "__main__":
    unittest.main()

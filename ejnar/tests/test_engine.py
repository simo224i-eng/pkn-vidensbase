import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine


def rows():
    return [
        {"Dato": "2021-03-01", "Titel": "Klager over afvisning af dækning for skimmelsvamp i kælder. Selskab medhold.",
         "Link": "https://x/1", "Tekst": "Skimmelsvamp i kælderen. Klagen kan ikke tages til følge.",
         "Excerpt": "", "Sagsnummer": "93497", "Selskab": "Tryg", "Udfald": "Ukendt",
         "Mangeltype": ["Tag/tagdækning"], "Forsikringstype": "Ejerskifteforsikring"},
        {"Dato": "2019-06-10", "Titel": "Selskabet afviste dækning for utæt undertag. Klager delvis medhold.",
         "Link": "https://x/2", "Tekst": "Undertaget var utæt. Klageren får i øvrigt ikke medhold.",
         "Excerpt": "", "Sagsnummer": "88001 (12/19)", "Selskab": "Codan", "Udfald": "Ikke medhold",
         "Mangeltype": [], "Forsikringstype": "Ejerskifteforsikring"},
        {"Dato": "2010-01-05", "Titel": "Ejerskifte - kloak",
         "Link": "https://x/3", "Tekst": "Rotter i kloakken. Derfor b e s t e m m e s : Nævnet kan ikke viderebe- handle sagen.",
         "Excerpt": "", "Sagsnummer": "60767", "Selskab": "Tryg", "Udfald": "",
         "Mangeltype": [], "Forsikringstype": "Ejerskifteforsikring"},
    ]


class OutcomeTests(unittest.TestCase):
    def test_title_outcome_wins_over_rejection_wording(self):
        # "afviste dækning" betyder ikke at sagen er afvist
        self.assertEqual(engine.detect_udfald_ejnar(
            "Selskabet afviste dækning for skimmel. Selskab medhold.", ""), "Ikke medhold")
        self.assertEqual(engine.detect_udfald_ejnar("... Klager medhold.", ""), "Medhold")
        self.assertEqual(engine.detect_udfald_ejnar("... Klager delvist medhold.", ""), "Delvis medhold")
        self.assertEqual(engine.detect_udfald_ejnar("... Klager delvis mehold.", ""), "Delvis medhold")
        self.assertEqual(engine.detect_udfald_ejnar("... Sag afvist.", ""), "Afvist")

    def test_conclusion_and_csv_fallbacks(self):
        self.assertEqual(engine.detect_udfald_ejnar("Ejerskifte - gasfyr", "Klagen kan ikke tages til følge."),
                         "Ikke medhold")
        self.assertEqual(engine.detect_udfald_ejnar("x", "b e s t e m m e s : Nævnet kan ikke behandle sagen."),
                         "Afvist")
        self.assertEqual(engine.detect_udfald_ejnar("x", "intet", "Medhold"), "Medhold")
        self.assertEqual(engine.detect_udfald_ejnar("x", "intet", "Ukendt"), "Ukendt")


class DefectTypeTests(unittest.TestCase):
    def test_no_substring_false_positives(self):
        self.assertEqual(engine.detect_mangeltyper(
            "Klagen kunne ikke tages til følge efter foretaget rådgivning", ""), ["Andet"])
        self.assertEqual(engine.detect_mangeltyper("Skævt gulv i Myresjøhus", ""), ["Gulv"])

    def test_detects_from_title_then_text(self):
        self.assertIn("Tag/tagdækning", engine.detect_mangeltyper("Utæt undertag", ""))
        self.assertIn("Skimmel/fugt", engine.detect_mangeltyper("Skimmelsvamp i kælder", ""))
        self.assertNotIn("Råd/svamp/insekt", engine.detect_mangeltyper("Skimmelsvamp", ""))
        self.assertIn("Kloak/dræn", engine.detect_mangeltyper("AnkeforsikringDBECT_1.aspx", "brud på kloakledning"))


class CorpusTests(unittest.TestCase):
    def setUp(self):
        df = engine.prepare_frame(rows())
        vec, mat = engine.build_index(df)
        self.c = engine.Corpus(df=df, vec=vec, mat=mat, options=engine.filter_options(df))

    def test_prepare_frame_reclassifies_and_ids(self):
        df = self.c.df
        self.assertEqual(list(df["Udfald"]), ["Ikke medhold", "Delvis medhold", "Afvist"])
        self.assertNotIn("Tag/tagdækning", df.loc[0, "Mangeltype"])
        self.assertEqual(df["Id"].nunique(), 3)
        self.assertEqual(df.loc[0, "Id"], engine.decision_id("https://x/1"))

    def test_find_by_id_and_case_number(self):
        self.assertEqual(self.c.find(self.c.df.loc[1, "Id"])["Sagsnummer"], "88001 (12/19)")
        self.assertEqual(self.c.find("88001")["Link"], "https://x/2")
        self.assertIsNone(self.c.find("nope"))

    def test_filters(self):
        self.assertIsNone(self.c.sub_idx(år_fra=None, mangeltyper=[]))
        self.assertEqual(self.c.sub_idx(selskaber=["Tryg"]), [0, 2])
        self.assertEqual(self.c.sub_idx(år_fra=2015, udfald=["Delvis medhold"]), [1])
        self.assertEqual(self.c.sub_idx(mangeltyper=["Kloak/dræn"]), [2])

    def test_exact_search(self):
        hits = engine.ordret_søg("undertag", self.c.df)
        self.assertEqual(list(hits["Link"]), ["https://x/2"])

    def test_cited_sources(self):
        self.assertEqual(engine.citerede_kilder("A [Kilde 2] B [Kilde 1, 2, 9]", 3), [2, 1])


if __name__ == "__main__":
    unittest.main()

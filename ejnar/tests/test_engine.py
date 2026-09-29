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


class CoverageTests(unittest.TestCase):
    def test_detects_basis_and_extended(self):
        d = engine.detect_daekning
        self.assertEqual(d("Klager har tegnet ejerskifteforsikring med udvidet dækning i Codan."), "Udvidet")
        self.assertEqual(d("Klagerne har tegnet en ejerskifteforsikring uden udvidet dækning."), "Basis")
        self.assertEqual(d("klageren ikke har tegnet udvidet forsikring med dækning for ulovlige forhold"), "Basis")
        # Negation vinder, selv om udvidet dækning også omtales generelt
        self.assertEqual(d("Udvidet dækning omfatter ulovlige forhold. Klager havde ikke tegnet udvidet dækning."), "Basis")
        self.assertEqual(d("Klager overtog huset i 2019."), "Ikke angivet")


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

    def test_relevance_search_is_llm_free(self):
        from unittest import mock
        engine.ensure_runtimes()
        with mock.patch.object(engine.shared, "_llm", side_effect=AssertionError("LLM kaldt")):
            idx = engine.relevans_søg("klager dækning", self.c.df, self.c.vec, self.c.mat, top_n=5)
        self.assertTrue(idx)
        self.assertTrue(set(idx) <= {0, 1, 2})
        self.assertEqual(engine.relevans_søg("", self.c.df, self.c.vec, self.c.mat), [])

    def test_exact_search(self):
        hits = engine.ordret_søg("undertag", self.c.df)
        self.assertEqual(list(hits["Link"]), ["https://x/2"])

    def test_fuse_rankings_boosts_overlap_without_dropping(self):
        a, b, c = {"Link": "a"}, {"Link": "b"}, {"Link": "c"}
        fused = engine.fuse_rankings([[b, c], [a, b]], limit=10)
        self.assertEqual([r["Link"] for r in fused][0], "b")
        self.assertEqual({r["Link"] for r in fused}, {"a", "b", "c"})

    def test_smart_retrieval_keeps_unfiltered_candidates(self):
        from unittest import mock
        df = self.c.df
        calls = []

        def fake_tfidf(q, df_, vec, mat, sub_idx=None, top_n=30, ekspander=False):
            calls.append(list(sub_idx))
            return df_.loc[sub_idx].reset_index(drop=True)

        with mock.patch.object(engine.shared, "klassificer_query", return_value={"top_retrieve": 10, "top_final": 5}), \
             mock.patch.object(engine.shared, "omformuler_opfoelgning", return_value="kloak"), \
             mock.patch.object(engine.shared, "auto_filter_query", return_value={"Mangeltype": ["Kloak/dræn"]}), \
             mock.patch.object(engine.shared, "udvid_query", return_value="kloak"), \
             mock.patch.object(engine.shared, "llm_rerank", side_effect=lambda q, k, top_n: k[:top_n]), \
             mock.patch.object(engine.shared, "apply_auto_filters", return_value=([2], True)), \
             mock.patch.object(engine, "tfidf_søg", side_effect=fake_tfidf):
            debug = {}
            _, kilder = engine.smart_retrieval("kloak", df, None, None, [0, 1, 2], [],
                                               filter_options=self.c.options, debug=debug)
        self.assertTrue(debug["applied"])
        self.assertEqual(kilder[0]["Link"], "https://x/3")  # metadata-match boostes
        self.assertEqual({k["Link"] for k in kilder}, {"https://x/1", "https://x/2", "https://x/3"})

    def test_citation_check_tolerates_pdf_word_breaks(self):
        docs = [{"Tekst": "Nævnet fandt, at sels kabet med rette havde afvist dækning, da undersøgel- se ikke var foretaget."}]
        ok = 'Nævnet fandt: "at selskabet med rette havde afvist dækning, da undersøgelse ikke var foretaget" [Kilde 1]'
        bad = 'Nævnet fandt: "at selskabet skal betale fuld erstatning for hele kælderen og følgeskader" [Kilde 1]'
        self.assertEqual(engine.mistænkelige_citater(ok, docs), [])
        self.assertEqual(len(engine.mistænkelige_citater(bad, docs)), 1)

    def test_citation_check_pairs_quotes_correctly(self):
        docs = [{"Tekst": "forholdet medførte ikke nedsat brugbarhed. Klageren havde ikke godtgjort at skaden var til stede ved overtagelsen."}]
        answer = ('Nævnet talte om "nedsat brugbarhed" [Kilde 1]. Det var afgørende, at '
                  '"Klageren havde ikke godtgjort at skaden var til stede ved overtagelsen" [Kilde 1], '
                  'og „forholdet medførte ikke nedsat brugbarhed“ [Kilde 1].')
        self.assertEqual(engine.mistænkelige_citater(answer, docs), [])
        fake = 'Nævnet sagde “selskabet skal betale fuld erstatning for hele kælderen” [Kilde 1].'
        self.assertEqual(len(engine.mistænkelige_citater(fake, docs)), 1)

    def test_citation_check_accepts_ellipsis_and_user_question(self):
        docs = [{"Tekst": "Det kan ikke udelukkes, at der er tale om brud på dræn eller svigtende funktion af det oprindelige dræn."}]
        answer = 'Nævnet skrev "Det kan ikke udelukkes … svigtende funktion af det oprindelige dræn" [Kilde 1].'
        self.assertEqual(engine.mistænkelige_citater(answer, docs), [])
        question = "TR skriver: 'Fugtig krybekælder, der er risiko for skimmelvækst'"
        own = 'TR-formuleringen "Fugtig krybekælder, der er risiko for skimmelvækst" er afgørende.'
        self.assertEqual(engine.mistænkelige_citater(own, docs, question), [])
        self.assertEqual(len(engine.mistænkelige_citater(own, docs)), 1)

    def test_prompt_asks_for_short_answer_first(self):
        text = engine.byg_prompt("Dækkes skimmel?", [])[0]["text"]
        self.assertIn("## Kort svar", text)
        self.assertIn("## Anbefaling", text)
        self.assertIn("besvar hvert led for sig", text)
        self.assertIn("årsspændet", text)

    def test_context_headers_show_outcome(self):
        import shared
        docs = self.c.df.to_dict("records")
        ctx = shared.byg_fokuseret_kontekst("skimmel kælder", docs)
        self.assertIn("[Kilde 1] 01.03.2021 – [Udfald for klager: Ikke medhold]", ctx)
        self.assertIn("[Kilde 3]", ctx)

    def test_cited_sources(self):
        self.assertEqual(engine.citerede_kilder("A [Kilde 2] B [Kilde 1, 2, 9]", 3), [2, 1])


if __name__ == "__main__":
    unittest.main()

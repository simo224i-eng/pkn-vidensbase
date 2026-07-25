import unittest

from ejnar.retrieval_runtime import _exact_match_ranking, _phrase_match


class _Row(dict):
    def __init__(self, *args, forbid_text=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.forbid_text = forbid_text

    def get(self, key, default=None):
        if key == "Tekst" and self.forbid_text:
            raise AssertionError("Tekst må ikke læses ved rent kendelses-ID-opslag")
        return super().get(key, default)


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


class FastExactMatchTests(unittest.TestCase):
    def test_decision_id_lookup_does_not_read_full_text(self):
        frame = _Frame([
            _Row(
                Sagsnummer="100123",
                Titel="Kendelse",
                Link="https://ankeforsikring.dk/kendelser/100123",
                Tekst="stor tekst",
                forbid_text=True,
            ),
            _Row(Sagsnummer="200456", Titel="Anden", Link="b", Tekst="tekst", forbid_text=True),
        ])
        result = _exact_match_ranking("Find kendelse nr. 100123", frame, None, 10)
        self.assertEqual(result[0], 0)

    def test_phrase_matching_accepts_whitespace_variation(self):
        self.assertTrue(
            _phrase_match(
                "undertaget er ikke ført sammen over kip",
                "undertaget er ikke ført\n\n sammen over kip",
            )
        )

    def test_phrase_matching_is_case_insensitive(self):
        self.assertTrue(_phrase_match("Aluminiumtape", "Der blev anvendt aluminiumtape."))

    def test_exact_phrase_boosts_matching_decision(self):
        frame = _Frame([
            _Row(Sagsnummer="1", Titel="A", Link="a", Tekst="Generel ventilation ved kip."),
            _Row(
                Sagsnummer="2",
                Titel="B",
                Link="b",
                Tekst="Undertaget er ikke ført sammen over kip.",
            ),
        ])
        result = _exact_match_ranking(
            'Find afgørelser hvor der står "undertaget er ikke ført sammen over kip"',
            frame,
            None,
            10,
        )
        self.assertEqual(result, [1])

    def test_sub_index_is_respected(self):
        frame = _Frame([
            _Row(Sagsnummer="1", Titel="A", Link="a", Tekst="aluminiumtape"),
            _Row(Sagsnummer="2", Titel="B", Link="b", Tekst="aluminiumtape"),
        ])
        result = _exact_match_ranking(
            'Find afgørelser hvor der står "aluminiumtape"',
            frame,
            [1],
            10,
        )
        self.assertEqual(result, [1])

    def test_query_without_phrase_or_identifier_has_no_direct_ranking(self):
        frame = _Frame([_Row(Sagsnummer="1", Titel="A", Link="a", Tekst="tag")])
        self.assertEqual(_exact_match_ranking("Hvad er praksis om tag?", frame, None, 10), [])


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.paragraph_retrieval import (
    build_paragraph_records,
    citation_payload,
    decision_identity,
    exact_phrase_search,
    split_sections,
)


class ParagraphRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "Sagsnummer": "100123",
            "Titel": "Undertag ved kip",
            "Dato": "2025-02-01",
            "Link": "https://example.test/100123",
            "Tekst": (
                "## Sagens oplysninger\n"
                "Huset er opført i 1950. Taget blev renoveret i 2004.\n\n"
                "Undertaget er ikke ført sammen over kip. Der er ventilation under rygningsstenene.\n\n"
                "## Nævnets begrundelse\n"
                "Nævnet finder efter en samlet vurdering, at klageren ikke har bevist en dækningsberettiget skade."
            ),
        }

    def test_decision_identity_is_stable(self):
        first = decision_identity(self.document)
        second = decision_identity(dict(reversed(list(self.document.items()))))
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("dec-"))

    def test_sections_preserve_headings(self):
        sections = split_sections(self.document["Tekst"])
        self.assertEqual([title for title, _ in sections], ["Sagens oplysninger", "Nævnets begrundelse"])
        self.assertEqual(len(sections[0][1]), 2)

    def test_build_records_has_stable_hierarchy(self):
        records = build_paragraph_records(self.document)
        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].decision_id, records[1].decision_id)
        self.assertEqual(records[0].section_id, records[1].section_id)
        self.assertNotEqual(records[1].section_id, records[2].section_id)
        self.assertTrue(all(record.paragraph_id.startswith("par-") for record in records))

    def test_exact_phrase_search_returns_matching_paragraph(self):
        records = build_paragraph_records(self.document)
        hits = exact_phrase_search(
            'Find kendelser hvor der står "undertaget er ikke ført sammen over kip"',
            records,
        )
        self.assertEqual(len(hits), 1)
        self.assertIn("ikke ført sammen over kip", hits[0].text.lower())

    def test_long_paragraph_is_split(self):
        document = dict(self.document)
        document["Tekst"] = "## Sektion\n" + "Dette er en sætning. " * 100
        records = build_paragraph_records(document, max_chars=180, min_chars=10)
        self.assertGreater(len(records), 1)
        self.assertTrue(all(len(record.text) <= 220 for record in records))

    def test_citation_payload_is_verifiable(self):
        record = build_paragraph_records(self.document)[1]
        payload = citation_payload(record)
        self.assertEqual(payload["case_number"], "100123")
        self.assertEqual(payload["quote"], record.text)
        self.assertLess(payload["char_start"], payload["char_end"])
        self.assertIn("paragraph_id", payload)


if __name__ == "__main__":
    unittest.main()

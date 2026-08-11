import unittest

from ejnar.answer_citation_explainability import (
    claims_for_source,
    extract_source_claims,
    render_source_claims_html,
)


class AnswerCitationExplainabilityTests(unittest.TestCase):
    def test_maps_cited_sentence_to_source(self):
        answer = (
            "Nævnet lagde vægt på, at forholdet var anmærket i tilstandsrapporten "
            "[Kilde 2]. En anden kendelse angik fugt [Kilde 3]."
        )
        self.assertEqual(
            claims_for_source(answer, 2, source_count=3),
            (
                "Nævnet lagde vægt på, at forholdet var anmærket i tilstandsrapporten [Kilde 2].",
            ),
        )
        self.assertEqual(
            claims_for_source(answer, 3, source_count=3),
            ("En anden kendelse angik fugt [Kilde 3].",),
        )

    def test_multi_source_reference_maps_same_claim_to_each_source(self):
        answer = "Flere kendelser peger på samme moment [Kilde 1, 3]."
        claims = extract_source_claims(answer, source_count=3)
        self.assertEqual(claims[1], (answer,))
        self.assertEqual(claims[3], (answer,))
        self.assertNotIn(2, claims)

    def test_html_blocks_are_reduced_to_plain_claims(self):
        answer = (
            "<div><strong>Direkte praksis</strong></div>"
            "<p>Nævnet fandt, at forholdet ikke var godtgjort ved overtagelsen "
            "[Kilde 4].</p>"
        )
        claim = claims_for_source(answer, 4, source_count=4)[0]
        self.assertIn("ikke var godtgjort ved overtagelsen", claim)
        self.assertNotIn("<p>", claim)
        self.assertNotIn("<strong>", claim)

    def test_out_of_range_source_numbers_are_ignored(self):
        answer = "Påstand A [Kilde 2]. Påstand B [Kilde 99]."
        claims = extract_source_claims(answer, source_count=4)
        self.assertIn(2, claims)
        self.assertNotIn(99, claims)

    def test_duplicate_reference_in_same_claim_is_deduplicated(self):
        answer = "Samme begrundelse fremgår to steder [Kilde 1] [Kilde 1]."
        self.assertEqual(len(claims_for_source(answer, 1, source_count=1)), 1)

    def test_rendering_escapes_answer_content(self):
        answer = "<p>&lt;script&gt;alert(1)&lt;/script&gt; [Kilde 1].</p>"
        rendered = render_source_claims_html(answer, 1, source_count=1)
        self.assertIn("Brugt i svaret til", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)

    def test_rendering_does_not_claim_legal_support(self):
        answer = "Dette er dækket [Kilde 1]."
        rendered = render_source_claims_html(answer, 1, source_count=1)
        self.assertIn("ikke en automatisk vurdering", rendered)
        self.assertNotIn("understøttet: ja", rendered.casefold())
        self.assertNotIn("misvisende", rendered.casefold())

    def test_uncited_source_has_no_claim_card(self):
        self.assertEqual(
            render_source_claims_html("Kun [Kilde 1] bruges.", 2, source_count=2),
            "",
        )


if __name__ == "__main__":
    unittest.main()

import unittest

from ejnar.source_explainability import (
    render_source_decision_core_html,
    source_decision_core,
)


class SourceExplainabilityTests(unittest.TestCase):
    def test_beam_source_shows_actual_condition_report_ground(self):
        document = {
            "Tekst": """
## Sagkyndig
Den sagkyndige oplyser, at bjælkens bæreevne er væsentligt nedsat.

## Nævnets bemærkninger og afgørelse
Nævnet bemærker, at der er nedbrydning i bjælken.
Det fremgår imidlertid af tilstandsrapporten, at forholdet var anmærket før købet. Nævnet finder derfor, at selskabet er berettiget til at afvise forholdet.
"""
        }
        core = source_decision_core(document, "Hvornår udgør nedbrydning af en bjælke en skade?")
        self.assertIsNotNone(core)
        self.assertIn("tilstandsrapporten", core.text)
        self.assertNotIn("væsentligt nedsat", core.text)

    def test_multi_issue_source_is_query_specific(self):
        document = {
            "Tekst": """
## Nævnets bemærkninger
Vedrørende murværket finder nævnet, at revnerne er kosmetiske og ikke udgør skade.

Vedrørende ventilationen i tagrummet finder nævnet, at den manglende ventilation har medført skimmel. Forholdet udgør derfor skade.

Vedrørende vinduet finder nævnet, at utætheden er anmærket i tilstandsrapporten. Klageren får derfor ikke medhold.
"""
        }
        core = source_decision_core(document, "Hvad er praksis om manglende ventilation i tagrum?")
        self.assertIsNotNone(core)
        self.assertIn("ventilation", core.text.casefold())
        self.assertIn("skimmel", core.text.casefold())
        self.assertNotIn("vinduet", core.text.casefold())

    def test_html_is_escaped_and_does_not_assign_legal_role(self):
        document = {
            "Tekst": """
## Nævnets vurdering
Nævnet finder, at <script>alert('x')</script> ikke ændrer resultatet. Klageren får ikke medhold.
"""
        }
        rendered = render_source_decision_core_html(document, "Hvad fandt nævnet?")
        self.assertIn("Nævnets afgørelseskerne", rendered)
        self.assertIn("&lt;script&gt;", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertNotIn("Direkte praksis", rendered)
        self.assertNotIn("Indirekte støtte", rendered)

    def test_empty_source_returns_no_card(self):
        self.assertIsNone(source_decision_core({"Tekst": ""}, "test"))
        self.assertEqual(render_source_decision_core_html({"Tekst": ""}, "test"), "")


if __name__ == "__main__":
    unittest.main()

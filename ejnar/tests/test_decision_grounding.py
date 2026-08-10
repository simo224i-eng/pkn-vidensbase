import unittest

from ejnar.decision_grounding import (
    build_decision_grounding_context,
    extract_decision_grounding,
    inject_grounding_policy,
)


class DecisionGroundingTests(unittest.TestCase):
    def test_board_reasoning_keeps_other_decisive_ground_with_relevant_beam_passage(self):
        document = {
            "Sagsnummer": "102106",
            "Titel": "Nedbrud i bjælke",
            "Tekst": """
## Selskabets opfattelse
Selskabet anfører, at bjælkens bæreevne ikke var væsentligt nedsat ved overtagelsen.

## Nævnets bemærkninger og afgørelse
Nævnet bemærker, at der er konstateret nedbrydning i den bærende bjælke, og at forholdet kan have betydning for bæreevnen.

Det fremgår imidlertid af tilstandsrapporten, at der var anmærket nedbrydning samme sted før købet. Nævnet finder på den baggrund, at selskabet er berettiget til at afvise forholdet med henvisning til tilstandsrapporten.

Klageren får derfor ikke medhold.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertFalse(grounding.used_fallback)
        self.assertIn("Nævnets bemærkninger", grounding.section_title)
        self.assertIn("bæreevnen", grounding.text)
        self.assertIn("tilstandsrapporten", grounding.text)
        self.assertIn("ikke medhold", grounding.text)

    def test_prefers_board_section_over_party_argument(self):
        document = {
            "Tekst": """
## Klagerens opfattelse
Klageren gør gældende, at enhver nedbrydning af en bjælke er en skade.

## Selskabets opfattelse
Selskabet anfører, at bæreevnen ikke er væsentligt nedsat.

## Nævnets vurdering
Nævnet finder, at det ikke er godtgjort, at forholdet var til stede ved overtagelsen. Klageren får derfor ikke medhold.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertIn("Nævnet finder", grounding.text)
        self.assertIn("godtgjort", grounding.text)
        self.assertIn("ikke medhold", grounding.text)
        self.assertNotIn("enhver nedbrydning", grounding.text)

    def test_generic_legacy_section_drops_policy_preamble_before_inline_board_marker(self):
        document = {
            "Tekst": """
## Kendelse
Ved skade forstås brud, lækage og andre fysiske forhold. Undtagelser fra dækning omfatter kendte forhold og almindeligt slid.

Forsikringsbetingelserne indeholder desuden en række bestemmelser om erstatningsopgørelse.

Nævnet udtaler: Nævnet finder, at forholdet med vinduet var klart beskrevet i tilstandsrapporten. Selskabet er derfor berettiget til at afvise forholdet.

Klageren får ikke medhold.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertIn("Nævnet udtaler", grounding.text)
        self.assertIn("tilstandsrapporten", grounding.text)
        self.assertIn("ikke medhold", grounding.text)
        self.assertNotIn("Ved skade forstås", grounding.text)
        self.assertNotIn("Undtagelser fra dækning", grounding.text)
        self.assertNotIn("erstatningsopgørelse", grounding.text)

    def test_inline_marker_can_trim_prefix_inside_same_paragraph(self):
        document = {
            "Tekst": """
## Afgørelse
Forsikringsbetingelserne angiver flere generelle begrænsninger. Nævnet udtaler: Nævnet finder efter de konkrete oplysninger, at klageren ikke har godtgjort forholdets tilstedeværelse ved overtagelsen.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertTrue(grounding.text.startswith("Nævnet udtaler:"))
        self.assertIn("ikke har godtgjort", grounding.text)
        self.assertNotIn("generelle begrænsninger", grounding.text)
        self.assertEqual(grounding.paragraph_count, 1)

    def test_explicit_board_section_preserves_intro_before_find_marker(self):
        document = {
            "Tekst": """
## Nævnets vurdering
Det fremgår af billederne, at bjælken har lokal nedbrydning, men der ses ikke eftergivenhed. Nævnet finder på den baggrund, at bæreevnen ikke er påvirket.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertIn("Det fremgår af billederne", grounding.text)
        self.assertIn("Nævnet finder", grounding.text)
        self.assertIn("bæreevnen ikke er påvirket", grounding.text)

    def test_falls_back_to_final_section_when_no_board_heading_exists(self):
        document = {
            "Tekst": """
## Sagens oplysninger
Der er konstateret fugt.

## Konklusion
Det er ikke sandsynliggjort, at fugten var til stede ved overtagelsen.
""",
        }

        grounding = extract_decision_grounding(document)

        self.assertTrue(grounding.used_fallback)
        self.assertIn("ikke sandsynliggjort", grounding.text)

    def test_context_preserves_source_number_and_explains_purpose(self):
        document = {
            "Sagsnummer": "12345",
            "Titel": "Bjælkesag",
            "Tekst": """
## Nævnets bemærkninger
Nævnet finder, at forholdet var beskrevet i tilstandsrapporten. Klageren får ikke medhold.
""",
        }

        context = build_decision_grounding_context([document])

        self.assertIn("AFGØRELSESKERNE", context)
        self.assertIn("[AFGØRELSESKERNE Kilde 1]", context)
        self.assertIn("tilstandsrapporten", context)

    def test_prompt_policy_requires_decisive_ground_and_party_attribution(self):
        prompt = [
            {
                "type": "text",
                "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
            },
            {"type": "text", "text": "KENDELSER"},
        ]

        grounded = inject_grounding_policy(prompt)
        text = grounded[0]["text"]

        self.assertIn("AFGØRELSESGRUND (OBLIGATORISK)", text)
        self.assertIn("reelt blev afgjort på et andet grundlag", text)
        self.assertIn("klageren, selskabet, en sagkyndig", text)
        self.assertNotEqual(prompt[0]["text"], text)

    def test_prompt_policy_is_idempotent(self):
        prompt = [
            {
                "type": "text",
                "text": "Du er en juridisk assistent.\nREGLER:\n1. Brug kilderne.",
            }
        ]

        once = inject_grounding_policy(prompt)
        twice = inject_grounding_policy(once)

        self.assertEqual(
            once[0]["text"].count("AFGØRELSESGRUND (OBLIGATORISK)"),
            1,
        )
        self.assertEqual(twice, once)


if __name__ == "__main__":
    unittest.main()

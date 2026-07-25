import unittest

from ejnar.metadata_schema import extract_metadata


class MetadataSchemaTests(unittest.TestCase):
    def test_extracts_building_part_cause_and_material(self):
        metadata = extract_metadata(
            "Tagrenden af zink er utæt som følge af sædvanligt slid og udløbet levetid."
        )
        self.assertIn("tagrende", metadata.building_parts)
        self.assertIn("zink", metadata.materials)
        self.assertIn("slid og ælde", metadata.causes)
        self.assertIn("udløbet levetid", metadata.causes)

    def test_extracts_construction_years_without_duplicates(self):
        metadata = extract_metadata(
            "Huset er opført i 1974. Gulvet er ligeledes fra 1974."
        )
        self.assertEqual(metadata.construction_years, (1974,))

    def test_unrelated_dates_are_not_construction_years(self):
        metadata = extract_metadata(
            "Kendelsen blev afsagt i 2024. Ejendommen blev overtaget i 2023."
        )
        self.assertEqual(metadata.construction_years, ())

    def test_extracts_coverage_and_exclusion(self):
        metadata = extract_metadata(
            "Forholdet er ikke dækket, fordi der er tale om manglende vedligeholdelse."
        )
        self.assertIn("ikke dækket", metadata.coverage_outcomes)
        self.assertIn("slid/vedligeholdelse", metadata.exclusions)

    def test_extracts_remedy_and_depreciation(self):
        metadata = extract_metadata(
            "Udbedring sker ved udskiftning. Erstatningen opgøres med afskrivning efter restlevetid."
        )
        self.assertIn("udskiftning", metadata.remedies)
        self.assertIn("afskrivning", metadata.depreciation)
        self.assertIn("restlevetid", metadata.depreciation)

    def test_substrings_do_not_create_false_metadata(self):
        metadata = extract_metadata(
            "Efter overtagelsen træffer rådgiveren en afgørelse, fordi forholdet faldt bort."
        )
        self.assertNotIn("tag", metadata.building_parts)
        self.assertNotIn("træ", metadata.materials)
        self.assertNotIn("råd", metadata.consequences)
        self.assertEqual(metadata.laws, ())

    def test_true_compound_terms_still_match(self):
        metadata = extract_metadata(
            "Tagkonstruktionen har rådskadede trævinduer og flere utætheder."
        )
        self.assertIn("tag", metadata.building_parts)
        self.assertIn("vindue", metadata.building_parts)
        self.assertIn("træ", metadata.materials)
        self.assertIn("råd", metadata.consequences)
        self.assertIn("utæthed", metadata.consequences)

    def test_extracts_only_bounded_law_references(self):
        metadata = extract_metadata(
            "Sagen henviser til FAL og lov nr. 123. Et andet forhold faldt uden for sagen."
        )
        self.assertEqual(
            metadata.laws,
            ("forsikringsaftaleloven", "lov nr. 123"),
        )

    def test_extracts_named_property_consumer_law(self):
        metadata = extract_metadata(
            "Lov om forbrugerbeskyttelse ved erhvervelse af fast ejendom finder anvendelse."
        )
        self.assertEqual(
            metadata.laws,
            ("lov om forbrugerbeskyttelse ved erhvervelse af fast ejendom",),
        )

    def test_unknown_text_returns_empty_fields(self):
        metadata = extract_metadata("Parterne har afgivet bemærkninger.")
        self.assertEqual(metadata.building_parts, ())
        self.assertEqual(metadata.construction_years, ())
        self.assertEqual(metadata.laws, ())


if __name__ == "__main__":
    unittest.main()

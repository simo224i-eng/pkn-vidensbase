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

    def test_extracts_years_without_duplicates(self):
        metadata = extract_metadata("Huset er opført i 1974. Gulvet er ligeledes fra 1974.")
        self.assertEqual(metadata.construction_years, (1974,))

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

    def test_unknown_text_returns_empty_fields(self):
        metadata = extract_metadata("Parterne har afgivet bemærkninger.")
        self.assertEqual(metadata.building_parts, ())
        self.assertEqual(metadata.construction_years, ())


if __name__ == "__main__":
    unittest.main()

"""Auto-detektion af opførelsesår, udfald og mangeltype (porteret 1:1)."""
from __future__ import annotations

from app.core.detect import detect_mangeltyper, detect_opførelsesår, detect_udfald_ejnar


def test_opførelsesår_varianter():
    assert detect_opførelsesår("Huset er opført i 1962 og har fået nyt tag.") == 1962
    assert detect_opførelsesår("Opførelsesår: 1987. Tilbygning fra 1995.") == 1987
    assert detect_opførelsesår("Byggeår: 2004") == 2004
    # NB: "Villaen er fra …" matcher IKKE det porterede mønster ("villaen"
    # falder uden for (?:et|men)?-bøjningerne) — original-adfærd, bevaret 1:1.
    assert detect_opførelsesår("Huset er fra 1926 med originalt murværk.") == 1926
    assert detect_opførelsesår("ejendommen blev opført omkring 1955") == 1955


def test_opførelsesår_ingen_match():
    assert detect_opførelsesår("Der er ingen årstal i denne tekst.") is None
    assert detect_opførelsesår("") is None


def test_udfald_fra_titel():
    assert detect_udfald_ejnar("Klager fik ikke medhold i skimmelsag", "") == "Ikke medhold"
    assert detect_udfald_ejnar("Delvis medhold om tagskade", "") == "Delvis medhold"
    assert detect_udfald_ejnar("Medhold — skjult fugtskade", "") == "Medhold"
    assert detect_udfald_ejnar("Sagen afvist som forældet", "") == "Afvist"


def test_udfald_fra_tekstens_hale():
    tekst = "Lang sagsfremstilling. " * 50 + "Nævnet finder, at klageren får medhold."
    assert detect_udfald_ejnar("Neutral titel", tekst) == "Medhold"
    tekst2 = "Baggrund. " * 50 + "Selskabet frifindes derfor."
    assert detect_udfald_ejnar("Neutral titel", tekst2) == "Ikke medhold"


def test_udfald_ukendt_når_intet_signal():
    assert detect_udfald_ejnar("Neutral titel", "Neutral tekst uden konklusion.") == "Ukendt"


def test_mangeltyper():
    assert "Skimmel/fugt" in detect_mangeltyper("Skimmel i kælderen", "")
    assert "Tag/tagdækning" in detect_mangeltyper("", "utæt tagdækning og defekt undertag")
    assert detect_mangeltyper("Helt ukendt emne", "intet genkendeligt") == ["Andet"]

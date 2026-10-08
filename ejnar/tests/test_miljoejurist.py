"""Tests for Miljøjuristen (screeningstjek)."""
import json

import pytest

from miljoejurist import citatkontrol, dokument, llm_tjek, lovkilder, tjek

SVAG = """Screeningsafgørelse for etablering af solcelleanlæg på 40 ha ved Vestby.
Projektet er omfattet af bilag 2, pkt. 3, litra a. Kommunen har foretaget en screening efter miljøvurderingslovens § 21.
Anlægget placeres på landbrugsjord. Der er ikke kendskab til forekomst af bilag IV-arter i området.
Nærmeste Natura 2000-område ligger ca. 3 km fra projektområdet, og projektet vurderes derfor ikke at påvirke området.
Støj fra invertere forventes ikke at give gener. Anlægget afskærmes med beplantning, som bør etableres.
Samlet vurderes projektet ikke at have væsentlig indvirkning på miljøet. Afgørelsen kan påklages inden 4 uger."""


def test_citat_tåler_mellemrum_og_udeladelser():
    kilde = "Afgørelsen skal begrundes med hovedårsagerne til\nafgørelsen og henvisning til de i bilag 6 opførte relevante kriterier."
    assert citatkontrol.find("Afgørelsen skal begrundes med hovedårsagerne til afgørelsen", kilde)
    assert citatkontrol.find("Afgørelsen skal begrundes […] relevante kriterier", kilde)
    assert not citatkontrol.find("Afgørelsen skal begrundes med de vigtigste årsager", kilde)
    assert not citatkontrol.find("relevante kriterier […] Afgørelsen skal begrundes", kilde)  # forkert rækkefølge


def test_lovopslag_og_henvisninger():
    s = lovkilder.slå_op("mvl", "§ 21")
    assert s and "bilag 6" in s.tekst
    assert lovkilder.slå_op("mvl", "bilag 6")
    refs = lovkilder.find_henvisninger("jf. miljøvurderingslovens § 21, stk. 2, og § 6 i habitatbekendtgørelsen")
    assert ("mvl", "§ 21") in refs and ("habitatbek", "§ 6") in refs


def test_alle_lovuddrag_i_tjeklisten_står_ordret():
    for p in tjek.tjekliste():
        for kode, nr, uddrag in p["lov"]:
            st = lovkilder.slå_op(kode, nr)
            assert st, (p["id"], kode, nr)
            assert citatkontrol.find(uddrag, st.tekst), (p["id"], kode, nr, uddrag)


def test_tjek_finder_svagheder_med_ordrette_citater():
    d = dokument.fra_tekst(SVAG, "svag.txt")
    r = tjek.tjek(d)
    punkter = {s.punkt for s in r.svagheder}
    assert {"D1", "D2", "C3"} <= punkter
    for s in r.svagheder:
        if s.citat_dokument:
            assert s.citat_ok and citatkontrol.find(s.citat_dokument, SVAG)
        assert s.kilder, s.punkt
    assert r.ikke_vurderet


def test_rapporten_frikender_aldrig():
    d = dokument.fra_tekst(SVAG, "svag.txt")
    md = tjek.som_markdown(tjek.tjek(d))
    assert not tjek.FORBUDT.search(md.replace("ikke en juridisk vurdering", ""))


def test_model_citater_kontrolleres_og_opdigtede_fjernes():
    d = dokument.fra_tekst(SVAG, "svag.txt")
    svar = json.dumps({"svagheder": [
        {"punkt": "D2", "svaghed": "Bilag IV ikke undersøgt", "citat": "Der er ikke kendskab til forekomst af bilag IV-arter i området.",
         "hvorfor": "Habitatbekendtgørelsen kræver en vurdering. Afgørelsen er i orden på andre punkter.", "alvor": "høj"},
        {"punkt": "C4", "svaghed": "Støj", "citat": "Støjen er beregnet til 55 dB ved naboen.", "hvorfor": "x", "alvor": "lav"},
    ], "ikke_vurderet": ["Kort"]})
    r = llm_tjek.supplér(tjek.tjek_regler(d), d, None, svar=svar)
    model = [s for s in r.svagheder if s.kilde_lag == "model"]
    assert len(model) == 1 and model[0].punkt == "D2"
    assert "i orden" not in model[0].hvorfor
    assert "fjernet" in r.note


@pytest.mark.parametrize("tekst,forventet", [
    ("Lokalplanen fastlægger anvendelsen af mindre områder på lokalt plan, jf. § 8, stk. 2, og bilag 3. Planforslaget screenes.", "screening_plan"),
    ("Projektet er omfattet af bilag 2, pkt. 10. Screeningsafgørelse efter § 21 under hensyn til bilag 6.", "screening_projekt"),
])
def test_dokumenttype(tekst, forventet):
    assert tjek.dokumenttype(tekst * 3)[0] == forventet


def test_sætninger_deler_ikke_ved_forkortelser():
    s = dokument.sætninger("Det følger af § 21, stk. 2, jf. bilag 6. Næste sætning starter her.")
    assert len(s) == 2

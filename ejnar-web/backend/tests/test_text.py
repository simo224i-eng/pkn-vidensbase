"""Tekstlogik: markdown, HTML-oprensning, chunking, citatvalidering, læsevisning.
Modulet er porteret 1:1 fra ejnar/shared.py — testene låser adfærden fast."""
from __future__ import annotations

from app.core.text import (
    byg_indeks_tekst, byg_lækker_afgørelse, chunk_tekst, citater_for_kilde,
    md_til_html, strip_html, udtræk_kerneafsnit, valider_citationer,
)


# ── md_til_html ───────────────────────────────────────────────────────────────
def test_md_overskrifter_fed_og_lister():
    html = md_til_html("## Vurdering\n\n**Vigtigt:** nævnet fandt *delvist* medhold.\n\n- punkt et\n- punkt to\n\n1. først\n2. dernæst")
    assert "<h2>Vurdering</h2>" in html
    assert "<strong>Vigtigt:</strong>" in html
    assert "<em>delvist</em>" in html
    assert html.count("<li>") == 4 and "<ul>" in html and "<ol>" in html


def test_md_escaper_html():
    html = md_til_html("tekst med <script>alert(1)</script> i")
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_md_vandret_linje_og_afsnit():
    html = md_til_html("afsnit et\n\n---\n\nafsnit to")
    assert "<hr>" in html and html.count("<p>") == 2


def test_md_bevarer_kilde_tokens():
    assert "[Kilde 3]" in md_til_html("Se dommen [Kilde 3].")


# ── strip_html ────────────────────────────────────────────────────────────────
def test_strip_html_entities():
    assert strip_html("s&aelig;lger p&aring; &sect; 2") == "sælger på § 2"


def test_strip_html_preserve_headings():
    ud = strip_html("<h2>Klagen</h2><p>Selve klagen.</p><h3>Bilag</h3>", preserve_headings=True)
    assert "## Klagen" in ud and "### Bilag" in ud and "Selve klagen." in ud


def test_strip_html_fed_paragraf_bliver_underoverskrift():
    ud = strip_html("<p><strong>Nævnets vurdering</strong></p><p>tekst</p>", preserve_headings=True)
    assert "#### Nævnets vurdering" in ud


# ── chunking / kerneafsnit ────────────────────────────────────────────────────
def test_chunk_tekst_kort_tekst_er_ét_chunk():
    assert chunk_tekst("kort tekst her", titel="Sag") == ["Sag\nkort tekst her"]


def test_chunk_tekst_overlap():
    ord_liste = [f"ord{i}" for i in range(1000)]
    chunks = chunk_tekst(" ".join(ord_liste), chunk_size=300, overlap=50)
    assert len(chunks) == 4
    # Overlap: slutningen af chunk 1 går igen i starten af chunk 2
    assert "ord299" in chunks[0] and "ord250" in chunks[1]


def test_udtræk_kerneafsnit_prioriterer_afgørelsen():
    tekst = ("## Sagens oplysninger\nLang neutral baggrund.\n"
             "## Klagen\nKlageren kræver dækning.\n"
             "## Nævnets bemærkninger og afgørelse\nNævnet giver medhold.\n")
    kerne = udtræk_kerneafsnit(tekst, max_tegn=500)
    assert "Nævnet giver medhold" in kerne and "Klageren kræver dækning" in kerne
    assert "Lang neutral baggrund" not in kerne


def test_byg_indeks_tekst_booster_titel():
    ud = byg_indeks_tekst("Skimmel i tag", "## Klagen\nIndhold")
    assert ud.count("Skimmel i tag") == 3


# ── citatvalidering ───────────────────────────────────────────────────────────
_KILDE = {"Tekst": "Nævnet udtalte, at skjult skimmelsvamp i tagkonstruktionen dækkes af forsikringen, "
                   "når skaden ikke var synlig ved overtagelsen."}


def test_ægte_citat_er_ikke_suspekt():
    svar = 'Nævnet fandt: "skjult skimmelsvamp i tagkonstruktionen dækkes af forsikringen" [Kilde 1]'
    assert valider_citationer(svar, [_KILDE]) == []


def test_fabrikeret_citat_fanges():
    svar = 'Nævnet skrev: "dette citat findes ikke i nogen kilde overhovedet her" [Kilde 1]'
    suspekte = valider_citationer(svar, [_KILDE])
    assert suspekte == ["dette citat findes ikke i nogen kilde overhovedet her"]


def test_danske_citationstegn_valideres_også():
    svar = "Nævnet fandt: »skjult skimmelsvamp i tagkonstruktionen dækkes af forsikringen« [Kilde 1]"
    assert valider_citationer(svar, [_KILDE]) == []


def test_citater_for_kilde_matcher_kun_rigtig_kilde():
    svar = 'Se: "skjult skimmelsvamp i tagkonstruktionen dækkes af forsikringen".'
    assert citater_for_kilde(svar, _KILDE) != []
    assert citater_for_kilde(svar, {"Tekst": "Helt anden tekst om kloakrør."}) == []


# ── læsevisning ───────────────────────────────────────────────────────────────
def test_byg_lækker_afgørelse_toc_og_ankre():
    tekst = "## Klagen\nFørste afsnit.\n## Afgørelse\nAndet afsnit."
    toc, body = byg_lækker_afgørelse(tekst, anchor_prefix="t")
    assert 'href="#t-1"' in toc and 'href="#t-2"' in toc
    assert 'id="t-1"' in body and 'id="t-2"' in body
    assert "Første afsnit." in body


def test_byg_lækker_afgørelse_fremhæver_citat():
    tekst = "## Afgørelse\nNævnet fandt at skimmelsvampen var skjult ved overtagelsen af huset."
    _, body = byg_lækker_afgørelse(tekst, highlight_quotes=["skimmelsvampen var skjult ved overtagelsen"])
    assert "<mark" in body


def test_byg_lækker_afgørelse_uden_overskrifter():
    toc, body = byg_lækker_afgørelse("Bare løbende tekst uden sektioner.")
    assert toc == "" and "Bare løbende tekst" in body

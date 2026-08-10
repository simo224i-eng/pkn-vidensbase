"""RAG-limlaget: prompt-bygning, rerank-parsing, historik-kilder, retrieval.
Alle Haiku-kald er patched (conftest) — flowet skal fungere deterministisk
når LLM-boosts fejler, præcis som i produktion ved API-nedbrud."""
from __future__ import annotations

import app.core.rag as rag
from app.core.rag import (
    _hist_kilder, byg_prompt, klassificer_query, llm_rerank, smart_retrieval,
)

_DOCS = [
    {"Dato": "2021-05-04", "Titel": "Skimmelsag", "Tekst": "## Klagen\nSkimmel i badeværelset."},
    {"Dato": "2019-08-21", "Titel": "Tagsag", "Tekst": "## Klagen\nUtæt tag over køkkenet."},
]


def test_byg_prompt_struktur():
    blokke = byg_prompt("Hvornår dækkes skimmel?", _DOCS)
    assert len(blokke) == 3
    assert "KILDEREGISTER" in blokke[0]["text"]
    assert "[Kilde 1] = 04.05.2021 – Skimmelsag" in blokke[0]["text"]
    assert blokke[1]["cache_control"] == {"type": "ephemeral"}
    assert "SPØRGSMÅL: Hvornår dækkes skimmel?" in blokke[2]["text"]


def test_byg_prompt_medtager_seneste_assistent_svar():
    # Regression for [:-1]-fejlen: web-frontenden sender kun AFSLUTTEDE ture
    # (spørgsmålet er separat), så hele historikken skal med — især det
    # seneste assistent-svar, som et opfølgningsspørgsmål typisk peger på.
    historik = [
        {"rolle": "bruger", "tekst": "Hvornår dækkes skimmel?"},
        {"rolle": "assistent", "tekst": "Skjult skimmel dækkes som udgangspunkt."},
    ]
    blokke = byg_prompt("Gælder det også synlig skimmel?", _DOCS, historik)
    samtale = blokke[2]["text"]
    assert "TIDLIGERE SAMTALE" in samtale
    assert "Bruger: Hvornår dækkes skimmel?" in samtale
    assert "Assistent: Skjult skimmel dækkes som udgangspunkt." in samtale


def test_byg_prompt_uden_historik_har_ingen_samtaleblok():
    blokke = byg_prompt("Spørgsmål", _DOCS, [])
    assert "TIDLIGERE SAMTALE" not in blokke[2]["text"]


def test_byg_prompt_overlever_kilde_uden_dato():
    # Regression (fundet af testkorpusset): én NaT-dato blandt kilderne
    # væltede hele prompt-bygningen med "NaTType does not support strftime".
    import pandas as pd
    docs = [{"Dato": pd.NaT, "Titel": "Datoløs sag", "Tekst": "## Klagen\nSkimmel."}] + _DOCS
    blokke = byg_prompt("Dækkes skimmel?", docs)
    assert "ukendt dato – Datoløs sag" in blokke[0]["text"]


# ── llm_rerank ────────────────────────────────────────────────────────────────
def _kandidater(n):
    return [{"Dato": "2020-01-01", "Titel": f"Sag {i}", "Tekst": f"tekst {i}", "Link": f"L{i}"}
            for i in range(n)]


def test_rerank_følger_haikus_rækkefølge_og_fylder_op(monkeypatch):
    monkeypatch.setattr(rag, "llm_haiku", lambda *a, **k: "3, 1")
    ud = llm_rerank("q", _kandidater(5), top_n=3)
    assert [k["Titel"] for k in ud] == ["Sag 3", "Sag 1", "Sag 0"]


def test_rerank_ignorerer_ugyldige_og_duplikerede_indekser(monkeypatch):
    monkeypatch.setattr(rag, "llm_haiku", lambda *a, **k: "7, 2, 2, 0")
    ud = llm_rerank("q", _kandidater(4), top_n=3)
    assert [k["Titel"] for k in ud] == ["Sag 2", "Sag 0", "Sag 1"]


def test_rerank_fallback_ved_tomt_haiku_svar():
    # conftest patcher llm_haiku til "" — fallback er de første top_n
    ud = llm_rerank("q", _kandidater(6), top_n=4)
    assert [k["Titel"] for k in ud] == ["Sag 0", "Sag 1", "Sag 2", "Sag 3"]


def test_rerank_springer_llm_over_ved_få_kandidater():
    ud = llm_rerank("q", _kandidater(3), top_n=8)
    assert len(ud) == 3


# ── historik-kilder ───────────────────────────────────────────────────────────
def test_hist_kilder_dedup_og_rækkefølge():
    historik = [
        {"rolle": "bruger", "tekst": "x"},
        {"rolle": "assistent", "tekst": "y", "kilder": [{"Link": "A"}, {"Link": "B"}]},
        {"rolle": "bruger", "tekst": "z"},
        {"rolle": "assistent", "tekst": "w", "kilder": [{"Link": "B"}, {"Link": "C"}]},
    ]
    seen = {"A"}
    ud = _hist_kilder(historik, seen)
    # Nyeste svar først, allerede sete links springes over
    assert [k["Link"] for k in ud] == ["B", "C"]


def test_hist_kilder_respekterer_max():
    historik = [{"rolle": "assistent", "tekst": "s",
                 "kilder": [{"Link": f"L{i}"} for i in range(20)]}]
    assert len(_hist_kilder(historik, set(), max_n=5)) == 5


# ── klassifikation + retrieval ────────────────────────────────────────────────
def test_klassificer_query_default_når_haiku_fejler():
    assert klassificer_query("Hvornår dækkes skimmelsvamp i kælderen?") == {
        "type": "åben", "top_retrieve": 40, "top_final": 8}


def test_smart_retrieval_ende_til_ende_uden_llm(store):
    sub_idx = list(range(len(store.df)))
    standalone, kilder, af_info = smart_retrieval(
        "skjult skimmelsvamp i badeværelset", store.df, store.vec, store.mat,
        sub_idx, historik=[], filter_options={"Mangeltype": store.mangeltyper})
    assert standalone == "skjult skimmelsvamp i badeværelset"
    assert kilder and kilder[0]["Titel"] == "Skjult skimmelsvamp i badeværelse"
    assert all("Tekst" in k for k in kilder)  # interne kilder er FULDE rækker
    assert af_info["applied"] is False and af_info["suggested"] == {}


def test_smart_retrieval_intet_match_giver_tom_liste(store):
    sub_idx = list(range(len(store.df)))
    _, kilder, _ = smart_retrieval(
        "kvantemekanik zzyzx", store.df, store.vec, store.mat, sub_idx, [], None)
    assert kilder == []

"""Semantik-laget (sovende i v1): loader, chunk-søgning, RRF-hybrid, rerank-
opgradering og semantisk kontekst-udvalg — alt testet offline med fakes.
Vigtigst af alt: ALT skal degradere stille til keyword-adfærd uden nøgle."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import app.core.rag as rag
import app.core.semantic as semantic
from app.core.semantic import (
    chunk_span_tekst, embedding_soeg, hybrid_retrieval, load_chunk_embeds,
    semantisk_chunk_udvalg,
)


@pytest.fixture(autouse=True)
def _tom_memo():
    semantic._QV_MEMO.clear()
    yield


def _norm(v):
    v = np.asarray(v, dtype=np.float32)
    return v / np.linalg.norm(v)


# ── Loader (link-baseret remapping) ───────────────────────────────────────────
def _skriv_npz(tmp_path, doc_links, chunk_to_doc, n_chunks, sidecar=True):
    d = tmp_path / "embeds"
    d.mkdir(exist_ok=True)
    sti = d / "test__voyage__voyage-3-large__3d_5c.npz"
    vecs = np.random.default_rng(1).random((n_chunks, 4)).astype(np.float16)
    hoved = {"embeddings": vecs, "chunk_to_doc": np.array(chunk_to_doc, dtype=np.int64)}
    if sidecar:
        np.savez(sti, **hoved)
        np.savez(str(sti)[:-4] + "__links.npz", doc_links=np.array(doc_links, dtype=object))
    else:
        np.savez(sti, **hoved, doc_links=np.array(doc_links, dtype=object))
    return sti


def _df(links):
    return pd.DataFrame({"Link": links, "Titel": [f"T{i}" for i in range(len(links))]})


def test_loader_remapper_via_links(tmp_path):
    # Build'ets doc-rækkefølge er en ANDEN end appens df — links er nøglen.
    df = _df(["L0", "L1", "L2", "L3"])
    _skriv_npz(tmp_path, doc_links=["L2", "L0", "L_væk"], chunk_to_doc=[0, 0, 1, 2, 2], n_chunks=5)
    e = load_chunk_embeds(df, str(tmp_path))
    assert e is not None
    # Chunks for det forsvundne link er droppet; resten peger på df-positioner
    assert list(e["chunk_to_doc"]) == [2, 2, 0]
    assert e["vectors"].dtype == np.float32  # float16 → float32
    assert e["dækning"] == (2, 4)


def test_loader_uden_sidecar_bruger_indlejrede_links(tmp_path):
    df = _df(["L0", "L1", "L2"])
    _skriv_npz(tmp_path, doc_links=["L1", "L2", "L0"], chunk_to_doc=[0, 1, 2, 2, 1],
               n_chunks=5, sidecar=False)
    e = load_chunk_embeds(df, str(tmp_path))
    assert e is not None and len(e["chunk_to_doc"]) == 5


def test_loader_kasserer_forældet_indeks(tmp_path):
    # Kun 1 af 4 links matcher → dækning under halvdelen → None
    df = _df(["A", "B", "C", "D"])
    _skriv_npz(tmp_path, doc_links=["A", "x", "y"], chunk_to_doc=[0, 1, 2, 1, 0], n_chunks=5)
    assert load_chunk_embeds(df, str(tmp_path)) is None


def test_loader_ingen_filer(tmp_path):
    assert load_chunk_embeds(_df(["A"]), str(tmp_path)) is None


# ── Chunk-søgning ─────────────────────────────────────────────────────────────
def _fake_embeds():
    # 4 chunks: doc0 har [1,0], [0.9,0.1]; doc1 har [0,1]; doc2 har [0.5,0.5]
    return {
        "vectors": np.array([_norm([1, 0]), _norm([0.9, 0.1]),
                             _norm([0, 1]), _norm([0.5, 0.5])], dtype=np.float32),
        "chunk_to_doc": np.array([0, 0, 1, 2], dtype=np.int32),
    }


def test_embedding_soeg_max_chunkscore_pr_doc(monkeypatch, store):
    monkeypatch.setattr(semantic, "hyde_embed", lambda q: _norm([1, 0]))
    hits = embedding_soeg("q", store.df, _fake_embeds())
    docs = [d for d, _ in hits]
    assert docs[0] == 0                # bedste chunk-match
    assert 2 in docs and 1 not in docs # doc1 ([0,1]·[1,0]=0) er under 0.15-tærsklen
    assert hits[0][1] > hits[-1][1]


def test_embedding_soeg_respekterer_sub_idx(monkeypatch, store):
    monkeypatch.setattr(semantic, "hyde_embed", lambda q: _norm([1, 0]))
    hits = embedding_soeg("q", store.df, _fake_embeds(), sub_idx=[1, 2])
    assert [d for d, _ in hits] == [2]  # doc0 filtreret væk; doc1 under tærsklen


def test_embedding_soeg_uden_nøgle_giver_tom_liste(store):
    # Ingen VOYAGE_API_KEY i tests → embed-kald returnerer None → [] (stille)
    assert embedding_soeg("q", store.df, _fake_embeds()) == []


# ── Hybrid RRF ────────────────────────────────────────────────────────────────
def test_hybrid_fusionerer_tfidf_og_semantik(monkeypatch, store):
    sub = list(range(len(store.df)))
    ren_tfidf = hybrid_retrieval("skimmelsvamp badeværelse", store.df, store.vec,
                                 store.mat, embeds=None, sub_idx=sub)
    # Semantikken insisterer på doc 5 (kloak-sagen — deler ingen ord med query)
    monkeypatch.setattr(semantic, "embedding_soeg",
                        lambda *a, **k: [(4, 0.9), (ren_tfidf[0], 0.8)])
    fusion = hybrid_retrieval("skimmelsvamp badeværelse", store.df, store.vec,
                              store.mat, embeds=_fake_embeds(), sub_idx=sub)
    assert ren_tfidf[0] == fusion[0]      # enighed om topdok → stadig øverst
    assert 4 in fusion                    # semantisk-only dok kom med i fusionen
    assert 4 not in ren_tfidf


def test_hybrid_uden_embeds_er_ren_tfidf(store):
    sub = list(range(len(store.df)))
    idxs = hybrid_retrieval("skjult skimmelsvamp badeværelse", store.df, store.vec,
                            store.mat, embeds=None, sub_idx=sub)
    assert idxs and store.df.iloc[idxs[0]]["Sagsnummer"] == "100001"


# ── Rerank-opgradering ────────────────────────────────────────────────────────
def test_llm_rerank_bruger_voyage_når_muligt(monkeypatch):
    kandidater = [{"Dato": "2020-01-01", "Titel": f"Sag {i}", "Tekst": f"t{i}"} for i in range(5)]
    monkeypatch.setattr(semantic, "voyage_rerank",
                        lambda q, docs, top_n: [(3, 0.95), (0, 0.60)])
    ud = rag.llm_rerank("q", kandidater, top_n=2)
    assert [k["Titel"] for k in ud] == ["Sag 3", "Sag 0"]


def test_llm_rerank_falder_tilbage_til_haiku_uden_voyage(monkeypatch):
    kandidater = [{"Dato": "2020-01-01", "Titel": f"Sag {i}", "Tekst": f"t{i}"} for i in range(5)]
    monkeypatch.setattr(semantic, "voyage_rerank", lambda *a, **k: None)
    monkeypatch.setattr(rag, "llm_haiku", lambda *a, **k: "2, 4")
    ud = rag.llm_rerank("q", kandidater, top_n=2)
    assert [k["Titel"] for k in ud] == ["Sag 2", "Sag 4"]


# ── Semantisk kontekst-udvalg ─────────────────────────────────────────────────
def test_chunk_span_geometri():
    ord_liste = [f"o{i}" for i in range(2000)]
    tekst = " ".join(ord_liste)
    s0, s1 = chunk_span_tekst(tekst, 0), chunk_span_tekst(tekst, 1)
    assert s0.startswith("o0 ") and s0.endswith(" o769")   # 770 ord
    assert s1.startswith("o655")                           # stride 655
    assert chunk_span_tekst("kort tekst", 3) == "kort tekst"


def test_semantisk_chunk_udvalg(monkeypatch, store):
    monkeypatch.setattr(semantic, "embed_query_memo", lambda q: _norm([1, 0]))
    docs = [store.df.iloc[0].to_dict()]
    link_til_idx = {str(store.df.iloc[0]["Link"]): 0}
    ud = semantisk_chunk_udvalg("q", docs, _fake_embeds(), link_til_idx)
    assert 0 in ud and ud[0].strip()      # valgte chunks for kilde 1


def test_semantisk_chunk_udvalg_uden_nøgle_er_tomt(store):
    docs = [store.df.iloc[0].to_dict()]
    assert semantisk_chunk_udvalg("q", docs, _fake_embeds(),
                                  {str(store.df.iloc[0]["Link"]): 0}) == {}


# ── Dansk synonym-udvidelse ───────────────────────────────────────────────────
def test_udvid_query_dansk_tilføjer_fagtermer():
    from app.core.synonymer import udvid_query_dansk
    ud = udvid_query_dansk("Mug i kælderen")
    assert "skimmel" in ud and ud.startswith("Mug i kælderen")
    ud2 = udvid_query_dansk("dækkes MgO-plader?")
    assert "magnesiumoxid" in ud2


def test_udvid_query_dansk_uændret_uden_match():
    from app.core.synonymer import udvid_query_dansk
    q = "Hvad er selskabets frist for genoptagelse?"
    assert udvid_query_dansk(q) == q
    assert udvid_query_dansk("") == ""


def test_udvid_query_dansk_ingen_dubletter_og_ordgrænser():
    from app.core.synonymer import udvid_query_dansk
    # "skimmelsvamp" i query må ikke tilføjes igen af "skimmel"-nøglen …
    ud = udvid_query_dansk("skimmel og skimmelsvamp")
    assert ud.lower().split().count("skimmelsvamp") == 1
    # … og "eltavle" må ikke trigge "el"-nøglen (ordgrænse)
    assert udvid_query_dansk("fejl i eltavlen") == "fejl i eltavlen"


def test_udvid_query_dansk_hjælper_søgningen(store):
    # Hverdagssprog ("mug") rammer nu skimmel-kendelserne i det rigtige indeks
    from app.core.synonymer import udvid_query_dansk
    from app.core.search import tfidf_søg
    rå = tfidf_søg("mug bag væggen i stuen", store.df, store.vec, store.mat, top_n=5)
    udvidet = tfidf_søg(udvid_query_dansk("mug bag væggen i stuen"),
                        store.df, store.vec, store.mat, top_n=5)
    rå_titler = set(rå["Titel"]) if len(rå) else set()
    ud_titler = set(udvidet["Titel"]) if len(udvidet) else set()
    assert "Skimmel bag vægbeklædning" in ud_titler
    assert len(ud_titler) >= len(rå_titler)


# ── Ende-til-ende: smart_retrieval med semantik ──────────────────────────────
def test_smart_retrieval_hybrid_sti(monkeypatch, store):
    # Semantikken skyder kloak-sagen (idx 4) ind — keyword-only ville aldrig
    # finde den for et skimmel-spørgsmål.
    monkeypatch.setattr(semantic, "embedding_soeg", lambda *a, **k: [(4, 0.9)])
    sub = list(range(len(store.df)))
    _, kilder, _ = smart_ret = rag.smart_retrieval(
        "skjult skimmelsvamp i badeværelset", store.df, store.vec, store.mat,
        sub, [], None, embeds=_fake_embeds())
    titler = [k["Titel"] for k in kilder]
    assert "Kloakproblemer og rotter" in titler
    assert any("skimmelsvamp" in t.lower() for t in titler)

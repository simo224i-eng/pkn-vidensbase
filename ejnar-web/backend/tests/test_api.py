"""API-kontrakter gennem TestClient: søgning, detalje, stats, SSE-chat,
notat og kilde-citat — inkl. regressionstests for kilde-formfejlen
(kapitaliserede nøgler mod browseren) og SSE-kontrakten (altid done/error)."""
from __future__ import annotations

import json

import app.main as main
from app.core.claude import LLMFejl


def _sse_events(text: str) -> list[dict]:
    ud = []
    for blok in text.split("\n\n"):
        blok = blok.strip()
        if blok.startswith("data: "):
            ud.append(json.loads(blok[len("data: "):]))
    return ud


def _fake_stream(chunks, captured=None, exc=None):
    """Generator-fabrik der efterligner stream_claude."""
    def fake(prompt, max_tokens=3000, model=None):
        if captured is not None:
            captured["prompt"] = prompt
        yield from chunks
        if exc is not None:
            raise exc
    return fake


# ── basis ─────────────────────────────────────────────────────────────────────
def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_filters(client):
    d = client.get("/api/filters").json()
    assert d["år_min"] == 2016 and d["år_max"] == 2024
    assert d["opførelsesår_min"] == 1926 and d["opførelsesår_max"] == 1974
    assert "Skimmel/fugt" in d["mangeltyper"]


# ── kendelser (liste/søgning) ─────────────────────────────────────────────────
def test_kendelser_default_sorteret_nyeste_først(client):
    d = client.get("/api/kendelser").json()
    assert d["total"] == 10
    assert d["items"][0]["id"] == "100010"
    # Kendelse-formen mod browseren: små nøgler, ingen tung tekst
    assert "titel" in d["items"][0] and "Tekst" not in d["items"][0]


def test_kendelser_ordret_søgning(client):
    d = client.get("/api/kendelser", params={"q": "skimmelsvamp", "søgetype": "ordret"}).json()
    assert {i["id"] for i in d["items"]} == {"100001", "100002", "100007", "100010"}


def test_kendelser_intelligent_søgning(client):
    d = client.get("/api/kendelser",
                   params={"q": "skjult skimmelsvamp badeværelse", "søgetype": "intelligent"}).json()
    assert d["items"][0]["id"] == "100001"


def test_kendelser_paginering(client):
    d = client.get("/api/kendelser", params={"page": 2, "page_size": 3}).json()
    assert [i["id"] for i in d["items"]] == ["100001", "100002", "100003"]


def test_kendelser_årfilter_med_datoløs_række(client):
    # Regression: rækken med NaT-dato må ikke vælte år-filteret (pandas 2.x
    # rejser ved NA i boolske masker) — den skal blot ekskluderes.
    d = client.get("/api/kendelser", params={"år_min": 2000, "år_max": 2030}).json()
    assert d["total"] == 9


def test_kendelse_detalje(client):
    d = client.get("/api/kendelser/100001").json()
    assert d["titel"] == "Skjult skimmelsvamp i badeværelse"
    assert d["opførelsesår"] == 1962
    assert "rd-toc" in d["toc_html"] and "Klagen" in d["body_html"]


def test_kendelse_detalje_ukendt_id(client):
    assert client.get("/api/kendelser/999999").status_code == 404


# ── statistik ─────────────────────────────────────────────────────────────────
def test_stats(client):
    d = client.get("/api/stats").json()
    assert d["total"] == 10
    assert d["medhold_pct"] == 60.0  # 4×Medhold + 2×Delvis af 10
    assert d["år_span"] == "2016–2024"
    assert len(d["per_år"]) == 9
    mt = {r["mangeltype"]: r["antal"] for r in d["top_mangeltyper"]}
    assert mt["Skimmel/fugt"] == 4


def test_stats_tomt_filter_giver_nulsvar(client):
    d = client.get("/api/stats", params={"selskab": "Findes Ikke A/S"}).json()
    assert d["total"] == 0 and d["per_år"] == []


# ── AI-assistent (SSE) ────────────────────────────────────────────────────────
def test_ask_streamer_kilder_deltaer_og_done(client, monkeypatch):
    ægte_citat = "skjult skimmelsvamp i tagkonstruktionen dækkes af ejerskifteforsikringen"
    chunks = ["Nævnet fandt at ", f'"{ægte_citat}" ', "[Kilde 1]."]
    monkeypatch.setattr(main, "stream_claude", _fake_stream(chunks))

    r = client.post("/api/ask", json={"spørgsmål": "Dækkes skjult skimmelsvamp?", "historik": [], "filtre": {}})
    ev = _sse_events(r.text)

    assert ev[0]["type"] == "kilder" and ev[0]["kilder"]
    kilde = ev[0]["kilder"][0]
    # Regression: kilder mod browseren SKAL være i slank Kendelse-form
    assert "titel" in kilde and "id" in kilde
    assert "Titel" not in kilde and "Tekst" not in kilde

    deltas = [e["text"] for e in ev if e["type"] == "delta"]
    done = [e for e in ev if e["type"] == "done"]
    assert deltas == chunks and len(done) == 1
    assert done[0]["text"] == "".join(chunks)
    assert done[0]["suspekte"] == []  # citatet findes ordret i kilden


def test_ask_fanger_fabrikeret_citat(client, monkeypatch):
    chunks = ['Nævnet skrev: "dette citat er helt og aldeles opdigtet af modellen" [Kilde 1].']
    monkeypatch.setattr(main, "stream_claude", _fake_stream(chunks))
    r = client.post("/api/ask", json={"spørgsmål": "Dækkes skimmel?", "historik": [], "filtre": {}})
    done = [e for e in _sse_events(r.text) if e["type"] == "done"][0]
    assert done["suspekte"] == ["dette citat er helt og aldeles opdigtet af modellen"]


def test_ask_prompt_medtager_seneste_assistent_svar(client, monkeypatch, store):
    # Ende-til-ende-regression for [:-1]-fejlen + rehydrering af slanke kilder.
    captured: dict = {}
    monkeypatch.setattr(main, "stream_claude", _fake_stream(["ok"], captured=captured))
    historik = [
        {"rolle": "bruger", "tekst": "Hvad gælder for skimmelsvamp?"},
        {"rolle": "assistent", "tekst": "Skjult skimmelsvamp dækkes som udgangspunkt.",
         "kilder": [{"link": str(store.df.iloc[1]["Link"]), "titel": "slank kilde fra browseren"}]},
    ]
    client.post("/api/ask", json={"spørgsmål": "Også i kælderen?", "historik": historik, "filtre": {}})
    samtale = captured["prompt"][2]["text"]
    assert "Bruger: Hvad gælder for skimmelsvamp?" in samtale
    assert "Assistent: Skjult skimmelsvamp dækkes som udgangspunkt." in samtale


def test_ask_llmfejl_giver_error_event(client, monkeypatch):
    monkeypatch.setattr(main, "stream_claude",
                        _fake_stream(["halvt svar "], exc=LLMFejl("forbindelsen røg")))
    r = client.post("/api/ask", json={"spørgsmål": "Dækkes skimmel?", "historik": [], "filtre": {}})
    ev = _sse_events(r.text)
    assert any(e["type"] == "error" and "forbindelsen røg" in e["message"] for e in ev)
    assert not any(e["type"] == "done" for e in ev)


def test_ask_uventet_fejl_giver_stadig_error_event(client, monkeypatch):
    # SSE-kontrakt: klienten skal ALTID få done eller error — også ved
    # ikke-LLMFejl-undtagelser midt i streamen.
    monkeypatch.setattr(main, "stream_claude",
                        _fake_stream(["chunk "], exc=ValueError("noget uventet")))
    r = client.post("/api/ask", json={"spørgsmål": "Dækkes skimmel?", "historik": [], "filtre": {}})
    ev = _sse_events(r.text)
    assert any(e["type"] == "error" for e in ev)
    assert not any(e["type"] == "done" for e in ev)


def test_ask_retrievalfejl_giver_error_event(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("indeks væk")
    monkeypatch.setattr(main, "smart_retrieval", boom)
    r = client.post("/api/ask", json={"spørgsmål": "x?", "historik": [], "filtre": {}})
    ev = _sse_events(r.text)
    assert len(ev) == 1 and ev[0]["type"] == "error" and "Søgning fejlede" in ev[0]["message"]


def test_ask_kræver_spørgsmål(client):
    assert client.post("/api/ask", json={"historik": []}).status_code == 422


# ── rehydrering (notat + intern hjælper) ──────────────────────────────────────
def test_rehydrate_kilder_direkte(store):
    slank = [{"link": str(store.df.iloc[1]["Link"]), "titel": "fra browseren"}]
    fuld = main._rehydrate_kilder(store, slank)
    assert fuld[0]["Titel"] == store.df.iloc[1]["Titel"] and "Tekst" in fuld[0]
    # Ukendt link beholdes as-is (best effort)
    stale = [{"link": "https://x/forsvundet"}]
    assert main._rehydrate_kilder(store, stale) == stale


def test_notat_rehydrerer_slanke_kilder(client, store):
    r = client.post("/api/notat", json={
        "spørgsmål": "Dækkes skimmel?",
        "svar": "Ja, se [Kilde 1].",
        "kilder": [{"link": str(store.df.iloc[0]["Link"]), "titel": "slank"}],
    })
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    # Regression: notatet skal vise kildens RIGTIGE titel/sagsnr — ikke tomme
    # felter fra den slanke browserform.
    assert "Skjult skimmelsvamp i badeværelse" in r.text
    assert "100001" in r.text


# ── kilde-citat ───────────────────────────────────────────────────────────────
def test_kilde_citat_finder_og_fremhæver(client):
    svar = ('Nævnet udtalte: "skjult skimmelsvamp i tagkonstruktionen dækkes af '
            'ejerskifteforsikringen" [Kilde 1].')
    r = client.post("/api/kilde-citat", json={"kendelse_id": "100001", "svar": svar})
    d = r.json()
    assert d["quotes"] and "<mark" in d["body_html"]


def test_kilde_citat_ukendt_id(client):
    assert client.post("/api/kilde-citat",
                       json={"kendelse_id": "999999", "svar": "x"}).status_code == 404


def test_kilde_citat_tom_id_giver_404(client):
    # Regression: tom id matchede tidligere første række via Link.endswith("")
    assert client.post("/api/kilde-citat",
                       json={"kendelse_id": "", "svar": "x"}).status_code == 404


def test_kilde_citat_kræver_kendelse_id(client):
    assert client.post("/api/kilde-citat", json={"svar": "x"}).status_code == 422

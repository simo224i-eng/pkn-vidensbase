"""Fælles test-opsætning.

Principper:
- INTET netværk: llm_haiku er patched til "" (alle Haiku-boosts falder tilbage
  til deterministisk adfærd), og requests.post/get rejser AssertionError hvis
  noget alligevel forsøger.
- INGEN rigtig data: et lille syntetisk datalager (10 kendelser, ægte TF-IDF-
  indeks bygget på millisekunder) erstatter det ~90 sek tunge rigtige build.
- Kendte settings: env sættes FØR app.config importeres (Settings læser env
  ved import), og pr.-test-overrides sker som instans-attributter på
  get_settings()-singletonen via monkeypatch (ryddes op automatisk).
"""
from __future__ import annotations

import os
import sys

# Skal ske FØR app.* importeres — Settings læser env ved klasse-definition,
# og en evt. lokal .env må ikke lække ind i testene (_load_dotenv bruger
# setdefault, så eksplicitte værdier her vinder).
os.environ["APP_PASSWORD"] = ""
os.environ["SESSION_SECRET"] = "test-hemmelighed-til-suiten"
os.environ["EJNAR_WARMUP"] = "0"
os.environ["COOKIE_SECURE"] = "0"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.main as main  # noqa: E402
from app import auth  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.core.data import Store  # noqa: E402
from app.core.search import byg_tfidf_index  # noqa: E402


def _doc(sagsnr: str, dato: str, titel: str, brød: str, udfald: str,
         mangeltype: list[str], selskab: str, opført=None) -> dict:
    tekst = (
        "## Klagen\n"
        f"Klageren har tegnet ejerskifteforsikring hos selskabet. {brød}\n"
        "## Sagens oplysninger\n"
        "Ejendommen blev besigtiget af bygningssagkyndig før overtagelsen.\n"
        "## Nævnets bemærkninger og afgørelse\n"
        f"Nævnet har vurderet sagen. Udfaldet blev: {udfald.lower()} til klageren.\n"
    )
    return {
        "Dato": dato, "Titel": titel, "Link": f"https://ankeforsikring.dk/kendelser/{sagsnr}",
        "Tekst": tekst, "Excerpt": brød[:120], "Sagsnummer": sagsnr, "Selskab": selskab,
        "Udfald": udfald, "Mangeltype": mangeltype, "Forsikringstype": "Ejerskifteforsikring",
        "_opført": opført,
    }


# Ordforråd er bevidst overlappende på tværs af dokumenter — byg_tfidf_index
# bruger min_df=2, så ord der kun findes i ét dokument ryger ud af vokabularet.
_DOCS = [
    _doc("100001", "2021-05-04", "Skjult skimmelsvamp i badeværelse",
         "Der er konstateret skimmelsvamp og fugt i badeværelset. Nævnet fandt, at skjult "
         "skimmelsvamp i tagkonstruktionen dækkes af ejerskifteforsikringen. Huset er opført i 1962.",
         "Medhold", ["Skimmel/fugt"], "Tryg", opført=1962),
    _doc("100002", "2020-03-12", "Skimmel og fugt i kælder",
         "Klagen vedrører skimmelsvamp og fugt i kælderen efter overtagelsen. Selskabet afviste "
         "dækning med henvisning til tilstandsrapporten.",
         "Ikke medhold", ["Skimmel/fugt"], "Alm. Brand"),
    _doc("100003", "2019-08-21", "Utæt tag efter storm",
         "Taget er utæt, og der trænger vand ind ved tagkonstruktionen. Villaen er fra 1926 og "
         "taget har begrænset restlevetid.",
         "Delvis medhold", ["Tag/tagdækning"], "Tryg", opført=1926),
    _doc("100004", "2018-11-02", "Tagkonstruktion med råd",
         "Der er råd og svamp i tagkonstruktionen. Taget skal udskiftes helt ifølge skønsmanden.",
         "Medhold", ["Tag/tagdækning", "Råd/svamp/insekt"], "Gjensidige"),
    _doc("100005", "2022-01-19", "Kloakproblemer og rotter",
         "Kloakken er defekt og der er konstateret rotter. Afløb og kloak skal renoveres.",
         "Ikke medhold", ["Kloak/dræn"], "Alm. Brand"),
    _doc("100006", "2017-06-30", "Fejl i el-installationer",
         "El-installationerne er ulovlige og skal udbedres. Selskabet har afvist dækning.",
         "Afvist", ["Installationer"], "Topdanmark"),
    _doc("100007", "", "Gammel sag uden dato",
         "Ældre sag om skimmelsvamp hvor datoen mangler i registret. Skimmel blev påvist i taget.",
         "Ukendt", ["Skimmel/fugt"], ""),
    _doc("100008", "2023-04-11", "Fundamentrevner i parcelhus",
         "Der er revner i fundamentet og tegn på sætningsskade. Huset er opført i 1974.",
         "Medhold", ["Fundament"], "Tryg", opført=1974),
    _doc("100009", "2016-02-14", "Vandskade fra badeværelse",
         "Vådrumsmembranen i badeværelset er defekt, og der er fugt i etageadskillelsen.",
         "Delvis medhold", ["Badeværelse/vådrum"], "Gjensidige"),
    _doc("100010", "2024-09-05", "Skimmel bag vægbeklædning",
         "Omfattende skimmelsvamp bag vægbeklædningen i stuen. Fugt er trængt ind over flere år.",
         "Medhold", ["Skimmel/fugt"], "Topdanmark"),
]


def _byg_test_store() -> Store:
    df = pd.DataFrame([{k: v for k, v in d.items() if k != "_opført"} for d in _DOCS])
    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"] = df["Dato"].dt.year.astype("Int64")
    df["Opførelsesår"] = pd.array([d["_opført"] for d in _DOCS], dtype="Int64")
    df["Selskab"] = df["Selskab"].fillna("").astype(str)
    df = df.reset_index(drop=True)
    vec, mat = byg_tfidf_index(df)
    return Store(
        df=df, vec=vec, mat=mat,
        mangeltyper=sorted({m for ms in df["Mangeltype"] for m in ms}),
        selskaber=sorted({s for s in df["Selskab"] if s}),
        udfald=["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"],
        link_index={lnk: i for i, lnk in enumerate(df["Link"]) if lnk},
    )


@pytest.fixture(scope="session")
def store() -> Store:
    return _byg_test_store()


@pytest.fixture(autouse=True)
def _ren_konfig(monkeypatch):
    """Kendt baseline pr. test: auth slået fra, kendt hemmelighed, tom
    rate-limit-tilstand. Tests der vil have auth til, sætter app_password selv."""
    s = get_settings()
    monkeypatch.setattr(s, "app_password", "", raising=False)
    monkeypatch.setattr(s, "cookie_secure", False, raising=False)
    monkeypatch.setattr(s, "session_secret", "test-hemmelighed-til-suiten", raising=False)
    auth._login_forsøg.clear()
    yield


@pytest.fixture(autouse=True)
def _ingen_netvaerk(monkeypatch):
    """Garantér at ingen test når ud på nettet: Haiku-kald degraderer stille
    (som ved LLMFejl i produktion), og rå requests-kald smider AssertionError."""
    monkeypatch.setattr("app.core.rag.llm_haiku", lambda *a, **k: "")

    def _blokeret(*a, **k):
        raise AssertionError("Netværkskald i test — patch det relevante lag i stedet.")

    monkeypatch.setattr("requests.post", _blokeret)
    monkeypatch.setattr("requests.get", _blokeret)


@pytest.fixture()
def client(monkeypatch, store) -> TestClient:
    """TestClient med det syntetiske datalager. Lifespan køres bevidst ikke
    (ingen warmup/produktionstjek i tests — de testes direkte for sig)."""
    monkeypatch.setattr(main, "get_store", lambda: store)
    return TestClient(main.app)


@pytest.fixture()
def auth_client(client, monkeypatch) -> TestClient:
    """Som client, men med adgangskode slået til."""
    monkeypatch.setattr(get_settings(), "app_password", "korrekt-hest-batteri", raising=False)
    return client

"""Auth: token-livscyklus, cookie-flow, rate limiting."""
from __future__ import annotations

import time

from app import auth
from app.config import get_settings


# ── Token-enhedstests ─────────────────────────────────────────────────────────
def test_udstedt_token_er_gyldigt():
    assert auth._token_valid(auth.issue_token())


def test_udløbet_token_afvises():
    udløbet = str(int(time.time()) - 10)
    sig = auth._sign(udløbet, get_settings().session_secret)
    assert not auth._token_valid(f"{udløbet}.{sig}")


def test_manipuleret_signatur_afvises():
    token = auth.issue_token()
    expires, sig = token.split(".", 1)
    forfalsket = f"{expires}.{'0' * len(sig)}"
    assert not auth._token_valid(forfalsket)


def test_malformet_token_afvises_uden_crash():
    # Regression: "abc.def" gav tidligere ValueError → 500 i stedet for 401.
    assert not auth._token_valid("abc.def")
    assert not auth._token_valid("ingenpunktum")
    assert not auth._token_valid("")


def test_token_med_andet_udløb_end_signeret_afvises():
    token = auth.issue_token()
    _, sig = token.split(".", 1)
    fremtid = str(int(time.time()) + 999_999)
    assert not auth._token_valid(f"{fremtid}.{sig}")


# ── Cookie-flow gennem API'et ─────────────────────────────────────────────────
def test_me_uden_auth_konfigureret_er_åben(client):
    assert client.get("/api/me").status_code == 200


def test_login_flow(auth_client):
    # Uden cookie: afvist
    assert auth_client.get("/api/me").status_code == 401
    # Forkert kode: afvist
    assert auth_client.post("/api/login", json={"password": "forkert"}).status_code == 401
    # Rigtig kode: cookie sættes og giver adgang
    r = auth_client.post("/api/login", json={"password": "korrekt-hest-batteri"})
    assert r.status_code == 200
    assert auth.COOKIE_NAME in r.headers.get("set-cookie", "")
    assert auth_client.get("/api/me").status_code == 200
    # Logout rydder cookien
    r = auth_client.post("/api/logout")
    assert auth.COOKIE_NAME in r.headers.get("set-cookie", "")


def test_malformet_cookie_giver_401_ikke_500(auth_client):
    auth_client.cookies.set(auth.COOKIE_NAME, "abc.def")
    assert auth_client.get("/api/me").status_code == 401


def test_rate_limit_på_login(auth_client):
    for _ in range(10):
        assert auth_client.post("/api/login", json={"password": "forkert"}).status_code == 401
    # 11. forsøg blokeres — også med KORREKT kode (tjekket sker før sammenligning)
    r = auth_client.post("/api/login", json={"password": "korrekt-hest-batteri"})
    assert r.status_code == 429
    # Vinduet nulstilles → adgang igen
    auth.nulstil_login_forsøg("testclient")
    assert auth_client.post("/api/login", json={"password": "korrekt-hest-batteri"}).status_code == 200


def test_succesfuldt_login_nulstiller_tælleren(auth_client):
    for _ in range(5):
        auth_client.post("/api/login", json={"password": "forkert"})
    assert auth_client.post("/api/login", json={"password": "korrekt-hest-batteri"}).status_code == 200
    # Tælleren er nulstillet — 10 nye fejl er tilladt før 429
    for _ in range(10):
        assert auth_client.post("/api/login", json={"password": "forkert"}).status_code == 401
    assert auth_client.post("/api/login", json={"password": "forkert"}).status_code == 429

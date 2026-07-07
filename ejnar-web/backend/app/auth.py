"""Simpel delt-adgangskode-auth (samme model som Streamlit-appen i dag: én
adgangskode for alle brugere). Udsteder et signeret, tidsbegrænset token som
en httpOnly-cookie — ingen database, ingen brugerkonti.

Løftes til rigtig pr.-bruger-auth ved behov; det er en isoleret modul at
skifte ud uden at røre resten af backend'en."""
from __future__ import annotations

import hashlib
import hmac
import threading
import time

from fastapi import Cookie, HTTPException, Request, status

from .config import get_settings

COOKIE_NAME = "ejnar_session"
_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 dage

# ── Rate limiting af login (in-memory, per proces) ───────────────────────────
# Én delt adgangskode gør brute force til DEN relevante trussel — en simpel
# glidende-vindue-tæller pr. IP er nok i denne skala (én proces, få brugere).
_LOGIN_MAX_FORSØG = 10
_LOGIN_VINDUE_SEK = 15 * 60
_login_forsøg: dict[str, list[float]] = {}
_login_lock = threading.Lock()


def klient_ip(request: Request) -> str:
    """Klientens IP — første hop i X-Forwarded-For når vi står bag Next-proxyen
    (ellers ville alle klienter dele proxyens IP og rate-limite hinanden).
    XFF kan spoofes hvis backend'en eksponeres direkte uden betroet proxy —
    acceptabelt her: konsekvensen er blot at en angriber rammer sit eget vindue."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "ukendt"


def login_tilladt(ip: str) -> bool:
    nu = time.time()
    with _login_lock:
        forsøg = [t for t in _login_forsøg.get(ip, []) if nu - t < _LOGIN_VINDUE_SEK]
        _login_forsøg[ip] = forsøg
        return len(forsøg) < _LOGIN_MAX_FORSØG


def registrer_login_fejl(ip: str) -> None:
    with _login_lock:
        _login_forsøg.setdefault(ip, []).append(time.time())


def nulstil_login_forsøg(ip: str) -> None:
    with _login_lock:
        _login_forsøg.pop(ip, None)


def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def issue_token() -> str:
    settings = get_settings()
    expires = str(int(time.time()) + _TTL_SECONDS)
    sig = _sign(expires, settings.session_secret)
    return f"{expires}.{sig}"


def _token_valid(token: str) -> bool:
    settings = get_settings()
    try:
        expires_str, sig = token.split(".", 1)
        expires = int(expires_str)
    except ValueError:
        # Manipuleret/malformet cookie ("abc.def") skal give 401, ikke 500.
        return False
    if expires < time.time():
        return False
    expected = _sign(expires_str, settings.session_secret)
    return hmac.compare_digest(sig, expected)


def require_auth(ejnar_session: str | None = Cookie(default=None)) -> None:
    """FastAPI-dependency: kast 401 hvis sessionen mangler/er udløbet.

    Hvis APP_PASSWORD ikke er sat, er auth slået fra (praktisk til lokal dev) —
    ligesom Streamlit-appens adfærd i dag."""
    settings = get_settings()
    if not settings.app_password:
        return
    if not ejnar_session or not _token_valid(ejnar_session):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Log ind for at fortsætte.")

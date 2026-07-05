"""Simpel delt-adgangskode-auth (samme model som Streamlit-appen i dag: én
adgangskode for alle brugere). Udsteder et signeret, tidsbegrænset token som
en httpOnly-cookie — ingen database, ingen brugerkonti.

Løftes til rigtig pr.-bruger-auth ved behov; det er en isoleret modul at
skifte ud uden at røre resten af backend'en."""
from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import Cookie, HTTPException, status

from .config import get_settings

COOKIE_NAME = "ejnar_session"
_TTL_SECONDS = 60 * 60 * 24 * 14  # 14 dage


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
    except ValueError:
        return False
    if int(expires_str) < time.time():
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

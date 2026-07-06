"""Konfiguration — læser miljøvariabler. Ingen Streamlit-afhængighed.

For lokal udvikling: opret en .env-fil (se .env.example) eller eksportér
variablerne direkte. I produktion sættes de som rigtige environment-variabler
hos hosting-udbyderen (Railway/Fly/Render/…)."""
from __future__ import annotations

import os
from functools import lru_cache

# Simpel .env-loader uden ekstra dependency (python-dotenv er ikke nødvendig
# for et par nøgler) — indlæser kun variabler der IKKE allerede er sat.
def _load_dotenv() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(here, "..", ".env"),
        os.path.join(here, "..", "..", ".env"),
    ):
        if os.path.exists(candidate):
            with open(candidate, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            return


_load_dotenv()


class Settings:
    app_password: str = os.environ.get("APP_PASSWORD", "")
    anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
    voyage_api_key: str = os.environ.get("VOYAGE_API_KEY", "")
    # Feature-flag: semantisk søgning er bevidst SLÅET FRA i v1 for at undgå
    # Voyage-omkostninger, uanset om en nøgle er sat. Sæt ENABLE_SEMANTIC=1
    # når I er klar til at betale for embeddings.
    enable_semantic: bool = os.environ.get("ENABLE_SEMANTIC", "0") == "1"
    session_secret: str = os.environ.get("SESSION_SECRET", "") or "dev-only-insecure-secret"
    # Sæt COOKIE_SECURE=1 i produktion (HTTPS) så session-cookien kun sendes over
    # https. Slået FRA som udgangspunkt, ellers virker login ikke på http://localhost
    # i lokal udvikling.
    cookie_secure: bool = os.environ.get("COOKIE_SECURE", "0") == "1"
    cors_origins: list[str] = [
        o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
        if o.strip()
    ]
    data_dir: str = os.environ.get(
        "EJNAR_DATA_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "ejnar")),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

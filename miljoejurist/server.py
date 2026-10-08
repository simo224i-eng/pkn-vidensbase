"""Miljøjuristen som selvstændig webapp.

    python -m uvicorn miljoejurist.server:app --port 8766      (fra repo-roden)

Siden ligger i miljoejurist/web/. Lokalt kræves ingen nøgle. Sættes MILJOEJURIST_API_KEYS
(kommasepareret), kræver API'et headeren X-API-Key, og siden beder om nøglen.
Sprogmodel: samme konfiguration som Ejnar (LLM_PROVIDER m.fl.), se api_routes.llm_udbyder().
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles

from .api_routes import llm_udbyder, router

WEB = Path(__file__).resolve().parent / "web"


def _nøgler() -> list[str]:
    return [k.strip() for k in os.environ.get("MILJOEJURIST_API_KEYS", "").split(",") if k.strip()]


def kræv_nøgle(request: Request) -> None:
    nøgler = _nøgler()
    if not nøgler:
        return
    givet = request.headers.get("x-api-key", "")
    if not any(hmac.compare_digest(givet.encode(), k.encode()) for k in nøgler):
        raise HTTPException(401, "Manglende eller ugyldig adgangsnøgle.")


app = FastAPI(title="Miljøjuristen", description="Screeningstjek mod lov, vejledning og nævnspraksis.")
app.include_router(router, dependencies=[Depends(kræv_nøgle)])


@app.get("/health")
def health():
    return {"ok": True, "llm": llm_udbyder() is not None, "nøgle_kræves": bool(_nøgler())}


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")

"""REST-ruter for Miljøjuristen (screeningstjek). Monteres i ejnar/api.py.

POST /v1/miljoejurist/tjek        upload (multipart "fil") eller JSON {"tekst": ...}
GET  /v1/miljoejurist/tjekliste   tjeklisten med lovgrundlag, vejledning og eksempler
GET  /v1/miljoejurist/kilder      hvilke kilder og hvilken dato datagrundlaget har

Uploadede dokumenter gemmes ikke. Teksten sendes kun til en sprogmodel, hvis brugeren
selv vælger "brug_model" og der er konfigureret en udbyder.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import dokument, tjek

MAKS_BYTES = 15 * 1024 * 1024
router = APIRouter(prefix="/v1/miljoejurist", tags=["miljøjuristen"])


class TekstInput(BaseModel):
    tekst: str = Field(..., min_length=200, max_length=400_000)
    navn: str = "indsat tekst"
    dokumenttype: str | None = None
    brug_model: bool = False


def _llm_eller_none(brug: bool):
    if not brug:
        return None
    try:
        import shared
        if not shared.llm_tilgaengelig():
            raise HTTPException(503, "Ingen sprogmodel er konfigureret. Kør uden 'brug_model'.")
        return lambda prompt: shared._llm(prompt, max_tokens=4000, model="claude-sonnet-4-6")
    except ImportError:
        raise HTTPException(503, "Sprogmodel er ikke tilgængelig i dette miljø.")


def _svar(d: dokument.Dokument, dtype: str | None, brug_model: bool) -> dict:
    if d.ord < 50:
        raise HTTPException(422, "Dokumentet indeholder for lidt tekst. Er det en scannet PDF uden tekstlag?")
    r = tjek.tjek(d, dtype=dtype, llm=_llm_eller_none(brug_model))
    out = r.to_json()
    out["markdown"] = tjek.som_markdown(r)
    out["ord"] = d.ord
    return out


@router.post("/tjek")
async def tjek_fil(fil: UploadFile = File(...), dokumenttype: str | None = Form(None),
                   brug_model: bool = Form(False)):
    data = await fil.read()
    if len(data) > MAKS_BYTES:
        raise HTTPException(413, "Filen er for stor (maks. 15 MB).")
    d = dokument.læs(fil.filename or "dokument", data)
    return _svar(d, dokumenttype or None, brug_model)


@router.post("/tjek-tekst")
def tjek_tekst(inp: TekstInput):
    return _svar(dokument.fra_tekst(inp.tekst, inp.navn), inp.dokumenttype, inp.brug_model)


@router.get("/tjekliste")
def tjekliste():
    p = Path(__file__).parent / "data" / "tjekliste.json"
    if not p.exists():
        return {"meta": {}, "punkter": tjek.tjekliste()}
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/kilder")
def kilder():
    from . import lovkilder
    idx = Path(__file__).resolve().parents[2] / "lovgrundlag" / "index.json"
    lov = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else []
    from . import praksis
    s = praksis.sager()
    return {"lovgrundlag": [{"navn": x["navn"], "url": x["url"]} for x in lov],
            "praksis_sager": len(s), "praksis_seneste": s[0]["dato"] if s else None,
            "stykker": len(lovkilder.alle())}

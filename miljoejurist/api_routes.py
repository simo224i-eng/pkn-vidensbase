"""REST-ruter for Miljøjuristen (screeningstjek). Bruges af server.py.

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
    kommune: str | None = None
    plannr: str | None = None
    adresse: str | None = None
    stedtjek: bool = True
    udeluk: list[str] = []  # simulation: nævnsafgørelser, der skjules fra praksissøgningen


def llm_udbyder():
    """Sprogmodel-udbyderen (genbruger llm_provider.py fra ejnar/, konfigureret med LLM_PROVIDER m.fl.).
    Returnerer modulet, eller None hvis ingen udbyder er konfigureret."""
    import sys
    ejnar = Path(__file__).resolve().parents[1] / "ejnar"
    if str(ejnar) not in sys.path:
        sys.path.append(str(ejnar))
    try:
        import llm_provider
    except ImportError:
        return None
    try:
        return llm_provider if llm_provider.is_configured() else None
    except ValueError:
        return None


def _llm_eller_none(brug: bool):
    if not brug:
        return None
    lp = llm_udbyder()
    if lp is None:
        raise HTTPException(503, "Ingen sprogmodel er konfigureret. Kør uden 'brug_model'.")
    return lambda prompt: lp.complete(prompt, max_tokens=4000, model="claude-sonnet-4-6")


def _udeluk(v) -> set[str]:
    if isinstance(v, str):
        v = v.replace(";", ",").split(",")
    return {x.strip() for x in (v or []) if x and x.strip()}


def _svar(d: dokument.Dokument, dtype: str | None, brug_model: bool, sted: dict | None = None,
          udeluk: set[str] | None = None) -> dict:
    if d.ord < 50:
        raise HTTPException(422, "Dokumentet indeholder for lidt tekst. Er det en scannet PDF uden tekstlag?")
    r = tjek.tjek(d, dtype=dtype, udeluk=udeluk or None, llm=_llm_eller_none(brug_model), sted=sted)
    out = r.to_json()
    out["markdown"] = tjek.som_markdown(r)
    out["ord"] = d.ord
    out["udeluk"] = sorted(udeluk or [])
    return out


@router.post("/tjek")
async def tjek_fil(fil: UploadFile = File(...), dokumenttype: str | None = Form(None),
                   brug_model: bool = Form(False), stedtjek: bool = Form(True),
                   kommune: str | None = Form(None), plannr: str | None = Form(None),
                   adresse: str | None = Form(None), udeluk: str | None = Form(None)):
    data = await fil.read()
    if len(data) > MAKS_BYTES:
        raise HTTPException(413, "Filen er for stor (maks. 15 MB).")
    d = dokument.læs(fil.filename or "dokument", data)
    sted = {"kommune": kommune, "plannr": plannr, "adresse": adresse} if stedtjek else None
    return _svar(d, dokumenttype or None, brug_model, sted, _udeluk(udeluk))


@router.post("/tjek-tekst")
def tjek_tekst(inp: TekstInput):
    sted = {"kommune": inp.kommune, "plannr": inp.plannr, "adresse": inp.adresse} if inp.stedtjek else None
    return _svar(dokument.fra_tekst(inp.tekst, inp.navn), inp.dokumenttype, inp.brug_model, sted, _udeluk(inp.udeluk))


@router.get("/tjekliste")
def tjekliste():
    p = Path(__file__).parent / "data" / "tjekliste.json"
    if not p.exists():
        return {"meta": {}, "punkter": tjek.tjekliste()}
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/sag/{sid}")
def sag(sid: str):
    """En underkendt sag: nævnets fejl med citater og links til myndighedens oprindelige dokument."""
    from . import praksis
    d = praksis.sag(sid)
    if d is None:
        raise HTTPException(404, "Sagen findes ikke i praksisdata.")
    return d


@router.get("/kilder")
def kilder():
    from . import lovkilder
    idx = Path(__file__).resolve().parents[1] / "lovgrundlag" / "index.json"
    lov = json.loads(idx.read_text(encoding="utf-8")) if idx.exists() else []
    from . import praksis
    s = praksis.sager()
    return {"lovgrundlag": [{"navn": x["navn"], "url": x["url"]} for x in lov],
            "praksis_sager": len(s), "praksis_seneste": s[0]["dato"] if s else None,
            "stykker": len(lovkilder.alle())}

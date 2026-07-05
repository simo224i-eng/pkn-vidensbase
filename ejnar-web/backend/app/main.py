"""Ejnar-web API — FastAPI-backend der genbruger RAG-motoren fra ejnar/shared.py
(porteret til app/core/, framework-frit). Keyword-baseret (TF-IDF) i v1 —
ingen Voyage/semantisk søgning, se app/core/rag.py."""
from __future__ import annotations

import json
import re
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .auth import COOKIE_NAME, issue_token, require_auth
from .config import get_settings
from .core.claude import LLMFejl, stream_claude
from .core.data import get_store
from .core.rag import byg_prompt, smart_retrieval
from .core.search import tfidf_søg
from .core.text import byg_lækker_afgørelse, byg_notat_html, citater_for_kilde, valider_citationer
from .models import (
    AskRequest, FilterOptions, Kendelse, KendelseDetalje, KendelserResponse,
    LoginRequest, NotatRequest, StatsResponse,
)

app = FastAPI(title="Ejnar API", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Hjælpere ──────────────────────────────────────────────────────────────────
def kendelse_id(row) -> str:
    sag = str(row.get("Sagsnummer") or "").strip()
    if sag:
        return sag
    return str(row.get("Link") or "").rstrip("/").rsplit("/", 1)[-1][-40:]


def row_to_kendelse(row) -> dict:
    dato = row.get("Dato")
    return {
        "id": kendelse_id(row),
        "dato": dato.strftime("%Y-%m-%d") if pd.notna(dato) else None,
        "år": int(row["År"]) if pd.notna(row.get("År")) else None,
        "opførelsesår": int(row["Opførelsesår"]) if pd.notna(row.get("Opførelsesår")) else None,
        "titel": row.get("Titel") or "",
        "link": row.get("Link") or "",
        "excerpt": row.get("Excerpt") or "",
        "sagsnummer": row.get("Sagsnummer") or "",
        "selskab": row.get("Selskab") or "",
        "udfald": row.get("Udfald") or "Ukendt",
        "mangeltype": row.get("Mangeltype") or [],
    }


def _apply_filters(df: pd.DataFrame, mangeltype: list[str] | None, selskab: list[str] | None,
                   udfald: list[str] | None, år_min: int | None, år_max: int | None,
                   opførelsesår_min: int | None, opførelsesår_max: int | None) -> pd.DataFrame:
    mask = pd.Series(True, index=df.index)
    if år_min is not None:
        mask &= df["År"] >= år_min
    if år_max is not None:
        mask &= df["År"] <= år_max
    if opførelsesår_min is not None and opførelsesår_max is not None:
        mask &= df["Opførelsesår"].between(opførelsesår_min, opførelsesår_max).fillna(False).astype(bool)
    if mangeltype:
        mask &= df["Mangeltype"].apply(lambda mts: any(m in mts for m in mangeltype))
    if selskab:
        mask &= df["Selskab"].isin(selskab)
    if udfald:
        mask &= df["Udfald"].isin(udfald)
    return df[mask]


def find_kendelse(df: pd.DataFrame, kid: str) -> Optional[pd.Series]:
    hit = df[df["Sagsnummer"].astype(str).str.strip() == kid]
    if hit.empty:
        hit = df[df["Link"].astype(str).str.rstrip("/").str.endswith(kid)]
    return hit.iloc[0] if not hit.empty else None


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    if not settings.app_password:
        return {"ok": True, "note": "Ingen adgangskode konfigureret — auth er slået fra."}
    if body.password != settings.app_password:
        raise HTTPException(401, "Forkert adgangskode.")
    token = issue_token()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                        max_age=60 * 60 * 24 * 14)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"ok": True}


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/me", dependencies=[Depends(require_auth)])
def me():
    """Let auth-tjek — rører IKKE datalageret (undgår at udløse en ~90s
    kold TF-IDF-opbygning bare for at tjekke om brugeren er logget ind)."""
    return {"authenticated": True}


# ── Filtre ────────────────────────────────────────────────────────────────────
@app.get("/api/filters", response_model=FilterOptions, dependencies=[Depends(require_auth)])
def get_filters():
    store = get_store()
    df = store.df
    år_min, år_max = (int(df["År"].min()), int(df["År"].max())) if df["År"].notna().any() else (2000, 2026)
    opf_min, opf_max = (int(df["Opførelsesår"].min()), int(df["Opførelsesår"].max())) \
        if df["Opførelsesår"].notna().any() else (1850, 2026)
    return FilterOptions(
        mangeltyper=store.mangeltyper, selskaber=store.selskaber, udfald=store.udfald,
        år_min=år_min, år_max=år_max, opførelsesår_min=opf_min, opførelsesår_max=opf_max,
    )


# ── Kendelser (søgning/liste) ─────────────────────────────────────────────────
@app.get("/api/kendelser", response_model=KendelserResponse, dependencies=[Depends(require_auth)])
def list_kendelser(
    q: str = "", søgetype: str = "ordret",
    mangeltype: list[str] = Query(default=[]), selskab: list[str] = Query(default=[]),
    udfald: list[str] = Query(default=[]),
    år_min: Optional[int] = None, år_max: Optional[int] = None,
    opførelsesår_min: Optional[int] = None, opførelsesår_max: Optional[int] = None,
    page: int = 1, page_size: int = 25,
):
    store = get_store()
    df_filter = _apply_filters(store.df, mangeltype, selskab, udfald,
                               år_min, år_max, opførelsesår_min, opførelsesår_max)

    q = q.strip()
    if q and søgetype == "intelligent":
        sub_idx = df_filter.index.tolist()
        df_vis = tfidf_søg(q, store.df, store.vec, store.mat, sub_idx=sub_idx, top_n=500)
    elif q:
        mask = (df_filter["Titel"].str.contains(q, case=False, na=False, regex=False) |
                df_filter["Tekst"].str.contains(q, case=False, na=False, regex=False))
        df_vis = df_filter[mask].sort_values("Dato", ascending=False)
    else:
        df_vis = df_filter.sort_values("Dato", ascending=False)

    total = len(df_vis)
    start = (page - 1) * page_size
    page_rows = df_vis.iloc[start:start + page_size]
    return KendelserResponse(
        total=total,
        items=[Kendelse(**row_to_kendelse(r)) for _, r in page_rows.iterrows()],
    )


@app.get("/api/kendelser/{kid}", dependencies=[Depends(require_auth)])
def get_kendelse(kid: str):
    store = get_store()
    row = find_kendelse(store.df, kid)
    if row is None:
        raise HTTPException(404, "Kendelse ikke fundet.")
    base = row_to_kendelse(row)
    toc_html, body_html = byg_lækker_afgørelse(row.get("Tekst", ""), anchor_prefix="detail")
    return {**base, "tekst": row.get("Tekst", ""), "toc_html": toc_html, "body_html": body_html}


# ── Statistik ─────────────────────────────────────────────────────────────────
@app.get("/api/stats", response_model=StatsResponse, dependencies=[Depends(require_auth)])
def stats(
    mangeltype: list[str] = Query(default=[]), selskab: list[str] = Query(default=[]),
    udfald: list[str] = Query(default=[]),
    år_min: Optional[int] = None, år_max: Optional[int] = None,
    opførelsesår_min: Optional[int] = None, opførelsesår_max: Optional[int] = None,
):
    store = get_store()
    d = _apply_filters(store.df, mangeltype, selskab, udfald,
                       år_min, år_max, opførelsesår_min, opførelsesår_max)
    if d.empty:
        return StatsResponse(total=0, medhold_pct=0, antal_selskaber=0, år_span="–",
                             per_år=[], udfald_per_år=[], top_mangeltyper=[],
                             top_selskaber=[], medhold_rate_per_mangeltype=[])

    medhold_pct = float(d["Udfald"].isin(["Medhold", "Delvis medhold"]).mean() * 100)
    år_span = f"{int(d['År'].min())}–{int(d['År'].max())}" if d["År"].notna().any() else "–"

    per_år = (d.dropna(subset=["År"]).groupby("År").size()
              .reset_index(name="antal").rename(columns={"År": "år"}))
    udfald_år = (d.dropna(subset=["År"]).groupby(["År", "Udfald"]).size()
                 .reset_index(name="antal").rename(columns={"År": "år", "Udfald": "udfald"}))

    mt_rows = [m for ms in d["Mangeltype"] for m in ms]
    top_mt = (pd.Series(mt_rows).value_counts().rename_axis("mangeltype")
              .reset_index(name="antal").head(15)) if mt_rows else pd.DataFrame(columns=["mangeltype", "antal"])

    sel_df = (d[d["Selskab"] != ""].groupby("Selskab").size()
              .reset_index(name="antal").rename(columns={"Selskab": "selskab"})
              .sort_values("antal", ascending=False).head(15))

    rate_rows = []
    for mt in sorted({m for ms in d["Mangeltype"] for m in ms}):
        sub = d[d["Mangeltype"].apply(lambda ms: mt in ms)]
        if len(sub) >= 3:
            rate_rows.append({
                "mangeltype": mt, "antal": int(len(sub)),
                "medhold_pct": round(float(sub["Udfald"].isin(["Medhold", "Delvis medhold"]).mean() * 100), 1),
            })

    return StatsResponse(
        total=len(d), medhold_pct=round(medhold_pct, 1), antal_selskaber=int(d[d["Selskab"] != ""]["Selskab"].nunique()),
        år_span=år_span, per_år=per_år.to_dict("records"), udfald_per_år=udfald_år.to_dict("records"),
        top_mangeltyper=top_mt.to_dict("records"), top_selskaber=sel_df.to_dict("records"),
        medhold_rate_per_mangeltype=sorted(rate_rows, key=lambda r: r["medhold_pct"]),
    )


# ── AI-assistent (streaming) ──────────────────────────────────────────────────
def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"


@app.post("/api/ask", dependencies=[Depends(require_auth)])
def ask(body: AskRequest):
    store = get_store()
    df = store.df

    filtre = body.filtre or {}
    df_filter = _apply_filters(
        df, filtre.get("mangeltype"), filtre.get("selskab"), filtre.get("udfald"),
        filtre.get("år_min"), filtre.get("år_max"),
        filtre.get("opførelsesår_min"), filtre.get("opførelsesår_max"),
    )
    sub_idx = df_filter.index.tolist()
    historik = [m.model_dump() for m in body.historik]
    filter_options = {"Mangeltype": store.mangeltyper}

    def gen():
        try:
            standalone, kilder, af_info = smart_retrieval(
                body.spørgsmål, df, store.vec, store.mat, sub_idx, historik, filter_options)
        except Exception as e:  # retrieval-fejl skal stadig give brugeren besked
            yield _sse({"type": "error", "message": f"Søgning fejlede: {e}"})
            return

        yield _sse({"type": "kilder", "kilder": kilder, "auto_filter": af_info})

        if not kilder:
            msg = "Jeg fandt ingen kendelser der matcher spørgsmålet inden for de valgte filtre."
            yield _sse({"type": "delta", "text": msg})
            yield _sse({"type": "done", "text": msg, "suspekte": []})
            return

        prompt = byg_prompt(body.spørgsmål, kilder, historik)
        full = ""
        try:
            for chunk in stream_claude(prompt, max_tokens=3000):
                full += chunk
                yield _sse({"type": "delta", "text": chunk})
        except LLMFejl as e:
            yield _sse({"type": "error", "message": str(e)})
            return

        try:
            suspekte = valider_citationer(full, kilder)
        except Exception:
            suspekte = []
        yield _sse({"type": "done", "text": full, "suspekte": suspekte})

    return StreamingResponse(gen(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.post("/api/kilde-citat", dependencies=[Depends(require_auth)])
def kilde_citat(body: dict):
    """Find citater fra et givet svar i én bestemt kilde + fremhæv dem i
    den lækre læsevisning — bruges når brugeren klikker en citat-chip."""
    store = get_store()
    kid = body.get("kendelse_id", "")
    svar = body.get("svar", "")
    row = find_kendelse(store.df, kid)
    if row is None:
        raise HTTPException(404, "Kendelse ikke fundet.")
    doc = {"Tekst": row.get("Tekst", "")}
    quotes = citater_for_kilde(svar, doc)
    toc_html, body_html = byg_lækker_afgørelse(
        row.get("Tekst", ""), highlight_quotes=quotes, anchor_prefix=f"c{kid}")
    return {"quotes": quotes, "toc_html": toc_html, "body_html": body_html}


# ── Notat-eksport ─────────────────────────────────────────────────────────────
@app.post("/api/notat", dependencies=[Depends(require_auth)])
def notat(body: NotatRequest):
    html = byg_notat_html(body.spørgsmål, body.svar, body.kilder)
    return Response(content=html, media_type="text/html", headers={
        "Content-Disposition": 'attachment; filename="ejnar-notat.html"',
    })

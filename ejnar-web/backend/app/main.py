"""Ejnar-web API — FastAPI-backend der genbruger RAG-motoren fra ejnar/shared.py
(porteret til app/core/, framework-frit). Keyword-baseret (TF-IDF) i v1 —
ingen Voyage/semantisk søgning, se app/core/rag.py."""
from __future__ import annotations

import json
import re
import secrets
import threading
from contextlib import asynccontextmanager
from typing import Optional

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

from .auth import (
    COOKIE_NAME, issue_token, klient_ip, login_tilladt, nulstil_login_forsøg,
    registrer_login_fejl, require_auth,
)
from .config import get_settings, tjek_produktionskonfig
from .core.claude import LLMFejl, stream_claude
from .core.data import get_store, store_klar
from .core.rag import byg_prompt, smart_retrieval
from .core.search import tfidf_søg
from .core.text import byg_lækker_afgørelse, byg_notat_html, citater_for_kilde, valider_citationer
from .models import (
    AskRequest, FilterOptions, Kendelse, KendelseDetalje, KendelserResponse,
    KildeCitatRequest, LoginRequest, NotatRequest, StatsResponse,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tjek_produktionskonfig(get_settings())
    if get_settings().warmup:
        # Byg TF-IDF-indekset (~90 sek) i baggrunden med det samme, så første
        # bruger ikke betaler koldstarten. /api/health svarer imens (liveness);
        # dataafhængige endpoints venter blot på get_store()-låsen som hidtil.
        threading.Thread(target=_warm_store, daemon=True, name="ejnar-warmup").start()
    yield


def _warm_store() -> None:
    try:
        get_store()
    except Exception as e:
        # Fejl her må ikke vælte processen — første rigtige kald rapporterer
        # samme fejl til brugeren via normal exception-håndtering.
        print(f"[ejnar] Warmup fejlede: {e}")


app = FastAPI(title="Ejnar API", version="0.1.0", lifespan=lifespan)

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
    # NB: .fillna(False) på alle Int64-sammenligninger — rækker uden dato/år har
    # NA, og NA i en boolsk maske rejser under pandas 2.x (deploy-pinnen).
    mask = pd.Series(True, index=df.index)
    if år_min is not None:
        mask &= (df["År"] >= år_min).fillna(False).astype(bool)
    if år_max is not None:
        mask &= (df["År"] <= år_max).fillna(False).astype(bool)
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
    kid = (kid or "").strip()
    if not kid:
        # Tom id må ALDRIG matche: Link.endswith("") er sandt for alle rækker og
        # ville ellers returnere en tilfældig (første) kendelse.
        return None
    hit = df[df["Sagsnummer"].astype(str).str.strip() == kid]
    if hit.empty:
        hit = df[df["Link"].astype(str).str.rstrip("/").str.endswith(kid)]
    return hit.iloc[0] if not hit.empty else None


def _rehydrate_kilder(store, kilder_in: list | None) -> list:
    """Slå kilder op igen i datalageret på deres Link og returnér de fulde
    DataFrame-rækker (med Tekst, kapitaliserede nøgler) — samme form som
    ejnar/shared.py-porten forventer.

    Kilder der har været i browseren (chat-historik, notat-eksport) ankommer i
    den slanke Kendelse-form (små nøgler, ingen Tekst). Den porterede RAG/notat/
    citat-logik læser 'Titel'/'Dato'/'Tekst' osv., så vi genskaber den fulde
    række her i stedet for at stole på det browseren sendte tilbage. Ukendte
    links (fx efter en data-opdatering) beholdes as-is (best effort)."""
    out = []
    for k in kilder_in or []:
        lnk = k.get("link") or k.get("Link") or ""
        pos = store.link_index.get(lnk)
        out.append(store.df.iloc[pos].to_dict() if pos is not None else k)
    return out


# ── Auth ──────────────────────────────────────────────────────────────────────
@app.post("/api/login")
def login(body: LoginRequest, request: Request, response: Response):
    if not settings.app_password:
        return {"ok": True, "note": "Ingen adgangskode konfigureret — auth er slået fra."}
    ip = klient_ip(request)
    if not login_tilladt(ip):
        raise HTTPException(429, "For mange loginforsøg — prøv igen om et kvarter.")
    # compare_digest: konstant-tids-sammenligning, så svartiden ikke lækker
    # hvor mange tegn af adgangskoden der var rigtige.
    if not secrets.compare_digest(body.password.encode(), settings.app_password.encode()):
        registrer_login_fejl(ip)
        raise HTTPException(401, "Forkert adgangskode.")
    nulstil_login_forsøg(ip)
    token = issue_token()
    response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=60 * 60 * 24 * 14)
    return {"ok": True}


@app.post("/api/logout")
def logout(response: Response):
    # Samme attributter som ved set_cookie, ellers rydder browseren den ikke.
    response.delete_cookie(COOKIE_NAME, httponly=True, samesite="lax",
                           secure=settings.cookie_secure)
    return {"ok": True}


@app.get("/api/health")
def health():
    """Liveness: processen kører. Svarer også under den ~90 sek warmup."""
    return {"ok": True}


@app.get("/api/ready")
def ready():
    """Readiness: 200 først når TF-IDF-indekset er bygget, ellers 503 — så
    deploy-platformens healthcheck holder trafik tilbage til processen er varm."""
    if store_klar():
        return {"ready": True}
    return JSONResponse({"ready": False, "note": "Bygger indeks…"}, status_code=503)


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
        from .core.synonymer import udvid_query_dansk
        sub_idx = df_filter.index.tolist()
        df_vis = tfidf_søg(udvid_query_dansk(q), store.df, store.vec, store.mat,
                           sub_idx=sub_idx, top_n=500)
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
    # Re-hydrér kilder fra tidligere svar (de kom fra browseren i slank form) så
    # smart_retrieval/_hist_kilder ser fulde rækker med Tekst og 'Link'-nøgle.
    for msg in historik:
        if msg.get("kilder"):
            msg["kilder"] = _rehydrate_kilder(store, msg["kilder"])
    filter_options = {"Mangeltype": store.mangeltyper}

    def gen():
        try:
            standalone, kilder, af_info = smart_retrieval(
                body.spørgsmål, df, store.vec, store.mat, sub_idx, historik,
                filter_options, embeds=store.embeds)
        except Exception as e:  # retrieval-fejl skal stadig give brugeren besked
            yield _sse({"type": "error", "message": f"Søgning fejlede: {e}"})
            return

        # Kilder ud til browseren mappes til den slanke Kendelse-form (små nøgler,
        # uden Tekst) som frontendens typer/komponenter forventer. Den fulde
        # 'kilder' (kapitaliserede nøgler, med Tekst) beholdes internt til
        # byg_prompt() og valider_citationer() nedenfor.
        kilder_ud = [row_to_kendelse(k) for k in kilder]
        yield _sse({"type": "kilder", "kilder": kilder_ud, "auto_filter": af_info})

        if not kilder:
            msg = "Jeg fandt ingen kendelser der matcher spørgsmålet inden for de valgte filtre."
            yield _sse({"type": "delta", "text": msg})
            yield _sse({"type": "done", "text": msg, "suspekte": []})
            return

        prompt = byg_prompt(body.spørgsmål, kilder, historik,
                            embeds=store.embeds, link_til_idx=store.link_index)
        full = ""
        try:
            for chunk in stream_claude(prompt, max_tokens=3000):
                full += chunk
                yield _sse({"type": "delta", "text": chunk})
        except LLMFejl as e:
            yield _sse({"type": "error", "message": str(e)})
            return
        except Exception as e:
            # SSE-kontrakt: klienten skal ALTID få done eller error — ellers
            # hænger chatten i "svarer…" for evigt hvis noget uventet vælter.
            yield _sse({"type": "error", "message": f"Uventet fejl under svaret: {e}"})
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
def kilde_citat(body: KildeCitatRequest):
    """Find citater fra et givet svar i én bestemt kilde + fremhæv dem i
    den lækre læsevisning — bruges når brugeren klikker en citat-chip."""
    store = get_store()
    kid = body.kendelse_id
    svar = body.svar
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
    # body.kilder kommer fra browseren i slank form; byg_notat_html (porteret)
    # læser kapitaliserede nøgler ('Titel','Dato','Sagsnummer'...) → re-hydrér.
    kilder = _rehydrate_kilder(get_store(), body.kilder)
    html = byg_notat_html(body.spørgsmål, body.svar, kilder)
    return Response(content=html, media_type="text/html", headers={
        "Content-Disposition": 'attachment; filename="ejnar-notat.html"',
    })

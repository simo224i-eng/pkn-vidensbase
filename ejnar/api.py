"""Ejnar REST-API (FastAPI).

Kør lokalt:
    cd ejnar
    pip install -r requirements.txt -r requirements-api.txt
    EJNAR_API_KEYS=hemmelig LLM_PROVIDER=gemini LLM_API_KEY=... uvicorn api:app --port 8000

Dokumentation: http://localhost:8000/docs (OpenAPI/Swagger).
Alle /v1-endpoints kræver headeren ``X-API-Key`` eller ``Authorization: Bearer``.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import queue
import re
import threading
import time
from contextlib import asynccontextmanager
from typing import Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import engine
import shared

log = logging.getLogger("ejnar.api")

API_VERSION = "1.0.0"


# ── Korpus: indlæses i baggrunden ved opstart ─────────────────────────────────
class _State:
    corpus: engine.Corpus | None = None
    error: str = ""
    started: float = 0.0
    lock = threading.Lock()


STATE = _State()


def _load_corpus(with_embeddings: bool) -> None:
    try:
        STATE.corpus = engine.Corpus.load(with_embeddings=with_embeddings)
        log.info("Korpus indlæst: %d kendelser (%s)", len(STATE.corpus.df), STATE.corpus.search_mode)
    except Exception as exc:  # pragma: no cover - logges og vises i /health
        log.exception("Kunne ikke indlæse korpus")
        STATE.error = f"{type(exc).__name__}: {exc}"


def start_loading(with_embeddings: bool = True) -> None:
    with STATE.lock:
        if STATE.started:
            return
        STATE.started = time.time()
    threading.Thread(target=_load_corpus, args=(with_embeddings,), daemon=True).start()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if os.environ.get("EJNAR_API_EAGER_LOAD", "1") != "0":
        start_loading(os.environ.get("EJNAR_API_EMBEDDINGS", "1") != "0")
    yield


app = FastAPI(
    title="Ejnar API",
    version=API_VERSION,
    summary="Praksissøgning og RAG over Ankenævnet for Forsikrings kendelser om ejerskifteforsikring.",
    lifespan=lifespan,
)

_origins = [o.strip() for o in os.environ.get("EJNAR_CORS_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(
        CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-API-Key", "Content-Type"],
    )


# ── Auth ──────────────────────────────────────────────────────────────────────
def _api_keys() -> list[str]:
    raw = os.environ.get("EJNAR_API_KEYS", "") or shared._secret("EJNAR_API_KEYS", "")
    return [k.strip() for k in str(raw).split(",") if k.strip()]


def require_api_key(request: Request) -> None:
    keys = _api_keys()
    if not keys:
        raise HTTPException(503, "API'et er ikke konfigureret: sæt EJNAR_API_KEYS.")
    supplied = request.headers.get("x-api-key", "")
    auth = request.headers.get("authorization", "")
    if not supplied and auth.lower().startswith("bearer "):
        supplied = auth[7:].strip()
    if not any(hmac.compare_digest(supplied.encode(), k.encode()) for k in keys):
        raise HTTPException(401, "Manglende eller ugyldig API-nøgle.",
                            headers={"WWW-Authenticate": "Bearer"})


# ── Rate limiting (pr. API-nøgle, kun LLM-endpoints) ─────────────────────────
class _RateLimiter:
    """Glidende vindue i hukommelsen. Rækker til én API-proces; bag en load
    balancer med flere instanser bør det flyttes til fx Redis."""

    def __init__(self):
        self.hits: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def check(self, key: str, limit: int, window: float = 60.0) -> float:
        """Returnér 0 hvis kaldet er tilladt, ellers sekunder til næste ledige plads."""
        now = time.monotonic()
        with self.lock:
            hits = [t for t in self.hits.get(key, []) if now - t < window]
            if len(hits) >= limit:
                self.hits[key] = hits
                return window - (now - hits[0])
            hits.append(now)
            self.hits[key] = hits
            return 0.0


RATE = _RateLimiter()


def llm_rate_limit(request: Request) -> None:
    limit = int(os.environ.get("EJNAR_LLM_RATE_PER_MIN", "20") or 0)
    if limit <= 0:
        return
    who = request.headers.get("x-api-key") or request.headers.get("authorization", "")
    wait = RATE.check(hashlib.sha256(who.encode()).hexdigest(), limit)
    if wait:
        raise HTTPException(429, f"For mange AI-forespørgsler – prøv igen om {int(wait) + 1} sekunder.",
                            headers={"Retry-After": str(int(wait) + 1)})


def corpus() -> engine.Corpus:
    if STATE.corpus is not None:
        return STATE.corpus
    if STATE.error:
        raise HTTPException(500, f"Korpus kunne ikke indlæses: {STATE.error}")
    if not STATE.started:
        start_loading()
    raise HTTPException(503, "Korpus indlæses stadig – prøv igen om lidt.",
                        headers={"Retry-After": "15"})


# ── Modeller ──────────────────────────────────────────────────────────────────
Udfald = Literal["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]


class Filters(BaseModel):
    year_from: int | None = Field(None, ge=1900, le=2100)
    year_to: int | None = Field(None, ge=1900, le=2100)
    defect_types: list[str] = Field(default_factory=list, description="Mangeltyper, fx 'Skimmel/fugt'.")
    companies: list[str] = Field(default_factory=list, description="Forsikringsselskaber.")
    outcomes: list[Udfald] = Field(default_factory=list)

    def sub_idx(self, c: engine.Corpus):
        return c.sub_idx(år_fra=self.year_from, år_til=self.year_to,
                         mangeltyper=self.defect_types, selskaber=self.companies,
                         udfald=self.outcomes)


class SearchRequest(BaseModel):
    query: str = Field("", max_length=2000)
    mode: Literal["keyword", "exact", "smart"] = Field(
        "keyword",
        description="keyword = hurtig hybrid-relevans (TF-IDF + BM25 + embeddings, ingen LLM). exact = ordret frase, nyeste først. "
                    "smart = fuld RAG-retrieval (query-omskrivning, hybrid søgning, rerank).",
    )
    filters: Filters = Field(default_factory=Filters)
    limit: int = Field(20, ge=1, le=100)
    offset: int = Field(0, ge=0)


class Decision(BaseModel):
    id: str
    case_number: str
    date: str | None
    year: int | None
    title: str
    company: str
    outcome: str
    defect_types: list[str]
    link: str
    snippet: str
    score: float | None = None


class DecisionFull(Decision):
    text: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    total: int
    outcome_counts: dict[str, int] = Field(default_factory=dict,
                                           description="Udfaldsfordeling over alle resultater (ikke kun siden).")
    results: list[Decision]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=20000)
    source_ids: list[str] = Field(default_factory=list,
                                  description="Kilde-ID'er fra et tidligere svar (bevarer kildenummerering).")


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    filters: Filters = Field(default_factory=Filters)
    stream: bool = Field(False, description="true = Server-Sent Events (sources → delta* → done).")


class Source(Decision):
    n: int = Field(..., description="Kildenummer som svaret henviser til med [Kilde n].")
    cited: bool


class AnswerResponse(BaseModel):
    answer: str
    sources: list[Source]
    suspect_quotes: list[str]
    debug: dict


# ── Hjælpere ──────────────────────────────────────────────────────────────────
def _to_decision(rec: dict, query: str = "", score=None, full: bool = False) -> dict:
    dato = rec.get("Dato")
    ts = pd.Timestamp(dato) if dato is not None and not pd.isna(dato) else None
    år = rec.get("År")
    out = {
        "id": str(rec.get("Id") or engine.decision_id(rec.get("Link", ""))),
        "case_number": str(rec.get("Sagsnummer") or ""),
        "date": ts.strftime("%Y-%m-%d") if ts is not None else None,
        "year": int(år) if år is not None and not pd.isna(år) else (ts.year if ts is not None else None),
        "title": str(rec.get("Titel") or ""),
        "company": str(rec.get("Selskab") or ""),
        "outcome": str(rec.get("Udfald") or "Ukendt"),
        "defect_types": list(rec.get("Mangeltype") or []),
        "link": str(rec.get("Link") or ""),
        "snippet": engine.snippet(rec.get("Tekst", ""), query),
        "score": None if score is None or pd.isna(score) else round(float(score), 4),
    }
    if full:
        out["text"] = str(rec.get("Tekst") or "")
    return out


def _history(c: engine.Corpus, messages: list[ChatMessage]) -> list:
    hist = []
    for m in messages:
        item = {"rolle": "bruger" if m.role == "user" else "assistent", "tekst": m.content}
        if m.role == "assistant" and m.source_ids:
            item["kilder"] = [r for r in (c.find(i) for i in m.source_ids) if r]
        hist.append(item)
    return hist


def _sources(kilder: list, cited: list[int]) -> list[dict]:
    return [
        {**_to_decision(k), "n": i + 1, "cited": (i + 1) in cited}
        for i, k in enumerate(kilder)
    ]


def _require_llm() -> None:
    if not shared.llm_tilgaengelig():
        raise HTTPException(503, "Ingen LLM konfigureret (LLM_PROVIDER/LLM_API_KEY eller ANTHROPIC_API_KEY).")


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health():
    c = STATE.corpus
    return {
        "status": "ok" if c is not None else ("error" if STATE.error else "loading"),
        "version": API_VERSION,
        "decisions": int(len(c.df)) if c is not None else None,
        "search_mode": c.search_mode if c is not None else None,
        "llm": shared.llm_label() if shared.llm_tilgaengelig() else None,
        "error": STATE.error or None,
    }


@app.get("/v1/meta", tags=["søgning"], dependencies=[Depends(require_api_key)])
def meta():
    """Filterværdier og nøgletal til at bygge en søge-UI."""
    c = corpus()
    df = c.df
    years = df["År"].dropna()
    return {
        "decisions": int(len(df)),
        "year_min": int(years.min()) if len(years) else None,
        "year_max": int(years.max()) if len(years) else None,
        "defect_types": c.options.get("Mangeltype", []),
        "companies": c.options.get("Selskab", []),
        "outcomes": engine.UDFALD,
        "outcome_counts": {k: int(v) for k, v in df["Udfald"].value_counts().items()},
    }


@app.post("/v1/search", response_model=SearchResponse, tags=["søgning"],
          dependencies=[Depends(require_api_key)])
def search(req: SearchRequest):
    """Find kendelser. Svarer altid med metadata + et uddrag omkring søgeordet."""
    c = corpus()
    sub = req.filters.sub_idx(c)
    q = req.query.strip()
    if req.mode == "smart" and q:
        _require_llm()
        _, kilder = engine.smart_retrieval(
            q, c.df, c.vec, c.mat, sub if sub is not None else c.df.index.tolist(), [],
            embeds=c.embeds, filter_options=c.options,
        )
        recs = [(k, None) for k in kilder]
    elif req.mode == "keyword" and q:
        idx = engine.relevans_søg(q, c.df, c.vec, c.mat, c.embeds, sub_idx=sub, top_n=200)
        recs = [(r, None) for r in c.df.iloc[idx].to_dict("records")] if idx else []
    else:
        hits = engine.ordret_søg(q, c.df, sub_idx=sub)
        recs = [(r, None) for r in hits.to_dict("records")]
    # Et sagsnummer i søgefeltet lægger den kendelse øverst uanset søgemetode.
    direkte = engine.sagsnummer_hits(q, c.df if sub is None else c.df.loc[sub])
    if len(direkte):
        links = set(direkte["Link"])
        recs = [(r, None) for r in direkte.to_dict("records")] + [x for x in recs if x[0].get("Link") not in links]
    page = recs[req.offset:req.offset + req.limit]
    counts: dict[str, int] = {}
    for r, _ in recs:
        counts[r.get("Udfald") or "Ukendt"] = counts.get(r.get("Udfald") or "Ukendt", 0) + 1
    return {
        "query": q, "mode": req.mode, "total": len(recs), "outcome_counts": counts,
        "results": [_to_decision(r, q, s) for r, s in page],
    }


class StatsRequest(BaseModel):
    query: str = Field("", max_length=500, description="Valgfri ordret frase, der afgrænser grundlaget.")
    filters: Filters = Field(default_factory=Filters)


def _group(df: pd.DataFrame, col: str, limit: int | None = None, explode: bool = False) -> list[dict]:
    frame = df[[col, "Udfald"]].explode(col) if explode else df[[col, "Udfald"]]
    frame = frame[frame[col].astype(str).str.strip() != ""]
    tab = pd.crosstab(frame[col], frame["Udfald"])
    tab["_total"] = tab.sum(axis=1)
    tab = tab.sort_values("_total", ascending=False)
    if limit:
        tab = tab.head(limit)
    return [
        {"label": str(idx) if not isinstance(idx, float) else str(int(idx)), "total": int(row["_total"]),
         "counts": {o: int(row[o]) for o in engine.UDFALD if o in row.index and row[o]}}
        for idx, row in tab.iterrows()
    ]


@app.post("/v1/stats", tags=["søgning"], dependencies=[Depends(require_api_key)])
def stats(req: StatsRequest):
    """Udfaldsstatistik for et udsnit af praksis: pr. år, mangeltype og selskab."""
    c = corpus()
    sub = req.filters.sub_idx(c)
    base = c.df if sub is None else c.df.loc[sub]
    if req.query.strip():
        base = engine.ordret_søg(req.query, base)
    by_year = _group(base.assign(År=base["År"].astype("Int64")), "År") if len(base) else []
    by_year.sort(key=lambda r: int(r["label"]))
    return {
        "total": int(len(base)),
        "outcome_counts": {k: int(v) for k, v in base["Udfald"].value_counts().items()},
        "by_year": by_year,
        "by_defect": _group(base, "Mangeltype", explode=True) if len(base) else [],
        "by_company": _group(base, "Selskab", limit=15) if len(base) else [],
    }


@app.get("/v1/decisions/{key}", response_model=DecisionFull, tags=["kendelser"],
         dependencies=[Depends(require_api_key)])
def get_decision(key: str, q: str = Query("", description="Valgfri søgetekst til uddraget.")):
    """Hent en kendelse på ID eller sagsnummer, inkl. fuld tekst."""
    rec = corpus().find(key)
    if rec is None:
        raise HTTPException(404, "Kendelsen findes ikke.")
    return _to_decision(rec, q, full=True)


@app.get("/v1/decisions/{key}/similar", response_model=list[Decision], tags=["kendelser"],
         dependencies=[Depends(require_api_key)])
def similar_decisions(key: str, limit: int = Query(6, ge=1, le=20)):
    """Kendelser der ligner denne mest (samme søgekæde som relevanssøgning, ingen LLM)."""
    c = corpus()
    rec = c.find(key)
    if rec is None:
        raise HTTPException(404, "Kendelsen findes ikke.")
    # AKF's titel er et resumé af faktum og resultat og er derfor en god forespørgsel.
    query = re.sub(r"\b(?:Selskab|Klager)(?:et|en)?\s+(?:delvis\w*\s+)?medhold\.?\s*$", "", rec["Titel"]).strip()
    idx = engine.relevans_søg(query[:600], c.df, c.vec, c.mat, c.embeds, top_n=limit + 5)
    out = [r for r in c.df.iloc[idx].to_dict("records") if r["Id"] != rec["Id"]] if idx else []
    return [_to_decision(r) for r in out[:limit]]


@app.post("/v1/decisions/{key}/summary", tags=["kendelser"],
          dependencies=[Depends(require_api_key), Depends(llm_rate_limit)])
def summarize_decision(key: str):
    """Kort struktureret resumé af en kendelse (LLM)."""
    rec = corpus().find(key)
    if rec is None:
        raise HTTPException(404, "Kendelsen findes ikke.")
    _require_llm()
    return {"id": rec["Id"], "summary": shared._llm(engine.resumé_prompt(rec["Titel"], rec["Tekst"]))}


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/v1/answer", response_model=AnswerResponse, tags=["assistent"],
          dependencies=[Depends(require_api_key), Depends(llm_rate_limit)],
          responses={200: {"content": {"text/event-stream": {}}}})
def answer(req: AnswerRequest):
    """Besvar et praksisspørgsmål med kildehenvisninger ([Kilde n]) og citatkontrol."""
    c = corpus()
    _require_llm()
    sub = req.filters.sub_idx(c)
    hist = _history(c, req.history)

    if not req.stream:
        res = c.answer(req.question, hist, sub_idx=sub)
        return {
            "answer": res["svar"],
            "sources": _sources(res["kilder"], res["citerede"]),
            "suspect_quotes": res["mistænkelige_citater"],
            "debug": _jsonable(res["debug"]),
        }

    events: queue.Queue = queue.Queue()

    def work():
        try:
            kilder, h, debug = c.retrieve(req.question, hist, sub)
            events.put(_sse("sources", {"sources": _sources(kilder, []), "debug": _jsonable(debug)}))
            sent = [0]

            def on_text(full: str):
                if len(full) > sent[0]:
                    events.put(_sse("delta", {"text": full[sent[0]:]}))
                    sent[0] = len(full)

            res = c.generate(req.question, kilder, h, on_text=on_text)
            on_text(res["svar"])
            events.put(_sse("done", {
                "answer": res["svar"],
                "cited": res["citerede"],
                "suspect_quotes": res["mistænkelige_citater"],
            }))
        except Exception as exc:
            log.exception("Fejl under streamet svar")
            events.put(_sse("error", {"detail": str(exc)}))
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def stream():
        while (item := events.get()) is not None:
            yield item

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _jsonable(obj):
    return json.loads(json.dumps(obj, default=str, ensure_ascii=False))


# ── Webapp ────────────────────────────────────────────────────────────────────
# Registreres til sidst, så /health, /docs og /v1/* matches først.
_WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
if os.path.isdir(_WEB_DIR):
    app.mount("/", StaticFiles(directory=_WEB_DIR, html=True), name="web")

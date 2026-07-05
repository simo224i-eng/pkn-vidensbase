"""Pydantic-modeller for API'ets request/response-bodies."""
from __future__ import annotations

from pydantic import BaseModel


class LoginRequest(BaseModel):
    password: str


class Kendelse(BaseModel):
    id: str  # sagsnummer eller link-baseret fallback — bruges i URL'en
    dato: str | None
    år: int | None
    opførelsesår: int | None
    titel: str
    link: str
    excerpt: str
    sagsnummer: str
    selskab: str
    udfald: str
    mangeltype: list[str]


class KendelseDetalje(Kendelse):
    tekst: str


class KendelserResponse(BaseModel):
    total: int
    items: list[Kendelse]


class FilterOptions(BaseModel):
    mangeltyper: list[str]
    selskaber: list[str]
    udfald: list[str]
    år_min: int
    år_max: int
    opførelsesår_min: int
    opførelsesår_max: int


class ChatMessage(BaseModel):
    rolle: str  # "bruger" | "assistent"
    tekst: str
    kilder: list[dict] | None = None


class AskRequest(BaseModel):
    spørgsmål: str
    historik: list[ChatMessage] = []
    filtre: dict | None = None
    kendelse_ids: list[str] | None = None  # afgræns til et forudvalgt sæt (fra søgning/filtre)


class NotatRequest(BaseModel):
    spørgsmål: str
    svar: str
    kilder: list[dict]


class StatsResponse(BaseModel):
    total: int
    medhold_pct: float
    antal_selskaber: int
    år_span: str
    per_år: list[dict]
    udfald_per_år: list[dict]
    top_mangeltyper: list[dict]
    top_selskaber: list[dict]
    medhold_rate_per_mangeltype: list[dict]

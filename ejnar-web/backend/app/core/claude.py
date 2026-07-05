"""Claude API-klient: blokerende kald + en streaming-generator til SSE.

Adapteret fra ejnar/shared.py's _llm/_llm_stream — samme retry-logik og
fejlhåndtering, men _llm_stream skrev til en Streamlit-placeholder; her
yielder stream_claude() tekst-deltaer, så en FastAPI-endpoint kan sende dem
videre som Server-Sent Events."""
from __future__ import annotations

import json
import time
from typing import Iterator

import requests

from ..config import get_settings

_API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-4-6"
HAIKU_MODEL = "claude-haiku-4-5-20251001"


class LLMFejl(RuntimeError):
    pass


def _headers(use_cache: bool = False) -> dict:
    key = get_settings().anthropic_api_key
    if not key:
        return {}
    h = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    if use_cache:
        h["anthropic-beta"] = "prompt-caching-2024-07-31"
    return h


def _body(prompt, max_tokens: int, stream: bool = False, model: str = DEFAULT_MODEL) -> dict:
    body = {"model": model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    if stream:
        body["stream"] = True
    return body


def llm(prompt, max_tokens: int = 2000, model: str = DEFAULT_MODEL) -> str:
    """Blokerende Claude-kald med retry. prompt kan være en str eller en liste
    af content-blokke (til prompt caching)."""
    key = get_settings().anthropic_api_key
    if not key:
        raise LLMFejl("ANTHROPIC_API_KEY er ikke sat på serveren.")

    use_cache = isinstance(prompt, list)
    headers = _headers(use_cache)
    body = _body(prompt, max_tokens, model=model)

    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(_API_URL, headers=headers, json=body, timeout=300)
            if r.status_code == 529 or r.status_code >= 500:
                last_err = f"{r.status_code} {r.reason}: {r.text[:300]}"
                time.sleep(2 ** attempt)
                continue
            if not r.ok:
                raise LLMFejl(f"{r.status_code} {r.reason}: {r.text[:500]}")
            return r.json()["content"][0]["text"]
        except requests.exceptions.Timeout:
            last_err = "Timeout – Claude svarede ikke inden for 5 minutter."
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            last_err = "Netværksfejl – kunne ikke nå Claude API."
            time.sleep(2 ** attempt)
    raise LLMFejl(last_err or "Ukendt fejl efter 3 forsøg.")


def llm_haiku(prompt: str, max_tokens: int = 400) -> str:
    """Hurtigt/billigt Haiku-kald til query-forståelse (klassifikation,
    query-omskrivning, auto-filtre, rerank-fallback). Fejler stille (tom
    streng) i stedet for at vælte hele søgningen — disse er kvalitetsboosts,
    ikke kritisk sti."""
    try:
        return llm(prompt, max_tokens=max_tokens, model=HAIKU_MODEL)
    except LLMFejl:
        return ""


def stream_claude(prompt, max_tokens: int = 3000, model: str = DEFAULT_MODEL) -> Iterator[str]:
    """Generator: yielder tekst-deltaer efterhånden som Claude streamer svaret.
    Sidste yield er ikke specielt markeret — kalderen samler selv den fulde
    tekst op (se rag.py's stream_answer)."""
    key = get_settings().anthropic_api_key
    if not key:
        raise LLMFejl("ANTHROPIC_API_KEY er ikke sat på serveren.")

    use_cache = isinstance(prompt, list)
    headers = _headers(use_cache)
    body = _body(prompt, max_tokens, stream=True, model=model)

    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(_API_URL, headers=headers, json=body, timeout=300, stream=True)
            if r.status_code == 529 or r.status_code >= 500:
                last_err = f"{r.status_code} {r.reason}"
                time.sleep(2 ** attempt)
                continue
            if not r.ok:
                raise LLMFejl(f"{r.status_code} {r.reason}: {r.text[:500]}")

            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    evt = json.loads(data_str)
                except json.JSONDecodeError:
                    continue
                if evt.get("type") == "content_block_delta":
                    chunk = evt.get("delta", {}).get("text", "")
                    if chunk:
                        yield chunk
            return
        except requests.exceptions.Timeout:
            last_err = "Timeout – Claude svarede ikke inden for 5 minutter."
            time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            last_err = "Netværksfejl – kunne ikke nå Claude API."
            time.sleep(2 ** attempt)
    raise LLMFejl(last_err or "Ukendt fejl efter 3 forsøg.")

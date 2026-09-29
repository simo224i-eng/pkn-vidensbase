"""Udskiftelig LLM-udbyder til Ejnar.

Ejnar kalder altid ``shared._llm`` / ``shared._llm_stream`` med et Claude-
modelnavn. Dette modul oversætter kaldet til den udbyder, der er valgt i
secrets, så en billig model kan kobles på uden kodeændringer.

Secrets (alle valgfri; uden dem bruges Anthropic som hidtil):

    LLM_PROVIDER    = "anthropic" | "deepseek" | "gemini" | "openai"
                      | "openrouter" | "groq" | "mistral" | "openai_compatible"
                      | "claude_cli"  (dit eget Claude-abonnement via Claude Code –
                                       KUN til personlig, lokal brug, se README)
    LLM_API_KEY     = "..."      # falder tilbage til <PROVIDER>_API_KEY
    LLM_MODEL       = "..."      # hovedmodel (svar, syntese)
    LLM_FAST_MODEL  = "..."      # hurtig model (query-omskrivning, rerank, HyDE)
    LLM_BASE_URL    = "..."      # kun nødvendig for openai_compatible
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Callable

import requests

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_MAIN = "claude-sonnet-4-6"
ANTHROPIC_FAST = "claude-haiku-4-5-20251001"

# base_url, standard-hovedmodel, standard-hurtigmodel, navn på egen key-secret
PRESETS: dict[str, tuple[str, str, str, str]] = {
    "deepseek": ("https://api.deepseek.com/v1", "deepseek-chat", "deepseek-chat", "DEEPSEEK_API_KEY"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "gemini-2.5-flash", "gemini-2.5-flash-lite", "GEMINI_API_KEY",
    ),
    "openai": ("https://api.openai.com/v1", "gpt-4.1-mini", "gpt-4.1-nano", "OPENAI_API_KEY"),
    "openrouter": (
        "https://openrouter.ai/api/v1",
        "deepseek/deepseek-chat", "google/gemini-2.5-flash-lite", "OPENROUTER_API_KEY",
    ),
    "groq": (
        "https://api.groq.com/openai/v1",
        "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "GROQ_API_KEY",
    ),
    "mistral": ("https://api.mistral.ai/v1", "mistral-medium-latest", "mistral-small-latest", "MISTRAL_API_KEY"),
    "openai_compatible": ("", "", "", "LLM_API_KEY"),
}


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    api_key: str
    base_url: str
    main_model: str
    fast_model: str

    @property
    def is_anthropic(self) -> bool:
        return self.provider == "anthropic"

    @property
    def is_cli(self) -> bool:
        return self.provider == "claude_cli"

    def resolve_model(self, requested: str | None) -> str:
        """Kortlæg et Claude-modelnavn fra kaldstedet til udbyderens model.

        Kaldesteder bruger Haiku til hurtige hjælpekald og Sonnet til svar; det
        bevares som en fast/main-opdeling på tværs af udbydere."""
        fast = "haiku" in (requested or "").lower()
        return self.fast_model if fast else self.main_model

    @property
    def label(self) -> str:
        if self.main_model == self.fast_model:
            return f"{self.provider} · {self.main_model}"
        return f"{self.provider} · {self.main_model} / {self.fast_model}"


def _default_secret(name: str) -> str:
    try:
        import streamlit as st

        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return str(value or os.environ.get(name, "")).strip()


def load_config(get_secret: Callable[[str], str] = _default_secret) -> LLMConfig:
    provider = (get_secret("LLM_PROVIDER") or "anthropic").strip().lower()
    if provider in ("claude", "anthropic"):
        return LLMConfig(
            provider="anthropic",
            api_key=get_secret("LLM_API_KEY") or get_secret("ANTHROPIC_API_KEY"),
            base_url=ANTHROPIC_URL,
            main_model=get_secret("LLM_MODEL") or ANTHROPIC_MAIN,
            fast_model=get_secret("LLM_FAST_MODEL") or ANTHROPIC_FAST,
        )
    if provider in ("claude_cli", "claude_code"):
        return LLMConfig(
            provider="claude_cli",
            api_key="",
            base_url=get_secret("LLM_CLAUDE_BIN") or "claude",
            main_model=get_secret("LLM_MODEL") or "sonnet",
            fast_model=get_secret("LLM_FAST_MODEL") or "haiku",
        )
    if provider not in PRESETS:
        raise ValueError(
            f"Ukendt LLM_PROVIDER '{provider}'. Gyldige: anthropic, " + ", ".join(PRESETS)
        )
    base_url, main, fast, key_name = PRESETS[provider]
    main_model = get_secret("LLM_MODEL") or main
    return LLMConfig(
        provider=provider,
        api_key=get_secret("LLM_API_KEY") or get_secret(key_name),
        base_url=(get_secret("LLM_BASE_URL") or base_url).rstrip("/"),
        main_model=main_model,
        fast_model=get_secret("LLM_FAST_MODEL") or fast or main_model,
    )


def is_configured(get_secret: Callable[[str], str] = _default_secret) -> bool:
    try:
        cfg = load_config(get_secret)
    except ValueError:
        return False
    if cfg.is_cli:
        return shutil.which(cfg.base_url) is not None
    return bool(cfg.api_key and cfg.main_model and cfg.base_url)


def missing_key_message(get_secret: Callable[[str], str] = _default_secret) -> str:
    try:
        cfg = load_config(get_secret)
    except ValueError as exc:
        return str(exc)
    if cfg.is_anthropic:
        return "Tilføj ANTHROPIC_API_KEY (eller LLM_PROVIDER + LLM_API_KEY) i Streamlit secrets."
    if cfg.is_cli:
        return f"Claude Code-CLI'en '{cfg.base_url}' blev ikke fundet. Installér den og log ind med 'claude'."
    if not cfg.base_url or not cfg.main_model:
        return "Sæt LLM_BASE_URL og LLM_MODEL i Streamlit secrets for openai_compatible."
    return f"Tilføj LLM_API_KEY i Streamlit secrets for udbyderen '{cfg.provider}'."


# ── Beskedformat ──────────────────────────────────────────────────────────────
def prompt_to_text(prompt) -> str:
    """Flad Anthropic content-blokke (bruges til prompt caching) ud til tekst."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, list):
        parts = []
        for block in prompt:
            if isinstance(block, dict):
                parts.append(str(block.get("text", "")))
            else:
                parts.append(str(block))
        return "\n\n".join(p for p in parts if p)
    return str(prompt)


def build_request(cfg: LLMConfig, prompt, max_tokens: int, model: str | None, stream: bool):
    """Returnér (url, headers, body) for det valgte API."""
    resolved = cfg.resolve_model(model)
    if cfg.is_anthropic:
        headers = {
            "x-api-key": cfg.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        if isinstance(prompt, list):
            headers["anthropic-beta"] = "prompt-caching-2024-07-31"
        body = {
            "model": resolved,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        headers = {
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        }
        if cfg.provider == "openrouter":
            headers["X-Title"] = "Ejnar"
        body = {
            "model": resolved,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt_to_text(prompt)}],
        }
    if stream:
        body["stream"] = True
    url = cfg.base_url if cfg.is_anthropic else f"{cfg.base_url}/chat/completions"
    return url, headers, body


def extract_text(cfg: LLMConfig, payload: dict) -> str:
    if cfg.is_anthropic:
        return "".join(
            b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text"
        )
    choices = payload.get("choices") or [{}]
    return (choices[0].get("message") or {}).get("content") or ""


def extract_delta(cfg: LLMConfig, event: dict) -> str:
    if cfg.is_anthropic:
        if event.get("type") == "content_block_delta":
            return event.get("delta", {}).get("text", "") or ""
        return ""
    choices = event.get("choices") or [{}]
    return (choices[0].get("delta") or {}).get("content") or ""


# ── Kald ──────────────────────────────────────────────────────────────────────
_RETRYABLE = {408, 429, 500, 502, 503, 504, 529}


def _post(cfg, prompt, max_tokens, model, stream):
    url, headers, body = build_request(cfg, prompt, max_tokens, model, stream)
    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(url, headers=headers, json=body, timeout=300, stream=stream)
            if r.status_code in _RETRYABLE:
                last_err = f"{cfg.provider} {r.status_code} {r.reason}: {r.text[:300]}"
                time.sleep(2 ** attempt)
                continue
            if not r.ok:
                raise RuntimeError(f"{cfg.provider} {r.status_code} {r.reason}: {r.text[:500]}")
            return r
        except requests.exceptions.Timeout:
            last_err = "Timeout – serveren svarede ikke inden for 5 minutter."
        except requests.exceptions.ConnectionError:
            last_err = f"Netværksfejl – kunne ikke nå {cfg.provider}-API'et."
        time.sleep(2 ** attempt)
    raise RuntimeError(last_err or "Ukendt fejl efter 3 forsøg.")


# ── Claude Code-CLI (personligt abonnement) ───────────────────────────────────
_CLI_SYSTEM = (
    "Du er sprogmodellen bag juraværktøjet Ejnar. Besvar brugerens prompt direkte "
    "og følg dens instruktioner. Du har ingen værktøjer."
)


def cli_command(cfg: LLMConfig, model: str | None, stream: bool) -> list[str]:
    cmd = [
        cfg.base_url, "-p",
        "--model", cfg.resolve_model(model),
        "--tools", "",                # ingen værktøjer: modellen kan kun svare
        "--strict-mcp-config",        # ingen MCP-servere
        "--disable-slash-commands",
        "--setting-sources", "",      # ignorér bruger-/projektindstillinger
        "--no-session-persistence",
        "--system-prompt", _CLI_SYSTEM,
    ]
    if stream:
        cmd += ["--output-format", "stream-json", "--verbose", "--include-partial-messages"]
    else:
        cmd += ["--output-format", "text"]
    return cmd


def _cli_env() -> dict:
    # Uden API-nøgle i miljøet bruger CLI'en abonnements-login'et i stedet for API'et.
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)
    return env


def _cli_complete(cfg: LLMConfig, prompt, model) -> str:
    r = subprocess.run(cli_command(cfg, model, stream=False), input=prompt_to_text(prompt),
                       capture_output=True, text=True, timeout=600, env=_cli_env())
    if r.returncode != 0:
        raise RuntimeError(f"claude_cli fejlede ({r.returncode}): {(r.stderr or r.stdout)[:500]}")
    return r.stdout.strip()


def _cli_stream(cfg: LLMConfig, prompt, model, on_text) -> str:
    proc = subprocess.Popen(cli_command(cfg, model, stream=True), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=_cli_env())
    proc.stdin.write(prompt_to_text(prompt))
    proc.stdin.close()
    full_text, final = "", None
    for line in proc.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "stream_event":
            inner = event.get("event") or {}
            delta = inner.get("delta") or {}
            if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                full_text += delta.get("text", "")
                if on_text:
                    on_text(full_text)
        elif event.get("type") == "result":
            final = event.get("result")
    proc.wait(timeout=30)
    if proc.returncode != 0 and not full_text:
        raise RuntimeError(f"claude_cli fejlede ({proc.returncode}): {proc.stderr.read()[:500]}")
    if final and final != full_text:
        full_text = final
        if on_text:
            on_text(full_text)
    return full_text


def complete(prompt, max_tokens: int = 2000, model: str | None = None, cfg: LLMConfig | None = None) -> str:
    cfg = cfg or load_config()
    if cfg.is_cli:
        return _cli_complete(cfg, prompt, model)
    return extract_text(cfg, _post(cfg, prompt, max_tokens, model, stream=False).json())


def stream(prompt, max_tokens: int = 2000, model: str | None = None, on_text=None,
           cfg: LLMConfig | None = None) -> str:
    """Stream svaret; ``on_text(fuld_tekst_indtil_nu)`` kaldes for hver delta."""
    cfg = cfg or load_config()
    if cfg.is_cli:
        return _cli_stream(cfg, prompt, model, on_text)
    r = _post(cfg, prompt, max_tokens, model, stream=True)
    full_text = ""
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            event = json.loads(data)
        except json.JSONDecodeError:
            continue
        chunk = extract_delta(cfg, event)
        if chunk:
            full_text += chunk
            if on_text:
                on_text(full_text)
    return full_text

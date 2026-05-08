"""Runtime-fetcher: hent fuld vejledningstekst fra retsinformation.dk."""
import json
import os
import re
import threading

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en;q=0.5",
}

_SESSION = requests.Session()
_SESSION.headers.update(_HEADERS)

_CACHE: dict[str, str | None] = {}
_LOCK = threading.Lock()

MIN_FULL_TEXT_LENGTH = 5_000


def _extract_text(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    content = (
        soup.find("div", class_=re.compile(r"teleLogText", re.I))
        or soup.find("div", class_=re.compile(r"teleLogContent", re.I))
        or soup.find("div", id="LovContent")
        or soup.find("div", class_=re.compile(r"teleContent", re.I))
        or soup.find("article")
        or soup.find("div", class_=re.compile(r"teleLog", re.I))
    )

    if not content:
        divs = soup.find_all("div", class_=re.compile(r"content|text|body", re.I))
        if divs:
            content = max(divs, key=lambda d: len(d.get_text()))
        else:
            content = soup.find("body")

    if not content:
        return None

    text = content.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)

    if len(text) < 200:
        return None
    return text


def fetch_vejledning(url: str) -> str | None:
    if not url:
        return None

    with _LOCK:
        if url in _CACHE:
            return _CACHE[url]

    try:
        resp = _SESSION.get(url, timeout=20)
        if resp.status_code != 200:
            with _LOCK:
                _CACHE[url] = None
            return None

        text = _extract_text(resp.text)
        with _LOCK:
            _CACHE[url] = text
        return text
    except Exception:
        with _LOCK:
            _CACHE[url] = None
        return None


def is_summary(tekst: str) -> bool:
    return len(tekst) < MIN_FULL_TEXT_LENGTH


def persist_to_json(json_path: str, vejl_id: str, full_text: str):
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for entry in data:
            if entry.get("id") == vejl_id:
                entry["tekst"] = full_text
                break
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

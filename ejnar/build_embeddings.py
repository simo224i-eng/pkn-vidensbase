#!/usr/bin/env python3
"""Embedding-builder for Ejnar (ejerskifteforsikrings-kendelser).

Kører uafhængigt af Streamlit. Gemmer fremskridt løbende, så afbrudte
kørsler kan genoptages. Voyage AI's voyage-multilingual-2 (samme model
som Harald) er primær — sæt VOYAGE_API_KEY i miljøet før kørsel.

Brug:
    cd ejnar
    VOYAGE_API_KEY=... python3 build_embeddings.py
"""
import csv
import io
import os
import re
import sys
import time
import zipfile

import numpy as np
import requests

VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")
MODEL = "voyage-multilingual-2"
DIM = 1024
BATCH_SIZE = 32
MAX_TEXT_LEN = 8000

ROOT = os.path.dirname(os.path.abspath(__file__))
EMBEDS_DIR = os.path.join(ROOT, "embeds")
PROGRESS_DIR = os.path.join(EMBEDS_DIR, "_progress")
os.makedirs(EMBEDS_DIR, exist_ok=True)
os.makedirs(PROGRESS_DIR, exist_ok=True)

CACHE_KEY = "ejnar_ejerskifteforsikring"
CSV_NAMES = ["ejnar_ejerskifteforsikring.csv"]   # tilføj flere hvis du splitter op


# ── HTML strip (samme regler som shared.py) ─────────────────────────────────
_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
    "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
    "&ndash;": "–", "&mdash;": "—",
    "&ldquo;": '"', "&rdquo;": '"',
    "&laquo;": "«", "&raquo;": "»",
    "&sect;": "§", "&#167;": "§",
}


def strip_html(text: str) -> str:
    text = re.sub(r"<h([2-4])[^>]*>(.*?)</h\1>", lambda m: f"\n## {m.group(2).strip()}\n", text, flags=re.I | re.S)
    text = re.sub(r"</p>|<br\s*/?>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in _ENTITIES.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out, prev_blank = [], False
    for ln in lines:
        if ln == "" and prev_blank:
            continue
        out.append(ln)
        prev_blank = (ln == "")
    return "\n".join(out).strip()


def kerneafsnit(tekst: str, max_tegn: int = 6000) -> str:
    """Foretræk klagens kerne + nævnets begrundelse/afgørelse."""
    sektioner = re.split(r"\n(#{2,3} .+)", tekst)
    dele = []
    for i, d in enumerate(sektioner):
        if d.startswith("## ") or d.startswith("### "):
            ind = sektioner[i + 1] if i + 1 < len(sektioner) else ""
            dele.append((d.lstrip("#").strip().lower(), ind.strip()))
    prio = [
        "klagen", "klagerens påstand",
        "selskabets påstand",
        "ankenævnets bemærkninger",
        "ankenævnets afgørelse",
        "begrundelse", "afgørelse",
    ]
    udtræk, brugt = [], 0
    for p in prio:
        for h, ind in dele:
            if p in h and ind:
                t = f"[{h.upper()}]\n{ind}"
                if brugt + len(t) <= max_tegn:
                    udtræk.append(t)
                    brugt += len(t)
    if udtræk:
        return "\n\n".join(udtræk)
    return tekst[-max_tegn:]


def indeks_tekst(titel: str, tekst: str, max_tegn: int = 4000) -> str:
    t = titel or ""
    return f"{t} {t} {t} {kerneafsnit(tekst or '', max_tegn=max_tegn)}"


# ── Voyage embedding ───────────────────────────────────────────────────────
def embed_batch(texts, retries: int = 4):
    url = "https://api.voyageai.com/v1/embeddings"
    headers = {"Authorization": f"Bearer {VOYAGE_API_KEY}", "Content-Type": "application/json"}
    payload = {"input": texts, "model": MODEL, "input_type": "document", "truncation": True}
    for attempt in range(retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.ok:
                data = r.json().get("data", [])
                return np.array([d["embedding"] for d in data], dtype=np.float32)
            if r.status_code == 429 and attempt < retries:
                wait = min(2 ** (attempt + 1), 30)
                print(f"  Rate limited – venter {wait}s…")
                time.sleep(wait)
                continue
            print(f"  HTTP {r.status_code}: {r.text[:200]}")
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            print(f"  ERROR: {e}")
            return None
    return None


# ── Data load ───────────────────────────────────────────────────────────────
def load_csv_or_zip(name: str) -> list[tuple[str, str]]:
    """Returnér liste af (titel, renset_tekst) fra ejnar_*.csv eller .csv.zip."""
    csv.field_size_limit(10_000_000)
    csv_path = os.path.join(ROOT, name)
    zip_path = csv_path + ".zip"

    rows: list[tuple[str, str]] = []

    def _read_reader(reader):
        for r in reader:
            tekst = strip_html(r.get("Tekst", ""))
            rows.append((r.get("Titel", ""), tekst))

    if os.path.exists(csv_path):
        with open(csv_path, newline="", encoding="utf-8") as f:
            _read_reader(csv.DictReader(f))
    elif os.path.exists(zip_path):
        with zipfile.ZipFile(zip_path) as z:
            inner = next(n for n in z.namelist() if n.endswith(".csv"))
            with z.open(inner) as src:
                _read_reader(csv.DictReader(io.TextIOWrapper(src, "utf-8")))
    else:
        print(f"  Springer over: {name} findes ikke")

    return rows


def load_all() -> list[tuple[str, str]]:
    seen_titles: set[str] = set()
    out: list[tuple[str, str]] = []
    for name in CSV_NAMES:
        for t, tx in load_csv_or_zip(name):
            key = (t or "")[:200]
            if key in seen_titles:
                continue
            seen_titles.add(key)
            out.append((t, tx))
    return out


# ── Build + save ───────────────────────────────────────────────────────────
def build(cache_key: str, data) -> bool:
    n = len(data)
    if n == 0:
        print(f"  {cache_key}: ingen data")
        return True

    fname = f"{cache_key}__voyage__{MODEL}__{n}.npz"
    out_path = os.path.join(EMBEDS_DIR, fname)

    if os.path.exists(out_path):
        try:
            arr = np.load(out_path)["arr_0"]
            if arr.shape[0] == n:
                print(f"  SKIP {cache_key}: findes allerede ({n} rækker)")
                return True
        except Exception:
            pass

    texts = [indeks_tekst(t, tx)[:MAX_TEXT_LEN] for t, tx in data]
    out = np.zeros((n, DIM), dtype=np.float32)
    start_batch = 0

    progress_path = os.path.join(PROGRESS_DIR, f"{cache_key}__partial.npz")
    if os.path.exists(progress_path):
        try:
            p = np.load(progress_path)
            parr, pdone = p["embeddings"], int(p["n_done"])
            if parr.shape == (n, DIM) and pdone > 0:
                if parr.dtype == np.float16:
                    parr = parr.astype(np.float32)
                out[:pdone] = parr[:pdone]
                start_batch = pdone // BATCH_SIZE
                print(f"  Genoptager {cache_key} fra batch {start_batch} ({pdone}/{n} done)")
        except Exception:
            pass

    n_batches = (n + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(start_batch, n_batches):
        s = b * BATCH_SIZE
        e = min(s + BATCH_SIZE, n)
        arr = embed_batch(texts[s:e])
        if arr is None:
            if s > 0:
                np.savez_compressed(progress_path,
                                    embeddings=out.astype(np.float16),
                                    n_done=np.array(s))
                print(f"  PARTIAL SAVE ved {s}/{n}")
            return False
        out[s:e] = arr
        if (b + 1) % 5 == 0 or b == n_batches - 1:
            print(f"  {cache_key}: {e}/{n} ({(b + 1) / n_batches * 100:.0f}%)")

    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms

    np.savez_compressed(out_path, out.astype(np.float16))
    print(f"  DONE {cache_key}: {n} rækker — {os.path.getsize(out_path) // 1024}KB")

    if os.path.exists(progress_path):
        os.remove(progress_path)
    return True


def main():
    if not VOYAGE_API_KEY:
        print("ERROR: VOYAGE_API_KEY ikke sat — eksportér nøglen først.")
        sys.exit(1)

    print(f"Voyage model: {MODEL} (dim {DIM})")
    print(f"Output: {EMBEDS_DIR}\n")

    print("Test af API-nøgle…")
    if embed_batch(["test"]) is None:
        print("API-nøgle virker ikke.")
        sys.exit(1)
    print("OK.\n")

    print("Indlæser kendelser…")
    data = load_all()
    print(f"  {len(data)} kendelser i alt\n")

    print("Bygger embeddings…")
    ok = build(CACHE_KEY, data)
    print()

    if ok:
        print("Færdig. Husk at committe ejnar/embeds/*.npz hvis du vil gøre dem")
        print("tilgængelige for Streamlit Cloud uden at bygge fra API ved start.")
    else:
        print("Build ufærdig — kør igen for at genoptage.")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Embedding-builder for Ejnar (ejerskifteforsikrings-kendelser).

Bygger CHUNK-NIVEAU embeddings: hver kendelse deles i overlappende
~1000-token-chunks (hver med titel-prefix), og hver chunk får sin egen
vektor. Det giver væsentligt bedre præcision på lange juridiske tekster
hvor kun ét afsnit er relevant for et givet spørgsmål.

Bruger Voyage-3-large (2024-modellen, bedre på dansk end multilingual-2).

Output-format (.npz med flere arrays):
    embeddings:   (N_chunks, DIM)    float16, L2-normaliserede
    chunk_to_doc: (N_chunks,)        int32, hvilket dokument hver chunk hører til
    n_docs:       scalar             total antal dokumenter

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
MODEL = "voyage-3-large"
DIM = 1024
BATCH_SIZE = 32

# Chunk-parametre
CHUNK_SIZE = 1000      # tokens (ca. 4000 tegn) — passer godt til afsnit i juridiske tekster
CHUNK_OVERLAP = 150    # tokens — sikrer at sætninger ikke skæres midt over
MAX_CHUNKS_PER_DOC = 80 # cap højt nok til at dække selv længste kendelse (74 chunks) → 0% tekst tabt

ROOT = os.path.dirname(os.path.abspath(__file__))
EMBEDS_DIR = os.path.join(ROOT, "embeds")
PROGRESS_DIR = os.path.join(EMBEDS_DIR, "_progress")
os.makedirs(EMBEDS_DIR, exist_ok=True)
os.makedirs(PROGRESS_DIR, exist_ok=True)

CACHE_KEY = "ejnar_ejerskifteforsikring"
CSV_NAMES = ["ejnar_ejerskifteforsikring.csv"]


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


# ── Chunking ───────────────────────────────────────────────────────────────
def chunk_text(titel: str, tekst: str,
               chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP,
               max_chunks: int = MAX_CHUNKS_PER_DOC) -> list[str]:
    """Del en kendelse i overlappende chunks med titel-prefix.

    Hvert chunk får titlen prependet, så embedding-modellen altid har
    kontekst til at forstå hvad chunk'en handler om — kritisk for
    præcis matching af spørgsmål til den rigtige kendelse."""
    titel = (titel or "").strip()
    tekst = (tekst or "").strip()
    if not tekst:
        return [titel] if titel else []

    # Vi bruger ord som proxy for tokens (1 ord ≈ 1.3 tokens i dansk).
    # CHUNK_SIZE = 1000 tokens ≈ 770 ord.
    chunk_words = int(chunk_size * 0.77)
    overlap_words = int(overlap * 0.77)

    ord_liste = tekst.split()
    if len(ord_liste) <= chunk_words:
        return [f"{titel}\n\n{tekst}" if titel else tekst]

    chunks = []
    start = 0
    while start < len(ord_liste) and len(chunks) < max_chunks:
        end = min(start + chunk_words, len(ord_liste))
        chunk_body = " ".join(ord_liste[start:end])
        if titel:
            chunks.append(f"{titel}\n\n{chunk_body}")
        else:
            chunks.append(chunk_body)
        if end >= len(ord_liste):
            break
        start += chunk_words - overlap_words

    return chunks


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
def load_csv_or_zip(name: str) -> list[tuple[str, str, str]]:
    """Returnér liste af (titel, renset_tekst, link) fra ejnar_*.csv eller .csv.zip."""
    csv.field_size_limit(10_000_000)
    csv_path = os.path.join(ROOT, name)
    zip_path = csv_path + ".zip"

    rows: list[tuple[str, str, str]] = []

    def _read_reader(reader):
        for r in reader:
            tekst = strip_html(r.get("Tekst", ""))
            rows.append((r.get("Titel", ""), tekst, r.get("Link", "")))

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


def load_all() -> list[tuple[str, str, str]]:
    """Dedup på LINK — SKAL matche appens load_data (dedup på Link), ellers
    forskydes chunk→doc-mappingen. (Tidligere titel-dedup droppede kendelser
    med enslydende titler og gjorde indekset ubrugeligt uden link-remap.)"""
    seen_links: set[str] = set()
    out: list[tuple[str, str, str]] = []
    for name in CSV_NAMES:
        for t, tx, l in load_csv_or_zip(name):
            if l in seen_links:
                continue
            seen_links.add(l)
            out.append((t, tx, l))
    return out


# ── Build + save ───────────────────────────────────────────────────────────
def build(cache_key: str, data) -> bool:
    n_docs = len(data)
    if n_docs == 0:
        print(f"  {cache_key}: ingen data")
        return True

    # 1. Chunk alle dokumenter, byg samtidig chunk-til-doc mapping
    print(f"  Chunker {n_docs} dokumenter (chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})…")
    all_chunks: list[str] = []
    chunk_to_doc: list[int] = []
    doc_links = [l for _, _, l in data]
    for doc_idx, (titel, tekst, _l) in enumerate(data):
        for c in chunk_text(titel, tekst):
            all_chunks.append(c)
            chunk_to_doc.append(doc_idx)
    n_chunks = len(all_chunks)
    print(f"  → {n_chunks} chunks ({n_chunks / max(n_docs, 1):.2f} chunks pr. dokument i snit)")

    fname = f"{cache_key}__voyage__{MODEL}__{n_docs}d_{n_chunks}c.npz"
    out_path = os.path.join(EMBEDS_DIR, fname)

    if os.path.exists(out_path):
        try:
            arr = np.load(out_path)
            if "embeddings" in arr.files and arr["embeddings"].shape[0] == n_chunks:
                print(f"  SKIP {cache_key}: findes allerede ({n_chunks} chunks)")
                return True
        except Exception:
            pass

    # 2. Embed i batches med resume-support
    out = np.zeros((n_chunks, DIM), dtype=np.float32)
    start_batch = 0

    progress_path = os.path.join(PROGRESS_DIR, f"{cache_key}__partial_chunked.npz")
    if os.path.exists(progress_path):
        try:
            p = np.load(progress_path)
            parr, pdone = p["embeddings"], int(p["n_done"])
            if parr.shape == (n_chunks, DIM) and pdone > 0:
                if parr.dtype == np.float16:
                    parr = parr.astype(np.float32)
                out[:pdone] = parr[:pdone]
                start_batch = pdone // BATCH_SIZE
                print(f"  Genoptager {cache_key} fra batch {start_batch} ({pdone}/{n_chunks} done)")
        except Exception:
            pass

    n_batches = (n_chunks + BATCH_SIZE - 1) // BATCH_SIZE
    t_start = time.time()
    for b in range(start_batch, n_batches):
        s = b * BATCH_SIZE
        e = min(s + BATCH_SIZE, n_chunks)
        arr = embed_batch(all_chunks[s:e])
        if arr is None:
            if s > 0:
                np.savez_compressed(progress_path,
                                    embeddings=out.astype(np.float16),
                                    n_done=np.array(s))
                print(f"  PARTIAL SAVE ved {s}/{n_chunks}")
            return False
        out[s:e] = arr
        if (b + 1) % 5 == 0 or b == n_batches - 1:
            elapsed = time.time() - t_start
            pct = (b + 1) / n_batches * 100
            eta = elapsed / (b + 1 - start_batch) * (n_batches - b - 1) if b + 1 > start_batch else 0
            print(f"  {cache_key}: {e}/{n_chunks} ({pct:.0f}%) — ETA {int(eta)}s")

    # 3. L2-normalisér
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms

    # 4. Gem som komprimeret .npz med chunk → doc mapping
    np.savez_compressed(out_path,
                        embeddings=out.astype(np.float16),
                        chunk_to_doc=np.array(chunk_to_doc, dtype=np.int32),
                        n_docs=np.array(n_docs, dtype=np.int32),
                        doc_links=np.array(doc_links, dtype=object))
    print(f"  DONE {cache_key}: {n_chunks} chunks fra {n_docs} docs — "
          f"{os.path.getsize(out_path) // 1024}KB")

    if os.path.exists(progress_path):
        os.remove(progress_path)
    return True


def main():
    if not VOYAGE_API_KEY:
        print("ERROR: VOYAGE_API_KEY ikke sat — eksportér nøglen først.")
        sys.exit(1)

    print(f"Voyage model: {MODEL} (dim {DIM})")
    print(f"Chunk-størrelse: {CHUNK_SIZE} tokens, overlap {CHUNK_OVERLAP}")
    print(f"Output: {EMBEDS_DIR}\n")

    print("Test af API-nøgle…")
    if embed_batch(["test"]) is None:
        print("API-nøgle virker ikke — eller modellen er ikke tilgængelig.")
        sys.exit(1)
    print("OK.\n")

    print("Indlæser kendelser…")
    data = load_all()
    print(f"  {len(data)} kendelser i alt\n")

    print("Bygger chunk-niveau embeddings…")
    ok = build(CACHE_KEY, data)
    print()

    if ok:
        print("Færdig. Husk at committe ejnar/embeds/*.npz hvis du vil gøre dem")
        print("tilgængelige for Streamlit Cloud uden at bygge fra API ved start.")
    else:
        print("Build ufærdig — kør igen for at genoptage.")


if __name__ == "__main__":
    main()

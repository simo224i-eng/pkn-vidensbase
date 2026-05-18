#!/usr/bin/env python3
"""Standalone embedding builder for PKN + MFKN.
Runs independently of Streamlit. Saves progress after each batch.
Usage: python3 build_all_embeddings.py
"""
import os, sys, csv, re, time, json, zipfile, io
import numpy as np
import requests

VOYAGE_API_KEY = os.environ.get("VOYAGE_API_KEY", "")
MODEL = "voyage-multilingual-2"
DIM = 1024
BATCH_SIZE = 32
MAX_TEXT_LEN = 8000
ROOT = os.path.dirname(os.path.abspath(__file__))
EMBEDS_DIR = os.path.join(ROOT, "embeds")
PROGRESS_DIR = os.path.join(ROOT, "embeds", "_progress")
os.makedirs(EMBEDS_DIR, exist_ok=True)
os.makedirs(PROGRESS_DIR, exist_ok=True)

# ── HTML stripping (replicated from shared.py) ─────────────────────────────
_ENTITIES = {
    "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
    "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
    "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
    "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
    "&sect;": "§", "&para;": "¶", "&copy;": "©", "&reg;": "®",
    "&#167;": "§",
}

def strip_html(text, preserve_headings=True):
    if preserve_headings:
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', lambda m: f'\n## {m.group(1).strip()}\n', text, flags=re.I|re.S)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: f'\n### {m.group(1).strip()}\n', text, flags=re.I|re.S)
        text = re.sub(r'<h[456][^>]*>(.*?)</h[456]>', lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I|re.S)
        text = re.sub(r'<p[^>]*>\s*<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>\s*</p>',
                      lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I|re.S)
        text = re.sub(r'</p>|<br\s*/?>|</div>', '\n', text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in _ENTITIES.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    if preserve_headings:
        lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.splitlines()]
        out_lines = []
        prev_blank = False
        for ln in lines:
            is_blank = ln == ""
            if is_blank and prev_blank:
                continue
            out_lines.append(ln)
            prev_blank = is_blank
        return '\n'.join(out_lines).strip()
    return re.sub(r"\s+", " ", text).strip()


_HTML_ENTITY_MAP = {
    '&aelig;': 'æ', '&oslash;': 'ø', '&aring;': 'å',
    '&Aelig;': 'Æ', '&Oslash;': 'Ø', '&Aring;': 'Å',
    '&nbsp;': ' ', '&amp;': '&', '&sect;': '§',
    '&quot;': '"', '&lt;': '<', '&gt;': '>',
    '&ndash;': '–', '&mdash;': '—',
}


def _decode_html_entities(s):
    for k, v in _HTML_ENTITY_MAP.items():
        if k in s:
            s = s.replace(k, v)
    return s


def _split_html_sections(html):
    text = _decode_html_entities(html)
    heading_re = re.compile(r'<(h[1-6])\b[^>]*>(.*?)</\1>', re.IGNORECASE | re.DOTALL)
    matches = list(heading_re.finditer(text))
    if not matches:
        return []
    dele = []
    for i, m in enumerate(matches):
        heading = re.sub(r'<[^>]+>', '', m.group(2))
        heading = re.sub(r'\s+', ' ', heading).strip().lower()
        if not heading or len(heading) > 200:
            continue
        heading = re.sub(r'^\d+(\.\d+)*\.?\s+', '', heading)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        indhold = re.sub(r'<[^>]+>', ' ', text[start:end])
        indhold = re.sub(r'\s+', ' ', indhold).strip()
        if indhold:
            dele.append((heading, indhold))
    return dele


def udtræk_kerneafsnit(tekst, max_tegn=8000):
    if not tekst:
        return ""
    if tekst.count('<') > 5 and '>' in tekst:
        dele = _split_html_sections(tekst)
    else:
        sektioner = re.split(r'\n(#{2,3} .+)', tekst)
        dele = []
        for i, del_ in enumerate(sektioner):
            if del_.startswith('## ') or del_.startswith('### '):
                indhold = sektioner[i + 1] if i + 1 < len(sektioner) else ""
                dele.append((del_.lstrip('#').strip().lower(), indhold.strip()))
    SKIP_PREFIKSER = (
        "sagens oplysninger", "sagsfremstilling", "sagens baggrund",
        "ejendommen og lokalplan", "ejendommen og planforhold",
        "forløbet før kommunens afgørelse", "forløbet forud for",
        "afgørelsen, der er klaget over", "afgørelsen der er klaget over",
        "den påklagede afgørelse", "tidligere afgørelse", "tidligere behandling",
    )

    def _er_faktuel(h):
        return any(h.startswith(p) or h == p.rstrip() for p in SKIP_PREFIKSER)

    def _er_kerne(h):
        return any(n in h for n in (
            "vurdering", "afgørelse", "begrundelse",
            "konklusion", "bemærkninger og afgørelse",
            "kompetence", "klageberettig", "klagefrist",
        ))

    relevante = [(i, h, c) for i, (h, c) in enumerate(dele)
                 if c and not _er_faktuel(h)]
    if not relevante:
        relevante = [(i, h, c) for i, (h, c) in enumerate(dele) if c]

    if relevante:
        kerne_idx = {i for i, h, c in relevante if _er_kerne(h)}
        valgte = set()
        brugt = 0
        for prioriter_kerne in (True, False):
            for i, h, c in relevante:
                if i in valgte:
                    continue
                if prioriter_kerne and i not in kerne_idx:
                    continue
                blok = f"[{h.upper()}]\n{c}"
                if brugt + len(blok) + 2 <= max_tegn:
                    valgte.add(i)
                    brugt += len(blok) + 2
                elif prioriter_kerne and not valgte:
                    valgte.add(i)
                    brugt = max_tegn
        if valgte:
            ud = []
            rest = max_tegn
            for i, h, c in relevante:
                if i not in valgte:
                    continue
                blok = f"[{h.upper()}]\n{c}"
                if len(blok) > rest:
                    blok = blok[:max(0, rest)]
                ud.append(blok)
                rest -= len(blok) + 2
                if rest <= 0:
                    break
            if ud:
                return "\n\n".join(ud)

    if tekst.count('<') > 5:
        stripped = re.sub(r'<[^>]+>', ' ', _decode_html_entities(tekst))
        stripped = re.sub(r'\s+', ' ', stripped).strip()
        return stripped[-max_tegn:]
    return tekst[-max_tegn:]


def byg_indeks_tekst(titel, tekst, max_tegn=4000):
    t = titel or ""
    kerne = udtræk_kerneafsnit(tekst or "", max_tegn=max_tegn)
    return f"{t} {t} {t} {kerne}"


# ── Voyage API ──────────────────────────────────────────────────────────────
def embed_batch(texts, retries=4):
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
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue
            print(f"  ERROR: HTTP {r.status_code}: {r.text[:200]}")
            return None
        except Exception as e:
            if attempt < retries:
                time.sleep(2 ** (attempt + 1))
                continue
            print(f"  ERROR: {e}")
            return None
    return None


# ── Data loading ────────────────────────────────────────────────────────────
def load_pkn():
    """Load all PKN CSVs, dedup by Link, return list of (titel, tekst)."""
    csv.field_size_limit(10_000_000)
    _LEGACY = {
        "pkn_vidensbase_fuld_tekst.csv": "Planloven, retlig (efter 1. februar 2017)",
        "pkn_miljoevurderingsloven_fuld_tekst.csv": "Miljøvurderingsloven",
    }
    rows = []
    seen = set()

    def _load_csv(path):
        if not path or not os.path.exists(path):
            return
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                link = row.get("Link", "")
                if link in seen:
                    continue
                seen.add(link)
                tekst = strip_html(row.get("Tekst", ""), preserve_headings=True)
                rows.append((row.get("Titel", ""), tekst))

    def _find(name):
        direct = os.path.join(ROOT, name)
        if os.path.exists(direct):
            return direct
        zpath = direct + ".zip"
        if os.path.exists(zpath):
            tmp = os.path.join("/tmp/pkn_build", name)
            if not os.path.exists(tmp):
                os.makedirs(os.path.dirname(tmp), exist_ok=True)
                with zipfile.ZipFile(zpath) as z:
                    for m in z.namelist():
                        if m.endswith(".csv"):
                            with z.open(m) as src, open(tmp, "wb") as dst:
                                dst.write(src.read())
                            break
            return tmp if os.path.exists(tmp) else ""
        return ""

    _load_csv(_find("pkn_vidensbase_fuld_tekst.csv"))
    import glob as _g
    names = (
        {os.path.basename(p) for p in _g.glob(os.path.join(ROOT, "pkn_*.csv"))} |
        {os.path.basename(p)[:-4] for p in _g.glob(os.path.join(ROOT, "pkn_*.csv.zip"))}
    )
    for name in sorted(names):
        if name == "pkn_vidensbase_fuld_tekst.csv":
            continue
        _load_csv(_find(name))

    return rows


def load_mfkn_category(zip_path):
    """Load one MFKN category from zip, return list of (titel, tekst)."""
    csv.field_size_limit(10_000_000)
    rows = []
    try:
        z = zipfile.ZipFile(zip_path)
        csvname = [m for m in z.namelist() if m.endswith('.csv')][0]
        reader = csv.DictReader(io.TextIOWrapper(z.open(csvname), 'utf-8'))
        for row in reader:
            tekst = strip_html(row.get("Tekst", ""), preserve_headings=True)
            rows.append((row.get("Titel", ""), tekst))
    except Exception as e:
        print(f"  Error loading {zip_path}: {e}")
    return rows


# ── Build + save embeddings ─────────────────────────────────────────────────
def build_embeddings(cache_key, data_rows):
    """Build embeddings for data_rows list of (titel, tekst).
    Saves progress after each batch. Returns True on success."""
    n = len(data_rows)
    if n == 0:
        print(f"  Skipping {cache_key}: no data")
        return True

    fname = f"{cache_key}__voyage__{MODEL}__{n}.npz"
    out_path = os.path.join(EMBEDS_DIR, fname)

    if os.path.exists(out_path):
        try:
            arr = np.load(out_path)["arr_0"]
            if arr.shape[0] == n:
                print(f"  SKIP {cache_key}: already exists ({n} rows)")
                return True
        except Exception:
            pass

    texts = [byg_indeks_tekst(t, tx)[:MAX_TEXT_LEN] for t, tx in data_rows]
    out = np.zeros((n, DIM), dtype=np.float32)
    start_batch = 0

    progress_path = os.path.join(PROGRESS_DIR, f"{cache_key}__partial.npz")
    if os.path.exists(progress_path):
        try:
            pdata = np.load(progress_path)
            parr = pdata["embeddings"]
            pdone = int(pdata["n_done"])
            if parr.shape == (n, DIM) and pdone > 0:
                if parr.dtype == np.float16:
                    parr = parr.astype(np.float32)
                out[:pdone] = parr[:pdone]
                start_batch = pdone // BATCH_SIZE
                print(f"  Resuming {cache_key} from batch {start_batch} ({pdone}/{n} done)")
        except Exception:
            pass

    n_batches = (n + BATCH_SIZE - 1) // BATCH_SIZE
    for b in range(start_batch, n_batches):
        start = b * BATCH_SIZE
        end = min(start + BATCH_SIZE, n)
        batch = texts[start:end]

        arr = embed_batch(batch)
        if arr is None:
            if start > 0:
                np.savez_compressed(progress_path,
                                    embeddings=out.astype(np.float16),
                                    n_done=np.array(start))
                print(f"  PARTIAL SAVE at {start}/{n} for {cache_key}")
            return False

        out[start:end] = arr

        if (b + 1) % 10 == 0 or b == n_batches - 1:
            pct = (b + 1) / n_batches * 100
            print(f"  {cache_key}: {end}/{n} ({pct:.0f}%)")

    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms

    out16 = out.astype(np.float16)
    np.savez_compressed(out_path, out16)
    fsize = os.path.getsize(out_path)
    print(f"  DONE {cache_key}: {n} rows, {fsize//1024}KB")

    if os.path.exists(progress_path):
        os.remove(progress_path)

    return True


# ── Main ────────────────────────────────────────────────────────────────────
def main():
    if not VOYAGE_API_KEY:
        print("ERROR: Set VOYAGE_API_KEY environment variable")
        sys.exit(1)

    print(f"Voyage model: {MODEL}, dim: {DIM}")
    print(f"Output dir: {EMBEDS_DIR}")
    print()

    # Test API key first
    print("Testing Voyage API key...")
    test = embed_batch(["test"])
    if test is None:
        print("FATAL: Voyage API key is invalid or has no credits")
        sys.exit(1)
    print(f"API key works! Test embedding shape: {test.shape}")
    print()

    all_ok = True

    # 1. PKN
    print("=" * 60)
    print("BUILDING PKN EMBEDDINGS")
    print("=" * 60)
    pkn_rows = load_pkn()
    print(f"Loaded {len(pkn_rows)} PKN documents")
    if not build_embeddings("pkn", pkn_rows):
        print("PKN build incomplete (will resume on next run)")
        all_ok = False

    # 2. MFKN (31 categories)
    print()
    print("=" * 60)
    print("BUILDING MFKN EMBEDDINGS")
    print("=" * 60)
    import glob as _g
    mfkn_zips = sorted(_g.glob(os.path.join(ROOT, "mfkn_*.csv.zip")))
    print(f"Found {len(mfkn_zips)} MFKN categories")

    for i, zpath in enumerate(mfkn_zips):
        stem = os.path.basename(zpath).replace(".csv.zip", "")
        print(f"\n[{i+1}/{len(mfkn_zips)}] {stem}")
        mfkn_rows = load_mfkn_category(zpath)
        print(f"  {len(mfkn_rows)} documents")
        if not build_embeddings(f"mfkn_{stem}", mfkn_rows):
            print(f"  {stem} build incomplete (will resume on next run)")
            all_ok = False

    print()
    print("=" * 60)
    if all_ok:
        print("ALL EMBEDDINGS BUILT SUCCESSFULLY!")
        # Clean up progress dir
        import shutil
        if os.path.exists(PROGRESS_DIR):
            shutil.rmtree(PROGRESS_DIR)
            print("Cleaned up progress files.")
    else:
        print("SOME BUILDS INCOMPLETE. Run again to resume.")
    print("=" * 60)

    # List output files
    import glob as _g2
    files = sorted(_g2.glob(os.path.join(EMBEDS_DIR, "*.npz")))
    total_size = sum(os.path.getsize(f) for f in files)
    print(f"\nTotal: {len(files)} files, {total_size // (1024*1024)}MB")
    for f in files:
        print(f"  {os.path.basename(f):70s} {os.path.getsize(f)//1024:>6}KB")


if __name__ == "__main__":
    main()

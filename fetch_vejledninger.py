"""
Hent vejledningstekster fra retsinformation.dk og andre kilder.

Bruges typisk via GitHub Actions (.github/workflows/fetch-vejledninger.yml)
men kan også køres lokalt:

    pip install requests beautifulsoup4 trafilatura pdfplumber
    python fetch_vejledninger.py [--force] [--only retsinformation]

Default: kun vejledninger uden 'tekst' eller med tekst < MIN_REAL_LEN
hentes. Med --force genhentes alt.
"""
import argparse
import json
import os
import re
import sys
import time
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installer dependencies først:")
    print("  pip install requests beautifulsoup4 trafilatura pdfplumber")
    sys.exit(1)

try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

ROOT = os.path.dirname(os.path.abspath(__file__))
VEJL_DIR = os.path.join(ROOT, "vejledninger")

# Tekster kortere end dette betragtes som resume / placeholder og genhentes
MIN_REAL_LEN = 8000

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en;q=0.5",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def _clean(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_html(url: str) -> str | None:
    """Hent og udtræk hovedtekst fra en HTML-side. Bruger trafilatura
    primært (purpose-built for content extraction) med BeautifulSoup som
    fallback."""
    try:
        resp = SESSION.get(url, timeout=30, allow_redirects=True)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code}")
            return None
        html = resp.text
    except Exception as e:
        print(f"    Henter-fejl: {e}")
        return None

    if HAS_TRAFILATURA:
        try:
            extracted = trafilatura.extract(
                html,
                include_comments=False,
                include_tables=True,
                favor_recall=True,
                deduplicate=True,
            )
            if extracted and len(extracted) > 500:
                return _clean(extracted)
        except Exception as e:
            print(f"    trafilatura-fejl: {e}")

    # Fallback: BeautifulSoup heuristik
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        candidates = []
        for selector in [
            ("div", {"id": "LovContent"}),
            ("article", {}),
            ("main", {}),
            ("div", {"class": re.compile(r"(content|tekst|body|text|article|main)", re.I)}),
        ]:
            for el in soup.find_all(selector[0], selector[1] if selector[1] else True):
                text = el.get_text(separator="\n", strip=True)
                if len(text) > 500:
                    candidates.append((len(text), text))

        if not candidates:
            body = soup.find("body")
            if body:
                candidates.append((0, body.get_text(separator="\n", strip=True)))

        if candidates:
            candidates.sort(reverse=True)
            return _clean(candidates[0][1])
    except Exception as e:
        print(f"    BS4-fejl: {e}")

    return None


def fetch_pdf(url: str) -> str | None:
    """Hent og udtræk tekst fra PDF."""
    if not HAS_PDFPLUMBER:
        print("    pdfplumber ikke installeret")
        return None
    try:
        resp = SESSION.get(url, timeout=60)
        if resp.status_code != 200:
            return None

        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(resp.content)
            tmp_path = f.name

        text_parts = []
        try:
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        finally:
            os.unlink(tmp_path)

        text = "\n\n".join(text_parts)
        return _clean(text) if len(text) > 200 else None
    except Exception as e:
        print(f"    PDF-fejl: {e}")
        return None


def process_vejledning(vejl: dict) -> str | None:
    """Prøv at hente fuld tekst for en vejledning. Returnerer ny tekst
    eller None ved fejl."""
    url = vejl.get("url") or ""
    pdf_url = vejl.get("pdf_url") or ""

    # Direkte PDF-URL
    if url.lower().endswith(".pdf"):
        text = fetch_pdf(url)
        if text:
            return text

    # HTML-URL (alle domæner)
    if url and url.startswith("http"):
        text = fetch_html(url)
        if text:
            return text

    # Eksplicit pdf_url-felt som fallback
    if pdf_url and pdf_url.startswith("http"):
        text = fetch_pdf(pdf_url)
        if text:
            return text

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Genhent også vejledninger der allerede har lang tekst")
    parser.add_argument("--only", default=None,
                        help="Behandl kun vejledninger hvor URL indeholder denne streng")
    args = parser.parse_args()

    if not HAS_TRAFILATURA:
        print("ADVARSEL: trafilatura ikke installeret — falder tilbage til BS4")
    if not HAS_PDFPLUMBER:
        print("ADVARSEL: pdfplumber ikke installeret — PDF'er kan ikke hentes")

    json_files = []
    for fname in sorted(os.listdir(VEJL_DIR)):
        if fname.endswith("_vejledninger.json"):
            json_files.append(os.path.join(VEJL_DIR, fname))

    if not json_files:
        print(f"Ingen *_vejledninger.json filer i {VEJL_DIR}")
        return 1

    total_fetched = 0
    total_skipped = 0
    total_failed = 0
    total_no_url = 0

    for json_path in json_files:
        print(f"\n{'='*60}")
        print(f"Behandler: {os.path.basename(json_path)}")
        print(f"{'='*60}")

        with open(json_path, "r", encoding="utf-8") as f:
            vejledninger = json.load(f)

        changed = False
        for i, vejl in enumerate(vejledninger):
            titel = vejl.get("titel", "Ukendt")
            url = vejl.get("url") or ""
            existing = vejl.get("tekst") or ""

            print(f"\n  [{i+1}/{len(vejledninger)}] {titel[:70]}")

            if args.only and args.only not in url:
                print(f"    – Skipped (--only {args.only})")
                continue

            if not args.force and len(existing) >= MIN_REAL_LEN:
                print(f"    ✓ Har allerede fuld tekst ({len(existing)} tegn)")
                total_skipped += 1
                continue

            if not url:
                print(f"    – Ingen URL — beholder resume ({len(existing)} tegn)")
                total_no_url += 1
                continue

            print(f"    Henter {urlparse(url).netloc}…")
            text = process_vejledning(vejl)

            if text and len(text) > len(existing):
                # Bevar resumé så vi har en fallback hvis fetch'en blev dårlig
                if existing and "tekst_resume" not in vejl:
                    vejl["tekst_resume"] = existing
                vejl["tekst"] = text
                vejl["tekst_kilde"] = url
                changed = True
                total_fetched += 1
                print(f"    ✓ Hentet! ({len(text):,} tegn)".replace(",", "."))
            else:
                total_failed += 1
                print(f"    ✗ Kunne ikke hente — beholder resume ({len(existing)} tegn)")

            time.sleep(1.5)

        if changed:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(vejledninger, f, ensure_ascii=False, indent=2)
            print(f"\n  Gemt: {json_path}")

    print(f"\n{'='*60}")
    print(f"RESULTAT:")
    print(f"  Hentet:    {total_fetched}")
    print(f"  Skippet:   {total_skipped} (havde allerede fuld tekst)")
    print(f"  Uden URL:  {total_no_url}")
    print(f"  Fejlet:    {total_failed}")
    print(f"{'='*60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

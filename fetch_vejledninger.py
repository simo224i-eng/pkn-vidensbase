"""
Hent vejledningstekster fra retsinformation.dk og gem i JSON-filer.

Kør dette script lokalt (ikke i sandbox) for at populere vejledninger/*.json
med den fulde tekst fra hver vejledning.

Brug:
    python fetch_vejledninger.py

Kræver: requests, beautifulsoup4
    pip install requests beautifulsoup4
"""
import json
import os
import re
import sys
import time

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Installer dependencies først:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)

ROOT = os.path.dirname(os.path.abspath(__file__))
VEJL_DIR = os.path.join(ROOT, "vejledninger")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en;q=0.5",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch_retsinformation(url: str) -> str | None:
    """Hent tekst fra retsinformation.dk."""
    try:
        resp = SESSION.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"    HTTP {resp.status_code} for {url}")
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        content = soup.find("div", class_="444teleLogText") or \
                  soup.find("div", class_="444teleLogContent") or \
                  soup.find("div", id="LovContent") or \
                  soup.find("div", class_="444teleContent") or \
                  soup.find("article") or \
                  soup.find("div", class_="444teleLog")

        if not content:
            content_divs = soup.find_all("div", class_=re.compile(r"content|text|body", re.I))
            if content_divs:
                content = max(content_divs, key=lambda d: len(d.get_text()))
            else:
                content = soup.find("body")

        if not content:
            return None

        text = content.get_text(separator="\n", strip=True)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        if len(text) < 100:
            return None

        return text

    except Exception as e:
        print(f"    Fejl: {e}")
        return None


def fetch_pdf(url: str) -> str | None:
    """Hent tekst fra PDF (kræver pdfplumber)."""
    try:
        import pdfplumber
    except ImportError:
        print("    Skipping PDF - installer pdfplumber: pip install pdfplumber")
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
        with pdfplumber.open(tmp_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        os.unlink(tmp_path)

        text = "\n\n".join(text_parts)
        if len(text) < 100:
            return None
        return text

    except Exception as e:
        print(f"    PDF-fejl: {e}")
        return None


def process_vejledning(vejl: dict) -> str | None:
    """Forsøg at hente tekst for en vejledning."""
    url = vejl.get("url")
    pdf_url = vejl.get("pdf_url")

    if url and "retsinformation.dk" in url:
        print(f"    Henter fra retsinformation.dk...")
        text = fetch_retsinformation(url)
        if text:
            return text

    if pdf_url:
        print(f"    Henter PDF...")
        text = fetch_pdf(pdf_url)
        if text:
            return text

    if url and url.endswith(".pdf"):
        print(f"    Henter PDF fra URL...")
        text = fetch_pdf(url)
        if text:
            return text

    return None


def main():
    json_files = [
        os.path.join(VEJL_DIR, "pkn_vejledninger.json"),
        os.path.join(VEJL_DIR, "mfkn_vejledninger.json"),
    ]

    for pattern in os.listdir(VEJL_DIR):
        if pattern.endswith("_vejledninger.json"):
            full = os.path.join(VEJL_DIR, pattern)
            if full not in json_files:
                json_files.append(full)

    total_fetched = 0
    total_skipped = 0
    total_failed = 0

    for json_path in json_files:
        if not os.path.exists(json_path):
            continue

        print(f"\n{'='*60}")
        print(f"Behandler: {os.path.basename(json_path)}")
        print(f"{'='*60}")

        with open(json_path, "r", encoding="utf-8") as f:
            vejledninger = json.load(f)

        changed = False
        for i, vejl in enumerate(vejledninger):
            titel = vejl.get("titel", "Ukendt")
            print(f"\n  [{i+1}/{len(vejledninger)}] {titel[:60]}")

            if vejl.get("tekst"):
                print(f"    ✓ Tekst allerede hentet ({len(vejl['tekst'])} tegn)")
                total_skipped += 1
                continue

            text = process_vejledning(vejl)
            if text:
                vejl["tekst"] = text
                changed = True
                total_fetched += 1
                print(f"    ✓ Hentet! ({len(text)} tegn)")
            else:
                total_failed += 1
                print(f"    ✗ Kunne ikke hentes")

            time.sleep(2)

        if changed:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(vejledninger, f, ensure_ascii=False, indent=2)
            print(f"\n  Gemt opdateret fil: {json_path}")

    print(f"\n{'='*60}")
    print(f"RESULTAT:")
    print(f"  Hentet:   {total_fetched}")
    print(f"  Skippet:  {total_skipped} (allerede hentet)")
    print(f"  Fejlet:   {total_failed}")
    print(f"{'='*60}")

    if total_failed > 0:
        print("\nTip: Vejledninger der fejlede kan evt. hentes manuelt fra:")
        print("  - retsinformation.dk (søg på vejledningsnr.)")
        print("  - mst.dk (Miljøstyrelsens publikationer)")
        print("  - planinfo.dk (planlægningsvejledninger)")


if __name__ == "__main__":
    main()

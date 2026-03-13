"""
PKN Scraper – henter afgørelser fra pkn.naevneneshus.dk API pr. kategori
og gemmer til en CSV-fil med en Retsomraade-kolonne.

Brug:
  python3 scrape_pkn.py --id "5aaf6311-0832-4f06-b114-2ac68eb0d6d4" \
                        --navn "Planloven, landzone (efter 1. februar 2017)" \
                        [--cookie "MY_SESSION=..."]

Kendte kategori-IDs (fra PKN søge-UI):
  Planloven, retlig (efter 1. februar 2017):  hent fra browser-cURL
  Planloven, landzone (efter 1. februar 2017): 5aaf6311-0832-4f06-b114-2ac68eb0d6d4
  Miljøvurderingsloven:                        hent fra browser-cURL
  Planloven, VVM:                              hent fra browser-cURL
  Planloven, retlig (før 1. februar 2017):     hent fra browser-cURL
  Planloven, landzone (før 1. februar 2017):   hent fra browser-cURL
  Aktindsigt:                                  hent fra browser-cURL
  Sommerhusloven:                              hent fra browser-cURL

Kræver: pip install requests beautifulsoup4
"""

import argparse
import csv
import html
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL  = "https://pkn.naevneneshus.dk"
API_URL   = f"{BASE_URL}/api/search"
PAGE_SIZE = 50
SLEEP_SEC = 0.4


def csv_filnavn(kategori_navn: str) -> str:
    """Lav et sikkert filnavn ud fra kategorinavnet."""
    navn = kategori_navn.lower()
    navn = re.sub(r"[^a-z0-9æøå]+", "_", navn).strip("_")
    navn = navn.replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    return f"pkn_{navn}.csv"


def strip_html(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t))
    t = html.unescape(t)
    return re.sub(r"\s{2,}", " ", t).strip()


def fetch_full_text(url: str, session: requests.Session) -> str:
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for selector in ["article", "main .content", ".afgoerelse-tekst",
                         "main", ".content", "#content"]:
            el = soup.select_one(selector)
            if el:
                for tag in el.select("nav, footer, header, script, style, .breadcrumb"):
                    tag.decompose()
                tekst = strip_html(el.get_text(separator=" ", strip=True))
                if len(tekst) > 200:
                    return tekst
        body = soup.find("body")
        return strip_html(body.get_text(separator=" ", strip=True)) if body else ""
    except Exception as e:
        print(f"  !! Fejl ved hentning af {url}: {e}")
        return ""


def search_kategori(session: requests.Session, kategori_id: str,
                    kategori_navn: str, headers: dict) -> list[dict]:
    """Hent alle afgørelser for én kategori fra søge-API'et."""
    kategori_obj = [{"id": kategori_id, "title": kategori_navn}]
    results = []
    skip = 0

    payload = {"categories": kategori_obj, "query": "", "sort": "Descending",
                "types": [], "skip": 0, "size": 1}
    try:
        r = session.post(API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Fejl ved første API-kald: {e}")
        sys.exit(1)

    total = (data.get("total") or data.get("count") or
             data.get("totalCount") or data.get("numberOfHits") or 0)
    print(f"API: {total} afgørelser i kategorien '{kategori_navn}'")

    while skip < total:
        payload = {"categories": kategori_obj, "query": "", "sort": "Descending",
                   "types": [], "skip": skip, "size": PAGE_SIZE}
        try:
            r = session.post(API_URL, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"  Fejl ved skip={skip}: {e}")
            time.sleep(2)
            continue

        hits = data.get("results", data.get("hits", data.get("items", [])))
        if not hits:
            break

        for h in hits:
            afgørelse_id = h.get("id", h.get("afgoerelseId", ""))
            link = (h.get("url") or h.get("link") or
                    f"{BASE_URL}/afgoerelse/{afgørelse_id}")
            results.append({
                "id":    afgørelse_id,
                "Titel": h.get("title", h.get("titel", "")),
                "Dato":  (h.get("date", h.get("dato", "")) or "")[:10],
                "Link":  link,
            })

        skip += PAGE_SIZE
        pct = min(skip, total) / total * 100
        print(f"  Indekseret {min(skip, total)}/{total} ({pct:.0f}%)…", end="\r")
        time.sleep(SLEEP_SEC)

    print(f"\nFandt {len(results)} afgørelser via API")
    return results


def load_existing_csv(path: Path) -> dict[str, dict]:
    existing = {}
    if not path.exists():
        return existing
    csv.field_size_limit(10_000_000)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            existing[row["Link"]] = row
    print(f"Eksisterende CSV ({path.name}): {len(existing)} rækker")
    return existing


def append_to_csv(path: Path, rows: list[dict]) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Dato", "Titel", "Link", "Tekst", "Retsomraade"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Scraper til PKN-afgørelser pr. kategori")
    parser.add_argument("--id",    required=True, help="Kategori-ID fra PKN API")
    parser.add_argument("--navn",  required=True, help="Kategorinavn (bruges i CSV og filnavn)")
    parser.add_argument("--cookie", default="",   help="MY_SESSION=... cookie-streng fra browser")
    args = parser.parse_args()

    csv_path = Path(csv_filnavn(args.navn))
    print(f"Output: {csv_path}")

    headers = {
        "Accept":       "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/116.0.0.0 Safari/537.36",
        "Referer":      "https://pkn.naevneneshus.dk/soeg",
    }
    if args.cookie:
        headers["Cookie"] = args.cookie

    session = requests.Session()
    session.headers.update({"User-Agent": headers["User-Agent"]})

    # 1. Hent alle afgørelser for kategorien
    alle = search_kategori(session, args.id, args.navn, headers)

    # 2. Sammenlign med eksisterende CSV
    eksisterende = load_existing_csv(csv_path)
    nye = [a for a in alle if a["Link"] not in eksisterende]
    print(f"Nye afgørelser der mangler: {len(nye)}")

    if not nye:
        print("Ingen nye afgørelser – CSV er up to date.")
        return

    # 3. Hent fuld tekst og gem
    ny_batch = []
    for idx, a in enumerate(nye, 1):
        print(f"  [{idx}/{len(nye)}] {a['Titel'][:70]}…")
        tekst = fetch_full_text(a["Link"], session)
        if not tekst:
            print(f"    → Ingen tekst, springer over")
            continue
        ny_batch.append({
            "Dato":       a["Dato"],
            "Titel":      a["Titel"],
            "Link":       a["Link"],
            "Tekst":      tekst,
            "Retsomraade": args.navn,
        })
        time.sleep(SLEEP_SEC)

        if len(ny_batch) % 100 == 0:
            append_to_csv(csv_path, ny_batch)
            print(f"  → Gemt {len(ny_batch)} rækker løbende")
            ny_batch = []

    if ny_batch:
        append_to_csv(csv_path, ny_batch)

    print(f"\nFærdig! Tilføjede op til {len(nye)} nye afgørelser til {csv_path}")
    print("Husk at zippe og uploade til Streamlit Cloud.")


if __name__ == "__main__":
    main()

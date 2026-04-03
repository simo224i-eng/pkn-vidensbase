"""
MFKN Scraper – henter afgørelser fra mfkn.naevneneshus.dk API pr. kategori
og gemmer til en CSV-fil.

Brug:
  python3 scrape_mfkn.py --liste --cookie "MY_SESSION=..."
  python3 scrape_mfkn.py --kategori "Vandforsyningsloven" --cookie "MY_SESSION=..."
  python3 scrape_mfkn.py --alle --cookie "MY_SESSION=..."

Kræver: pip install requests pandas
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from pathlib import Path

import requests

BASE_URL  = "https://mfkn.naevneneshus.dk"
API_URL   = f"{BASE_URL}/api/search"
PAGE_SIZE = 100
SLEEP_MIN = 0.8
SLEEP_MAX = 2.0


def csv_filnavn(kategori_navn: str) -> str:
    navn = kategori_navn.lower()
    navn = navn.replace("–", "-").replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    navn = re.sub(r"[^a-z0-9]+", "_", navn).strip("_")
    return f"mfkn_{navn}.csv"


def hent_kategorier(session: requests.Session, headers: dict) -> list[dict]:
    """Hent alle kategorier fra API – returnerer liste med category, count og id."""
    payload = {
        "categories": [],
        "query": "",
        "sort": "Descending",
        "types": [],
        "skip": 0,
        "size": 1,
    }
    try:
        r = session.post(API_URL, headers=headers, json=payload, timeout=20)
        if r.status_code != 200:
            print(f"Serverfejl ({r.status_code}). Tjek din cookie.")
            return []
        data = r.json()
        return data.get("categoryCounts", [])
    except Exception as e:
        print(f"Fejl ved hentning af kategorier: {e}")
        return []


def load_existing_csv(path: Path) -> set[str]:
    """Returnerer sæt af allerede hentede links."""
    if not path.exists():
        return set()
    csv.field_size_limit(10_000_000)
    links = set()
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            links.add(row.get("Link", ""))
    return links


def append_to_csv(path: Path, rows: list[dict]) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["Dato", "Titel", "Link", "Tekst", "Retsomraade"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def scrape_kategori(session: requests.Session, kategori_navn: str,
                    kategori_id: str, headers: dict) -> None:
    """Scrape én kategori og gem til CSV. Teksten hentes direkte fra body-feltet."""
    csv_path = Path(csv_filnavn(kategori_navn))
    eksisterende = load_existing_csv(csv_path)

    print(f"\n{'='*60}")
    print(f"Kategori: {kategori_navn}")
    print(f"Output:   {csv_path}  (eksisterende: {len(eksisterende)})")
    print(f"{'='*60}")

    base_payload = {
        "categories": [{"id": kategori_id, "title": kategori_navn}],
        "query": "",
        "sort": "Descending",
        "types": [],
    }

    alle_sager = []
    skip = 0

    while True:
        payload = {**base_payload, "skip": skip, "size": PAGE_SIZE}

        try:
            r = session.post(API_URL, headers=headers, json=payload, timeout=20)
            if r.status_code != 200:
                print(f"\nServerfejl ({r.status_code}) ved skip={skip}. Cookie udløbet?")
                break
            data = r.json()
        except Exception as e:
            print(f"\nFejl ved skip={skip}: {e}")
            time.sleep(5)
            continue

        items = data.get("publications", [])
        if not items:
            break

        for i in items:
            link = f"{BASE_URL}/afgoerelse/{i.get('id', '')}"
            if link in eksisterende:
                continue
            alle_sager.append({
                "Dato":        (i.get("date", "") or "")[:10],
                "Titel":       i.get("title", ""),
                "Link":        link,
                "Tekst":       i.get("body", ""),
                "Retsomraade": kategori_navn,
            })

        print(f"  Hentet {skip}–{skip + len(items)} / {data.get('totalCount', '?')}…",
              end="\r")
        skip += PAGE_SIZE
        time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))

        # Gem løbende per 200
        if len(alle_sager) >= 200:
            append_to_csv(csv_path, alle_sager)
            eksisterende.update(r["Link"] for r in alle_sager)
            alle_sager = []

    if alle_sager:
        append_to_csv(csv_path, alle_sager)

    print(f"\nFærdig med '{kategori_navn}'!")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper til MFKN-afgørelser (mfkn.naevneneshus.dk)")
    parser.add_argument("--kategori", default="",
                        help="Kategorinavn, fx 'Vandforsyningsloven'")
    parser.add_argument("--alle", action="store_true",
                        help="Scrape ALLE kategorier")
    parser.add_argument("--liste", "--list", action="store_true",
                        help="Vis tilgængelige kategorier og afslut")
    parser.add_argument("--cookie", default="",
                        help="MY_SESSION=... cookie fra browser (påkrævet)")
    args = parser.parse_args()

    if not args.cookie:
        print("FEJL: Angiv --cookie med din MY_SESSION cookie.")
        print("Åbn DevTools → Application → Cookies → mfkn.naevneneshus.dk")
        sys.exit(1)

    cookie_val = args.cookie
    if not cookie_val.startswith("MY_SESSION="):
        cookie_val = f"MY_SESSION={cookie_val}"

    headers = {
        "Accept":       "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Cookie":       cookie_val,
        "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/116.0.0.0 Safari/537.36",
        "Origin":       BASE_URL,
        "Referer":      f"{BASE_URL}/soeg?s=&sort=desc",
    }

    session = requests.Session()
    session.headers.update({"User-Agent": headers["User-Agent"]})

    print("Henter kategorier fra MFKN API…")
    kategorier = hent_kategorier(session, headers)
    if not kategorier:
        print("Kunne ikke hente kategorier. Tjek din cookie.")
        sys.exit(1)

    # Vis kategoriliste
    print(f"\n{'Kategori':<45} {'Antal':>8}  {'ID'}")
    print("-" * 90)
    for k in sorted(kategorier, key=lambda x: x.get("count", 0), reverse=True):
        kid = k.get("id", "MANGLER")
        print(f"  {k['category']:<43} {k.get('count', 0):>6}  {kid}")
    print(f"\n  I alt: {sum(k.get('count', 0) for k in kategorier):>6}")

    if args.liste:
        return

    # Check at ID'er er tilgængelige
    mangler_id = [k["category"] for k in kategorier if "id" not in k]
    if mangler_id:
        print(f"\nADVARSEL: Disse kategorier mangler ID i API-svaret: {mangler_id}")
        print("API returnerer ikke ID'er i categoryCounts.")
        print("\nTip: Gå til mfkn.naevneneshus.dk/soeg, klik en kategori og")
        print("kopiér UUID'et fra URL'en (?categories=UUID) og send til Simon.")
        sys.exit(1)

    if args.alle:
        for k in sorted(kategorier, key=lambda x: x.get("count", 0), reverse=True):
            scrape_kategori(session, k["category"], k["id"], headers)
        print("\n\nALLE KATEGORIER FÆRDIGE!")
        print("Husk at zippe CSV-filerne og uploade til repo'et.")

    elif args.kategori:
        kat = next((k for k in kategorier
                    if k["category"].lower() == args.kategori.lower()), None)
        if not kat:
            print(f"FEJL: '{args.kategori}' ikke fundet. Brug --liste for at se kategorier.")
            sys.exit(1)
        if "id" not in kat:
            print(f"FEJL: Ingen ID for '{args.kategori}'.")
            sys.exit(1)
        scrape_kategori(session, kat["category"], kat["id"], headers)
        print("Husk at zippe CSV-filen og uploade til repo'et.")

    else:
        print("\nBrug --kategori 'Navn' eller --alle for at starte scraping.")
        print("Brug --liste for at se kategorier.")


if __name__ == "__main__":
    main()

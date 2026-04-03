"""
MFKN Scraper – henter afgørelser fra mfkn.naevneneshus.dk API pr. kategori
og gemmer til en CSV-fil.

Brug:
  python3 scrape_mfkn.py --kategori "Vandforsyningsloven" \
                         --cookie "MY_SESSION=..."

  python3 scrape_mfkn.py --alle --cookie "MY_SESSION=..."

Kendte kategorier (fra API response):
  Miljøbeskyttelsesloven          ~2499
  Husdyrbrugloven                 ~2217
  Fødevarer                       ~2200
  NBL – beskyttelseslinier        ~2099
  NBL – beskyttede naturtyper     ~1420
  Landbrugsstøtte                 ~1434
  Projektstøtte                   ~1240
  Dyresundhed og –velfærd         ~1096
  Vandforsyningsloven             ~836
  Vandløbsloven                   (scroll for antal)
  Miljøvurdering af konkrete projekter  (scroll for antal)
  + flere...

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

BASE_URL  = "https://mfkn.naevneneshus.dk"
API_URL   = f"{BASE_URL}/api/search"
PAGE_SIZE = 50
SLEEP_SEC = 0.5


def csv_filnavn(kategori_navn: str) -> str:
    """Lav et sikkert filnavn ud fra kategorinavnet."""
    navn = kategori_navn.lower()
    # Erstat specielle danske tegn og bindestreger
    navn = navn.replace("–", "-").replace("æ", "ae").replace("ø", "oe").replace("å", "aa")
    navn = re.sub(r"[^a-z0-9]+", "_", navn).strip("_")
    return f"mfkn_{navn}.csv"


def strip_html(t: str) -> str:
    t = re.sub(r"<[^>]+>", " ", str(t))
    t = html.unescape(t)
    return re.sub(r"\s{2,}", " ", t).strip()


def fetch_full_text(url: str, session: requests.Session) -> str:
    """Hent fuld afgørelsestekst fra en MFKN-afgørelsesside."""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        # Bevar HTML-headings til senere sektionsudtræk
        for selector in ["article", ".ruling-content", ".afgoerelse-tekst",
                         "main .content", "main", ".content", "#content"]:
            el = soup.select_one(selector)
            if el:
                for tag in el.select("nav, footer, header, script, style, .breadcrumb"):
                    tag.decompose()
                # Bevar HTML for headings-parsing i Harald
                raw_html = str(el)
                tekst = strip_html(raw_html)
                if len(tekst) > 200:
                    return raw_html
        body = soup.find("body")
        return str(body) if body else ""
    except Exception as e:
        print(f"  !! Fejl ved hentning af {url}: {e}")
        return ""


def hent_kategorier(session: requests.Session, headers: dict) -> list[dict]:
    """Hent alle tilgængelige kategorier fra MFKN API."""
    payload = {
        "query": "",
        "types": ["ruling"],
        "skip": 0,
        "size": 1,
        "sort": "Score",
        "categories": [],
    }
    try:
        r = session.post(API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        return data.get("categoryCounts", [])
    except Exception as e:
        print(f"Fejl ved hentning af kategorier: {e}")
        return []


def search_kategori(session: requests.Session, kategori_obj: dict,
                    headers: dict) -> list[dict]:
    """Hent alle afgørelser for én kategori fra søge-API'et."""
    kategori_navn = kategori_obj["category"]
    cat_filter = [{"id": kategori_obj["id"], "title": kategori_navn}]
    results = []
    skip = 0

    # Først: hent total count
    payload = {
        "query": "",
        "types": ["ruling"],
        "skip": 0,
        "size": 1,
        "sort": "Score",
        "categories": cat_filter,
    }
    try:
        r = session.post(API_URL, json=payload, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Fejl ved første API-kald: {e}")
        return []

    total = data.get("totalCount", 0)
    print(f"API: {total} afgørelser i kategorien '{kategori_navn}'")

    while skip < total:
        payload = {
            "query": "",
            "types": ["ruling"],
            "skip": skip,
            "size": PAGE_SIZE,
            "sort": "Score",
            "categories": cat_filter,
        }
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
            # Tilpas til MFKN's response-format
            afgoerelse_id = h.get("id", h.get("afgoerelseId", ""))
            link = (h.get("url") or h.get("link") or
                    f"{BASE_URL}/afgoerelse/{afgoerelse_id}")
            # Sørg for fuldt URL
            if link.startswith("/"):
                link = BASE_URL + link

            results.append({
                "id":    afgoerelse_id,
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


def scrape_kategori(session: requests.Session, kategori_obj: dict,
                    headers: dict) -> None:
    """Scrape én kategori: hent liste + fuld tekst, gem til CSV."""
    kategori_navn = kategori_obj["category"]
    csv_path = Path(csv_filnavn(kategori_navn))
    print(f"\n{'='*60}")
    print(f"Kategori: {kategori_navn}")
    print(f"Output:   {csv_path}")
    print(f"{'='*60}")

    # 1. Hent alle afgørelser for kategorien
    alle = search_kategori(session, kategori_obj, headers)

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
            "Retsomraade": kategori_navn,
        })
        time.sleep(SLEEP_SEC)

        # Gem løbende per 50 afgørelser
        if len(ny_batch) % 50 == 0:
            append_to_csv(csv_path, ny_batch)
            print(f"  → Gemt {len(ny_batch)} rækker løbende")
            ny_batch = []

    if ny_batch:
        append_to_csv(csv_path, ny_batch)

    total_gemt = len(eksisterende) + sum(1 for a in nye if a.get("Link"))
    print(f"\nFærdig med '{kategori_navn}'! CSV har nu ~{total_gemt} afgørelser.")


def main():
    parser = argparse.ArgumentParser(
        description="Scraper til MFKN-afgørelser (mfkn.naevneneshus.dk)")
    parser.add_argument("--kategori", default="",
                        help="Kategorinavn, fx 'Vandforsyningsloven'")
    parser.add_argument("--alle", action="store_true",
                        help="Scrape ALLE kategorier")
    parser.add_argument("--list", action="store_true",
                        help="Vis tilgængelige kategorier og afslut")
    parser.add_argument("--cookie", default="",
                        help="MY_SESSION=... cookie fra browser (påkrævet)")
    args = parser.parse_args()

    if not args.cookie and not args.list:
        print("FEJL: Du skal angive --cookie med din MY_SESSION cookie.")
        print("Åbn DevTools i browseren → Application → Cookies → mfkn.naevneneshus.dk")
        print("Kopiér værdien af MY_SESSION og kør:")
        print('  python3 scrape_mfkn.py --list --cookie "MY_SESSION=din_cookie_her"')
        sys.exit(1)

    headers = {
        "Accept":       "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36",
        "Referer":      "https://mfkn.naevneneshus.dk/soeg",
        "Origin":       "https://mfkn.naevneneshus.dk",
    }
    if args.cookie:
        cookie_val = args.cookie
        if not cookie_val.startswith("MY_SESSION="):
            cookie_val = f"MY_SESSION={cookie_val}"
        headers["Cookie"] = cookie_val

    session = requests.Session()
    session.headers.update({"User-Agent": headers["User-Agent"]})

    # Vis kategorier
    if args.list or args.alle or not args.kategori:
        print("Henter kategorier fra MFKN API…")
        kategorier = hent_kategorier(session, headers)
        if not kategorier:
            print("Kunne ikke hente kategorier. Tjek din cookie.")
            sys.exit(1)

        print(f"\n{'Kategori':<45} {'Antal':>8}")
        print("-" * 55)
        for k in sorted(kategorier, key=lambda x: x["count"], reverse=True):
            print(f"  {k['category']:<43} {k['count']:>6}")
        print(f"\n  I alt: {sum(k['count'] for k in kategorier):>6}")

        if args.list:
            return

    if args.alle:
        kategorier = hent_kategorier(session, headers)
        for k in sorted(kategorier, key=lambda x: x["count"], reverse=True):
            scrape_kategori(session, k, headers)
        print("\n\nALLE KATEGORIER FÆRDIGE!")
        print("Husk at zippe CSV-filerne og uploade til repo'et.")
    elif args.kategori:
        # Find kategori-objektet med id
        kategorier = hent_kategorier(session, headers)
        kat_obj = next((k for k in kategorier
                        if k["category"].lower() == args.kategori.lower()), None)
        if not kat_obj:
            print(f"FEJL: Kategorien '{args.kategori}' blev ikke fundet.")
            sys.exit(1)
        scrape_kategori(session, kat_obj, headers)
        print("\nHusk at zippe CSV-filen og uploade til repo'et.")
    else:
        print("\nBrug --kategori 'Navn' eller --alle for at starte scraping.")
        print("Brug --list for at se kategorier.")


if __name__ == "__main__":
    main()

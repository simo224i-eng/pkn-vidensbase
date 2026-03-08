"""
PKN Scraper – henter alle afgørelser fra pkn.naevneneshus.dk API
og tilføjer nye til pkn_vidensbase_fuld_tekst.csv

Kør: python3 scrape_pkn.py

Kræver: pip install requests beautifulsoup4
"""

import csv
import html
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Konfiguration ──────────────────────────────────────────────────────────────
CSV_PATH   = Path("pkn_vidensbase_fuld_tekst.csv")
BASE_URL   = "https://pkn.naevneneshus.dk"
API_URL    = f"{BASE_URL}/api/search"
PAGE_SIZE  = 50          # max per request
SLEEP_SEC  = 0.4         # pause mellem requests (vær skånsom mod serveren)

HEADERS = {
    "Accept":       "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/116.0.0.0 Safari/537.36",
    "Referer":      "https://pkn.naevneneshus.dk/soeg",
}

# ── Hjælpefunktioner ───────────────────────────────────────────────────────────
def strip_html(t: str) -> str:
    """Fjern HTML-tags og dekod HTML-entiteter."""
    t = re.sub(r"<[^>]+>", " ", str(t))
    t = html.unescape(t)
    return re.sub(r"\s{2,}", " ", t).strip()


def fetch_full_text(url: str, session: requests.Session) -> str:
    """Hent fuld tekst fra en afgørelse-side."""
    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # PKN's afgørelse-sider har typisk brødtekst i article / main / .content
        for selector in ["article", "main .content", ".afgoerelse-tekst",
                         "main", ".content", "#content"]:
            el = soup.select_one(selector)
            if el:
                # Fjern navigation/footer-elementer inde i elementet
                for tag in el.select("nav, footer, header, script, style, .breadcrumb"):
                    tag.decompose()
                tekst = strip_html(el.get_text(separator=" ", strip=True))
                if len(tekst) > 200:
                    return tekst

        # Fallback: body-tekst
        body = soup.find("body")
        return strip_html(body.get_text(separator=" ", strip=True)) if body else ""
    except Exception as e:
        print(f"  !! Fejl ved hentning af {url}: {e}")
        return ""


def search_all(session: requests.Session) -> list[dict]:
    """
    Hent alle afgørelser fra søge-API'et uden kategorifilter.
    Returnerer liste af dicts med: id, titel, dato, link.
    """
    results = []
    skip = 0

    # Første kald for at finde totalt antal
    payload = {"categories": [], "query": "", "sort": "Descending",
                "types": [], "skip": 0, "size": 1}
    try:
        r = session.post(API_URL, json=payload, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"Fejl ved første API-kald: {e}")
        sys.exit(1)

    # Diagnostik: print top-level keys og en enkelt record så vi kender strukturen
    print(f"API top-level keys: {list(data.keys())}")
    sample_list = (data.get("results") or data.get("hits") or
                   data.get("items") or data.get("data") or [])
    if sample_list:
        print(f"Første record keys: {list(sample_list[0].keys())}")
        print(f"Første record: {json.dumps(sample_list[0], ensure_ascii=False, indent=2)[:500]}")

    total = (data.get("total") or data.get("count") or
             data.get("totalCount") or data.get("numberOfHits") or 0)
    print(f"API rapporterer {total} afgørelser i alt")

    while skip < total:
        payload = {"categories": [], "query": "", "sort": "Descending",
                   "types": [], "skip": skip, "size": PAGE_SIZE}
        try:
            r = session.post(API_URL, json=payload, headers=HEADERS, timeout=15)
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
            # Tilpas feltnavn til hvad API'et faktisk returnerer
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
    """Læs eksisterende CSV og returner dict keyed by Link."""
    existing = {}
    if not path.exists():
        return existing
    csv.field_size_limit(10_000_000)
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            existing[row["Link"]] = row
    print(f"Eksisterende CSV: {len(existing)} rækker")
    return existing


def append_to_csv(path: Path, rows: list[dict]) -> None:
    """Tilføj nye rækker til CSV-filen."""
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Dato", "Titel", "Link", "Tekst"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


# ── Hoved-scraping ─────────────────────────────────────────────────────────────
def main():
    session = requests.Session()
    session.headers.update({"User-Agent": HEADERS["User-Agent"]})

    # 1. Find alle afgørelser via API
    alle = search_all(session)

    # 2. Sammenlign med eksisterende CSV
    eksisterende = load_existing_csv(CSV_PATH)
    nye = [a for a in alle if a["Link"] not in eksisterende]
    print(f"Nye afgørelser der mangler i CSV: {len(nye)}")

    if not nye:
        print("Ingen nye afgørelser – CSV er up to date.")
        return

    # 3. Hent fuld tekst for hver ny afgørelse
    ny_batch = []
    for idx, a in enumerate(nye, 1):
        print(f"  [{idx}/{len(nye)}] {a['Titel'][:70]}…")
        tekst = fetch_full_text(a["Link"], session)
        if not tekst:
            print(f"    → Ingen tekst fundet, springer over")
            continue
        ny_batch.append({
            "Dato":  a["Dato"],
            "Titel": a["Titel"],
            "Link":  a["Link"],
            "Tekst": tekst,
        })
        time.sleep(SLEEP_SEC)

        # Gem løbende for hvert 100. resultat
        if len(ny_batch) % 100 == 0:
            append_to_csv(CSV_PATH, ny_batch)
            print(f"  → Gemt {len(ny_batch)} nye rækker til CSV")
            ny_batch = []

    # Gem resten
    if ny_batch:
        append_to_csv(CSV_PATH, ny_batch)

    print(f"\nFærdig! Tilføjede op til {len(nye)} nye afgørelser til {CSV_PATH}")
    print("Husk at genzippe CSV-filen og uploade til Streamlit Cloud.")


if __name__ == "__main__":
    main()

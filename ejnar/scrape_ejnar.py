"""
Ejnar Scraper – henter kendelser om ejerskifteforsikring fra
Ankenævnet for Forsikrings afgørelsesdatabase (ankeforsikring.dk).

Output: ejnar_ejerskifteforsikring.csv med kolonnerne
        Dato, Titel, Link, Tekst, Sagsnummer, Selskab, Udfald, Forsikringstype

Brug:
  python3 scrape_ejnar.py [--limit 100] [--cookie "MY_SESSION=..."] [--debug]

═══════════════════════════════════════════════════════════════════════════════
VIGTIGT — INDEN FØRSTE KØRSEL:

Sandboxede miljøer kan ikke probe ankeforsikring.dk, så følgende konstanter
skal verificeres lokalt med browserens DevTools (Network-tab) før scraperen
kører i produktion:

  • SEARCH_URL og PAYLOAD-format    (find ved at udføre en søgning og kopiere
                                     POST-requesten i DevTools → Network)
  • EJERSKIFTE_FAGOMRADE / kategori-værdi (kig i payload for filterets værdi)
  • RESULT_TITLE_SEL og RESULT_LINK_SEL (HTML-selectors i resultatlisten)
  • DETAIL_TEXT_SEL                  (selector på selve kendelsessiden)

Sektionerne markeret med "TODO: VERIFICÉR" indeholder mine bedste gæt — udskift
dem efter første inspektion.
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL  = "https://ankeforsikring.dk"
# TODO: VERIFICÉR — typisk noget i retning af /api/search eller en JSON-endpoint
#                   bag /da/afgoerelser-og-praksis/sog-i-afgorelsesdatabasen
SEARCH_URL = f"{BASE_URL}/da/afgoerelser-og-praksis/sog-i-afgorelsesdatabasen"

# TODO: VERIFICÉR — den eksakte streng siden bruger til at filtrere på
#                   ejerskifteforsikring (typisk i payload som "Fagområde" el.lign.)
EJERSKIFTE_FAGOMRADE = "Ejerskifteforsikring"

PAGE_SIZE = 25
SLEEP_SEC = 0.5
OUTPUT_CSV = Path(__file__).resolve().parent / "ejnar_ejerskifteforsikring.csv"

DEFAULT_HEADERS = {
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "da,en;q=0.7",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36",
    "Referer":         f"{BASE_URL}/",
}


# ── Hjælpere ────────────────────────────────────────────────────────────────
def strip_html_keep_structure(soup_or_html) -> str:
    """Fjern script/style/nav, returnér tekst med bevarede afsnitsskift."""
    if isinstance(soup_or_html, str):
        soup = BeautifulSoup(soup_or_html, "html.parser")
    else:
        soup = soup_or_html
    for tag in soup.select("script, style, nav, footer, header, .breadcrumb, .cookie, form"):
        tag.decompose()
    # Bevar p/h2/h3 som linjeskift
    for br in soup.find_all(["br"]):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "h2", "h3", "h4", "div", "li"]):
        blk.append("\n")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    # Reducér whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def safe_text(el) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)).strip()


def detect_udfald(tekst: str) -> str:
    """Klassificér AKF-kendelse efter typiske udfaldsformuleringer."""
    t = tekst.lower()
    # Bredt: tjek de sidste ~3000 tegn som typisk indeholder konklusionen
    halen = t[-3000:]
    if any(p in halen for p in (
        "klageren får ikke medhold",
        "klagerens påstand tages ikke til følge",
        "selskabet frifindes",
        "den indklagede tilpligtes ikke",
    )):
        return "Ikke medhold"
    if any(p in halen for p in (
        "klageren får delvist medhold",
        "klageren får delvis medhold",
        "delvist medhold",
        "delvis medhold",
    )):
        return "Delvis medhold"
    if any(p in halen for p in (
        "klageren får medhold",
        "klagerens påstand tages til følge",
        "den indklagede tilpligtes",
        "selskabet skal anerkende",
        "selskabet skal betale",
    )):
        return "Medhold"
    if any(p in halen for p in (
        "klagen afvises",
        "afvises som åbenbart",
        "kan ikke realitetsbehandles",
    )):
        return "Afvist"
    return "Ukendt"


# Stikord til mangeltype-detektion (samme liste bruges også i ejnar.py UI'en).
MANGELTYPER = {
    "Skimmel/fugt":         ["skimmel", "fugt", "fugtskade", "fugtindtrængning"],
    "Tag/tagdækning":       ["tag", "tagdækning", "tagsten", "undertag", "tagrende"],
    "Kloak/dræn":           ["kloak", "dræn", "afløb", "spildevand", "faldstamme"],
    "Installationer":       ["el-install", "el install", "vand-install", "varmeinstal",
                             "installationsskade", "stikledning"],
    "Fundament":            ["fundament", "sokkel", "sætningsskade", "revner i fundament"],
    "Vinduer/døre":         ["vindue", "døre", "vinduesparti"],
    "Murværk/facade":       ["murværk", "mursten", "facade", "puds", "revner i mur"],
    "Råd/svamp/insekt":     ["råd", "trænedbrydende", "svamp", "ægte hussvamp", "insektangreb",
                             "borebille"],
    "Konstruktion/bærende": ["bjælke", "bærende konstruktion", "spær", "trækonstruktion",
                             "etageadskillelse"],
    "Badeværelse/vådrum":   ["badeværelse", "vådrum", "vådrumsmembran", "fliser i bad"],
    "Gulv":                 ["gulv", "trægulv", "klinkegulv", "parketgulv"],
}


def detect_mangeltyper(tekst: str) -> list[str]:
    t = tekst.lower()
    fundet = []
    for label, stikord in MANGELTYPER.items():
        if any(s in t for s in stikord):
            fundet.append(label)
    return fundet or ["Andet"]


# Liste af danske forsikringsselskaber (bruges til selskab-detektion).
SELSKABER = [
    "Topdanmark", "Tryg", "Alm. Brand", "Codan", "If", "Gjensidige",
    "GF Forsikring", "Lærerstandens", "LB Forsikring", "FDM Forsikring",
    "Købstædernes Forsikring", "Privatsikring", "Concordia",
    "Dansk Boligforsikring", "Dansk Glasforsikring", "Eika", "Pension Danmark",
]


def detect_selskab(tekst: str) -> str:
    for s in SELSKABER:
        if re.search(rf"\b{re.escape(s)}\b", tekst, flags=re.I):
            return s
    return ""


def extract_sagsnummer(titel: str, tekst: str) -> str:
    # Typisk format hos AKF: "9X.XXX" eller "AK XX.XXX"
    for src in (titel, tekst[:1000]):
        m = re.search(r"\b(?:AK\s*)?\d{2}[.\s]?\d{3,4}\b", src)
        if m:
            return m.group(0).replace(" ", "")
    return ""


# ── Søgning + pagination ─────────────────────────────────────────────────────
def search_results(session: requests.Session, max_results: int | None,
                    cookie: str = "", debug: bool = False) -> list[dict]:
    """Hent resultatliste fra AKF's søgning, filtreret på ejerskifteforsikring.

    TODO: VERIFICÉR — denne funktion antager at AKF bruger en JSON-payload
    a la pkn.naevneneshus.dk. I praksis kan det være query-params i en GET-request.
    Tilpas requesten herunder efter inspektion i DevTools."""
    headers = dict(DEFAULT_HEADERS)
    if cookie:
        headers["Cookie"] = cookie
    headers["Accept"] = "application/json, text/html;q=0.9"

    results: list[dict] = []
    page = 0
    while True:
        # ── Variant A: JSON-API (verificér payload-strukturen) ────────────
        payload = {
            "fagområde": EJERSKIFTE_FAGOMRADE,   # TODO: feltnavn kan hedde "kategori", "filter" osv.
            "page": page,
            "size": PAGE_SIZE,
            "sort": "date_desc",
        }
        try:
            r = session.post(SEARCH_URL, headers=headers, json=payload, timeout=20)
        except requests.RequestException as e:
            print(f"[Side {page}] Netværksfejl: {e}")
            break

        if debug:
            print(f"[Side {page}] HTTP {r.status_code} — {len(r.content)} bytes")

        # ── Hvis API'et returnerer JSON ──────────────────────────────────
        ct = r.headers.get("Content-Type", "")
        if r.ok and "json" in ct.lower():
            try:
                data = r.json()
            except json.JSONDecodeError:
                data = None
            if data:
                hits = data.get("results") or data.get("items") or data.get("hits") or []
                for h in hits:
                    href = h.get("url") or h.get("link") or h.get("href") or ""
                    if href and not href.startswith("http"):
                        href = urljoin(BASE_URL, href)
                    results.append({
                        "Titel": (h.get("title") or h.get("titel") or "").strip(),
                        "Dato":  (h.get("date") or h.get("dato") or "")[:10],
                        "Link":  href,
                    })
                if not hits:
                    break
                page += 1
                if max_results and len(results) >= max_results:
                    return results[:max_results]
                time.sleep(SLEEP_SEC)
                continue

        # ── Variant B: HTML-fallback ─────────────────────────────────────
        # Send GET med query-params i stedet og parse HTML-listen.
        get_params = {
            "fagomrade": EJERSKIFTE_FAGOMRADE,    # TODO: VERIFICÉR
            "page": page + 1,
        }
        try:
            r = session.get(SEARCH_URL, headers=headers, params=get_params, timeout=20)
            r.raise_for_status()
        except requests.RequestException as e:
            print(f"[Side {page}] HTML-fallback fejlede: {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        # TODO: VERIFICÉR — find selectoren ved at højreklikke på et resultat
        # i browseren og vælge "Inspect".
        kort = soup.select(".search-result, .afgoerelse-card, article a")
        if not kort:
            kort = soup.select("a[href*='/afgoerelser-og-praksis/'][href*='/ak']")
        if not kort:
            if debug:
                print("Ingen resultater fundet på siden — tjek HTML-selectors.")
            break

        for el in kort:
            link = el.get("href", "")
            if link and not link.startswith("http"):
                link = urljoin(BASE_URL, link)
            titel = safe_text(el)
            # Forsøg at læse dato fra et søsterelement
            dato = ""
            parent = el.find_parent()
            if parent:
                date_el = parent.select_one("time, .date, .dato, [datetime]")
                if date_el:
                    dato = (date_el.get("datetime", "") or date_el.get_text(strip=True))[:10]
            if titel and link:
                results.append({"Titel": titel, "Dato": dato, "Link": link})

        page += 1
        if max_results and len(results) >= max_results:
            return results[:max_results]
        time.sleep(SLEEP_SEC)

    return results


def fetch_kendelse_text(session: requests.Session, url: str, debug: bool = False) -> str:
    """Hent fuld tekst fra en kendelses-side."""
    try:
        r = session.get(url, headers=DEFAULT_HEADERS, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        if debug:
            print(f"  Fejl ved {url}: {e}")
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    # TODO: VERIFICÉR — selectoren til selve kendelsens brødtekst
    for sel in (
        "article .field--name-body",
        "article .body",
        "article",
        "main .content",
        ".afgoerelse-tekst",
        "main",
    ):
        el = soup.select_one(sel)
        if el and len(safe_text(el)) > 400:
            return strip_html_keep_structure(el)
    # Fallback: hele body
    body = soup.find("body")
    return strip_html_keep_structure(body) if body else ""


# ── CSV I/O ──────────────────────────────────────────────────────────────────
FIELDNAMES = [
    "Dato", "Titel", "Link", "Tekst",
    "Sagsnummer", "Selskab", "Udfald",
    "Mangeltype",         # liste, comma-separeret
    "Forsikringstype",    # konstant: Ejerskifteforsikring
]


def load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    csv.field_size_limit(10_000_000)
    with open(path, newline="", encoding="utf-8") as f:
        return {r["Link"]: r for r in csv.DictReader(f)}


def append_rows(path: Path, rows: list[dict]) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDNAMES})


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(description="Scraper til Ankenævnet for Forsikrings "
                                            "ejerskifteforsikrings-kendelser.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max antal kendelser at hente (default: alle)")
    p.add_argument("--cookie", default="", help="Evt. session-cookie fra browser")
    p.add_argument("--debug", action="store_true", help="Verbose output")
    args = p.parse_args()

    print(f"Output: {OUTPUT_CSV}")
    print(f"Filter: fagområde='{EJERSKIFTE_FAGOMRADE}'")
    if args.limit:
        print(f"Limit:  {args.limit}")

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    print("\n[1/3] Henter resultatliste…")
    alle = search_results(session, max_results=args.limit,
                          cookie=args.cookie, debug=args.debug)
    print(f"      Fandt {len(alle)} kendelser i resultatlisten")
    if not alle:
        print("Ingen resultater. Tjek SEARCH_URL, payload-format og selectors i toppen af scriptet.")
        sys.exit(1)

    print("\n[2/3] Sammenligner med eksisterende CSV…")
    eksisterende = load_existing(OUTPUT_CSV)
    nye = [a for a in alle if a["Link"] not in eksisterende]
    print(f"      Eksisterende: {len(eksisterende)} | Nye: {len(nye)}")
    if not nye:
        print("Intet at hente — CSV er up to date.")
        return

    print("\n[3/3] Henter fuld tekst og parser metadata…")
    batch: list[dict] = []
    for i, a in enumerate(nye, 1):
        print(f"  [{i}/{len(nye)}] {a['Titel'][:70]}…")
        tekst = fetch_kendelse_text(session, a["Link"], debug=args.debug)
        if not tekst or len(tekst) < 200:
            print(f"      → for kort tekst, springer over")
            continue

        sag = extract_sagsnummer(a["Titel"], tekst)
        selskab = detect_selskab(tekst)
        udfald = detect_udfald(tekst)
        mangeltyper = detect_mangeltyper(tekst)

        batch.append({
            "Dato":            a["Dato"],
            "Titel":           a["Titel"],
            "Link":            a["Link"],
            "Tekst":           tekst,
            "Sagsnummer":      sag,
            "Selskab":         selskab,
            "Udfald":          udfald,
            "Mangeltype":      ", ".join(mangeltyper),
            "Forsikringstype": "Ejerskifteforsikring",
        })
        time.sleep(SLEEP_SEC)

        # Gem hver 50 i tilfælde af crash
        if len(batch) % 50 == 0:
            append_rows(OUTPUT_CSV, batch)
            print(f"      → gemt {len(batch)} rækker løbende")
            batch = []

    if batch:
        append_rows(OUTPUT_CSV, batch)

    print(f"\nFærdig. Tilføjede {len(batch) if batch else 0} (+ allerede gemte løbende-batches) "
          f"nye kendelser til {OUTPUT_CSV.name}")
    print("Næste skridt:")
    print(f"  • python3 ejnar/build_embeddings.py     (kræver VOYAGE_API_KEY)")
    print(f"  • git add ejnar/ejnar_ejerskifteforsikring.csv ejnar/embeds/*.npz")


if __name__ == "__main__":
    main()

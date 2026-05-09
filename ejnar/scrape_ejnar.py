"""
Ejnar Scraper — henter kendelser om ejerskifteforsikring fra
Ankenævnet for Forsikrings afgørelsesdatabase (ankeforsikring.dk).

Bruger SharePoint Search REST API'et:
  GET https://ankeforsikring.dk/_api/search/query
      ?querytext='*'
      &refinementfilters='AnkeforsikringInsuranceType:equals("Ejerskifteforsikring")'
      &rowlimit=50&startrow=N
      &selectproperties='Title,Path,Write,...'

Output: ejnar_ejerskifteforsikring.csv

Brug:
  python3 scrape_ejnar.py [--limit 100] [--debug]

Ankenævnet har ~5641 ejerskifteforsikrings-kendelser. Med rowlimit=50 og
0,5 sek pause pr. side tager en fuld kørsel ca. 60-90 sekunder for listen
+ ekstra tid til at hente fuld tekst på hver kendelse.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ankeforsikring.dk"
SEARCH_API = f"{BASE_URL}/_api/search/query"

# Filteret som UI'en bruger
REFINEMENT_FILTER = 'AnkeforsikringInsuranceType:equals("Ejerskifteforsikring")'

# Note: vi sender IKKE selectproperties — i stedet lader vi SharePoint
# returnere alle standardfelter + alle Ankeforsikring-specifikke felter
# der måtte være konfigureret. Det undgår 500-fejl ved at bede om felter
# der ikke findes som managed properties på serveren.
ROW_LIMIT = 50
SLEEP_SEC = 0.5

OUTPUT_CSV = Path(__file__).resolve().parent / "ejnar_ejerskifteforsikring.csv"

DEFAULT_HEADERS = {
    "Accept":          "application/json;odata=verbose",
    "Accept-Language": "da,en;q=0.7",
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0 Safari/537.36",
    "Referer":         f"{BASE_URL}/kendelser/Sider/kendelser.aspx",
}


# ── Hjælpere ─────────────────────────────────────────────────────────────────
def cells_to_dict(cells: list) -> dict:
    """Konvertér SharePoint Cells.results-liste til {Key: Value}-dict."""
    out = {}
    for c in cells or []:
        k = c.get("Key")
        v = c.get("Value")
        if k:
            out[k] = v
    return out


def parse_sp_date(s: str) -> str:
    """SharePoint Write/LastModifiedTime kommer som '2024-03-15T08:26:38.0000000Z'.
    Returnér 'YYYY-MM-DD'."""
    if not s:
        return ""
    return s[:10]


def strip_html_keep_structure(soup_or_html) -> str:
    if isinstance(soup_or_html, str):
        soup = BeautifulSoup(soup_or_html, "html.parser")
    else:
        soup = soup_or_html
    for tag in soup.select(
        "script, style, nav, footer, header, .breadcrumb, .cookie, "
        "form, .ms-webpart-titleText, #s4-titlerow, #s4-ribbonrow"
    ):
        tag.decompose()
    for br in soup.find_all(["br"]):
        br.replace_with("\n")
    for blk in soup.find_all(["p", "h2", "h3", "h4", "div", "li"]):
        blk.append("\n")
    text = soup.get_text(separator=" ")
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Udfald-detektion ─────────────────────────────────────────────────────────
def detect_udfald(tekst: str, ruling_type: str = "") -> str:
    """AKF's officielle kategorier: Klager medhold, Klager delvist medhold,
    Selskab medhold, Afvist, Principielle afgørelser. Vi mapper til Ejnar's
    interne udfaldsnavne (Medhold / Delvis medhold / Ikke medhold / Afvist)."""
    rt = (ruling_type or "").lower()
    if "delvis" in rt:
        return "Delvis medhold"
    if "klager medhold" in rt:
        return "Medhold"
    if "selskab medhold" in rt:
        return "Ikke medhold"
    if "afvist" in rt or "afvis" in rt:
        return "Afvist"

    # Fald tilbage til tekstanalyse
    halen = (tekst or "").lower()[-3000:]
    if any(p in halen for p in (
        "klageren får ikke medhold", "klagerens påstand tages ikke til følge",
        "selskabet frifindes", "selskab medhold",
    )):
        return "Ikke medhold"
    if any(p in halen for p in (
        "delvist medhold", "delvis medhold", "klageren får delvist medhold",
    )):
        return "Delvis medhold"
    if any(p in halen for p in (
        "klageren får medhold", "klagerens påstand tages til følge",
        "den indklagede tilpligtes", "selskabet skal anerkende",
    )):
        return "Medhold"
    if any(p in halen for p in ("klagen afvises", "afvises som")):
        return "Afvist"
    return "Ukendt"


# ── Mangeltype-detektion ─────────────────────────────────────────────────────
MANGELTYPER = {
    "Skimmel/fugt":         ["skimmel", "fugt", "fugtskade", "fugtindtrængning"],
    "Tag/tagdækning":       ["tag", "tagdækning", "tagsten", "undertag", "tagrende"],
    "Kloak/dræn":           ["kloak", "dræn", "afløb", "spildevand", "faldstamme"],
    "Installationer":       ["el-install", "el install", "vand-install",
                             "varmeinstal", "installationsskade", "stikledning"],
    "Fundament":            ["fundament", "sokkel", "sætningsskade"],
    "Vinduer/døre":         ["vindue", "døre", "vinduesparti"],
    "Murværk/facade":       ["murværk", "mursten", "facade", "puds"],
    "Råd/svamp/insekt":     ["råd", "trænedbrydende", "svamp", "ægte hussvamp",
                             "insektangreb", "borebille"],
    "Konstruktion/bærende": ["bjælke", "bærende konstruktion", "spær",
                             "trækonstruktion", "etageadskillelse"],
    "Badeværelse/vådrum":   ["badeværelse", "vådrum", "vådrumsmembran"],
    "Gulv":                 ["gulv", "trægulv", "klinkegulv", "parketgulv"],
}


def detect_mangeltyper(tekst: str) -> list[str]:
    t = (tekst or "").lower()
    fundet = [label for label, ord in MANGELTYPER.items()
              if any(s in t for s in ord)]
    return fundet or ["Andet"]


# ── SharePoint Search API ────────────────────────────────────────────────────
def search_page(session: requests.Session, start_row: int, debug: bool = False) -> dict:
    """Hent én side af søgeresultater (rowlimit kendelser).
    Parametrene er bevidst valgt så de matcher det browseren sender — undtagen
    rowlimit/startrow som tilføjes til paginering."""
    params = {
        "querytext":                  "'(*)'",
        "refiners":                   "'AnkeforsikringCompanyNameAndID(sort=name:ascending,filter=500/0/*),AnkeforsikringInsuranceType(sort=name:ascending,filter=50/0/*)'",
        "properties":                 "'SourceName:AnkeforsikringKendelser,SourceLevel:SSA'",
        "culture":                    1030,
        "QueryTemplatePropertiesUrl": "'spfile://webroot/queryparametertemplate.xml'",
        "refinementfilters":          f"'{REFINEMENT_FILTER}'",
        "rowlimit":                   ROW_LIMIT,
        "startrow":                   start_row,
    }
    r = session.get(SEARCH_API, headers=DEFAULT_HEADERS, params=params, timeout=30)
    if debug:
        print(f"  [startrow={start_row}] HTTP {r.status_code} ({len(r.content)} bytes)")
    r.raise_for_status()
    return r.json()


def parse_search_response(data: dict) -> tuple[list[dict], int]:
    """Returnér (rækker, total_hits)."""
    try:
        rel = (data.get("d", {})
                   .get("query", {})
                   .get("PrimaryQueryResult", {})
                   .get("RelevantResults", {}) or {})
    except AttributeError:
        return [], 0

    total = rel.get("TotalRows") or rel.get("RowCount") or 0
    rows_obj = rel.get("Table", {}).get("Rows", {}) or {}
    raw_rows = rows_obj.get("results", []) if isinstance(rows_obj, dict) else []

    out = []
    for row in raw_rows:
        cells = (row.get("Cells", {}) or {}).get("results", [])
        d = cells_to_dict(cells)
        path = d.get("OriginalPath") or d.get("Path") or ""
        if not path:
            continue
        if not path.startswith("http"):
            path = urljoin(BASE_URL, path)
        # Vi prøver flere mulige feltnavne — SharePoint sites har ofte
        # forskellige konventioner (refinable strings owstaxIdAnkeforsikring* osv.)
        out.append({
            "Titel":      (d.get("Title") or d.get("AnkeforsikringTitle") or
                           d.get("AnkeforsikringSubject") or ""),
            "Link":       path,
            "Dato":       parse_sp_date(
                d.get("AnkeforsikringRulingDate") or
                d.get("RulingDate") or
                d.get("Write") or ""),
            "Sagsnummer": (d.get("AnkeforsikringCaseNumber") or
                           d.get("CaseNumber") or
                           d.get("AnkeforsikringRulingNumber") or ""),
            "Selskab":    (d.get("AnkeforsikringCompanyName") or
                           d.get("CompanyName") or ""),
            "RulingType": (d.get("AnkeforsikringRulingType") or
                           d.get("RulingType") or ""),
            "ApiSummary": (d.get("AnkeforsikringSummary") or
                           d.get("HitHighlightedSummary") or ""),
            "_alle_felter": d,   # bevares til debug
        })
    return out, int(total)


def fetch_kendelse_text(session: requests.Session, url: str, debug: bool = False) -> str:
    """Hent fuld tekst fra én kendelses-side."""
    try:
        r = session.get(url, headers={
            "User-Agent":      DEFAULT_HEADERS["User-Agent"],
            "Accept":          "text/html,application/xhtml+xml",
            "Accept-Language": "da,en;q=0.7",
        }, timeout=20)
        r.raise_for_status()
    except requests.RequestException as e:
        if debug:
            print(f"  Fejl ved {url}: {e}")
        return ""

    soup = BeautifulSoup(r.text, "html.parser")
    # SharePoint-publishing-sider har typisk indhold i én af disse:
    for sel in (
        "#contentBox", "#mainContent", ".ms-rtestate-field",
        ".content-box", "main", "article",
        "#DeltaPlaceHolderMain", ".s4-ca",
    ):
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) > 400:
            return strip_html_keep_structure(el)
    body = soup.find("body")
    return strip_html_keep_structure(body) if body else ""


# ── CSV ──────────────────────────────────────────────────────────────────────
FIELDNAMES = [
    "Dato", "Titel", "Link", "Tekst",
    "Sagsnummer", "Selskab", "Udfald",
    "Mangeltype", "Forsikringstype", "RulingType",
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
    p = argparse.ArgumentParser(description="Scraper til AKF's ejerskifteforsikrings-kendelser.")
    p.add_argument("--limit", type=int, default=None,
                   help="Max antal kendelser at hente (default: alle ~5641)")
    p.add_argument("--debug", action="store_true", help="Verbose output")
    p.add_argument("--list-only", action="store_true",
                   help="Kun hent listen — spring fuld tekst-hentning over")
    args = p.parse_args()

    print(f"Output: {OUTPUT_CSV}")
    print(f"Filter: {REFINEMENT_FILTER}")
    if args.limit:
        print(f"Limit:  {args.limit}")

    session = requests.Session()
    session.headers.update(DEFAULT_HEADERS)

    # 1. Hent komplet liste
    print("\n[1/3] Henter resultatliste fra SharePoint Search…")
    alle: list[dict] = []
    start = 0
    total_hits = None
    while True:
        try:
            data = search_page(session, start, debug=args.debug)
        except requests.HTTPError as e:
            print(f"  HTTP-fejl ved startrow={start}: {e}")
            break
        rows, total = parse_search_response(data)
        if total_hits is None:
            total_hits = total
            print(f"  Total hits ifølge API: {total_hits}")
            if args.debug and rows:
                print(f"  Felter returneret pr. række (første resultat):")
                for k in sorted(rows[0].get("_alle_felter", {}).keys()):
                    v = rows[0]["_alle_felter"][k]
                    if v not in (None, ""):
                        print(f"    {k} = {str(v)[:80]}")
        if not rows:
            break
        alle.extend(rows)
        print(f"  {min(len(alle), total_hits)}/{total_hits}…", end="\r")
        if args.limit and len(alle) >= args.limit:
            alle = alle[:args.limit]
            break
        if len(alle) >= total_hits:
            break
        start += ROW_LIMIT
        time.sleep(SLEEP_SEC)
    print()
    print(f"      Hentet {len(alle)} kendelser fra listen")
    if not alle:
        print("Ingen resultater. Tjek netværk og at API-kaldet i toppen af "
              "scriptet matcher det din browser sender.")
        sys.exit(1)

    # 2. Sammenlign med eksisterende CSV
    print("\n[2/3] Sammenligner med eksisterende CSV…")
    eksisterende = load_existing(OUTPUT_CSV)
    nye = [a for a in alle if a["Link"] not in eksisterende]
    print(f"      Eksisterende: {len(eksisterende)} | Nye: {len(nye)}")
    if not nye:
        print("Intet at hente — CSV er up to date.")
        return

    # 3. Hent fuld tekst (medmindre --list-only)
    print(f"\n[3/3] Henter fuld tekst for {len(nye)} kendelser…")
    batch: list[dict] = []
    for i, a in enumerate(nye, 1):
        titel_kort = (a["Titel"] or a["Link"])[:70]
        print(f"  [{i}/{len(nye)}] {titel_kort}…")
        if args.list_only:
            tekst = a.get("ApiSummary") or ""
        else:
            tekst = fetch_kendelse_text(session, a["Link"], debug=args.debug)
        if not tekst or len(tekst) < 200:
            if not args.list_only:
                print(f"      → for kort tekst, springer over")
                continue

        udfald = detect_udfald(tekst, a.get("RulingType", ""))
        mangler = detect_mangeltyper(tekst)

        batch.append({
            "Dato":            a["Dato"],
            "Titel":           a["Titel"],
            "Link":            a["Link"],
            "Tekst":           tekst,
            "Sagsnummer":      a.get("Sagsnummer", ""),
            "Selskab":         a.get("Selskab", ""),
            "Udfald":          udfald,
            "Mangeltype":      ", ".join(mangler),
            "Forsikringstype": "Ejerskifteforsikring",
            "RulingType":      a.get("RulingType", ""),
        })

        if not args.list_only:
            time.sleep(SLEEP_SEC)

        if len(batch) >= 50:
            append_rows(OUTPUT_CSV, batch)
            print(f"      → gemt {len(batch)} rækker løbende")
            batch = []

    if batch:
        append_rows(OUTPUT_CSV, batch)

    print(f"\nFærdig. CSV: {OUTPUT_CSV}")
    print("Næste skridt:")
    print(f"  • VOYAGE_API_KEY=... python3 build_embeddings.py")
    print(f"  • git add ejnar/ejnar_ejerskifteforsikring.csv ejnar/embeds/*.npz")


if __name__ == "__main__":
    main()

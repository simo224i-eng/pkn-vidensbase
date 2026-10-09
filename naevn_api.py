"""
Fælles kode til at hente afgørelser fra Nævnenes Hus (pkn.naevneneshus.dk og
mfkn.naevneneshus.dk).

Søge-API'et returnerer den fulde afgørelsestekst (HTML) direkte i søgeresultatet,
så der skal ikke hentes én side pr. afgørelse. Kategori-id'erne hentes fra
/api/sitesettings. Der kræves ingen cookie.

Teksten gemmes som ren tekst, hvor overskrifter står på egen linje med "## " foran,
så nævnets vurdering kan findes ved overskrift (se miljoejurist/sections.py).
"""

import csv
import html as htmlmod
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PAGE_SIZE = 100
SLEEP_SEC = 1.0          # max ca. 1 forespørgsel pr. sekund
FIELDS = ["id", "Naevn", "Jnr", "Dato", "Titel", "Link", "Retsomraade", "Tekst"]
UA = "Mozilla/5.0 (pkn-vidensbase forskningsscraper; 1 req/s)"


def base_url(naevn: str) -> str:
    return f"https://{naevn}.naevneneshus.dk"


def html_to_text(body: str) -> str:
    """HTML -> tekst med bevarede afsnit og markerede overskrifter."""
    soup = BeautifulSoup(body or "", "lxml")
    for t in soup(["script", "style"]):
        t.decompose()
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        h.insert_before("\n## ")
        h.insert_after("\n")
    for t in soup.find_all(["p", "li", "div", "tr", "br", "table"]):
        t.insert_after("\n")
    for li in soup.find_all("li"):
        li.insert_before("• ")
    txt = soup.get_text("")
    txt = htmlmod.unescape(txt).replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r" *\n *", "\n", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()


def get_topics(session: requests.Session, naevn: str) -> list[dict]:
    r = session.get(base_url(naevn) + "/api/sitesettings", timeout=30)
    r.raise_for_status()
    return r.json().get("topics", [])


def search_page(session, naevn, topic, skip, size=PAGE_SIZE, retries=5):
    payload = {"query": "", "types": ["ruling"], "skip": skip, "size": size,
               "sort": "Descending",
               "categories": [{"id": topic["id"], "title": topic["title"]}]}
    for forsoeg in range(retries):
        try:
            r = session.post(base_url(naevn) + "/api/search", json=payload,
                             headers={"Content-Type": "application/json"}, timeout=60)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # netværksfejl: vent og prøv igen
            print(f"  fejl skip={skip} ({e}); prøver igen", file=sys.stderr)
            time.sleep(5 * (forsoeg + 1))
    raise RuntimeError(f"Opgav {naevn} {topic['title']} skip={skip}")


def fetch_topic(session, naevn: str, topic: dict) -> list[dict]:
    first = search_page(session, naevn, topic, 0, size=1)
    total = first.get("totalCount", 0)
    print(f"{naevn}: {topic['title']}: {total} afgørelser")
    rows, skip = [], 0
    while skip < total:
        time.sleep(SLEEP_SEC)
        d = search_page(session, naevn, topic, skip)
        pubs = d.get("publications", [])
        if not pubs:
            break
        for p in pubs:
            rows.append({
                "id": p["id"],
                "Naevn": naevn.upper(),
                "Jnr": "; ".join(p.get("jnr") or []),
                "Dato": (p.get("date") or "")[:10],
                "Titel": p.get("title", ""),
                "Link": f"{base_url(naevn)}/afgoerelse/{p['id']}",
                "Retsomraade": topic["title"],
                "Tekst": html_to_text(p.get("body", "")),
            })
        skip += len(pubs)
        print(f"  {skip}/{total}", end="\r")
    print()
    return rows


def slug(s: str) -> str:
    s = s.lower().replace("–", "-")
    for a, b in (("æ", "ae"), ("ø", "oe"), ("å", "aa")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def write_csv_zip(path: Path, rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS)
    w.writeheader()
    w.writerows(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr(path.name[:-4], buf.getvalue())


def read_csv_zip(path: Path) -> list[dict]:
    csv.field_size_limit(100_000_000)
    with zipfile.ZipFile(path) as z:
        name = z.namelist()[0]
        with z.open(name) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))


def run(naevn: str, wanted: list[str] | None, outdir: Path, prefix: str) -> None:
    session = requests.Session()
    session.headers["User-Agent"] = UA
    topics = get_topics(session, naevn)
    if wanted:
        lw = {w.lower() for w in wanted}
        topics = [t for t in topics if t["title"].lower() in lw]
        missing = lw - {t["title"].lower() for t in topics}
        if missing:
            print("Ukendte kategorier:", missing, file=sys.stderr)
    for t in topics:
        path = outdir / f"{prefix}_{slug(t['title'])}.csv.zip"
        rows = fetch_topic(session, naevn, t)
        write_csv_zip(path, rows)
        print(f"  gemt {len(rows)} -> {path}")
        time.sleep(SLEEP_SEC)

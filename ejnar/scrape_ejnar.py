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


_DK_MND = {
    "januar": 1, "februar": 2, "marts": 3, "april": 4, "maj": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "okt": 10, "nov": 11, "dec": 12,
}


def extract_kendelse_date(tekst: str) -> str:
    """Træk afsigelsesdatoen ud af kendelsens PDF-tekst.

    Typisk format i AKF-kendelser:
        'Den 29. maj 2006 blev i sag nr. 66.295: ...'
        'København, den 12. december 2018'
        '12. december 2018'
    Returnér 'YYYY-MM-DD' eller tom streng."""
    if not tekst:
        return ""
    # Mønster: (valgfrit "Den") + dag + ". " + mdr + " " + årstal
    pat = re.compile(
        r"(?:Den|den)?\s*(\d{1,2})\.\s*(januar|februar|marts|april|maj|juni|juli|"
        r"august|september|oktober|november|december|jan|feb|mar|apr|jun|jul|aug|"
        r"sep|okt|nov|dec)\s+(19\d{2}|20\d{2})",
        flags=re.IGNORECASE,
    )
    # Læs kun de første 3000 tegn (afsigelsesdatoen står næsten altid på side 1)
    m = pat.search(tekst[:3000])
    if not m:
        return ""
    dag = int(m.group(1))
    mdr = _DK_MND.get(m.group(2).lower())
    aar = int(m.group(3))
    if not mdr:
        return ""
    return f"{aar:04d}-{mdr:02d}-{dag:02d}"


def extract_kendelse_sagsnr(tekst: str) -> str:
    """Hent referencenummer som 'NNN/YY' fra øverste højre hjørne af kendelsen."""
    if not tekst:
        return ""
    m = re.search(r"\b(\d{1,4}/\d{2})\b", tekst[:500])
    return m.group(1) if m else ""


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
        # Ask SharePoint to also include candidate CN/sagsnummer fields.
        # If a property doesn't exist server-side it's silently ignored
        # (single bad name → 500 only when MIXED with valid; safe-list).
        "selectproperties":           "'CN,AnkeforsikringCN,AnkeforsikringCaseNumber,"
                                       "AnkeforsikringSagsnummer,AnkeforsikringRulingNumber,"
                                       "ListItemID,SPListItemID,owsCN,owsCN0,"
                                       "AnkeforsikringRulingDate,AnkeforsikringInsuranceType,"
                                       "AnkeforsikringCompanyName,AnkeforsikringSummary,"
                                       "Title,Path,OriginalPath,Write,LastModifiedTime'",
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
        sagsnr = (d.get("AnkeforsikringCaseNumber") or
                  d.get("CaseNumber") or "")
        if not sagsnr:
            # Hvis vi ikke har et sagsnummer kan vi ikke lave en offentlig URL
            continue
        public_url = f"{BASE_URL}/adm-ankenaevnet/Sider/viewdoc.aspx?CN={sagsnr}"
        # Internal BDC path bevares til evt. fuld-tekst download
        bdc_path = d.get("OriginalPath") or d.get("Path") or ""
        out.append({
            "Titel":      d.get("AnkeforsikringSummary") or d.get("Title") or "",
            "Link":       public_url,
            "BDCPath":    bdc_path,
            "Dato":       parse_sp_date(
                d.get("AnkeforsikringRulingDate") or
                d.get("Write") or ""),
            "Sagsnummer": sagsnr,
            "Selskab":    (d.get("AnkeforsikringCompanyName") or
                           d.get("CompanyName") or ""),
            "RulingType": (d.get("AnkeforsikringRulingType") or
                           d.get("RulingType") or ""),
            "ApiSummary": (d.get("AnkeforsikringSummary") or ""),
            "_alle_felter": d,
        })
    return out, int(total)


def _extract_doc_url(html: str) -> str:
    """Find URL'en til den indlejrede Word-fil i en viewdoc.aspx-side.

    Word vises i en Office-viewer der indlæser dokumentet via en URL i
    iframe-src, et data-attribut eller et JavaScript-objekt som fx
    'sourceDoc' / 'WopiSrc' / 'fileUrl'. Vi prøver flere mønstre."""
    # 1. Iframe / embed med .doc/.docx
    for pat in (
        r'src=["\']([^"\']+\.docx?(?:\?[^"\']*)?)["\']',
        r'data-doc=["\']([^"\']+)["\']',
        r'WopiSrc["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'sourceDoc["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'fileUrl["\']?\s*[:=]\s*["\']([^"\']+)["\']',
        r'(/adm-ankenaevnet/[^\s"\']+\.docx?)',
    ):
        m = re.search(pat, html, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _docx_to_text(content: bytes) -> str:
    """Træk tekst ud af en .docx eller (gammel) .doc fil."""
    # .docx er en zip — læs document.xml direkte uden afhængigheder
    try:
        import zipfile, io as _io, xml.etree.ElementTree as ET
        with zipfile.ZipFile(_io.BytesIO(content)) as z:
            if "word/document.xml" in z.namelist():
                xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
                # Strip namespace, så <w:t>tekst</w:t> bliver pænt
                xml_clean = re.sub(r'\s+xmlns[^=]*="[^"]*"', '', xml)
                xml_clean = re.sub(r'<[^/][^>]*:', '<', xml_clean)
                xml_clean = re.sub(r'</[^>]*:', '</', xml_clean)
                root = ET.fromstring(xml_clean)
                paragraphs = []
                for p in root.iter('p'):
                    txt = "".join(t.text or "" for t in p.iter('t'))
                    if txt.strip():
                        paragraphs.append(txt.strip())
                return "\n\n".join(paragraphs)
    except Exception:
        pass

    # Gammel .doc binær — prøv python-docx2txt hvis tilgængelig
    try:
        import docx2txt, tempfile
        with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
            tmp.write(content)
            tmp.flush()
            return docx2txt.process(tmp.name)
    except Exception:
        pass

    # Fald-tilbage: prøv at trække ASCII-tekst ud af binær-blobben
    text = content.decode("latin-1", errors="ignore")
    # Behold kun printbare karakterer + danske bogstaver + linjeskift
    text = re.sub(r'[^\x20-\x7eæøåÆØÅ\n]', ' ', text)
    text = re.sub(r'\s{3,}', '\n\n', text)
    return text.strip()


def _looks_like_doc(content: bytes) -> str | None:
    """Returnér 'docx', 'doc', 'pdf' eller None alt efter binær-signaturen."""
    if not content or len(content) < 8:
        return None
    if content[:4] == b'PK\x03\x04':
        return "docx"
    if content[:4] == b'\xd0\xcf\x11\xe0':
        return "doc"
    if content[:5] == b'%PDF-':
        return "pdf"
    return None


def _pdf_to_text(content: bytes) -> str:
    """Træk tekst ud af en PDF. Forsøger pypdf, derefter pdfminer.six."""
    # pypdf (mest udbredt, pure-python)
    try:
        import io as _io
        from pypdf import PdfReader
        reader = PdfReader(_io.BytesIO(content))
        sider = []
        for page in reader.pages:
            try:
                sider.append(page.extract_text() or "")
            except Exception:
                pass
        text = "\n\n".join(s.strip() for s in sider if s.strip())
        if text:
            return text
    except ImportError:
        pass
    except Exception:
        pass

    # pdfminer.six (mere robust)
    try:
        import io as _io
        from pdfminer.high_level import extract_text
        text = extract_text(_io.BytesIO(content))
        if text:
            return text.strip()
    except ImportError:
        pass
    except Exception:
        pass

    return ""


def fetch_kendelse_text(session: requests.Session, url: str, debug: bool = False) -> str:
    """Hent fuld tekst fra en viewdoc.aspx-kendelses-side.

    viewdoc.aspx leverer ofte Word-filen direkte (ikke en HTML-side med
    en viewer). Vi henter med Accept der signalerer at vi gerne vil have
    den rå fil, og parser bytes som .doc/.docx hvis signaturerne matcher.
    Falder tilbage til HTML-parsing hvis det er en almindelig side."""
    try:
        r = session.get(url, headers={
            "User-Agent": DEFAULT_HEADERS["User-Agent"],
            "Accept":     "application/msword,application/vnd.openxmlformats-officedocument.wordprocessingml.document,*/*",
            "Accept-Language": "da,en;q=0.7",
            "Referer":    f"{BASE_URL}/kendelser/Sider/kendelser.aspx",
        }, timeout=30)
        r.raise_for_status()
    except requests.RequestException as e:
        if debug:
            print(f"  Fejl ved {url}: {e}")
        return ""

    ct = (r.headers.get("Content-Type") or "").lower()
    body_kind = _looks_like_doc(r.content)
    if debug:
        print(f"  HTTP {r.status_code} | Content-Type: {ct[:60]} | "
              f"signatur: {body_kind} | størrelse: {len(r.content)} bytes")

    # 1a. Hvis svaret ER en PDF → parse direkte
    if body_kind == "pdf" or "application/pdf" in ct:
        text = _pdf_to_text(r.content)
        if text and len(text) > 200:
            return text
        if debug:
            print(f"  PDF-parsing gav kun {len(text or '')} tegn — "
                  f"installér pypdf eller pdfminer.six?")

    # 1b. Hvis svaret ER en Word-fil → parse direkte
    if body_kind in ("doc", "docx") or "officedocument" in ct or "msword" in ct:
        text = _docx_to_text(r.content)
        if text and len(text) > 200:
            return text
        if debug:
            print(f"  Word-parsing gav kun {len(text or '')} tegn")

    # 2. Ellers: forsøg at finde en .doc-URL i HTML'en (gammel sti)
    doc_url = _extract_doc_url(r.text)
    if doc_url:
        if not doc_url.startswith("http"):
            doc_url = urljoin(BASE_URL, doc_url)
        if debug:
            print(f"  Fundet doc-URL i HTML: {doc_url}")
        try:
            r2 = session.get(doc_url, headers={
                "User-Agent": DEFAULT_HEADERS["User-Agent"],
                "Accept":     "*/*",
                "Referer":    url,
            }, timeout=30)
            r2.raise_for_status()
            text = _docx_to_text(r2.content)
            if text and len(text) > 200:
                return text
            if debug:
                print(f"  doc-tekst kun {len(text)} tegn — falder tilbage til HTML")
        except requests.RequestException as e:
            if debug:
                print(f"  Fejl ved doc-download {doc_url}: {e}")

    # Fald-tilbage: forsøg at hive synlig tekst ud af viewdoc.aspx-siden
    soup = BeautifulSoup(r.text, "html.parser")
    for sel in ("#contentBox", "#mainContent", ".ms-rtestate-field",
                "main", "article", "#DeltaPlaceHolderMain", ".s4-ca"):
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


def _sanitize(s):
    """Fjern lone surrogates og andre ugyldige UTF-8-sekvenser fra en streng.
    Gamle scannede PDF'er kan indeholde tegn som '\\udbc0' (et halvt surrogate-par)
    som Python ikke kan skrive til en utf-8-fil — vi smider dem væk."""
    if not isinstance(s, str):
        return s
    if not s:
        return s
    # Fjern lone surrogates (\ud800-\udfff)
    cleaned = re.sub(r'[\ud800-\udfff]', '', s)
    # Round-trip via utf-8 for at fange andre ugyldige sekvenser
    return cleaned.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def append_rows(path: Path, rows: list[dict]) -> None:
    write_header = not path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        if write_header:
            w.writeheader()
        for r in rows:
            clean = {k: _sanitize(r.get(k, "")) for k in FIELDNAMES}
            try:
                w.writerow(clean)
            except (UnicodeEncodeError, ValueError) as e:
                print(f"  ⚠ kunne ikke skrive række ({e}); springer over: "
                      f"{(clean.get('Link') or '')[:80]}")
                continue


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

        # Datoen fra PDF-teksten er den korrekte afsigelsesdato. SharePoint's
        # Write/LastModifiedTime er kun at-data, så den overskriver vi.
        pdf_dato = extract_kendelse_date(tekst)
        # Reference-nummer (749/06 i øverste højre hjørne) — ofte mere brugbart
        # som visnings-reference end SharePoint's interne CN.
        pdf_ref = extract_kendelse_sagsnr(tekst)

        # Brug AnkeforsikringCaseNumber som primært sagsnummer (= CN i URL'en),
        # men hvis der er et tydeligere "NNN/ÅÅ" øverst i kendelsen, tag det med.
        sagsnr_kombineret = a.get("Sagsnummer", "")
        if pdf_ref and pdf_ref != sagsnr_kombineret:
            sagsnr_kombineret = f"{sagsnr_kombineret} ({pdf_ref})" if sagsnr_kombineret else pdf_ref

        batch.append({
            "Dato":            pdf_dato or a["Dato"],
            "Titel":           a["Titel"],
            "Link":            a["Link"],
            "Tekst":           tekst,
            "Sagsnummer":      sagsnr_kombineret,
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

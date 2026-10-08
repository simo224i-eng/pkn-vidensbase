"""
Hent afgørelser, hvor teksten kun findes som PDF-dokument (tom brødtekst i API'et).

    python fetch_pdf_afgoerelser.py

Læser data_2026/*.csv.zip, finder rækker med under 200 tegns tekst fra 2017 og frem,
henter /api/publication/{id} og PDF'en under /media/<file>, udtrækker teksten og
gemmer data_2026/pdf_afgoerelser.csv.zip i samme format. Korpusset
(ejnar/miljoejurist/corpus.py) foretrækker den længste tekst pr. id.
"""
import io
import re
import sys
import time
from pathlib import Path

import pdfplumber
import requests

import naevn_api

OUT = Path("data_2026/pdf_afgoerelser.csv.zip")


def main():
    tomme = []
    for p in sorted(Path("data_2026").glob("*.csv.zip")):
        if p.name == OUT.name:
            continue
        for r in naevn_api.read_csv_zip(p):
            if len(r["Tekst"]) < 200 and r["Dato"] >= "2017":
                tomme.append(r)
    print(f"{len(tomme)} afgørelser uden brødtekst")
    s = requests.Session()
    s.headers["User-Agent"] = naevn_api.UA
    ud, set_ = [], set()
    for i, r in enumerate(tomme, 1):
        if r["id"] in set_:
            continue
        set_.add(r["id"])
        base = naevn_api.base_url(r["Naevn"].lower())
        try:
            d = s.get(f"{base}/api/publication/{r['id']}", timeout=60).json()
            time.sleep(naevn_api.SLEEP_SEC)
            docs = d.get("documents") or []
            tekster = []
            for doc in docs:
                pdf = s.get(f"{base}/media/{doc['file']}", timeout=120)
                time.sleep(naevn_api.SLEEP_SEC)
                if pdf.status_code != 200 or not pdf.content.startswith(b"%PDF"):
                    continue
                with pdfplumber.open(io.BytesIO(pdf.content)) as f:
                    tekster.append("\n".join((pg.extract_text() or "") for pg in f.pages))
            tekst = re.sub(r"[ \t]+", " ", "\n\n".join(tekster)).strip()
        except Exception as e:
            print(f"  fejl {r['id']}: {e}", file=sys.stderr)
            continue
        if len(tekst) >= 200:
            ud.append({**r, "Tekst": tekst})
        print(f"  {i}/{len(tomme)} {len(tekst)} tegn", flush=True)
        if i % 50 == 0:
            naevn_api.write_csv_zip(OUT, ud)
    naevn_api.write_csv_zip(OUT, ud)
    print(f"gemt {len(ud)} -> {OUT}")


if __name__ == "__main__":
    main()

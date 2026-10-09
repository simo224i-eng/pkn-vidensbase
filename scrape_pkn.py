"""
PKN-scraper: henter Planklagenævnets afgørelser fra pkn.naevneneshus.dk.

Søge-API'et returnerer den fulde tekst, og kategori-id'erne hentes automatisk
fra /api/sitesettings (ingen cookie). Max ca. 1 forespørgsel pr. sekund.

Brug:
  python scrape_pkn.py --list
  python scrape_pkn.py --relevante                 # miljøvurdering, VVM, planloven
  python scrape_pkn.py --kategori "Miljøvurderingsloven"
  python scrape_pkn.py --alle

Output: data_2026/pkn_<kategori>.csv.zip med kolonnerne
id, Naevn, Jnr, Dato, Titel, Link, Retsomraade, Tekst.
De gamle filer i repo-roden (pkn_*.csv.zip) røres ikke.
"""

import argparse
from pathlib import Path

import requests

import naevn_api

RELEVANTE = [
    "Miljøvurderingsloven",
    "Planloven, VVM",
    "Planloven, retlig (efter 1. februar 2017)",
    "Planloven, landzone (efter 1. februar 2017)",
    "Planloven, retlig (før 1. februar 2017)",
    "Planloven, landzone (før 1. februar 2017)",
    "Sommerhusloven",
    "Ekspropriation",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--kategori", action="append", default=[])
    ap.add_argument("--relevante", action="store_true")
    ap.add_argument("--alle", action="store_true")
    ap.add_argument("--outdir", default="data_2026")
    a = ap.parse_args()
    if a.list:
        s = requests.Session(); s.headers["User-Agent"] = naevn_api.UA
        for t in naevn_api.get_topics(s, "pkn"):
            print(t["id"], t["title"])
        return
    wanted = None if a.alle else (RELEVANTE if a.relevante else a.kategori)
    if wanted == []:
        ap.error("angiv --kategori, --relevante eller --alle")
    naevn_api.run("pkn", wanted, Path(a.outdir), "pkn")


if __name__ == "__main__":
    main()

"""
MFKN-scraper: henter Miljø- og Fødevareklagenævnets afgørelser fra
mfkn.naevneneshus.dk.

Søge-API'et returnerer den fulde tekst, og kategori-id'erne hentes automatisk
fra /api/sitesettings (ingen cookie). Max ca. 1 forespørgsel pr. sekund.

Brug:
  python scrape_mfkn.py --list
  python scrape_mfkn.py --relevante      # miljøvurdering, husdyr, natur, miljø m.fl.
  python scrape_mfkn.py --kategori "Husdyrbrugloven"
  python scrape_mfkn.py --alle

Output: data_2026/mfkn_<kategori>.csv.zip med kolonnerne
id, Naevn, Jnr, Dato, Titel, Link, Retsomraade, Tekst.
De gamle filer i repo-roden (mfkn_*.csv.zip) røres ikke.
"""

import argparse
from pathlib import Path

import requests

import naevn_api

RELEVANTE = [
    "Miljøvurdering af konkrete projekter",
    "Miljøvurdering af planer og programmer",
    "Husdyrbrugloven",
    "Miljøbeskyttelsesloven",
    "NBL - beskyttede naturtyper",
    "NBL - beskyttelseslinier",
    "NBL - øvrige",
    "NBL - fredningsområdet",
    "Fredning mv.",
    "Råstofloven",
    "Vandløbsloven",
    "Vandforsyningsloven",
    "Kystbeskyttelsesloven",
    "Skovloven",
    "Jordforureningsloven",
    "Miljømålsloven og vandplanlægningsloven",
    "Havmiljøloven",
    "Museumsloven",
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
        for t in naevn_api.get_topics(s, "mfkn"):
            print(t["id"], t["title"])
        return
    wanted = None if a.alle else (RELEVANTE if a.relevante else a.kategori)
    if wanted == []:
        ap.error("angiv --kategori, --relevante eller --alle")
    naevn_api.run("mfkn", wanted, Path(a.outdir), "mfkn")


if __name__ == "__main__":
    main()

"""
Find de EU-domme, som PKN og MFKN oftest citerer i miljøsager, og hent dem på
dansk fra EUR-Lex til eu_domme/.

    python fetch_eu_domme.py [--antal 30]

Optællingen bruger det rensede korpus (ejnar/miljoejurist/corpus.py) og tæller
hver dom én gang pr. afgørelse. Sagsnumre skrives fx "C-127/02" eller "C‑127/02".
CELEX-nummeret er 6 + årstal + CJ + løbenummer med fire cifre (domme fra
Domstolen). Findes der ingen dansk dom (fx kendelser), forsøges CO (kendelse).
"""

import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "ejnar"))
from miljoejurist import corpus  # noqa: E402

OUT = ROOT / "eu_domme"
SAG_RE = re.compile(r"\b(C|T)\s?[-‑–]\s?(\d{1,3})\s?/\s?(\d{2})\b")


def tæl(korpus) -> collections.Counter:
    c = collections.Counter()
    for a in korpus:
        fundet = {f"{m[0]}-{int(m[1])}/{m[2]}" for m in SAG_RE.findall(a.tekst)}
        c.update(fundet)
    return c


def celex(sag: str, typ: str = "CJ") -> str:
    m = re.match(r"(C|T)-(\d+)/(\d{2})", sag)
    nr, yy = int(m.group(2)), int(m.group(3))
    aar = 1900 + yy if yy > 50 else 2000 + yy
    kode = typ if m.group(1) == "C" else typ.replace("C", "T", 1)
    return f"6{aar}{kode}{nr:04d}"


def hent(s: requests.Session, sag: str) -> dict | None:
    for typ in ("CJ", "CO"):
        cx = celex(sag, typ)
        url = f"https://eur-lex.europa.eu/legal-content/DA/TXT/HTML/?uri=CELEX:{cx}"
        r = s.get(url, timeout=60)
        if r.status_code != 200 or len(r.text) < 5000:
            time.sleep(1)
            continue
        soup = BeautifulSoup(r.text, "lxml")
        for t in soup(["script", "style"]):
            t.decompose()
        tekst = soup.get_text("\n")
        tekst = re.sub(r"[ \t\xa0]+", " ", tekst)
        tekst = re.sub(r"\s*\n\s*", "\n", tekst).strip()
        if "Domstolen" not in tekst and "DOMSTOLENS" not in tekst:
            time.sleep(1)
            continue
        titel = next((ln for ln in tekst.splitlines() if sag.split("/")[0][2:] in ln), "")[:300]
        return {"sag": sag, "celex": cx, "url": url.replace("/HTML/", "/"), "titel": titel, "tekst": tekst}
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--antal", type=int, default=30)
    a = ap.parse_args()
    k = corpus.load()
    miljø = [x for x in k if any(re.search(r"miljøvurdering|VVM|husdyr|NBL|naturtyper|Planloven", c) for c in x.kategorier)]
    c = tæl(miljø)
    OUT.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (pkn-vidensbase)"
    index = []
    for sag, n in c.most_common(a.antal + 15):
        if len(index) >= a.antal:
            break
        d = hent(s, sag)
        time.sleep(1)
        if not d:
            print(f"{sag}: ikke fundet på dansk")
            continue
        fn = sag.replace("/", "-") + ".txt"
        (OUT / fn).write_text(d.pop("tekst"), encoding="utf-8")
        d.update({"fil": fn, "citeret_i_afgoerelser": n})
        index.append(d)
        print(f"{sag}: citeret i {n} afgørelser, {d['celex']}")
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

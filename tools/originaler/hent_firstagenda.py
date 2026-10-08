"""Find kommunernes oprindelige screeninger på FirstAgenda-dagsordener.

    python tools/originaler/hent_firstagenda.py [--kun-plan] [--max N]

For hver screeningssag (analyser/miljoevurdering/v2/originaler_kandidater.json), hvor kommunen bruger
FirstAgenda (tools/originaler/firstagenda.json), søges der i dagsordenerne efter plannummeret (planer)
eller projektets nøgleord (projekter). Møder tæt på (og før) myndighedens afgørelse foretrækkes. I det
fundne dagsordenpunkt vælges bilag, hvis navn ligner en screening.

Output (tools/originaler/fund_firstagenda.json): pr. sag kandidater med møde, punkt, bilag og URL.
Selve PDF'erne hentes ikke her; kun links (de kan indeholde navne og hører ikke i repoet).
Max ca. 1 forespørgsel pr. sekund pr. kommune.
"""
from __future__ import annotations

import argparse
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import json
import re
import time
import urllib.parse as up
from datetime import date
from pathlib import Path

import requests

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
KAND = REPO / "analyser" / "miljoevurdering" / "v2" / "originaler_kandidater.json"
UD = HER / "fund_firstagenda.json"
SEL = {"Id": "true", "Udvalg": {"Navn": "true"}, "Moede": {"Id": "true", "Dato": "true"}}
SCREENING_RX = re.compile(r"screening|miljøvurdering|miljøscreening|afgørelse om ikke|ikke miljøvurderingspligt|VVM", re.I)
STOP = set("""afgørelse klagesag kommunes kommune screeningsafgørelse forslag til om at for af og
i på ikke skal miljøvurderes miljøvurdering omfattet krav ophævelse hjemvisning stadfæstelse medhold
klage over etablering den det en et med lokalplan kommuneplantillæg nr tillæg samt ved fra
dele matr eksisterende anvendelse ændring virksomhed projekt projektet miljøvurderingsloven reglerne""".split())


def søg(s, base, tekst, år=None, limit=20):
    q = (f"{base}/api/agenda/soeg/?request.select={up.quote(json.dumps(SEL))}&request.kriterie.udvalgId="
         f"&request.kriterie.fritekst={up.quote(tekst)}&request.paging.startIndex=0&request.paging.limit={limit}")
    if år:
        q += f"&request.kriterie.moedeDato={år}"
    r = s.get(q, timeout=40)
    r.raise_for_status()
    return r.json().get("Dagsordner", [])


def dagsorden(s, base, did, tekst):
    r = s.get(f"{base}/api/agenda/dagsorden/{did}?fritekst={up.quote(tekst)}", timeout=60)
    r.raise_for_status()
    return r.json()


def nøgleord(k: dict) -> list[str]:
    """Søgeforespørgsler: plantype + nummer først, ellers særprægede ord fra det screenede objekt."""
    ud = []
    kilde = f"{k.get('objekt', '')} {' '.join(k.get('planer') or [])} {k['titel']}"
    for typ, nr in re.findall(r"(lokalplan|kommuneplantillæg|tillæg|spildevandsplan|klimatilpasningsplan|"
                              r"varmeplan|vandforsyningsplan|planforslag)\w*\s+(?:nr\.\s*)?([\w./-]*\d[\w./-]*)", kilde, re.I):
        nr = nr.strip(" .,")
        typ = "tillæg" if typ.lower().startswith(("kommuneplantillæg", "tillæg")) else typ.lower()
        q = f"{typ} {nr}"
        if q not in ud:
            ud.append(q)
    obj = re.sub(r"\[[^\]]*\]", " ", k.get("objekt") or k["titel"])
    ord_ = [w for w in re.findall(r"[A-Za-zÆØÅæøå\-]{4,}", obj) if w.lower() not in STOP]
    # Særprægede ord: egennavne og lange ord først
    ord_.sort(key=lambda w: (not w[0].isupper(), -len(w)))
    if ord_:
        ud.append(" ".join(dict.fromkeys(ord_[:3])))
    return ud[:3]


def score(møde_dato: str, afg: str | None, punkt_navn: str, forespørgsel: str, bilag_navne: list[str]) -> float:
    sc = 0.0
    if afg:
        d = (date.fromisoformat(afg) - date.fromisoformat(møde_dato[:10])).days
        if 0 <= d <= 200:
            sc += 2 - d / 200      # møde før afgørelsen, jo tættere jo bedre
        elif -30 <= d < 0:
            sc += 0.5
        else:
            sc -= 1
    nr = re.findall(r"\d[\w./-]*", forespørgsel)
    if nr and any(n.lower() in punkt_navn.lower() for n in nr):
        sc += 2
    if any(SCREENING_RX.search(b) for b in bilag_navne):
        sc += 1.5
    if re.search(r"forslag|høring|vedtagelse|screening", punkt_navn, re.I):
        sc += 0.5
    return round(sc, 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kun-plan", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    a = ap.parse_args()
    portaler = json.loads((HER / "firstagenda.json").read_text(encoding="utf-8"))
    kand = json.loads(KAND.read_text(encoding="utf-8"))
    fund = json.loads(UD.read_text(encoding="utf-8")) if UD.exists() else {}
    opgaver = defaultdict(list)
    for k in kand:
        base = portaler.get(k["myndighed"] or "")
        if not base or k["id"] in fund or k.get("fredningsnaevn") or (a.kun_plan and k["type"] != "screening_plan"):
            continue
        opgaver[base].append(k)
    if a.max:
        opgaver = dict(list(opgaver.items())[: a.max])
    lås = threading.Lock()

    def kommune(base, sager):
        s = requests.Session()
        s.headers["User-Agent"] = "Mozilla/5.0 (pkn-vidensbase research; 1 req/s)"
        for k in sager:
            entry = behandl(s, base, k)
            bedst = entry["kandidater"][0] if entry["kandidater"] else None
            with lås:
                fund[k["id"]] = entry
                UD.write_text(json.dumps(fund, ensure_ascii=False, indent=1), encoding="utf-8")
                print(k["id"], k["myndighed"], "->", (bedst["møde"], bedst["punkt"][:60], bedst["score"],
                                                       len(bedst["screening_bilag"])) if bedst else "intet", flush=True)

    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(lambda kv: kommune(*kv), opgaver.items()))
    print("FÆRDIG", len(fund), flush=True)


def behandl(s, base, k) -> dict:
    afg = k.get("afgoerelse_dato")
    år = (afg or k["naevn_dato"])[:4]
    kandidater = []
    for q in nøgleord(k):
        for y in dict.fromkeys([år, str(int(år) - 1)]):
            try:
                res = søg(s, base, q, y)
            except Exception as e:
                print("  søgefejl", k["id"], e, flush=True)
                res = []
            time.sleep(1)
            if afg:  # nærmeste møder før afgørelsen først
                res.sort(key=lambda d: abs((date.fromisoformat(afg) - date.fromisoformat(d["Moede"]["Dato"][:10])).days - 30))
            for d in res[:4]:
                try:
                    dg = dagsorden(s, base, d["Id"], q)
                except Exception:
                    continue
                time.sleep(1)
                for p in dg.get("Dagsordenpunkter", []):
                    navn = p.get("Navn") or ""
                    tekst = " ".join(f.get("Html") or "" for f in p.get("Felter") or [])
                    nr = re.findall(r"\d[\w./-]*", q)
                    if nr and not any(x.lower() in (navn + tekst).lower() for x in nr):
                        continue
                    if not nr and not all(w.lower() in (navn + tekst).lower() for w in q.split()[:2]):
                        continue
                    bilag = [{"navn": b.get("Navn"), "url": f"{base}/vis/pdf/bilag/{b['Id']}/?redirectDirectlyToPdf=false"}
                             for b in p.get("Bilag") or []]
                    kandidater.append({
                        "forespørgsel": q, "møde": d["Moede"]["Dato"][:10], "udvalg": d["Udvalg"]["Navn"],
                        "punkt": navn, "punkt_url": f"{base}/vis?id={d['Id']}",
                        "punkt_pdf": f"{base}/vis/pdf/dagsordenpunkt/{p['Id']}?redirectDirectlyToPdf=false",
                        "screening_bilag": [b for b in bilag if SCREENING_RX.search(b["navn"] or "")],
                        "bilag": bilag[:12], "bilag_antal": len(bilag),
                        "score": score(d["Moede"]["Dato"], afg, navn, q, [b["navn"] or "" for b in bilag])})
            if kandidater:
                break
        if any(c["score"] >= 3 for c in kandidater):
            break
    kandidater.sort(key=lambda c: -c["score"])
    return {"myndighed": k["myndighed"], "type": k["type"], "afgoerelse_dato": afg, "kandidater": kandidater[:4]}


if __name__ == "__main__":
    main()

"""Forbered testsættene til Miljøjuristen (punkt 6).

    python ejnar/evaluation/miljoejurist/forbered_test.py

Laver ejnar/evaluation/miljoejurist/work/ (gitignoreret, indeholder sagstekster):
  T1  30 underkendte screeninger: sagsfremstillingen UDEN nævnets vurdering, indledning og titel,
      så en skribent kan rekonstruere kommunens screening uden at kende afgørelsen.
  T3  20 stadfæstede screeninger: samme, til falske alarmer og (T2) indsatte fejl.
Facit (nævnets fejlkategorier) gemmes i facit.json (i repoet; uden sagstekst).
"""
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HER = Path(__file__).resolve().parent
REPO = HER.parents[2]
V2 = REPO / "analyser" / "miljoevurdering" / "v2"
sys.path.insert(0, str(REPO / "ejnar"))
from miljoejurist import corpus  # noqa: E402

WORK = HER / "work"
SCREENING = ("screening_projekt", "screening_plan")


def fremstilling(tekst: str) -> str | None:
    """Teksten fra første overskrift til (ikke med) nævnets vurdering. None hvis den ikke kan findes."""
    secs = corpus.sektioner(tekst)
    if len(secs) < 3:
        return None
    ud = []
    for h, t in secs[1:]:
        if corpus.VURDERING_RE.search(h) or re.search(r"nævnets (bemærkninger|vurdering|afgørelse)|klagenævnets kompetence", h, re.I):
            break
        if re.match(r"^\s*(Indhold|Klagevejledning)", h):
            continue
        ud.append(f"## {h}\n{t.strip()}")
    txt = "\n\n".join(ud)
    # Fjern nævnets egne henvisninger til udfaldet, hvis de står i sagsfremstillingen
    txt = re.sub(r"[^.\n]*(Planklagenævnet|Miljø- og Fødevareklagenævnet|nævnet) (ophæver|stadfæster|hjemviser|giver)[^.\n]*\.", "", txt)
    return txt if len(txt) > 2500 else None


def main():
    WORK.mkdir(exist_ok=True)
    (WORK / "fremstilling").mkdir(exist_ok=True)
    rng = random.Random(20261008)
    praksis = json.loads((REPO / "ejnar" / "miljoejurist" / "data" / "praksis.json").read_text(encoding="utf-8"))
    sagstekst = {}

    def tekst(i):
        if i not in sagstekst:
            p = V2 / "sager" / f"{i}.txt"
            t = p.read_text(encoding="utf-8") if p.exists() else ""
            sagstekst[i] = t.split("=== HELE AFGØRELSEN (sagsfremstilling og nævnets vurdering) ===\n", 1)[-1]
        return sagstekst[i]

    # T1: underkendte screeninger, spredt over fejlkategorier
    kand = []
    for s in praksis:
        if s["dokumenttype"] not in SCREENING or s["dato"] < "2020-06-01":
            continue
        afg = [f for f in s["fejl"] if f.get("afgoerende")] or s["fejl"]
        f = fremstilling(tekst(s["id"]))
        if f:
            kand.append((s, afg, f))
    rng.shuffle(kand)
    valgt, pr_kat = [], Counter()
    for s, afg, f in sorted(kand, key=lambda x: -len(x[1])):
        k = afg[0]["fejlkategori"]
        if pr_kat[k] >= 4:
            continue
        valgt.append((s, afg, f))
        pr_kat[k] += 1
        if len(valgt) >= 30:
            break

    facit = {}
    for n, (s, afg, f) in enumerate(valgt, 1):
        tid = f"T1_{n:02d}"
        (WORK / "fremstilling" / f"{tid}.txt").write_text(f, encoding="utf-8")
        facit[tid] = {"sag": s["id"], "gruppe": "T1", "dokumenttype": s["dokumenttype"], "dato": s["dato"],
                      "link": s["link"], "kategorier": sorted({x["fejlkategori"] for x in afg}),
                      "alle_kategorier": sorted({x["fejlkategori"] for x in s["fejl"]}),
                      "fejl": [x["fejl"] for x in afg]}

    # T3: stadfæstede screeninger
    s1 = [json.loads(l) for l in open(V2 / "s1_genbrug.jsonl", encoding="utf-8")]
    for f in sorted((V2 / "s1_ny").glob("*.jsonl")):
        s1 += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    stad = [d for d in s1 if d.get("udfald") == "stadfæstet" and d.get("behandlet_paa_indhold")
            and d.get("afgoerelsestype") in SCREENING and u.get(d["id"], {}).get("dato", "") >= "2020-06-01"]
    rng.shuffle(stad)
    n = 0
    for d in stad:
        f = fremstilling(tekst(d["id"]))
        if not f:
            continue
        n += 1
        tid = f"T3_{n:02d}"
        (WORK / "fremstilling" / f"{tid}.txt").write_text(f, encoding="utf-8")
        facit[tid] = {"sag": d["id"], "gruppe": "T3", "dokumenttype": d["afgoerelsestype"],
                      "dato": u[d["id"]]["dato"], "link": u[d["id"]]["link"], "kategorier": [], "fejl": []}
        if n >= 20:
            break
    (HER / "facit.json").write_text(json.dumps(facit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"T1: {len(valgt)} ({dict(pr_kat)}), T3: {n}")


if __name__ == "__main__":
    main()

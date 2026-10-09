"""Forbered audit v1: 20 ophævede + 20 stadfæstede screeninger, som ingen tidligere test har brugt.

    python miljoejurist/evaluation/forbered_audit.py

Skriver work/audit/fremstilling/A_xx.txt (sagsfremstilling uden nævnets vurdering; gitignoreret)
og audit_facit.json (sag, gruppe, nævnets afgørende fejl; uden sagstekst).
"""
import glob
import json
import random
import re
from pathlib import Path

from forbered_test import REPO, SCREENING, V2, WORK, fremstilling

HER = Path(__file__).resolve().parent
UD = WORK / "audit"


def main():
    (UD / "fremstilling").mkdir(parents=True, exist_ok=True)
    rng = random.Random(20261009)
    brugt = set()
    for f in glob.glob(str(HER / "*.json")):
        if "audit" not in f:
            brugt |= set(re.findall(r"[PM][0-9a-f]{8}", open(f, encoding="utf-8").read()))
    brugt.add("P1c222e8f")

    def tekst(i):
        p = V2 / "sager" / f"{i}.txt"
        t = p.read_text(encoding="utf-8") if p.exists() else ""
        return t.split("=== HELE AFGØRELSEN (sagsfremstilling og nævnets vurdering) ===\n", 1)[-1]

    praksis = json.loads((REPO / "miljoejurist" / "data" / "praksis.json").read_text(encoding="utf-8"))
    oph = [s for s in praksis if s["dokumenttype"] in SCREENING and s["dato"] >= "2022-01-01" and s["id"] not in brugt]
    rng.shuffle(oph)
    s1 = [json.loads(l) for l in open(V2 / "s1_genbrug.jsonl", encoding="utf-8")]
    for f in sorted((V2 / "s1_ny").glob("*.jsonl")):
        s1 += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    stad = [d for d in s1 if d.get("udfald") == "stadfæstet" and d.get("behandlet_paa_indhold")
            and d.get("afgoerelsestype") in SCREENING and u.get(d["id"], {}).get("dato", "") >= "2022-01-01"
            and d["id"] not in brugt]
    rng.shuffle(stad)

    valgt = []
    for s in oph:
        f = fremstilling(tekst(s["id"]))
        if f:
            afg = [x for x in s["fejl"] if x.get("afgoerende")] or s["fejl"]
            valgt.append(("ophævet", s["id"], s["dokumenttype"], s["dato"], s["link"], afg, f))
        if len(valgt) >= 20:
            break
    n = len(valgt)
    for d in stad:
        f = fremstilling(tekst(d["id"]))
        if f:
            valgt.append(("stadfæstet", d["id"], d["afgoerelsestype"], u[d["id"]]["dato"], u[d["id"]]["link"], [], f))
        if len(valgt) >= n + 20:
            break
    rng.shuffle(valgt)  # blind rækkefølge
    facit = {}
    for i, (gruppe, sid, dt, dato, link, afg, f) in enumerate(valgt, 1):
        aid = f"A_{i:02d}"
        (UD / "fremstilling" / f"{aid}.txt").write_text(f, encoding="utf-8", newline="\n")
        facit[aid] = {"sag": sid, "gruppe": gruppe, "dokumenttype": dt, "dato": dato, "link": link,
                      "kategorier": sorted({x["fejlkategori"] for x in afg}), "fejl": [x["fejl"] for x in afg]}
    (HER / "audit_facit.json").write_text(json.dumps(facit, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    from collections import Counter
    print(len(facit), Counter(v["gruppe"] for v in facit.values()), Counter(v["dokumenttype"] for v in facit.values()))


if __name__ == "__main__":
    main()

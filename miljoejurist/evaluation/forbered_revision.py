"""Læg dokument, rapport og facit klar til revisorerne (work/rev<N>/<blind>/).

    python miljoejurist/evaluation/forbered_revision.py --runde 2 --batches 12
"""
import argparse
import json
import random
import shutil
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
WORK = HER / "work"
sys.path.insert(0, str(HER))
from koer_test import testdokumenter  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runde", default="2")
    ap.add_argument("--batches", type=int, default=12)
    a = ap.parse_args()
    rev = WORK / f"rev{a.runde}"
    rev.mkdir(exist_ok=True)
    ids = []
    for d in testdokumenter():
        rapport = WORK / f"runde{a.runde}" / f"{d['tid']}_model.md"
        if not rapport.exists():
            continue
        mappe = rev / d["blind"]
        mappe.mkdir(exist_ok=True)
        shutil.copy(d["fil"], mappe / "dokument.txt")
        shutil.copy(rapport, mappe / "rapport.md")
        if d["gruppe"] == "T3":
            facit = {"nævnets_fejl": [], "note": "Nævnet stadfæstede afgørelsen."}
        elif d["gruppe"] == "T2":
            facit = {"indsat_fejl": d["kategorier"], "note": "En fejl af denne type er indsat i dokumentet."}
        else:
            facit = {"nævnets_fejl": d.get("fejl", []), "kategorier": d["kategorier"]}
        (mappe / "facit.json").write_text(json.dumps(facit, ensure_ascii=False), encoding="utf-8")
        ids.append(d["blind"])
    random.Random(int(a.runde) * 7).shuffle(ids)
    n = -(-len(ids) // a.batches)
    for b in range(a.batches):
        (WORK / f"rev{a.runde}_{b + 1:02d}.txt").write_text("\n".join(ids[b * n:(b + 1) * n]))
    print(len(ids), "dokumenter i", a.batches, "batches")


if __name__ == "__main__":
    main()

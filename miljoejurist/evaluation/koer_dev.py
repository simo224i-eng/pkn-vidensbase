"""Udviklingssæt til kalibrering af risikovurderingen (T1 = ophævede, T3 = stadfæstede fra runde 1-4).

    python miljoejurist/evaluation/koer_dev.py prompts [--navn v2]   # work/dev_<navn>/prompt/<blind>.md
    python miljoejurist/evaluation/koer_dev.py score   [--navn v2]   # svar/<blind>.json -> tal

Audit-sættet (koer_audit.py) bruges kun til den endelige måling, så der ikke tunes på testen.
"""
import argparse
import json
import sys
from pathlib import Path

from koer_test import WORK, kør, punkt_kategorier, ramt, testdokumenter

HER = Path(__file__).resolve().parent


def _auc(pos, neg):
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)) if pos and neg else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trin", choices=["prompts", "score"])
    ap.add_argument("--navn", default="v2")
    a = ap.parse_args()
    ud = WORK / f"dev_{a.navn}"
    (ud / "prompt").mkdir(parents=True, exist_ok=True)
    (ud / "svar").mkdir(exist_ok=True)
    docs = [d for d in testdokumenter() if d["gruppe"] in ("T1", "T3")]
    pk = punkt_kategorier()
    rows = []
    for d in docs:
        sp = ud / "svar" / f"{d['blind']}.json"
        svar = sp.read_text(encoding="utf-8") if a.trin == "score" and sp.exists() else None
        if a.trin == "score" and svar is None:
            continue
        r, rm, prompt, dok = kør(d, svar)
        if a.trin == "prompts":
            (ud / "prompt" / f"{d['blind']}.md").write_text(prompt, encoding="utf-8")
            continue
        kat = set(d.get("kategorier") or [])
        u = rm.udfald or {}
        rows.append({"tid": d["tid"], "gruppe": d["gruppe"], "type": d.get("dokumenttype"),
                     "p": u.get("sandsynlighed"), "n_risiko": sum(s.niveau == "svaghed" for s in rm.svagheder),
                     "n_høj": sum(s.risiko == "høj" for s in rm.svagheder),
                     "n_opm": sum(s.niveau == "opmærksomhed" for s in rm.svagheder),
                     "ramt_risiko": ramt(rm, kat, pk, kun_svaghed=True) if kat else None,
                     "ramt_alle": ramt(rm, kat, pk) if kat else None})
    if a.trin == "prompts":
        print("prompts:", len(docs))
        return
    (ud / "resultat.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    o = [r for r in rows if r["gruppe"] == "T1"]
    s = [r for r in rows if r["gruppe"] == "T3"]
    print(f"{len(o)} ophævede, {len(s)} stadfæstede")
    po, ps = [r["p"] for r in o if r["p"] is not None], [r["p"] for r in s if r["p"] is not None]
    print(f"sandsynlighed: ophævede gns {sum(po)/len(po):.0f}, stadfæstede gns {sum(ps)/len(ps):.0f}, AUC {_auc(po, ps):.2f}")
    for t in (30, 40, 50, 60):
        print(f"  tærskel {t}: {sum(x >= t for x in po)}/{len(po)} ophævede over, {sum(x < t for x in ps)}/{len(ps)} stadfæstede under")
    for k in ("n_risiko", "n_høj", "n_opm"):
        print(f"{k}: ophævede {sum(r[k] for r in o)/len(o):.1f}, stadfæstede {sum(r[k] for r in s)/len(s):.1f}, "
              f"AUC {_auc([r[k] for r in o], [r[k] for r in s]):.2f}")
    print(f"nævnets kategori blandt risikopunkter: {sum(bool(r['ramt_risiko']) for r in o)}/{len(o)}; "
          f"blandt alle punkter: {sum(bool(r['ramt_alle']) for r in o)}/{len(o)}")


if __name__ == "__main__":
    main()

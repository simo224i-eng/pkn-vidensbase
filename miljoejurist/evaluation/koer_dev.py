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
from miljoejurist import llm_tjek  # noqa: E402

HER = Path(__file__).resolve().parent


AEGTE_STADFAESTET = ["P11b2706a", "P2f921c2f", "P4ffb925f", "P587f909c", "P5bb42397", "P9659ca33", "Padef2fad",
                     "Pc7ec551b", "Pcdc7b0e8", "Pea990052"]  # originaler kontrolleret af Haiku (dom "ok"), stadfæstet


def aegte_dokumenter() -> list[dict]:
    """Ægte myndighedsdokumenter: T4 (ophævede) + Gladsaxe (ophævet) + kontrollerede stadfæstede originaler.
    gruppe T1 = ophævet, T3 = stadfæstet (samme koder som dev-sættet)."""
    repo = HER.parents[1]
    cache = repo / "tools" / "originaler" / "cache"
    ud = []
    for tid, f in json.loads((HER / "t4_facit.json").read_text(encoding="utf-8")).items():
        p = WORK / "dok_ægte" / f"{tid}.txt"
        if p.exists():
            ud.append({**f, "tid": tid, "fil": p, "gruppe": "T1", "blind": tid})
    g = cache / "P1c222e8f" / "screening.txt"
    if g.exists():
        ud.append({"tid": "G_01", "fil": g, "gruppe": "T1", "blind": "G_01", "sag": "P1c222e8f",
                   "dokumenttype": "screening_plan", "kategorier": ["omfattet_bilag_projektbegreb", "sagsoplysning_dokumentation"]})
    for i, sid in enumerate(AEGTE_STADFAESTET, 1):
        p = cache / sid / "dokument.txt"
        if p.exists():
            ud.append({"tid": f"S_{i:02d}", "fil": p, "gruppe": "T3", "blind": f"S_{i:02d}", "sag": sid,
                       "dokumenttype": "screening_plan", "kategorier": []})
    return ud


def _auc(pos, neg):
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg)) if pos and neg else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trin", choices=["prompts", "dommer", "score"])
    ap.add_argument("--navn", default="v2")
    ap.add_argument("--saet", default="dev", choices=["dev", "aegte", "rekon"])
    a = ap.parse_args()
    ud = WORK / f"{a.saet}_{a.navn}"
    (ud / "prompt").mkdir(parents=True, exist_ok=True)
    (ud / "svar").mkdir(exist_ok=True)
    (ud / "dommer_prompt").mkdir(exist_ok=True)
    (ud / "dommer_svar").mkdir(exist_ok=True)
    if a.saet == "dev":
        docs = [d for d in testdokumenter() if d["gruppe"] in ("T1", "T3")]
    elif a.saet == "aegte":
        docs = aegte_dokumenter()
    else:  # rekonstruktioner af de ægte stadfæstede (måler rekonstruktionsbias)
        docs = [d for d in aegte_dokumenter() if d["gruppe"] == "T3" and (WORK / "rekon_test" / "dok" / f"{d['tid']}.txt").exists()]
        docs = [{**d, "fil": WORK / "rekon_test" / "dok" / f"{d['tid']}.txt"} for d in docs]
    pk = punkt_kategorier()
    rows = []
    for d in docs:
        sp = ud / "svar" / f"{d['blind']}.json"
        svar = sp.read_text(encoding="utf-8") if a.trin in ("score", "dommer") and sp.exists() else None
        if a.trin in ("score", "dommer") and svar is None:
            continue
        r, rm, prompt, dok = kør(d, svar)
        if a.trin == "prompts":
            (ud / "prompt" / f"{d['blind']}.md").write_text(prompt, encoding="utf-8")
            continue
        udeluk = {d["sag"]} if d.get("sag") else set()
        if a.trin == "dommer":
            dp = llm_tjek.byg_dommer_prompt(dok, rm, udeluk)
            if dp:
                (ud / "dommer_prompt" / f"{d['blind']}.md").write_text(dp, encoding="utf-8")
            continue
        p_model = (rm.udfald or {}).get("sandsynlighed")
        ds = ud / "dommer_svar" / f"{d['blind']}.json"
        if ds.exists():
            rm = llm_tjek.anvend_dommer(rm, ds.read_text(encoding="utf-8"))
        kat = set(d.get("kategorier") or [])
        u = rm.udfald or {}
        rows.append({"tid": d["tid"], "gruppe": d["gruppe"], "type": d.get("dokumenttype"),
                     "p": u.get("sandsynlighed"), "p_model": p_model, "dommer": {k: u.get(k) for k in ("underkendt_sikre", "underkendt_usikre", "holdt", "punkter")},
                     "n_risiko": sum(s.niveau == "svaghed" for s in rm.svagheder),
                     "n_høj": sum(s.risiko == "høj" for s in rm.svagheder),
                     "n_opm": sum(s.niveau == "opmærksomhed" for s in rm.svagheder),
                     "ramt_risiko": ramt(rm, kat, pk, kun_svaghed=True) if kat else None,
                     "ramt_alle": ramt(rm, kat, pk) if kat else None})
    if a.trin in ("prompts", "dommer"):
        print(a.trin, "ok:", len(list((ud / ("prompt" if a.trin == "prompts" else "dommer_prompt")).glob("*.md"))))
        return
    (ud / "resultat.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    o = [r for r in rows if r["gruppe"] == "T1"]
    s = [r for r in rows if r["gruppe"] == "T3"]
    print(f"{len(o)} ophævede, {len(s)} stadfæstede")
    po, ps = [r["p"] for r in o if r["p"] is not None], [r["p"] for r in s if r["p"] is not None]
    pm = [r["p_model"] for r in o if r["p_model"] is not None]; sm_ = [r["p_model"] for r in s if r["p_model"] is not None]
    if pm and sm_:
        print(f"model-sandsynlighed (uden dommer): AUC {_auc(pm, sm_):.2f}")
    for r in rows:
        r["su"] = (r["dommer"].get("underkendt_sikre") or 0)
    print(f"dommer: sikre UNDERKENDT ≥1: ophævede {sum(r['su'] >= 1 for r in o)}/{len(o)}, stadfæstede {sum(r['su'] >= 1 for r in s)}/{len(s)}")
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

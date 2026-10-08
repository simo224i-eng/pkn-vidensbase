"""Kør Miljøjuristen på testsættene og beregn måltal.

    python ejnar/evaluation/miljoejurist/koer_test.py prompts   # regellag + modelprompts
    python ejnar/evaluation/miljoejurist/koer_test.py score [--runde N]

Testdokumenter (work/, gitignoreret):
  dok/R*.txt        rekonstruerede screeninger (T1 underkendte, T3 stadfæstede), id-kort i rekon_map.json
  dok_inj/T2_*.txt  stadfæstede screeninger med én indsat fejl (inj_facit.json)
  dok_ægte/*.txt    ægte oprindelige screeninger (T4)
Sagens egen afgørelse udelukkes altid fra praksissøgningen (udeluk={sag}).

Modellaget: work/prompts/<tid>.txt er præcis den prompt, webappen sender. En agent spiller
sprogmodellen og skriver sit JSON-svar til work/svar/<tid>.json.
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

HER = Path(__file__).resolve().parent
REPO = HER.parents[2]
sys.path.insert(0, str(REPO / "ejnar"))
from miljoejurist import dokument, llm_tjek, tjek  # noqa: E402

WORK = HER / "work"


def testdokumenter() -> list[dict]:
    facit = json.loads((HER / "facit.json").read_text(encoding="utf-8"))
    ud = []
    m = json.loads((WORK / "rekon_map.json").read_text()) if (WORK / "rekon_map.json").exists() else {}
    for tid, r in m.items():
        p = WORK / "dok" / f"{r}.txt"
        if p.exists():
            ud.append({"tid": tid, "fil": p, "blind": r, **facit[tid]})
    blind = json.loads((WORK / "blind_map.json").read_text()) if (WORK / "blind_map.json").exists() else {}
    inj = WORK / "inj_facit.json"
    if inj.exists():
        for tid, f in json.loads(inj.read_text(encoding="utf-8")).items():
            p = WORK / "dok_inj" / f"{tid}.txt"
            if p.exists():
                ud.append({"tid": tid, "fil": p, "gruppe": "T2", "blind": blind.get(tid, tid), **f})
    ægte = HER / "t4_facit.json"
    if ægte.exists():
        for tid, f in json.loads(ægte.read_text(encoding="utf-8")).items():
            p = WORK / "dok_ægte" / f"{tid}.txt"
            if p.exists():
                ud.append({"tid": tid, "fil": p, "gruppe": "T4", "blind": blind.get(tid, tid), **f})
    return ud


def punkt_kategorier() -> dict[str, set]:
    return {p["id"]: set(p["fejlkategorier"]) for p in tjek.tjekliste()}


def kør(d: dict, svar: str | None = None):
    dok = dokument.læs(d["fil"].name, d["fil"].read_bytes())
    udeluk = {d["sag"]} if d.get("sag") else set()
    r = tjek.tjek_regler(dok, dtype=d.get("dokumenttype"), udeluk=udeluk)
    prompt = llm_tjek.byg_prompt(dok, r, udeluk)
    rm = None
    if svar is not None:
        r2 = tjek.tjek_regler(dok, dtype=d.get("dokumenttype"), udeluk=udeluk)
        rm = tjek.renset(llm_tjek.supplér(r2, dok, None, udeluk=udeluk, svar=svar))
    return tjek.renset(r), rm, prompt, dok


def ramt(rapport, kategorier: set, pk: dict, top: int | None = None, kun_svaghed: bool = False) -> bool:
    sv = rapport.svagheder[:top] if top else rapport.svagheder
    if kun_svaghed:
        sv = [s for s in sv if getattr(s, "niveau", "svaghed") == "svaghed"]
    return any(pk.get(s.punkt, set()) & kategorier for s in sv)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trin", choices=["prompts", "score"])
    ap.add_argument("--runde", default="1")
    a = ap.parse_args()
    pk = punkt_kategorier()
    (WORK / "prompts").mkdir(exist_ok=True)
    sb, pb = ("sb", "pb") if a.runde == "1" else (f"sb{a.runde}", f"pb{a.runde}")
    (WORK / sb).mkdir(exist_ok=True)
    ud_dir = WORK / f"runde{a.runde}"
    ud_dir.mkdir(exist_ok=True)
    docs = testdokumenter()
    res = []
    for d in docs:
        sp = WORK / sb / f"{d['blind']}.json"
        svar = sp.read_text(encoding="utf-8") if (a.trin == "score" and sp.exists()) else None
        r, rm, prompt, dok = kør(d, svar)
        if a.trin == "prompts":
            (WORK / "prompts" / f"{d['tid']}.txt").write_text(prompt, encoding="utf-8")
            (WORK / pb).mkdir(exist_ok=True)
            (WORK / pb / f"{d['blind']}.txt").write_text(prompt, encoding="utf-8")
        kat = set(d.get("kategorier") or [])
        row = {"tid": d["tid"], "gruppe": d["gruppe"], "type": d.get("dokumenttype"), "kategorier": sorted(kat),
               "ord": dok.ord, "regler_n": len(r.svagheder),
               "regler_ramt": ramt(r, kat, pk) if kat else None,
               "regler_ramt_top3": ramt(r, kat, pk, 3) if kat else None,
               "regler_punkter": [s.punkt for s in r.svagheder],
               "regler_n_svag": sum(1 for s in r.svagheder if s.niveau == "svaghed"),
               "regler_ramt_svag": ramt(r, kat, pk, kun_svaghed=True) if kat else None}
        if rm:
            row.update({"model_n": len(rm.svagheder), "model_ramt": ramt(rm, kat, pk) if kat else None,
                        "model_ramt_top3": ramt(rm, kat, pk, 3) if kat else None,
                        "model_punkter": [s.punkt for s in rm.svagheder],
                        "model_fund": sum(1 for s in rm.svagheder if s.kilde_lag == "model"),
                        "model_n_svag": sum(1 for s in rm.svagheder if s.niveau == "svaghed"),
                        "model_ramt_svag": ramt(rm, kat, pk, kun_svaghed=True) if kat else None,
                        "model_n_høj": sum(1 for s in rm.svagheder if s.kilde_lag == "model" and s.vægt >= 3),
                        "note": rm.note})
            (ud_dir / f"{d['tid']}_model.md").write_text(tjek.som_markdown(rm), encoding="utf-8")
            (ud_dir / f"{d['tid']}_model.json").write_text(json.dumps(rm.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
        (ud_dir / f"{d['tid']}_regler.json").write_text(json.dumps(r.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
        res.append(row)
    (ud_dir / "resultat.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    if a.trin == "score":
        print(opsummer(res))


def opsummer(res: list[dict]) -> str:
    ud = []
    for g in ("T1", "T2", "T3", "T4"):
        rr = [r for r in res if r["gruppe"] == g]
        if not rr:
            continue
        n = len(rr)
        line = f"{g}: n={n}, svagheder/dok regler {sum(r['regler_n'] for r in rr) / n:.1f}"
        if any("model_n" in r for r in rr):
            m = [r for r in rr if "model_n" in r]
            line += (f", model {sum(r['model_n'] for r in m) / max(1, len(m)):.1f} (n={len(m)}),"
                     f" heraf svagheder {sum(r.get('model_n_svag', 0) for r in m) / max(1, len(m)):.1f},"
                     f" høj {sum(r.get('model_n_høj', 0) for r in m) / max(1, len(m)):.1f}")
        med_kat = [r for r in rr if r["kategorier"]]
        if med_kat:
            k = len(med_kat)
            line += (f" | ramt regler {sum(r['regler_ramt'] for r in med_kat)}/{k}"
                     f" (top3 {sum(r['regler_ramt_top3'] for r in med_kat)}/{k})")
            m = [r for r in med_kat if r.get("model_ramt") is not None]
            if m:
                line += (f", ramt model {sum(r['model_ramt'] for r in m)}/{len(m)}"
                         f" (top3 {sum(r['model_ramt_top3'] for r in m)}/{len(m)},"
                         f" blandt svagheder {sum(bool(r.get('model_ramt_svag')) for r in m)}/{len(m)})")
        ud.append(line)
    pr_kat = defaultdict(Counter)
    for r in res:
        for k in r["kategorier"]:
            pr_kat[k]["n"] += 1
            pr_kat[k]["regler"] += bool(r.get("regler_ramt"))
            pr_kat[k]["model"] += bool(r.get("model_ramt"))
    ud.append("Pr. kategori (n / ramt regler / ramt model): " +
              "; ".join(f"{k} {c['n']}/{c['regler']}/{c['model']}" for k, c in sorted(pr_kat.items())))
    return "\n".join(ud)


if __name__ == "__main__":
    main()

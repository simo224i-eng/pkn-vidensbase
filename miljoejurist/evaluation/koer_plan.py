"""Måler effekten af planens rammer (tjekpunkt A5): samme dokument med og uden lokalplanen.

    python miljoejurist/evaluation/koer_plan.py prompts   # work/plan/{med,uden}/prompt/P_xx.md + nævnets vurdering
    python miljoejurist/evaluation/koer_plan.py flet      # svar -> rapport/P_xx.md (til revision)
    python miljoejurist/evaluation/koer_plan.py score     # revision/P_xx.json -> tal

Sager: rekonstruerede plan-screeninger fra dev- og audit-sættet, hvor planens PDF findes på plandata.dk.
"""
import json
import random
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
sys.path.insert(0, str(REPO))
from miljoejurist import corpus, dokument, llm_tjek, planbestemmelser, tjek  # noqa: E402

UD = HER / "work" / "plan"
V2 = REPO / "analyser" / "miljoevurdering" / "v2"
OPHÆVET = ["P92636523", "Pba8eea03", "P7063f89e", "P1e849b3a", "P058e19c1", "Pa169bffc", "Pe0bc51bd",
           "P81ecf86e", "P15950b82", "Pe5072919"]
STADFÆSTET = ["P6e1145f8", "Pfbf94c1c", "P998018a5", "P4fef5402", "P4ffb925f", "P5367fcf3", "Ped1ca6f4",
              "P060bedb6", "Pd9aa1b2f", "P828afc0f"]


def sager() -> list[dict]:
    fac = json.loads((HER / "facit.json").read_text(encoding="utf-8"))
    rm = json.loads((HER / "work" / "rekon_map.json").read_text())
    dok = {fac[t]["sag"]: HER / "work" / "dok" / f"{r}.txt" for t, r in rm.items()}
    for a, f in json.loads((HER / "audit_facit.json").read_text(encoding="utf-8")).items():
        dok[f["sag"]] = HER / "work" / "audit" / "dok" / f"{a}.txt"
    fp = json.loads((REPO / "tools" / "originaler" / "fund_plandata.json").read_text(encoding="utf-8"))
    ud = []
    rng = random.Random(7)
    alle = [(s, "ophævet") for s in OPHÆVET] + [(s, "stadfæstet") for s in STADFÆSTET]
    rng.shuffle(alle)
    for i, (sid, g) in enumerate(alle, 1):
        h = sorted(fp.get(sid) or [], key=lambda x: str(x.get("status")) != "F")
        ud.append({"pid": f"P_{i:02d}", "sag": sid, "gruppe": g, "fil": dok[sid],
                   "planlink": h[0]["url"] if h else None,
                   "plantitel": f"{h[0]['plan']} {h[0].get('plannavn') or ''}".strip() if h else ""})
    return ud


def _plan(s):
    return planbestemmelser.hent(s["planlink"], s["plantitel"]) if s["planlink"] else None


def prompts():
    for d in ("med/prompt", "uden/prompt", "vurdering"):
        (UD / d).mkdir(parents=True, exist_ok=True)
    meta = {}
    for s in sager():
        d = dokument.læs(s["fil"].name, s["fil"].read_bytes())
        pl = _plan(s)
        r = tjek.tjek_regler(d, dtype="screening_plan", udeluk={s["sag"]})
        (UD / "uden" / "prompt" / f"{s['pid']}.md").write_text(llm_tjek.byg_prompt(d, r, {s["sag"]}), encoding="utf-8")
        if pl:
            (UD / "med" / "prompt" / f"{s['pid']}.md").write_text(llm_tjek.byg_prompt(d, r, {s["sag"]}, pl),
                                                                encoding="utf-8")
        t = (V2 / "sager" / f"{s['sag']}.txt").read_text(encoding="utf-8")
        udf = "OPHÆVET/UNDERKENDT (helt eller delvist)" if s["gruppe"] == "ophævet" else "STADFÆSTET"
        (UD / "vurdering" / f"{s['pid']}.txt").write_text(
            f"NÆVNETS UDFALD: {udf}\n\n" + corpus.nævnets_vurdering(t)[:60000], encoding="utf-8")
        meta[s["pid"]] = {"sag": s["sag"], "gruppe": s["gruppe"], "plan": bool(pl),
                          "plan_tegn": len(pl.tekst) if pl else 0, "uddrag_tegn": len(pl.uddrag) if pl else 0}
        print(s["pid"], s["sag"], s["gruppe"], "plan:", meta[s["pid"]]["plan_tegn"], meta[s["pid"]]["uddrag_tegn"])
    (UD / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")


def flet():
    meta = json.loads((UD / "meta.json").read_text(encoding="utf-8"))
    ss = {s["pid"]: s for s in sager()}
    for cond in ("med", "uden"):
        (UD / cond / "rapport").mkdir(exist_ok=True)
        for pid in meta:
            sp = UD / cond / "svar" / f"{pid}.json"
            if not sp.exists():
                continue
            s = ss[pid]
            d = dokument.læs(s["fil"].name, s["fil"].read_bytes())
            pl = _plan(s) if cond == "med" else None
            r = tjek.tjek_regler(d, dtype="screening_plan", udeluk={s["sag"]})
            r = llm_tjek.supplér(r, d, None, {s["sag"]}, svar=sp.read_text(encoding="utf-8"), plan=pl)
            (UD / cond / "rapport" / f"{pid}.json").write_text(json.dumps(r.to_json(), ensure_ascii=False),
                                                               encoding="utf-8")
            lin = [f"# {pid}: rapport ({len(r.svagheder)} fund)", ""]
            for i, sv in enumerate(r.svagheder, 1):
                niv = "risiko for ophævelse" if sv.niveau == "svaghed" else "opmærksomhedspunkt"
                planc = next((k.citat for k in sv.kilder if k.type == "plan"), None)
                lin += [f"{i}. [{niv}{', ' + sv.risiko if sv.risiko else ''}] {sv.punkt} {sv.titel}: {sv.svaghed}",
                        f"   Citat: «{sv.citat_dokument or '-'}»" + (f"  Planen: «{planc}»" if planc else ""),
                        f"   Hvorfor: {sv.hvorfor or '-'}", ""]
            (UD / cond / "rapport" / f"{pid}.md").write_text("\n".join(lin), encoding="utf-8")
    print("flettet")


def _auc(p, n):
    return sum((a > b) + .5 * (a == b) for a in p for b in n) / (len(p) * len(n)) if p and n else float("nan")


def score():
    meta = json.loads((UD / "meta.json").read_text(encoding="utf-8"))
    rows = []
    for pid, m in meta.items():
        row = {"pid": pid, **m}
        for cond in ("med", "uden"):
            rp, rv = UD / cond / "rapport" / f"{pid}.json", UD / cond / "revision" / f"{pid}.json"
            if not rp.exists():
                continue
            rap = json.loads(rp.read_text(encoding="utf-8"))
            rev = json.loads(rv.read_text(encoding="utf-8")) if rv.exists() else {}
            fund = rev.get("fund") or []
            row[cond] = {"fanget": rev.get("fanget"), "fanget_nr": rev.get("fanget_nr"),
                         "a5": sum(s["punkt"] == "A5" for s in rap["svagheder"]),
                         "planciteret": sum(any(k["type"] == "plan" for k in s["kilder"]) for s in rap["svagheder"]),
                         "rå": (rap.get("udfald") or {}).get("model_score"),
                         "risiko": sum(s["niveau"] == "svaghed" for s in rap["svagheder"]),
                         "forkerte": sum(f.get("vurdering") == "forkert" for f in fund if f.get("niveau") == "svaghed"),
                         "relevante": sum(f.get("vurdering") == "relevant" for f in fund),
                         "plan_ok": sum(f.get("plan_korrekt") is True for f in fund),
                         "plan_fejl": sum(f.get("plan_korrekt") is False for f in fund)}
        rows.append(row)
    (UD / "resultat.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    for cond in ("uden", "med"):
        o = [r[cond] for r in rows if r["gruppe"] == "ophævet" and cond in r]
        s = [r[cond] for r in rows if r["gruppe"] == "stadfæstet" and cond in r]
        if not o:
            continue
        print(f"{cond.upper()}: ophævede fanget ja {sum(x['fanget'] == 'ja' for x in o)}/{len(o)}, "
              f"delvist {sum(x['fanget'] == 'delvist' for x in o)}; A5-fund oph {sum(x['a5'] for x in o)}, "
              f"stad {sum(x['a5'] for x in s)}; plan citeret {sum(x['planciteret'] for x in o + s)}; "
              f"AUC rå {_auc([x['rå'] for x in o if x['rå'] is not None], [x['rå'] for x in s if x['rå'] is not None]):.2f}; "
              f"risikopunkter oph {sum(x['risiko'] for x in o) / len(o):.1f} stad {sum(x['risiko'] for x in s) / max(len(s), 1):.1f}; "
              f"forkerte risikopunkter i stadfæstede {sum(x['forkerte'] for x in s)}; "
              f"planpåstande korrekte/forkerte {sum(x['plan_ok'] for x in o + s)}/{sum(x['plan_fejl'] for x in o + s)}")


if __name__ == "__main__":
    {"prompts": prompts, "flet": flet, "score": score}[sys.argv[1]]()

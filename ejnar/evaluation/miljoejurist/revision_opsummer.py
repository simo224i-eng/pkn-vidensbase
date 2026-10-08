"""Saml revisionernes vurderinger (work/rev<N>/<blind>/revision.jsonl) til måltal.

    python ejnar/evaluation/miljoejurist/revision_opsummer.py --runde 1
"""
import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

HER = Path(__file__).resolve().parent
WORK = HER / "work"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runde", default="1")
    a = ap.parse_args()
    blind = {}
    for f in ("rekon_map.json", "blind_map.json"):
        p = WORK / f
        if p.exists():
            blind.update({v: k for k, v in json.loads(p.read_text()).items()})
    rev = WORK / f"rev{a.runde}"
    pr_gruppe = defaultdict(lambda: defaultdict(Counter))
    pr_punkt = defaultdict(Counter)
    dok_ramt, oversete = defaultdict(list), []
    for d in sorted(rev.iterdir()):
        p = d / "revision.jsonl"
        if not p.exists():
            continue
        tid = blind.get(d.name, d.name)
        g = tid[:2]
        rj = WORK / f"runde{a.runde}" / f"{tid}_model.json"
        sv = json.loads(rj.read_text(encoding="utf-8"))["svagheder"] if rj.exists() else []
        match = False
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("nr") == 0:
                if r.get("overset") and r["overset"].strip().lower() not in ("intet", "intet.", ""):
                    oversete.append((tid, r["overset"][:200]))
                continue
            i = int(r.get("nr", 0)) - 1
            s = sv[i] if 0 <= i < len(sv) else {}
            lag = s.get("kilde_lag", "?")
            niv = s.get("niveau", "svaghed")
            for nøgle in ("læsning", "relevant", "kilder_bærer", "matcher_facit"):
                pr_gruppe[g][f"{nøgle}"][r.get(nøgle)] += 1
                pr_gruppe[g][f"{nøgle}|{niv}"][r.get(nøgle)] += 1
                pr_gruppe[g][f"{nøgle}|{lag}"][r.get(nøgle)] += 1
            pr_punkt[r.get("punkt")][r.get("relevant")] += 1
            if r.get("matcher_facit") in ("ja", "delvist") and niv == "svaghed":
                match = True
        dok_ramt[g].append(match)
    ud = [f"# Revision, runde {a.runde}", ""]
    for g in sorted(pr_gruppe):
        c = pr_gruppe[g]
        n = sum(c["relevant"].values())

        def pct(nøgle, v=("ja",)):
            t = sum(c[nøgle].values())
            return f"{100 * sum(c[nøgle][x] for x in v) / t:.0f} %" if t else "–"
        ud.append(f"## {g}: {len(dok_ramt[g])} dokumenter, {n} reviderede fund")
        ud.append(f"- Læst korrekt: {pct('læsning', ('korrekt',))}")
        ud.append(f"- Relevant (ja / ja+delvist): {pct('relevant')} / {pct('relevant', ('ja', 'delvist'))}; "
                  f"blandt 'svagheder' {pct('relevant|svaghed')} / {pct('relevant|svaghed', ('ja', 'delvist'))}; "
                  f"blandt 'opmærksomhed' {pct('relevant|opmærksomhed')} / {pct('relevant|opmærksomhed', ('ja', 'delvist'))}")
        ud.append(f"- Kilderne bærer (ja / ja+delvist): {pct('kilder_bærer')} / {pct('kilder_bærer', ('ja', 'delvist'))}")
        ud.append(f"- Relevant fra modellaget: {pct('relevant|model', ('ja', 'delvist'))}; fra regellaget: "
                  f"{pct('relevant|regel', ('ja', 'delvist'))}")
        if g in ("T1", "T2", "T4"):
            ud.append(f"- Dokumenter, hvor en 'svaghed' matcher nævnets begrundelse/den indsatte fejl: "
                      f"{sum(dok_ramt[g])}/{len(dok_ramt[g])}")
        ud.append("")
    ud.append("## Relevans pr. tjeklistepunkt (ja/delvist/nej)")
    ud += [f"- {p}: {c['ja']}/{c['delvist']}/{c['nej']}" for p, c in sorted(pr_punkt.items(), key=lambda x: str(x[0]))]
    ud.append("\n## Oversete forhold (revisorernes noter)")
    ud += [f"- {t}: {o}" for t, o in oversete]
    tekst = "\n".join(ud)
    (HER / f"revision_runde{a.runde}.md").write_text(tekst, encoding="utf-8")
    print(tekst[:4000])


if __name__ == "__main__":
    main()

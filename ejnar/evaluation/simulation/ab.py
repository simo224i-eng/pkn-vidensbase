"""Blind A/B-sammenligning af to simulationskørsler.

    python -m ejnar.evaluation.simulation.ab pack --base runs/r1 --new runs/r2 --out runs/ab-r1-r2
    python -m ejnar.evaluation.simulation.ab score --out runs/ab-r1-r2

``pack`` lægger for hver sag spørgsmålet og de to svar i tilfældig (seedet)
rækkefølge som A/B i ``<out>/<ID>.md``. Nøglen gemmes i ``<out>/.key.json``, som
bedømmerne ikke skal læse. ``score`` afkoder bedømmernes ``verdicts.json``
(``[{"id": "S01", "winner": "A"|"B"|"lige", ...}]``) til en samlet opgørelse.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def pack(base: Path, new: Path, out: Path, seed: int = 20260929) -> None:
    rng = random.Random(seed)
    out.mkdir(parents=True, exist_ok=True)
    key = {}
    for case_file in sorted(new.glob("*.case.json")):
        case = json.loads(case_file.read_text(encoding="utf-8"))
        cid = case["id"]
        answers = {
            "base": (base / f"{cid}.answer.md").read_text(encoding="utf-8"),
            "new": (new / f"{cid}.answer.md").read_text(encoding="utf-8"),
        }
        order = ["base", "new"]
        rng.shuffle(order)
        key[cid] = {"A": order[0], "B": order[1]}
        (out / f"{cid}.md").write_text(
            f"# {cid} · {case.get('persona', '')} · {case.get('type', '')}\n\n"
            f"## Spørgsmål\n\n{case['question']}\n\n"
            f"## Hvad et godt svar skal indeholde (brugerens forventning)\n\n{case.get('what_good_looks_like', '')}\n\n"
            f"## Kildemateriale\n\nSe `{new.name}/{cid}.prompt.txt` (afsnittet KENDELSER).\n\n"
            f"---\n\n## Svar A\n\n{answers[order[0]]}\n\n---\n\n## Svar B\n\n{answers[order[1]]}\n",
            encoding="utf-8",
        )
    (out / ".key.json").write_text(json.dumps(key, indent=2), encoding="utf-8")
    print(f"{len(key)} sager pakket i {out}")


def score(out: Path) -> dict:
    key = json.loads((out / ".key.json").read_text(encoding="utf-8"))
    verdicts = json.loads((out / "verdicts.json").read_text(encoding="utf-8"))
    tally = {"new": 0, "base": 0, "lige": 0}
    rows = []
    for v in verdicts:
        w = v.get("winner", "lige")
        who = key[v["id"]].get(w, "lige") if w in ("A", "B") else "lige"
        tally[who] += 1
        rows.append({"id": v["id"], "winner": who, "reason": v.get("reason", "")})
    result = {"tally": tally, "cases": rows}
    (out / "ab-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack")
    p.add_argument("--base", required=True)
    p.add_argument("--new", required=True)
    p.add_argument("--out", required=True)
    s = sub.add_parser("score")
    s.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.cmd == "pack":
        pack(Path(args.base), Path(args.new), Path(args.out))
    else:
        score(Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Udsagnsrevision: holder hvert udsagn om en kendelse, når man læser kendelsen?

Et praksisværktøj er kun så godt som dets gengivelse af praksis. Karakterer fra en
bedømmer er subjektive; her efterprøves i stedet hvert enkelt udsagn i svaret mod
den kendelse, det henviser til:

1. ``pack``   For hvert besvaret spørgsmål skrives ``audit/<ID>.md`` med svaret og –
              for hver citeret kilde – kendelsens faktum og nævnets begrundelse.
2.            En revisor-agent læser filerne og skriver ``audit/claims.json``::

                  [{"id": "P01", "claims": [{"claim": "...", "sources": [3],
                    "verdict": "understøttet" | "delvist" | "ikke_understøttet" | "modsagt",
                    "note": "..."}]}]

3. ``score``  Andel understøttede udsagn, modsagte udsagn og udfaldskonflikter.

    python -m ejnar.evaluation.simulation.claim_audit pack  --run runs/p1
    python -m ejnar.evaluation.simulation.claim_audit score --run runs/p1
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EJNAR = HERE.parents[1]
if str(EJNAR) not in sys.path:
    sys.path.insert(0, str(EJNAR))

VERDICTS = ["understøttet", "delvist", "ikke_understøttet", "modsagt"]


def _source_text(tekst: str, facts_chars: int = 3000, core_chars: int = 9000) -> str:
    import shared

    tekst = re.sub(r"[ \t]+", " ", str(tekst or ""))
    kerne = shared.udtræk_kerneafsnit(tekst, max_tegn=core_chars)
    start = tekst[:facts_chars]
    if kerne and kerne[:200] in start:
        return start
    return f"{start}\n\n[…]\n\nNÆVNETS BEGRUNDELSE OG RESULTAT (uddrag):\n{kerne}"


def pack(run: Path) -> None:
    import engine

    df = engine.load_data()
    texts = dict(zip(df["Id"], df["Tekst"]))
    audit = run / "audit"
    audit.mkdir(exist_ok=True)
    n_cases = 0
    for case_file in sorted(run.glob("*.case.json")):
        case = json.loads(case_file.read_text(encoding="utf-8"))
        answer_path = run / case["answer_file"]
        if not answer_path.exists():
            continue
        answer = answer_path.read_text(encoding="utf-8")
        cited = engine.citerede_kilder(answer, len(case["sources"]))
        parts = [f"# {case['id']}\n\n## Spørgsmål\n\n{case['question']}\n\n## Svar\n\n{answer}\n\n"
                 f"## Citerede kendelser ({len(cited)})\n"]
        for s in case["sources"]:
            if s["n"] not in cited:
                continue
            parts.append(
                f"\n### [Kilde {s['n']}] AKF {s.get('case_number', '')} · {s.get('date', '')} · "
                f"udfald for klager: {s.get('outcome', '')}\n\n{s.get('title', '')}\n\n"
                f"{_source_text(texts.get(s['id'], ''))}\n")
        (audit / f"{case['id']}.md").write_text("".join(parts), encoding="utf-8")
        n_cases += 1
    print(f"{n_cases} svar pakket i {audit}")


def score(run: Path) -> dict:
    claims = json.loads((run / "audit" / "claims.json").read_text(encoding="utf-8"))
    total = Counter()
    rows = []
    for item in claims:
        c = Counter(cl.get("verdict", "ikke_understøttet") for cl in item.get("claims", []))
        total.update(c)
        checks_path = run / f"{item['id']}.checks.json"
        checks = json.loads(checks_path.read_text(encoding="utf-8")) if checks_path.exists() else {}
        rows.append({"id": item["id"], "claims": sum(c.values()), **{v: c.get(v, 0) for v in VERDICTS},
                     "suspect_quotes": len(checks.get("suspect_quotes", [])),
                     "outcome_conflicts": len(checks.get("outcome_conflicts", []))})
    n = sum(total.values()) or 1
    result = {
        "answers": len(rows),
        "claims": sum(total.values()),
        "supported_pct": round(100 * total["understøttet"] / n, 1),
        "supported_or_partly_pct": round(100 * (total["understøttet"] + total["delvist"]) / n, 1),
        "unsupported": total["ikke_understøttet"],
        "contradicted": total["modsagt"],
        "suspect_quotes": sum(r["suspect_quotes"] for r in rows),
        "outcome_conflicts": sum(r["outcome_conflicts"] for r in rows),
        "rows": rows,
    }
    (run / "audit" / "audit-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    for r in rows:
        print(f"  {r['id']}: {r['claims']} udsagn · understøttet {r['understøttet']} · delvist {r['delvist']} · "
              f"ikke understøttet {r['ikke_understøttet']} · modsagt {r['modsagt']}")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["pack", "score"])
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    {"pack": pack, "score": score}[args.cmd](Path(args.run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

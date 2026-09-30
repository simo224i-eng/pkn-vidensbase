"""Udsagnsrevision: holder hvert udsagn om en kendelse, når man læser kendelsen?

Et praksisværktøj er kun så godt som dets gengivelse af praksis. Karakterer fra en
bedømmer er subjektive; her efterprøves i stedet hvert enkelt udsagn i svaret mod
den kendelse, det henviser til:

1. ``pack``   For hvert besvaret spørgsmål skrives ``audit/<ID>.md`` med svaret og –
              for hver citeret kilde – de uddrag, modellen fik, sagens begyndelse og
              nævnets egen vurdering (efter nævnets gengivelse af parterne).
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
_ALIAS = {"delvis": "delvist", "ikke understøttet": "ikke_understøttet", "ikke_understottet": "ikke_understøttet"}


def _verdict(value: str) -> str:
    v = str(value or "").strip().lower()
    v = _ALIAS.get(v, v)
    return v if v in VERDICTS else "ikke_understøttet"


def _source_text(tekst: str, facts_chars: int = 2500, core_chars: int = 10000) -> str:
    """Sagens begyndelse + nævnets egen vurdering (efter gengivelsen af parterne)."""
    import board_reasoning

    rå = str(tekst or "")
    delt = board_reasoning.del_kendelse(rå)
    kerne = rå[delt[1]:] if delt else rå[-core_chars:]
    rens = lambda t: re.sub(r"[ \t]+", " ", t).strip()
    return (f"SAGENS BEGYNDELSE:\n{rens(rå[:facts_chars])}\n\n[…]\n\n"
            f"NÆVNETS VURDERING OG RESULTAT:\n{rens(kerne[:core_chars])}")


_BLOK_START = re.compile(r"^\[(?:AFGØRELSESKERNE )?Kilde (\d+)\]", re.M)


def _prompt_uddrag(prompt: str) -> dict[int, list[str]]:
    """Uddragene pr. kilde, præcis som modellen så dem i promptens KENDELSER-afsnit."""
    krop = prompt.split("KENDELSER:", 1)[-1].split("\nSPØRGSMÅL:", 1)[0]
    starts = list(_BLOK_START.finditer(krop))
    out: dict[int, list[str]] = {}
    for i, m in enumerate(starts):
        slut = starts[i + 1].start() if i + 1 < len(starts) else len(krop)
        blok = krop[m.start():slut]
        blok = re.split(r"\n(?=[A-ZÆØÅ ]{8,}:?\n)", blok)[0].strip()   # stop ved næste afsnitsoverskrift
        out.setdefault(int(m.group(1)), []).append(blok)
    return out


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
        prompt_path = run / case.get("prompt_file", f"{case['id']}.prompt.txt")
        uddrag = _prompt_uddrag(prompt_path.read_text(encoding="utf-8")) if prompt_path.exists() else {}
        parts = [f"# {case['id']}\n\n## Spørgsmål\n\n{case['question']}\n\n## Svar\n\n{answer}\n\n"
                 f"## Citerede kendelser ({len(cited)})\n"]
        for s in case["sources"]:
            if s["n"] not in cited:
                continue
            parts.append(
                f"\n### [Kilde {s['n']}] AKF {s.get('case_number', '')} · {s.get('date', '')} · "
                f"udfald for klager: {s.get('outcome', '')}\n\n{s.get('title', '')}\n\n"
                "UDDRAG SOM MODELLEN FIK:\n" + "\n\n".join(uddrag.get(s["n"], ["(ingen)"])) + "\n\n"
                f"{_source_text(texts.get(s['id'], ''))}\n")
        (audit / f"{case['id']}.md").write_text("".join(parts), encoding="utf-8")
        n_cases += 1
    print(f"{n_cases} svar pakket i {audit}")


def score(run: Path) -> dict:
    # claims.json eller flere revisorfiler (claims-a.json, claims-b.json, …)
    claims = [item for path in sorted((run / "audit").glob("claims*.json"))
              for item in json.loads(path.read_text(encoding="utf-8"))]
    total = Counter()
    rows = []
    for item in claims:
        c = Counter(_verdict(cl.get("verdict")) for cl in item.get("claims", []))
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

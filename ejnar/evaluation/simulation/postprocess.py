"""Automatisk efterbehandling af simulerede svar + samlet rapport.

Del 3 af praksissimulationen (se README.md). For hvert svar køres de samme
kontroller som i appen (citatkontrol mod kilderne, hvilke kilder der er citeret,
henvisninger til ikke-eksisterende kilder), og anmeldernes JSON-bedømmelser
samles i en markdown-rapport.

    python -m ejnar.evaluation.simulation.postprocess --run ejnar/evaluation/simulation/runs/demo
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EJNAR = HERE.parents[1]
if str(EJNAR) not in sys.path:
    sys.path.insert(0, str(EJNAR))

PROFESSOR_KEYS = ["retrieval", "korrekthed", "forankring", "praksissyntese", "konkrethed"]
HANDLER_KEYS = ["anvendelighed", "tidsbesparelse", "tillid"]


def auto_checks(answer: str, sources: list[dict], texts_by_n: dict[int, str] | None = None,
                question: str = "") -> dict:
    import engine

    refs = [int(n) for g in re.findall(r"\[Kilde[r]?\s+([^\]]+)\]", answer, flags=re.I)
            for n in re.findall(r"\d+", g)]
    cited = engine.citerede_kilder(answer, len(sources))
    suspect = []
    conflicts = engine.udfaldskonflikter(answer, [{"Udfald": s.get("outcome", "")} for s in sources])
    if texts_by_n:
        docs = [{"Tekst": texts_by_n.get(s["n"], ""), "Titel": s.get("title", "")} for s in sources]
        suspect = engine.mistænkelige_citater(answer, docs, question)
    return {
        "chars": len(answer),
        "citations_total": len(refs),
        "cited_sources": cited,
        "invalid_source_refs": sorted({n for n in refs if n < 1 or n > len(sources)}),
        "suspect_quotes": suspect,
        "outcome_conflicts": conflicts,
        "cites_case_numbers_directly": bool(re.search(r"\b(?:sag|j\.?\s?nr)\.?\s*\d{4,6}", answer, re.I)),
    }


_TEXTS_BY_ID: dict[str, str] = {}


def _load_texts(sources: list[dict]) -> dict[int, str]:
    if not _TEXTS_BY_ID:
        import engine

        df = engine.load_data()
        _TEXTS_BY_ID.update(zip(df["Id"], df["Tekst"]))
    return {s["n"]: _TEXTS_BY_ID.get(s["id"], "") for s in sources}


def _mean(values):
    values = [v for v in values if isinstance(v, (int, float))]
    return round(statistics.mean(values), 2) if values else None


def report(run: Path) -> str:
    cases = sorted(run.glob("*.case.json"))
    rows, reviews = [], {}
    review_file = run / "reviews.json"
    if review_file.exists():
        reviews = {r["id"]: r for r in json.loads(review_file.read_text(encoding="utf-8"))}
    for path in cases:
        case = json.loads(path.read_text(encoding="utf-8"))
        answer_path = run / case["answer_file"]
        answer = answer_path.read_text(encoding="utf-8") if answer_path.exists() else ""
        texts = _load_texts(case["sources"])
        checks = auto_checks(answer, case["sources"], texts, case["question"]) if answer else {}
        (run / f"{case['id']}.checks.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2), encoding="utf-8")
        rows.append((case, checks, reviews.get(case["id"])))

    lines = ["# Ejnar – praksissimulation", "", f"Kørsel: `{run.name}` · {len(rows)} sager", ""]
    prof = {k: _mean([r[2]["professor"].get(k) for r in rows if r[2]]) for k in PROFESSOR_KEYS}
    hand = {k: _mean([r[2]["sagsbehandler"].get(k) for r in rows if r[2]]) for k in HANDLER_KEYS}
    lines += ["## Samlet score (1–5)", "",
              "| Juraprofessor | | Skadesbehandler | |", "|---|---|---|---|"]
    for i in range(max(len(PROFESSOR_KEYS), len(HANDLER_KEYS))):
        pk = PROFESSOR_KEYS[i] if i < len(PROFESSOR_KEYS) else ""
        hk = HANDLER_KEYS[i] if i < len(HANDLER_KEYS) else ""
        lines.append(f"| {pk} | {prof.get(pk, '') if pk else ''} | {hk} | {hand.get(hk, '') if hk else ''} |")
    lines += ["", "## Automatiske kontroller", "",
              "| Sag | Type | Kilder | Citeret | Henvisninger | Ugyldige | Mistænkelige citater | Udfaldskonflikter |",
              "|---|---|---|---|---|---|---|---|"]
    for case, checks, _ in rows:
        lines.append(
            f"| {case['id']} | {case.get('type', '')} | {len(case['sources'])} | {len(checks.get('cited_sources', []))} | "
            f"{checks.get('citations_total', 0)} | {checks.get('invalid_source_refs', [])} | {len(checks.get('suspect_quotes', []))} | {len(checks.get('outcome_conflicts', []))} |")
    lines += ["", "## Pr. sag", ""]
    for case, checks, rev in rows:
        lines += [f"### {case['id']} · {case.get('persona', '')} · {case.get('type', '')}", "",
                  f"> {case['question']}", ""]
        if rev:
            p, h = rev["professor"], rev["sagsbehandler"]
            lines.append("Professor: " + ", ".join(f"{k} {p.get(k)}" for k in PROFESSOR_KEYS)
                         + " · Skadesbehandler: " + ", ".join(f"{k} {h.get(k)}" for k in HANDLER_KEYS))
            for label, key in (("Styrker", "styrker"), ("Fejl", "fejl"), ("Forbedringer", "forbedringer")):
                if p.get(key):
                    lines.append(f"- **{label}:** " + "; ".join(p[key]))
            if h.get("kommentar"):
                lines.append(f"- **Skadesbehandler:** {h['kommentar']}")
            if rev.get("vigtigste_forbedring"):
                lines.append(f"- **Vigtigste forbedring:** {rev['vigtigste_forbedring']}")
        lines.append("")
    text = "\n".join(lines)
    (run / "REPORT.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", required=True)
    args = ap.parse_args()
    print(report(Path(args.run)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

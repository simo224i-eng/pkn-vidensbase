"""Compare cross-host retrieval stage traces and locate first divergent layer."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from .run_pipeline_stage_trace import STAGE_ORDER


def _load(path: Path) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            rows[str(row["question_id"])] = row
    return rows


def compare_stage_traces(runs: dict[str, dict[str, dict]]) -> dict:
    names = list(runs)
    all_questions = sorted(set().union(*(set(rows) for rows in runs.values())))
    details = []
    first_counts: Counter[str] = Counter()

    for question_id in all_questions:
        missing = [name for name in names if question_id not in runs[name]]
        if missing:
            details.append({"question_id": question_id, "first_divergent_stage": "missing_question", "missing_runs": missing})
            first_counts["missing_question"] += 1
            continue

        first = None
        stage_matches: dict[str, bool] = {}
        for stage in STAGE_ORDER:
            values = [tuple(runs[name][question_id].get("stages", {}).get(stage, [])) for name in names]
            same = all(value == values[0] for value in values[1:])
            stage_matches[stage] = same
            if first is None and not same:
                first = stage

        if first is not None:
            first_counts[first] += 1
            details.append(
                {
                    "question_id": question_id,
                    "query": runs[names[0]][question_id].get("query", ""),
                    "first_divergent_stage": first,
                    "stage_matches": stage_matches,
                    "stage_results": {
                        stage: {name: runs[name][question_id].get("stages", {}).get(stage, []) for name in names}
                        for stage in STAGE_ORDER
                        if not stage_matches.get(stage, True)
                    },
                }
            )

    return {
        "schema_version": 1,
        "exact_reproducibility": not details,
        "runs": names,
        "questions": len(all_questions),
        "affected_questions": len(details),
        "first_divergent_stage_counts": dict(first_counts),
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare Ejnar stage traces across hosts")
    parser.add_argument("--run", action="append", required=True, help="name=path")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    runs: dict[str, dict[str, dict]] = {}
    for item in args.run:
        name, raw_path = item.split("=", 1)
        runs[name] = _load(Path(raw_path))

    report = compare_stage_traces(runs)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "Stage reproducibility: "
        f"exact={report['exact_reproducibility']} "
        f"affected={report['affected_questions']} "
        f"first={report['first_divergent_stage_counts']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

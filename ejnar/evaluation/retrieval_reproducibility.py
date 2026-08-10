"""Compare independent Ejnar retrieval runs for exact reproducibility.

Human-reviewed audit pools and regression metrics must not drift because of Python hash
seed, unstable tie ordering, or process-local implementation details. This comparator
ignores timing metadata and compares the ordered decision identities returned for every
question.

It is diagnostic infrastructure only; it does not change retrieval or legal answers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}: line {line_number} is not a JSON object")
            rows.append(payload)
    return rows


def decision_identity(result: dict[str, Any]) -> str:
    case_number = " ".join(str(result.get("Sagsnummer") or "").split()).casefold()
    if case_number:
        return f"case:{case_number}"
    link = " ".join(str(result.get("Link") or "").split()).casefold()
    if link:
        return f"link:{link}"
    title = " ".join(str(result.get("Titel") or "").split()).casefold()
    date = " ".join(str(result.get("Dato") or "").split()).casefold()
    return f"fallback:{title}|{date}"


def canonical_run(rows: Iterable[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    by_question: dict[str, tuple[str, ...]] = {}
    for position, row in enumerate(rows, start=1):
        question_id = str(row.get("question_id") or "").strip()
        if not question_id:
            raise ValueError(f"result row {position}: missing question_id")
        if question_id in by_question:
            raise ValueError(f"duplicate question_id: {question_id}")
        results = tuple(decision_identity(result) for result in (row.get("results") or []))
        if len(results) != len(set(results)):
            raise ValueError(f"{question_id}: duplicate decision identity in result list")
        by_question[question_id] = results
    return by_question


def run_digest(canonical: dict[str, tuple[str, ...]]) -> str:
    payload = [
        {"question_id": question_id, "results": list(canonical[question_id])}
        for question_id in sorted(canonical)
    ]
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def compare_runs(named_runs: list[tuple[str, list[dict[str, Any]]]]) -> dict[str, Any]:
    if len(named_runs) < 2:
        raise ValueError("at least two retrieval runs are required")

    canonical = {name: canonical_run(rows) for name, rows in named_runs}
    baseline_name = named_runs[0][0]
    baseline = canonical[baseline_name]
    baseline_questions = set(baseline)

    comparisons: list[dict[str, Any]] = []
    total_order_mismatches = 0
    total_set_mismatches = 0
    affected_questions: set[str] = set()

    for name, _ in named_runs[1:]:
        other = canonical[name]
        missing_questions = sorted(baseline_questions - set(other))
        extra_questions = sorted(set(other) - baseline_questions)
        question_rows: list[dict[str, Any]] = []

        for question_id in sorted(baseline_questions & set(other)):
            expected = baseline[question_id]
            actual = other[question_id]
            order_matches = expected == actual
            set_matches = set(expected) == set(actual)
            if order_matches:
                continue
            affected_questions.add(question_id)
            total_order_mismatches += 1
            if not set_matches:
                total_set_mismatches += 1
            first_difference = next(
                (
                    rank
                    for rank, (left, right) in enumerate(zip(expected, actual), start=1)
                    if left != right
                ),
                min(len(expected), len(actual)) + 1,
            )
            question_rows.append(
                {
                    "question_id": question_id,
                    "ordered_match": False,
                    "set_match": set_matches,
                    "first_different_rank": first_difference,
                    "baseline_only": sorted(set(expected) - set(actual)),
                    "other_only": sorted(set(actual) - set(expected)),
                    "baseline_results": list(expected),
                    "other_results": list(actual),
                }
            )

        if missing_questions or extra_questions:
            affected_questions.update(missing_questions)
            affected_questions.update(extra_questions)

        comparisons.append(
            {
                "baseline": baseline_name,
                "other": name,
                "baseline_sha256": run_digest(baseline),
                "other_sha256": run_digest(other),
                "missing_questions": missing_questions,
                "extra_questions": extra_questions,
                "ordered_result_mismatches": len(question_rows),
                "set_mismatches": sum(not row["set_match"] for row in question_rows),
                "questions": question_rows,
            }
        )

    exact = (
        not affected_questions
        and all(
            not comparison["missing_questions"]
            and not comparison["extra_questions"]
            for comparison in comparisons
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "ejnar_retrieval_reproducibility_v1",
        "exact_reproducibility": exact,
        "runs": [
            {
                "name": name,
                "questions": len(canonical[name]),
                "sha256": run_digest(canonical[name]),
            }
            for name, _ in named_runs
        ],
        "summary": {
            "runs": len(named_runs),
            "questions": len(baseline),
            "affected_unique_questions": len(affected_questions),
            "ordered_mismatches_across_comparisons": total_order_mismatches,
            "set_mismatches_across_comparisons": total_set_mismatches,
        },
        "comparisons": comparisons,
    }


def write_report(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare independent Ejnar retrieval runs")
    parser.add_argument("--run", action="append", required=True, metavar="NAME=PATH")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-differences", action="store_true")
    args = parser.parse_args(argv)

    named_runs: list[tuple[str, list[dict[str, Any]]]] = []
    for value in args.run:
        if "=" not in value:
            raise ValueError(f"--run must be NAME=PATH, got {value!r}")
        name, raw_path = value.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("run name cannot be empty")
        named_runs.append((name, read_jsonl(Path(raw_path))))

    report = compare_runs(named_runs)
    write_report(args.output, report)
    summary = report["summary"]
    print(
        "Retrieval reproducibility: "
        f"exact={report['exact_reproducibility']} "
        f"affected_questions={summary['affected_unique_questions']} "
        f"order_mismatches={summary['ordered_mismatches_across_comparisons']} "
        f"set_mismatches={summary['set_mismatches_across_comparisons']}"
    )
    return 0 if (report["exact_reproducibility"] or args.allow_differences) else 1


if __name__ == "__main__":
    raise SystemExit(main())

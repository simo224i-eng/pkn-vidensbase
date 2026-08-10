"""Evaluate Ejnar practice-synthesis evidence use against frozen human labels.

This module is intentionally downstream of human adjudication. It does not infer which
Ankenævnet decisions are direct practice. Instead, it consumes labels frozen by
``grounding_review.py`` and evaluates a system's structured evidence-role predictions.

The benchmark measures source-role correctness and whether distributions/generalisation
claims are structurally grounded in decisions labelled ``direct_practice``. It does NOT
claim to determine whether multiple direct decisions are substantively consistent enough
to constitute settled/fast practice; that remains a legal human judgment.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
ROLES = ("direct_practice", "indirect_support", "not_useful", "uncertain")
BENCHMARKABLE_ROLES = ("direct_practice", "indirect_support", "not_useful")


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_human_labels(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Validate and index frozen grounding human labels by audit_id."""
    indexed: dict[str, dict[str, Any]] = {}
    for position, row in enumerate(rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        question_id = _normalise(row.get("question_id"))
        role = _normalise(row.get("label")).casefold()
        if not audit_id:
            raise ValueError(f"human label row {position}: missing audit_id")
        if audit_id in indexed:
            raise ValueError(f"duplicate human audit_id: {audit_id}")
        if not question_id:
            raise ValueError(f"{audit_id}: missing question_id")
        if role not in ROLES:
            raise ValueError(f"{audit_id}: invalid human role {role!r}")
        relevance = row.get("benchmark_relevance")
        expected_relevance = {
            "direct_practice": 2,
            "indirect_support": 1,
            "not_useful": 0,
            "uncertain": None,
        }[role]
        if relevance != expected_relevance:
            raise ValueError(
                f"{audit_id}: relevance {relevance!r} does not match role {role!r}"
            )
        indexed[audit_id] = {
            "audit_id": audit_id,
            "question_id": question_id,
            "query": _normalise(row.get("query")),
            "case_number": _normalise(row.get("case_number")),
            "link": _normalise(row.get("link")),
            "label": role,
            "benchmark_relevance": relevance,
        }
    return indexed


def prediction_template(source_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a label-free structured prediction template from a blind review source.

    ``source_rows`` should be the blind pool, not the frozen human-label file. The output
    deliberately contains no human role, heuristic priority or retrieval rank.
    """
    grouped: dict[str, dict[str, Any]] = {}
    seen_audit_ids: set[str] = set()
    for position, row in enumerate(source_rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        question_id = _normalise(row.get("question_id"))
        query = _normalise(row.get("query"))
        if not audit_id or not question_id:
            raise ValueError(f"source row {position}: missing audit_id/question_id")
        if audit_id in seen_audit_ids:
            raise ValueError(f"duplicate source audit_id: {audit_id}")
        seen_audit_ids.add(audit_id)
        item = grouped.setdefault(
            question_id,
            {
                "question_id": question_id,
                "query": query,
                "source_roles": {},
                "distribution_denominator_audit_ids": [],
                "states_practice_line": False,
                "states_fixed_practice": False,
            },
        )
        if item["query"] != query:
            raise ValueError(f"{question_id}: source rows disagree on query text")
        item["source_roles"][audit_id] = ""
    return [grouped[key] for key in sorted(grouped)]


def validate_predictions(
    predictions: list[dict[str, Any]],
    labels_by_id: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Validate prediction shape and prevent cross-question source leakage."""
    by_question: dict[str, dict[str, Any]] = {}
    known_by_question: dict[str, set[str]] = defaultdict(set)
    for audit_id, label in labels_by_id.items():
        known_by_question[label["question_id"]].add(audit_id)

    for position, prediction in enumerate(predictions, start=1):
        question_id = _normalise(prediction.get("question_id"))
        if not question_id:
            raise ValueError(f"prediction {position}: missing question_id")
        if question_id in by_question:
            raise ValueError(f"duplicate prediction question_id: {question_id}")
        if question_id not in known_by_question:
            raise ValueError(f"prediction references unknown question_id: {question_id}")

        roles_raw = prediction.get("source_roles") or {}
        if not isinstance(roles_raw, dict):
            raise ValueError(f"{question_id}: source_roles must be an object")
        source_roles: dict[str, str] = {}
        for audit_id_raw, role_raw in roles_raw.items():
            audit_id = _normalise(audit_id_raw)
            role = _normalise(role_raw).casefold()
            if audit_id not in known_by_question[question_id]:
                raise ValueError(
                    f"{question_id}: audit_id {audit_id!r} does not belong to this question"
                )
            if role not in ROLES:
                raise ValueError(f"{question_id}/{audit_id}: invalid predicted role {role!r}")
            source_roles[audit_id] = role

        denominator_raw = prediction.get("distribution_denominator_audit_ids") or []
        if not isinstance(denominator_raw, list):
            raise ValueError(f"{question_id}: distribution denominator must be a list")
        denominator: list[str] = []
        seen_denominator: set[str] = set()
        for audit_id_raw in denominator_raw:
            audit_id = _normalise(audit_id_raw)
            if audit_id not in known_by_question[question_id]:
                raise ValueError(
                    f"{question_id}: denominator audit_id {audit_id!r} belongs elsewhere"
                )
            if audit_id not in seen_denominator:
                seen_denominator.add(audit_id)
                denominator.append(audit_id)

        by_question[question_id] = {
            "question_id": question_id,
            "query": _normalise(prediction.get("query")),
            "source_roles": source_roles,
            "distribution_denominator_audit_ids": denominator,
            "states_practice_line": bool(prediction.get("states_practice_line", False)),
            "states_fixed_practice": bool(prediction.get("states_fixed_practice", False)),
        }
    return by_question


def _precision_recall(tp: int, fp: int, fn: int) -> tuple[float | None, float | None]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    return precision, recall


def evaluate(
    human_rows: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    labels_by_id = validate_human_labels(human_rows)
    predictions_by_question = validate_predictions(predictions, labels_by_id)

    benchmarkable = {
        audit_id: row
        for audit_id, row in labels_by_id.items()
        if row["label"] in BENCHMARKABLE_ROLES
    }
    role_totals = {role: {"tp": 0, "fp": 0, "fn": 0} for role in BENCHMARKABLE_ROLES}
    correct = 0
    predicted_benchmarkable = 0
    missing_predictions: list[str] = []

    for audit_id, human in benchmarkable.items():
        prediction = predictions_by_question.get(human["question_id"], {})
        predicted_role = (prediction.get("source_roles") or {}).get(audit_id)
        if predicted_role is None:
            missing_predictions.append(audit_id)
            for role in BENCHMARKABLE_ROLES:
                if human["label"] == role:
                    role_totals[role]["fn"] += 1
            continue
        if predicted_role in BENCHMARKABLE_ROLES:
            predicted_benchmarkable += 1
        if predicted_role == human["label"]:
            correct += 1
        for role in BENCHMARKABLE_ROLES:
            if predicted_role == role and human["label"] == role:
                role_totals[role]["tp"] += 1
            elif predicted_role == role and human["label"] != role:
                role_totals[role]["fp"] += 1
            elif predicted_role != role and human["label"] == role:
                role_totals[role]["fn"] += 1

    per_role: dict[str, dict[str, Any]] = {}
    for role, counts in role_totals.items():
        precision, recall = _precision_recall(counts["tp"], counts["fp"], counts["fn"])
        per_role[role] = {**counts, "precision": precision, "recall": recall}

    denominator_count = 0
    denominator_direct_count = 0
    denominator_leaks: list[dict[str, str]] = []
    distribution_claims = 0
    distribution_minimum_violations: list[str] = []
    practice_line_claims = 0
    practice_line_minimum_violations: list[str] = []
    fixed_practice_claims = 0
    fixed_practice_minimum_violations: list[str] = []

    direct_by_question: dict[str, set[str]] = defaultdict(set)
    for audit_id, row in labels_by_id.items():
        if row["label"] == "direct_practice":
            direct_by_question[row["question_id"]].add(audit_id)

    for question_id, prediction in predictions_by_question.items():
        denominator = prediction["distribution_denominator_audit_ids"]
        if denominator:
            distribution_claims += 1
            if len(denominator) < 2:
                distribution_minimum_violations.append(question_id)
        for audit_id in denominator:
            denominator_count += 1
            if labels_by_id[audit_id]["label"] == "direct_practice":
                denominator_direct_count += 1
            else:
                denominator_leaks.append(
                    {
                        "question_id": question_id,
                        "audit_id": audit_id,
                        "human_label": labels_by_id[audit_id]["label"],
                    }
                )

        if prediction["states_practice_line"]:
            practice_line_claims += 1
            if len(direct_by_question[question_id]) < 3:
                practice_line_minimum_violations.append(question_id)
        if prediction["states_fixed_practice"]:
            fixed_practice_claims += 1
            # Three direct decisions are a minimum evidence guardrail only. Human legal
            # review must still establish consistent reasoning and absence of contrary law.
            if len(direct_by_question[question_id]) < 3:
                fixed_practice_minimum_violations.append(question_id)

    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark": "ejnar_practice_synthesis_human_v1",
        "scope": (
            "Human-grounded structural benchmark for source roles and safe evidence use. "
            "It does not determine substantive consistency or whether practice is legally settled."
        ),
        "summary": {
            "human_rows": len(labels_by_id),
            "benchmarkable_human_rows": len(benchmarkable),
            "uncertain_human_rows": len(labels_by_id) - len(benchmarkable),
            "predicted_benchmarkable_roles": predicted_benchmarkable,
            "missing_role_predictions": len(missing_predictions),
            "role_accuracy": correct / len(benchmarkable) if benchmarkable else None,
            "distribution_claims": distribution_claims,
            "distribution_denominator_entries": denominator_count,
            "distribution_direct_precision": (
                denominator_direct_count / denominator_count if denominator_count else None
            ),
            "distribution_indirect_or_unusable_leaks": len(denominator_leaks),
            "distribution_minimum_evidence_violations": len(distribution_minimum_violations),
            "practice_line_claims": practice_line_claims,
            "practice_line_minimum_evidence_violations": len(practice_line_minimum_violations),
            "fixed_practice_claims": fixed_practice_claims,
            "fixed_practice_minimum_evidence_violations": len(fixed_practice_minimum_violations),
        },
        "per_role": per_role,
        "violations": {
            "missing_role_predictions": missing_predictions,
            "distribution_denominator_leaks": denominator_leaks,
            "distribution_minimum_evidence": distribution_minimum_violations,
            "practice_line_minimum_evidence": practice_line_minimum_violations,
            "fixed_practice_minimum_evidence": fixed_practice_minimum_violations,
        },
        "interpretation": {
            "distribution_guardrail": (
                "Every source counted in a distribution must be human-labelled direct_practice."
            ),
            "practice_line_guardrail": (
                "At least three direct_practice decisions are required before a structured "
                "prediction may state a practice line; this is necessary, not sufficient."
            ),
            "fixed_practice_guardrail": (
                "At least three direct_practice decisions are required, but this metric does not "
                "test whether their legal reasoning is substantively consistent."
            ),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Ejnar practice synthesis")
    sub = parser.add_subparsers(dest="command", required=True)

    template = sub.add_parser("template", help="Build label-free prediction template")
    template.add_argument("--source", type=Path, required=True)
    template.add_argument("--output", type=Path, required=True)

    evaluate_cmd = sub.add_parser("evaluate", help="Evaluate predictions against human labels")
    evaluate_cmd.add_argument("--labels", type=Path, required=True)
    evaluate_cmd.add_argument("--predictions", type=Path, required=True)
    evaluate_cmd.add_argument("--output", type=Path, required=True)
    evaluate_cmd.add_argument("--fail-on-structural-violations", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "template":
        rows = prediction_template(read_jsonl(args.source))
        write_jsonl(args.output, rows)
        print(f"Prepared {len(rows)} synthesis prediction rows")
        return 0

    report = evaluate(read_jsonl(args.labels), read_jsonl(args.predictions))
    _write_json(args.output, report)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if args.fail_on_structural_violations:
        summary = report["summary"]
        violations = (
            summary["distribution_indirect_or_unusable_leaks"]
            + summary["distribution_minimum_evidence_violations"]
            + summary["practice_line_minimum_evidence_violations"]
            + summary["fixed_practice_minimum_evidence_violations"]
        )
        return 1 if violations else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

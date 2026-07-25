"""Mål Ejnars retrieval mod et fastfrosset, auditerbart qrels-datasæt.

Bootstrap-qrels er et ufuldstændigt relevance-pool: kendelser uden dom er derfor
"unjudged" og ikke automatisk irrelevante. Modulet rapporterer både klassiske
ranking-metrikker og judged coverage/precision, så rapporten ikke skjuler hvor
stor en del af topresultaterne der faktisk er bedømt.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class Qrel:
    question_id: str
    case_number: str
    relevance: int
    confidence: float
    source: str = ""
    link: str = ""


@dataclass(frozen=True)
class QrelsCaseMetrics:
    question_id: str
    result_count: int
    judged_total: int
    relevant_total: int
    recall_at_5: float | None
    recall_at_10: float | None
    recall_at_20: float | None
    reciprocal_rank: float | None
    ndcg_at_10: float | None
    judged_coverage_at_5: float | None
    judged_coverage_at_10: float | None
    judged_coverage_at_20: float | None
    judged_precision_at_5: float | None
    judged_precision_at_10: float | None
    first_relevant_rank: int | None


def _normalise(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def _result_keys(result: dict[str, Any]) -> tuple[str, ...]:
    keys: list[str] = []
    for field in (
        "decision_id", "Sagsnummer", "sagsnummer", "case_number",
        "kendelsesnummer", "id", "Link", "link", "url",
    ):
        value = _normalise(result.get(field))
        if value and value not in keys:
            keys.append(value)
    return tuple(keys)


def _qrel_keys(qrel: Qrel) -> tuple[str, ...]:
    keys: list[str] = []
    for value in (qrel.case_number, qrel.link):
        normalised = _normalise(value)
        if normalised and normalised not in keys:
            keys.append(normalised)
    return tuple(keys)


def load_qrels(
    path: str | Path,
    *,
    min_confidence: float = 0.0,
    include_uncertain: bool = False,
) -> list[Qrel]:
    qrels: list[Qrel] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            question_id = str(row.get("question_id") or "").strip()
            case_number = str(row.get("case_number") or "").strip()
            if not question_id or not case_number:
                continue
            try:
                relevance = int(row.get("relevance") or 0)
                confidence = float(row.get("confidence") or 0.0)
            except (TypeError, ValueError):
                continue
            if relevance < 0 and not include_uncertain:
                continue
            if confidence < min_confidence:
                continue
            qrels.append(
                Qrel(
                    question_id=question_id,
                    case_number=case_number,
                    relevance=relevance,
                    confidence=confidence,
                    source=str(row.get("source") or ""),
                    link=str(row.get("link") or ""),
                )
            )
    return qrels


def load_results(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Ugyldig JSON på linje {line_number}: {exc}") from exc
            question_id = str(payload.get("question_id") or "").strip()
            results = payload.get("results")
            if not question_id or not isinstance(results, list):
                raise ValueError(
                    f"Linje {line_number} skal indeholde question_id og en results-liste"
                )
            output[question_id] = [item for item in results if isinstance(item, dict)]
    return output


def group_qrels(qrels: Iterable[Qrel]) -> dict[str, list[Qrel]]:
    grouped: dict[str, list[Qrel]] = {}
    for qrel in qrels:
        grouped.setdefault(qrel.question_id, []).append(qrel)
    return grouped


def _match_result(result: dict[str, Any], qrels: Iterable[Qrel]) -> Qrel | None:
    result_keys = set(_result_keys(result))
    if not result_keys:
        return None
    for qrel in qrels:
        if result_keys & set(_qrel_keys(qrel)):
            return qrel
    return None


def _mean_available(values: Iterable[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return mean(available) if available else None


def _recall(relevance_by_rank: list[int | None], relevant_total: int, k: int) -> float | None:
    if relevant_total <= 0:
        return None
    found = sum(1 for value in relevance_by_rank[:k] if value is not None and value >= 1)
    return found / relevant_total


def _judged_coverage(relevance_by_rank: list[int | None], result_count: int, k: int) -> float | None:
    denominator = min(k, result_count)
    if denominator <= 0:
        return None
    return sum(value is not None for value in relevance_by_rank[:k]) / denominator


def _judged_precision(relevance_by_rank: list[int | None], k: int) -> float | None:
    judged = [value for value in relevance_by_rank[:k] if value is not None]
    if not judged:
        return None
    return sum(value >= 1 for value in judged) / len(judged)


def _ndcg(relevance_by_rank: list[int | None], qrels: list[Qrel], k: int) -> float | None:
    if not qrels:
        return None
    gains = [max(0, int(value or 0)) for value in relevance_by_rank[:k]]
    dcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))
    ideal = sorted((max(0, qrel.relevance) for qrel in qrels), reverse=True)[:k]
    idcg = sum((2**gain - 1) / math.log2(rank + 1) for rank, gain in enumerate(ideal, start=1))
    return dcg / idcg if idcg else None


def evaluate_case(
    question_id: str,
    qrels: list[Qrel],
    results: list[dict[str, Any]],
) -> QrelsCaseMetrics:
    relevance_by_rank: list[int | None] = []
    for result in results:
        matched = _match_result(result, qrels)
        relevance_by_rank.append(matched.relevance if matched is not None else None)

    relevant_total = sum(qrel.relevance >= 1 for qrel in qrels)
    first_rank = next(
        (rank for rank, value in enumerate(relevance_by_rank, start=1) if value is not None and value >= 1),
        None,
    )
    reciprocal_rank = (
        1.0 / first_rank if first_rank is not None else (0.0 if relevant_total else None)
    )
    return QrelsCaseMetrics(
        question_id=question_id,
        result_count=len(results),
        judged_total=len(qrels),
        relevant_total=relevant_total,
        recall_at_5=_recall(relevance_by_rank, relevant_total, 5),
        recall_at_10=_recall(relevance_by_rank, relevant_total, 10),
        recall_at_20=_recall(relevance_by_rank, relevant_total, 20),
        reciprocal_rank=reciprocal_rank,
        ndcg_at_10=_ndcg(relevance_by_rank, qrels, 10),
        judged_coverage_at_5=_judged_coverage(relevance_by_rank, len(results), 5),
        judged_coverage_at_10=_judged_coverage(relevance_by_rank, len(results), 10),
        judged_coverage_at_20=_judged_coverage(relevance_by_rank, len(results), 20),
        judged_precision_at_5=_judged_precision(relevance_by_rank, 5),
        judged_precision_at_10=_judged_precision(relevance_by_rank, 10),
        first_relevant_rank=first_rank,
    )


def aggregate(metrics: list[QrelsCaseMetrics]) -> dict[str, Any]:
    return {
        "questions": len(metrics),
        "questions_with_relevant_qrels": sum(item.relevant_total > 0 for item in metrics),
        "mean_recall_at_5": _mean_available(item.recall_at_5 for item in metrics),
        "mean_recall_at_10": _mean_available(item.recall_at_10 for item in metrics),
        "mean_recall_at_20": _mean_available(item.recall_at_20 for item in metrics),
        "mrr": _mean_available(item.reciprocal_rank for item in metrics),
        "mean_ndcg_at_10": _mean_available(item.ndcg_at_10 for item in metrics),
        "mean_judged_coverage_at_5": _mean_available(item.judged_coverage_at_5 for item in metrics),
        "mean_judged_coverage_at_10": _mean_available(item.judged_coverage_at_10 for item in metrics),
        "mean_judged_coverage_at_20": _mean_available(item.judged_coverage_at_20 for item in metrics),
        "mean_judged_precision_at_5": _mean_available(item.judged_precision_at_5 for item in metrics),
        "mean_judged_precision_at_10": _mean_available(item.judged_precision_at_10 for item in metrics),
    }


def evaluate(
    qrels: list[Qrel],
    results_by_id: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    grouped = group_qrels(qrels)
    benchmarked_ids = sorted(grouped)
    result_ids = set(results_by_id)
    qrel_ids = set(grouped)
    per_case = [
        evaluate_case(question_id, grouped[question_id], results_by_id.get(question_id, []))
        for question_id in benchmarked_ids
    ]
    return {
        "summary": aggregate(per_case),
        "cases": [asdict(item) for item in per_case],
        "qrels": {
            "judgments": len(qrels),
            "sources": sorted({qrel.source for qrel in qrels if qrel.source}),
            "benchmarked_questions": len(qrel_ids),
            "result_questions": len(result_ids),
            "unbenchmarked_result_questions": sorted(result_ids - qrel_ids),
            "missing_result_questions": sorted(qrel_ids - result_ids),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Mål Ejnar mod et qrels-datasæt")
    parser.add_argument("--qrels", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--output")
    parser.add_argument("--min-confidence", type=float, default=0.0)
    args = parser.parse_args()

    report = evaluate(
        load_qrels(args.qrels, min_confidence=max(0.0, args.min_confidence)),
        load_results(args.results),
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

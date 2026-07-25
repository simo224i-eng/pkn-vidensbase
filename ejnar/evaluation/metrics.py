"""Metrikker til reproducerbar evaluering af Ejnars retrieval.

Modulet er uafhængigt af Streamlit, embeddings og LLM-kald. Det evaluerer et
JSONL-resultat fra en vilkårlig retrieval-version mod ``eval_questions.csv``.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import argparse
import csv
import json
import math
from pathlib import Path
import re
from statistics import mean
from typing import Any, Iterable


@dataclass(frozen=True)
class EvaluationCase:
    question_id: str
    query: str
    intent: str
    expected_decision_ids: tuple[str, ...]
    expected_terms: tuple[str, ...]
    expected_phrase: str
    notes: str = ""


@dataclass(frozen=True)
class CaseMetrics:
    question_id: str
    result_count: int
    unique_decisions: int
    recall_at_5: float | None
    recall_at_10: float | None
    recall_at_20: float | None
    reciprocal_rank: float | None
    ndcg_at_10: float | None
    expected_term_coverage: float | None
    exact_phrase_hit: bool | None
    first_relevant_rank: int | None


def _normalise(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _split_pipe(value: str) -> tuple[str, ...]:
    values: list[str] = []
    for part in (value or "").split("|"):
        cleaned = part.strip()
        if cleaned and cleaned not in values:
            values.append(cleaned)
    return tuple(values)


def load_cases(path: str | Path) -> list[EvaluationCase]:
    """Indlæs det juristvedligeholdte CSV-evalueringssæt."""
    cases: list[EvaluationCase] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            question_id = (row.get("question_id") or "").strip()
            query = (row.get("query") or "").strip()
            if not question_id or not query:
                continue
            cases.append(
                EvaluationCase(
                    question_id=question_id,
                    query=query,
                    intent=(row.get("intent") or "").strip(),
                    expected_decision_ids=_split_pipe(row.get("expected_decision_ids") or ""),
                    expected_terms=_split_pipe(row.get("expected_terms") or ""),
                    expected_phrase=(row.get("expected_phrase") or "").strip(),
                    notes=(row.get("notes") or "").strip(),
                )
            )
    return cases


def load_results(path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Indlæs JSONL: én linje med ``question_id`` og ``results`` per spørgsmål."""
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
            output[question_id] = [r for r in results if isinstance(r, dict)]
    return output


def _result_identity(result: dict[str, Any]) -> str:
    for key in (
        "decision_id", "Sagsnummer", "sagsnummer", "case_number",
        "kendelsesnummer", "id", "Link", "link", "url",
    ):
        value = _normalise(result.get(key))
        if value:
            return value
    return _normalise(result.get("Titel") or result.get("title"))


def _result_search_text(result: dict[str, Any]) -> str:
    fields = (
        "Sagsnummer", "sagsnummer", "Titel", "title", "Tekst", "text",
        "Excerpt", "excerpt", "Link", "link", "url",
    )
    return _normalise("\n".join(str(result.get(field) or "") for field in fields))


def _expected_match(expected_id: str, result: dict[str, Any]) -> bool:
    expected = _normalise(expected_id)
    if not expected:
        return False
    identity = _result_identity(result)
    text = _result_search_text(result)
    return expected == identity or expected in identity or expected in text


def _relevant_positions(
    expected_ids: Iterable[str], results: list[dict[str, Any]]
) -> tuple[list[int], set[str]]:
    expected = tuple(_normalise(value) for value in expected_ids if _normalise(value))
    positions: list[int] = []
    found: set[str] = set()
    for rank, result in enumerate(results, start=1):
        matched = [value for value in expected if _expected_match(value, result)]
        if matched:
            positions.append(rank)
            found.update(matched)
    return positions, found


def _recall(expected_ids: tuple[str, ...], results: list[dict[str, Any]], k: int) -> float | None:
    expected = {_normalise(value) for value in expected_ids if _normalise(value)}
    if not expected:
        return None
    _, found = _relevant_positions(expected, results[:k])
    return len(found) / len(expected)


def _ndcg(expected_ids: tuple[str, ...], results: list[dict[str, Any]], k: int) -> float | None:
    expected = tuple(value for value in expected_ids if _normalise(value))
    if not expected:
        return None
    relevance = [1.0 if any(_expected_match(e, result) for e in expected) else 0.0
                 for result in results[:k]]
    dcg = sum(rel / math.log2(rank + 1) for rank, rel in enumerate(relevance, start=1))
    ideal_hits = min(len({_normalise(e) for e in expected}), k)
    idcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
    return dcg / idcg if idcg else 0.0


def evaluate_case(case: EvaluationCase, results: list[dict[str, Any]]) -> CaseMetrics:
    """Beregn retrieval-metrikker for ét spørgsmål."""
    positions, _ = _relevant_positions(case.expected_decision_ids, results)
    first_rank = min(positions) if positions else None
    reciprocal_rank = (1.0 / first_rank) if case.expected_decision_ids and first_rank else (
        0.0 if case.expected_decision_ids else None
    )

    top_text = "\n".join(_result_search_text(result) for result in results[:20])
    expected_terms = [_normalise(term) for term in case.expected_terms if _normalise(term)]
    term_coverage = None
    if expected_terms:
        term_coverage = sum(term in top_text for term in expected_terms) / len(expected_terms)

    phrase = _normalise(case.expected_phrase)
    phrase_hit = (phrase in top_text) if phrase else None

    identities = {_result_identity(result) for result in results if _result_identity(result)}
    return CaseMetrics(
        question_id=case.question_id,
        result_count=len(results),
        unique_decisions=len(identities),
        recall_at_5=_recall(case.expected_decision_ids, results, 5),
        recall_at_10=_recall(case.expected_decision_ids, results, 10),
        recall_at_20=_recall(case.expected_decision_ids, results, 20),
        reciprocal_rank=reciprocal_rank,
        ndcg_at_10=_ndcg(case.expected_decision_ids, results, 10),
        expected_term_coverage=term_coverage,
        exact_phrase_hit=phrase_hit,
        first_relevant_rank=first_rank,
    )


def _mean_available(values: Iterable[float | None]) -> float | None:
    available = [value for value in values if value is not None]
    return mean(available) if available else None


def aggregate(metrics: list[CaseMetrics]) -> dict[str, Any]:
    """Aggregér uden at lade tomme ground-truth-felter tælle som fejl."""
    phrase_values = [m.exact_phrase_hit for m in metrics if m.exact_phrase_hit is not None]
    return {
        "questions": len(metrics),
        "questions_with_expected_ids": sum(m.recall_at_20 is not None for m in metrics),
        "mean_recall_at_5": _mean_available(m.recall_at_5 for m in metrics),
        "mean_recall_at_10": _mean_available(m.recall_at_10 for m in metrics),
        "mean_recall_at_20": _mean_available(m.recall_at_20 for m in metrics),
        "mrr": _mean_available(m.reciprocal_rank for m in metrics),
        "mean_ndcg_at_10": _mean_available(m.ndcg_at_10 for m in metrics),
        "mean_expected_term_coverage": _mean_available(
            m.expected_term_coverage for m in metrics
        ),
        "exact_phrase_hit_rate": (
            sum(bool(value) for value in phrase_values) / len(phrase_values)
            if phrase_values else None
        ),
        "mean_unique_decisions": (
            mean(m.unique_decisions for m in metrics) if metrics else None
        ),
    }


def evaluate(cases: list[EvaluationCase], results_by_id: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    per_case = [evaluate_case(case, results_by_id.get(case.question_id, [])) for case in cases]
    return {
        "summary": aggregate(per_case),
        "cases": [asdict(item) for item in per_case],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Beregn Ejnars retrieval-metrikker")
    parser.add_argument("--questions", required=True, help="Sti til eval_questions.csv")
    parser.add_argument("--results", required=True, help="Sti til retrieval_results.jsonl")
    parser.add_argument("--output", help="Valgfri JSON-outputfil")
    args = parser.parse_args()

    report = evaluate(load_cases(args.questions), load_results(args.results))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

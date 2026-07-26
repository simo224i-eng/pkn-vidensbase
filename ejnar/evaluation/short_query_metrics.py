"""Topic-level metrics og merge-gate til Query Planners korte søgninger."""
from __future__ import annotations

from dataclasses import asdict
import random
from statistics import mean
from typing import Any, Iterable, Sequence

from .qrels_metrics import Qrel, evaluate_case, group_qrels
from .short_query_benchmark import (
    GUARDRAIL_COHORT,
    TREATED_COHORT,
    ShortQuerySpec,
)


_FIELDS = (
    "recall_at_5",
    "recall_at_10",
    "recall_at_20",
    "reciprocal_rank",
    "ndcg_at_10",
    "judged_coverage_at_5",
    "judged_coverage_at_10",
    "judged_precision_at_5",
    "judged_precision_at_10",
)


def _mean(values: Iterable[float | None]) -> float | None:
    available = [float(value) for value in values if value is not None]
    return mean(available) if available else None


def _result_map(
    payloads: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    return {
        str(item.get("question_id") or ""): [
            result
            for result in item.get("results") or []
            if isinstance(result, dict)
        ]
        for item in payloads
        if item.get("question_id")
    }


def evaluate_short_queries(
    specs: Sequence[ShortQuerySpec],
    qrels: Sequence[Qrel],
    payloads: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluér pr. query og makro-gennemsnit pr. uafhængigt emne."""
    results = _result_map(payloads)
    qrels_by_id = group_qrels(qrels)
    query_rows: list[dict[str, Any]] = []
    for spec in specs:
        metrics = evaluate_case(
            spec.question_id,
            qrels_by_id.get(spec.question_id, []),
            results.get(spec.question_id, []),
        )
        row = asdict(metrics)
        row.update(
            {
                "topic_id": spec.topic_id,
                "variant": spec.variant,
                "category": spec.category,
                "cohort": spec.cohort,
                "split": spec.split,
            }
        )
        query_rows.append(row)

    treated_rows = [
        item for item in query_rows if item["cohort"] == TREATED_COHORT
    ]
    topics: list[dict[str, Any]] = []
    for topic_id in sorted({item["topic_id"] for item in treated_rows}):
        variants = [item for item in treated_rows if item["topic_id"] == topic_id]
        row: dict[str, Any] = {
            "topic_id": topic_id,
            "category": variants[0]["category"],
            "split": variants[0]["split"],
            "queries": len(variants),
        }
        for field in _FIELDS:
            row[field] = _mean(item.get(field) for item in variants)
        topics.append(row)

    categories: dict[str, dict[str, Any]] = {}
    for category in sorted({item["category"] for item in topics}):
        rows = [item for item in topics if item["category"] == category]
        categories[category] = {
            "topics": len(rows),
            **{
                field: _mean(item.get(field) for item in rows)
                for field in _FIELDS
            },
        }

    splits: dict[str, dict[str, Any]] = {}
    for split in sorted({item["split"] for item in topics}):
        rows = [item for item in topics if item["split"] == split]
        splits[split] = {
            "topics": len(rows),
            "macro_topic_ndcg_at_10": _mean(
                item.get("ndcg_at_10") for item in rows
            ),
            "macro_topic_recall_at_20": _mean(
                item.get("recall_at_20") for item in rows
            ),
            "macro_topic_mrr": _mean(
                item.get("reciprocal_rank") for item in rows
            ),
            "macro_topic_judged_precision_at_5": _mean(
                item.get("judged_precision_at_5") for item in rows
            ),
        }

    fully_judged = [
        item["question_id"]
        for item in query_rows
        if item.get("judged_coverage_at_10") == 1.0
    ]
    coverage_violations = [
        item["question_id"]
        for item in query_rows
        if item.get("judged_coverage_at_10") != 1.0
    ]
    return {
        "summary": {
            "queries": len(query_rows),
            "treated_queries": len(treated_rows),
            "treated_topics": len(topics),
            "macro_topic_ndcg_at_10": _mean(
                item.get("ndcg_at_10") for item in topics
            ),
            "macro_topic_recall_at_20": _mean(
                item.get("recall_at_20") for item in topics
            ),
            "macro_topic_mrr": _mean(
                item.get("reciprocal_rank") for item in topics
            ),
            "macro_topic_judged_precision_at_5": _mean(
                item.get("judged_precision_at_5") for item in topics
            ),
            "fully_judged_top_10_queries": len(fully_judged),
        },
        "queries": query_rows,
        "topics": topics,
        "categories": categories,
        "splits": splits,
        "fully_judged_top_10": fully_judged,
        "coverage_violations_top_10": coverage_violations,
    }


def _topic_values(
    report: dict[str, Any],
    *,
    split: str | None = None,
) -> dict[str, float]:
    return {
        str(item["topic_id"]): float(item["ndcg_at_10"])
        for item in report.get("topics") or []
        if item.get("ndcg_at_10") is not None
        and (split is None or item.get("split") == split)
    }


def paired_bootstrap_lower_bound(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    samples: int = 5000,
    seed: int = 20260726,
    percentile: float = 0.025,
    split: str | None = None,
) -> float | None:
    """Deterministisk nedre percentil for parrede topic-NDCG-deltaer."""
    base = _topic_values(baseline, split=split)
    cand = _topic_values(candidate, split=split)
    topic_ids = sorted(set(base) & set(cand))
    if not topic_ids:
        return None
    deltas = [cand[topic_id] - base[topic_id] for topic_id in topic_ids]
    generator = random.Random(seed)
    draws = sorted(
        mean(generator.choice(deltas) for _ in deltas)
        for _ in range(max(1, samples))
    )
    index = min(
        len(draws) - 1,
        max(0, int(percentile * len(draws))),
    )
    return draws[index]


def compare_short_query_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    planner_effect: dict[str, Any],
    minimum_planner_applications: int = 12,
    minimum_evaluation_split_applications: int = 5,
    minimum_evaluation_split_topics: int = 5,
    minimum_ndcg_gain: float = 0.01,
    minimum_bootstrap_lower_bound: float = -0.005,
    maximum_secondary_drop: float = 0.01,
    maximum_category_ndcg_drop: float = 0.03,
    evaluation_split: str = "holdout",
) -> dict[str, Any]:
    """Anvend den dokumenterede default-on gate på et blindbedømt datasæt."""
    baseline_summary = (
        (baseline.get("splits") or {}).get(evaluation_split)
        or baseline.get("summary")
        or {}
    )
    candidate_summary = (
        (candidate.get("splits") or {}).get(evaluation_split)
        or candidate.get("summary")
        or {}
    )
    metric_names = {
        "macro_topic_ndcg_at_10": minimum_ndcg_gain,
        "macro_topic_recall_at_20": -maximum_secondary_drop,
        "macro_topic_mrr": -maximum_secondary_drop,
        "macro_topic_judged_precision_at_5": -maximum_secondary_drop,
    }
    metric_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for name, required_delta in metric_names.items():
        base = baseline_summary.get(name)
        cand = candidate_summary.get(name)
        delta = (
            float(cand) - float(base)
            if base is not None and cand is not None
            else None
        )
        passed = delta is not None and delta >= required_delta - 1e-12
        if not passed:
            failures.append(name)
        metric_rows.append(
            {
                "metric": name,
                "baseline": base,
                "candidate": cand,
                "delta": delta,
                "required_delta": required_delta,
                "passed": passed,
            }
        )

    treated = int((planner_effect or {}).get("treated_queries") or 0)
    if treated < minimum_planner_applications:
        failures.append("minimum_planner_applications")
    evaluation_effect = (
        ((planner_effect or {}).get("treated_by_split") or {}).get(
            evaluation_split
        )
        or {}
    )
    split_applications = int(
        evaluation_effect.get("planner_applications") or 0
    )
    split_topics = int(evaluation_effect.get("active_topics") or 0)
    if split_applications < minimum_evaluation_split_applications:
        failures.append("minimum_evaluation_split_applications")
    if split_topics < minimum_evaluation_split_topics:
        failures.append("minimum_evaluation_split_topics")

    if baseline.get("coverage_violations_top_10"):
        failures.append("baseline_top_10_not_fully_judged")
    if candidate.get("coverage_violations_top_10"):
        failures.append("candidate_top_10_not_fully_judged")
    if (planner_effect or {}).get("precision_guardrail_violations"):
        failures.append("precision_guardrail_results")
    if (planner_effect or {}).get("fallback_violations"):
        failures.append("fallback_results")

    lower_bound = paired_bootstrap_lower_bound(
        baseline,
        candidate,
        split=evaluation_split,
    )
    if lower_bound is None or lower_bound < minimum_bootstrap_lower_bound:
        failures.append("paired_bootstrap_lower_bound")

    def category_ndcg(report: dict[str, Any]) -> dict[str, float]:
        output: dict[str, list[float]] = {}
        for topic in report.get("topics") or []:
            if topic.get("split") != evaluation_split:
                continue
            value = topic.get("ndcg_at_10")
            if value is None:
                continue
            output.setdefault(str(topic.get("category") or ""), []).append(
                float(value)
            )
        return {
            category: mean(values)
            for category, values in output.items()
            if category and values
        }

    base_categories = category_ndcg(baseline)
    candidate_categories = category_ndcg(candidate)
    category_rows: list[dict[str, Any]] = []
    for category in sorted(set(base_categories) & set(candidate_categories)):
        base = base_categories[category]
        cand = candidate_categories[category]
        delta = (
            float(cand) - float(base)
            if base is not None and cand is not None
            else None
        )
        passed = (
            delta is not None
            and delta >= -maximum_category_ndcg_drop - 1e-12
        )
        if not passed:
            failures.append(f"category_ndcg:{category}")
        category_rows.append(
            {
                "category": category,
                "baseline": base,
                "candidate": cand,
                "delta": delta,
                "passed": passed,
            }
        )

    base_topics = _topic_values(baseline, split=evaluation_split)
    cand_topics = _topic_values(candidate, split=evaluation_split)
    paired = [
        cand_topics[topic_id] - base_topics[topic_id]
        for topic_id in sorted(set(base_topics) & set(cand_topics))
    ]
    return {
        "passed": not failures,
        "failures": list(dict.fromkeys(failures)),
        "metrics": metric_rows,
        "categories": category_rows,
        "paired_bootstrap_95_lower_bound": lower_bound,
        "topic_win_tie_loss": {
            "wins": sum(delta > 1e-12 for delta in paired),
            "ties": sum(abs(delta) <= 1e-12 for delta in paired),
            "losses": sum(delta < -1e-12 for delta in paired),
        },
        "policy": {
            "minimum_planner_applications": minimum_planner_applications,
            "minimum_evaluation_split_applications": (
                minimum_evaluation_split_applications
            ),
            "minimum_evaluation_split_topics": minimum_evaluation_split_topics,
            "minimum_ndcg_gain": minimum_ndcg_gain,
            "minimum_bootstrap_lower_bound": minimum_bootstrap_lower_bound,
            "maximum_secondary_drop": maximum_secondary_drop,
            "maximum_category_ndcg_drop": maximum_category_ndcg_drop,
            "top_10_must_be_fully_judged": True,
            "guardrail_rankings_must_be_identical": True,
            "fallback_rankings_must_be_identical": True,
            "claim_decisions_generated": False,
            "evaluation_split": evaluation_split,
        },
    }

"""Benchmark Query Planner v1 mod samme proces og frosne qrels.

Kontrolkørslen installerer den levende pipeline uden planneren. Kandidatkørslen
installerer derefter kun query-planner-runtime oven på den samme proces, corpus og
TF-IDF-matrice. Dermed isoleres plannerens effekt fra data- og miljøvariation.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .compare_reports import compare_reports, render_markdown
from .metrics import load_cases
from .qrels_metrics import evaluate as evaluate_qrels
from .qrels_metrics import load_qrels
from .run_live_retrieval import install_live_retrieval_pipeline
from .run_retrieval import (
    EJNAR_DIR,
    _metrics_input,
    build_tfidf,
    load_corpus,
    run_cases,
    write_jsonl,
)


# Én procentpoint er den største tilladte samlede kvalitetsregression. De
# precision-sensitive opslag ændres slet ikke af planneren.
PLANNER_REGRESSION_THRESHOLDS = {
    "mean_recall_at_5": 0.01,
    "mean_recall_at_10": 0.01,
    "mean_recall_at_20": 0.01,
    "mrr": 0.01,
    "mean_ndcg_at_10": 0.01,
    "mean_judged_precision_at_5": 0.01,
    "mean_judged_precision_at_10": 0.01,
}
MAX_LATENCY_RATIO = 1.25


def _result_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    """Returnér den synlige resultatrækkefølge med stabile identifikatorer."""
    values: list[str] = []
    for result in payload.get("results") or []:
        if not isinstance(result, dict):
            continue
        value = str(
            result.get("Sagsnummer")
            or result.get("decision_id")
            or result.get("Link")
            or ""
        ).strip()
        if value:
            values.append(value)
    return tuple(values)


def summarise_planner_effect(
    baseline_payloads: list[dict[str, Any]],
    candidate_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """Dokumentér om planneren faktisk behandlede og flyttede forespørgsler.

    En grøn kvalitetsrapport er ikke i sig selv evidens for en planner-effekt:
    hvis ingen effektive forespørgsler ændres, har testen alene vist, at koden
    ikke gjorde skade. Denne rapport gør no-op-eksperimenter synlige.
    """

    baseline_by_id = {
        str(item.get("question_id") or ""): item
        for item in baseline_payloads
        if item.get("question_id")
    }
    candidate_by_id = {
        str(item.get("question_id") or ""): item
        for item in candidate_payloads
        if item.get("question_id")
    }
    rows: list[dict[str, Any]] = []
    precision_guardrail_violations: list[str] = []
    for question_id in sorted(set(baseline_by_id) | set(candidate_by_id)):
        baseline = baseline_by_id.get(question_id) or {}
        candidate = candidate_by_id.get(question_id) or {}
        baseline_query = str(baseline.get("effective_query") or "")
        candidate_query = str(candidate.get("effective_query") or "")
        baseline_ids = _result_ids(baseline)
        candidate_ids = _result_ids(candidate)
        effective_query_changed = baseline_query != candidate_query
        result_list_changed = baseline_ids != candidate_ids
        detected_intent = str(
            candidate.get("detected_intent")
            or baseline.get("detected_intent")
            or ""
        )
        precision_sensitive = detected_intent in {
            "exact_content_search",
            "specific_decision_search",
        }
        if precision_sensitive and (
            effective_query_changed or result_list_changed
        ):
            precision_guardrail_violations.append(question_id)
        rows.append(
            {
                "question_id": question_id,
                "detected_intent": detected_intent,
                "effective_query_changed": effective_query_changed,
                "result_list_changed": result_list_changed,
                "precision_sensitive": precision_sensitive,
                "baseline_effective_query": baseline_query,
                "candidate_effective_query": candidate_query,
            }
        )

    return {
        "questions": len(rows),
        "treated_queries": sum(
            bool(item["effective_query_changed"]) for item in rows
        ),
        "changed_result_lists": sum(
            bool(item["result_list_changed"]) for item in rows
        ),
        "precision_guardrail_violations": precision_guardrail_violations,
        "cases": rows,
    }


def apply_planner_policy(
    comparison: dict[str, Any],
    *,
    planner_effect: dict[str, Any] | None = None,
    min_treated_queries: int = 0,
    min_result_list_changes: int = 0,
    min_ndcg_gain: float | None = None,
) -> dict[str, Any]:
    """Gør kvalitet, guardrails og et eventuelt no-op-eksperiment blokerende."""
    output = dict(comparison)
    regressions = list(output.get("regressions") or [])
    latency_ratio = (output.get("latency") or {}).get("ratio")
    latency_regression = (
        latency_ratio is not None
        and float(latency_ratio) > MAX_LATENCY_RATIO
    )
    if latency_regression and "mean_latency_ms" not in regressions:
        regressions.append("mean_latency_ms")
    effect = dict(planner_effect or {})
    if int(effect.get("treated_queries") or 0) < max(0, min_treated_queries):
        regressions.append("planner_treated_queries")
    if int(effect.get("changed_result_lists") or 0) < max(
        0, min_result_list_changes
    ):
        regressions.append("planner_result_list_changes")
    if effect.get("precision_guardrail_violations"):
        regressions.append("precision_guardrail_results")

    if min_ndcg_gain is not None:
        ndcg = next(
            (
                item
                for item in output.get("metrics") or []
                if item.get("metric") == "mean_ndcg_at_10"
            ),
            {},
        )
        delta = ndcg.get("delta")
        if delta is None or float(delta) < float(min_ndcg_gain):
            regressions.append("mean_ndcg_at_10_gain")

    regressions = list(dict.fromkeys(regressions))
    output["regressions"] = regressions
    output["passed"] = not regressions
    output["planner_effect"] = effect
    output["policy"] = {
        "max_material_drop": PLANNER_REGRESSION_THRESHOLDS,
        "max_latency_ratio": MAX_LATENCY_RATIO,
        "min_treated_queries": max(0, min_treated_queries),
        "min_result_list_changes": max(0, min_result_list_changes),
        "min_ndcg_gain": min_ndcg_gain,
        "precision_sensitive_intents_are_not_expanded": True,
        "claim_decisions_generated": False,
    }
    return output


def _with_run_metadata(
    report: dict[str, Any],
    payloads: list[dict[str, Any]],
    *,
    pipeline: str,
    documents: int,
    top_k: int,
) -> dict[str, Any]:
    output = dict(report)
    output["run"] = {
        "pipeline": pipeline,
        "documents": documents,
        "questions": len(payloads),
        "top_k": top_k,
        "mean_latency_ms": (
            sum(float(item["latency_ms"]) for item in payloads) / len(payloads)
            if payloads
            else None
        ),
    }
    return output


def evaluate_payloads(
    payloads: list[dict[str, Any]],
    *,
    qrels_path: str | Path,
    pipeline: str,
    documents: int,
    top_k: int,
) -> dict[str, Any]:
    report = evaluate_qrels(
        load_qrels(qrels_path),
        _metrics_input(payloads),
    )
    return _with_run_metadata(
        report,
        payloads,
        pipeline=pipeline,
        documents=documents,
        top_k=top_k,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Ejnars konservative Query Planner v1"
    )
    parser.add_argument(
        "--questions",
        default=str(EJNAR_DIR / "evaluation" / "eval_questions.csv"),
    )
    parser.add_argument(
        "--qrels",
        default=str(EJNAR_DIR / "evaluation" / "bootstrap_qrels_v2.csv"),
    )
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--min-treated-queries",
        type=int,
        default=0,
        help="Fejl hvis færre effektive forespørgsler ændres af planneren.",
    )
    parser.add_argument(
        "--min-result-list-changes",
        type=int,
        default=0,
        help="Fejl hvis planneren flytter færre resultatrækkefølger end angivet.",
    )
    parser.add_argument(
        "--min-ndcg-gain",
        type=float,
        help="Valgfrit minimumskrav til absolut forbedring i NDCG@10.",
    )
    parser.add_argument(
        "--allow-material-regression",
        action="store_true",
        help="Skriv rapporter, men returnér 0 selv ved en målbar regression.",
    )
    args = parser.parse_args()

    top_k = max(1, args.top_k)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import shared

    install_live_retrieval_pipeline(shared, include_query_planner=False)
    cases = load_cases(args.questions)
    frame = load_corpus(Path(args.data_dir), shared)
    vectorizer, matrix = build_tfidf(frame, shared)

    baseline_payloads = run_cases(
        cases,
        frame,
        vectorizer,
        matrix,
        shared,
        top_k=top_k,
        rerank=False,
    )

    try:
        from query_planner_runtime import install_query_planner_runtime
    except ImportError:
        from ejnar.query_planner_runtime import install_query_planner_runtime

    install_query_planner_runtime(shared)
    candidate_payloads = run_cases(
        cases,
        frame,
        vectorizer,
        matrix,
        shared,
        top_k=top_k,
        rerank=False,
    )

    baseline_results = output_dir / "baseline-results.jsonl"
    candidate_results = output_dir / "candidate-results.jsonl"
    write_jsonl(baseline_results, baseline_payloads)
    write_jsonl(candidate_results, candidate_payloads)

    baseline_report = evaluate_payloads(
        baseline_payloads,
        qrels_path=args.qrels,
        pipeline=(
            "intent+paragraph_bm25+metadata+query_feature_0.12+"
            "specific_decision"
        ),
        documents=len(frame),
        top_k=top_k,
    )
    candidate_report = evaluate_payloads(
        candidate_payloads,
        qrels_path=args.qrels,
        pipeline=(
            "intent+query_planner_v1+paragraph_bm25+metadata+"
            "query_feature_0.12+specific_decision"
        ),
        documents=len(frame),
        top_k=top_k,
    )
    planner_effect = summarise_planner_effect(
        baseline_payloads,
        candidate_payloads,
    )
    comparison = apply_planner_policy(
        compare_reports(
            baseline_report,
            candidate_report,
            thresholds=PLANNER_REGRESSION_THRESHOLDS,
        ),
        planner_effect=planner_effect,
        min_treated_queries=max(0, args.min_treated_queries),
        min_result_list_changes=max(0, args.min_result_list_changes),
        min_ndcg_gain=args.min_ndcg_gain,
    )

    (output_dir / "baseline-qrels-report.json").write_text(
        json.dumps(baseline_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "candidate-qrels-report.json").write_text(
        json.dumps(candidate_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "comparison.md").write_text(
        render_markdown(comparison),
        encoding="utf-8",
    )

    print(json.dumps(comparison, ensure_ascii=False, indent=2))
    if comparison["passed"] or args.allow_material_regression:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

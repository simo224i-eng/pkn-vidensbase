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


def apply_planner_policy(comparison: dict[str, Any]) -> dict[str, Any]:
    """Gør både kvalitets- og væsentlig latency-regression blokerende."""
    output = dict(comparison)
    regressions = list(output.get("regressions") or [])
    latency_ratio = (output.get("latency") or {}).get("ratio")
    latency_regression = (
        latency_ratio is not None
        and float(latency_ratio) > MAX_LATENCY_RATIO
    )
    if latency_regression and "mean_latency_ms" not in regressions:
        regressions.append("mean_latency_ms")
    output["regressions"] = regressions
    output["passed"] = not regressions
    output["policy"] = {
        "max_material_drop": PLANNER_REGRESSION_THRESHOLDS,
        "max_latency_ratio": MAX_LATENCY_RATIO,
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
    comparison = apply_planner_policy(
        compare_reports(
            baseline_report,
            candidate_report,
            thresholds=PLANNER_REGRESSION_THRESHOLDS,
        )
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

"""Kør et isoleret Query Planner-eksperiment på frosne korte søgninger.

Runneren kan først bruges i ``--pool-only``-tilstand til blind bedømmelse. Når
qrels er frosset, beregner den topic-level metrics og anvender den strengere
default-on gate. Det almindelige qrels-v2-benchmark forbliver et separat globalt
regressionsværn.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .qrels_metrics import load_qrels
from .run_live_retrieval import install_live_retrieval_pipeline
from .run_query_planner_experiment import summarise_planner_effect
from .run_retrieval import EJNAR_DIR, build_tfidf, load_corpus, run_cases, write_jsonl
from .short_query_benchmark import (
    FALLBACK_COHORT,
    GUARDRAIL_COHORT,
    TREATED_COHORT,
    build_blind_pool,
    load_specs,
    specs_sha256,
    validate_specs,
    write_jsonl as write_pool_jsonl,
)
from .short_query_metrics import (
    compare_short_query_reports,
    evaluate_short_queries,
)


DEFAULT_QUESTIONS = EJNAR_DIR / "evaluation" / "short_query_questions_v1.csv"
DEFAULT_QRELS = EJNAR_DIR / "evaluation" / "short_query_silver_qrels_v1.csv"


def _cohort_effect(
    effect: dict[str, Any],
    specs: list[Any],
) -> dict[str, Any]:
    output = dict(effect)
    spec_by_id = {item.question_id: item for item in specs}
    rows = list(output.get("cases") or [])
    for row in rows:
        spec = spec_by_id.get(row.get("question_id"))
        row["cohort"] = spec.cohort if spec else ""
        row["split"] = spec.split if spec else ""
        row["topic_id"] = spec.topic_id if spec else ""
    treated = [row for row in rows if row.get("cohort") == TREATED_COHORT]
    fallbacks = [row for row in rows if row.get("cohort") == FALLBACK_COHORT]
    guardrails = [row for row in rows if row.get("cohort") == GUARDRAIL_COHORT]
    output["treated_queries"] = sum(
        bool(row.get("effective_query_changed")) for row in treated
    )
    output["treated_result_list_changes"] = sum(
        bool(row.get("result_list_changed")) for row in treated
    )
    output["precision_guardrail_violations"] = [
        str(row["question_id"])
        for row in guardrails
        if row.get("effective_query_changed") or row.get("result_list_changed")
    ]
    output["fallback_violations"] = [
        str(row["question_id"])
        for row in fallbacks
        if row.get("effective_query_changed") or row.get("result_list_changed")
    ]
    output["treated_by_split"] = {}
    for split in sorted({row.get("split") for row in treated if row.get("split")}):
        split_rows = [row for row in treated if row.get("split") == split]
        active_rows = [
            row for row in split_rows if row.get("effective_query_changed")
        ]
        output["treated_by_split"][str(split)] = {
            "queries": len(split_rows),
            "planner_applications": len(active_rows),
            "active_topics": len(
                {
                    str(row.get("topic_id"))
                    for row in active_rows
                    if row.get("topic_id")
                }
            ),
            "changed_result_lists": sum(
                bool(row.get("result_list_changed")) for row in split_rows
            ),
        }
    output["cases"] = rows
    return output


def _render_markdown(
    integrity: dict[str, Any],
    effect: dict[str, Any],
    comparison: dict[str, Any] | None,
) -> str:
    lines = [
        "# Ejnar short-query planner benchmark",
        "",
        f"- Queries: **{integrity['questions']}**",
        f"- Treated topics: **{integrity['treated_topics']}**",
        f"- Planner applications: **{effect.get('treated_queries', 0)}**",
        f"- Treated result-list changes: **{effect.get('treated_result_list_changes', 0)}**",
        f"- Guardrail violations: **{len(effect.get('precision_guardrail_violations') or [])}**",
        f"- Fallback violations: **{len(effect.get('fallback_violations') or [])}**",
    ]
    for split, values in sorted(
        (effect.get("treated_by_split") or {}).items()
    ):
        lines.append(
            f"- {split.title()} activations: "
            f"**{values.get('planner_applications', 0)} queries / "
            f"{values.get('active_topics', 0)} topics**"
        )
    if comparison is None:
        lines.extend(
            [
                "",
                "Pool-only run: no quality verdict was produced.",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(
        [
            "",
            f"## Verdict: {'PASS' if comparison.get('passed') else 'INCONCLUSIVE/FAIL'}",
            "",
            "| Metric | Baseline | Candidate | Delta | Required |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in comparison.get("metrics") or []:
        def fmt(value: Any) -> str:
            return "–" if value is None else f"{float(value):.4f}"

        lines.append(
            f"| {item['metric']} | {fmt(item.get('baseline'))} | "
            f"{fmt(item.get('candidate'))} | {fmt(item.get('delta'))} | "
            f"{fmt(item.get('required_delta'))} |"
        )
    if comparison.get("failures"):
        lines.extend(
            [
                "",
                "Failures: " + ", ".join(comparison["failures"]),
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark Query Planner på korte, blindbedømte søgninger"
    )
    parser.add_argument("--questions", default=str(DEFAULT_QUESTIONS))
    parser.add_argument("--qrels", default=str(DEFAULT_QRELS))
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-k", type=int, default=30)
    parser.add_argument("--pool-depth", type=int, default=30)
    parser.add_argument(
        "--minimum-treated-cohort-size",
        type=int,
        default=60,
    )
    parser.add_argument(
        "--minimum-planner-applications",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--minimum-holdout-planner-applications",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--minimum-holdout-active-topics",
        type=int,
        default=5,
    )
    parser.add_argument(
        "--pool-only",
        action="store_true",
        help="Skriv blind kandidatpulje uden at kræve eller evaluere qrels.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    specs = load_specs(args.questions)
    integrity = validate_specs(
        specs,
        minimum_treated_cohort_size=max(
            1, args.minimum_treated_cohort_size
        ),
    )
    integrity["specs_sha256"] = specs_sha256(specs)
    cases = [item.to_evaluation_case() for item in specs]

    import shared

    frame = load_corpus(Path(args.data_dir), shared)
    vectorizer, matrix = build_tfidf(frame, shared)
    top_k = max(1, args.top_k)
    original_expand = shared.udvid_query
    try:
        shared.udvid_query = lambda query: query
        lexical_payloads = run_cases(
            cases,
            frame,
            vectorizer,
            matrix,
            shared,
            top_k=top_k,
            rerank=False,
        )
    finally:
        shared.udvid_query = original_expand

    install_live_retrieval_pipeline(shared, include_query_planner=False)
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
    write_jsonl(output_dir / "lexical-results.jsonl", lexical_payloads)
    write_jsonl(output_dir / "baseline-results.jsonl", baseline_payloads)
    write_jsonl(output_dir / "candidate-results.jsonl", candidate_payloads)

    blind_pool, pool_provenance = build_blind_pool(
        specs,
        {
            "original_query_lexical": lexical_payloads,
            "baseline": baseline_payloads,
            "query_planner_v1": candidate_payloads,
        },
        pool_depth=max(1, args.pool_depth),
    )
    write_pool_jsonl(output_dir / "blind-pool.jsonl", blind_pool)
    write_pool_jsonl(output_dir / "pool-provenance.jsonl", pool_provenance)

    effect = _cohort_effect(
        summarise_planner_effect(baseline_payloads, candidate_payloads),
        specs,
    )
    comparison: dict[str, Any] | None = None
    if not args.pool_only:
        qrels_path = Path(args.qrels)
        if not qrels_path.exists():
            raise FileNotFoundError(
                f"Qrels mangler: {qrels_path}. Kør først med --pool-only."
            )
        qrels = load_qrels(qrels_path)
        baseline_report = evaluate_short_queries(
            specs,
            qrels,
            baseline_payloads,
        )
        candidate_report = evaluate_short_queries(
            specs,
            qrels,
            candidate_payloads,
        )
        comparison = compare_short_query_reports(
            baseline_report,
            candidate_report,
            planner_effect=effect,
            minimum_planner_applications=max(
                1, args.minimum_planner_applications
            ),
            minimum_evaluation_split_applications=max(
                1, args.minimum_holdout_planner_applications
            ),
            minimum_evaluation_split_topics=max(
                1, args.minimum_holdout_active_topics
            ),
        )
        (output_dir / "baseline-report.json").write_text(
            json.dumps(baseline_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "candidate-report.json").write_text(
            json.dumps(candidate_report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (output_dir / "comparison.json").write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    (output_dir / "integrity.json").write_text(
        json.dumps(integrity, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "planner-effect.json").write_text(
        json.dumps(effect, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        _render_markdown(integrity, effect, comparison),
        encoding="utf-8",
    )

    payload = {
        "integrity": integrity,
        "planner_effect": effect,
        "comparison": comparison,
        "pool_candidates": len(blind_pool),
        "quality_label": (
            "silver" if comparison is not None else "unjudged_pool"
        ),
        "claim_decisions_generated": False,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    control_violations = (
        effect.get("precision_guardrail_violations")
        or effect.get("fallback_violations")
    )
    too_few_applications = (
        int(effect.get("treated_queries") or 0)
        < max(1, args.minimum_planner_applications)
    )
    holdout_effect = (
        (effect.get("treated_by_split") or {}).get("holdout") or {}
    )
    too_few_holdout_applications = (
        int(holdout_effect.get("planner_applications") or 0)
        < max(1, args.minimum_holdout_planner_applications)
    )
    too_few_holdout_topics = (
        int(holdout_effect.get("active_topics") or 0)
        < max(1, args.minimum_holdout_active_topics)
    )
    if (
        args.pool_only
        and not control_violations
        and not too_few_applications
        and not too_few_holdout_applications
        and not too_few_holdout_topics
    ):
        return 0
    if comparison and comparison.get("passed"):
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Kør evaluering mod samme retrieval-lag som den levende Ejnar-app.

Den oprindelige runner bevares som lexical/intention-baseline. Denne runner installerer
intent-, paragraph-, metadata-, query-feature- og specific-decision-runtime i samme
rækkefølge som ``ejnar/app.py``. Citation-runtime ændrer kun LLM-kontekst og indgår
ikke i retrieval-metrikkerne.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import evaluate, load_cases
from .run_retrieval import (
    EJNAR_DIR,
    _metrics_input,
    build_tfidf,
    load_corpus,
    run_cases,
    write_jsonl,
)


def install_live_retrieval_pipeline(shared_module: Any) -> None:
    """Installér produktionslagene i samme rækkefølge som Streamlit-appen."""
    try:
        from retrieval_runtime import install_retrieval_runtime
        from paragraph_runtime import install_paragraph_runtime
        from metadata_runtime import install_metadata_runtime
        from query_feature_runtime import install_query_feature_runtime
        from specific_decision_runtime import install_specific_decision_runtime
    except ImportError:
        from ejnar.retrieval_runtime import install_retrieval_runtime
        from ejnar.paragraph_runtime import install_paragraph_runtime
        from ejnar.metadata_runtime import install_metadata_runtime
        from ejnar.query_feature_runtime import install_query_feature_runtime
        from ejnar.specific_decision_runtime import install_specific_decision_runtime

    install_retrieval_runtime(shared_module)
    install_paragraph_runtime(shared_module)
    install_metadata_runtime(shared_module)
    install_query_feature_runtime(shared_module)
    install_specific_decision_runtime(shared_module)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Kør Ejnars retrieval-evaluering mod den levende pipeline"
    )
    parser.add_argument(
        "--questions",
        default=str(EJNAR_DIR / "evaluation" / "eval_questions.csv"),
    )
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument(
        "--results",
        default=str(EJNAR_DIR / "evaluation" / "live_retrieval_results.jsonl"),
    )
    parser.add_argument(
        "--report",
        default=str(EJNAR_DIR / "evaluation" / "live_retrieval_report.json"),
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Brug LLM-rerank; kræver relevante secrets og bruges ikke i CI-baseline",
    )
    args = parser.parse_args()

    import shared

    install_live_retrieval_pipeline(shared)
    cases = load_cases(args.questions)
    frame = load_corpus(Path(args.data_dir), shared)
    vectorizer, matrix = build_tfidf(frame, shared)
    payloads = run_cases(
        cases,
        frame,
        vectorizer,
        matrix,
        shared,
        top_k=max(1, args.top_k),
        rerank=args.rerank,
    )

    results_path = Path(args.results)
    report_path = Path(args.report)
    write_jsonl(results_path, payloads)
    report = evaluate(cases, _metrics_input(payloads))
    report["run"] = {
        "pipeline": "intent+paragraph_bm25+metadata+query_feature_0.12+specific_decision",
        "documents": len(frame),
        "questions": len(cases),
        "top_k": max(1, args.top_k),
        "rerank": bool(args.rerank),
        "mean_latency_ms": (
            sum(float(item["latency_ms"]) for item in payloads) / len(payloads)
            if payloads else None
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

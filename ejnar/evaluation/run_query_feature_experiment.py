"""Sammenlign Ejnars frosne retrieval-baseline med query-feature-reranking.

Eksperimentet ændrer ikke produktionsretrieval. Det genbruger den levende pipeline,
bevarer den samme top-k candidate pool og skriver ét resultatsæt pr. styrke, så
qrels v2 kan evaluere effekten direkte.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .metrics import evaluate, load_cases
from .run_live_retrieval import install_live_retrieval_pipeline
from .run_retrieval import (
    EJNAR_DIR,
    _metrics_input,
    build_tfidf,
    load_corpus,
    run_cases,
    write_jsonl,
)

try:
    from query_feature_rerank import rerank_by_query_features
except ImportError:
    from ejnar.query_feature_rerank import rerank_by_query_features


def _parse_strengths(raw: str) -> list[float]:
    values: list[float] = []
    for item in raw.split(","):
        value = float(item.strip())
        if value < 0:
            raise ValueError("strength skal være mindst 0")
        values.append(value)
    return sorted(set(values))


def _rerank_payload(
    payload: dict[str, Any],
    *,
    strength: float,
    top_k: int,
) -> dict[str, Any]:
    output = dict(payload)
    reranked = rerank_by_query_features(
        str(payload.get("query") or ""),
        list(payload.get("results") or []),
        strength=strength,
    )
    output["results"] = [
        {**row, "rank": rank}
        for rank, row in enumerate(reranked[:top_k], start=1)
    ]
    output["query_feature_rerank"] = {
        "enabled": strength > 0,
        "strength": strength,
        "candidate_pool": len(payload.get("results") or []),
    }
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark query-feature-reranking mod Ejnars levende baseline"
    )
    parser.add_argument(
        "--questions",
        default=str(EJNAR_DIR / "evaluation" / "eval_questions.csv"),
    )
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--strengths",
        default="0,0.02,0.05,0.08,0.12",
        help="Komma-separerede metadata-styrker; 0 er kontrol",
    )
    args = parser.parse_args()

    strengths = _parse_strengths(args.strengths)
    top_k = max(1, args.top_k)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    import shared

    install_live_retrieval_pipeline(shared)
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

    manifest: dict[str, Any] = {
        "pipeline": "intent+paragraph_bm25+metadata+specific_decision",
        "documents": len(frame),
        "questions": len(cases),
        "top_k": top_k,
        "strengths": strengths,
        "runs": [],
    }
    for strength in strengths:
        payloads = [
            _rerank_payload(payload, strength=strength, top_k=top_k)
            for payload in baseline_payloads
        ]
        label = f"strength-{strength:.2f}".replace(".", "_")
        results_path = output_dir / f"{label}.jsonl"
        report_path = output_dir / f"{label}-expected-report.json"
        write_jsonl(results_path, payloads)
        report = evaluate(cases, _metrics_input(payloads))
        report["run"] = {
            "query_feature_strength": strength,
            "top_k": top_k,
            "documents": len(frame),
            "questions": len(cases),
        }
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["runs"].append(
            {
                "strength": strength,
                "results": results_path.name,
                "expected_report": report_path.name,
            }
        )

    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

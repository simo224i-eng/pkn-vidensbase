"""Diagnostic runner that records Ejnar retrieval output after every runtime layer.

Used by the reproducibility workflow to locate the *first* layer whose ordered
candidate list differs across otherwise identical GitHub runners. This is
measurement-only and does not affect the production app.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Callable

from .metrics import load_cases
from .run_retrieval import EJNAR_DIR, build_tfidf, load_corpus


STAGE_ORDER = (
    "deterministic_base",
    "intent",
    "paragraph",
    "metadata",
    "query_feature",
    "specific_decision",
)


def _identity(df: Any, idx: int) -> str:
    try:
        row = df.iloc[int(idx)]
    except Exception:
        return f"idx:{int(idx)}"
    case = str(row.get("Sagsnummer", "") or "").strip()
    if case:
        return f"case:{case}"
    link = str(row.get("Link", "") or "").strip()
    if link:
        return f"link:{link}"
    return f"idx:{int(idx)}"


def _wrap_hybrid(shared_module: Any, stage: str, sink: list[dict[str, Any]]) -> None:
    original = shared_module.hybrid_retrieval

    def traced_hybrid(
        query: str,
        df: Any,
        vec: Any,
        mat: Any,
        embeds: Any,
        sub_idx: Any = None,
        top_retrieve: int = 40,
        top_final: int = 20,
    ) -> list[int]:
        result = original(
            query,
            df,
            vec,
            mat,
            embeds,
            sub_idx=sub_idx,
            top_retrieve=top_retrieve,
            top_final=top_final,
        )
        sink.append(
            {
                "stage": stage,
                "query": query,
                "indices": [int(idx) for idx in result],
                "identities": [_identity(df, int(idx)) for idx in result],
            }
        )
        return result

    shared_module.hybrid_retrieval = traced_hybrid


def install_traced_pipeline(shared_module: Any, sink: list[dict[str, Any]]) -> None:
    try:
        from deterministic_retrieval_runtime import install_deterministic_retrieval_runtime
        from retrieval_runtime import install_retrieval_runtime
        from query_planner_runtime import install_query_planner_runtime
        from paragraph_runtime import install_paragraph_runtime
        from metadata_runtime import install_metadata_runtime
        from query_feature_runtime import install_query_feature_runtime
        from specific_decision_runtime import install_specific_decision_runtime
    except ImportError:
        from ejnar.deterministic_retrieval_runtime import install_deterministic_retrieval_runtime
        from ejnar.retrieval_runtime import install_retrieval_runtime
        from ejnar.query_planner_runtime import install_query_planner_runtime
        from ejnar.paragraph_runtime import install_paragraph_runtime
        from ejnar.metadata_runtime import install_metadata_runtime
        from ejnar.query_feature_runtime import install_query_feature_runtime
        from ejnar.specific_decision_runtime import install_specific_decision_runtime

    install_deterministic_retrieval_runtime(shared_module)
    _wrap_hybrid(shared_module, "deterministic_base", sink)

    install_retrieval_runtime(shared_module)
    _wrap_hybrid(shared_module, "intent", sink)

    # Query planner changes the effective query, not hybrid_retrieval itself.
    install_query_planner_runtime(shared_module)

    install_paragraph_runtime(shared_module)
    _wrap_hybrid(shared_module, "paragraph", sink)

    install_metadata_runtime(shared_module)
    _wrap_hybrid(shared_module, "metadata", sink)

    install_query_feature_runtime(shared_module)
    _wrap_hybrid(shared_module, "query_feature", sink)

    install_specific_decision_runtime(shared_module)
    _wrap_hybrid(shared_module, "specific_decision", sink)


def _collapse_trace(events: list[dict[str, Any]]) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for event in events:
        stage = str(event.get("stage") or "")
        if stage:
            output[stage] = list(event.get("identities") or [])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Trace Ejnar retrieval after every runtime layer")
    parser.add_argument("--questions", default=str(EJNAR_DIR / "evaluation" / "eval_questions.csv"))
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument("--output", required=True)
    parser.add_argument("--top-k", type=int, default=20)
    args = parser.parse_args()

    import shared
    from query_intent import classify_query

    sink: list[dict[str, Any]] = []
    install_traced_pipeline(shared, sink)
    cases = load_cases(args.questions)
    frame = load_corpus(Path(args.data_dir), shared)
    vectorizer, matrix = build_tfidf(frame, shared)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for case in cases:
            plan = classify_query(case.query)
            effective_query = shared.udvid_query(case.query) if plan.expand_query else case.query
            sink.clear()
            shared.hybrid_retrieval(
                effective_query,
                frame,
                vectorizer,
                matrix,
                embeds=None,
                sub_idx=list(range(len(frame))),
                top_retrieve=max(plan.top_retrieve, args.top_k),
                top_final=max(plan.top_final, args.top_k),
            )
            payload = {
                "question_id": case.question_id,
                "query": case.query,
                "effective_query": effective_query,
                "stages": _collapse_trace(sink),
            }
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

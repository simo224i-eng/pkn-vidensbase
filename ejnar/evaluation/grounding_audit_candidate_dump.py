"""Dump all grounding-audit candidates before contrast thresholding.

This is diagnostics-only. It exists so cross-host audit reproducibility can distinguish
whether a drifting review row comes from the query excerpt, decision core, or threshold
selection. No legal label is inferred and this file is never included in the blind human
review package.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from grounding_audit_pool import build_candidates, read_jsonl, write_jsonl
except ImportError:
    from ejnar.evaluation.grounding_audit_pool import build_candidates, read_jsonl, write_jsonl


_DIAGNOSTIC_FIELDS = (
    "audit_id",
    "question_id",
    "query",
    "retrieval_rank",
    "case_number",
    "title",
    "query_excerpt_section",
    "query_excerpt",
    "query_matched_terms",
    "query_excerpt_score",
    "decision_core_section",
    "decision_core",
    "grounding_used_fallback",
    "core_ground_tags",
    "excerpt_ground_tags",
    "exclusive_ground_tags",
    "section_differs",
    "contrast_score",
    "priority",
)


def diagnostic_rows(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {field: candidate.get(field) for field in _DIAGNOSTIC_FIELDS}
        for candidate in candidates
    ]
    rows.sort(key=lambda row: (str(row.get("audit_id") or ""), int(row.get("retrieval_rank") or 0)))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dump all grounding audit candidates before threshold")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--top-results-per-query", type=int, default=10)
    args = parser.parse_args(argv)

    payloads = read_jsonl(args.results)
    candidates = build_candidates(
        payloads,
        top_results_per_query=max(0, args.top_results_per_query),
    )
    rows = diagnostic_rows(candidates)
    write_jsonl(args.output, rows)
    print(json.dumps({"candidate_rows": len(rows)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Sammenlign to Ejnar retrieval-rapporter og markér målbare regressioner."""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MetricDelta:
    metric: str
    baseline: float | None
    candidate: float | None
    delta: float | None
    threshold: float
    regression: bool


DEFAULT_THRESHOLDS = {
    "mean_recall_at_5": 0.03,
    "mean_recall_at_10": 0.03,
    "mean_recall_at_20": 0.02,
    "mrr": 0.03,
    "mean_ndcg_at_10": 0.03,
    "exact_phrase_hit_rate": 0.03,
    "mean_expected_term_coverage": 0.03,
}


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare_reports(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    limits = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        limits.update(thresholds)

    base_summary = baseline.get("summary") or {}
    candidate_summary = candidate.get("summary") or {}
    deltas: list[MetricDelta] = []
    for metric, threshold in limits.items():
        base_value = _number(base_summary.get(metric))
        candidate_value = _number(candidate_summary.get(metric))
        delta = (
            candidate_value - base_value
            if base_value is not None and candidate_value is not None
            else None
        )
        regression = delta is not None and delta < -abs(float(threshold))
        deltas.append(
            MetricDelta(
                metric=metric,
                baseline=base_value,
                candidate=candidate_value,
                delta=delta,
                threshold=float(threshold),
                regression=regression,
            )
        )

    latency_base = _number((baseline.get("run") or {}).get("mean_latency_ms"))
    latency_candidate = _number((candidate.get("run") or {}).get("mean_latency_ms"))
    latency_ratio = (
        latency_candidate / latency_base
        if latency_base and latency_candidate is not None
        else None
    )
    regressions = [item.metric for item in deltas if item.regression]
    return {
        "passed": not regressions,
        "regressions": regressions,
        "metrics": [asdict(item) for item in deltas],
        "latency": {
            "baseline_ms": latency_base,
            "candidate_ms": latency_candidate,
            "ratio": latency_ratio,
        },
    }


def render_markdown(report: dict[str, Any]) -> str:
    status = "✅ Bestået" if report.get("passed") else "❌ Regression fundet"
    lines = [f"## Retrieval-sammenligning — {status}", "", "| Metric | Baseline | Kandidat | Delta |", "|---|---:|---:|---:|"]
    for item in report.get("metrics") or []:
        def fmt(value: Any) -> str:
            return "–" if value is None else f"{float(value):.4f}"
        marker = " ⚠️" if item.get("regression") else ""
        lines.append(
            f"| {item['metric']}{marker} | {fmt(item.get('baseline'))} | "
            f"{fmt(item.get('candidate'))} | {fmt(item.get('delta'))} |"
        )
    latency = report.get("latency") or {}
    if latency.get("ratio") is not None:
        lines.extend(["", f"Latency ratio: **{float(latency['ratio']):.2f}×**"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Sammenlign Ejnar retrieval-rapporter")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--output")
    parser.add_argument("--markdown")
    parser.add_argument("--fail-on-regression", action="store_true")
    args = parser.parse_args()

    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    result = compare_reports(baseline, candidate)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(render_markdown(result), encoding="utf-8")
    print(rendered)
    return 1 if args.fail_on_regression and not result["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

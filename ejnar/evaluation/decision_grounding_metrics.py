"""Deterministic evaluation for Ejnar's decision-grounding layer.

This benchmark is deliberately adversarial: the query-relevant fact may point one way
while the Board's actual decision rests on a condition report, proof, a deadline,
an exclusion, a threshold, or another ground. It evaluates context extraction only; it
must not be described as a gold benchmark of Ankenævnet practice.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from decision_grounding import extract_decision_grounding
except ImportError:
    from ejnar.decision_grounding import extract_decision_grounding


DEFAULT_CASES = Path(__file__).with_name("decision_grounding_cases_v1.json")


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def load_cases(path: Path = DEFAULT_CASES) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("decision-grounding cases must be a JSON list")
    seen: set[str] = set()
    for case in payload:
        case_id = str(case.get("case_id") or "").strip()
        if not case_id or case_id in seen:
            raise ValueError(f"missing or duplicate case_id: {case_id!r}")
        seen.add(case_id)
    return payload


def evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    grounding = extract_decision_grounding({"Tekst": str(case.get("text") or "")})
    text = _normalise(grounding.text)
    section = _normalise(grounding.section_title)

    expected_terms = [
        str(value) for value in (case.get("expected_grounding_terms") or []) if str(value).strip()
    ]
    forbidden_terms = [
        str(value) for value in (case.get("forbidden_grounding_terms") or []) if str(value).strip()
    ]
    expected_section = _normalise(case.get("expected_section_contains"))
    expected_fallback = bool(case.get("expected_fallback", False))

    found_expected = [term for term in expected_terms if _normalise(term) in text]
    missing_expected = [term for term in expected_terms if _normalise(term) not in text]
    leaked_forbidden = [term for term in forbidden_terms if _normalise(term) in text]
    section_ok = not expected_section or expected_section in section
    fallback_ok = grounding.used_fallback == expected_fallback
    term_recall = (len(found_expected) / len(expected_terms)) if expected_terms else 1.0

    passed = (
        not missing_expected
        and not leaked_forbidden
        and section_ok
        and fallback_ok
    )
    return {
        "case_id": case["case_id"],
        "category": case.get("category", ""),
        "query": case.get("query", ""),
        "passed": passed,
        "section_title": grounding.section_title,
        "section_ok": section_ok,
        "expected_fallback": expected_fallback,
        "used_fallback": grounding.used_fallback,
        "fallback_ok": fallback_ok,
        "expected_terms": expected_terms,
        "found_expected_terms": found_expected,
        "missing_expected_terms": missing_expected,
        "forbidden_terms": forbidden_terms,
        "leaked_forbidden_terms": leaked_forbidden,
        "term_recall": term_recall,
        "grounding_text": grounding.text,
        "notes": case.get("notes", ""),
    }


def evaluate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    results = [evaluate_case(case) for case in cases]
    total = len(results)
    passed = sum(bool(result["passed"]) for result in results)
    expected_term_count = sum(len(result["expected_terms"]) for result in results)
    found_term_count = sum(len(result["found_expected_terms"]) for result in results)
    forbidden_count = sum(len(result["forbidden_terms"]) for result in results)
    leakage_count = sum(len(result["leaked_forbidden_terms"]) for result in results)

    categories: dict[str, dict[str, int]] = {}
    for result in results:
        category = str(result["category"] or "uncategorised")
        bucket = categories.setdefault(category, {"cases": 0, "passed": 0})
        bucket["cases"] += 1
        bucket["passed"] += int(bool(result["passed"]))

    return {
        "schema_version": 1,
        "benchmark": "decision_grounding_adversarial_v1",
        "scope": (
            "Synthetic/adversarial extraction regression suite. "
            "Not a gold benchmark of Ankenævnet practice and not a claim-decision evaluator."
        ),
        "summary": {
            "cases": total,
            "passed_cases": passed,
            "failed_cases": total - passed,
            "case_pass_rate": (passed / total) if total else 1.0,
            "expected_term_recall": (
                found_term_count / expected_term_count if expected_term_count else 1.0
            ),
            "forbidden_term_leakage_rate": (
                leakage_count / forbidden_count if forbidden_count else 0.0
            ),
            "section_accuracy": (
                sum(bool(result["section_ok"]) for result in results) / total if total else 1.0
            ),
            "fallback_accuracy": (
                sum(bool(result["fallback_ok"]) for result in results) / total if total else 1.0
            ),
        },
        "categories": categories,
        "results": results,
    }


def write_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, default=Path("decision_grounding_report.json"))
    parser.add_argument(
        "--allow-failures",
        action="store_true",
        help="Write the report but return exit code 0 even when cases fail.",
    )
    args = parser.parse_args(argv)

    report = evaluate(load_cases(args.cases))
    write_report(report, args.output)
    summary = report["summary"]
    print(
        "Decision grounding: "
        f"{summary['passed_cases']}/{summary['cases']} cases passed; "
        f"expected-term recall={summary['expected_term_recall']:.3f}; "
        f"forbidden leakage={summary['forbidden_term_leakage_rate']:.3f}"
    )
    if summary["failed_cases"] and not args.allow_failures:
        for result in report["results"]:
            if not result["passed"]:
                print(
                    f"FAIL {result['case_id']}: "
                    f"missing={result['missing_expected_terms']} "
                    f"leaked={result['leaked_forbidden_terms']} "
                    f"section_ok={result['section_ok']} "
                    f"fallback_ok={result['fallback_ok']}"
                )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Prepare, validate and freeze human review of Ejnar grounding audit cases.

The input is the blind adjudication pool produced by ``grounding_audit_pool``.  This
module deliberately never reads the diagnostics artifact: retrieval rank, contrast score
and heuristic tags must not leak into the human review surface.

A completed review can be frozen as a provenance-rich human label set.  The tool does
not itself decide what a decision means and never upgrades unreviewed or uncertain rows
to ground truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 1
REVIEW_LABELS: dict[str, str] = {
    "direct_practice": (
        "Nævnets egen begrundelse tager direkte stilling til det juridiske spørgsmål, "
        "og det spørgsmålsrelevante uddrag kan bruges som direkte praksisstøtte."
    ),
    "indirect_support": (
        "Kendelsen belyser spørgsmålet, men udfaldet eller den bærende begrundelse "
        "hviler på et andet grundlag. Brug kun som analogi eller indirekte støtte."
    ),
    "not_useful": (
        "Kendelsen/uddraget giver ikke pålidelig støtte til det stillede spørgsmål."
    ),
    "uncertain": (
        "Det kan ikke afgøres sikkert på det viste materiale; kræver yderligere kontrol."
    ),
}

_SOURCE_FIELDS = (
    "audit_id",
    "question_id",
    "query",
    "case_number",
    "title",
    "date",
    "link",
    "query_excerpt_section",
    "query_excerpt",
    "decision_core_section",
    "decision_core",
)
_REVIEW_FIELDS = (
    "review_order",
    "audit_id",
    "query",
    "case_number",
    "title",
    "date",
    "link",
    "query_excerpt_section",
    "query_excerpt",
    "decision_core_section",
    "decision_core",
    "review_label",
    "reviewer",
    "review_notes",
)


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _canonical_source_row(row: dict[str, Any]) -> dict[str, str]:
    return {field: _normalise(row.get(field)) for field in _SOURCE_FIELDS}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def source_digest(rows: Iterable[dict[str, Any]]) -> str:
    canonical = sorted(
        (_canonical_source_row(dict(row)) for row in rows),
        key=lambda item: item["audit_id"],
    )
    return hashlib.sha256(_canonical_json(canonical).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"line {line_number} is not a JSON object")
            rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_review_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_REVIEW_FIELDS), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in _REVIEW_FIELDS})


def _validate_blind_source(rows: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    forbidden = {
        "retrieval_rank",
        "contrast_score",
        "priority",
        "exclusive_ground_tags",
        "core_ground_tags",
        "query_excerpt_score",
        "query_matched_terms",
    }
    for index, row in enumerate(rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        if not audit_id:
            raise ValueError(f"source row {index} has no audit_id")
        if audit_id in seen:
            raise ValueError(f"duplicate audit_id in source: {audit_id}")
        seen.add(audit_id)
        leaked = sorted(forbidden.intersection(row))
        if leaked:
            raise ValueError(
                f"blind source contains diagnostic fields for {audit_id}: {', '.join(leaked)}"
            )


def _blind_order(audit_id: str) -> str:
    # Stable pseudo-random order independent of retrieval ranking or heuristics.
    return hashlib.sha256(f"ejnar-grounding-human-v1\x1f{audit_id}".encode("utf-8")).hexdigest()


def prepare_review_rows(source_rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    _validate_blind_source(source_rows)
    prepared: list[dict[str, str]] = []
    for source in source_rows:
        row = _canonical_source_row(source)
        prepared.append(
            {
                "review_order": _blind_order(row["audit_id"]),
                "audit_id": row["audit_id"],
                "query": row["query"],
                "case_number": row["case_number"],
                "title": row["title"],
                "date": row["date"],
                "link": row["link"],
                "query_excerpt_section": row["query_excerpt_section"],
                "query_excerpt": row["query_excerpt"],
                "decision_core_section": row["decision_core_section"],
                "decision_core": row["decision_core"],
                "review_label": "",
                "reviewer": "",
                "review_notes": "",
            }
        )
    prepared.sort(key=lambda item: (item["review_order"], item["audit_id"]))
    for position, row in enumerate(prepared, start=1):
        row["review_order"] = str(position)
    return prepared


def review_manifest(source_rows: list[dict[str, Any]]) -> dict[str, Any]:
    _validate_blind_source(source_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ejnar_grounding_human_review_v1",
        "rows": len(source_rows),
        "source_sha256": source_digest(source_rows),
        "labels": REVIEW_LABELS,
        "protocol": [
            "Læs først brugerens spørgsmål.",
            "Læs derefter det spørgsmålsrelevante uddrag og afgørelseskernen.",
            "Bedøm om kendelsen er direkte praksis, indirekte støtte, ikke nyttig eller usikker.",
            "Vælg indirect_support når det relevante udsagn findes, men kendelsen reelt afgøres på et andet grundlag.",
            "Skriv aldrig label ud fra udfald alene; den bærende begrundelse er afgørende.",
            "Brug uncertain hvis det viste materiale ikke er tilstrækkeligt og kontrollér originalkendelsen før endelig label.",
        ],
        "blinding": (
            "Reviewpakken indeholder ingen retrieval-rank, heuristisk contrast score, "
            "priority eller automatiske juridiske labels."
        ),
    }


def validate_review(
    review_rows: list[dict[str, str]],
    *,
    source_rows: list[dict[str, Any]] | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    seen: set[str] = set()
    label_counts = {label: 0 for label in REVIEW_LABELS}
    reviewers: set[str] = set()

    for position, row in enumerate(review_rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        label = _normalise(row.get("review_label")).casefold()
        reviewer = _normalise(row.get("reviewer"))
        notes = _normalise(row.get("review_notes"))
        if not audit_id:
            errors.append(f"row {position}: missing audit_id")
            continue
        if audit_id in seen:
            errors.append(f"duplicate audit_id: {audit_id}")
        seen.add(audit_id)

        if not label:
            if require_complete:
                errors.append(f"{audit_id}: missing review_label")
            continue
        if label not in REVIEW_LABELS:
            errors.append(f"{audit_id}: invalid review_label {label!r}")
            continue
        label_counts[label] += 1
        if not reviewer:
            errors.append(f"{audit_id}: labelled row has no reviewer")
        else:
            reviewers.add(reviewer)
        if label == "uncertain" and not notes:
            errors.append(f"{audit_id}: uncertain requires review_notes")
        if label == "indirect_support" and not notes:
            warnings.append(f"{audit_id}: indirect_support should preferably explain the other ground")

    source_hash = None
    source_count = None
    if source_rows is not None:
        _validate_blind_source(source_rows)
        source_ids = {_normalise(row.get("audit_id")) for row in source_rows}
        review_ids = {_normalise(row.get("audit_id")) for row in review_rows if _normalise(row.get("audit_id"))}
        missing = sorted(source_ids - review_ids)
        extra = sorted(review_ids - source_ids)
        if missing:
            errors.append(f"review is missing {len(missing)} source audit_ids")
        if extra:
            errors.append(f"review contains {len(extra)} unknown audit_ids")
        source_hash = source_digest(source_rows)
        source_count = len(source_rows)

    return {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "rows": len(review_rows),
        "source_rows": source_count,
        "source_sha256": source_hash,
        "label_counts": label_counts,
        "reviewers": sorted(reviewers),
        "errors": errors,
        "warnings": warnings,
    }


def freeze_human_labels(
    review_rows: list[dict[str, str]],
    source_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    report = validate_review(review_rows, source_rows=source_rows, require_complete=True)
    if not report["valid"]:
        raise ValueError("cannot freeze invalid review: " + "; ".join(report["errors"][:8]))

    source_by_id = {
        _normalise(row.get("audit_id")): _canonical_source_row(row)
        for row in source_rows
    }
    frozen: list[dict[str, Any]] = []
    for review in review_rows:
        audit_id = _normalise(review.get("audit_id"))
        label = _normalise(review.get("review_label")).casefold()
        source = source_by_id[audit_id]
        frozen.append(
            {
                "audit_id": audit_id,
                "question_id": source["question_id"],
                "query": source["query"],
                "case_number": source["case_number"],
                "link": source["link"],
                "label": label,
                "benchmark_relevance": {
                    "direct_practice": 2,
                    "indirect_support": 1,
                    "not_useful": 0,
                    "uncertain": None,
                }[label],
                "reviewer": _normalise(review.get("reviewer")),
                "review_notes": _normalise(review.get("review_notes")),
            }
        )
    frozen.sort(key=lambda item: item["audit_id"])

    benchmarkable = sum(item["benchmark_relevance"] is not None for item in frozen)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "ejnar_grounding_human_labels_v1",
        "rows": len(frozen),
        "benchmarkable_rows": benchmarkable,
        "uncertain_rows": len(frozen) - benchmarkable,
        "source_sha256": source_digest(source_rows),
        "reviewers": report["reviewers"],
        "label_counts": report["label_counts"],
        "relevance_mapping": {
            "direct_practice": 2,
            "indirect_support": 1,
            "not_useful": 0,
            "uncertain": None,
        },
        "warning": (
            "Human labels describe whether each retrieved decision supports the stated query. "
            "They are not automatic coverage decisions and uncertain rows are excluded from metrics."
        ),
    }
    return frozen, manifest


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejnar grounding human-review tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    prepare = sub.add_parser("prepare", help="Convert blind JSONL pool to review CSV")
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--csv", type=Path, required=True)
    prepare.add_argument("--manifest", type=Path, required=True)

    validate = sub.add_parser("validate", help="Validate completed review CSV")
    validate.add_argument("--csv", type=Path, required=True)
    validate.add_argument("--source", type=Path)
    validate.add_argument("--report", type=Path, required=True)
    validate.add_argument("--allow-incomplete", action="store_true")

    freeze = sub.add_parser("freeze", help="Freeze a completed human label set")
    freeze.add_argument("--csv", type=Path, required=True)
    freeze.add_argument("--source", type=Path, required=True)
    freeze.add_argument("--labels", type=Path, required=True)
    freeze.add_argument("--manifest", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        source_rows = read_jsonl(args.source)
        write_review_csv(args.csv, prepare_review_rows(source_rows))
        _write_json(args.manifest, review_manifest(source_rows))
        print(f"Prepared {len(source_rows)} blind review rows")
        return 0

    if args.command == "validate":
        source_rows = read_jsonl(args.source) if args.source else None
        report = validate_review(
            read_review_csv(args.csv),
            source_rows=source_rows,
            require_complete=not args.allow_incomplete,
        )
        _write_json(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["valid"] else 1

    source_rows = read_jsonl(args.source)
    frozen, manifest = freeze_human_labels(read_review_csv(args.csv), source_rows)
    write_jsonl(args.labels, frozen)
    manifest["review_csv_sha256"] = file_digest(args.csv)
    _write_json(args.manifest, manifest)
    print(f"Frozen {len(frozen)} human-reviewed rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

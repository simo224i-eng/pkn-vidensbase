"""Split and recombine Ejnar's blind grounding review sheet safely.

The master review CSV is already blinded by ``grounding_review.py``. This module makes
human adjudication manageable by splitting that stable order into small CSV batches. It
never reads diagnostics and allows only review_label/reviewer/review_notes to differ from
the master when batches are recombined.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

try:
    from grounding_review import file_digest, read_review_csv, write_review_csv
except ImportError:
    from ejnar.evaluation.grounding_review import file_digest, read_review_csv, write_review_csv


SCHEMA_VERSION = 1
_EDITABLE_FIELDS = {"review_label", "reviewer", "review_notes"}


def _normalise(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _evidence_payload(row: dict[str, Any]) -> dict[str, str]:
    return {
        key: _normalise(value)
        for key, value in row.items()
        if key not in _EDITABLE_FIELDS
    }


def _row_digest(row: dict[str, Any]) -> str:
    payload = json.dumps(
        _evidence_payload(row),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_batches(
    review_rows: list[dict[str, Any]],
    *,
    batch_size: int = 15,
) -> list[list[dict[str, Any]]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for position, row in enumerate(review_rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        if not audit_id:
            raise ValueError(f"review row {position}: missing audit_id")
        if audit_id in seen:
            raise ValueError(f"duplicate audit_id in master review: {audit_id}")
        seen.add(audit_id)
        rows.append(dict(row))
    return [rows[start:start + batch_size] for start in range(0, len(rows), batch_size)]


def write_batches(
    output_dir: Path,
    batches: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    width = max(2, len(str(max(1, len(batches)))))
    for number, batch in enumerate(batches, start=1):
        filename = f"grounding-review-batch-{number:0{width}d}.csv"
        path = output_dir / filename
        write_review_csv(path, batch)
        audit_ids = [_normalise(row.get("audit_id")) for row in batch]
        entries.append(
            {
                "batch": number,
                "file": filename,
                "rows": len(batch),
                "first_review_order": _normalise(batch[0].get("review_order")) if batch else "",
                "last_review_order": _normalise(batch[-1].get("review_order")) if batch else "",
                "audit_ids_sha256": hashlib.sha256(
                    "\x1f".join(audit_ids).encode("utf-8")
                ).hexdigest(),
                "file_sha256": file_digest(path),
            }
        )
    return entries


def batch_manifest(
    master_csv: Path,
    review_rows: list[dict[str, Any]],
    entries: list[dict[str, Any]],
    *,
    batch_size: int,
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ejnar_grounding_review_batches_v1",
        "master_rows": len(review_rows),
        "batch_size": batch_size,
        "batches": len(entries),
        "master_csv_sha256": file_digest(master_csv),
        "batch_entries": entries,
        "editable_fields": sorted(_EDITABLE_FIELDS),
        "warning": (
            "Batch files preserve the blind master evidence. Only review_label, reviewer "
            "and review_notes may be edited before recombination."
        ),
    }


def combine_batches(
    master_rows: list[dict[str, Any]],
    batch_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    master_by_id: dict[str, dict[str, Any]] = {}
    master_order: list[str] = []
    for position, row in enumerate(master_rows, start=1):
        audit_id = _normalise(row.get("audit_id"))
        if not audit_id:
            raise ValueError(f"master row {position}: missing audit_id")
        if audit_id in master_by_id:
            raise ValueError(f"duplicate audit_id in master: {audit_id}")
        master_by_id[audit_id] = dict(row)
        master_order.append(audit_id)

    reviewed_by_id: dict[str, dict[str, Any]] = {}
    evidence_errors: list[str] = []
    duplicates: list[str] = []
    unknown: list[str] = []
    for row in batch_rows:
        audit_id = _normalise(row.get("audit_id"))
        if not audit_id:
            raise ValueError("batch row has no audit_id")
        if audit_id in reviewed_by_id:
            duplicates.append(audit_id)
            continue
        if audit_id not in master_by_id:
            unknown.append(audit_id)
            continue
        if _row_digest(row) != _row_digest(master_by_id[audit_id]):
            evidence_errors.append(audit_id)
            continue
        reviewed_by_id[audit_id] = dict(row)

    missing = [audit_id for audit_id in master_order if audit_id not in reviewed_by_id]
    errors: list[str] = []
    if duplicates:
        errors.append(f"duplicate audit_ids across batches: {', '.join(sorted(set(duplicates))[:8])}")
    if unknown:
        errors.append(f"unknown audit_ids in batches: {', '.join(sorted(set(unknown))[:8])}")
    if evidence_errors:
        errors.append(
            "immutable review evidence changed for: "
            + ", ".join(sorted(set(evidence_errors))[:8])
        )
    if missing:
        errors.append(f"missing {len(missing)} master audit_ids")

    report = {
        "schema_version": SCHEMA_VERSION,
        "valid": not errors,
        "master_rows": len(master_rows),
        "combined_rows": len(reviewed_by_id),
        "missing_rows": len(missing),
        "duplicate_rows": len(set(duplicates)),
        "unknown_rows": len(set(unknown)),
        "edited_evidence_rows": len(set(evidence_errors)),
        "errors": errors,
    }
    if errors:
        return [], report

    combined = [reviewed_by_id[audit_id] for audit_id in master_order]
    return combined, report


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ejnar grounding review batching")
    sub = parser.add_subparsers(dest="command", required=True)

    split = sub.add_parser("split", help="Split blind master review CSV into small batches")
    split.add_argument("--csv", type=Path, required=True)
    split.add_argument("--output-dir", type=Path, required=True)
    split.add_argument("--manifest", type=Path, required=True)
    split.add_argument("--batch-size", type=int, default=15)

    combine = sub.add_parser("combine", help="Combine completed review batches safely")
    combine.add_argument("--master", type=Path, required=True)
    combine.add_argument("--input-dir", type=Path, required=True)
    combine.add_argument("--output", type=Path, required=True)
    combine.add_argument("--report", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "split":
        rows = read_review_csv(args.csv)
        batches = split_batches(rows, batch_size=args.batch_size)
        entries = write_batches(args.output_dir, batches)
        _write_json(
            args.manifest,
            batch_manifest(args.csv, rows, entries, batch_size=args.batch_size),
        )
        print(f"Split {len(rows)} rows into {len(batches)} blind review batches")
        return 0

    master_rows = read_review_csv(args.master)
    paths = sorted(args.input_dir.glob("grounding-review-batch-*.csv"))
    if not paths:
        raise FileNotFoundError(f"no grounding review batches found in {args.input_dir}")
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(read_review_csv(path))
    combined, report = combine_batches(master_rows, rows)
    _write_json(args.report, report)
    if not report["valid"]:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    write_review_csv(args.output, combined)
    print(f"Combined {len(combined)} reviewed rows from {len(paths)} batches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

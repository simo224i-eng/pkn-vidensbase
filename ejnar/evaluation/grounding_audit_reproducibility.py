"""Fingerprint and compare Ejnar's blind grounding-review package across hosts.

Retrieval reproducibility is necessary but not sufficient for a stable human benchmark:
audit selection, blind ordering, CSV serialisation or batch splitting could introduce a
second source of drift. This module fingerprints the *actual adjudication package* that a
jurist would review and compares independent builds without reading or inferring legal
labels.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from grounding_review import file_digest, read_jsonl, read_review_csv, source_digest
except ImportError:
    from ejnar.evaluation.grounding_review import (
        file_digest,
        read_jsonl,
        read_review_csv,
        source_digest,
    )


SCHEMA_VERSION = 1


def _canonical_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _required(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(path)
    return path


def build_fingerprint(adjudication_dir: Path) -> dict[str, Any]:
    """Return a provenance fingerprint for the exact blind human-review package."""
    root = Path(adjudication_dir)
    blind_path = _required(root / "blind-pool.jsonl")
    review_path = _required(root / "grounding-review.csv")
    review_manifest_path = _required(root / "review-manifest.json")
    batch_manifest_path = _required(root / "review-batches-manifest.json")
    protocol_path = _required(root / "REVIEW_PROTOCOL.md")
    batch_dir = _required(root / "review-batches")

    blind_rows = read_jsonl(blind_path)
    review_rows = read_review_csv(review_path)
    review_manifest = _load_json(review_manifest_path)
    batch_manifest = _load_json(batch_manifest_path)

    audit_ids = sorted(str(row.get("audit_id") or "").strip() for row in blind_rows)
    if not audit_ids or any(not value for value in audit_ids):
        raise ValueError("blind grounding pool contains empty audit_id")
    if len(set(audit_ids)) != len(audit_ids):
        raise ValueError("blind grounding pool contains duplicate audit_id")

    source_sha = source_digest(blind_rows)
    manifest_source_sha = str(review_manifest.get("source_sha256") or "")
    if manifest_source_sha != source_sha:
        raise ValueError("review manifest source_sha256 does not match blind pool")
    if int(review_manifest.get("rows") or -1) != len(blind_rows):
        raise ValueError("review manifest row count does not match blind pool")
    if len(review_rows) != len(blind_rows):
        raise ValueError("review CSV row count does not match blind pool")

    batch_paths = sorted(batch_dir.glob("grounding-review-batch-*.csv"))
    expected_batches = int(batch_manifest.get("batches") or 0)
    if len(batch_paths) != expected_batches:
        raise ValueError("batch manifest count does not match batch files")

    batch_files = {
        path.name: file_digest(path)
        for path in batch_paths
    }
    manifest_entries = list(batch_manifest.get("batch_entries") or [])
    manifest_file_hashes = {
        str(entry.get("file") or ""): str(entry.get("file_sha256") or "")
        for entry in manifest_entries
    }
    if batch_files != manifest_file_hashes:
        raise ValueError("batch file hashes do not match batch manifest")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "ejnar_grounding_audit_reproducibility_v1",
        "rows": len(blind_rows),
        "batches": len(batch_paths),
        "audit_ids_sha256": _digest_text("\x1f".join(audit_ids)),
        "blind_source_sha256": source_sha,
        "blind_file_sha256": file_digest(blind_path),
        "review_csv_sha256": file_digest(review_path),
        "review_manifest_sha256": _digest_text(_canonical_json(review_manifest)),
        "batch_manifest_sha256": _digest_text(_canonical_json(batch_manifest)),
        "batch_files_sha256": _digest_text(_canonical_json(batch_files)),
        "protocol_sha256": file_digest(protocol_path),
    }


def compare_fingerprints(runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if len(runs) < 2:
        raise ValueError("at least two fingerprints are required")
    names = list(runs)
    reference_name = names[0]
    reference = runs[reference_name]
    comparisons: list[dict[str, Any]] = []
    differing_fields: set[str] = set()

    for name in names[1:]:
        current = runs[name]
        keys = sorted(set(reference) | set(current))
        differences = {
            key: {reference_name: reference.get(key), name: current.get(key)}
            for key in keys
            if reference.get(key) != current.get(key)
        }
        differing_fields.update(differences)
        comparisons.append(
            {
                "reference": reference_name,
                "candidate": name,
                "exact": not differences,
                "differences": differences,
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "exact_reproducibility": not differing_fields,
        "runs": names,
        "differing_fields": sorted(differing_fields),
        "comparisons": comparisons,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Grounding audit package reproducibility")
    sub = parser.add_subparsers(dest="command", required=True)

    fingerprint = sub.add_parser("fingerprint")
    fingerprint.add_argument("--adjudication-dir", type=Path, required=True)
    fingerprint.add_argument("--output", type=Path, required=True)

    compare = sub.add_parser("compare")
    compare.add_argument("--run", action="append", required=True, help="name=path")
    compare.add_argument("--output", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "fingerprint":
        payload = build_fingerprint(args.adjudication_dir)
        _write_json(args.output, payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    runs: dict[str, dict[str, Any]] = {}
    for item in args.run:
        name, raw_path = item.split("=", 1)
        runs[name] = _load_json(Path(raw_path))
    report = compare_fingerprints(runs)
    _write_json(args.output, report)
    print(
        "Grounding audit reproducibility: "
        f"exact={report['exact_reproducibility']} "
        f"differing_fields={report['differing_fields']}"
    )
    return 0 if report["exact_reproducibility"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Kør Ejnars faktiske retrieval mod det juristvedligeholdte evalueringssæt.

Runneren er bevidst en CLI og påvirker ikke Streamlit-appen. Den genbruger
``shared.py`` og den installerede intent-runtime, men kan køre uden API-nøgler i
``lexical``-tilstand. Resultater skrives som JSONL og kan derefter evalueres af
``metrics.py``.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time
from typing import Any, Iterable
import zipfile

import pandas as pd


EJNAR_DIR = Path(__file__).resolve().parents[1]
ROOT_DIR = EJNAR_DIR.parent
if str(EJNAR_DIR) not in sys.path:
    sys.path.insert(0, str(EJNAR_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from evaluation.metrics import EvaluationCase, evaluate, load_cases  # noqa: E402
from query_intent import classify_query  # noqa: E402


def _strip_html_fallback(value: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(value or "", "html.parser").get_text("\n", strip=True)


def _read_csv(path: Path, strip_html) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    csv.field_size_limit(10_000_000)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            text = strip_html(row.get("Tekst", ""), preserve_headings=True)
            rows.append(
                {
                    "Dato": row.get("Dato", ""),
                    "Titel": row.get("Titel", ""),
                    "Link": row.get("Link", ""),
                    "Tekst": text,
                    "Excerpt": " ".join(text.split())[:500],
                    "Sagsnummer": row.get("Sagsnummer", ""),
                    "Selskab": row.get("Selskab", ""),
                    "Udfald": row.get("Udfald", ""),
                    "Mangeltype": row.get("Mangeltype", ""),
                }
            )
    return rows


def _extract_zipped_csv(zip_path: Path, temp_dir: Path) -> Path | None:
    temp_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not members:
            return None
        member = members[0]
        target = temp_dir / Path(member).name
        if not target.exists() or target.stat().st_mtime < zip_path.stat().st_mtime:
            target.write_bytes(archive.read(member))
        return target


def discover_data_files(data_dir: Path) -> list[Path]:
    """Find Ejnar-CSV'er og udpak zip-varianter deterministisk."""
    files = sorted(data_dir.glob("ejnar_*.csv"))
    temp_dir = data_dir / ".evaluation_tmp"
    for zip_path in sorted(data_dir.glob("ejnar_*.csv.zip")):
        extracted = _extract_zipped_csv(zip_path, temp_dir)
        if extracted and extracted.name not in {item.name for item in files}:
            files.append(extracted)
    return files


def load_corpus(data_dir: Path, shared_module: Any) -> pd.DataFrame:
    files = discover_data_files(data_dir)
    if not files:
        raise FileNotFoundError(f"Ingen ejnar_*.csv eller ejnar_*.csv.zip fundet i {data_dir}")

    strip_html = getattr(shared_module, "strip_html", _strip_html_fallback)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        for row in _read_csv(path, strip_html):
            identity = row.get("Link") or row.get("Sagsnummer") or f"{row.get('Titel')}|{row.get('Dato')}"
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)

    frame = pd.DataFrame(rows)
    frame["Dato"] = pd.to_datetime(frame["Dato"], errors="coerce")
    frame["År"] = frame["Dato"].dt.year.astype("Int64")
    return frame


def build_tfidf(frame: pd.DataFrame, shared_module: Any):
    texts = (
        shared_module.byg_indeks_tekst(title, text)
        for title, text in zip(frame["Titel"].astype(str), frame["Tekst"].astype(str))
    )
    # Deterministisk max_features-udvælgelse: sklearn's egen afhænger af CPU'ens
    # SIMD-sortering ved uafgjorte termhyppigheder (se shared.DeterministicTfidfVectorizer).
    vectorizer = shared_module.DeterministicTfidfVectorizer(
        max_features=60_000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
        tokenizer=shared_module.dansk_tokenizer,
        token_pattern=None,
    )
    matrix = vectorizer.fit_transform(texts)
    return vectorizer, matrix


def _serialise_result(row: dict[str, Any], rank: int) -> dict[str, Any]:
    date = row.get("Dato")
    if isinstance(date, pd.Timestamp):
        date = date.isoformat() if pd.notna(date) else None
    return {
        "rank": rank,
        "Sagsnummer": row.get("Sagsnummer", ""),
        "Titel": row.get("Titel", ""),
        "Dato": date,
        "Link": row.get("Link", ""),
        "Selskab": row.get("Selskab", ""),
        "Udfald": row.get("Udfald", ""),
        "Mangeltype": row.get("Mangeltype", ""),
        "Excerpt": row.get("Excerpt", ""),
        "Tekst": row.get("Tekst", ""),
    }


def retrieve_case(
    case: EvaluationCase,
    frame: pd.DataFrame,
    vectorizer: Any,
    matrix: Any,
    shared_module: Any,
    *,
    top_k: int = 20,
    rerank: bool = False,
) -> dict[str, Any]:
    started = time.perf_counter()
    plan = classify_query(case.query)
    effective_query = shared_module.udvid_query(case.query) if plan.expand_query else case.query

    indices = shared_module.hybrid_retrieval(
        effective_query,
        frame,
        vectorizer,
        matrix,
        embeds=None,
        sub_idx=list(range(len(frame))),
        top_retrieve=max(plan.top_retrieve, top_k),
        top_final=max(plan.top_final, top_k),
    )
    candidates = frame.iloc[indices].to_dict("records") if indices else []
    if rerank and candidates:
        candidates = shared_module.llm_rerank(case.query, candidates, top_n=top_k)
    else:
        candidates = candidates[:top_k]

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    return {
        "question_id": case.question_id,
        "query": case.query,
        "declared_intent": case.intent,
        "detected_intent": plan.intent.value,
        "retrieval_plan": {
            "use_hyde": plan.use_hyde,
            "expand_query": plan.expand_query,
            "use_auto_filters": plan.use_auto_filters,
            "prioritize_lexical": plan.prioritize_lexical,
            "top_retrieve": plan.top_retrieve,
            "top_final": plan.top_final,
        },
        "effective_query": effective_query,
        "latency_ms": elapsed_ms,
        "results": [_serialise_result(row, rank) for rank, row in enumerate(candidates, start=1)],
    }


def run_cases(
    cases: Iterable[EvaluationCase],
    frame: pd.DataFrame,
    vectorizer: Any,
    matrix: Any,
    shared_module: Any,
    *,
    top_k: int = 20,
    rerank: bool = False,
) -> list[dict[str, Any]]:
    return [
        retrieve_case(
            case,
            frame,
            vectorizer,
            matrix,
            shared_module,
            top_k=top_k,
            rerank=rerank,
        )
        for case in cases
    ]


def write_jsonl(path: Path, payloads: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _metrics_input(payloads: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {str(item["question_id"]): list(item.get("results") or []) for item in payloads}


def main() -> int:
    parser = argparse.ArgumentParser(description="Kør Ejnars retrieval-evaluering")
    parser.add_argument(
        "--questions",
        default=str(EJNAR_DIR / "evaluation" / "eval_questions.csv"),
    )
    parser.add_argument("--data-dir", default=str(EJNAR_DIR))
    parser.add_argument(
        "--results",
        default=str(EJNAR_DIR / "evaluation" / "retrieval_results.jsonl"),
    )
    parser.add_argument(
        "--report",
        default=str(EJNAR_DIR / "evaluation" / "retrieval_report.json"),
    )
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Brug Voyage/Haiku-rerank; kræver relevante Streamlit-secrets",
    )
    args = parser.parse_args()

    import shared
    from retrieval_runtime import install_retrieval_runtime

    install_retrieval_runtime(shared)
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
        "documents": len(frame),
        "questions": len(cases),
        "top_k": max(1, args.top_k),
        "rerank": bool(args.rerank),
        "mean_latency_ms": (
            sum(float(item["latency_ms"]) for item in payloads) / len(payloads)
            if payloads else None
        ),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

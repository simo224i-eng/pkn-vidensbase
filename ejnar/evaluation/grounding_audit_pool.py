"""Build a human-review pool for decision-grounding risks in real retrieval results.

The pool juxtaposes the paragraph that best matches the user's question with the compact,
query-specific Board decision-core. It prioritises cases where that decision-core contains
a potentially dispositive ground that is absent from the query-relevant excerpt — exactly
the pattern behind misleading-but-correct citations.

This is a diagnostic/adjudication tool, not an automatic legal classifier. The blind
artifact hides retrieval rank and heuristic scores from the human reviewer; those live in
a separate diagnostics file.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

try:
    from decision_grounding import extract_decision_grounding
    from paragraph_bm25 import ParagraphBM25Index
    from paragraph_retrieval import build_paragraph_records
except ImportError:
    from ejnar.decision_grounding import extract_decision_grounding
    from ejnar.paragraph_bm25 import ParagraphBM25Index
    from ejnar.paragraph_retrieval import build_paragraph_records


_PROTECTED_INTENTS = {"exact_content_search", "specific_decision_search"}
_SPACE_RE = re.compile(r"\s+")
_GROUND_PATTERNS: dict[str, tuple[str, ...]] = {
    "condition_report": ("tilstandsrapport", "anmærket", "anmærkning"),
    "known_condition": ("bekendt med", "kendt forhold", "oplyst om forholdet"),
    "takeover_proof": (
        "ikke godtgjort",
        "ikke er godtgjort",
        "ikke sandsynliggjort",
        "ikke dokumenteret",
        "ved overtagelsen",
        "på overtagelsestidspunktet",
    ),
    "deadline_or_limitation": ("frist", "foræld", "for sent anmeldt"),
    "amount_threshold": ("5.000", "5000", "beløbsgrænse", "bagatelgrænse"),
    "coverage_exclusion": ("undtaget fra dækning", "undtagelse", "ikke omfattet"),
    "maintenance": ("manglende vedligeholdelse", "løbende vedligeholdelse"),
    "wear_or_lifetime": ("slid og ælde", "aldersbetinget slid", "udløbet levetid", "udtjent"),
    "post_takeover_cause": ("efterfølgende", "efter overtagelsen", "kan ikke henføres til"),
    "procedural": ("bevisførelse", "afvises fra nævnsbehandling", "kan ikke afgøres"),
    "legal_compliance_only": ("forskrifter", "lovkrav", "ikke i sig selv"),
}


def _normalise(value: Any) -> str:
    return _SPACE_RE.sub(" ", str(value or "").strip().casefold())


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


def _audit_id(question_id: str, document: dict[str, Any]) -> str:
    identity = (
        str(document.get("Sagsnummer") or "").strip()
        or str(document.get("Link") or "").strip()
        or f"{document.get('Titel', '')}|{document.get('Dato', '')}"
    )
    digest = hashlib.sha1(f"{question_id}\x1f{identity}".encode("utf-8")).hexdigest()[:14]
    return f"ga-{digest}"


def detect_ground_tags(text: str) -> tuple[str, ...]:
    normalised = _normalise(text)
    return tuple(
        name
        for name, phrases in _GROUND_PATTERNS.items()
        if any(_normalise(phrase) in normalised for phrase in phrases)
    )


def best_query_excerpt(query: str, document: dict[str, Any]) -> dict[str, Any]:
    records = build_paragraph_records(document)
    if records and query.strip():
        hits = ParagraphBM25Index(records).search(query, limit=1)
        if hits:
            hit = hits[0]
            return {
                "section_title": hit.record.section_title,
                "text": hit.record.text,
                "matched_terms": list(hit.matched_terms),
                "bm25_score": round(float(hit.score), 6),
            }

    fallback = str(document.get("Excerpt") or "").strip()
    if not fallback:
        text = str(document.get("Tekst") or "")
        fallback = _SPACE_RE.sub(" ", text).strip()[:800]
    return {
        "section_title": "Fallback excerpt",
        "text": fallback,
        "matched_terms": [],
        "bm25_score": 0.0,
    }


def _contrast(excerpt: dict[str, Any], core_text: str, core_section: str) -> dict[str, Any]:
    excerpt_text = str(excerpt.get("text") or "")
    core_tags = detect_ground_tags(core_text)
    excerpt_tags = set(detect_ground_tags(excerpt_text))
    exclusive = tuple(tag for tag in core_tags if tag not in excerpt_tags)
    section_differs = _normalise(excerpt.get("section_title")) != _normalise(core_section)

    score = 2.0 * len(exclusive) + (0.5 if section_differs else 0.0)
    if len(exclusive) >= 2:
        priority = "high"
    elif len(exclusive) == 1:
        priority = "medium"
    else:
        priority = "low"
    return {
        "core_ground_tags": list(core_tags),
        "excerpt_ground_tags": sorted(excerpt_tags),
        "exclusive_ground_tags": list(exclusive),
        "section_differs": section_differs,
        "contrast_score": score,
        "priority": priority,
    }


def build_candidates(
    retrieval_payloads: Iterable[dict[str, Any]],
    *,
    top_results_per_query: int = 10,
    include_protected_intents: bool = False,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for payload in retrieval_payloads:
        question_id = str(payload.get("question_id") or "").strip()
        query = str(payload.get("query") or "").strip()
        intent = str(payload.get("detected_intent") or "").strip()
        if not question_id or not query:
            continue
        if not include_protected_intents and intent in _PROTECTED_INTENTS:
            continue

        for result in list(payload.get("results") or [])[:max(0, top_results_per_query)]:
            document = dict(result)
            audit_id = _audit_id(question_id, document)
            if audit_id in seen:
                continue
            seen.add(audit_id)

            excerpt = best_query_excerpt(query, document)
            grounding = extract_decision_grounding(document, query=query)
            if not excerpt["text"] or not grounding.text:
                continue
            contrast = _contrast(excerpt, grounding.text, grounding.section_title)
            candidates.append({
                "audit_id": audit_id,
                "question_id": question_id,
                "query": query,
                "detected_intent": intent,
                "retrieval_rank": int(result.get("rank") or 0),
                "case_number": str(document.get("Sagsnummer") or ""),
                "title": str(document.get("Titel") or ""),
                "date": document.get("Dato"),
                "link": str(document.get("Link") or ""),
                "query_excerpt_section": excerpt["section_title"],
                "query_excerpt": excerpt["text"],
                "query_matched_terms": excerpt["matched_terms"],
                "query_excerpt_score": excerpt["bm25_score"],
                "decision_core_section": grounding.section_title,
                "decision_core": grounding.text,
                "grounding_used_fallback": grounding.used_fallback,
                **contrast,
            })
    return candidates


def select_pool(
    candidates: Iterable[dict[str, Any]],
    *,
    min_contrast: float = 2.0,
    max_pool: int = 120,
) -> list[dict[str, Any]]:
    eligible = [
        dict(candidate)
        for candidate in candidates
        if float(candidate.get("contrast_score") or 0.0) >= min_contrast
    ]
    eligible.sort(
        key=lambda item: (
            -float(item.get("contrast_score") or 0.0),
            int(item.get("retrieval_rank") or 9999),
            str(item.get("question_id") or ""),
            str(item.get("audit_id") or ""),
        )
    )
    return eligible[:max(0, max_pool)]


def blind_rows(selected: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "audit_id": item["audit_id"],
            "question_id": item["question_id"],
            "query": item["query"],
            "case_number": item["case_number"],
            "title": item["title"],
            "date": item["date"],
            "link": item["link"],
            "query_excerpt_section": item["query_excerpt_section"],
            "query_excerpt": item["query_excerpt"],
            "decision_core_section": item["decision_core_section"],
            "decision_core": item["decision_core"],
            "review_label": "",
            "review_notes": "",
        }
        for item in selected
    ]
    rows.sort(key=lambda item: str(item["audit_id"]))
    return rows


def diagnostics_rows(selected: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(item) for item in selected]


def summary_payload(
    all_candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    retrieval_payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    priority_counts = {"high": 0, "medium": 0, "low": 0}
    tag_counts: dict[str, int] = {}
    for item in selected:
        priority = str(item.get("priority") or "low")
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        for tag in item.get("exclusive_ground_tags") or []:
            tag_counts[str(tag)] = tag_counts.get(str(tag), 0) + 1
    return {
        "schema_version": 1,
        "scope": (
            "Heuristic candidate pool for human review of decision grounding. "
            "Not legal labels and not a gold benchmark."
        ),
        "retrieval_queries": len(retrieval_payloads),
        "candidate_pairs": len(all_candidates),
        "selected_pairs": len(selected),
        "priority_counts": priority_counts,
        "exclusive_ground_tag_counts": dict(sorted(tag_counts.items())),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--blind-output", type=Path, required=True)
    parser.add_argument("--diagnostics-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--top-results-per-query", type=int, default=10)
    parser.add_argument("--max-pool", type=int, default=120)
    parser.add_argument("--min-contrast", type=float, default=2.0)
    parser.add_argument("--include-protected-intents", action="store_true")
    args = parser.parse_args(argv)

    payloads = read_jsonl(args.results)
    candidates = build_candidates(
        payloads,
        top_results_per_query=max(0, args.top_results_per_query),
        include_protected_intents=args.include_protected_intents,
    )
    selected = select_pool(
        candidates,
        min_contrast=float(args.min_contrast),
        max_pool=max(0, args.max_pool),
    )
    blind = blind_rows(selected)
    diagnostics = diagnostics_rows(selected)
    summary = summary_payload(candidates, selected, payloads)

    write_jsonl(args.blind_output, blind)
    write_jsonl(args.diagnostics_output, diagnostics)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

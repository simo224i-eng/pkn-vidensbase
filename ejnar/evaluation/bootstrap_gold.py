"""Bootstrap et auditerbart relevance-facit til Ejnars retrieval-evaluering.

Modulet er bevidst konservativt: klare matches får label 2/1, klare irrelevante
resultater får 0, og tvivlstilfælde får -1 til senere stikprøvekontrol. Hver dom
indeholder confidence, signaler og en kort begrundelse, så facit kan revideres.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable

_TOKEN_RE = re.compile(r"[a-zæøå0-9]+", re.IGNORECASE)
_QUOTE_RE = re.compile(r'["“”„«»](.{3,500}?)["“”„«»]', re.DOTALL)
_CASE_RE = re.compile(r"\b\d{5,6}\b")
_STOPWORDS = {
    "af", "at", "de", "den", "det", "der", "en", "er", "et", "for", "fra",
    "har", "hvad", "hvor", "i", "ikke", "med", "når", "og", "om", "på", "som",
    "til", "var", "ved", "vil", "find", "afgørelser", "kendelse", "kendelser",
    "ankenævnets", "nævnet", "praksis", "sager", "sag",
}


@dataclass(frozen=True)
class Judgment:
    question_id: str
    query: str
    case_number: str
    rank: int
    relevance: int
    confidence: float
    source: str
    signals: tuple[str, ...]
    rationale: str
    title: str = ""
    link: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["signals"] = "|".join(self.signals)
        return payload


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _tokens(value: Any) -> set[str]:
    return {
        match.group(0).lower()
        for match in _TOKEN_RE.finditer(str(value or ""))
        if len(match.group(0)) >= 3 and match.group(0).lower() not in _STOPWORDS
    }


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [item.strip() for item in re.split(r"[|;,]", text) if item.strip()]


def _result_blob(result: dict[str, Any]) -> str:
    return _norm("\n".join(str(result.get(key, "") or "") for key in (
        "Sagsnummer", "Titel", "Excerpt", "Tekst", "Mangeltype", "Udfald"
    )))


def judge_result(case: dict[str, Any], result: dict[str, Any]) -> Judgment:
    query = str(case.get("query") or "")
    question_id = str(case.get("question_id") or case.get("id") or "")
    rank = int(result.get("rank") or 0)
    case_number = str(result.get("Sagsnummer") or "").strip()
    blob = _result_blob(result)
    title_blob = _norm(result.get("Titel"))
    signals: list[str] = []
    score = 0.0

    expected_ids = {item.lower() for item in _as_list(case.get("expected_ids"))}
    if case_number.lower() in expected_ids and case_number:
        score += 10.0
        signals.append("seed_expected_id")

    requested_ids = set(_CASE_RE.findall(query))
    if requested_ids:
        if case_number in requested_ids:
            score += 12.0
            signals.append("requested_case_exact")
        elif any(identifier in blob for identifier in requested_ids):
            score += 7.0
            signals.append("requested_case_in_text")
        else:
            score -= 8.0
            signals.append("requested_case_missing")

    phrases = [_norm(value) for value in _QUOTE_RE.findall(query) if _norm(value)]
    phrase_hit = any(phrase in blob for phrase in phrases)
    if phrases:
        if phrase_hit:
            score += 9.0
            signals.append("exact_phrase")
        else:
            phrase_tokens = set().union(*(_tokens(p) for p in phrases))
            coverage = len(phrase_tokens & _tokens(blob)) / len(phrase_tokens) if phrase_tokens else 0.0
            if coverage >= 0.85:
                score += 4.5
                signals.append("near_phrase")
            elif coverage < 0.45:
                score -= 4.0
                signals.append("phrase_missing")

    expected_terms = set(_as_list(case.get("expected_terms")))
    expected_tokens = set().union(*(_tokens(term) for term in expected_terms)) if expected_terms else set()
    query_tokens = _tokens(query)
    target_tokens = expected_tokens or query_tokens
    blob_tokens = _tokens(blob)
    coverage = len(target_tokens & blob_tokens) / len(target_tokens) if target_tokens else 0.0
    title_coverage = len(target_tokens & _tokens(title_blob)) / len(target_tokens) if target_tokens else 0.0

    if coverage >= 0.75:
        score += 4.0
        signals.append("high_term_coverage")
    elif coverage >= 0.5:
        score += 2.0
        signals.append("medium_term_coverage")
    elif coverage < 0.25:
        score -= 3.0
        signals.append("low_term_coverage")

    if title_coverage >= 0.5:
        score += 2.0
        signals.append("title_match")

    # Rank er kun et svagt prior-signal; det må aldrig skabe relevans alene.
    if 1 <= rank <= 3:
        score += 0.6
    elif rank >= 16:
        score -= 0.2

    if score >= 8.0:
        relevance = 2
        confidence = min(0.99, 0.78 + score / 80.0)
        rationale = "Meget stærkt match mellem forespørgsel og kendelse."
    elif score >= 3.5:
        relevance = 1
        confidence = min(0.95, 0.62 + score / 50.0)
        rationale = "Kendelsen er sandsynligvis relevant, men ikke nødvendigvis central."
    elif score <= -2.5:
        relevance = 0
        confidence = min(0.96, 0.68 + abs(score) / 40.0)
        rationale = "Kendelsen mangler centrale identifikatorer, fraser eller emnesignaler."
    else:
        relevance = -1
        confidence = max(0.35, 0.58 - abs(score) / 30.0)
        rationale = "Tvivlstilfælde; beholdes til senere stikprøvekontrol."

    return Judgment(
        question_id=question_id,
        query=query,
        case_number=case_number,
        rank=rank,
        relevance=relevance,
        confidence=round(confidence, 3),
        source="ai_bootstrap_v1",
        signals=tuple(signals),
        rationale=rationale,
        title=str(result.get("Titel") or ""),
        link=str(result.get("Link") or ""),
    )


def bootstrap_judgments(cases: Iterable[dict[str, Any]], results_by_id: dict[str, list[dict[str, Any]]]) -> list[Judgment]:
    output: list[Judgment] = []
    for case in cases:
        question_id = str(case.get("question_id") or case.get("id") or "")
        for result in results_by_id.get(question_id, []):
            output.append(judge_result(case, result))
    return output


def write_qrels(path: Path, judgments: Iterable[Judgment]) -> None:
    rows = [item.to_dict() for item in judgments]
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0]) if rows else [
        "question_id", "query", "case_number", "rank", "relevance", "confidence",
        "source", "signals", "rationale", "title", "link",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_cases(path: Path) -> list[dict[str, Any]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_results(path: Path) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            payload = json.loads(line)
            output[str(payload["question_id"])] = list(payload.get("results") or [])
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap Ejnar qrels med auditerbare AI-domme")
    parser.add_argument("--questions", required=True)
    parser.add_argument("--results", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    judgments = bootstrap_judgments(_read_cases(Path(args.questions)), _read_results(Path(args.results)))
    write_qrels(Path(args.output), judgments)
    summary = {
        "judgments": len(judgments),
        "highly_relevant": sum(item.relevance == 2 for item in judgments),
        "relevant": sum(item.relevance == 1 for item in judgments),
        "irrelevant": sum(item.relevance == 0 for item in judgments),
        "uncertain": sum(item.relevance == -1 for item in judgments),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

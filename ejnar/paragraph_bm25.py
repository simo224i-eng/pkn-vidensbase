"""Letvægts-BM25 til Ejnars paragraph-level retrieval.

Ingen ekstern søgebibliotek-afhængighed. Modulet indekserer ParagraphRecord-objekter,
returnerer rangerede paragraph-hits og kan aggregere dem til kendelsesniveau.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import re
from typing import Iterable

try:
    from paragraph_retrieval import ParagraphRecord
except ImportError:
    from ejnar.paragraph_retrieval import ParagraphRecord

_TOKEN_RE = re.compile(r"[a-zæøå0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _TOKEN_RE.finditer(text or "")]


@dataclass(frozen=True)
class ParagraphHit:
    record: ParagraphRecord
    score: float
    matched_terms: tuple[str, ...]
    rank: int


@dataclass(frozen=True)
class DecisionHit:
    decision_id: str
    score: float
    paragraph_hits: tuple[ParagraphHit, ...]
    case_number: str
    title: str
    link: str


class ParagraphBM25Index:
    def __init__(
        self,
        records: Iterable[ParagraphRecord],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.records = list(records)
        self.k1 = float(k1)
        self.b = float(b)
        self._tokens = [tokenize(f"{r.section_title} {r.text}") for r in self.records]
        self._term_freqs = [Counter(tokens) for tokens in self._tokens]
        self._doc_lengths = [len(tokens) for tokens in self._tokens]
        self.avg_doc_length = (
            sum(self._doc_lengths) / len(self._doc_lengths) if self._doc_lengths else 0.0
        )
        document_frequency: Counter[str] = Counter()
        for tokens in self._tokens:
            document_frequency.update(set(tokens))
        n = len(self.records)
        self._idf = {
            term: math.log(1.0 + (n - df + 0.5) / (df + 0.5))
            for term, df in document_frequency.items()
        }

    def __len__(self) -> int:
        return len(self.records)

    def search(
        self,
        query: str,
        *,
        limit: int = 30,
        allowed_decision_ids: set[str] | None = None,
    ) -> list[ParagraphHit]:
        query_terms = tokenize(query)
        if not query_terms or not self.records:
            return []
        unique_terms = tuple(dict.fromkeys(query_terms))
        scored: list[tuple[float, int, tuple[str, ...]]] = []
        for idx, record in enumerate(self.records):
            if allowed_decision_ids is not None and record.decision_id not in allowed_decision_ids:
                continue
            tf = self._term_freqs[idx]
            dl = self._doc_lengths[idx]
            score = 0.0
            matched: list[str] = []
            for term in unique_terms:
                frequency = tf.get(term, 0)
                if not frequency:
                    continue
                matched.append(term)
                denominator = frequency + self.k1 * (
                    1.0 - self.b
                    + self.b * (dl / self.avg_doc_length if self.avg_doc_length else 0.0)
                )
                score += self._idf.get(term, 0.0) * (
                    frequency * (self.k1 + 1.0) / denominator
                )
            if score > 0:
                # Et paragraph med flere forskellige query-termer er typisk mere nyttigt
                # end et paragraph med mange gentagelser af ét ord.
                score *= 1.0 + min(0.5, 0.08 * max(0, len(matched) - 1))
                scored.append((score, idx, tuple(matched)))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [
            ParagraphHit(
                record=self.records[idx],
                score=score,
                matched_terms=matched,
                rank=rank,
            )
            for rank, (score, idx, matched) in enumerate(scored[:limit], start=1)
        ]


def aggregate_decisions(
    hits: Iterable[ParagraphHit],
    *,
    limit: int = 20,
    max_paragraphs_per_decision: int = 3,
    rrf_k: int = 20,
) -> list[DecisionHit]:
    """Aggregér paragraphs til kendelser uden at lade lange kendelser dominere."""
    grouped: dict[str, list[ParagraphHit]] = defaultdict(list)
    for hit in hits:
        grouped[hit.record.decision_id].append(hit)

    decision_hits: list[DecisionHit] = []
    for decision_id, paragraph_hits in grouped.items():
        paragraph_hits.sort(key=lambda h: (-h.score, h.rank))
        selected = paragraph_hits[:max_paragraphs_per_decision]
        score = sum(1.0 / (rrf_k + hit.rank) for hit in selected)
        # Bevar en lille del af den absolutte BM25-score som tie-breaker.
        score += 0.001 * sum(hit.score for hit in selected)
        first = selected[0].record
        decision_hits.append(
            DecisionHit(
                decision_id=decision_id,
                score=score,
                paragraph_hits=tuple(selected),
                case_number=first.case_number,
                title=first.title,
                link=first.link,
            )
        )
    decision_hits.sort(key=lambda item: (-item.score, item.decision_id))
    return decision_hits[:limit]


def decision_order_for_dataframe(
    decision_hits: Iterable[DecisionHit],
    df: object,
) -> list[int]:
    """Map kendelses-hits tilbage til DataFrame-positioner via sagsnummer/link."""
    by_case: dict[str, int] = {}
    by_link: dict[str, int] = {}
    for idx in range(len(df)):  # type: ignore[arg-type]
        row = df.iloc[idx]  # type: ignore[attr-defined]
        case_number = str(row.get("Sagsnummer", "") or "").strip().lower()
        link = str(row.get("Link", "") or "").strip().lower()
        if case_number:
            by_case.setdefault(case_number, idx)
        if link:
            by_link.setdefault(link, idx)

    ordered: list[int] = []
    seen: set[int] = set()
    for hit in decision_hits:
        idx = None
        case_key = (hit.case_number or "").strip().lower()
        link_key = (hit.link or "").strip().lower()
        if case_key:
            idx = by_case.get(case_key)
        if idx is None and link_key:
            idx = by_link.get(link_key)
        if idx is not None and idx not in seen:
            seen.add(idx)
            ordered.append(idx)
    return ordered

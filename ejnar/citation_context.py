"""Byg præcis, budgetteret AI-kontekst fra Ejnars paragraph-indeks.

Modulet vælger de mest relevante paragraphs inden for de kendelser, retrieval allerede
har fundet. Det ændrer ikke selve rangeringen og kan derfor indføres separat.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

try:
    from paragraph_bm25 import ParagraphBM25Index, ParagraphHit
    from paragraph_retrieval import citation_payload, decision_identity
except ImportError:
    from ejnar.paragraph_bm25 import ParagraphBM25Index, ParagraphHit
    from ejnar.paragraph_retrieval import citation_payload, decision_identity


@dataclass(frozen=True)
class CitationContext:
    text: str
    citations: tuple[dict[str, Any], ...]
    used_characters: int
    truncated: bool


def _allowed_decision_ids(df: Any, ranked_indices: Iterable[int], max_decisions: int) -> set[str]:
    allowed: set[str] = set()
    for idx in ranked_indices:
        if len(allowed) >= max_decisions:
            break
        try:
            allowed.add(decision_identity(dict(df.iloc[int(idx)])))
        except (IndexError, TypeError, ValueError):
            continue
    return allowed


def _select_diverse_hits(
    hits: Iterable[ParagraphHit],
    *,
    max_paragraphs_per_decision: int,
    max_total: int,
) -> list[ParagraphHit]:
    selected: list[ParagraphHit] = []
    counts: dict[str, int] = {}
    seen_paragraphs: set[str] = set()
    for hit in hits:
        record = hit.record
        if record.paragraph_id in seen_paragraphs:
            continue
        count = counts.get(record.decision_id, 0)
        if count >= max_paragraphs_per_decision:
            continue
        selected.append(hit)
        seen_paragraphs.add(record.paragraph_id)
        counts[record.decision_id] = count + 1
        if len(selected) >= max_total:
            break
    return selected


def build_citation_context(
    query: str,
    df: Any,
    ranked_indices: Iterable[int],
    index: ParagraphBM25Index,
    *,
    max_decisions: int = 8,
    max_paragraphs_per_decision: int = 2,
    max_total_paragraphs: int = 12,
    char_budget: int = 12_000,
) -> CitationContext:
    """Returnér kompakt kontekst med stabile paragraph-citationer.

    Kun paragraphs fra de allerede rangerede kendelser er tilladt. Budgettet måles på
    den tekst, der faktisk sendes videre til modellen.
    """
    if char_budget <= 0:
        return CitationContext("", (), 0, False)

    allowed = _allowed_decision_ids(df, ranked_indices, max_decisions)
    if not allowed:
        return CitationContext("", (), 0, False)

    hits = index.search(
        query,
        limit=max(40, max_total_paragraphs * 5),
        allowed_decision_ids=allowed,
    )
    selected = _select_diverse_hits(
        hits,
        max_paragraphs_per_decision=max_paragraphs_per_decision,
        max_total=max_total_paragraphs,
    )

    blocks: list[str] = []
    citations: list[dict[str, Any]] = []
    used = 0
    truncated = False
    for number, hit in enumerate(selected, start=1):
        payload = citation_payload(hit.record)
        header = (
            f"[KILDE {number}] {payload['case_number'] or payload['title']}"
            f" — {payload['section_title']}"
        )
        block = f"{header}\n{payload['quote']}"
        separator = "\n\n" if blocks else ""
        required = len(separator) + len(block)
        if used + required > char_budget:
            truncated = True
            break
        blocks.append(block)
        citations.append(payload)
        used += required

    return CitationContext(
        text="\n\n".join(blocks),
        citations=tuple(citations),
        used_characters=used,
        truncated=truncated,
    )

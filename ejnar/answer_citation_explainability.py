"""Deterministic mapping from Ejnar answer claims to cited sources.

The purpose is human verification, not automatic legal validation. For each ``[Kilde N]``
reference in an answer, the module extracts the nearby answer sentence/claim and can render
it next to the source's query-specific Board decision core. This makes it possible to
compare what Ejnar used the source to say with what the Board actually decided.
"""
from __future__ import annotations

import html
import re


_SOURCE_RE = re.compile(r"\[Kilde\s+([\d,\s]+)\]", flags=re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(
    r"</?(?:p|div|li|ul|ol|h[1-6]|blockquote|br)\b[^>]*>",
    flags=re.IGNORECASE,
)
_SENTENCE_BOUNDARY_RE = re.compile(r"[.!?](?:[\"'»”)]*)\s+")


def _plain_answer(text: str) -> str:
    value = str(text or "")
    # Preserve structural boundaries before removing arbitrary HTML.
    value = _BLOCK_TAG_RE.sub("\n", value)
    value = _TAG_RE.sub("", value)
    value = html.unescape(value)
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def _claim_window(text: str, start: int, end: int, *, max_chars: int = 420) -> str:
    """Return the sentence-like window containing a source reference."""
    paragraph_start = text.rfind("\n", 0, start) + 1
    paragraph_end = text.find("\n", end)
    if paragraph_end < 0:
        paragraph_end = len(text)

    paragraph = text[paragraph_start:paragraph_end].strip()
    local_start = max(0, start - paragraph_start)
    local_end = max(local_start, end - paragraph_start)

    # Prefer a single sentence around the citation. We find the last completed sentence
    # before the reference and the first completed sentence ending after it. If the
    # answer uses bullets without punctuation, the whole (bounded) bullet is retained.
    sentence_start = 0
    for match in _SENTENCE_BOUNDARY_RE.finditer(paragraph, 0, local_start):
        sentence_start = match.end()

    sentence_end = len(paragraph)
    for match in _SENTENCE_BOUNDARY_RE.finditer(paragraph, local_end):
        sentence_end = match.start() + 1
        break

    claim = paragraph[sentence_start:sentence_end].strip(" -•\t")
    if not claim:
        claim = paragraph
    claim = re.sub(r"\s+", " ", claim).strip()

    if len(claim) <= max_chars:
        return claim

    # Keep the citation and the words immediately before it when a sentence is very long.
    ref_offset = max(0, local_start - sentence_start)
    half = max_chars // 2
    left = max(0, ref_offset - half)
    right = min(len(claim), left + max_chars)
    left = max(0, right - max_chars)
    clipped = claim[left:right].strip()
    if left > 0:
        clipped = "…" + clipped
    if right < len(claim):
        clipped += "…"
    return clipped


def extract_source_claims(
    answer: str,
    *,
    source_count: int | None = None,
    max_claims_per_source: int = 4,
) -> dict[int, tuple[str, ...]]:
    """Map 1-based source numbers to answer claims that cite them.

    No attempt is made to decide whether a claim is legally supported. Invalid/out-of-range
    source numbers are ignored when ``source_count`` is supplied.
    """
    text = _plain_answer(answer)
    if not text or max_claims_per_source <= 0:
        return {}

    claims: dict[int, list[str]] = {}
    for match in _SOURCE_RE.finditer(text):
        numbers = [int(value) for value in re.findall(r"\d+", match.group(1))]
        if not numbers:
            continue
        claim = _claim_window(text, match.start(), match.end())
        if not claim:
            continue
        for number in numbers:
            if number < 1:
                continue
            if source_count is not None and number > source_count:
                continue
            bucket = claims.setdefault(number, [])
            if claim not in bucket and len(bucket) < max_claims_per_source:
                bucket.append(claim)

    return {number: tuple(values) for number, values in sorted(claims.items())}


def claims_for_source(
    answer: str,
    source_number: int,
    *,
    source_count: int | None = None,
) -> tuple[str, ...]:
    return extract_source_claims(answer, source_count=source_count).get(
        int(source_number), ()
    )


def render_source_claims_html(
    answer: str,
    source_number: int,
    *,
    source_count: int | None = None,
) -> str:
    """Render cited answer claims as neutral, escaped UI evidence."""
    claims = claims_for_source(
        answer,
        source_number,
        source_count=source_count,
    )
    if not claims:
        return ""

    items = "".join(
        '<div style="margin:5px 0;padding:7px 9px;background:#f8fafc;'
        'border-left:3px solid #94a3b8;border-radius:3px;font-size:11.5px;'
        f'line-height:1.5;color:#334155;">{html.escape(claim)}</div>'
        for claim in claims
    )
    return (
        '<div style="margin:8px 0 9px;">'
        '<div style="font-size:9.5px;font-weight:700;color:#64748b;text-transform:uppercase;'
        'letter-spacing:.8px;margin-bottom:4px;">Brugt i svaret til</div>'
        f'{items}'
        '<div style="font-size:9.5px;color:#94a3b8;margin-top:5px;">'
        'Viser kun hvor Ejnar citerede kilden; det er ikke en automatisk vurdering af, '
        'om påstanden er juridisk understøttet.'
        '</div></div>'
    )

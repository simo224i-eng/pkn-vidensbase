"""Ground Ejnar answers in what the Board actually decided.

Retrieval can legitimately surface a highly relevant sentence from a decision even when
that decision was ultimately resolved on a different ground. This module extracts a
compact decision-core so answer generation can distinguish a useful passage from the
Board's dispositive reasoning.

For multi-issue decisions, the Board section is selected first and paragraph selection is
then made query-aware inside that section. This prevents reasoning about another issue in
the same decision from being presented as the basis for the user's question.

The module is deterministic and does not decide coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Iterable

try:
    from paragraph_retrieval import split_sections
except ImportError:  # package import in tests/tools
    from ejnar.paragraph_retrieval import split_sections


@dataclass(frozen=True)
class DecisionGrounding:
    section_title: str
    text: str
    used_fallback: bool
    paragraph_count: int


_DECISION_SECTION_PHRASES = (
    "nævnets bemærkninger og afgørelse",
    "nævnets bemærkninger",
    "nævnets vurdering",
    "nævnets afgørelse",
    "ankenævnets bemærkninger",
    "ankenævnets vurdering",
    "ankenævnets afgørelse",
    "nævnet udtaler",
    "afgørelse",
)
_PARTY_SECTION_PHRASES = (
    "klagerens",
    "klageren",
    "selskabets",
    "selskabet",
    "sagens oplysninger",
    "parternes",
)
_DECISION_SIGNALS = (
    "nævnet finder",
    "nævnet bemærker",
    "nævnet lægger",
    "nævnet udtaler",
    "nævnet kan",
    "nævnet har",
    "på den baggrund",
    "derfor",
    "ikke godtgjort",
    "ikke sandsynliggjort",
    "får ikke medhold",
    "får medhold",
    "selskabet skal",
    "selskabet er berettiget",
    "tilstandsrapport",
    "anmærk",
    "bekendt med",
    "kendt forhold",
    "foræld",
    "frist",
)
_CONCLUSION_SIGNALS = (
    "får ikke medhold",
    "får medhold",
    "kan derfor ikke kritisere",
    "kan ikke kritisere",
    "selskabet skal",
    "selskabet er berettiget",
    "ikke grundlag for at kritisere",
    "kan ikke føre til andet resultat",
    "kan ikke i sig selv føre til et krav",
    "afvises fra nævnsbehandling",
    # Materielle konklusioner kan afslutte et enkelt forhold uden den mere formelle
    # 'kan ikke kritisere'-formulering. De skal stoppe den lokale vandring, ellers kan
    # næste anmeldte forhold i samme nævnsafsnit blive blandet ind i afgørelseskernen.
    "udgør ikke skade",
    "udgør ikke en skade",
    "udgør skade",
    "udgør en skade",
    "ikke omfattet af forsikringen",
    "er omfattet af forsikringen",
    "anerkende dækning",
)
# Older decisions are not always structurally marked up. A generic "Kendelse" or
# "Afgørelse" section may contain policy wording followed later by the Board's own
# reasoning. Strong inline markers let us trim that preamble without guessing from a
# mere occurrence of the word "nævnet".
_BOARD_INLINE_MARKERS = (
    "nævnet udtaler:",
    "nævnet udtaler",
    "ankenævnet udtaler:",
    "ankenævnet udtaler",
    "nævnet finder",
    "ankenævnet finder",
    "nævnet bemærker",
    "ankenævnet bemærker",
    "nævnet lægger",
    "ankenævnet lægger",
    "efter en gennemgang af sagen finder nævnet",
    "efter en samlet vurdering finder nævnet",
)
_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-zæøå0-9]+", flags=re.IGNORECASE)
# These terms are useful for routing a legal query but do not distinguish one issue from
# another inside a multi-issue Board section. Excluding them makes terms such as
# "ventilation", "tagrum", "vinduer" and "bjælke" dominate local grounding.
_QUERY_STOPWORDS = {
    "af", "afgørelse", "afgørelser", "afvist", "at", "de", "den", "der", "det",
    "dække", "dækket", "dækning", "dækningsberettigende", "ejerskifteforsikring",
    "en", "er", "et", "find", "for", "forhold", "forholdet", "fra", "har", "hvad",
    "hvilke", "hvilken", "hvordan", "hvornår", "i", "ikke", "imod", "kan", "klager",
    "med", "medhold", "nævnet", "om", "og", "på", "praksis", "sag", "sager", "skade",
    "skader", "som", "taler", "til", "ved", "eller", "typisk", "resultat", "resultater",
}
_QUERY_SUFFIXES = (
    "ernes", "ende", "erne", "ene", "ets", "ers", "er", "en", "et", "es", "e", "s",
)


def _normalise(value: str) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip().casefold())


def _has_explicit_board_heading(title: str) -> bool:
    normalised = _normalise(title)
    return "nævn" in normalised or "ankenævn" in normalised


def _section_score(title: str, position: int, total: int) -> float:
    """Score explicit Board/decision headings; position is only a tie-breaker."""
    normalised = _normalise(title)
    if any(phrase in normalised for phrase in _PARTY_SECTION_PHRASES):
        return -100.0

    score = 0.0
    for rank, phrase in enumerate(_DECISION_SECTION_PHRASES):
        if phrase in normalised:
            score = max(score, 100.0 - rank * 7.0)
    if "nævn" in normalised:
        score += 25.0
    if "bemærk" in normalised or "vurder" in normalised:
        score += 15.0

    # Position may choose between recognised decision sections, but may never turn an
    # unknown heading into a recognised decision section.
    if score > 0 and total > 1:
        score += 4.0 * (position / (total - 1))
    return score


def _paragraph_score(text: str, position: int, total: int) -> float:
    normalised = _normalise(text)
    score = sum(4.0 for phrase in _DECISION_SIGNALS if phrase in normalised)
    if "nævnet" in normalised:
        score += 5.0
    if total > 1:
        score += 2.0 * (position / (total - 1))
    return score


def _inline_board_start(paragraph: str) -> int | None:
    """Locate the first strong Board-reasoning marker in a paragraph."""
    if not paragraph:
        return None
    best: int | None = None
    for marker in _BOARD_INLINE_MARKERS:
        tokens = [re.escape(token) for token in marker.split()]
        pattern = r"\s+".join(tokens)
        match = re.search(pattern, paragraph, flags=re.IGNORECASE)
        if match is not None and (best is None or match.start() < best):
            best = match.start()
    return best


def _trim_to_board_reasoning(paragraphs: Iterable[str]) -> list[str]:
    """Drop policy/party preamble before an inline Board reasoning marker."""
    cleaned = [re.sub(r"\s+", " ", str(paragraph or "")).strip() for paragraph in paragraphs]
    cleaned = [paragraph for paragraph in cleaned if paragraph]
    for index, paragraph in enumerate(cleaned):
        start = _inline_board_start(paragraph)
        if start is None:
            continue
        trimmed_first = paragraph[start:].strip()
        output = ([trimmed_first] if trimmed_first else []) + cleaned[index + 1 :]
        return output or cleaned
    return cleaned


def _clean_paragraphs(paragraphs: Iterable[str]) -> list[str]:
    return [
        value
        for value in (
            re.sub(r"\s+", " ", str(paragraph or "")).strip()
            for paragraph in paragraphs
        )
        if value
    ]


def _stem_query_token(token: str) -> str:
    token = token.casefold()
    for suffix in _QUERY_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 4:
            return token[: -len(suffix)]
    return token


def _query_terms(query: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(query or ""):
        token = match.group(0).casefold()
        if len(token) < 3 or token in _QUERY_STOPWORDS or token.isdigit():
            continue
        stem = _stem_query_token(token)
        if len(stem) < 3 or stem in seen:
            continue
        seen.add(stem)
        terms.append(stem)
    return tuple(terms)


def _paragraph_stems(text: str) -> set[str]:
    return {
        _stem_query_token(match.group(0).casefold())
        for match in _TOKEN_RE.finditer(text or "")
        if len(match.group(0)) >= 3
    }


def _query_scores(paragraphs: list[str], query: str) -> list[float]:
    """Return discriminative lexical scores within the selected Board section.

    IDF is calculated only across paragraphs in this decision. A term occurring in one
    paragraph therefore contributes more than a generic term repeated through the whole
    Board section. This is a local selector, not a new retrieval system.
    """
    terms = _query_terms(query)
    if not terms or not paragraphs:
        return [0.0] * len(paragraphs)

    stems = [_paragraph_stems(paragraph) for paragraph in paragraphs]
    document_frequency = {
        term: sum(term in paragraph_stems for paragraph_stems in stems)
        for term in terms
    }
    scores: list[float] = []
    for paragraph_stems in stems:
        matched = [term for term in terms if term in paragraph_stems]
        if not matched:
            scores.append(0.0)
            continue
        score = sum(
            1.0 + math.log((len(paragraphs) + 1.0) / (document_frequency[term] + 1.0))
            for term in matched
        )
        # Coverage of multiple distinct issue terms is more useful than repeated use of
        # one token. Keep the boost bounded so Board-reasoning signals remain relevant.
        score *= 1.0 + min(0.6, 0.15 * max(0, len(matched) - 1))
        scores.append(score)
    return scores


def _has_conclusion_signal(text: str) -> bool:
    normalised = _normalise(text)
    return any(signal in normalised for signal in _CONCLUSION_SIGNALS)


def _query_local_indices(
    cleaned: list[str],
    query: str,
    *,
    max_paragraphs: int,
) -> list[int]:
    """Select a local issue window inside a multi-issue Board section.

    The strongest query paragraph is the anchor. We then walk forward because the Board's
    actual reason/result commonly follows the issue-specific paragraph. We stop once a
    conclusion signal is reached. Additional query-matching paragraphs can fill remaining
    slots, but unrelated global concluding paragraphs are not pulled in.
    """
    if max_paragraphs <= 0:
        return []
    query_scores = _query_scores(cleaned, query)
    if not query_scores or max(query_scores, default=0.0) <= 0:
        return []

    decision_scores = [
        _paragraph_score(text, idx, len(cleaned))
        for idx, text in enumerate(cleaned)
    ]
    anchor = max(
        range(len(cleaned)),
        key=lambda idx: (query_scores[idx], decision_scores[idx], -idx),
    )

    selected: list[int] = [anchor]
    if not _has_conclusion_signal(cleaned[anchor]):
        for idx in range(anchor + 1, min(len(cleaned), anchor + max_paragraphs)):
            selected.append(idx)
            if _has_conclusion_signal(cleaned[idx]):
                break
            if len(selected) >= max_paragraphs:
                break

    if len(selected) < max_paragraphs:
        additional = sorted(
            (
                (query_scores[idx], decision_scores[idx], idx)
                for idx in range(len(cleaned))
                if query_scores[idx] > 0 and idx not in selected
            ),
            key=lambda item: (-item[0], -item[1], item[2]),
        )
        for _, _, idx in additional:
            selected.append(idx)
            if len(selected) >= max_paragraphs:
                break

    # Previous paragraph can contain the issue introduction, but only include it when it
    # shares a query term; this avoids pulling the prior issue into the window.
    previous = anchor - 1
    if (
        len(selected) < max_paragraphs
        and previous >= 0
        and query_scores[previous] > 0
        and previous not in selected
    ):
        selected.append(previous)

    return sorted(set(selected))[:max_paragraphs]


def _default_indices(cleaned: list[str], *, max_paragraphs: int) -> list[int]:
    if not cleaned or max_paragraphs <= 0:
        return []
    total = len(cleaned)
    scored = [(_paragraph_score(text, idx, total), idx) for idx, text in enumerate(cleaned)]
    _, best_idx = max(scored, key=lambda item: (item[0], item[1]))

    desired = {best_idx, total - 1}
    if best_idx > 0:
        desired.add(best_idx - 1)
    if best_idx + 1 < total:
        desired.add(best_idx + 1)
    if total <= max_paragraphs:
        return list(range(total))

    ranked = [best_idx, best_idx + 1, total - 1, best_idx - 1]
    output: list[int] = []
    for idx in ranked:
        if 0 <= idx < total and idx not in output:
            output.append(idx)
        if len(output) >= max_paragraphs:
            break
    return sorted(output)


def _render_selected(
    cleaned: list[str],
    indices: Iterable[int],
    *,
    max_chars: int,
) -> tuple[str, int]:
    selected: list[str] = []
    used = 0
    for idx in indices:
        paragraph = cleaned[idx]
        separator = 2 if selected else 0
        remaining = max_chars - used - separator
        if remaining <= 0:
            break
        if len(paragraph) > remaining:
            if remaining >= 180:
                selected.append(paragraph[: remaining - 1].rstrip() + "…")
            break
        selected.append(paragraph)
        used += separator + len(paragraph)
    return "\n\n".join(selected), len(selected)


def _choose_paragraphs(
    paragraphs: Iterable[str],
    *,
    max_paragraphs: int,
    max_chars: int,
    trim_inline_board_preamble: bool = False,
    query: str = "",
) -> tuple[str, int]:
    cleaned = (
        _trim_to_board_reasoning(paragraphs)
        if trim_inline_board_preamble
        else _clean_paragraphs(paragraphs)
    )
    if not cleaned or max_paragraphs <= 0 or max_chars <= 0:
        return "", 0

    indices = _query_local_indices(cleaned, query, max_paragraphs=max_paragraphs)
    if not indices:
        indices = _default_indices(cleaned, max_paragraphs=max_paragraphs)
    return _render_selected(cleaned, indices, max_chars=max_chars)


def extract_decision_grounding(
    document: dict[str, Any],
    *,
    query: str = "",
    max_chars: int = 1800,
    max_paragraphs: int = 4,
) -> DecisionGrounding:
    """Extract a compact, optionally query-specific representation of Board reasoning.

    Formal Board/decision sections are selected before query relevance is considered.
    Query-aware selection happens only *within* that Board section, so party arguments or
    factual sections cannot replace the Board's own reasoning. When a decision contains
    several issues in the same Board section, the selected core stays around the issue
    matching the user's question and follows it forward to its conclusion/other ground.
    """
    text = str(document.get("Tekst") or document.get("text") or "")
    sections = split_sections(text)
    if not sections:
        return DecisionGrounding("", "", True, 0)

    scored = [
        (_section_score(title, idx, len(sections)), idx, title, paragraphs)
        for idx, (title, paragraphs) in enumerate(sections)
    ]
    best = max(scored, key=lambda item: (item[0], item[1]))
    used_fallback = best[0] <= 0
    if used_fallback:
        _, _, title, paragraphs = scored[-1]
    else:
        _, _, title, paragraphs = best

    core, count = _choose_paragraphs(
        paragraphs,
        max_paragraphs=max_paragraphs,
        max_chars=max_chars,
        trim_inline_board_preamble=not _has_explicit_board_heading(str(title or "")),
        query=query,
    )
    return DecisionGrounding(
        section_title=str(title or "Kendelse"),
        text=core,
        used_fallback=used_fallback,
        paragraph_count=count,
    )


def build_decision_grounding_context(
    documents: list[dict[str, Any]],
    *,
    query: str = "",
    max_documents: int = 6,
    per_document_chars: int = 1400,
    char_budget: int = 7000,
) -> str:
    """Build numbered decision-core blocks aligned with Ejnar's [Kilde X] register."""
    if not documents or max_documents <= 0 or char_budget <= 0:
        return ""

    intro = (
        "AFGØRELSESKERNE — kontrol af hvad kendelsen faktisk blev afgjort på. "
        "Et spørgsmålsrelevant citat må ikke behandles som en generel praksisregel, "
        "hvis afgørelseskernen viser, at udfaldet hvilede på et andet grundlag."
    )
    blocks: list[str] = [intro]
    used = len(intro)

    for source_number, document in enumerate(documents[:max_documents], start=1):
        grounding = extract_decision_grounding(
            document,
            query=query,
            max_chars=per_document_chars,
        )
        if not grounding.text:
            continue
        case_number = str(document.get("Sagsnummer") or "").strip()
        title = str(document.get("Titel") or "").strip()
        label = case_number or title or f"Kilde {source_number}"
        block = (
            f"[AFGØRELSESKERNE Kilde {source_number}] {label} — "
            f"{grounding.section_title}\n{grounding.text}"
        )
        required = 2 + len(block)
        if used + required > char_budget:
            break
        blocks.append(block)
        used += required

    return "\n\n".join(blocks) if len(blocks) > 1 else ""


_POLICY_MARKER = "AFGØRELSESGRUND (OBLIGATORISK)"
_GROUNDING_POLICY = (
    "\n\nAFGØRELSESGRUND (OBLIGATORISK):\n"
    "9. Før du bruger en kendelse som støtte for en juridisk pointe, fastslå hvad "
    "nævnet faktisk lagde til grund for udfaldet.\n"
    "10. Et citat, teknisk udsagn eller relevant delproblem må IKKE fremstilles som "
    "nævnets generelle praksis for spørgsmålet, hvis kendelsen reelt blev afgjort på "
    "et andet grundlag, fx tilstandsrapport/kendt forhold, bevis, frist, undtagelse "
    "eller beløbsgrænse. Oplys i stedet det afgørende grundlag eksplicit.\n"
    "11. Skeln mellem udsagn fra klageren, selskabet, en sagkyndig og nævnets egen "
    "begrundelse. Skriv kun 'Nævnet udtalte', når udsagnet faktisk er nævnets.\n"
    "12. Hvis en kendelse kun belyser spørgsmålet indirekte, beskriv den som analogi "
    "eller støttepunkt — ikke som direkte praksis for spørgsmålet."
)


def inject_grounding_policy(prompt: Any) -> Any:
    """Add decision-basis safeguards to Ejnar answer prompts without mutating input."""
    if not isinstance(prompt, list):
        return prompt

    copied: list[Any] = []
    changed = False
    for block in prompt:
        if not isinstance(block, dict):
            copied.append(block)
            continue
        new_block = dict(block)
        text = new_block.get("text")
        if (
            not changed
            and isinstance(text, str)
            and "REGLER:" in text
            and "Du er en juridisk assistent" in text
        ):
            if _POLICY_MARKER not in text:
                new_block["text"] = text + _GROUNDING_POLICY
            changed = True
        copied.append(new_block)
    return copied

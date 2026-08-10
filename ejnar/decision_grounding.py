"""Ground Ejnar answers in what the Board actually decided.

Retrieval can legitimately surface a highly relevant sentence from a decision even when
that decision was ultimately resolved on a different ground. This module extracts a
compact decision-core so answer generation can distinguish a useful passage from the
Board's dispositive reasoning.

The module is deterministic and does not decide coverage.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def _normalise(value: str) -> str:
    return _SPACE_RE.sub(" ", (value or "").strip().casefold())


def _has_explicit_board_heading(title: str) -> bool:
    normalised = _normalise(title)
    return "nævn" in normalised or "ankenævn" in normalised


def _section_score(title: str, position: int, total: int) -> float:
    """Score explicit Board/decision headings; position is only a tie-breaker.

    An unrecognised late heading must not become a false positive merely because it is
    close to the end of the decision. Unknown headings therefore stay at score zero and
    are handled by the explicit final-section fallback in ``extract_decision_grounding``.
    """
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
    """Drop policy/party preamble before an inline Board reasoning marker.

    This is deliberately conservative: trimming occurs only when a strong marker is
    found. If none is found, the section is returned unchanged.
    """
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


def _choose_paragraphs(
    paragraphs: Iterable[str],
    *,
    max_paragraphs: int,
    max_chars: int,
    trim_inline_board_preamble: bool = False,
) -> tuple[str, int]:
    cleaned = (
        _trim_to_board_reasoning(paragraphs)
        if trim_inline_board_preamble
        else _clean_paragraphs(paragraphs)
    )
    if not cleaned or max_paragraphs <= 0 or max_chars <= 0:
        return "", 0

    total = len(cleaned)
    scored = [(_paragraph_score(text, idx, total), idx) for idx, text in enumerate(cleaned)]
    _, best_idx = max(scored, key=lambda item: (item[0], item[1]))

    desired = {best_idx, total - 1}
    if best_idx > 0:
        desired.add(best_idx - 1)
    if best_idx + 1 < total:
        desired.add(best_idx + 1)

    if total <= max_paragraphs:
        ordered = list(range(total))
    else:
        ordered = sorted(desired)
        if len(ordered) > max_paragraphs:
            ordered = ordered[-max_paragraphs:]

    selected: list[str] = []
    used = 0
    for idx in ordered:
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


def extract_decision_grounding(
    document: dict[str, Any],
    *,
    max_chars: int = 1800,
    max_paragraphs: int = 4,
) -> DecisionGrounding:
    """Extract a compact representation of the Board's dispositive reasoning.

    Formal Board/decision sections are preferred. If the source has no recognisable
    decision heading, the final section is used as a conservative fallback. Within a
    generic/legacy decision section, policy text before a strong inline Board marker is
    trimmed away. Explicit Board-labelled sections are preserved verbatim before normal
    paragraph selection so their introductory reasoning is not lost.
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
        grounding = extract_decision_grounding(document, max_chars=per_document_chars)
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

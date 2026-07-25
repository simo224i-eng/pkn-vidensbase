"""Paragraph- og citation-level retrieval for Ejnar.

Modulet er uafhængigt af Streamlit og embeddings. Det omdanner en kendelse til en
stabil struktur: kendelse -> sektion -> paragraph. Strukturen kan senere bruges
til BM25/embedding-indekser og præcise citater uden at ændre den eksisterende
produktionspipeline endnu.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re
from typing import Any, Iterable


_HEADING_RE = re.compile(r"^(?:#{1,6}\s+|[A-ZÆØÅ][A-ZÆØÅ0-9 /().,:;-]{3,})$")
_SENTENCE_BREAK_RE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÆØÅ0-9])")


@dataclass(frozen=True)
class ParagraphRecord:
    decision_id: str
    section_id: str
    paragraph_id: str
    section_title: str
    paragraph_index: int
    text: str
    char_start: int
    char_end: int
    title: str = ""
    date: str = ""
    link: str = ""
    case_number: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalise_space(value: str) -> str:
    return re.sub(r"[ \t]+", " ", (value or "")).strip()


def _slug(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zæøå0-9]+", "-", (value or "").lower()).strip("-")
    return cleaned[:60] or fallback


def _stable_id(*parts: str, prefix: str) -> str:
    digest = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def decision_identity(document: dict[str, Any]) -> str:
    """Returnér et stabilt kendelses-ID uden at være afhængig af rækkefølge."""
    for key in ("Sagsnummer", "sagsnummer", "case_number", "Link", "link", "url"):
        value = _normalise_space(str(document.get(key) or ""))
        if value:
            return _stable_id(value.lower(), prefix="dec")
    title = _normalise_space(str(document.get("Titel") or document.get("title") or ""))
    date = _normalise_space(str(document.get("Dato") or document.get("date") or ""))
    return _stable_id(title.lower(), date.lower(), prefix="dec")


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return True
    if len(stripped) > 120:
        return False
    return bool(_HEADING_RE.match(stripped))


def _clean_heading(line: str) -> str:
    return _normalise_space(re.sub(r"^#{1,6}\s*", "", line))


def _split_long_paragraph(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = _SENTENCE_BREAK_RE.split(text)
    output: list[str] = []
    current: list[str] = []
    current_len = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        projected = current_len + (1 if current else 0) + len(sentence)
        if current and projected > max_chars:
            output.append(" ".join(current))
            current = [sentence]
            current_len = len(sentence)
        else:
            current.append(sentence)
            current_len = projected
    if current:
        output.append(" ".join(current))
    return output or [text]


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    """Split tekst i sektioner og rå paragraphs med konservativ heading-detektion."""
    current_title = "Kendelse"
    current_lines: list[str] = []
    sections: list[tuple[str, list[str]]] = []

    def flush() -> None:
        nonlocal current_lines
        blob = "\n".join(current_lines).strip()
        if blob:
            paragraphs = [
                _normalise_space(part.replace("\n", " "))
                for part in re.split(r"\n\s*\n+", blob)
                if _normalise_space(part)
            ]
            if paragraphs:
                sections.append((current_title, paragraphs))
        current_lines = []

    for raw_line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if _is_heading(line):
            flush()
            current_title = _clean_heading(line)
        else:
            current_lines.append(raw_line)
    flush()
    return sections


def build_paragraph_records(
    document: dict[str, Any],
    *,
    max_chars: int = 1800,
    min_chars: int = 20,
) -> list[ParagraphRecord]:
    """Omdan én kendelse til stabile paragraph-records."""
    text = str(document.get("Tekst") or document.get("text") or "")
    decision_id = decision_identity(document)
    title = str(document.get("Titel") or document.get("title") or "")
    date = str(document.get("Dato") or document.get("date") or "")
    link = str(document.get("Link") or document.get("link") or document.get("url") or "")
    case_number = str(document.get("Sagsnummer") or document.get("sagsnummer") or "")

    records: list[ParagraphRecord] = []
    cursor = 0
    for section_index, (section_title, raw_paragraphs) in enumerate(split_sections(text)):
        section_id = _stable_id(
            decision_id,
            str(section_index),
            _slug(section_title, "sektion"),
            prefix="sec",
        )
        paragraph_index = 0
        for raw in raw_paragraphs:
            for paragraph in _split_long_paragraph(raw, max_chars=max_chars):
                paragraph = _normalise_space(paragraph)
                if len(paragraph) < min_chars:
                    continue
                found_at = text.find(paragraph, cursor)
                if found_at < 0:
                    found_at = text.find(paragraph)
                if found_at < 0:
                    found_at = cursor
                char_end = found_at + len(paragraph)
                paragraph_id = _stable_id(
                    decision_id,
                    section_id,
                    str(paragraph_index),
                    paragraph,
                    prefix="par",
                )
                records.append(
                    ParagraphRecord(
                        decision_id=decision_id,
                        section_id=section_id,
                        paragraph_id=paragraph_id,
                        section_title=section_title,
                        paragraph_index=paragraph_index,
                        text=paragraph,
                        char_start=found_at,
                        char_end=char_end,
                        title=title,
                        date=date,
                        link=link,
                        case_number=case_number,
                    )
                )
                paragraph_index += 1
                cursor = max(cursor, char_end)
    return records


def build_corpus(documents: Iterable[dict[str, Any]], **kwargs: Any) -> list[ParagraphRecord]:
    records: list[ParagraphRecord] = []
    for document in documents:
        records.extend(build_paragraph_records(document, **kwargs))
    return records


def exact_phrase_search(
    query: str,
    records: Iterable[ParagraphRecord],
    *,
    limit: int = 20,
) -> list[ParagraphRecord]:
    """Find ordrette fraser i paragraphs, længste/mest præcise først."""
    phrases = re.findall(r'["“”„«»](.{3,500}?)["“”„«»]', query or "", flags=re.DOTALL)
    needles = [_normalise_space(value).lower() for value in phrases if _normalise_space(value)]
    if not needles:
        needles = [_normalise_space(query).lower()] if _normalise_space(query) else []
    if not needles:
        return []

    scored: list[tuple[int, int, ParagraphRecord]] = []
    for record in records:
        haystack = _normalise_space(record.text).lower()
        matches = [needle for needle in needles if needle in haystack]
        if not matches:
            continue
        longest = max(len(match) for match in matches)
        scored.append((len(matches), longest, record))
    scored.sort(key=lambda item: (-item[0], -item[1], len(item[2].text)))
    return [record for _, _, record in scored[:limit]]


def citation_payload(record: ParagraphRecord) -> dict[str, Any]:
    """Kompakt payload til LLM-kontekst og verificerbare kildehenvisninger."""
    return {
        "decision_id": record.decision_id,
        "section_id": record.section_id,
        "paragraph_id": record.paragraph_id,
        "case_number": record.case_number,
        "title": record.title,
        "date": record.date,
        "link": record.link,
        "section_title": record.section_title,
        "quote": record.text,
        "char_start": record.char_start,
        "char_end": record.char_end,
    }

"""Visible source-level explainability for Ejnar's AI answers.

The user should be able to inspect the Board reasoning Ejnar used without confusing a
query-relevant quotation with the dispositive ground of the case. This module exposes the
same query-aware decision-grounding extractor used at answer time as a small, escaped UI
card. It intentionally does *not* classify a decision as direct/indirect practice.
"""
from __future__ import annotations

from dataclasses import dataclass
import html
from typing import Any

try:
    from decision_grounding import extract_decision_grounding
except ImportError:
    from ejnar.decision_grounding import extract_decision_grounding


@dataclass(frozen=True)
class SourceDecisionCore:
    section_title: str
    text: str
    used_fallback: bool
    paragraph_count: int


def source_decision_core(
    document: dict[str, Any],
    query: str,
    *,
    max_chars: int = 1500,
) -> SourceDecisionCore | None:
    """Return the query-specific Board core used to sanity-check a source."""
    try:
        grounding = extract_decision_grounding(
            document,
            query=str(query or ""),
            max_chars=max(300, int(max_chars)),
            max_paragraphs=4,
        )
    except Exception:
        return None
    text = str(grounding.text or "").strip()
    if not text:
        return None
    return SourceDecisionCore(
        section_title=str(grounding.section_title or "Kendelse").strip() or "Kendelse",
        text=text,
        used_fallback=bool(grounding.used_fallback),
        paragraph_count=int(grounding.paragraph_count),
    )


def render_source_decision_core_html(document: dict[str, Any], query: str) -> str:
    """Render a neutral, escaped decision-core card for Streamlit source expanders."""
    core = source_decision_core(document, query)
    if core is None:
        return ""

    section = html.escape(core.section_title)
    body = html.escape(core.text).replace("\n\n", "</p><p>").replace("\n", "<br>")
    fallback = (
        '<div style="font-size:10.5px;color:#92400e;margin:3px 0 8px;">'
        'Uddraget er fundet i et generisk kendelsesafsnit; kontrollér originalen ved tvivl.'
        '</div>'
        if core.used_fallback
        else ""
    )
    return (
        '<div style="margin:9px 0 11px;padding:10px 11px;background:#fffaf5;'
        'border:1px solid #ead8c3;border-radius:6px;">'
        '<div style="font-size:9.5px;font-weight:700;color:#8C1C2E;text-transform:uppercase;'
        'letter-spacing:.8px;margin-bottom:3px;">Nævnets afgørelseskerne</div>'
        f'<div style="font-size:10.5px;color:#64748b;margin-bottom:7px;">Sektion: {section}</div>'
        f'{fallback}'
        '<div style="font-size:12px;line-height:1.55;color:#334155;max-height:230px;overflow-y:auto;">'
        f'<p style="margin:0;">{body}</p></div>'
        '<div style="font-size:9.5px;color:#94a3b8;margin-top:7px;">'
        'Viser det udsnit Ejnar bruger til at kontrollere, hvad kendelsen faktisk blev afgjort på.'
        '</div></div>'
    )

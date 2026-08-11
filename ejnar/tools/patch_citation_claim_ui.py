"""One-shot asserted patch for citation-claim source-card wiring.

Run once on the feature branch, then remove this helper before merge.
"""
from __future__ import annotations

from pathlib import Path


PAGE = Path("ejnar/pages/ejnar.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PAGE.read_text(encoding="utf-8")
    if "render_source_claims_html" in text:
        print("citation claim UI already wired; no changes")
        return 0

    text = replace_once(
        text,
        "from source_explainability import render_source_decision_core_html\n",
        "from source_explainability import render_source_decision_core_html\n"
        "from answer_citation_explainability import render_source_claims_html\n",
        "citation claim import",
    )

    marker = (
        '                                core_html = render_source_decision_core_html(k, source_query)\n'
        '                                if core_html:\n'
        '                                    st.markdown(core_html, unsafe_allow_html=True)\n'
    )
    replacement = (
        '                                claim_html = render_source_claims_html(\n'
        '                                    msg.get("tekst", ""), i + 1, source_count=len(kilder)\n'
        '                                )\n'
        '                                if claim_html:\n'
        '                                    st.markdown(claim_html, unsafe_allow_html=True)\n'
        + marker
    )
    text = replace_once(text, marker, replacement, "source claim card")

    PAGE.write_text(text, encoding="utf-8")
    print("wired cited answer claims into Ejnar source cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

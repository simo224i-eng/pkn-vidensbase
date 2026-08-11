"""One-shot, idempotent patch for the large Streamlit Ejnar page.

GitHub's contents API replaces whole files, so this script applies four narrowly scoped,
asserted replacements to avoid manually rewriting the ~1,200-line page through the API.
It is run once on the feature branch and removed before merge.
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
    if "render_source_decision_core_html" in text:
        print("source decision-core UI already wired; no changes")
        return 0

    text = replace_once(
        text,
        "import requests\n\nfrom shared import (",
        "import requests\n\nfrom source_explainability import render_source_decision_core_html\n\nfrom shared import (",
        "source explainability import",
    )

    suggested_append = (
        '                st.session_state.chat_historik.append(\n'
        '                    {"rolle": "assistent", "tekst": svar, "kilder": kilder, "auto_filters": af})\n'
    )
    suggested_replacement = (
        '                st.session_state.chat_historik.append(\n'
        '                    {"rolle": "assistent", "tekst": svar, "kilder": kilder,\n'
        '                     "auto_filters": af, "spørgsmål": f})\n'
    )
    text = replace_once(
        text,
        suggested_append,
        suggested_replacement,
        "suggested-question assistant append",
    )

    typed_append = (
        '            st.session_state.chat_historik.append(\n'
        '                {"rolle": "assistent", "tekst": svar, "kilder": kilder, "auto_filters": af})\n'
    )
    typed_replacement = (
        '            st.session_state.chat_historik.append(\n'
        '                {"rolle": "assistent", "tekst": svar, "kilder": kilder,\n'
        '                 "auto_filters": af, "spørgsmål": spørgsmål.strip()})\n'
    )
    text = replace_once(text, typed_append, typed_replacement, "typed-question assistant append")

    column_marker = "                col_svar, col_kld = st.columns([3, 2])\n"
    source_query_block = (
        '                source_query = str(msg.get("spørgsmål") or "").strip()\n'
        '                if not source_query and msg_idx > 0:\n'
        '                    previous = st.session_state.chat_historik[msg_idx - 1]\n'
        '                    if previous.get("rolle") == "bruger":\n'
        '                        source_query = str(previous.get("tekst") or "").strip()\n\n'
        + column_marker
    )
    text = replace_once(text, column_marker, source_query_block, "source query context")

    raw_marker = '                                rå = k.get("Tekst", "")\n'
    core_block = (
        '                                core_html = render_source_decision_core_html(k, source_query)\n'
        '                                if core_html:\n'
        '                                    st.markdown(core_html, unsafe_allow_html=True)\n'
        + raw_marker
    )
    text = replace_once(text, raw_marker, core_block, "source card decision core")

    PAGE.write_text(text, encoding="utf-8")
    print("wired query-specific decision core into Ejnar source cards")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

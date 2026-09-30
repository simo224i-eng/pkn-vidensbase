"""Byg de præcise svar-prompts, som Ejnar ville sende til sprogmodellen.

Del 1 af praksissimulationen (se README.md). For hver sag køres Ejnars rigtige
retrieval, og den færdige prompt fanges i LLM-laget, så alle runtime-politikker
(decision grounding, praksissyntese, citatkontekst) er med – præcis som i appen.

Ingen API-nøgle kræves: hjælpekald (query-udvidelse, omskrivning, rerank) får en
tom streng og falder tilbage til deterministisk retrieval, som når ingen LLM er
konfigureret. Selve svaret skrives bagefter af en agent (fx Claude Code), der
spiller modellens rolle.

    python -m ejnar.evaluation.simulation.build_prompts \\
        --cases ejnar/evaluation/simulation/cases.json --out ejnar/evaluation/simulation/runs/demo
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EJNAR = HERE.parents[1]
if str(EJNAR) not in sys.path:
    sys.path.insert(0, str(EJNAR))

import engine  # noqa: E402
import llm_provider  # noqa: E402
import shared  # noqa: E402


class PromptCapture:
    """Erstatter LLM-kaldet: hjælpekald får "", svar-prompten gemmes."""

    def __init__(self):
        self.prompt = None

    def complete(self, prompt, max_tokens=2000, model=None, cfg=None):
        if model and "haiku" in model.lower():
            return ""
        self.prompt = llm_provider.prompt_to_text(prompt)
        return "[SIMULATION: svaret skrives af agenten]"


def _source(rec: dict, n: int) -> dict:
    dato = rec.get("Dato")
    return {
        "n": n,
        "id": rec.get("Id"),
        "case_number": str(rec.get("Sagsnummer") or ""),
        "date": str(dato.date()) if hasattr(dato, "date") else str(dato or ""),
        "outcome": rec.get("Udfald"),
        "company": rec.get("Selskab"),
        "title": rec.get("Titel"),
        "link": rec.get("Link"),
    }


def build(cases: list[dict], out: Path) -> list[dict]:
    corpus = engine.Corpus.load(with_embeddings=False)
    capture = PromptCapture()
    out.mkdir(parents=True, exist_ok=True)
    index = []
    original = (llm_provider.complete, llm_provider.is_configured)
    llm_provider.complete = capture.complete
    llm_provider.is_configured = lambda *a, **k: True
    try:
        for case in cases:
            cid = case["id"]
            question = case["question"]
            capture.prompt = None
            kilder, historik, debug = corpus.retrieve(question, [])
            shared._llm(engine.byg_prompt(question, kilder, historik))
            (out / f"{cid}.prompt.txt").write_text(capture.prompt or "", encoding="utf-8")
            meta = {
                **case,
                "sources": [_source(k, i + 1) for i, k in enumerate(kilder)],
                "retrieval_debug": {k: v for k, v in debug.items() if k != "standalone"},
                "prompt_file": f"{cid}.prompt.txt",
                "answer_file": f"{cid}.answer.md",
            }
            (out / f"{cid}.case.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            index.append({"id": cid, "sources": len(kilder), "prompt_chars": len(capture.prompt or "")})
            print(f"{cid}: {len(kilder)} kilder, prompt {len(capture.prompt or ''):,} tegn")
    finally:
        llm_provider.complete, llm_provider.is_configured = original
    (out / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", default=str(HERE / "cases.json"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    build(cases, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

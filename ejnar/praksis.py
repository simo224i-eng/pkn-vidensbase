"""Byg Ejnars svar-prompt for et praksisspørgsmål uden LLM-nøgle.

Kører den samme søgning og kontekstbygning som appen og skriver den færdige prompt
til en fil, så en assistent (fx en Claude Code-session på eget abonnement) kan svare
ud fra præcis det, appen ville sende til modellen.

    python ejnar/praksis.py "Hvornår er et brud på en afløbsledning en skade?"
    python ejnar/praksis.py --check svar.md      # citat- og udfaldskontrol af et svar
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine  # noqa: E402
import llm_provider  # noqa: E402
import shared  # noqa: E402

UD = os.path.join(tempfile.gettempdir(), "ejnar_praksis")


def byg(spørgsmål: str) -> None:
    fanget = {}

    def complete(prompt, max_tokens=2000, model=None, cfg=None):
        if not (model and "haiku" in model.lower()):
            fanget["prompt"] = llm_provider.prompt_to_text(prompt)
        return ""

    llm_provider.complete, llm_provider.is_configured = complete, (lambda *a, **k: True)
    corpus = engine.Corpus.load(with_embeddings=False)
    kilder, historik, _ = corpus.retrieve(spørgsmål, [])
    shared._llm(engine.byg_prompt(spørgsmål, kilder, historik))
    os.makedirs(UD, exist_ok=True)
    with open(os.path.join(UD, "prompt.txt"), "w", encoding="utf-8") as f:
        f.write(fanget.get("prompt", ""))
    meta = [{"n": i + 1, "id": k.get("Id"), "sag": str(k.get("Sagsnummer")), "dato": str(k.get("Dato"))[:10],
             "udfald": k.get("Udfald"), "link": k.get("Link")} for i, k in enumerate(kilder)]
    with open(os.path.join(UD, "kilder.json"), "w", encoding="utf-8") as f:
        json.dump({"spørgsmål": spørgsmål, "kilder": meta}, f, ensure_ascii=False, indent=1)
    print(f"Prompt: {UD}/prompt.txt ({len(fanget.get('prompt', ''))} tegn)")
    for m in meta:
        print(f"[Kilde {m['n']}] AKF {m['sag']} · {m['dato']} · {m['udfald']} · {m['link']}")


def tjek(svarfil: str) -> None:
    with open(os.path.join(UD, "kilder.json"), encoding="utf-8") as f:
        data = json.load(f)
    df = engine.load_data().set_index("Id")
    kilder = [df.loc[m["id"]].to_dict() for m in data["kilder"]]
    with open(svarfil, encoding="utf-8") as f:
        svar = f.read()
    print("Mistænkelige citater:", engine.mistænkelige_citater(svar, kilder, data["spørgsmål"]) or "ingen")
    print("Udfaldskonflikter:", engine.udfaldskonflikter(svar, kilder) or "ingen")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spørgsmål", nargs="?")
    ap.add_argument("--check", metavar="SVARFIL")
    a = ap.parse_args()
    tjek(a.check) if a.check else byg(a.spørgsmål or ap.error("angiv et spørgsmål"))

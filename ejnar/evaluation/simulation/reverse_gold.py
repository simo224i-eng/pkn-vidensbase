"""Objektiv kvalitetssikring med "omvendt facit" – ingen menneskelig bedømmer nødvendig.

Facit er nævnets egen afgørelse, ikke en models vurdering:

1. ``sample``   Udtræk kendelser (stratificeret på udfald) og skriv kun sagens FAKTUM
                (resultat og nævnets begrundelse fjernet) til ``items/<GID>.md``. En agent
                skriver derefter et realistisk skadesbehandler-spørgsmål pr. sag i
                ``questions.json``: ``[{"gid": "G01", "question": "..."}]``.
2. ``build``    For hvert spørgsmål:
                a) retrieval-test: rangen af kildekendelsen i Ejnars søgning (ingen LLM);
                b) leave-one-out-prompt: kildekendelsen fjernes, så svaret må forudsige
                   udfaldet ud fra ANDEN praksis – præcis som ved en ny sag.
3.              En agent besvarer ``<GID>.prompt.txt`` → ``<GID>.answer.md``.
4. ``score``    Forudsagt udfald (linjen "FORVENTET UDFALD: …") sammenlignes med nævnets
                faktiske udfald – også mod basisraten "gæt altid Ikke medhold".

    python -m ejnar.evaluation.simulation.reverse_gold sample --out runs/gold --n 20
    python -m ejnar.evaluation.simulation.reverse_gold build  --out runs/gold
    python -m ejnar.evaluation.simulation.reverse_gold score  --out runs/gold
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
EJNAR = HERE.parents[1]
if str(EJNAR) not in sys.path:
    sys.path.insert(0, str(EJNAR))

import engine  # noqa: E402
import llm_provider  # noqa: E402
import shared  # noqa: E402

LABELS = ["Medhold", "Delvis medhold", "Ikke medhold"]
OUTCOME_INSTRUCTION = (
    "\n\n(Afslut dit svar med én separat linje på formen "
    "'FORVENTET UDFALD: Medhold' / 'Delvis medhold' / 'Ikke medhold' / 'Uafklaret', "
    "set fra klagers side.)"
)
# Sætninger der afslører resultatet eller nævnets vurdering
_REVEALS = re.compile(
    r"nævn|medhold|kritisere|tages\s+til\s+følge|afvis|dækning\s+(?:for|af)\s+.*\s+(?:blev|var)\s+(?:anerkendt|afvist)|"
    r"selskabet\s+skal|tilpligt|frifind|godtgjort|sandsynliggjort",
    re.IGNORECASE,
)


def facts_only(rec: dict, max_chars: int = 2500) -> str:
    """Titel + sagsfremstilling uden sætninger, der afslører udfald eller begrundelse."""
    title = " ".join(s for s in re.split(r"(?<=[.!?])\s+", str(rec.get("Titel") or ""))
                     if s and not _REVEALS.search(s))
    text = re.sub(r"\s+", " ", str(rec.get("Tekst") or ""))
    # Sagsfremstillingen står før parternes argumenter og nævnets bemærkninger
    cut = re.search(r"(?:klageren|klager|selskabet)\s+(?:har\s+)?(?:anført|gjort gældende)|nævnets bemærkninger|nævnet (?:finder|udtaler)", text, re.I)
    body = text[: cut.start()] if cut and cut.start() > 400 else text[:max_chars]
    body = " ".join(s for s in re.split(r"(?<=[.!?])\s+", body) if not _REVEALS.search(s))
    return (title + "\n\n" + body)[:max_chars]


def sample(out: Path, n: int, seed: int = 7) -> None:
    df, _, _ = engine.load_corpus_cached()
    rng = random.Random(seed)
    pool = df[df["Udfald"].isin(LABELS) & (df["År"].fillna(0) >= 2012)]
    per = {"Ikke medhold": round(n * 0.4), "Medhold": round(n * 0.3)}
    per["Delvis medhold"] = n - sum(per.values())
    items = []
    for label, k in per.items():
        idx = list(pool[pool["Udfald"] == label].index)
        items += [df.loc[i].to_dict() for i in rng.sample(idx, min(k, len(idx)))]
    rng.shuffle(items)
    (out / "items").mkdir(parents=True, exist_ok=True)
    key = {}
    for i, rec in enumerate(items, start=1):
        gid = f"G{i:02d}"
        key[gid] = {"id": rec["Id"], "case_number": str(rec["Sagsnummer"]), "outcome": rec["Udfald"],
                    "year": int(rec["År"]) if rec["År"] == rec["År"] else None}
        (out / "items" / f"{gid}.md").write_text(
            f"# {gid}\n\nSagens faktum (fra en afsluttet klagesag; resultatet er skjult):\n\n{facts_only(rec)}\n",
            encoding="utf-8")
    (out / ".gold.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(items)} sager udtrukket: {Counter(v['outcome'] for v in key.values())}")


def build(out: Path) -> None:
    gold = json.loads((out / ".gold.json").read_text(encoding="utf-8"))
    questions = {q["gid"]: q["question"] for q in json.loads((out / "questions.json").read_text(encoding="utf-8"))}
    corpus = engine.Corpus.load(with_embeddings=False)
    df = corpus.df
    captured = {}

    def capture(prompt, max_tokens=2000, model=None, cfg=None):
        if model and "haiku" in model.lower():
            return ""
        captured["prompt"] = llm_provider.prompt_to_text(prompt)
        return ""

    orig = (llm_provider.complete, llm_provider.is_configured)
    llm_provider.complete, llm_provider.is_configured = capture, (lambda *a, **k: True)
    ranks = {}
    try:
        for gid, question in questions.items():
            src_id = gold[gid]["id"]
            # a) Retrieval: findes kildekendelsen (med i korpus)?
            idx = engine.relevans_søg(question, df, corpus.vec, corpus.mat, None, top_n=100)
            ids = list(df.iloc[idx]["Id"]) if idx else []
            ranks[gid] = ids.index(src_id) + 1 if src_id in ids else None
            # b) Leave-one-out: byg svar-prompten uden kildekendelsen
            sub = df.index[df["Id"] != src_id].tolist()
            full_q = question + OUTCOME_INSTRUCTION
            kilder, historik, _ = corpus.retrieve(full_q, [], sub_idx=sub)
            assert all(k.get("Id") != src_id for k in kilder)
            shared._llm(engine.byg_prompt(full_q, kilder, historik))
            (out / f"{gid}.prompt.txt").write_text(captured.get("prompt", ""), encoding="utf-8")
    finally:
        llm_provider.complete, llm_provider.is_configured = orig
    (out / "retrieval_ranks.json").write_text(json.dumps(ranks, indent=2), encoding="utf-8")
    found = [r for r in ranks.values() if r]
    print(f"Retrieval: fundet i top-100 {len(found)}/{len(ranks)}; "
          f"top-1 {sum(r == 1 for r in found)}, top-5 {sum(r <= 5 for r in found)}, top-15 {sum(r <= 15 for r in found)}")


def _predicted(answer: str) -> str:
    m = re.search(r"FORVENTET\s+UDFALD\s*:\s*\**\s*(Delvis medhold|Ikke medhold|Medhold|Uafklaret)", answer, re.I)
    return m.group(1).capitalize() if m else "Mangler"


def score(out: Path) -> dict:
    gold = json.loads((out / ".gold.json").read_text(encoding="utf-8"))
    ranks = json.loads((out / "retrieval_ranks.json").read_text(encoding="utf-8"))
    rows = []
    for gid, g in sorted(gold.items()):
        path = out / f"{gid}.answer.md"
        if not path.exists():
            continue
        pred = _predicted(path.read_text(encoding="utf-8"))
        rows.append({"gid": gid, "actual": g["outcome"], "predicted": pred, "rank": ranks.get(gid)})
    n = len(rows)
    norm = lambda s: s.lower()
    exact = sum(norm(r["predicted"]) == norm(r["actual"]) for r in rows)
    # "Retning": skelner klager får (helt/delvist) medhold vs. ikke medhold
    side = lambda s: "klager" if norm(s) in ("medhold", "delvis medhold") else ("selskab" if norm(s) == "ikke medhold" else "?")
    direction = sum(side(r["predicted"]) == side(r["actual"]) for r in rows)
    baseline = sum(norm(r["actual"]) == "ikke medhold" for r in rows)
    per_label = {}
    for label in LABELS:
        sub = [r for r in rows if r["actual"] == label]
        per_label[label] = f"{sum(norm(r['predicted']) == norm(label) for r in sub)}/{len(sub)}"
    found = [r["rank"] for r in rows if r["rank"]]
    result = {
        "cases": n,
        "outcome_exact": f"{exact}/{n}",
        "outcome_direction": f"{direction}/{n}",
        "baseline_always_ikke_medhold": f"{baseline}/{n}",
        "per_label_recall": per_label,
        "uafklaret": sum(norm(r["predicted"]) == "uafklaret" for r in rows),
        "retrieval_top5": f"{sum(r <= 5 for r in found)}/{n}",
        "retrieval_top15": f"{sum(r <= 15 for r in found)}/{n}",
        "rows": rows,
    }
    (out / "gold-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["sample", "build", "score"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=20)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    {"sample": lambda: sample(out, args.n), "build": lambda: build(out), "score": lambda: score(out)}[args.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

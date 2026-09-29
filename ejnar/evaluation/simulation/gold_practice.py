"""Praksisfacit: et kildeforankret facitsæt til Ejnar.

Hvert facit bygger på én kendelse og nævnets egen vurdering af den:

1. ``sample``  Udtræk kendelser (stratificeret på mangeltype og udfald) og skriv
               ``items/<GID>.md`` med resumé, sagens begyndelse og nævnets vurdering.
2.             Facit-agenter skriver ``facit/<GID>.json``::

                   {"gid": "F01", "question": "praksisspørgsmål uden sagsnummer/dato",
                    "issue": "kort beskrivelse af det juridiske spørgsmål",
                    "key_points": [{"point": "hvad nævnet lagde vægt på",
                                    "quote": "ordret citat fra nævnets vurdering"}]}

3. ``check``   Kontrollér at hvert citat står ordret i kendelsen (ellers afvises facit).
4. ``build``   Kør Ejnars rigtige retrieval for hvert spørgsmål: findes facitkendelsen
               (rang i søgningen, med blandt kilderne)? Prompterne gemmes til svar.
5.             Svar-agenter besvarer ``<GID>.prompt.txt`` → ``<GID>.answer.md``.
6. ``gradepack`` Bedømmelsesfiler; bedømmere skriver ``grades*.json``::

                   [{"gid": "F01", "key_points": [{"verdict": "dækket" | "delvist" |
                     "mangler" | "modsagt", "note": "..."}], "misrepresented": false}]

7. ``score``   Citeres facitkendelsen, er dens udfald gengivet korrekt, og – efter
               bedømmernes ``grades*.json`` – rammer svaret nøglepunkterne?

    python -m ejnar.evaluation.simulation.gold_practice sample --out runs/gold60 --n 60
    python -m ejnar.evaluation.simulation.gold_practice check  --out runs/gold60
    python -m ejnar.evaluation.simulation.gold_practice build  --out runs/gold60
    python -m ejnar.evaluation.simulation.gold_practice score  --out runs/gold60
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

import board_reasoning  # noqa: E402
import engine  # noqa: E402

LABELS = ["Medhold", "Delvis medhold", "Ikke medhold"]


def _norm(t: str) -> str:
    """Normalisering til citatkontrol: små bogstaver, ingen orddeling/PDF-mellemrum."""
    t = re.sub(r"-\s*\n\s*", "", str(t or "")).lower()
    return re.sub(r"[^a-zæøå0-9]", "", t)


def _assessment(tekst: str) -> str:
    delt = board_reasoning.del_kendelse(tekst)
    return tekst[delt[1]:] if delt else ""


def sample(out: Path, n: int, seed: int = 29) -> None:
    df, _, _ = engine.load_corpus_cached()
    rng = random.Random(seed)
    df = df[df["Udfald"].isin(LABELS) & (df["År"].fillna(0) >= 2012)].copy()
    df["vurdering"] = df["Tekst"].map(_assessment)
    df = df[df["vurdering"].str.len().between(500, 20000)]
    df["hovedtype"] = df["Mangeltype"].map(lambda m: (list(m) or ["Andet"])[0])
    # Medhold/delvis medhold overvægtes: det er dér, skillelinjerne står
    kvote = {"Ikke medhold": round(n * 0.4), "Delvis medhold": round(n * 0.3)}
    kvote["Medhold"] = n - sum(kvote.values())
    valgt = []
    for label, k in kvote.items():
        pulje = df[df["Udfald"] == label]
        typer = sorted(pulje["hovedtype"].unique(), key=lambda t: -len(pulje[pulje["hovedtype"] == t]))
        runde = 0
        while k > 0 and runde < 50:                    # round-robin over mangeltyper
            for t in typer:
                kandidater = [i for i in pulje[pulje["hovedtype"] == t].index if i not in valgt]
                if kandidater and k > 0:
                    valgt.append(rng.choice(kandidater))
                    k -= 1
            runde += 1
    rng.shuffle(valgt)
    (out / "items").mkdir(parents=True, exist_ok=True)
    (out / "facit").mkdir(exist_ok=True)
    key = {}
    for j, i in enumerate(valgt, start=1):
        r = df.loc[i]
        gid = f"F{j:02d}"
        key[gid] = {"id": r["Id"], "case_number": str(r["Sagsnummer"]), "outcome": r["Udfald"],
                    "coverage": r["Dækning"], "defect": r["hovedtype"],
                    "date": str(r["Dato"])[:10]}
        rens = lambda t: re.sub(r"[ \t]+", " ", str(t)).strip()
        (out / "items" / f"{gid}.md").write_text(
            f"# {gid}\n\nUdfald for klager: {r['Udfald']} · Dækning: {r['Dækning']} · "
            f"Mangeltype: {', '.join(r['Mangeltype']) or '–'}\n\n## Resumé\n\n{r['Titel']}\n\n"
            f"## Sagens begyndelse\n\n{rens(str(r['Tekst'])[:3000])}\n\n"
            f"## Nævnets vurdering og resultat\n\n{rens(r['vurdering'])}\n",
            encoding="utf-8")
    (out / "key.json").write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(valgt)} kendelser: {Counter(v['outcome'] for v in key.values())}; "
          f"mangeltyper: {Counter(v['defect'] for v in key.values()).most_common()}")


def _facit(out: Path) -> dict:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((out / "facit").glob("F*.json"))}


def check(out: Path) -> dict:
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    tekster = dict(zip(*[engine.load_data()[c] for c in ("Id", "Tekst")]))
    fejl = {}
    for gid, f in _facit(out).items():
        kilde = _norm(tekster.get(key[gid]["id"], ""))
        mangler = [kp["quote"] for kp in f.get("key_points", []) if _norm(kp.get("quote")) not in kilde]
        if mangler or not f.get("question") or len(f.get("key_points", [])) < 2:
            fejl[gid] = mangler or ["mangler spørgsmål eller nøglepunkter"]
    print(f"{len(_facit(out))} facit, {len(fejl)} med fejl")
    for gid, m in fejl.items():
        print(f"  {gid}: {m[:2]}")
    return fejl


def build(out: Path) -> None:
    from ejnar.evaluation.simulation.build_prompts import PromptCapture
    import llm_provider
    import shared

    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    corpus = engine.Corpus.load(with_embeddings=False)
    df = corpus.df
    cap = PromptCapture()
    orig = (llm_provider.complete, llm_provider.is_configured)
    llm_provider.complete, llm_provider.is_configured = cap.complete, (lambda *a, **k: True)
    ranks = {}
    try:
        for gid, f in _facit(out).items():
            src = key[gid]["id"]
            idx = engine.relevans_søg(f["question"], df, corpus.vec, corpus.mat, None, top_n=100)
            ids = list(df.iloc[idx]["Id"]) if idx else []
            kilder, historik, _ = corpus.retrieve(f["question"], [])
            k_ids = [k.get("Id") for k in kilder]
            ranks[gid] = {"search_rank": ids.index(src) + 1 if src in ids else None,
                          "source_n": k_ids.index(src) + 1 if src in k_ids else None,
                          "sources": [{"n": i + 1, "id": k.get("Id"), "outcome": k.get("Udfald")}
                                      for i, k in enumerate(kilder)]}
            cap.prompt = None
            shared._llm(engine.byg_prompt(f["question"], kilder, historik))
            (out / f"{gid}.prompt.txt").write_text(cap.prompt or "", encoding="utf-8")
    finally:
        llm_provider.complete, llm_provider.is_configured = orig
    (out / "retrieval.json").write_text(json.dumps(ranks, indent=2), encoding="utf-8")
    fundet = [r for r in ranks.values() if r["source_n"]]
    print(f"Facitkendelsen blandt kilderne: {len(fundet)}/{len(ranks)}; "
          f"top-5 i søgningen: {sum((r['search_rank'] or 999) <= 5 for r in ranks.values())}")


def gradepack(out: Path) -> None:
    """Bedømmelsesfiler: facit + facitkendelsens vurdering + svaret → ``grade/<GID>.md``."""
    ret = json.loads((out / "retrieval.json").read_text(encoding="utf-8"))
    (out / "grade").mkdir(exist_ok=True)
    for gid, f in _facit(out).items():
        ans = out / f"{gid}.answer.md"
        if not ans.exists():
            continue
        item = (out / "items" / f"{gid}.md").read_text(encoding="utf-8")
        n = ret.get(gid, {}).get("source_n")
        punkter = "\n".join(f"{i}. {kp['point']}\n   Citat: \"{kp['quote']}\"" for i, kp in
                             enumerate(f["key_points"], start=1))
        (out / "grade" / f"{gid}.md").write_text(
            f"# {gid}\n\n## Spørgsmål\n\n{f['question']}\n\n## Facit\n\nFacitkendelsen var "
            + (f"[Kilde {n}] i svarets kildeliste." if n else "IKKE blandt svarets kilder.")
            + f"\n\nJuridisk spørgsmål: {f['issue']}\n\nNøglepunkter (hvad nævnet lagde vægt på):\n{punkter}"
            f"\n\n## Facitkendelsen\n\n{item.split(chr(10), 2)[-1]}\n\n## Svaret\n\n{ans.read_text(encoding='utf-8')}\n",
            encoding="utf-8")
    print(f"{len(list((out / 'grade').glob('F*.md')))} bedømmelsesfiler")


def score(out: Path) -> dict:
    key = json.loads((out / "key.json").read_text(encoding="utf-8"))
    ret = json.loads((out / "retrieval.json").read_text(encoding="utf-8"))
    grades = {}
    for p in sorted(out.glob("grades*.json")):
        for g in json.loads(p.read_text(encoding="utf-8")):
            grades[g["gid"]] = g
    rows = []
    for gid, r in sorted(ret.items()):
        ans_path = out / f"{gid}.answer.md"
        if not ans_path.exists():
            continue
        svar = ans_path.read_text(encoding="utf-8")
        n = r["source_n"]
        citeret = bool(n) and n in engine.citerede_kilder(svar, len(r["sources"]))
        kilder = [{"Udfald": s["outcome"]} for s in r["sources"]]
        konflikt = bool(n) and any(k["kilde"] == n for k in engine.udfaldskonflikter(svar, kilder))
        g = grades.get(gid, {})
        kp = Counter(p.get("verdict") for p in g.get("key_points", []))
        rows.append({"gid": gid, "outcome": key[gid]["outcome"], "found": bool(n), "cited": citeret,
                     "outcome_conflict": konflikt, "key_points": dict(kp),
                     "misrepresented": g.get("misrepresented", False)})
    n = len(rows) or 1
    kp_total = Counter()
    for row in rows:
        kp_total.update(row["key_points"])
    kp_n = sum(kp_total.values()) or 1
    result = {
        "questions": len(rows),
        "gold_decision_found": f"{sum(r['found'] for r in rows)}/{len(rows)}",
        "gold_decision_cited": f"{sum(r['cited'] for r in rows)}/{len(rows)}",
        "outcome_conflicts": sum(r["outcome_conflict"] for r in rows),
        "key_points": dict(kp_total),
        "key_points_covered_pct": round(100 * kp_total.get("dækket", 0) / kp_n, 1),
        "key_points_covered_or_partly_pct": round(100 * (kp_total.get("dækket", 0) + kp_total.get("delvist", 0)) / kp_n, 1),
        "gold_decision_misrepresented": sum(bool(r["misrepresented"]) for r in rows),
        "by_outcome": {lab: f"{sum(r['cited'] for r in rows if r['outcome'] == lab)}/"
                            f"{sum(r['outcome'] == lab for r in rows)} citeret" for lab in LABELS},
        "rows": rows,
    }
    (out / "gold-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("cmd", choices=["sample", "check", "build", "gradepack", "score"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=60)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    {"sample": lambda: sample(out, a.n), "check": lambda: check(out),
     "build": lambda: build(out), "gradepack": lambda: gradepack(out), "score": lambda: score(out)}[a.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

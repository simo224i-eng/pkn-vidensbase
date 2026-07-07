"""Offline retrieval-evaluering mod de RIGTIGE kendelser — gratis (ingen API).

Kør fra backend-mappen:  python eval/eval_retrieval.py
Bygger TF-IDF-indekset (~90 sek) og måler recall@8 / recall@25 / MRR for
guldsættet, både med og uden dansk synonym-udvidelse. Bruges til at holde
søgekvaliteten ærlig når stopord, synonymliste eller vægtning ændres."""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("EJNAR_WARMUP", "0")

import pandas as pd  # noqa: E402

from app.core.data import _find_csv, _load_rows  # noqa: E402
from app.core.search import byg_tfidf_index, tfidf_søg  # noqa: E402
from app.core.synonymer import udvid_query_dansk  # noqa: E402


def evaluer(df, vec, mat, spørgsmål: list, brug_synonymer: bool) -> dict:
    hits8 = hits25 = 0
    rr_sum = 0.0
    detaljer = []
    for item in spørgsmål:
        q = udvid_query_dansk(item["q"]) if brug_synonymer else item["q"]
        res = tfidf_søg(q, df, vec, mat, top_n=25)
        links = [str(l) for l in res["Link"]] if len(res) else []
        rank = next((i + 1 for i, l in enumerate(links) if item["cn"] in l), None)
        if rank is not None:
            rr_sum += 1.0 / rank
            hits25 += 1
            if rank <= 8:
                hits8 += 1
        detaljer.append((item["q"][:56], rank))
    n = len(spørgsmål)
    return {"recall@8": hits8 / n, "recall@25": hits25 / n, "mrr": rr_sum / n,
            "detaljer": detaljer}


def main() -> None:
    her = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(her, "guldsæt.json"), encoding="utf-8") as f:
        spørgsmål = json.load(f)["spørgsmål"]

    print("Indlæser kendelser…")
    df = pd.DataFrame(_load_rows(_find_csv(
        os.environ.get("EJNAR_DATA_DIR", os.path.join(her, "..", "..", "..", "ejnar")))))
    print(f"{len(df)} kendelser. Bygger TF-IDF-indeks (~90 sek)…")
    t0 = time.time()
    vec, mat = byg_tfidf_index(df)
    print(f"Indeks klar ({time.time()-t0:.0f} sek).\n")

    uden = evaluer(df, vec, mat, spørgsmål, brug_synonymer=False)
    med = evaluer(df, vec, mat, spørgsmål, brug_synonymer=True)

    print(f"{'':56s}  uden  med")
    for (tekst, r_u), (_, r_m) in zip(uden["detaljer"], med["detaljer"]):
        mark = " ▲" if (r_m or 99) < (r_u or 99) else (" ▼" if (r_m or 99) > (r_u or 99) else "")
        print(f"{tekst:56s}  {str(r_u or '–'):>4s}  {str(r_m or '–'):>3s}{mark}")
    print(f"\n{'metrik':12s} {'uden synonymer':>15s} {'med synonymer':>14s}")
    for k in ("recall@8", "recall@25", "mrr"):
        print(f"{k:12s} {uden[k]:15.3f} {med[k]:14.3f}")


if __name__ == "__main__":
    main()

"""Eval-harness for Ejnars RAG-pipeline — mål kvaliteten i stedet for at gætte.

Kører det RIGTIGE maskineri (samme funktioner som appen: hybrid retrieval,
rerank, kontekst-bygning, svar, citatkontrol) på et fast sæt guldspørgsmål og
skriver en rapport. Kør før/efter en ændring og sammenlign.

Brug (lokalt, kræver nøgler i miljøet):
    export ANTHROPIC_API_KEY=sk-ant-...
    export VOYAGE_API_KEY=pa-...          # valgfri men anbefalet (semantik + rerank)
    python3 eval_rag.py --kun-retrieval    # hurtig/billig: kun søgekvalitet
    python3 eval_rag.py                    # fuld: retrieval + svar + citatkontrol
    python3 eval_rag.py --judge            # + Haiku bedømmer svarene 1-5

Output: eval_rapport.md (+ resumé i terminalen).

Metrik (retrieval): precision@K som proxy — andel af de K udvalgte kilder hvis
tekst indeholder mindst ét af spørgsmålets forventede fagtermer. Groft, men
stabilt nok til at sammenligne to versioner af pipelinen.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import os
import sys
import zipfile

HER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HER)

import pandas as pd  # noqa: E402

from shared import (  # noqa: E402
    strip_html, byg_indeks_tekst, dansk_tokenizer, hent_nøgle,
    byg_embeddings_indeks, hybrid_retrieval, llm_rerank,
    byg_fokuseret_kontekst, valider_citationer, _llm, _llm_haiku,
)

GOLDEN = [
    {"sp": "Hvornår dækker ejerskifteforsikringen skimmelsvamp?", "termer": ["skimmel"]},
    {"sp": "Hvad er praksis om utætte tage uden undertag?", "termer": ["undertag", "tagsten", "utæt"]},
    {"sp": "Hvornår er en skade undtaget, fordi den er nævnt i tilstandsrapporten?", "termer": ["tilstandsrapport"]},
    {"sp": "Hvordan vurderes restlevetid ved nedslidte installationer?", "termer": ["levetid", "restlevetid"]},
    {"sp": "Hvad er praksis om kloakskader og defekte skjulte rør?", "termer": ["kloak", "faldstamme", "rør"]},
    {"sp": "Hvornår gives dækning for sætningsskader og revner i fundamentet?", "termer": ["sætning", "fundament", "revne"]},
    {"sp": "Hvornår afvises et krav som for sent anmeldt?", "termer": ["anmeld", "frist"]},
    {"sp": "Dækkes vandskader fra badeværelse uden vådrumsmembran?", "termer": ["vådrum", "membran", "badeværelse"]},
    {"sp": "Hvad sker der, når bygningssagkyndig har overset en synlig skade?", "termer": ["bygningssagkyndig", "huseftersyn", "overset"]},
    {"sp": "Hvornår får klager udbedringsomkostninger frem for værdiforringelse?", "termer": ["udbedring", "værdiforringelse", "erstatning"]},
    {"sp": "Hvad er praksis om råd og svamp i tagkonstruktionen?", "termer": ["råd", "svamp", "spær"]},
    {"sp": "Hvornår er fugt i kælderen dækket af ejerskifteforsikringen?", "termer": ["kælder", "fugt"]},
    {"sp": "Hvilken betydning har det, at køber kendte forholdet ved overtagelsen?", "termer": ["bekendt", "kendte", "overtagelse"]},
    {"sp": "Hvornår nedsættes erstatningen på grund af alder og slid?", "termer": ["afskriv", "alder", "slid", "levetid"]},
    {"sp": "Hvad er praksis om ulovlige el-installationer?", "termer": ["el-installation", "ulovlig", "el "]},
    {"sp": "Hvornår hæfter selskabet for forkerte oplysninger om isolering?", "termer": ["isolering"]},
]


def load_df() -> pd.DataFrame:
    """Minimal udgave af appens load_data (samme rensning + link-dedup)."""
    csv.field_size_limit(10_000_000)
    sti = os.path.join(HER, "ejnar_ejerskifteforsikring.csv")
    if not os.path.exists(sti):
        zsti = sti + ".zip"
        if not os.path.exists(zsti):
            sys.exit("FEJL: ingen ejnar_ejerskifteforsikring.csv(.zip) fundet")
        with zipfile.ZipFile(zsti) as z:
            m = next(n for n in z.namelist() if n.endswith(".csv"))
            z.extract(m, HER)
            if os.path.join(HER, m) != sti:
                os.replace(os.path.join(HER, m), sti)
    rows, seen = [], set()
    with open(sti, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("Link") in seen:
                continue
            seen.add(r.get("Link"))
            rows.append({
                "Dato": r.get("Dato", ""), "Titel": r.get("Titel", ""),
                "Link": r.get("Link", ""),
                "Tekst": strip_html(r.get("Tekst", ""), preserve_headings=True),
            })
    df = pd.DataFrame(rows)
    df["Dato"] = pd.to_datetime(df["Dato"], errors="coerce")
    return df


def byg_tfidf(df):
    from sklearn.feature_extraction.text import TfidfVectorizer
    texts = (byg_indeks_tekst(t, tx) for t, tx in
             zip(df["Titel"].astype(str), df["Tekst"].astype(str)))
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2), min_df=2,
                          sublinear_tf=True, tokenizer=dansk_tokenizer, token_pattern=None)
    mat = vec.fit_transform(texts)
    return vec, mat


def svar_prompt(spørgsmål: str, docs: list, embeds, link_til_idx) -> list:
    """Samme struktur som appens _byg_prompt (uden chat-historik)."""
    kontekst = byg_fokuseret_kontekst(
        spørgsmål, docs, max_chunks_per_doc=5, max_total_chars=60_000,
        embeds=embeds, link_til_idx=link_til_idx)
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel'][:80]}"
        for i, d in enumerate(docs))
    return [
        {"type": "text", "text": (
            "Du er en juridisk assistent specialiseret i Ankenævnet for Forsikrings praksis "
            "om ejerskifteforsikring. Besvar KUN ud fra de vedlagte kendelser, citér ordret "
            "i anførselstegn med [Kilde X], og skriv eksplicit hvis kilderne ikke svarer.\n\n"
            f"KILDEREGISTER:\n{kilde_liste}")},
        {"type": "text", "text": f"\nKENDELSER:\n{kontekst}\n"},
        {"type": "text", "text": f"SPØRGSMÅL: {spørgsmål}\n\nSVAR:"},
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kun-retrieval", action="store_true", help="spring svar-generering over")
    ap.add_argument("--judge", action="store_true", help="Haiku bedømmer svar 1-5")
    ap.add_argument("--top", type=int, default=8, help="antal kilder pr. spørgsmål (K)")
    args = ap.parse_args()

    if not hent_nøgle("ANTHROPIC_API_KEY") and not args.kun_retrieval:
        sys.exit("FEJL: ANTHROPIC_API_KEY mangler (eller kør --kun-retrieval).")

    print("Indlæser data…")
    df = load_df()
    print(f"  {len(df)} kendelser")
    print("Bygger TF-IDF…")
    vec, mat = byg_tfidf(df)
    print("Indlæser embeddings…")
    embeds = byg_embeddings_indeks(df, cache_key="ejnar_ejerskifteforsikring")
    if isinstance(embeds, dict):
        dk = embeds.get("dækning", (len(df), len(df)))
        print(f"  chunk-indeks aktivt · dækning {dk[0]}/{dk[1]} kendelser")
    else:
        print("  INGEN embeddings (sæt VOYAGE_API_KEY) — kører ren TF-IDF")
    link_til_idx = {str(l): i for i, l in enumerate(df["Link"])}

    K = args.top
    linjer = [f"# Ejnar RAG-eval · {datetime.date.today().isoformat()}",
              f"\n{len(df)} kendelser · K={K} · embeddings: "
              f"{'ja' if embeds is not None else 'nej'} · svar: "
              f"{'nej' if args.kun_retrieval else 'ja'}\n"]
    prec_sum, n_q = 0.0, 0

    for gi, g in enumerate(GOLDEN, 1):
        sp, termer = g["sp"], [t.lower() for t in g["termer"]]
        fused = hybrid_retrieval(sp, df, vec, mat, embeds, top_retrieve=60, top_final=30) \
            if embeds is not None else []
        if fused:
            kand = df.iloc[fused].to_dict("records")
        else:
            from sklearn.metrics.pairwise import cosine_similarity
            qv = vec.transform([sp])
            scores = cosine_similarity(qv, mat).flatten()
            top = scores.argsort()[-30:][::-1]
            kand = df.iloc[[int(i) for i in top if scores[i] > 0.01]].to_dict("records")
        kilder = llm_rerank(sp, kand, top_n=K)

        # Proxy-precision: kilde er "relevant" hvis mindst ét forventet term optræder
        rel = sum(1 for k in kilder
                  if any(t in ((k.get("Titel", "") + " " + (k.get("Tekst") or "")[:8000]).lower())
                         for t in termer))
        prec = rel / max(len(kilder), 1)
        prec_sum += prec
        n_q += 1
        print(f"[{gi:2}/{len(GOLDEN)}] p@{K}={prec:.2f} · {sp[:64]}")

        linjer.append(f"\n## {gi}. {sp}\n")
        linjer.append(f"**Retrieval:** {rel}/{len(kilder)} kilder matcher forventede termer "
                      f"({', '.join(g['termer'])}) → **p@{K} = {prec:.2f}**\n")
        for i, k in enumerate(kilder[:K]):
            try:
                ds = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
            except Exception:
                ds = "-"
            hit = "✅" if any(t in ((k.get("Titel", "") + " " + (k.get("Tekst") or "")[:8000]).lower())
                             for t in termer) else "▫️"
            linjer.append(f"- {hit} [{i+1}] {ds} · {k.get('Titel', '')[:100]}")

        if not args.kun_retrieval and kilder:
            svar = _llm(svar_prompt(sp, kilder, embeds, link_til_idx), max_tokens=1500)
            suspekte = valider_citationer(svar, kilder)
            linjer.append(f"\n**Citatkontrol:** {len(suspekte)} suspekte citater")
            if args.judge:
                dom = _llm_haiku(
                    "Bedøm dette svar på en juridisk forespørgsel. Skala 1-5 hvor 5 = "
                    "præcist, kildetro og direkte brugbart for en jurist. "
                    f"Svar KUN med et tal.\n\nSPØRGSMÅL: {sp}\n\nSVAR:\n{svar[:4000]}\n\nKARAKTER:",
                    max_tokens=5).strip()
                linjer.append(f"**Judge (Haiku):** {dom}/5")
            linjer.append(f"\n<details><summary>Svar</summary>\n\n{svar[:2500]}\n\n</details>")

    linjer.insert(2, f"\n**Samlet retrieval-precision@{K}: {prec_sum / max(n_q, 1):.2f}**\n")
    ud = os.path.join(HER, "eval_rapport.md")
    with open(ud, "w", encoding="utf-8") as f:
        f.write("\n".join(linjer))
    print(f"\nSamlet p@{K}: {prec_sum / max(n_q, 1):.2f} · rapport: {ud}")


if __name__ == "__main__":
    main()

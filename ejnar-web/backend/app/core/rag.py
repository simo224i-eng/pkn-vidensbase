"""RAG-orkestrering: query-forståelse, TF-IDF-retrieval, LLM-rerank,
kontekst-bygning og prompt til Claude.

v1 er BEVIDST keyword-only (TF-IDF) — ingen Voyage-embeddings, ingen Voyage
Rerank. Det er en eksplicit beslutning for at undgå ekstra API-omkostninger,
ikke en begrænsning i arkitekturen: semantisk søgning kan lægges til senere
som endnu en rangering der fusioneres ind (se ejnar/shared.py::hybrid_retrieval
for mønsteret når I er klar til det).

klassificer_query/auto_filter_query/omformuler_opfoelgning er 1:1 porteret fra
ejnar/shared.py (kalder kun Haiku — billigt, samme forbrug som i dag)."""
from __future__ import annotations

import re

import pandas as pd

from .claude import llm_haiku
from .search import apply_auto_filters, tfidf_søg
from .text import chunk_tekst, udtræk_kerneafsnit


def _datostr(dato) -> str:
    """dd.mm.yyyy — men crash-frit: en enkelt kendelse uden dato (NaT) må
    aldrig vælte hele prompt-bygningen og dermed svaret."""
    try:
        ts = pd.Timestamp(dato)
        if pd.isna(ts):
            return "ukendt dato"
        return ts.strftime("%d.%m.%Y")
    except Exception:
        return "ukendt dato"

def klassificer_query(query: str) -> dict:
    """Klassificér query-type med Haiku for at tilpasse retrieval-parametre.
    Returnerer dict med 'type' (faktuel/sammenligning/procedure/åben) og
    'top_k' (antal dokumenter at hente).

    - faktuel: specifik juridisk kendsgerning → færre, præcise hits
    - sammenligning: 'hvornår gives medhold vs afvist' → flere hits for bredde
    - procedure: processuelt spørgsmål → moderat
    - åben: bredt eksplorativt → mange hits"""
    default = {"type": "åben", "top_retrieve": 40, "top_final": 8}
    if not query or len(query) < 5:
        return default
    prompt = (
        "Klassificér dette juridiske spørgsmål i én af fire kategorier:\n"
        "- FAKTUEL: spørger til en specifik regel, afgørelse eller kendsgerning\n"
        "- SAMMENLIGNING: sammenligner praksis, vil se mønstre/tendenser på tværs\n"
        "- PROCEDURE: handler om proces, frister, kompetence, klagevej\n"
        "- ÅBEN: bredt, eksplorativt eller uklart spørgsmål\n\n"
        f"Spørgsmål: \"{query}\"\n\n"
        "Svar med KUN ét ord (FAKTUEL/SAMMENLIGNING/PROCEDURE/ÅBEN):"
    )
    svar = llm_haiku(prompt, max_tokens=10).strip().upper()
    if "FAKTUEL" in svar:
        return {"type": "faktuel", "top_retrieve": 25, "top_final": 6}
    elif "SAMMENLIGNING" in svar:
        return {"type": "sammenligning", "top_retrieve": 60, "top_final": 12}
    elif "PROCEDURE" in svar:
        return {"type": "procedure", "top_retrieve": 30, "top_final": 8}
    return default


def auto_filter_query(query: str, filter_options: dict) -> dict:
    """Use Haiku to extract implicit filter preferences from a user's question.
    filter_options = {"Kategori": ["val1", ...], "Plantype": ["val1", ...], ...}
    Returns dict of suggested filters, e.g. {"Kategori": ["Kommuneplan"]}."""
    if not query or not filter_options or len(query) < 10:
        return {}
    lines = []
    for name, vals in filter_options.items():
        lines.append(f"- {name}: [{', '.join(str(v) for v in vals[:40])}]")
    filter_desc = "\n".join(lines)
    prompt = (
        "Analysér dette juridiske spørgsmål og foreslå filtre der vil indsnævre "
        "søgningen til de mest relevante kendelser fra Ankenævnet for Forsikring "
        "om ejerskifteforsikring.\n\n"
        f"SPØRGSMÅL: \"{query}\"\n\n"
        f"TILGÆNGELIGE FILTRE (brug KUN værdier fra listerne):\n{filter_desc}\n\n"
        "REGLER:\n"
        "- Foreslå filtre der er impliceret af spørgsmålet — også når brugeren bruger "
        "flertalsformer som \"skimmelsager\", \"tagsager\" eller \"kloakker\".\n"
        "- Kopiér værdien PRÆCIS som den står i listen (ental, stavning, store/små bogstaver) — "
        "fx \"Skimmel/fugt\" (IKKE \"Skimmelsager\"), \"Tag/tagdækning\" (IKKE \"Tage\").\n"
        "- Vær konservativ — hellere for få filtre end for mange.\n"
        "- Undgå Udfald-filtre medmindre spørgsmålet eksplicit nævner udfald.\n"
        "- Hvis ingen filtre er tydelige, skriv: INGEN\n\n"
        "Svar i format (ét filter per linje, ingen forklaring):\n"
        "Filternavn: Værdi1, Værdi2\n\n"
        "FILTRE:"
    )
    svar = llm_haiku(prompt, max_tokens=150)
    if not svar or "INGEN" in svar.upper()[:30]:
        return {}
    suggested = {}
    for line in svar.strip().split("\n"):
        line = line.strip().lstrip("- ")
        if ":" not in line or "INGEN" in line.upper():
            continue
        parts = line.split(":", 1)
        name_raw = parts[0].strip()
        vals_raw = parts[1].strip()
        matched_name = None
        for fn in filter_options:
            if fn.lower() == name_raw.lower():
                matched_name = fn
                break
        if not matched_name:
            for fn in filter_options:
                if fn.lower() in name_raw.lower() or name_raw.lower() in fn.lower():
                    matched_name = fn
                    break
        if not matched_name:
            continue
        raw_vals = [v.strip() for v in vals_raw.split(",")]
        valid = []
        for rv in raw_vals:
            if not rv:
                continue
            rv_l = rv.lower().rstrip(".")
            # Normalisér danske bøjningsendelser: "kommuneplaner"→"kommuneplan",
            # "screeningsafgørelser"→"screeningsafgørelse" osv.
            def _stem(s):
                s = s.lower().rstrip(".")
                for suf in ("erne", "ene", "er", "en", "et", "e", "r"):
                    if s.endswith(suf) and len(s) - len(suf) >= 4:
                        return s[:-len(suf)]
                return s
            rv_stem = _stem(rv_l)
            match_opt = None
            for opt in filter_options[matched_name]:
                ol = str(opt).lower()
                if rv_l == ol:
                    match_opt = opt
                    break
            if not match_opt:
                for opt in filter_options[matched_name]:
                    ol = str(opt).lower()
                    ol_stem = _stem(ol)
                    if rv_stem == ol_stem or rv_stem == ol or rv_l == ol_stem:
                        match_opt = opt
                        break
            if not match_opt:
                # Substring-fallback: "kommuneplan" ⊂ "kommuneplantillæg" må IKKE matche,
                # så vi kræver at stem-formerne er identiske eller at den ene starter med den anden
                # og længdeforskellen er ≤ 2 (bøjning).
                for opt in filter_options[matched_name]:
                    ol = str(opt).lower()
                    if (rv_l.startswith(ol) or ol.startswith(rv_l)) and abs(len(rv_l) - len(ol)) <= 3:
                        match_opt = opt
                        break
            if match_opt and match_opt not in valid:
                valid.append(match_opt)
        if valid:
            suggested[matched_name] = valid
    return suggested


def omformuler_opfoelgning(spoergsmaal: str, historik: list) -> str:
    """Omskriv et opfølgningsspørgsmål til et standalone-spørgsmål baseret på chat-historik.
    Hvis spørgsmålet allerede er standalone eller der ikke er historik, returneres uændret."""
    if not historik or len(historik) < 2 or not spoergsmaal:
        return spoergsmaal
    # Byg kort kontekst fra de sidste 4 beskeder
    kort_hist = []
    for msg in historik[-4:]:
        rolle = "Bruger" if msg.get("rolle") == "bruger" else "Assistent"
        t = (msg.get("tekst") or "")[:300]
        kort_hist.append(f"{rolle}: {t}")
    hist_str = "\n".join(kort_hist)
    prompt = (
        "Omskriv det sidste brugerspørgsmål til et selvstændigt spørgsmål baseret på samtalekonteksten. "
        "Hvis spørgsmålet allerede er selvstændigt, returnér det uændret. "
        "Returnér KUN det omskrevne spørgsmål – ingen forklaring.\n\n"
        f"SAMTALE:\n{hist_str}\n\n"
        f"SIDSTE SPØRGSMÅL: {spoergsmaal}\n\n"
        "OMSKREVET SPØRGSMÅL:"
    )
    omskrevet = llm_haiku(prompt, max_tokens=200)
    omskrevet = (omskrevet or "").strip().strip('"').strip("'")
    if not omskrevet or len(omskrevet) < 5:
        return spoergsmaal
    return omskrevet


def llm_rerank(query: str, kandidater: list, top_n: int = 8) -> list:
    """Rerank kandidater med Haiku-scoring (v1 har ingen Voyage Rerank — se
    modul-docstring). kandidater = liste af dicts med mindst 'Titel','Dato','Tekst'.
    Returnerer top_n sorteret bedst-først."""
    if not kandidater or len(kandidater) <= top_n:
        return kandidater[:top_n]

    linjer = []
    for i, k in enumerate(kandidater):
        try:
            dato = pd.Timestamp(k.get("Dato")).strftime("%d.%m.%Y")
        except Exception:
            dato = "-"
        titel = (k.get("Titel") or "")[:120]
        kerne = udtræk_kerneafsnit(k.get("Tekst") or "", max_tegn=500).replace("\n", " ")[:400]
        linjer.append(f"[{i}] {dato} – {titel}\n    {kerne}")
    oversigt = "\n\n".join(linjer)
    prompt = (
        f"Du vurderer relevansen af juridiske afgørelser for dette spørgsmål:\n"
        f"SPØRGSMÅL: {query}\n\n"
        f"KANDIDATER ({len(kandidater)} stk):\n{oversigt}\n\n"
        f"Vurder hver kandidat 0-10 for direkte relevans for spørgsmålet. "
        f"Returnér KUN de {top_n} mest relevante indekser (0-baserede), komma-separeret, bedste først. "
        f"Ingen forklaring – kun tal.\n\n"
        f"TOP {top_n}:"
    )
    svar = llm_haiku(prompt, max_tokens=100)
    if not svar:
        return kandidater[:top_n]
    tal = [int(x) for x in re.findall(r"\d+", svar) if int(x) < len(kandidater)]
    seen: set[int] = set()
    valgte: list[int] = []
    for t in tal:
        if t not in seen:
            seen.add(t)
            valgte.append(t)
        if len(valgte) >= top_n:
            break
    if not valgte:
        return kandidater[:top_n]
    for i in range(len(kandidater)):
        if len(valgte) >= top_n:
            break
        if i not in seen:
            valgte.append(i)
    return [kandidater[i] for i in valgte[:top_n]]


def byg_fokuseret_kontekst(query: str, docs: list, max_chunks_per_doc: int = 5,
                           chunk_size: int = 400, max_total_chars: int = 60_000) -> str:
    """Chunk hvert dokument og vælg de mest relevante afsnit vha. mini-TF-IDF
    mod query (keyword-baseret — v1 har ingen embedding-vektorer at score
    chunks med). Returnerer formateret kontekst med [Kilde N]-headers."""
    if not docs:
        return ""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as _cos
    except ImportError:
        return "\n\n".join(
            f"[Kilde {i+1}] {_datostr(d['Dato'])} – {d['Titel']}\n"
            f"{udtræk_kerneafsnit(d.get('Tekst') or '', max_tegn=4000)}"
            for i, d in enumerate(docs)
        )

    all_chunks: list[tuple[int, str]] = []
    for i, d in enumerate(docs):
        kerne = udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=8000)
        chunks = chunk_tekst(kerne, titel="", chunk_size=chunk_size, overlap=80)
        if not chunks:
            chunks = [kerne[:3000]] if kerne else [d.get("Titel", "")]
        for c in chunks:
            all_chunks.append((i, c))
    if not all_chunks:
        return ""

    chunk_texts = [c for _, c in all_chunks]
    try:
        mini_vec = TfidfVectorizer(max_features=20_000, ngram_range=(1, 2), sublinear_tf=True)
        chunk_mat = mini_vec.fit_transform(chunk_texts)
        qv = mini_vec.transform([query])
        scores = _cos(qv, chunk_mat).flatten()
    except Exception:
        scores = [1.0] * len(all_chunks)

    from collections import defaultdict
    kilde_chunks: dict[int, list] = defaultdict(list)
    for idx, (kilde_i, chunk) in enumerate(all_chunks):
        kilde_chunks[kilde_i].append((float(scores[idx]), chunk))

    dele = []
    total_chars = 0
    for i, d in enumerate(docs):
        header = f"[Kilde {i+1}] {_datostr(d['Dato'])} – {d['Titel']}"
        best = sorted(kilde_chunks.get(i, []), key=lambda x: -x[0])[:max_chunks_per_doc]
        best_texts = [c for _, c in best]
        content = "\n[…]\n".join(best_texts) if best_texts \
            else udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=2000)
        entry = f"{header}\n{content}"
        if total_chars + len(entry) > max_total_chars:
            remaining = max_total_chars - total_chars
            if remaining > 500:
                dele.append(entry[:remaining] + "…")
            break
        dele.append(entry)
        total_chars += len(entry)
    return "\n\n".join(dele)


SYSTEM_PROMPT = (
    "Du er en juridisk assistent specialiseret i dansk forsikringsret og "
    "Ankenævnet for Forsikrings praksis om ejerskifteforsikring. "
    "Dine brugere er professionelle jurister og forsikringsfolk – giv "
    "præcise, faktabaserede svar.\n\n"
    "REGLER:\n"
    "1. Besvar spørgsmålet KUN baseret på de vedlagte kendelser. Opfind ikke fakta.\n"
    "2. Brug kildeformatet [Kilde X] konsekvent – ALDRIG sagsnumre eller datoer som reference.\n"
    "3. Svar på dansk. Strukturér med overskrifter og afsnit.\n"
    "4. Understøt påstande med ordret citat i anførselstegn, fx: Nævnet udtalte: \"...\" [Kilde 3]. "
    "Citér KUN tekst der ordret fremgår af kilden – parafrasér aldrig som citat.\n"
    "5. Identificér mønstre på tværs af kendelserne — fast praksis vs. variation. "
    "Angiv evt. fordelingen (fx \"3 af 5 kendelser giver klager medhold\").\n"
    "6. Nævn relevant lovhjemmel (lov om forbrugerbeskyttelse §§, forsikringsaftaleloven mv.) når det fremgår.\n"
    "7. Hvis kilderne ikke besvarer spørgsmålet, skriv det eksplicit. Gæt aldrig.\n"
    "8. Ved opfølgningsspørgsmål: brug den tidligere samtale – kilderne har samme nummerering."
)


def byg_prompt(spørgsmål: str, docs: list, historik: list | None = None) -> list:
    """Byg content-blok-listen der sendes til Claude — struktur og prompt-caching
    som i ejnar/pages/ejnar.py::_byg_prompt.

    NB på historik: Streamlit-appen appender det aktuelle spørgsmål til
    historikken FØR kaldet og skærer det fra med [:-1]. Web-frontenden sender
    kun afsluttede ture (spørgsmålet kommer separat), så her bruges HELE
    historikken — et [:-1] ville smide det seneste assistent-svar væk, netop
    dét et opfølgningsspørgsmål typisk refererer til."""
    kontekst = byg_fokuseret_kontekst(spørgsmål, docs)
    historik_tekst = ""
    if historik:
        for msg in historik:
            rolle = "Bruger" if msg.get("rolle") == "bruger" else "Assistent"
            historik_tekst += f"\n{rolle}: {msg.get('tekst', '')}\n"
    samtale_blok = f"\nTIDLIGERE SAMTALE:{historik_tekst}\n" if historik_tekst.strip() else ""
    kilde_liste = "\n".join(
        f"[Kilde {i+1}] = {_datostr(d['Dato'])} – {d['Titel'][:80]}"
        for i, d in enumerate(docs)
    )
    return [
        {"type": "text", "text": f"{SYSTEM_PROMPT}\n\nKILDEREGISTER:\n{kilde_liste}"},
        {"type": "text", "text": f"\nKENDELSER:\n{kontekst}\n", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": f"{samtale_blok}SPØRGSMÅL: {spørgsmål}\n\nSVAR:"},
    ]


def smart_retrieval(spørgsmål: str, df, vec, mat, sub_idx: list | None,
                    historik: list | None, filter_options: dict | None = None):
    """Orkestrering: klassificér query → filtrér → TF-IDF-søg → Haiku-rerank.
    Returnerer (standalone_spørgsmål, kilder). Ingen Voyage/embeds i v1 —
    se hybrid_retrieval i ejnar/shared.py for hvordan semantik lægges til senere."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=3 if filter_options else 2) as pool:
        f1 = pool.submit(klassificer_query, spørgsmål)
        f2 = pool.submit(omformuler_opfoelgning, spørgsmål, historik or [])
        f3 = pool.submit(auto_filter_query, spørgsmål, filter_options) if filter_options else None
        qtype = f1.result()
        standalone = f2.result()
        auto_filters = f3.result() if f3 else {}

    top_retrieve, top_final = qtype["top_retrieve"], qtype["top_final"]
    corpus_size = len(sub_idx) if sub_idx else len(df)
    if corpus_size > 500:
        top_retrieve, top_final = max(top_retrieve, 100), max(top_final, 15)
    elif corpus_size > 200:
        top_retrieve, top_final = max(top_retrieve, 70), max(top_final, 12)

    eff_sub, prefiltered = apply_auto_filters(df, sub_idx, auto_filters)

    def _do(sub):
        return tfidf_søg(standalone, df, vec, mat, sub_idx=sub, top_n=top_retrieve, ekspander=False)

    hits = _do(eff_sub)
    kand = hits.to_dict("records") if len(hits) > 0 else []
    seen = {r.get("Link", "") for r in kand}
    kand = kand + _hist_kilder(historik, seen)
    rerankede = llm_rerank(standalone, kand, top_n=top_final)
    if len(rerankede) < 3 and prefiltered:
        hits = _do(sub_idx)
        kand = hits.to_dict("records") if len(hits) > 0 else []
        seen = {r.get("Link", "") for r in kand}
        kand = kand + _hist_kilder(historik, seen)
        rerankede = llm_rerank(standalone, kand, top_n=top_final)

    auto_filter_info = {
        "suggested": auto_filters,
        "applied": prefiltered,
        "before": len(sub_idx) if sub_idx else len(df),
        "after": len(eff_sub) if eff_sub else 0,
    }
    return standalone, rerankede, auto_filter_info


def _hist_kilder(historik, seen: set, max_n: int = 10) -> list:
    """Kilder fra tidligere svar i samtalen — føjes til kandidatpuljen FØR
    rerank, så rerankeren vurderer dem mod det NYE spørgsmål."""
    out = []
    for msg in reversed(historik or []):
        if msg.get("rolle") == "assistent":
            for k in msg.get("kilder", []) or []:
                lnk = k.get("Link", "")
                if lnk and lnk not in seen:
                    seen.add(lnk)
                    out.append(k)
                    if len(out) >= max_n:
                        return out
    return out

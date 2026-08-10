"""TF-IDF-søgning (keyword-baseret — v1 har bevidst INGEN Voyage/semantisk søgning,
jf. beslutningen om at undgå ekstra API-omkostninger indtil videre).

1:1 porteret fra ejnar/shared.py + ejnar/pages/ejnar.py — hold i sync.

NB: tfidf_søg() kaldes altid med ekspander=False i denne backend (ekspander=True
ville kræve udvid_query(), som er et Haiku-kald og hører til rag.py — bevidst
ikke wired op i v1's keyword-only søgevej)."""
from __future__ import annotations

import re

import numpy as np

from .text import byg_indeks_tekst


def byg_tfidf_index(df):
    """Byg TF-IDF-indekset over hele df — svarer til Streamlit-appens
    (cachede) build_index(). Kaldes én gang ved data-load."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    texts = (byg_indeks_tekst(t, tx) for t, tx in
             zip(df["Titel"].astype(str), df["Tekst"].astype(str)))
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2), min_df=2,
                          sublinear_tf=True, tokenizer=dansk_tokenizer, token_pattern=None)
    mat = vec.fit_transform(texts)
    return vec, mat


_dk_stemmer = None


def _get_dk_stemmer():
    global _dk_stemmer
    if _dk_stemmer is None:
        try:
            from nltk.stem.snowball import SnowballStemmer
            _dk_stemmer = SnowballStemmer("danish")
        except ImportError:
            return None
    return _dk_stemmer


_TOKEN_RE = re.compile(r"[a-zæøåA-ZÆØÅ][a-zæøåA-ZÆØÅ\-]{1,}")


def dansk_tokenizer(text: str) -> list:
    """Tokenisér og stem dansk tekst med Snowball Danish stemmer.
    Bruges som custom analyzer i TfidfVectorizer for bedre matching
    af bøjningsformer (afgørelser→afgør, planloven→planlov osv.)."""
    stemmer = _get_dk_stemmer()
    tokens = _TOKEN_RE.findall(text.lower())
    if stemmer is None:
        return tokens
    return [stemmer.stem(t) for t in tokens]


def apply_auto_filters(df, sub_idx, auto_filters, min_hits: int = 3):
    """Apply auto-detected filters to narrow sub_idx within existing user filters.
    Returns (narrowed_idx, was_narrowed)."""
    if not auto_filters or not sub_idx:
        return sub_idx, False
    narrowed = []
    for idx in sub_idx:
        row = df.iloc[idx]
        match = True
        for col, vals in auto_filters.items():
            if col not in row.index:
                continue
            cell = row[col]
            if isinstance(cell, list):
                if not any(v in cell for v in vals):
                    match = False
                    break
            else:
                # None/NaN betyder at rækken ikke har den egenskab — ekskludér
                if cell is None or (isinstance(cell, float) and cell != cell):
                    match = False
                    break
                if cell not in vals:
                    match = False
                    break
        if match:
            narrowed.append(idx)
    if len(narrowed) >= min_hits and len(narrowed) < len(sub_idx) * 0.9:
        return narrowed, True
    return sub_idx, False


def rrf_merge(rangeringer: list, k: int = 60) -> dict:
    """Reciprocal Rank Fusion: kombinér flere rangeringer til én score.
    rangeringer = liste af lister, hvor hver indre liste er et globalt indeks sorteret bedst-først."""
    score = {}
    for rangering in rangeringer:
        for rank, idx in enumerate(rangering):
            score[idx] = score.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return score


def tfidf_søg(query, df, vec, mat, sub_idx=None, top_n=30, ekspander=False):
    from sklearn.metrics.pairwise import cosine_similarity
    if vec is None or mat is None:
        return df.iloc[0:0].copy()
    eff = udvid_query(query) if ekspander else query
    qv = vec.transform([eff])

    def _boost(idx, base):
        try:
            aar = int(df.at[idx, "År"])
            decay = 1.0 + max(0, min(0.15, (aar - 2017) * 0.02))
            return float(base) * decay
        except Exception:
            return float(base)

    if sub_idx is not None:
        scores = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local = scores.argsort()[-top_n * 2:][::-1]
        kand = [(sub_idx[i], scores[i]) for i in top_local if scores[i] > 0.01]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top = scores.argsort()[-top_n * 2:][::-1]
        kand = [(int(i), scores[i]) for i in top if scores[i] > 0.01]
    kand = [(g, _boost(g, s)) for g, s in kand]
    kand.sort(key=lambda x: x[1], reverse=True)
    kand = kand[:top_n]
    if not kand:
        return df.iloc[0:0].copy()
    idxs = [g for g, _ in kand]
    res = df.loc[idxs].copy() if sub_idx is not None else df.iloc[idxs].copy()
    res["_score"] = [s for _, s in kand]
    return res.reset_index(drop=True)


"""Semantisk søgning (Voyage) — porteret fra ejnar/shared.py, men SOVENDE i v1:
alt her aktiveres først når ENABLE_SEMANTIC=1 og VOYAGE_API_KEY er sat.
Uden dem kører systemet keyword-only præcis som hidtil, og intet koster penge.

Portering ift. shared.py:
- Kun Voyage (voyage-3-large, 1024d) — chunk-indekset er bygget med den model;
  OpenAI-fallback-grenen er bevidst udeladt.
- Kun chunk-format-indekset (dict med chunk_to_doc) — legacy doc-niveau-
  formatet er udeladt; loaderen producerer aldrig det.
- Alle API-fejl degraderer stille til keyword-adfærd (samme princip som
  llm_haiku): semantik er en kvalitetsboost, aldrig kritisk sti."""
from __future__ import annotations

import glob
import os
import time

import numpy as np
import requests

from ..config import get_settings
from .claude import llm_haiku
from .search import rrf_merge

# Geometri fra ejnar/build_embeddings.py: CHUNK_SIZE=1000 tokens ≈ 770 ord,
# CHUNK_OVERLAP=150 tokens ≈ 115 ord → stride 655 ord pr. chunk.
_BUILD_CHUNK_ORD = 770
_BUILD_STRIDE = 655

_QV_MEMO: dict[str, np.ndarray] = {}


# ── Voyage API ────────────────────────────────────────────────────────────────
def _embed_batch(texts: list, input_type: str = "query", retries: int = 2) -> "np.ndarray | None":
    key = get_settings().voyage_api_key
    if not key or not texts:
        return None
    for attempt in range(retries + 1):
        try:
            r = requests.post(
                "https://api.voyageai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"input": texts, "model": "voyage-3-large",
                      "input_type": input_type, "truncation": True},
                timeout=60,
            )
            if r.ok:
                data = r.json().get("data", [])
                return np.array([d["embedding"] for d in data], dtype=np.float32)
            if r.status_code == 429 and attempt < retries:
                time.sleep(min(2 ** (attempt + 1), 10))
                continue
            return None
        except Exception:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            return None
    return None


def embed_query(query: str) -> "np.ndarray | None":
    """Embed én forespørgsel som normaliseret vektor (cosine via dot product)."""
    if not query:
        return None
    arr = _embed_batch([query], input_type="query")
    if arr is None or len(arr) == 0:
        return None
    v = arr[0]
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def embed_query_memo(query: str) -> "np.ndarray | None":
    """Memoiseret query-embedding — retrieval og kontekst-bygning i samme tur
    skal ikke koste to API-kald."""
    if query in _QV_MEMO:
        return _QV_MEMO[query]
    qv = embed_query(query)
    if qv is not None:
        if len(_QV_MEMO) > 8:
            _QV_MEMO.clear()
        _QV_MEMO[query] = qv
    return qv


def hyde_embed(query: str) -> "np.ndarray | None":
    """HyDE: embed et hypotetisk nævns-uddrag (Haiku) sammen med spørgsmålet —
    rammer afgørelsernes terminologi bedre end det rå spørgsmål. Fallback: rå query."""
    if not query:
        return None
    hyp = llm_haiku(
        "Du er Ankenævnet for Forsikring og afgør sager om ejerskifteforsikring. "
        "Skriv et kort uddrag (100-150 ord) af en hypotetisk nævnskendelse "
        "der besvarer dette spørgsmål. Brug nævnets typiske sprog og forsikringsretlige "
        "termer (mangler ved bygning, dækning, selvrisiko, lov om forbrugerbeskyttelse "
        "ved erhvervelse af fast ejendom mv., tilstandsrapport, byggeskik, levetid mv.). "
        f"Skriv KUN uddraget – ingen indledning.\n\nSpørgsmål: {query}\n\nUddrag:",
        max_tokens=250,
    )
    if not hyp or len(hyp) < 30:
        return embed_query(query)
    arr = _embed_batch([f"{query}\n\n{hyp}"], input_type="query")
    if arr is None or len(arr) == 0:
        return embed_query(query)
    v = arr[0]
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def voyage_rerank(query: str, documents: list, top_n: int = 8) -> "list | None":
    """Voyage Rerank 2. Returnerer [(orig_index, score), …] eller None ved
    fejl/manglende nøgle — kalderen falder så tilbage til Haiku-rerank."""
    key = get_settings().voyage_api_key
    if not key or not documents:
        return None
    try:
        r = requests.post(
            "https://api.voyageai.com/v1/rerank",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"query": query, "documents": documents, "model": "rerank-2", "top_k": top_n},
            timeout=60,
        )
        if not r.ok:
            return None
        return [(d["index"], d["relevance_score"]) for d in r.json().get("data", [])]
    except Exception:
        return None


# ── Indeks-indlæsning (lokale .npz-filer — kræver INGEN nøgle) ───────────────
def load_chunk_embeds(df, data_dir: str) -> "dict | None":
    """Link-baseret indlæsning af chunk-embeddings fra <data_dir>/embeds/.

    Chunk→doc remappes via kendelses-links til den AKTUELLE df (build og app
    deduplikerer forskelligt — links er eneste stabile nøgle; det var netop
    dén lektie der genoplivede indekset i Streamlit-versionen). Kræver at
    mindst halvdelen af df er dækket, ellers kasseres indekset som forældet."""
    if df is None or len(df) == 0 or "Link" not in df.columns:
        return None
    link_til_idx = {str(l): i for i, l in enumerate(df["Link"])}
    kandidater = [p for p in glob.glob(os.path.join(data_dir, "embeds",
                                                    "*__voyage__voyage-3-large__*d_*c.npz"))
                  if "__links" not in os.path.basename(p)]
    for path in sorted(kandidater):
        try:
            data = np.load(path, allow_pickle=True)
            if "embeddings" not in data.files or "chunk_to_doc" not in data.files:
                continue
            if "doc_links" in data.files:
                doc_links = [str(x) for x in data["doc_links"]]
            else:
                sidecar = path[:-4] + "__links.npz"
                if not os.path.exists(sidecar):
                    continue
                doc_links = [str(x) for x in np.load(sidecar, allow_pickle=True)["doc_links"]]
            vectors = data["embeddings"]
            if vectors.dtype == np.float16:
                vectors = vectors.astype(np.float32)
            ctd = data["chunk_to_doc"].astype(np.int64)
            if len(doc_links) <= int(ctd.max()):
                continue
            arr_map = np.array([link_til_idx.get(l, -1) for l in doc_links], dtype=np.int64)
            ny_ctd = arr_map[ctd]
            keep = ny_ctd >= 0
            n_mapped = int((arr_map >= 0).sum())
            if n_mapped < max(1, len(df) // 2):
                continue
            if not keep.all():
                vectors, ny_ctd = vectors[keep], ny_ctd[keep]
            return {"vectors": vectors, "chunk_to_doc": ny_ctd.astype(np.int32),
                    "n_docs": len(df), "model": "voyage-3-large",
                    "dækning": (n_mapped, len(df))}
        except Exception:
            continue
    return None


# ── Retrieval ─────────────────────────────────────────────────────────────────
def embedding_soeg(query: str, df, embeds, sub_idx=None, top_n: int = 30,
                   use_hyde: bool = True) -> list:
    """Chunk-niveau semantisk søgning: max chunk-score pr. kendelse.
    Returnerer [(global_doc_idx, score), …] bedst-først; tom liste ved fejl."""
    if not isinstance(embeds, dict) or "chunk_to_doc" not in embeds or df is None or len(df) == 0:
        return []
    qv = hyde_embed(query) if use_hyde else embed_query_memo(query)
    if qv is None:
        qv = embed_query_memo(query)
    if qv is None:
        return []

    vectors, chunk_to_doc = embeds["vectors"], embeds["chunk_to_doc"]
    all_scores = vectors @ qv

    if sub_idx is not None and len(sub_idx) > 0:
        mask = np.isin(chunk_to_doc, np.asarray(sub_idx, dtype=np.int32))
        if not mask.any():
            return []
        chunk_indices = np.where(mask)[0]
        scores_sub = all_scores[chunk_indices]
        chunks_doc = chunk_to_doc[chunk_indices]
    else:
        scores_sub, chunks_doc = all_scores, chunk_to_doc

    if len(scores_sub) == 0:
        return []
    n_top = min(len(scores_sub), top_n * 8)
    top_local = np.argpartition(-scores_sub, n_top - 1)[:n_top]
    top_local = top_local[np.argsort(-scores_sub[top_local])]

    seen_docs: dict[int, float] = {}
    for li in top_local:
        d, s = int(chunks_doc[li]), float(scores_sub[li])
        if d not in seen_docs or s > seen_docs[d]:
            seen_docs[d] = s
    return [(d, s) for d, s in sorted(seen_docs.items(), key=lambda x: -x[1])[:top_n]
            if s > 0.15]


def hybrid_retrieval(query: str, df, vec, mat, embeds, sub_idx=None,
                     top_retrieve: int = 40, top_final: int = 20) -> list:
    """TF-IDF + embeddings via Reciprocal Rank Fusion → globale indekser
    bedst-først. Falder tilbage til ren TF-IDF-rangering hvis embeds mangler
    eller embedding-kaldet fejler."""
    from sklearn.metrics.pairwise import cosine_similarity as _cos
    qv = vec.transform([query])
    if sub_idx is not None and len(sub_idx) > 0:
        tfidf_scores = _cos(qv, mat[sub_idx]).flatten()
        order = np.argsort(-tfidf_scores)[:top_retrieve]
        tfidf_ranking = [int(sub_idx[i]) for i in order if tfidf_scores[i] > 0.01]
    else:
        tfidf_scores = _cos(qv, mat).flatten()
        order = np.argsort(-tfidf_scores)[:top_retrieve]
        tfidf_ranking = [int(i) for i in order if tfidf_scores[i] > 0.01]

    rangeringer = [tfidf_ranking]
    if embeds is not None:
        emb_ranking = [g for g, _ in embedding_soeg(query, df, embeds,
                                                    sub_idx=sub_idx, top_n=top_retrieve)]
        if emb_ranking:
            rangeringer.append(emb_ranking)

    fused = rrf_merge(rangeringer, k=60)
    if not fused:
        return tfidf_ranking[:top_final]
    return [idx for idx, _ in sorted(fused.items(), key=lambda x: -x[1])[:top_final]]


# ── Semantisk chunk-udvælgelse til svar-konteksten ───────────────────────────
def chunk_span_tekst(tekst: str, ordinal: int) -> str:
    """Rekonstruér (tilnærmet) chunk nr. `ordinal` med build-geometrien. Build
    og app renser HTML let forskelligt, så spans kan være forskudt få ord —
    acceptabelt til LLM-kontekst hvor vi blot skal ramme det rigtige afsnit."""
    ord_liste = (tekst or "").split()
    if len(ord_liste) <= _BUILD_CHUNK_ORD:
        return tekst or ""
    start = ordinal * _BUILD_STRIDE
    if start >= len(ord_liste):
        start = max(0, len(ord_liste) - _BUILD_CHUNK_ORD)
    return " ".join(ord_liste[start:start + _BUILD_CHUNK_ORD])


def semantisk_chunk_udvalg(query: str, docs: list, embeds, link_til_idx: dict,
                           max_chunks_per_doc: int = 5) -> dict:
    """Vælg de semantisk mest relevante chunks pr. kilde-dokument.
    Returnerer {doc_position: kontekst-tekst} for de dokumenter det lykkedes
    for — resten falder tilbage til keyword-udvælgelsen i rag.py."""
    if not isinstance(embeds, dict) or "chunk_to_doc" not in embeds or not link_til_idx:
        return {}
    qv = embed_query_memo(query)
    if qv is None:
        return {}
    vectors, ctd = embeds["vectors"], embeds["chunk_to_doc"]
    ud: dict[int, str] = {}
    for i, d in enumerate(docs):
        gidx = link_til_idx.get(str(d.get("Link", "")))
        if gidx is None:
            continue
        vec_idx = np.where(ctd == gidx)[0]
        if vec_idx.size == 0:
            continue
        scores = vectors[vec_idx] @ qv
        orden = np.argsort(-scores)[:max_chunks_per_doc]
        ordinaler = sorted(int(o) for o in orden)
        tekst = d.get("Tekst") or ""
        spans = [s for s in (chunk_span_tekst(tekst, o) for o in ordinaler) if s.strip()]
        if spans:
            ud[i] = "\n[…]\n".join(dict.fromkeys(spans))
    return ud

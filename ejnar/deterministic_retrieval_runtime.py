"""Deterministic retrieval wrapper for Ejnar's hybrid candidate generation.

Independent CI hosts can produce slightly different floating-point cosine similarities
because sparse floating-point accumulation depends on the underlying CPU/BLAS runtime.
Near a top-k boundary that can change result order or even candidate membership.

The lexical branch therefore converts the already-normalised TF-IDF feature weights to
fixed-point integers *before* similarity is accumulated. The document/query dot product
is then exact integer arithmetic, with the global dataframe index as a deterministic
secondary key. This removes host-dependent accumulation noise at its source instead of
rounding an already-divergent floating-point cosine score afterwards.

The fixed-point scale is deliberately fine (1e7): ordinary score differences are
preserved while sub-1e-7 feature-weight noise collapses. Frozen qrels and cross-host CI
protect against an overly coarse scale.
"""
from __future__ import annotations

import logging
import threading
from typing import Any, Iterable


_LOG = logging.getLogger("ejnar.deterministic_retrieval")
DEFAULT_WEIGHT_SCALE = 10_000_000
DEFAULT_MIN_LEXICAL_SCORE = 0.01
DEFAULT_EMBEDDING_SCORE_DECIMALS = 10

_FIXED_MATRIX_CACHE: dict[tuple[int, int], tuple[Any, Any]] = {}
_FIXED_MATRIX_LOCK = threading.Lock()


def _quantise(score: Any, *, decimals: int = DEFAULT_EMBEDDING_SCORE_DECIMALS) -> float:
    return round(float(score), max(0, int(decimals)))


def stable_score_ranking(
    scores: Iterable[Any],
    global_indices: Iterable[int],
    *,
    top_n: int,
    min_score: float,
    decimals: int = DEFAULT_EMBEDDING_SCORE_DECIMALS,
) -> list[int]:
    """Compatibility/helper ranking for already-computed floating scores.

    Production lexical TF-IDF no longer uses this helper; its scores are accumulated in
    fixed-point integer arithmetic by :func:`fixed_point_tfidf_ranking`.
    """
    if top_n <= 0:
        return []
    pairs: list[tuple[float, int]] = []
    for score, idx in zip(scores, global_indices):
        quantised = _quantise(score, decimals=decimals)
        if quantised <= min_score:
            continue
        pairs.append((quantised, int(idx)))
    pairs.sort(key=lambda item: (-item[0], item[1]))
    return [idx for _, idx in pairs[:top_n]]


def _fixed_point_matrix(matrix: Any, *, weight_scale: int) -> Any:
    """Quantise a TF-IDF CSR matrix once and cache the exact integer representation."""
    import numpy as np
    from scipy.sparse import csr_matrix

    scale = max(1, int(weight_scale))
    key = (id(matrix), scale)
    with _FIXED_MATRIX_LOCK:
        cached = _FIXED_MATRIX_CACHE.get(key)
        if cached is not None and cached[0] is matrix:
            return cached[1]

    csr = matrix.tocsr(copy=False)
    # TF-IDF weights are in [0, 1]. int32 safely stores scale<=~2e9; the
    # multiplication with the int64 query vector below promotes accumulation to int64.
    data = np.rint(csr.data * scale).astype(np.int32, copy=False)
    fixed = csr_matrix(
        (data, csr.indices.copy(), csr.indptr.copy()),
        shape=csr.shape,
        dtype=np.int32,
    )
    fixed.eliminate_zeros()

    with _FIXED_MATRIX_LOCK:
        # Streamlit may rebuild an index after data/filter changes. Keep the cache small
        # and hold the original matrix reference to protect against Python id reuse.
        if len(_FIXED_MATRIX_CACHE) >= 3:
            _FIXED_MATRIX_CACHE.clear()
        _FIXED_MATRIX_CACHE[key] = (matrix, fixed)
    return fixed


def fixed_point_tfidf_ranking(
    query_vector: Any,
    fixed_document_matrix: Any,
    global_indices: Iterable[int],
    *,
    top_n: int,
    min_score: float = DEFAULT_MIN_LEXICAL_SCORE,
    weight_scale: int = DEFAULT_WEIGHT_SCALE,
) -> list[int]:
    """Rank normalised TF-IDF vectors using exact fixed-point integer dot products.

    ``fixed_document_matrix`` must already contain document weights multiplied by
    ``weight_scale`` and rounded to integers. The query is quantised identically. Since
    both TF-IDF rows are L2-normalised, their floating cosine equals their dot product;
    the fixed-point score approximates that cosine by ``score * weight_scale**2``.
    """
    import numpy as np

    if top_n <= 0:
        return []
    scale = max(1, int(weight_scale))
    qv = query_vector.tocsr(copy=False)
    if qv.shape[0] != 1 or qv.nnz == 0:
        return []
    if fixed_document_matrix.shape[0] == 0:
        return []

    q_dense = np.zeros(qv.shape[1], dtype=np.int64)
    q_dense[qv.indices] = np.rint(qv.data * scale).astype(np.int64, copy=False)
    if not np.any(q_dense):
        return []

    # Sparse(int32) @ dense(int64) yields exact int64 accumulation. No BLAS floating
    # reduction is involved, so identical TF-IDF feature weights produce identical
    # scores on every host.
    raw_scores = fixed_document_matrix.dot(q_dense)
    scores = np.asarray(raw_scores, dtype=np.int64).reshape(-1)
    indices = [int(idx) for idx in global_indices]
    if len(indices) != len(scores):
        raise ValueError("global_indices must match fixed_document_matrix rows")

    threshold = int(round(float(min_score) * scale * scale))
    pairs = [
        (int(score), idx)
        for score, idx in zip(scores, indices)
        if int(score) > threshold
    ]
    pairs.sort(key=lambda item: (-item[0], item[1]))
    return [idx for _, idx in pairs[:top_n]]


def stable_embedding_ranking(
    hits: Iterable[tuple[int, Any]],
    *,
    top_n: int,
    decimals: int = DEFAULT_EMBEDDING_SCORE_DECIMALS,
) -> list[int]:
    pairs = [(_quantise(score, decimals=decimals), int(idx)) for idx, score in hits]
    pairs.sort(key=lambda item: (-item[0], item[1]))
    return [idx for _, idx in pairs[: max(0, top_n)]]


def stable_rrf_order(scores: dict[int, float], *, top_n: int) -> list[int]:
    return [
        int(idx)
        for idx, _ in sorted(
            scores.items(),
            key=lambda item: (-float(item[1]), int(item[0])),
        )[: max(0, top_n)]
    ]


def install_deterministic_retrieval_runtime(
    shared_module: Any | None = None,
    *,
    weight_scale: int = DEFAULT_WEIGHT_SCALE,
) -> bool:
    """Replace base hybrid retrieval with host-independent lexical score accumulation."""
    if shared_module is None:
        import shared as shared_module  # type: ignore

    if getattr(shared_module, "_EJNAR_DETERMINISTIC_RETRIEVAL_INSTALLED", False):
        return False

    original_hybrid = shared_module.hybrid_retrieval

    def deterministic_hybrid(
        query: str,
        df: Any,
        vec: Any,
        mat: Any,
        embeds: Any,
        sub_idx: Any = None,
        top_retrieve: int = 40,
        top_final: int = 20,
    ) -> list[int]:
        try:
            qv = vec.transform([query])
            fixed_full = _fixed_point_matrix(mat, weight_scale=weight_scale)

            if sub_idx is not None and len(sub_idx) > 0:
                candidate_indices = [int(idx) for idx in sub_idx]
                # Avoid copying the full matrix in the common evaluation/app case where
                # the supplied candidate universe is simply 0..N-1.
                is_full_range = (
                    len(candidate_indices) == len(df)
                    and all(idx == pos for pos, idx in enumerate(candidate_indices))
                )
                fixed_candidates = fixed_full if is_full_range else fixed_full[candidate_indices]
            else:
                candidate_indices = list(range(len(df)))
                fixed_candidates = fixed_full

            tfidf_ranking = fixed_point_tfidf_ranking(
                qv,
                fixed_candidates,
                candidate_indices,
                top_n=max(0, int(top_retrieve)),
                min_score=DEFAULT_MIN_LEXICAL_SCORE,
                weight_scale=weight_scale,
            )
            rankings = [tfidf_ranking]

            if embeds is not None:
                # Embeddings are outside the lexical CI gate. Preserve the existing
                # semantic search, but make its returned near-ties deterministic.
                all_candidates = len(candidate_indices)
                emb_hits = shared_module.embedding_soeg(
                    query,
                    df,
                    embeds,
                    sub_idx=sub_idx,
                    top_n=max(1, all_candidates),
                )
                emb_ranking = stable_embedding_ranking(
                    emb_hits,
                    top_n=max(0, int(top_retrieve)),
                )
                if emb_ranking:
                    rankings.append(emb_ranking)

            fused = shared_module.rrf_merge(rankings, k=60)
            if not fused:
                return tfidf_ranking[: max(0, int(top_final))]
            return stable_rrf_order(fused, top_n=max(0, int(top_final)))
        except Exception:  # pragma: no cover - production fail-open safety net
            _LOG.exception("Deterministic retrieval failed; using legacy hybrid retrieval")
            return original_hybrid(
                query,
                df,
                vec,
                mat,
                embeds,
                sub_idx=sub_idx,
                top_retrieve=top_retrieve,
                top_final=top_final,
            )

    shared_module.hybrid_retrieval = deterministic_hybrid
    shared_module._EJNAR_DETERMINISTIC_RETRIEVAL_ORIGINAL = original_hybrid
    shared_module._EJNAR_DETERMINISTIC_RETRIEVAL_WEIGHT_SCALE = int(weight_scale)
    shared_module._EJNAR_DETERMINISTIC_RETRIEVAL_INSTALLED = True
    return True

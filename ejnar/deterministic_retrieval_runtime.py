"""Deterministic retrieval wrapper for Ejnar's hybrid candidate generation.

Independent CI hosts can produce cosine similarities that differ in the last few floating
point bits. Near the top-k boundary those differences are enough to change result order or
even the candidate set. Human review pools and frozen qrels must not depend on the CPU/
BLAS host that happened to run the build.

This runtime mirrors the existing hybrid retrieval policy but quantises similarity scores
at a deliberately fine precision before ranking and uses the stable global dataframe
index as a secondary key. RRF ties are also broken by that global index.

The layer changes ranking only for numerical near-ties; ordinary score differences are
preserved. It is installed before the intent-aware wrappers so every downstream layer sees
the same deterministic candidate order.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable


_LOG = logging.getLogger("ejnar.deterministic_retrieval")
DEFAULT_SCORE_DECIMALS = 10


def _quantise(score: Any, *, decimals: int = DEFAULT_SCORE_DECIMALS) -> float:
    return round(float(score), max(0, int(decimals)))


def stable_score_ranking(
    scores: Iterable[Any],
    global_indices: Iterable[int],
    *,
    top_n: int,
    min_score: float,
    decimals: int = DEFAULT_SCORE_DECIMALS,
) -> list[int]:
    """Rank scores deterministically by quantised score then global index.

    The threshold is applied to the same quantised value used for ordering so a value
    within floating-point noise of the threshold cannot be admitted on one host and
    rejected on another.
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


def stable_embedding_ranking(
    hits: Iterable[tuple[int, Any]],
    *,
    top_n: int,
    decimals: int = DEFAULT_SCORE_DECIMALS,
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
    score_decimals: int = DEFAULT_SCORE_DECIMALS,
) -> bool:
    """Replace base hybrid retrieval with deterministic score ordering.

    Embedding search is broadened to all candidate indices before deterministic sorting.
    This avoids an unstable top-n cut inside the legacy embedding helper. The expensive
    embedding/dot-product work was already performed there; only the returned index list
    is larger. In lexical-only CI the embedding branch is not used.
    """
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
            from sklearn.metrics.pairwise import cosine_similarity

            qv = vec.transform([query])
            if sub_idx is not None and len(sub_idx) > 0:
                candidate_indices = [int(idx) for idx in sub_idx]
                tfidf_scores = cosine_similarity(qv, mat[candidate_indices]).flatten()
            else:
                candidate_indices = list(range(len(df)))
                tfidf_scores = cosine_similarity(qv, mat).flatten()

            tfidf_ranking = stable_score_ranking(
                tfidf_scores,
                candidate_indices,
                top_n=max(0, int(top_retrieve)),
                min_score=0.01,
                decimals=score_decimals,
            )
            rankings = [tfidf_ranking]

            if embeds is not None:
                # Fetch every threshold-passing embedding hit, then make the top-k cut
                # deterministically here instead of inside np.argsort on a near tie.
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
                    decimals=score_decimals,
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
    shared_module._EJNAR_DETERMINISTIC_RETRIEVAL_SCORE_DECIMALS = int(score_decimals)
    shared_module._EJNAR_DETERMINISTIC_RETRIEVAL_INSTALLED = True
    return True

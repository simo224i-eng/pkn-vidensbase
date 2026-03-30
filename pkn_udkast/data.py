"""Dataloading og TF-IDF søgning mod PKN miljøvurderingsafgørelser."""

import os
import re
import html as _html

import pandas as pd
import streamlit as st
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


# ── Sti til data ─────────────────────────────────────────────────────────────
# Data ligger i parent-dir (Harald-repoen). Kan overskrives med env var.
_DATA_PATH = os.environ.get(
    "PKN_DATA_PATH",
    os.path.join(os.path.dirname(__file__), "..", "pkn_miljoevurderingsloven_fuld_tekst.csv"),
)


def strip_html(text: str) -> str:
    """Fjern HTML-tags og unescape entities."""
    return _html.unescape(re.sub(r"<[^>]+>", " ", str(text)))


def _er_realitetsbehandlet_miljørapport(titel: str, tekst_ren: str) -> bool:
    """Filtrer til kun realitetsbehandlede miljørapport-sager."""
    t = titel.lower()
    txt = tekst_ren.lower()
    # Skal omhandle miljørapport (ikke screening)
    is_miljørapport = "miljørapport" in t or ("miljøvurdering" in t and "screening" not in t)
    # Skal have en faktisk vurdering
    has_vurdering = "planklagenævnets vurdering" in txt
    # Ikke afvisninger eller opsættende virkning
    not_afvist = "afviser klagen" not in txt and "afvisning" not in t
    not_opsættende = "opsættende virkning" not in t
    return is_miljørapport and has_vurdering and not_afvist and not_opsættende


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Indlæs kun realitetsbehandlede PKN miljørapport-afgørelser."""
    df = pd.read_csv(_DATA_PATH)
    df["Tekst_ren"] = df["Tekst"].apply(strip_html)
    mask = df.apply(lambda r: _er_realitetsbehandlet_miljørapport(r["Titel"], r["Tekst_ren"]), axis=1)
    df = df[mask].reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False)
def build_index(_n: int = 0):
    """Byg TF-IDF index. _n bruges til cache-invalidering."""
    df = load_data()
    vec = TfidfVectorizer(
        max_features=15000,
        ngram_range=(1, 2),
        min_df=2,
        sublinear_tf=True,
    )
    mat = vec.fit_transform(df["Tekst_ren"])
    return vec, mat


def find_relevante_sager(
    query: str,
    df: pd.DataFrame,
    vec: TfidfVectorizer,
    mat,
    top_n: int = 5,
) -> pd.DataFrame:
    """Find de mest relevante præcedensafgørelser via TF-IDF cosine similarity."""
    qv = vec.transform([query])
    scores = cosine_similarity(qv, mat).flatten()
    top_idx = scores.argsort()[-top_n:][::-1]
    result = df.iloc[top_idx].copy()
    result["_score"] = scores[top_idx]
    result = result[result["_score"] > 0.01]
    return result.reset_index(drop=True)

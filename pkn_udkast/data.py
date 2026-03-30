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


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Indlæs PKN miljøvurderingsafgørelser."""
    df = pd.read_csv(_DATA_PATH)
    df["Tekst_ren"] = df["Tekst"].apply(strip_html)
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

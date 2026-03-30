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

# ── Emnekategorier til emnespecifik matching ─────────────────────────────────
EMNE_KATEGORIER = {
    # Natur og arter
    "Natura 2000": ["natura 2000", "habitatområde", "fuglebeskyttelsesområde", "habitatdirektivet", "konsekvensvurdering", "lokalitetens integritet"],
    "Bilag IV-arter": ["bilag iv", "bilag iv-art", "flagermus", "vandsalamander", "springfrø", "markfirben", "odder", "økologisk funktionalitet"],
    "§3-natur": ["§ 3", "beskyttet natur", "naturbeskyttelseslov", "beskyttede naturtyper", "biodiversitet"],
    "Fugle og dyreliv": ["fugle", "dyreliv", "ynglefugle", "fuglebeskyttelse", "påvirkning af dyr"],
    # Vand
    "Grundvand": ["grundvand", "drikkevandsinteresser", "osd", "indvindingsopland", "grundvandsredegørelse", "nitratfølsom", "grundvandssænkning"],
    "Overfladevand": ["overfladevand", "vandløb", "vandrammedirektivet", "recipientvand", "udledning af overfladevand"],
    # Nabogener
    "Støj": ["støj", "støjniveau", "støjgrænse", "støjudbredelse", "støjvold", "vindmøllestøj", "trafikstøj", "virksomhedsstøj", "støjbekendtgørelsen"],
    "Skyggekast": ["skyggekast", "skyggegener", "skygge"],
    "Indbliksgener": ["indblik", "indbliksgener", "indsigtsgener", "lysforhold"],
    "Lugt": ["lugt", "lugtgener", "lugtemission"],
    # Trafik og infrastruktur
    "Trafik": ["trafik", "trafikbelastning", "trafikale", "vejkapacitet", "trafiksikkerhed", "parkeringsforhold", "adgangsvej"],
    # Landskab og kulturarv
    "Landskab": ["landskab", "visuel", "landskabelig", "landskabspåvirkning"],
    "Kulturarv": ["kulturarv", "kulturhistorisk", "kulturmiljø", "arkæologisk", "bevaringsværdi"],
    # Miljø og sundhed
    "Klima": ["klima", "co2", "klimatilpasning", "drivhusgas", "oversvømmelse"],
    "Jordforurening": ["jordforurening", "forurenet jord", "forureningsundersøgelse", "jord- og grundvandsforurening"],
    "Menneskers sundhed": ["menneskers sundhed", "sundhedsmæssig", "sundhedseffekt"],
    "Materielle goder": ["materielle goder", "ejendomsværdi", "værdiforringelse"],
    # Procesuelle emner
    "Alternativer": ["alternativ", "alternative placeringer", "0-alternativ", "nulalternativ"],
    "Afgrænsning af miljørapport": ["afgrænsning", "afgrænsningsfasen", "scoping", "omfanget af en miljøvurdering"],
    "Kumulative effekter": ["kumulativ", "kumulative", "samspilseffekt"],
    "Overvågning": ["overvågning", "overvågningsprogram"],
    "Ændringer ved endelig vedtagelse": ["ændringer ved den endelige vedtagelse", "§ 27, stk. 2", "fornyet høring", "fornyet offentliggørelse"],
    "Screening vs. miljørapport": ["screeningsafgørelse", "screening", "obligatorisk miljøvurdering", "bilag 3"],
    "Inhabilitet": ["inhabilitet", "inhabili", "forvaltningslovens § 3"],
    "Høring og offentlighed": ["høring", "offentlig høring", "partshøring", "offentlighedsfasen", "inddragelse af offentligheden"],
    "Rekreative interesser": ["rekreativ", "rekreative interesser", "friluftsliv"],
}


def strip_html(text: str) -> str:
    """Fjern HTML-tags og unescape entities."""
    return _html.unescape(re.sub(r"<[^>]+>", " ", str(text)))


def _er_realitetsbehandlet_miljørapport(titel: str, tekst_ren: str) -> bool:
    """Filtrer til kun realitetsbehandlede miljørapport-sager."""
    t = titel.lower()
    txt = tekst_ren.lower()
    is_miljørapport = "miljørapport" in t or ("miljøvurdering" in t and "screening" not in t)
    has_vurdering = "planklagenævnets vurdering" in txt
    not_afvist = "afviser klagen" not in txt and "afvisning" not in t
    not_opsættende = "opsættende virkning" not in t
    return is_miljørapport and has_vurdering and not_afvist and not_opsættende


def _detect_emner(tekst_ren: str) -> list[str]:
    """Detekter hvilke emner en afgørelse dækker."""
    txt = tekst_ren.lower()
    emner = []
    for emne, nøgleord in EMNE_KATEGORIER.items():
        if any(n in txt for n in nøgleord):
            emner.append(emne)
    return emner


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Indlæs kun realitetsbehandlede PKN miljørapport-afgørelser."""
    df = pd.read_csv(_DATA_PATH)
    df["Tekst_ren"] = df["Tekst"].apply(strip_html)
    mask = df.apply(lambda r: _er_realitetsbehandlet_miljørapport(r["Titel"], r["Tekst_ren"]), axis=1)
    df = df[mask].reset_index(drop=True)
    df["Emner"] = df["Tekst_ren"].apply(_detect_emner)
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


def _detect_query_emner(query: str) -> list[str]:
    """Detekter emner i brugerens søgeforespørgsel."""
    txt = query.lower()
    emner = []
    for emne, nøgleord in EMNE_KATEGORIER.items():
        if any(n in txt for n in nøgleord):
            emner.append(emne)
    return emner


def find_relevante_sager(
    query: str,
    df: pd.DataFrame,
    vec: TfidfVectorizer,
    mat,
    top_n: int = 5,
) -> pd.DataFrame:
    """Find relevante præcedensafgørelser med emnespecifik boosting.

    Sager der deler emne med klagepunktet boostes med 50%.
    """
    qv = vec.transform([query])
    scores = cosine_similarity(qv, mat).flatten()

    # Emnespecifik boosting
    query_emner = _detect_query_emner(query)
    if query_emner:
        for i, row in df.iterrows():
            sag_emner = row.get("Emner", [])
            overlap = len(set(query_emner) & set(sag_emner))
            if overlap > 0:
                # Boost proportionelt med emne-overlap
                scores[i] *= 1.0 + 0.5 * overlap

    top_idx = scores.argsort()[-top_n:][::-1]
    result = df.iloc[top_idx].copy()
    result["_score"] = scores[top_idx]
    result = result[result["_score"] > 0.01]
    return result.reset_index(drop=True)

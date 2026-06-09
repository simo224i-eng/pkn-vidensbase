"""
Børge — Byggeteknisk flashcards til ejerskifteforsikring.

Selvstændig Streamlit-app i samme repo som Harald (pkn/mfkn) og Ejnar
(ejerskifteforsikringspraksis). Hvor Ejnar lader dig *slå op* i Ankenævnet for
Forsikrings kendelser, lader Børge en jurist *terpe byggeteknikken bag* skaderne:
mangeltyper, skadesmekanismer, fagudtryk — og hvorfor det betyder noget for
dækningen. El- og VVS-installationer er bevidst udeladt.

Bevidst minimal: ét kurateret deck i data/flashcards.json, vend-kort, ingen
embeddings, ingen API-nøgler. Kan deployes for sig selv (Main file: byggeteknik/app.py).
"""
from __future__ import annotations

import base64 as _b64
import json
import random
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "flashcards.json"

ACCENT = "#8C1C2E"

st.set_page_config(
    page_title="Børge – Byggeteknisk flashcards",
    page_icon=":material/construction:",
    layout="centered",
    initial_sidebar_state="expanded",
)


# ── Logo (wordmark, samme stil som Ejnar) ─────────────────────────────────────
_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 56" width="{w}" '
    'style="display:block;margin:0 auto">'
    '<text x="110" y="34" text-anchor="middle" font-family="Inter,system-ui,sans-serif" '
    'font-size="24" font-weight="700" fill="{fill}" letter-spacing="5">BØRGE</text></svg>'
)


def logo(w: int, dark: bool = False) -> str:
    fill = "#f1f5f9" if dark else "#0f172a"
    svg = _LOGO_SVG.replace("{w}", str(w)).replace("{fill}", fill)
    b64 = _b64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" style="display:block;margin:0 auto"/>'


# ── CSS ───────────────────────────────────────────────────────────────────────
_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; }
header[data-testid="stHeader"] { background: transparent !important; height: 2.75rem !important; }
section[data-testid="stSidebar"] { background: #0f172a !important; }
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stMultiSelect [data-baseweb="tag"] { background: #8C1C2E !important; }
.block-container { padding-top: 2.2rem !important; max-width: 820px; }

.bx-chip {
    display:inline-block; font-size:10.5px; font-weight:600; letter-spacing:.4px;
    text-transform:uppercase; padding:3px 10px; border-radius:4px;
    background:#fef2f2; color:#8C1C2E; border:1px solid #f6dada;
}
.bx-level {
    display:inline-block; font-size:10px; font-weight:600; letter-spacing:.4px;
    text-transform:uppercase; padding:3px 9px; border-radius:4px; margin-left:6px;
    background:#f1f5f9; color:#64748b; border:1px solid #e2e8f0;
}
.bx-card {
    background:#ffffff; border:1px solid #e7eaf0; border-radius:12px;
    padding:2.2rem 2.2rem; box-shadow:0 1px 2px rgba(15,23,42,.04);
    min-height:240px;
}
.bx-card.answer { border-color:#f0d9dd; background:#fffafa; }
.bx-q { font-size:1.18rem; font-weight:700; color:#0f172a; line-height:1.5; margin-top:1rem; letter-spacing:-.2px; }
.bx-a { font-size:1.0rem; color:#1e293b; line-height:1.7; white-space:pre-wrap; }
.bx-a strong { color:#0f172a; }
.bx-label { font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#94a3b8; margin:.2rem 0 .4rem; }
.bx-jur {
    margin-top:1.4rem; padding:1rem 1.2rem; background:#f8fafc;
    border-left:3px solid #8C1C2E; border-radius:0 6px 6px 0;
    font-size:.9rem; color:#475569; line-height:1.6; white-space:pre-wrap;
}
.bx-jur b { color:#8C1C2E; }
.bx-progress { font-size:11px; color:#94a3b8; letter-spacing:.3px; text-align:center; margin:.4rem 0 1.2rem; }
.bx-counter { font-size:13px; font-weight:600; color:#475569; text-align:center; }
.stButton button { border-radius:7px !important; font-weight:600 !important; }
</style>
"""


def inject_css() -> None:
    try:
        st.html(_CSS)
    except AttributeError:
        st.markdown(_CSS, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def load_deck():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    cat_navn = {c["id"]: c["navn"] for c in data["kategorier"]}
    return data["meta"], data["kategorier"], cat_navn, data["kort"]


inject_css()
META, KATEGORIER, CAT_NAVN, KORT = load_deck()


# ── Valgfri adgangskode-gate ──────────────────────────────────────────────────
# Hvis APP_PASSWORD er sat i secrets, kræves login. Ellers er appen åben (så den
# virker out-of-the-box lokalt og kan beskyttes ved deploy uden kodeændring).
def _password_configured() -> str:
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return ""


_PW = _password_configured()
if _PW and not st.session_state.get("_auth_borge"):
    st.markdown(
        f"<div style='text-align:center;margin-top:6rem;margin-bottom:.4rem;'>{logo(150)}</div>"
        "<p style='text-align:center;color:#94a3b8;font-size:11px;letter-spacing:.6px;"
        "text-transform:uppercase;font-weight:500;margin-bottom:3rem;'>Byggeteknisk flashcards "
        "· ejerskifteforsikring</p>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 1.4, 1])[1]
    with col:
        pw = st.text_input("Adgangskode", type="password", placeholder="Indtast adgangskode…")
        if st.button("Log ind", use_container_width=True, type="primary"):
            if pw == _PW:
                st.session_state["_auth_borge"] = True
                st.rerun()
            else:
                st.error("Forkert adgangskode.")
    st.stop()


# ── Sidebar: filtre & indstillinger ───────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div style="padding:1.2rem 0 1.6rem;">{logo(120, dark=True)}'
        '<div style="text-align:center;font-size:9.5px;color:#64748b;text-transform:uppercase;'
        'letter-spacing:1.5px;font-weight:600;margin-top:.9rem;">Byggeteknik · ejerskifte</div></div>',
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:1px;background:#1e293b;margin:.2rem 0 1rem;'></div>", unsafe_allow_html=True)

    valgte_cat = st.multiselect(
        "Emner",
        options=[c["id"] for c in KATEGORIER],
        default=[c["id"] for c in KATEGORIER],
        format_func=lambda cid: CAT_NAVN[cid],
    )

    niveau_valg = st.radio(
        "Niveau",
        options=["Alle", "Grundniveau", "Videregående"],
        index=0,
        horizontal=False,
    )

    vis_jur = st.toggle("Vis juridisk relevans", value=True,
                        help="Vis boksen 'Hvorfor det betyder noget for dækningen' på bagsiden.")
    bland = st.toggle("Bland kortene", value=False)

    st.markdown("<div style='height:1px;background:#1e293b;margin:1.2rem 0 1rem;'></div>", unsafe_allow_html=True)
    if st.button("↻ Start forfra", use_container_width=True):
        st.session_state["idx"] = 0
        st.session_state["flip"] = False
        st.session_state.pop("order", None)
        st.rerun()

    if _PW and st.button("Log ud", use_container_width=True):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()


# ── Byg det aktuelle deck ud fra filtre ───────────────────────────────────────
def matcher_niveau(kort) -> bool:
    if niveau_valg == "Grundniveau":
        return kort.get("niveau") == "grund"
    if niveau_valg == "Videregående":
        return kort.get("niveau") == "videre"
    return True


deck = [k for k in KORT if k["kategori"] in valgte_cat and matcher_niveau(k)]

# Filter-signatur: nulstil position/rækkefølge når filtrene ændrer sig
sig = (tuple(sorted(valgte_cat)), niveau_valg, bland)
if st.session_state.get("_sig") != sig:
    st.session_state["_sig"] = sig
    st.session_state["idx"] = 0
    st.session_state["flip"] = False
    if bland:
        order = [k["id"] for k in deck]
        random.shuffle(order)
        st.session_state["order"] = order
    else:
        st.session_state.pop("order", None)

# Anvend evt. blandet rækkefølge
if bland and "order" in st.session_state:
    pos = {k["id"]: k for k in deck}
    deck = [pos[i] for i in st.session_state["order"] if i in pos]

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    f"<div style='text-align:center;padding:.4rem 0 1.2rem;'>{logo(150)}"
    "<div style='font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:2px;"
    "font-weight:500;margin-top:1rem;'>Byggeteknik bag ejerskifteforsikring · vend-kort</div></div>",
    unsafe_allow_html=True,
)

if not deck:
    st.info("Ingen kort matcher de valgte filtre. Vælg mindst ét emne i sidebaren.")
    st.stop()

# Hold idx inden for rækkevidde
idx = st.session_state.get("idx", 0)
idx = max(0, min(idx, len(deck) - 1))
st.session_state["idx"] = idx
flip = st.session_state.get("flip", False)

kort = deck[idx]

# ── Fremdrift ─────────────────────────────────────────────────────────────────
st.markdown(
    f"<div class='bx-progress'>Kort {idx + 1} af {len(deck)} &nbsp;·&nbsp; {len(KORT)} i hele decket</div>",
    unsafe_allow_html=True,
)
st.progress((idx + 1) / len(deck))

# ── Kortet ────────────────────────────────────────────────────────────────────
niveau_label = {"grund": "Grundniveau", "videre": "Videregående"}.get(kort.get("niveau", ""), "")
chip = (
    f"<span class='bx-chip'>{CAT_NAVN[kort['kategori']]}</span>"
    + (f"<span class='bx-level'>{niveau_label}</span>" if niveau_label else "")
)

if not flip:
    st.markdown(
        f"<div class='bx-card'>{chip}"
        f"<div class='bx-label' style='margin-top:1.2rem'>Spørgsmål</div>"
        f"<div class='bx-q'>{kort['spørgsmål']}</div></div>",
        unsafe_allow_html=True,
    )
else:
    jur_html = ""
    if vis_jur and kort.get("juridisk"):
        jur_html = (
            "<div class='bx-jur'><b>Hvorfor det betyder noget for dækningen</b><br>"
            f"{kort['juridisk']}</div>"
        )
    st.markdown(
        f"<div class='bx-card answer'>{chip}"
        f"<div class='bx-label' style='margin-top:1.2rem'>Spørgsmål</div>"
        f"<div style='font-size:.98rem;font-weight:600;color:#334155;line-height:1.5;margin-bottom:1.3rem;'>"
        f"{kort['spørgsmål']}</div>"
        f"<div class='bx-label'>Svar</div>"
        f"<div class='bx-a'>{kort['svar']}</div>"
        f"{jur_html}</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='height:.9rem'></div>", unsafe_allow_html=True)

# ── Vend-knap ─────────────────────────────────────────────────────────────────
if not flip:
    if st.button("Vis svar", use_container_width=True, type="primary"):
        st.session_state["flip"] = True
        st.rerun()
else:
    if st.button("Skjul svar", use_container_width=True):
        st.session_state["flip"] = False
        st.rerun()

# ── Navigation ────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    if st.button("← Forrige", use_container_width=True, disabled=idx == 0):
        st.session_state["idx"] = idx - 1
        st.session_state["flip"] = False
        st.rerun()
with c2:
    st.markdown(f"<div class='bx-counter' style='padding-top:.5rem'>{idx + 1} / {len(deck)}</div>",
                unsafe_allow_html=True)
with c3:
    if st.button("Næste →", use_container_width=True, disabled=idx >= len(deck) - 1):
        st.session_state["idx"] = idx + 1
        st.session_state["flip"] = False
        st.rerun()

# ── Fod ───────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;margin-top:2.6rem;padding-top:1.2rem;border-top:1px solid #eef1f6;'>"
    "<span style='font-size:10.5px;color:#cbd5e1;line-height:1.6;'>"
    "Børge er et lærings-deck — ikke juridisk rådgivning i en konkret sag. "
    "Slå konkret praksis op i Ejnar.</span></div>",
    unsafe_allow_html=True,
)

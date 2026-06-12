"""
Børge — Lær byggeteknik periode for periode.

Selvstændig Streamlit-app i samme repo som Harald (pkn/mfkn) og Ejnar
(ejerskifteforsikringspraksis), men med sit eget formål OG sit eget visuelle
udtryk: vælg en bygningsperiode (fx 1960–1979) og lær, hvordan husene fra den tid
er bygget — tag, vægge, fundament, materialer — med flashcards og quiz.

Rent byggeteknisk. Ingen jura. Ingen embeddings, ingen API-nøgler — kun ét
kurateret deck i data/flashcards.json.
"""
from __future__ import annotations

import base64 as _b64
import json
import random
import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "flashcards.json"

st.set_page_config(
    page_title="Børge – Lær byggeteknik",
    page_icon=":material/foundation:",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Visuel identitet ──────────────────────────────────────────────────────────
# Petrol/teal accent på varmt papir, Space Grotesk til wordmark/overskrifter.
INK = "#23211C"
PAPER = "#F4F1E9"
TEAL = "#0E7C7B"
TEAL_D = "#0B5E5D"
SAND = "#EDE7D9"

_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 260 60" width="{w}" '
    'style="display:block">'
    '<text x="0" y="40" font-family="\'Space Grotesk\',system-ui,sans-serif" '
    'font-size="40" font-weight="700" fill="{fill}" letter-spacing="-1">BØRGE</text>'
    '<rect x="170" y="14" width="74" height="6" rx="3" fill="{accent}"/>'
    '<rect x="170" y="26" width="52" height="6" rx="3" fill="{accent}" opacity="0.6"/>'
    '<rect x="170" y="38" width="34" height="6" rx="3" fill="{accent}" opacity="0.35"/>'
    "</svg>"
)


def logo(w: int) -> str:
    svg = _LOGO_SVG.replace("{w}", str(w)).replace("{fill}", INK).replace("{accent}", TEAL)
    b64 = _b64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" style="display:block"/>'


_CSS = f"""
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
.stApp {{ background:{PAPER}; }}
html, body, [class*="css"] {{ font-family:'Inter',system-ui,sans-serif; color:{INK}; }}
h1,h2,h3,.bx-wordmark {{ font-family:'Space Grotesk',system-ui,sans-serif; }}
header[data-testid="stHeader"] {{ background:transparent !important; }}
.block-container {{ padding-top:2.2rem !important; max-width:760px; }}

/* Hero */
.bx-hero {{ display:flex; align-items:flex-end; justify-content:space-between; gap:1rem;
            padding-bottom:.4rem; border-bottom:2px solid {SAND}; margin-bottom:1.4rem; }}
.bx-tag {{ font-size:12px; color:#7c7565; font-weight:500; letter-spacing:.2px; text-align:right; line-height:1.5; }}

/* Periode-intro */
.bx-era {{ background:linear-gradient(135deg,{TEAL} 0%,{TEAL_D} 100%); color:#f4fbfa;
           border-radius:16px; padding:1.3rem 1.5rem; margin:.2rem 0 1.4rem;
           box-shadow:0 6px 20px rgba(14,124,123,.18); }}
.bx-era .yr {{ font-size:11px; letter-spacing:2px; text-transform:uppercase; opacity:.8; font-weight:600; }}
.bx-era .ti {{ font-family:'Space Grotesk',sans-serif; font-size:1.45rem; font-weight:700; margin:.15rem 0 .5rem; }}
.bx-era .re {{ font-size:.93rem; line-height:1.6; color:#dff1f0; }}

/* Sektionslabel */
.bx-sec {{ font-size:10.5px; font-weight:700; letter-spacing:1.4px; text-transform:uppercase;
           color:#9a9281; margin:.4rem 0 .5rem; }}

/* Flashcard */
.bx-card {{ background:#fffefb; border:1px solid #e7e0d0; border-radius:18px;
            padding:2rem 2rem; min-height:230px; box-shadow:0 4px 16px rgba(35,33,28,.05); }}
.bx-card.back {{ background:#f6fbfa; border-color:#cfe7e5; }}
.bx-chip {{ display:inline-block; font-size:10.5px; font-weight:700; letter-spacing:.4px;
            text-transform:uppercase; padding:4px 11px; border-radius:20px;
            background:{SAND}; color:#6b6453; }}
.bx-chip.t {{ background:#dbefee; color:{TEAL_D}; }}
.bx-side {{ font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#b3aa97; margin:1.2rem 0 .4rem; }}
.bx-front {{ font-family:'Space Grotesk',sans-serif; font-size:1.3rem; font-weight:600; line-height:1.45; color:{INK}; }}
.bx-front.sm {{ font-size:1rem; font-weight:600; color:#5d564a; }}
.bx-back {{ font-size:1rem; line-height:1.7; color:#2c2a24; white-space:pre-wrap; }}
.bx-back strong {{ color:{TEAL_D}; }}
.bx-meta {{ text-align:center; font-size:11px; color:#9a9281; letter-spacing:.3px; margin:.3rem 0 1rem; }}

/* Diagram på kortets bagside */
.bx-fig {{ margin-top:1.2rem; background:{PAPER}; border:1px solid #e7e0d0;
           border-radius:12px; padding:.55rem .55rem .4rem; }}
.bx-fig img {{ width:100%; display:block; border-radius:8px; }}
.bx-figcap {{ font-size:.78rem; color:#9a9281; text-align:center; margin-top:.35rem; line-height:1.45; }}

/* Quiz */
.bx-q {{ font-family:'Space Grotesk',sans-serif; font-size:1.2rem; font-weight:600; line-height:1.5;
         color:{INK}; margin:.4rem 0 1.1rem; }}
.bx-expl {{ margin-top:1rem; padding:.9rem 1.1rem; border-radius:12px; font-size:.92rem; line-height:1.6; }}
.bx-expl.ok {{ background:#e7f5ec; color:#176c3a; border:1px solid #bfe3cb; }}
.bx-expl.no {{ background:#fbeaea; color:#9a2424; border:1px solid #f0cccc; }}
.bx-score {{ font-family:'Space Grotesk',sans-serif; font-size:2.4rem; font-weight:700; color:{TEAL_D}; text-align:center; }}

/* Knapper */
.stButton button {{ border-radius:11px !important; font-weight:600 !important; border:1px solid #e0d8c7 !important; }}
.stButton button:hover {{ border-color:{TEAL} !important; color:{TEAL_D} !important; }}
div[data-testid="stButton"] button[kind="primary"] {{ background:{TEAL} !important; border-color:{TEAL} !important; }}

/* Pills/segmented: lad temaets primaryColor (petrol) styre den valgte */
</style>
"""

try:
    st.html(_CSS)
except AttributeError:
    st.markdown(_CSS, unsafe_allow_html=True)


def md_html(text: str) -> str:
    """Konvertér kortenes lette markdown til HTML, da teksten indsættes i rå
    HTML-kort (hvor Streamlit ikke selv fortolker **fed** og punktopstilling)."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)   # **fed** → <strong>
    text = re.sub(r"(?m)^\s*-\s+", "• ", text)                       # "- " → "• "
    return text


@st.cache_data(show_spinner=False)
def asset_data_uri(rel: str):
    """Indlæs et diagram fra assets/ som data-URI, så det kan ligge inde i kort-HTML'en."""
    p = ROOT / "assets" / rel
    if not p.exists():
        return None
    mime = "image/svg+xml" if p.suffix == ".svg" else "image/png"
    return f"data:{mime};base64," + _b64.b64encode(p.read_bytes()).decode()


@st.cache_data(show_spinner=False)
def load_deck():
    d = json.loads(DATA.read_text(encoding="utf-8"))
    return d["meta"], d["perioder"], d["emner"], d["kort"]


META, PERIODER, EMNER, KORT = load_deck()
EMNE_NAVN = {e["id"]: e["navn"] for e in EMNER}
PER_BY_ID = {p["id"]: p for p in PERIODER}
# Rigtige æraer (alt undtagen den tværgående "alle"-gruppe)
ERAS = [p for p in PERIODER if p["id"] != "alle"]


# ── Valgfri adgangskode-gate ──────────────────────────────────────────────────
def _pw() -> str:
    try:
        return st.secrets.get("APP_PASSWORD", "")
    except Exception:
        return ""


PW = _pw()
if PW and not st.session_state.get("_auth_borge"):
    st.markdown(f"<div style='margin-top:5rem;margin-bottom:1.6rem;'>{logo(180)}</div>", unsafe_allow_html=True)
    st.caption("Byggeteknik · lær din bygning at kende")
    pw = st.text_input("Adgangskode", type="password", placeholder="Indtast adgangskode…")
    if st.button("Log ind", type="primary"):
        if pw == PW:
            st.session_state["_auth_borge"] = True
            st.rerun()
        else:
            st.error("Forkert adgangskode.")
    st.stop()


# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown(
    f"<div class='bx-hero'><div class='bx-wordmark'>{logo(168)}</div>"
    "<div class='bx-tag'>Lær byggeteknik<br>periode for periode</div></div>",
    unsafe_allow_html=True,
)

# ── Mode (Lær / Quiz) ─────────────────────────────────────────────────────────
mode = st.segmented_control(
    "Tilstand", ["📇 Lær", "🎯 Quiz"], default="📇 Lær",
    selection_mode="single", label_visibility="collapsed",
)
if mode is None:
    mode = "📇 Lær"

# ── Periodevælger (tidslinje) ─────────────────────────────────────────────────
ALLE_LABEL = "Alle perioder"
era_labels = [ALLE_LABEL] + [f"{p['navn']}" for p in ERAS]
valgt_label = st.pills("Periode", era_labels, default=ALLE_LABEL, label_visibility="collapsed")
if valgt_label is None:
    valgt_label = ALLE_LABEL
if valgt_label == ALLE_LABEL:
    periode_id = "ALLE"
else:
    periode_id = next(p["id"] for p in ERAS if p["navn"] == valgt_label)

# ── Filtre (emner + grundbegreber) ────────────────────────────────────────────
with st.expander("⚙️  Filtrér emner"):
    valgte_emner = st.multiselect(
        "Bygningsdele / emner",
        options=[e["id"] for e in EMNER],
        default=[e["id"] for e in EMNER],
        format_func=lambda eid: EMNE_NAVN[eid],
    )
    inkl_grund = st.toggle(
        "Tag tværgående grundbegreber med", value=True,
        help="Tværgående begreber (hvad er puds, mørtel, tegl …) vises uanset periode. Slå fra for kun periode-specifikt stof.",
    )

if not valgte_emner:
    valgte_emner = [e["id"] for e in EMNER]

# ── Regeltidslinje (byggeregler der ændrede byggeskikken) ─────────────────────
_milepaele = META.get("milepaele", [])
if _milepaele:
    with st.expander("📜  Regeltidslinje — byggeregler der ændrede byggeskikken"):
        rows = "".join(
            "<div style='display:flex;gap:.85rem;padding:.4rem 0;border-bottom:1px solid #ece6d8;'>"
            f"<div style='min-width:84px;font-family:\"Space Grotesk\",sans-serif;font-weight:700;"
            f"font-size:.85rem;color:{TEAL_D};'>{m['aar']}</div>"
            f"<div style='font-size:.88rem;color:#4a463d;line-height:1.5;'>{m['tekst']}</div></div>"
            for m in _milepaele
        )
        st.markdown(rows, unsafe_allow_html=True)


# ── Byg det aktuelle deck ─────────────────────────────────────────────────────
def build_deck():
    out = []
    for k in KORT:
        if k["emne"] not in valgte_emner:
            continue
        er_grund = k["perioder"] == ["alle"]
        if periode_id == "ALLE":
            if er_grund and not inkl_grund:
                continue
            out.append(k)
        else:
            if er_grund:
                if inkl_grund:
                    out.append(k)
            elif periode_id in k["perioder"]:
                out.append(k)
    return out


deck = build_deck()

# Periode-intro (kun når en konkret æra er valgt)
if periode_id != "ALLE":
    p = PER_BY_ID[periode_id]
    st.markdown(
        f"<div class='bx-era'><div class='yr'>{p['aar']}</div>"
        f"<div class='ti'>{p['titel']}</div><div class='re'>{md_html(p['resume'])}</div></div>",
        unsafe_allow_html=True,
    )

# Nulstil tilstand når filtre/mode ændrer sig
sig = (mode, periode_id, tuple(sorted(valgte_emner)), inkl_grund)
if st.session_state.get("_sig") != sig:
    st.session_state["_sig"] = sig
    st.session_state["fc_idx"] = 0
    st.session_state["fc_flip"] = False
    st.session_state["fc_order"] = [k["id"] for k in deck]
    st.session_state["qz_order"] = None  # bygges når quiz starter

if not deck:
    st.info("Ingen kort matcher de valgte filtre. Vælg flere emner, eller slå grundbegreber til.")
    st.stop()

by_id = {k["id"]: k for k in KORT}


# ══════════════════════════════════════════════════════════════════════════════
# LÆR (flashcards)
# ══════════════════════════════════════════════════════════════════════════════
def render_flashcards():
    order = [i for i in st.session_state.get("fc_order", []) if i in {k["id"] for k in deck}]
    if not order:
        order = [k["id"] for k in deck]
        st.session_state["fc_order"] = order
    idx = max(0, min(st.session_state.get("fc_idx", 0), len(order) - 1))
    st.session_state["fc_idx"] = idx
    kort = by_id[order[idx]]
    flip = st.session_state.get("fc_flip", False)

    st.markdown(f"<div class='bx-meta'>Kort {idx + 1} af {len(order)}</div>", unsafe_allow_html=True)
    st.progress((idx + 1) / len(order))

    chip = f"<span class='bx-chip'>{EMNE_NAVN[kort['emne']]}</span>"
    if kort["perioder"] == ["alle"]:
        chip += " <span class='bx-chip t'>Tværgående</span>"

    forside = md_html(kort["forside"])
    bagside = md_html(kort["bagside"])
    if not flip:
        st.markdown(
            f"<div class='bx-card'>{chip}<div class='bx-side'>Spørgsmål</div>"
            f"<div class='bx-front'>{forside}</div></div>",
            unsafe_allow_html=True,
        )
    else:
        fig_html = ""
        if kort.get("billede"):
            uri = asset_data_uri(kort["billede"])
            if uri:
                cap = kort.get("billedtekst", "")
                cap_html = f"<div class='bx-figcap'>{cap}</div>" if cap else ""
                fig_html = f"<div class='bx-fig'><img src='{uri}' alt=''/>{cap_html}</div>"
        st.markdown(
            f"<div class='bx-card back'>{chip}"
            f"<div class='bx-side'>Spørgsmål</div><div class='bx-front sm'>{forside}</div>"
            f"<div class='bx-side'>Svar</div><div class='bx-back'>{bagside}</div>{fig_html}</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height:.7rem'></div>", unsafe_allow_html=True)
    if st.button("Vis svar" if not flip else "Skjul svar", use_container_width=True,
                 type="primary" if not flip else "secondary"):
        st.session_state["fc_flip"] = not flip
        st.rerun()

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("← Forrige", use_container_width=True, disabled=idx == 0):
            st.session_state["fc_idx"] = idx - 1
            st.session_state["fc_flip"] = False
            st.rerun()
    with c2:
        if st.button("🔀 Bland", use_container_width=True):
            random.shuffle(order)
            st.session_state["fc_order"] = order
            st.session_state["fc_idx"] = 0
            st.session_state["fc_flip"] = False
            st.rerun()
    with c3:
        if st.button("Næste →", use_container_width=True, disabled=idx >= len(order) - 1):
            st.session_state["fc_idx"] = idx + 1
            st.session_state["fc_flip"] = False
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# QUIZ
# ══════════════════════════════════════════════════════════════════════════════
def render_quiz():
    quiz_ids = [k["id"] for k in deck if "quiz" in k]
    if not quiz_ids:
        st.info("Ingen quizspørgsmål i det aktuelle udvalg.")
        return

    if not st.session_state.get("qz_order"):
        order = quiz_ids[:]
        random.shuffle(order)
        st.session_state["qz_order"] = order
        st.session_state["qz_idx"] = 0
        st.session_state["qz_score"] = 0
        st.session_state["qz_answered"] = None
        st.session_state["qz_opts"] = None

    order = st.session_state["qz_order"]
    qidx = st.session_state["qz_idx"]

    # Slutskærm
    if qidx >= len(order):
        score = st.session_state["qz_score"]
        total = len(order)
        pct = round(100 * score / total)
        st.markdown(
            f"<div class='bx-meta'>Quiz færdig — {valgt_label}</div>"
            f"<div class='bx-score'>{score} / {total}</div>"
            f"<div class='bx-meta'>{pct}% rigtige</div>",
            unsafe_allow_html=True,
        )
        st.progress(score / total)
        if st.button("🔁 Tag quizzen igen", use_container_width=True, type="primary"):
            st.session_state["qz_order"] = None
            st.rerun()
        return

    kort = by_id[order[qidx]]
    q = kort["quiz"]

    # Fastlås en blandet svar-rækkefølge for netop dette spørgsmål
    if not st.session_state.get("qz_opts"):
        opts = list(range(len(q["valg"])))
        random.shuffle(opts)
        st.session_state["qz_opts"] = opts
    opts = st.session_state["qz_opts"]

    st.markdown(
        f"<div class='bx-meta'>Spørgsmål {qidx + 1} af {len(order)} &nbsp;·&nbsp; "
        f"score {st.session_state['qz_score']}</div>",
        unsafe_allow_html=True,
    )
    st.progress(qidx / len(order))
    st.markdown(
        f"<span class='bx-chip'>{EMNE_NAVN[kort['emne']]}</span>"
        f"<div class='bx-q'>{md_html(q['sp'])}</div>",
        unsafe_allow_html=True,
    )

    answered = st.session_state.get("qz_answered")  # valgt original-index eller None

    for orig_i in opts:
        valg = q["valg"][orig_i]
        if answered is None:
            if st.button(valg, key=f"opt_{qidx}_{orig_i}", use_container_width=True):
                st.session_state["qz_answered"] = orig_i
                if orig_i == q["korrekt"]:
                    st.session_state["qz_score"] += 1
                st.rerun()
        else:
            mark = ""
            if orig_i == q["korrekt"]:
                mark = "  ✅"
            elif orig_i == answered:
                mark = "  ❌"
            st.button(valg + mark, key=f"opt_{qidx}_{orig_i}", use_container_width=True, disabled=True)

    if answered is not None:
        rigtigt = answered == q["korrekt"]
        cls = "ok" if rigtigt else "no"
        head = "Rigtigt!" if rigtigt else "Ikke helt."
        st.markdown(
            f"<div class='bx-expl {cls}'><b>{head}</b> {md_html(q.get('forklaring', ''))}</div>",
            unsafe_allow_html=True,
        )
        # Vis kortets diagram som forklaring (først efter der er svaret)
        if kort.get("billede"):
            uri = asset_data_uri(kort["billede"])
            if uri:
                cap = kort.get("billedtekst", "")
                cap_html = f"<div class='bx-figcap'>{cap}</div>" if cap else ""
                st.markdown(
                    f"<div class='bx-fig'><img src='{uri}' alt=''/>{cap_html}</div>",
                    unsafe_allow_html=True,
                )
        sidste = qidx + 1 >= len(order)
        if st.button("Se resultat" if sidste else "Næste spørgsmål →",
                     use_container_width=True, type="primary"):
            st.session_state["qz_idx"] = qidx + 1
            st.session_state["qz_answered"] = None
            st.session_state["qz_opts"] = None
            st.rerun()


if mode == "🎯 Quiz":
    render_quiz()
else:
    render_flashcards()

# ── Fod ───────────────────────────────────────────────────────────────────────
st.markdown(
    f"<div style='text-align:center;margin-top:2.4rem;padding-top:1.1rem;border-top:2px solid {SAND};'>"
    "<span style='font-size:10.5px;color:#b3aa97;'>Børge · byggeteknisk læring — ikke juridisk rådgivning. "
    f"{len(KORT)} kort · {len(ERAS)} perioder</span></div>",
    unsafe_allow_html=True,
)

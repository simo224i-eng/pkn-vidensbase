"""Delte hjælpefunktioner, CSS og logo til Harald (PKN + MFKN)."""
import re
import csv
import base64 as _b64
import numpy as np  # noqa: F401 – bruges i page-filer via import shared
import pandas as pd
import requests
import streamlit as st

# ── Styling ───────────────────────────────────────────────────────────────────
_CSS_HTML = """
<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@700;900&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
<style>
/* ── Skjul Streamlit header (keyboard_double_ fix) ── */
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stMain"] .block-container { padding-top: 1.5rem !important; }

/* ── Base ── */
[data-testid="stAppViewContainer"] { background: #f8fafc; font-family: 'Inter', system-ui, sans-serif; }

/* ── Sidebar ── */
[data-testid="stSidebar"] { background: #0f172a !important; border-right: none; }
[data-testid="stSidebar"] * { color: #94a3b8 !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] .stTextInput input {
    background: #1e293b !important; border: 1px solid #334155 !important;
    color: #e2e8f0 !important; border-radius: 5px !important; font-size: 13px !important;
}
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #1e293b !important; border-color: #334155 !important; border-radius: 5px !important;
}
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #c49a3c !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a { color: #c49a3c !important; }
[data-testid="stSidebar"] .stCheckbox label { font-size: 11px !important; color: #64748b !important; }

/* ── Sidebar collapse-knap ── */
/* Expand-knap (vises når sidebar er lukket) */
[data-testid="collapsedControl"] {
    background: #1e293b !important; border-radius: 0 6px 6px 0 !important;
}
/* Skjul al tekst og SVG – dæk begge strukturer (<button> eller <div><button>) */
[data-testid="collapsedControl"],
[data-testid="collapsedControl"] button,
[data-testid="collapsedControl"] button * {
    font-size: 0 !important; color: transparent !important;
}
[data-testid="collapsedControl"] svg { display: none !important; }
/* Vis "›" via ::after på selve elementet (virker uanset struktur) */
[data-testid="collapsedControl"]::after {
    content: "›"; font-size: 22px !important; color: #c49a3c !important;
    font-weight: 300; display: flex !important; align-items: center;
    justify-content: center; height: 100%; pointer-events: none;
}
/* Collapse-knap (inden i sidebar) */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarCollapseButton"] button * {
    font-size: 0 !important; color: transparent !important;
}
[data-testid="stSidebarCollapseButton"] button {
    background: transparent !important; border: none !important;
}
[data-testid="stSidebarCollapseButton"] svg { display: none !important; }
[data-testid="stSidebarCollapseButton"] button::after {
    content: "‹"; font-size: 22px !important; color: #94a3b8 !important;
    font-weight: 300; display: block !important;
}

/* ── Sidebar navigation (multipage) ── */
[data-testid="stSidebarNav"] {
    padding: 1.2rem 0 0 !important;
    margin-bottom: 0 !important;
    border-bottom: 1px solid #1e293b;
}
[data-testid="stSidebarNav"]::before {
    content: "NÆVN";
    display: block;
    font-size: 9px;
    font-weight: 600;
    color: #475569;
    letter-spacing: 1.5px;
    padding: 0 1rem 0.5rem;
}
[data-testid="stSidebarNavLink"] {
    color: #64748b !important;
    font-size: 12px !important;
    font-weight: 500 !important;
    padding: 7px 1rem !important;
    border-radius: 0 !important;
    border-left: 2px solid transparent !important;
    transition: all .12s !important;
    background: transparent !important;
}
[data-testid="stSidebarNavLink"]:hover {
    color: #cbd5e1 !important;
    background: rgba(255,255,255,.04) !important;
    border-left-color: #334155 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    color: #c49a3c !important;
    background: rgba(196,154,60,.07) !important;
    border-left-color: #c49a3c !important;
    font-weight: 600 !important;
}
[data-testid="stSidebarNavSeparator"] { display: none !important; }

/* ── Download-knap i sidebar ── */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    color: #94a3b8 !important;
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    width: 100% !important;
    padding: 8px 12px !important;
    letter-spacing: 0.2px !important;
    transition: border-color .12s, color .12s !important;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    border-color: #c49a3c !important;
    color: #e2e8f0 !important;
}

/* ── Skjul keyboard-hint på tabs ── */
[data-testid="stTabs"] [role="tab"] span[data-testid],
[data-testid="stTabs"] [role="tab"] kbd { display: none !important; }

/* ── Sidebar branding ── */
.h-brand-wrap { text-align: center; padding: 1.4rem 0 1.2rem; border-bottom: 1px solid #1e293b; margin-bottom: 1.6rem; }
.h-logo-box { display: inline-block; padding: 6px 10px; margin-bottom: 0; filter: drop-shadow(0 3px 12px rgba(196,154,60,0.22)); }
.h-sub { display: none; }

/* ── Sidebar section labels ── */
.h-filter-label { font-size: 9px !important; font-weight: 600 !important; color: #475569 !important;
                  text-transform: uppercase; letter-spacing: 1.5px; margin: 1.4rem 0 0.35rem; display: block; }

/* ── Page header ── */
.h-page-header { margin-bottom: 1.8rem; padding-bottom: 1.2rem; border-bottom: 1px solid #e2e8f0; }
.h-page-title  { font-family: 'Cinzel', Georgia, serif; font-size: 1.65rem; font-weight: 900; color: #0f172a; letter-spacing: 5px; margin: 0 0 4px; }
.h-page-meta   { font-size: 12.5px; color: #94a3b8; margin: 0; }
.h-gold-line   { height: 2px; width: 32px; background: #c49a3c; border-radius: 1px; margin: 6px 0 8px; }

/* ── Cards ── */
.pkn-card {
    background: #ffffff; border-radius: 8px; padding: 18px 22px; margin-bottom: 4px;
    border: 1px solid #e2e8f0; transition: border-color .12s, box-shadow .12s;
}
.pkn-card:hover { border-color: #c49a3c; box-shadow: 0 2px 14px rgba(15,23,42,.07); }
.pkn-card-toprow  { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.pkn-card-dato    { font-size: 11px; color: #94a3b8; font-weight: 500; letter-spacing: .2px; }
.pkn-card-title   { font-size: 13.5px; font-weight: 600; color: #0f172a; margin: 0 0 8px; line-height: 1.5; }
.pkn-card-tags    { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
.pkn-tag          { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 500; color: #475569; background: #f1f5f9; border: 1px solid #e2e8f0; }
.pkn-card-excerpt { font-size: 12.5px; color: #64748b; line-height: 1.6; }
.pkn-card-footer  { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; }
.pkn-card-link    { font-size: 11px; color: #94a3b8; text-decoration: none; font-weight: 500; transition: color .12s; }
.pkn-card-link:hover { color: #c49a3c; }

/* ── Badges ── */
.pkn-badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 10px; font-weight: 600; margin-right: 4px; letter-spacing: .1px; }
.badge-medhold      { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.badge-ikke-medhold { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.badge-ophaevet     { background: #f5f3ff; color: #5b21b6; border: 1px solid #ddd6fe; }
.badge-afvist       { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.badge-ukendt       { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }

/* ── Stat cards ── */
.stat-card   { background: #fff; border-radius: 6px; padding: 22px 18px; text-align: center; border: 1px solid #e2e8f0; }
.stat-number { font-family: 'Cinzel', Georgia, serif; font-size: 28px; font-weight: 700; color: #0f172a; }
.stat-label  { font-size: 10px; color: #94a3b8; margin-top: 5px; text-transform: uppercase; letter-spacing: 1px; }

/* ── Chat ── */
.chat-user      { background: #0f172a; color: #f1f5f9; border-radius: 12px 12px 2px 12px; padding: 10px 14px; margin: 6px 0; max-width: 74%; margin-left: auto; font-size: 13px; line-height: 1.5; }
.chat-assistant { background: #fff; color: #0f172a; border-radius: 12px 12px 12px 2px; padding: 10px 14px; margin: 6px 0; max-width: 84%; border: 1px solid #e2e8f0; font-size: 13px; line-height: 1.5; }
.source-chip    { display: inline-block; padding: 3px 9px; border-radius: 4px; background: #f8fafc; color: #475569; font-size: 11px; margin: 3px; text-decoration: none; border: 1px solid #e2e8f0; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-size: 13px; font-weight: 500; color: #94a3b8; padding: 8px 18px; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #0f172a !important; border-bottom-color: #c49a3c !important; font-weight: 600; }

/* ── Buttons ── */
[data-testid="stBaseButton-secondary"] { border-color: #e2e8f0 !important; color: #475569 !important; font-size: 12px !important; border-radius: 5px !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: #c49a3c !important; color: #0f172a !important; }

/* ── Detail view ── */
.detail-back-row { margin-bottom: 2rem; }
.detail-hero { padding: 2.4rem 0 2rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2.4rem; }
.detail-udfald-row { margin-bottom: 1rem; }
.detail-udfald-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 700; letter-spacing: 1.2px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px; border: 1px solid; }
.detail-title { font-family: 'Inter', system-ui, sans-serif; font-size: clamp(1.4rem, 3vw, 2rem); font-weight: 800; color: #0f172a; line-height: 1.25; letter-spacing: -0.5px; margin: 0 0 1.6rem; }
.detail-gold-line { height: 2px; width: 36px; background: #c49a3c; border-radius: 2px; margin-bottom: 1.4rem; }
.detail-meta-strip { display: flex; flex-wrap: wrap; gap: 0; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; margin-bottom: 1.4rem; width: fit-content; }
.detail-meta-cell { padding: 10px 20px; border-right: 1px solid #e2e8f0; }
.detail-meta-cell:last-child { border-right: none; }
.detail-meta-lbl { font-size: 9.5px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 1.3px; display: block; margin-bottom: 3px; }
.detail-meta-val { font-size: 13.5px; font-weight: 600; color: #0f172a; white-space: nowrap; }
.detail-source-link { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #64748b; text-decoration: none; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 14px; transition: all .12s; font-weight: 500; }
.detail-source-link:hover { border-color: #c49a3c; color: #0f172a; }
.detail-reader { font-size: 15px; line-height: 1.9; color: #1e293b; font-family: 'Inter', system-ui, sans-serif; font-weight: 400; }
.detail-reader p { margin: 0 0 1.1em; }
.detail-reader p:last-child { margin-bottom: 0; }
.detail-section-heading {
    display: block; font-size: 10.5px; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 1.6px;
    margin: 2.2em 0 0.7em; padding: 0 0 6px 10px;
    border-left: 2px solid #c49a3c; border-bottom: 1px solid #f1f5f9;
}
.detail-ai-panel { background: #0f172a; border-radius: 12px; padding: 24px; position: sticky; top: 1rem; }
.detail-ai-title { font-size: 11px; font-weight: 700; letter-spacing: 1.8px; text-transform: uppercase; color: #c49a3c; margin-bottom: 16px; }
.detail-ai-resume { font-size: 13px; line-height: 1.75; color: #cbd5e1; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 8px; padding: 14px 16px; margin-top: 12px; }

/* ── Skjul browser-tooltip på collapse-knap ── */
[data-testid="stSidebarCollapseButton"] button::before { content: none !important; }

/* ── Home page cards ── */
.nævn-card {
    background: #fff; border-radius: 12px; padding: 2rem 2.4rem;
    border: 1px solid #e2e8f0; cursor: pointer;
    transition: border-color .15s, box-shadow .15s, transform .15s;
}
.nævn-card:hover { border-color: #c49a3c; box-shadow: 0 8px 32px rgba(15,23,42,.10); transform: translateY(-2px); }
.nævn-card.mfkn:hover { border-color: #2d6a4f; }
.nævn-card-icon { font-size: 2.4rem; margin-bottom: 1rem; }
.nævn-card-title { font-family: 'Cinzel', Georgia, serif; font-size: 1.1rem; font-weight: 700; color: #0f172a; letter-spacing: 3px; margin-bottom: 0.4rem; }
.nævn-card-sub { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 1.5px; margin-bottom: 1rem; }
.nævn-card-desc { font-size: 13px; color: #475569; line-height: 1.65; margin-bottom: 1.2rem; }
.nævn-card-count { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; }
</style>
<script>
(function removeIconTooltips() {
  var SEL = [
    '[data-testid="stSidebarCollapseButton"] button',
    '[data-testid="collapsedControl"]',
    '[data-testid="collapsedControl"] button',
    '[role="tab"]',
    '[data-testid="stTabs"] button',
  ].join(', ');
  function strip() {
    document.querySelectorAll(SEL).forEach(function(el) {
      el.removeAttribute('title');
    });
  }
  strip();
  new MutationObserver(strip).observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['title'] });
})();
</script>
"""

# ── Logo SVG ──────────────────────────────────────────────────────────────────
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 248" width="{w}" style="display:block;margin:0 auto">
  <defs>
    <linearGradient id="lgG" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#e8c86a"/>
      <stop offset="100%" stop-color="#b8882e"/>
    </linearGradient>
    <linearGradient id="shFill" x1="0" y1="0" x2="0.6" y2="1">
      <stop offset="0%" stop-color="#192340"/>
      <stop offset="100%" stop-color="#0d1628"/>
    </linearGradient>
  </defs>
  <path d="M36,14 L164,14 C174,14 176,24 176,50 L176,108 C176,152 100,194 100,194 C100,194 24,152 24,108 L24,50 C24,24 26,14 36,14 Z" fill="url(#shFill)" stroke="url(#lgG)" stroke-width="3"/>
  <path d="M44,24 L156,24 C163,24 165,32 165,54 L165,106 C165,144 100,182 100,182 C100,182 35,144 35,106 L35,54 C35,32 37,24 44,24 Z" fill="none" stroke="#c49a3c" stroke-width="0.9" opacity="0.35"/>
  <circle cx="100" cy="55" r="4.5" fill="#c49a3c"/>
  <rect x="98" y="55" width="4" height="70" rx="2" fill="url(#lgG)"/>
  <rect x="78" y="121" width="44" height="5" rx="2.5" fill="url(#lgG)"/>
  <rect x="42" y="68" width="116" height="4.5" rx="2.25" fill="url(#lgG)"/>
  <line x1="57" y1="72.5" x2="46" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="57" y1="72.5" x2="71" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M40,97 Q58,119 76,97" stroke="url(#lgG)" stroke-width="3" fill="rgba(196,154,60,0.13)" stroke-linecap="round"/>
  <line x1="143" y1="72.5" x2="129" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <line x1="143" y1="72.5" x2="154" y2="97" stroke="#c49a3c" stroke-width="2.5" stroke-linecap="round"/>
  <path d="M124,97 Q142,119 160,97" stroke="url(#lgG)" stroke-width="3" fill="rgba(196,154,60,0.13)" stroke-linecap="round"/>
  <text x="100" y="224" text-anchor="middle" font-family="Cinzel,Georgia,serif" font-size="22" font-weight="700" fill="url(#lgG)" letter-spacing="6">HARALD</text>
  <line x1="48" y1="231" x2="152" y2="231" stroke="#c49a3c" stroke-width="0.7" opacity="0.4"/>
  <text x="100" y="244" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="7.5" font-weight="500" fill="#4a6a8a" letter-spacing="2.8">LEGAL TECH AI</text>
</svg>"""


def inject_css() -> None:
    try:
        st.html(_CSS_HTML)
    except AttributeError:
        st.markdown(_CSS_HTML, unsafe_allow_html=True)


def logo(w: int) -> str:
    svg = _LOGO_SVG.replace("{w}", str(w))
    b64 = _b64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" style="display:block;margin:0 auto"/>'


# ── API ───────────────────────────────────────────────────────────────────────
def _llm(prompt: str) -> str:
    key = st.secrets.get("ANTHROPIC_API_KEY", "")
    if not key:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets (Settings → Secrets)."
    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-5",
            "max_tokens": 2000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


# ── Delte hjælpefunktioner ────────────────────────────────────────────────────
def strip_html(text: str) -> str:
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
        "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
        "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
        "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
        "&sect;": "§", "&para;": "¶", "&copy;": "©", "&reg;": "®",
        "&#167;": "§",
    }
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in entities.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


_HEADING_WORDS = [
    "Nævnets afgørelse", "Begrundelse for afgørelsen", "Oplysninger om sagen",
    "Sagens oplysninger", "Klagen vedrører", "Nævnets bemærkninger",
    "Nævnets vurdering", "Retlig vurdering", "Parternes synspunkter",
    "Faktiske oplysninger", "Afgørelse", "Begrundelse", "Klagen",
    "Sagsforløb", "Lovgrundlag", "Afstemning", "Klagetema",
    "Plangrundlag", "Resumé", "Konklusion",
]
_HEADING_WORDS.sort(key=len, reverse=True)  # længste først – undgår delvis match


_H_OPEN  = '<span class="detail-section-heading">'
_H_CLOSE = '</span>'


def format_afgørelse_tekst(tekst: str) -> str:
    """Formatér råtekst fra afgørelse til HTML med sektionsoverskrifter og afsnit."""
    out = tekst.strip()

    # 1. Overskrifter midt i tekst – kræver forudgående sætningsafslutning
    for h in _HEADING_WORDS:
        esc = re.escape(h)
        out = re.sub(
            rf'([.!?])\s+({esc})\s*:?\s+',
            rf'\1</p>{_H_OPEN}\2{_H_CLOSE}<p>',
            out,
        )

    # 2. Overskrift ved tekststart (ingen forudgående tegnsætning)
    for h in _HEADING_WORDS:
        m = re.match(rf'^({re.escape(h)})\s*:?\s+', out)
        if m:
            out = f'{_H_OPEN}{m.group(1)}{_H_CLOSE}<p>{out[m.end():]}'
            break

    # 3. Opdel resterende tekst i afsnit ved sætningsgrænser
    out = re.sub(r'\.(\s+)([A-ZÆØÅ])', r'.</p><p>\2', out)
    out = re.sub(r'(\s)(\d+\.\s+)([A-ZÆØÅ])', r'</p><p>\2\3', out)

    # 4. Afslut korrekt afhængig af om teksten begynder med en overskrift
    if out.startswith(_H_OPEN):
        return f'<div class="detail-reader">{out}</p></div>'
    return f'<div class="detail-reader"><p>{out}</p></div>'


def extract_kommune(titel: str) -> str:
    m = re.search(r"([A-ZÆØÅ][a-zæøå]+-?[A-ZÆØÅ]?[a-zæøå]*)\s+Kommunes?", titel)
    return m.group(1) if m else None


BADGE = {
    "Medhold":       "badge-medhold",
    "Ikke medhold":  "badge-ikke-medhold",
    "Ophævet":       "badge-ophaevet",
    "Afvist":        "badge-afvist",
    "Ukendt":        "badge-ukendt",
    # MFKN
    "Stadfæstelse":  "badge-ikke-medhold",
    "Ændring":       "badge-medhold",
    "Hjemvist":      "badge-ophaevet",
}

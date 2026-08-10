"""Delte hjælpefunktioner, CSS og logo til Ejnar (Forsikringsankenævnets praksis for ejerskifteforsikring)."""
from __future__ import annotations  # gør PEP 604-typehints (X | None) lazy → kører også på Python 3.9
import re
import csv
import base64 as _b64
import numpy as np  # noqa: F401 – bruges i page-filer via import shared
import pandas as pd
import requests
import streamlit as st

def hent_nøgle(navn: str) -> str:
    """API-nøgle/token: miljøvariabel først (headless scripts som eval/klassifikation),
    derefter st.secrets (Streamlit-appen). Tåler at køre uden secrets-fil."""
    import os as _os
    val = _os.environ.get(navn, "")
    if val:
        return val
    try:
        return st.secrets.get(navn, "") or ""
    except Exception:
        return ""


# ── Styling ───────────────────────────────────────────────────────────────────
# Design tokens (Ejnar — samme look-and-feel som Harald):
#   Background:  #ffffff (main)  #f8fafc (panel)
#   Sidebar:     #0f172a (flat)
#   Text:        #0f172a primær   #475569 sek.   #94a3b8 tert.
#   Border:      #e2e8f0 hairline   #cbd5e1 emphasis
#   Accent:      #2563eb (fintech-blå)   #eff6ff (accent bg)
#   Typografi:   Inter 400/500/600/700/800 — ingen Cinzel
#   Radius:      6px cards, 4px chips, 6px buttons
_CSS_HTML = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded" rel="stylesheet">
<style>
/* ── Material Symbols (ligature-baseret ikon-font) ── */
.material-symbols-rounded {
    font-family: 'Material Symbols Rounded' !important;
    font-weight: normal;
    font-style: normal;
    line-height: 1;
    letter-spacing: normal;
    text-transform: none;
    display: inline-block;
    white-space: nowrap;
    word-wrap: normal;
    direction: ltr;
    font-feature-settings: 'liga';
    -webkit-font-feature-settings: 'liga';
    -webkit-font-smoothing: antialiased;
}

/* ── Streamlit header: vises (indeholder mobil hamburger), men gøres transparent ── */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 2.75rem !important;
    z-index: 999 !important;
}
/* Skjul Streamlit-logo/brand inde i headeren, behold knapper */
header[data-testid="stHeader"] [data-testid="stDecoration"] { display: none !important; }
/* Style hamburger/sidebar-toggle inde i headeren */
header[data-testid="stHeader"] button[kind="header"],
header[data-testid="stHeader"] button[data-testid="baseButton-header"],
header[data-testid="stHeader"] button {
    background: #0f172a !important;
    color: #f1f5f9 !important;
    border-radius: 6px !important;
    border: 1px solid #334155 !important;
}
header[data-testid="stHeader"] button svg {
    fill: #f1f5f9 !important;
    color: #f1f5f9 !important;
}
[data-testid="stMain"] .block-container { padding-top: 1.5rem !important; }

/* ── Base ── */
[data-testid="stAppViewContainer"],
[data-testid="stApp"],
[data-testid="stMain"],
.main, body {
    font-family: 'Inter', system-ui, -apple-system, sans-serif;
    color: #0f172a;
}

/* ── Sidebar (flad mørk) ── */
[data-testid="stSidebar"] { background: #0f172a !important; border-right: 1px solid #1e293b; }
[data-testid="stSidebar"] *:not(.material-symbols-rounded):not(.material-symbols-rounded *) {
    color: #cbd5e1 !important;
    font-family: 'Inter', sans-serif !important;
}
[data-testid="stSidebar"] .material-symbols-rounded,
[data-testid="stSidebar"] [class*="material-symbols"] {
    font-family: 'Material Symbols Rounded' !important;
    font-feature-settings: 'liga' !important;
    -webkit-font-feature-settings: 'liga' !important;
}
[data-testid="stSidebar"] .stTextInput input {
    background: #1e293b !important; border: 1px solid #334155 !important;
    color: #f1f5f9 !important; border-radius: 6px !important; font-size: 13px !important;
}
[data-testid="stSidebar"] .stTextInput input::placeholder { color: #64748b !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #1e293b !important; border-color: #334155 !important; border-radius: 6px !important;
}
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #2563eb !important; }
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] a { color: #cbd5e1 !important; }
[data-testid="stSidebar"] .stCheckbox label { font-size: 11px !important; color: #94a3b8 !important; }

/* ── Sidebar collapse-knap (synlig på alle skærme) ── */
[data-testid="collapsedControl"],
[data-testid="stSidebarCollapsedControl"] {
    background: #0f172a !important;
    border: 1px solid #334155 !important;
    border-left: none !important;
    border-radius: 0 6px 6px 0 !important;
    width: 38px !important;
    height: 38px !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 999 !important;
    opacity: 1 !important;
    visibility: visible !important;
}
[data-testid="collapsedControl"] button,
[data-testid="collapsedControl"] button * {
    font-size: 0 !important; color: transparent !important;
    width: 100% !important; height: 100% !important;
}
[data-testid="collapsedControl"] svg { display: none !important; }
[data-testid="collapsedControl"]::after {
    content: "›"; font-size: 24px !important; color: #f1f5f9 !important;
    font-weight: 400; display: flex !important; align-items: center;
    justify-content: center;
    position: absolute; inset: 0;
    pointer-events: none;
}
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
    padding: 0.6rem 0.6rem 0.5rem !important;
    margin-bottom: 0 !important;
    border-bottom: 1px solid #1e293b;
}
[data-testid="stSidebarNav"]::before { display: none !important; }
[data-testid="stSidebarNavLink"] {
    color: #94a3b8 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 7px 12px !important;
    border-radius: 6px !important;
    border-left: none !important;
    transition: all .12s !important;
    background: transparent !important;
    letter-spacing: 0.1px !important;
}
[data-testid="stSidebarNavLink"]:hover {
    color: #e2e8f0 !important;
    background: rgba(255,255,255,.05) !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    color: #f1f5f9 !important;
    background: rgba(255,255,255,.08) !important;
    font-weight: 600 !important;
}
[data-testid="stSidebarNavSeparator"] { display: none !important; }
[data-testid="stSidebarNavLink"] span[data-testid="stIconMaterial"] { display: none !important; }

/* ── Download-knap i sidebar ── */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    background: transparent !important;
    border: 1px solid #334155 !important;
    color: #94a3b8 !important;
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    width: 100% !important;
    padding: 8px 12px !important;
    letter-spacing: 0.2px !important;
    transition: all .12s !important;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    border-color: #64748b !important;
    color: #f1f5f9 !important;
}

/* ── Nulstil filtre-knap i sidebar ── */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"][class*="reset"],
[data-testid="stSidebar"] div:has(> [data-testid="stBaseButton-secondary"]) button {
    font-size: 11px !important;
    font-weight: 500 !important;
    letter-spacing: 0.3px !important;
}

/* ── Skjul keyboard-hint på tabs ── */
[data-testid="stTabs"] [role="tab"] span[data-testid],
[data-testid="stTabs"] [role="tab"] kbd { display: none !important; }

/* ── Sidebar branding ── */
.h-brand-wrap { text-align: center; padding: 1.4rem 0 1.1rem; border-bottom: 1px solid #1e293b; margin-bottom: 1rem; }
.h-logo-box { display: inline-block; padding: 0; }
.h-sub { display: none; }

/* ── Sidebar section labels ── */
.h-filter-label {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 10px !important;
    font-weight: 600 !important;
    color: #64748b !important;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin: 1rem 0 0.3rem;
    display: block;
}

/* ── Page header ── */
.h-page-header {
    margin-bottom: 1.8rem; padding-bottom: 1rem;
    border-bottom: 1px solid #eef1f6;
    display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap;
}
.h-page-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 1.3rem; font-weight: 700;
    color: #0f172a; letter-spacing: -0.4px; margin: 0; line-height: 1.2;
}
.h-page-meta {
    font-size: 12px; color: #94a3b8; margin: 0;
    padding-left: 14px; border-left: 1px solid #eef1f6;
    font-weight: 400;
}
.h-gold-line { display: none; }

/* ── Cards ── */
.pkn-card {
    background: #ffffff; border-radius: 8px; padding: 16px 20px; margin-bottom: 4px;
    border: 1px solid #eef1f6; border-left: 2px solid transparent;
    transition: all .15s ease;
}
.pkn-card:hover { border-color: #e2e8f0; border-left-color: #0f172a; box-shadow: 0 2px 8px rgba(15,23,42,.04); }
.pkn-card-toprow  { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.pkn-card-dato    { font-size: 11px; color: #94a3b8; font-weight: 500; letter-spacing: .1px; }
.pkn-card-title   { font-size: 13px; font-weight: 600; color: #0f172a; margin: 0 0 8px; line-height: 1.5; }
.pkn-card-tags    { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 10px; }
.pkn-tag          { display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: 10px; font-weight: 500; color: #64748b; background: #f8fafc; border: 1px solid #eef1f6; }
.pkn-card-excerpt { font-size: 13px; color: #475569; line-height: 1.6; }
.pkn-card-footer  { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; }
.pkn-card-link    { font-size: 11px; color: #94a3b8; text-decoration: none; font-weight: 500; transition: color .12s; }
.pkn-card-link:hover { color: #0f172a; }

/* ── Badges ── */
.pkn-badge { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 10px; font-weight: 600; margin-right: 4px; letter-spacing: .2px; }
.badge-medhold      { background: #f0fdf4; color: #15803d; border: 1px solid #dcfce7; }
.badge-ikke-medhold { background: #fef2f2; color: #b91c1c; border: 1px solid #fee2e2; }
.badge-ophaevet     { background: #f5f3ff; color: #6d28d9; border: 1px solid #ede9fe; }
.badge-afvist       { background: #fffbeb; color: #a16207; border: 1px solid #fef3c7; }
.badge-ukendt       { background: #f8fafc; color: #64748b; border: 1px solid #eef1f6; }

/* ── Aktive filter-chips (klikbare til at fjerne) ── */
.active-filters-wrap {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    padding: 8px 0 6px; margin-bottom: 4px; border-bottom: 1px solid #eef1f6;
}
.active-filters-label {
    font-size: 10px; font-weight: 600; color: #94a3b8;
    text-transform: uppercase; letter-spacing: 0.8px; margin-right: 6px;
}
/* Style Streamlit-knapper som placeres inde i en chip-container */
.active-filters-wrap + div [data-testid="stHorizontalBlock"] button,
div[data-testid="element-container"]:has(.active-filters-anchor) ~ div button[kind="secondary"] {
    background: #f1f5f9 !important; color: #475569 !important;
    border: 1px solid #cbd5e1 !important; border-radius: 4px !important;
    font-size: 11.5px !important; font-weight: 500 !important;
    padding: 3px 10px !important; min-height: 26px !important; height: 26px !important;
    line-height: 1.2 !important;
}
div[data-testid="element-container"]:has(.active-filters-anchor) ~ div button[kind="secondary"]:hover {
    background: #f1f5f9 !important; color: #0f172a !important; border-color: #94a3b8 !important;
}
div[data-testid="element-container"]:has(.active-filters-clear-anchor) ~ div button {
    background: transparent !important; color: #0f172a !important;
    border: 1px solid #cbd5e1 !important; border-radius: 4px !important;
    font-size: 11.5px !important; font-weight: 600 !important;
    padding: 3px 10px !important; min-height: 26px !important; height: 26px !important;
}

/* ── Stat cards ── */
.stat-card   { background: #f8fafc; border-radius: 8px; padding: 20px 18px; text-align: center; border: 1px solid #cbd5e1; }
.stat-number { font-family: 'Inter', system-ui, sans-serif; font-size: 24px; font-weight: 700; color: #0f172a; letter-spacing: -0.5px; }
.stat-label  { font-size: 10px; color: #94a3b8; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.8px; font-weight: 500; }

/* ── AI Assistent intro ── */
.ai-hero {
    display: flex; align-items: flex-start; gap: 14px;
    background: #f8fafc;
    border: 1px solid #eef1f6; border-radius: 8px;
    padding: 16px 20px; margin-bottom: 20px;
}
.ai-hero-icon {
    font-size: 20px; flex-shrink: 0; color: #0f172a; line-height: 1;
    margin-top: 1px;
}
.ai-hero-icon .material-symbols-rounded { font-size: 20px; color: #0f172a; }
.ai-hero-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 13px; font-weight: 600;
    color: #0f172a; letter-spacing: -0.1px;
    margin: 0 0 3px;
}
.ai-hero-sub {
    font-size: 12px; color: #64748b; line-height: 1.6; margin: 0;
}
.ai-hero-sub strong { color: #334155; font-weight: 600; }
.ai-hero-badge { display: none; }

/* Forslagsknapper */
#ai-forslag-anchor ~ div button,
#ai-forslag-anchor ~ div ~ div button,
#ai-forslag-anchor ~ div ~ div ~ div button,
#ai-forslag-anchor ~ div ~ div ~ div ~ div button {
    background: #ffffff !important;
    border: 1px solid #eef1f6 !important;
    color: #475569 !important; border-radius: 8px !important;
    font-size: 12px !important; line-height: 1.5 !important;
    padding: 10px 14px !important; min-height: 56px !important;
    text-align: left !important; transition: all .15s ease !important;
    white-space: normal !important;
}
#ai-forslag-anchor ~ div button:hover,
#ai-forslag-anchor ~ div ~ div button:hover,
#ai-forslag-anchor ~ div ~ div ~ div button:hover,
#ai-forslag-anchor ~ div ~ div ~ div ~ div button:hover {
    background: #f8fafc !important;
    border-color: #cbd5e1 !important;
    color: #0f172a !important;
}

/* ── Chat ── */
.chat-user {
    background: #0f172a;
    color: #f1f5f9; border-radius: 12px 12px 4px 12px;
    padding: 12px 16px; margin: 6px 0 6px auto; max-width: 75%;
    font-size: 13px; line-height: 1.6;
}
.chat-assistant {
    background: #ffffff; color: #0f172a;
    border-radius: 4px 12px 12px 12px;
    padding: 14px 18px; margin: 6px 0; max-width: 92%;
    border: 1px solid #eef1f6; font-size: 14px; line-height: 1.7;
}
.chat-assistant h1 { font-size: 15px !important; font-weight: 700 !important; margin: 0.9em 0 0.4em !important; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px; }
.chat-assistant h2 { font-size: 14px !important; font-weight: 700 !important; margin: 0.7em 0 0.3em !important; }
.chat-assistant h3 { font-size: 13px !important; font-weight: 600 !important; margin: 0.6em 0 0.25em !important; }
.chat-assistant p  { margin: 0 0 0.6em !important; }
.chat-assistant ul, .chat-assistant ol { margin: 0.3em 0 0.6em 1.2em !important; }
.chat-assistant li { margin-bottom: 0.2em !important; }
.source-chip    { display: inline-block; padding: 3px 9px; border-radius: 3px; background: #f8fafc; color: #64748b; font-size: 11.5px; margin: 3px; text-decoration: none; border: 1px solid #eef1f6; transition: all .12s; }
.source-chip:hover { border-color: #cbd5e1; color: #0f172a; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-size: 13px; font-weight: 500; color: #94a3b8; padding: 8px 18px; transition: color .12s; }
[data-testid="stTabs"] [role="tab"]:hover { color: #475569; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #0f172a !important; border-bottom-color: #0f172a !important; font-weight: 600; }

/* ── Buttons ── */
[data-testid="stBaseButton-secondary"] { border-color: #eef1f6 !important; color: #475569 !important; font-size: 13px !important; border-radius: 6px !important; background: #ffffff !important; font-weight: 500 !important; transition: all .12s !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: #cbd5e1 !important; color: #0f172a !important; background: #f8fafc !important; }
[data-testid="stBaseButton-primary"] { background: #0f172a !important; border-color: #0f172a !important; color: #ffffff !important; border-radius: 6px !important; font-weight: 600 !important; transition: all .12s !important; }
[data-testid="stBaseButton-primary"]:hover { background: #1e293b !important; border-color: #1e293b !important; }

/* ── Detail view ── */
.detail-back-row { margin-bottom: 1.8rem; }
.detail-hero { padding: 1.8rem 0 1.6rem; border-bottom: 1px solid #eef1f6; margin-bottom: 1.8rem; }
.detail-udfald-row { margin-bottom: 1rem; }
.detail-udfald-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; padding: 4px 12px; border-radius: 3px; border: 1px solid; }
.detail-title { font-family: 'Inter', system-ui, sans-serif; font-size: clamp(1.2rem, 2vw, 1.55rem); font-weight: 700; color: #0f172a; line-height: 1.35; letter-spacing: -0.4px; margin: 0 0 1.2rem; }
.detail-gold-line { height: 2px; width: 28px; background: #0f172a; border-radius: 2px; margin-bottom: 1.2rem; }
.detail-meta-strip { display: flex; flex-wrap: wrap; gap: 0; border: 1px solid #eef1f6; border-radius: 6px; overflow: hidden; margin-bottom: 1.2rem; width: fit-content; background: #ffffff; }
.detail-meta-cell { padding: 10px 18px; border-right: 1px solid #eef1f6; }
.detail-meta-cell:last-child { border-right: none; }
.detail-meta-lbl { font-size: 10px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 1px; display: block; margin-bottom: 3px; }
.detail-meta-val { font-size: 13px; font-weight: 600; color: #0f172a; white-space: nowrap; }
.detail-source-link { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #64748b; text-decoration: none; border: 1px solid #eef1f6; border-radius: 6px; padding: 6px 14px; transition: all .12s; font-weight: 500; background: #ffffff; }
.detail-source-link:hover { border-color: #cbd5e1; color: #0f172a; }
.detail-reader { font-size: 15px; line-height: 1.85; color: #1e293b; font-family: 'Inter', system-ui, sans-serif; font-weight: 400; max-width: 70ch; }
.detail-reader p { margin: 0 0 1.2em; }
.detail-reader p:last-child { margin-bottom: 0; }
.detail-section-heading {
    display: block; font-size: 10px; font-weight: 700; color: #64748b;
    text-transform: uppercase; letter-spacing: 1px;
    margin: 2em 0 0.6em; padding: 0 0 5px 10px;
    border-left: 2px solid #0f172a; border-bottom: 1px solid #eef1f6;
}
.detail-ai-panel { background: #0f172a; border-radius: 8px; padding: 24px; position: sticky; top: 1rem; }
.detail-ai-title { font-size: 10px; font-weight: 600; letter-spacing: 1px; text-transform: uppercase; color: #64748b; margin-bottom: 14px; }
.detail-ai-resume { font-size: 13px; line-height: 1.7; color: #cbd5e1; background: rgba(255,255,255,.03); border: 1px solid rgba(255,255,255,.06); border-radius: 6px; padding: 14px 16px; margin-top: 12px; }

/* ── Skjul browser-tooltip på collapse-knap ── */
[data-testid="stSidebarCollapseButton"] button::before { content: none !important; }

/* ── Home page cards ── */
.nævn-card {
    background: #ffffff; border-radius: 8px; padding: 2rem 2.2rem 1.8rem;
    border: 1px solid #e2e8f0;
    transition: border-color .15s, box-shadow .15s, transform .15s;
    display: flex; flex-direction: column; height: 100%;
}
.nævn-card:hover { border-color: #2563eb; box-shadow: 0 4px 16px rgba(15,23,42,.06); transform: translateY(-2px); }
.nævn-card.mfkn:hover { border-color: #2563eb; }
.nævn-card-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 40px; height: 40px; border-radius: 8px;
    background: #eff6ff; color: #2563eb; margin-bottom: 1.2rem;
}
.nævn-card-icon .material-symbols-rounded { font-size: 22px; }
.nævn-card-title { font-family: 'Inter', system-ui, sans-serif; font-size: 1.05rem; font-weight: 700; color: #0f172a; letter-spacing: -0.3px; margin-bottom: 0.25rem; }
.nævn-card-sub { font-size: 11.5px; color: #64748b; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #f1f5f9; font-weight: 500; }
.nævn-card-desc { font-size: 13px; color: #475569; line-height: 1.65; margin-bottom: 1.2rem; flex: 1; }
.nævn-card-count { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 1.4rem; }
.nævn-card-cta {
    display: block; text-align: center; padding: 0.7rem 1rem;
    background: #ffffff; border: 1px solid #2563eb; border-radius: 6px;
    color: #2563eb; font-size: 13px; font-weight: 600; letter-spacing: 0.1px;
    transition: background .12s, color .12s;
}
.nævn-card:hover .nævn-card-cta { background: #2563eb; color: #ffffff; }

/* ── Card v2: knap smelter visuelt sammen med kortet ── */
.pkn-card-v2 { border-radius: 6px 6px 0 0; border-bottom: none !important; margin-bottom: 0; }
div[data-testid="element-container"]:has(.pkn-card-v2) { margin-bottom: 0 !important; }
div[data-testid="element-container"]:has(.pkn-card-v2) + div[data-testid="element-container"] [data-testid="stBaseButton-secondary"] {
    border-top: 1px solid #f1f5f9 !important;
    border-top-left-radius: 0 !important; border-top-right-radius: 0 !important;
    border-bottom-left-radius: 6px !important; border-bottom-right-radius: 6px !important;
    background: #f8fafc !important; color: #334155 !important;
    font-size: 13px !important; font-weight: 600 !important;
    padding: 10px 22px !important; letter-spacing: 0.2px !important;
}
div[data-testid="element-container"]:has(.pkn-card-v2) + div[data-testid="element-container"] [data-testid="stBaseButton-secondary"]:hover {
    background: #f1f5f9 !important; color: #0f172a !important;
}
div[data-testid="element-container"]:has(.pkn-card-v2) + div[data-testid="element-container"] { margin-bottom: 12px !important; }

/* ── Mobil breakpoints ── */
@media (max-width: 768px) {
    .h-page-header { flex-direction: column; gap: 8px; }
    .h-page-title { font-size: 1.2rem !important; letter-spacing: -0.2px !important; }
    .h-page-meta { padding-left: 0 !important; border-left: none !important; font-size: 11.5px !important; }
    .pkn-card { padding: 14px 16px !important; }
    .pkn-card-title { font-size: 12.5px !important; }
    .stat-card { padding: 14px 10px !important; }
    .stat-number { font-size: 20px !important; }
    .stat-label { font-size: 9.5px !important; }
    /* KPI-kort: 2x2 på mobil ved at lade Streamlit-kolonner wrappe */
    [data-testid="stHorizontalBlock"]:has(.stat-card) {
        flex-wrap: wrap !important;
    }
    [data-testid="stHorizontalBlock"]:has(.stat-card) > [data-testid="stColumn"] {
        min-width: 45% !important;
        flex: 1 1 45% !important;
    }
    .detail-title { font-size: 1.15rem !important; }
    .detail-meta-strip { flex-direction: column; width: 100% !important; }
    .detail-meta-cell { border-right: none !important; border-bottom: 1px solid #e2e8f0; padding: 8px 14px !important; }
    .detail-meta-cell:last-child { border-bottom: none; }
    .detail-reader { font-size: 14px !important; line-height: 1.75 !important; max-width: 100% !important; }
    .ai-hero { flex-direction: column; gap: 10px; padding: 14px 16px !important; }
    .chat-user { max-width: 95% !important; font-size: 13px !important; }
    .chat-assistant { max-width: 100% !important; font-size: 13px !important; }
    [data-testid="stTabs"] [role="tab"] { font-size: 11px !important; padding: 6px 10px !important; }
    .nævn-card { padding: 1.4rem 1.4rem 1.2rem !important; }
    /* Sidebar-toggle eksplicit synlig på mobil */
    [data-testid="collapsedControl"] {
        position: fixed !important;
        top: 12px !important;
        left: 0 !important;
        width: 42px !important;
        height: 42px !important;
        background: #0f172a !important;
        border: 1px solid #334155 !important;
        border-left: none !important;
        box-shadow: 0 2px 8px rgba(0,0,0,.18) !important;
        z-index: 9999 !important;
    }
    [data-testid="collapsedControl"]::after {
        font-size: 26px !important;
        color: #f1f5f9 !important;
    }
}

sup.detail-ref { font-size: 10px; font-weight: 700; color: #0f172a; vertical-align: super; letter-spacing: 0; }

/* ════════════════ Forenet fintech-blå + lækker læsevisning ════════════════ */
:root {
  --accent: #2563eb; --accent-700: #1d4ed8; --accent-50: #eff6ff;
  --ink: #0f172a; --ink-2: #334155; --ink-3: #64748b;
  --line: #e2e8f0; --line-soft: #eef1f6; --surface: #f8fafc;
}

/* ── Indholdsfortegnelse (sticky, klikbar) ── */
.rd-toc { position: sticky; top: 4.2rem; background: #fff; border: 1px solid var(--line-soft);
    border-radius: 10px; padding: 14px 14px 16px; }
.rd-toc-h { font-size: 10px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
    color: var(--ink-3); margin-bottom: 10px; }
.rd-toc-link { display: block; font-size: 12.5px; line-height: 1.45; color: var(--ink-2);
    text-decoration: none; padding: 5px 10px; border-radius: 6px; border-left: 2px solid transparent;
    margin-bottom: 2px; transition: all .12s; }
.rd-toc-link:hover { background: var(--accent-50); color: var(--accent-700); border-left-color: var(--accent); }
.rd-toc-l3 { padding-left: 20px; font-size: 12px; color: var(--ink-3); }

/* ── Reader-overskrifter med scroll-anker ── */
.rd-h2 { scroll-margin-top: 4.5rem; display: block; font-size: 12.5px; font-weight: 700; color: var(--ink);
    text-transform: uppercase; letter-spacing: 0.8px; margin: 2em 0 0.7em; padding: 9px 14px;
    background: var(--surface); border-left: 3px solid var(--accent); border-radius: 0 6px 6px 0; }
.rd-h3 { scroll-margin-top: 4.5rem; display: block; font-size: 11px; font-weight: 700; color: var(--ink-2);
    text-transform: uppercase; letter-spacing: 0.8px; margin: 1.6em 0 0.5em; padding: 6px 12px;
    background: var(--surface); border-left: 2px solid #cbd5e1; border-radius: 0 4px 4px 0; }
.rd-h4 { scroll-margin-top: 4.5rem; display: block; font-size: 10.5px; font-weight: 700; color: var(--ink-3);
    text-transform: uppercase; letter-spacing: 0.6px; margin: 1.1em 0 0.3em; padding: 3px 10px;
    border-left: 2px dotted #cbd5e1; }
mark.rd-cite { background: #fef08a; color: #1e293b; padding: 0 2px; border-radius: 2px;
    box-shadow: 0 0 0 1px #fde68a; }

/* ── Læserude (AI-fanen, citat → kilde) ── */
.rd-pane { border: 1px solid var(--line-soft); border-radius: 12px; overflow: hidden; background: #fff; }
.rd-pane-head { padding: 14px 16px 12px; border-bottom: 1px solid var(--line-soft); background: var(--surface); }
.rd-pane-title { font-size: 14px; font-weight: 700; color: var(--ink); line-height: 1.4; margin: 0 0 5px; }
.rd-pane-meta { font-size: 11px; color: var(--ink-3); }
.rd-body-scroll { max-height: 560px; overflow-y: auto; padding: 6px 18px 18px; }
.rd-body-scroll .rd-toc { position: static; margin: 10px 0 6px; }
.cite-callout { background: var(--accent-50); border: 1px solid #dbeafe; border-radius: 8px;
    padding: 12px 14px; margin: 14px 16px 0; }
.cite-callout-h { font-size: 10px; font-weight: 700; letter-spacing: .8px; text-transform: uppercase;
    color: var(--accent-700); margin-bottom: 6px; }
.cite-callout-q { font-size: 13px; line-height: 1.6; color: var(--ink-2); font-style: italic;
    border-left: 2px solid var(--accent); padding-left: 10px; margin: 6px 0; }

/* ── Kilde-kort (browse de fundne afgørelser) ── */
.src-list-h { font-size: 11px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase;
    color: var(--ink-3); margin: 0 0 10px; }
.src-card { background: #fff; border: 1px solid var(--line-soft); border-radius: 10px;
    padding: 12px 14px; margin-bottom: 2px; transition: border-color .12s, box-shadow .12s; }
.src-card:hover { border-color: #cbd5e1; box-shadow: 0 2px 10px rgba(15,23,42,.05); }
.src-card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.src-card-num { display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
    width: 20px; height: 20px; border-radius: 6px; background: var(--accent-50); color: var(--accent-700);
    font-size: 11px; font-weight: 700; }
.src-card-meta { font-size: 10.5px; color: var(--ink-3); }
.src-card-title { font-size: 12.5px; font-weight: 600; color: var(--ink); line-height: 1.45; margin: 0; }

/* ── Citat-chips (Perplexity-agtige, under svaret) ── */
.cite-chips-label { font-size: 10px; color: var(--ink-3); text-transform: uppercase; letter-spacing: 1px;
    font-weight: 600; margin: 8px 0 4px; }

/* ── Rolig citatkontrol (afløser den røde alarm-boks) ── */
[data-testid="stExpander"]:has(.cite-note-anchor) summary { font-size: 11.5px !important; color: #92400e !important; }
.cite-note { font-size: 12.5px; color: var(--ink-2); line-height: 1.65; }
.cite-note .q { color: var(--ink-3); font-style: italic; }

/* ── Chat-svar: lidt mere luft + ægte markdown-styling ── */
.chat-assistant { font-size: 14.5px !important; }
.chat-assistant h2 { color: var(--ink) !important; border-bottom: 1px solid var(--line) !important; padding-bottom: 4px !important; }
.chat-assistant hr { border: none; border-top: 1px solid var(--line); margin: 1em 0; }
.chat-assistant code { background: var(--surface); border: 1px solid var(--line-soft);
    border-radius: 4px; padding: 1px 5px; font-size: 12.5px; }
.chat-assistant strong { color: var(--ink); font-weight: 700; }

/* ── Accent-knapper (primær = blå) ── */
[data-testid="stBaseButton-primary"] { background: var(--accent) !important; border-color: var(--accent) !important; }
[data-testid="stBaseButton-primary"]:hover { background: var(--accent-700) !important; border-color: var(--accent-700) !important; }
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

# ── Logo SVG (wordmark) ───────────────────────────────────────────────────────
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 56" width="{w}" style="display:block;margin:0 auto">
  <text x="110" y="34" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="24" font-weight="700" fill="{fill}" letter-spacing="5">EJNAR</text>
</svg>"""


def inject_css() -> None:
    try:
        st.html(_CSS_HTML)
    except AttributeError:
        st.markdown(_CSS_HTML, unsafe_allow_html=True)


def render_filter_chips(chips: list, key_prefix: str = "flt") -> None:
    """Render clickable "active filter" chips. Each chip: (label, callback).

    Callback runs when chip is clicked (typically removes a value from session_state).
    Shows a "Ryd alle" chip at the end that runs the last callback in `chips` when its
    label is "__CLEAR_ALL__". Chips wrap across rows (max 8 per row).
    """
    if not chips:
        return
    st.markdown(
        '<div class="active-filters-wrap"><span class="active-filters-label">Aktive filtre</span></div>'
        '<span class="active-filters-anchor" style="display:none"></span>',
        unsafe_allow_html=True,
    )
    per_row = 8
    for row_start in range(0, len(chips), per_row):
        row_chips = chips[row_start:row_start + per_row]
        cols = st.columns([1] * len(row_chips) + [max(1, per_row - len(row_chips))])
        for i, (label, cb) in enumerate(row_chips):
            with cols[i]:
                if st.button(f"{label} ×", key=f"{key_prefix}_{row_start + i}", use_container_width=True):
                    cb()
                    st.rerun()


def copy_button(text: str, label: str = "Kopiér", key: str = "copy") -> None:
    """Renders a small copy-to-clipboard button using JS. text is what gets copied."""
    safe = text.replace("`", "\\`").replace("$", "\\$").replace("\\", "\\\\")
    st.components.v1.html(f"""
<button onclick="navigator.clipboard.writeText(`{safe}`).then(()=>{{
    this.innerText='✓ Kopieret';
    this.style.color='#166534';
    setTimeout(()=>{{this.innerText='{label}';this.style.color='';}} ,1800);
}})"
style="background:none;border:1px solid #e2e8f0;border-radius:4px;padding:3px 10px;
font-size:11px;color:#64748b;cursor:pointer;font-family:Inter,system-ui,sans-serif;
transition:all .15s;">
{label}
</button>
""", height=32)


def sidebar_log_ud() -> None:
    """Vis log ud-knap nederst i sidebaren."""
    with st.sidebar:
        st.markdown("---")
        if st.button("Log ud", use_container_width=True, key="_log_ud_btn"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


def logo(w: int, dark: bool = False) -> str:
    """Ejnar wordmark. dark=True giver lys tekst til mørk sidebar."""
    fill = "#f1f5f9" if dark else "#0f172a"
    svg = _LOGO_SVG.replace("{w}", str(w)).replace("{fill}", fill)
    b64 = _b64.b64encode(svg.encode()).decode()
    return f'<img src="data:image/svg+xml;base64,{b64}" width="{w}" style="display:block;margin:0 auto"/>'


def render_detail_header(
    titel: str,
    udfald: str,
    chip_style: str,
    dato_str: str,
    meta_extra: list,          # liste af (label, value) tupler
    link: str,
    link_label: str = "Åbn original på nævnets hjemmeside",
    accent: str = "#2563eb",
) -> str:
    """Returnér detail-header HTML med udelukkende inline styles.
    Bruges i stedet for CSS-klasser der kan blive strippet af Streamlit."""
    all_meta = [("Dato", dato_str)] + list(meta_extra)
    meta_cells = ""
    for i, (lbl, val) in enumerate(all_meta):
        border = "border-right:1px solid #e2e8f0;" if i < len(all_meta) - 1 else ""
        meta_cells += (
            f'<div style="padding:9px 18px;{border}">'
            f'<div style="font-size:9.5px;font-weight:600;color:#94a3b8;text-transform:uppercase;'
            f'letter-spacing:0.8px;margin-bottom:3px;">{lbl}</div>'
            f'<div style="font-size:13px;font-weight:600;color:#0f172a;white-space:nowrap;">{val}</div>'
            f'</div>'
        )
    return (
        f'<div style="padding:1.6rem 0 1.4rem;border-bottom:1px solid #e2e8f0;margin-bottom:2rem;">'
        f'<div style="margin-bottom:0.8rem;">'
        f'<span style="{chip_style};font-size:10px;font-weight:700;letter-spacing:0.8px;'
        f'text-transform:uppercase;padding:4px 11px;border-radius:20px;border:1px solid;">'
        f'{udfald}</span></div>'
        f'<div style="font-family:\'Inter\',system-ui,sans-serif;font-size:clamp(1.2rem,2vw,1.55rem);'
        f'font-weight:700;color:#0f172a;line-height:1.3;letter-spacing:-0.3px;margin:0 0 1rem;max-width:80ch;">'
        f'{titel}</div>'
        f'<div style="height:2px;width:28px;background:{accent};border-radius:2px;margin-bottom:1rem;"></div>'
        f'<div style="display:inline-flex;flex-wrap:wrap;border:1px solid #e2e8f0;border-radius:6px;'
        f'overflow:hidden;background:#ffffff;margin-bottom:1rem;">{meta_cells}</div><br>'
        f'<a href="{link}" target="_blank" style="display:inline-flex;align-items:center;gap:6px;'
        f'font-size:12px;font-weight:500;color:#475569;text-decoration:none;border:1px solid #e2e8f0;'
        f'border-radius:6px;padding:7px 14px;background:#ffffff;margin-top:0.5rem;">'
        f'{link_label} &nbsp;↗</a>'
        f'&nbsp;&nbsp;'
        f'<button onclick="navigator.clipboard.writeText(\'{titel.replace(chr(39), chr(8217))} – {dato_str} – {link}\').'
        f'then(function(){{this.textContent=\'Kopieret!\';var b=this;setTimeout(function(){{b.textContent=\'Kopiér reference\'}},2000)}}.bind(this))"'
        f' style="display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:500;'
        f'color:#475569;text-decoration:none;border:1px solid #e2e8f0;border-radius:6px;padding:7px 14px;'
        f'background:#ffffff;margin-top:0.5rem;cursor:pointer;font-family:inherit;">Kopiér reference</button>'
        f'</div>'
    )


# ── API ───────────────────────────────────────────────────────────────────────
import time as _time
import json as _json


def _api_headers(use_cache: bool = False) -> dict:
    key = hent_nøgle("ANTHROPIC_API_KEY")
    if not key:
        return {}
    headers = {
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    if use_cache:
        headers["anthropic-beta"] = "prompt-caching-2024-07-31"
    return headers


def _api_body(prompt, max_tokens: int, stream: bool = False, model: str = "claude-sonnet-4-6") -> dict:
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if stream:
        body["stream"] = True
    return body


def _llm(prompt, max_tokens: int = 2000, model: str = "claude-sonnet-4-6") -> str:
    """Send en prompt til Claude (blokerende, med retry).
    prompt kan være en str eller en liste af content-blokke (til prompt caching).
    """
    key = hent_nøgle("ANTHROPIC_API_KEY")
    if not key:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets (Settings → Secrets)."

    use_cache = isinstance(prompt, list)
    headers = _api_headers(use_cache)
    body = _api_body(prompt, max_tokens, model=model)

    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=300,
            )
            if r.status_code == 529 or r.status_code >= 500:
                # Overloaded / server error → retry
                last_err = f"{r.status_code} {r.reason}: {r.text[:300]}"
                _time.sleep(2 ** attempt)
                continue
            if not r.ok:
                raise RuntimeError(f"{r.status_code} {r.reason}: {r.text[:500]}")
            return r.json()["content"][0]["text"]
        except requests.exceptions.Timeout:
            last_err = "Timeout – serveren svarede ikke inden for 5 minutter."
            _time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            last_err = "Netværksfejl – kunne ikke nå API'et."
            _time.sleep(2 ** attempt)
    raise RuntimeError(last_err or "Ukendt fejl efter 3 forsøg.")


def _llm_stream(prompt, max_tokens: int = 2000, placeholder=None):
    """Stream svar fra Claude direkte ind i en Streamlit-placeholder.
    Returnerer den samlede tekst. Hvis placeholder=None, falder tilbage til _llm().
    prompt kan være en str eller en liste af content-blokke.
    """
    if placeholder is None:
        return _llm(prompt, max_tokens)

    key = hent_nøgle("ANTHROPIC_API_KEY")
    if not key:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets (Settings → Secrets)."

    use_cache = isinstance(prompt, list)
    headers = _api_headers(use_cache)
    body = _api_body(prompt, max_tokens, stream=True)

    last_err = None
    for attempt in range(3):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
                timeout=300,
                stream=True,
            )
            if r.status_code == 529 or r.status_code >= 500:
                last_err = f"{r.status_code} {r.reason}"
                _time.sleep(2 ** attempt)
                continue
            if not r.ok:
                raise RuntimeError(f"{r.status_code} {r.reason}: {r.text[:500]}")

            full_text = ""
            for line in r.iter_lines(decode_unicode=True):
                if not line or not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    evt = _json.loads(data_str)
                except _json.JSONDecodeError:
                    continue
                if evt.get("type") == "content_block_delta":
                    delta = evt.get("delta", {})
                    chunk = delta.get("text", "")
                    if chunk:
                        full_text += chunk
                        placeholder.markdown(full_text + "▌")
            placeholder.markdown(full_text)
            return full_text
        except requests.exceptions.Timeout:
            last_err = "Timeout – serveren svarede ikke inden for 5 minutter."
            _time.sleep(2 ** attempt)
        except requests.exceptions.ConnectionError:
            last_err = "Netværksfejl – kunne ikke nå API'et."
            _time.sleep(2 ** attempt)
    raise RuntimeError(last_err or "Ukendt fejl efter 3 forsøg.")


# ── Delte hjælpefunktioner ────────────────────────────────────────────────────
def strip_html(text: str, preserve_headings: bool = False) -> str:
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
        "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
        "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
        "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
        "&sect;": "§", "&para;": "¶", "&copy;": "©", "&reg;": "®",
        "&#167;": "§",
    }
    if preserve_headings:
        # Preserve h2/h3 as structural markers before stripping all other tags
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', lambda m: f'\n## {m.group(1).strip()}\n', text, flags=re.I | re.S)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', lambda m: f'\n### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        text = re.sub(r'<h[456][^>]*>(.*?)</h[456]>', lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        # Bold/strong standalone paragraph → treat as sub-heading
        text = re.sub(r'<p[^>]*>\s*<(?:strong|b)[^>]*>(.*?)</(?:strong|b)>\s*</p>',
                      lambda m: f'\n#### {m.group(1).strip()}\n', text, flags=re.I | re.S)
        # Preserve paragraph/line breaks as newlines
        text = re.sub(r'</p>|<br\s*/?>|</div>', '\n', text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in entities.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    if preserve_headings:
        # Collapse spaces within lines but keep newlines
        lines = [re.sub(r'[ \t]+', ' ', ln).strip() for ln in text.splitlines()]
        # Remove consecutive blank lines
        out_lines: list[str] = []
        prev_blank = False
        for ln in lines:
            is_blank = ln == ""
            if is_blank and prev_blank:
                continue
            out_lines.append(ln)
            prev_blank = is_blank
        return '\n'.join(out_lines).strip()
    return re.sub(r"\s+", " ", text).strip()


_HEADING_WORDS = [
    # Lange/specifikke varianter først (undgår delvis match)
    "Planklagenævnets bemærkninger og afgørelse",
    "Miljø- og Fødevareklagenævnets afgørelse",
    "Nævnets bemærkninger og afgørelse",
    "Begrundelse for afgørelsen",
    "Oplysninger om sagen",
    "Sagens oplysninger",
    "Klagen vedrører",
    "Nævnets bemærkninger",
    "Nævnets vurdering",
    "Nævnets afgørelse",
    "Retlig vurdering",
    "Parternes synspunkter",
    "Faktiske oplysninger",
    "Afgørelse",
    "Begrundelse",
    "Klagen",
    "Sagsforløb",
    "Lovgrundlag",
    "Afstemning",
    "Klagetema",
    "Plangrundlag",
    "Resumé",
    "Konklusion",
]
_HEADING_WORDS.sort(key=len, reverse=True)

_H_OPEN  = ('<div style="display:block;font-size:11.5px;font-weight:700;'
            'color:#475569;text-transform:uppercase;letter-spacing:0.8px;'
            'margin:2.2em 0 0.7em;padding:8px 14px;'
            'background:#f8fafc;border-left:3px solid #2563eb;'
            'border-radius:0 4px 4px 0;">')
_H_CLOSE = '</div>'
# Matcher sætningsafslutning + valgfrit afsnitstal (fx "1." "2)") + overskriftsord
_HEADING_PRE = r'([.!?])\s+(?:\d+[.)]\s+)?'


_H2_STYLE = (
    'display:block;font-size:12.5px;font-weight:700;color:#0f172a;'
    'text-transform:uppercase;letter-spacing:0.8px;'
    'margin:2em 0 0.6em;padding:9px 14px;'
    'background:#f8fafc;border-left:3px solid #2563eb;border-radius:0 4px 4px 0;'
)
_H3_STYLE = (
    'display:block;font-size:11px;font-weight:700;color:#475569;'
    'text-transform:uppercase;letter-spacing:0.8px;'
    'margin:1.5em 0 0.5em;padding:6px 12px;'
    'background:#f8fafc;border-left:2px solid #cbd5e1;border-radius:0 3px 3px 0;'
)
_H4_STYLE = (
    'display:block;font-size:10.5px;font-weight:700;color:#64748b;'
    'text-transform:uppercase;letter-spacing:0.6px;'
    'margin:1.1em 0 0.3em;padding:3px 10px;'
    'border-left:2px dotted #cbd5e1;'
)


def format_afgørelse_tekst(tekst: str) -> str:
    """Formatér råtekst fra afgørelse til HTML med sektionsoverskrifter og afsnit.

    Input kan være multiline tekst med ## / ### markorer fra strip_html(preserve_headings=True)
    eller plain tekst der stadig behandles med regex-fallback.
    """
    _P = 'style="margin:0 0 1.1em;font-size:15px;line-height:1.8;color:#1e293b;font-family:\'Inter\',system-ui,sans-serif;"'

    # Check om inputtet indeholder heading-markers (fra preserve_headings=True)
    has_markers = '\n## ' in tekst or '\n### ' in tekst or tekst.startswith('## ') or tekst.startswith('### ')

    if has_markers:
        # Ny sti: behandl linje for linje
        html_parts: list[str] = []
        para_lines: list[str] = []

        def flush_para():
            if not para_lines:
                return
            text_block = ' '.join(para_lines).strip()
            if not text_block:
                para_lines.clear()
                return
            # Style inline fodnotereferencer
            text_block = re.sub(
                r'\[(\d{1,2})\]',
                r'<sup style="font-size:9px;font-weight:700;color:#2563eb;vertical-align:super;letter-spacing:0;">[\1]</sup>',
                text_block,
            )
            # Split i sætningsgrupper (~280 tegn)
            sentences = re.split(r'(?<=[.!?]) +(?=[A-ZÆØÅ0-9])', text_block)
            buf = ""
            for s in sentences:
                if not buf:
                    buf = s
                elif len(buf) < 280:
                    buf += " " + s
                else:
                    html_parts.append(f'<p {_P}>{buf}</p>')
                    buf = s
            if buf:
                html_parts.append(f'<p {_P}>{buf}</p>')
            para_lines.clear()

        for line in tekst.splitlines():
            stripped = line.strip()
            if stripped.startswith('## '):
                flush_para()
                heading_text = stripped[3:].strip()
                html_parts.append(f'<div style="{_H2_STYLE}">{heading_text}</div>')
            elif stripped.startswith('### '):
                flush_para()
                heading_text = stripped[4:].strip()
                html_parts.append(f'<div style="{_H3_STYLE}">{heading_text}</div>')
            elif stripped.startswith('#### '):
                flush_para()
                heading_text = stripped[5:].strip()
                html_parts.append(f'<div style="{_H4_STYLE}">{heading_text}</div>')
            elif stripped == '':
                # Blank line → paragraph break
                flush_para()
            else:
                para_lines.append(stripped)

        flush_para()
        out = ''.join(html_parts)

    else:
        # Fallback (plain text, ingen markers): gammel regex-logik
        out = tekst.strip()

        # 1. Style inline fodnotereferencer
        out = re.sub(
            r'\[(\d{1,2})\]',
            r'<sup style="font-size:9px;font-weight:700;color:#2563eb;vertical-align:super;letter-spacing:0;">[\1]</sup>',
            out,
        )

        # 2. Kendte overskriftsord midt i tekst
        for h in _HEADING_WORDS:
            esc = re.escape(h)
            out = re.sub(
                rf'{_HEADING_PRE}({esc})\s*:?\s+(?=[A-ZÆØÅ])',
                lambda m, hh=h: m.group(1) + f'</p><div style="{_H2_STYLE}">{hh}</div><p>',
                out,
            )

        # 2b. Overskrift ved tekststart
        for h in _HEADING_WORDS:
            m = re.match(rf'^(?:\d+[.)]\s+)?({re.escape(h)})\s*:?\s+', out)
            if m:
                out = f'<div style="{_H2_STYLE}">{m.group(1)}</div><p>{out[m.end():]}'
                break

        # 3a. Hård split ved nummererede afsnitsmarkører
        _SEP = "§§SPLIT§§"
        out = re.sub(
            r'([.!?])\s+(\d+(?:\.\d+)*\.\s+(?=[A-ZÆØÅ]))',
            lambda m: m.group(1) + _SEP + m.group(2),
            out,
        )

        # 3b. Bløde sætningsgrupper
        hard_blocks = out.split(_SEP)
        chunks: list[str] = []
        for block in hard_blocks:
            sentences = re.split(r'(?<=[.!?]) +(?=[A-ZÆØÅ])', block)
            buf = ""
            for s in sentences:
                if not buf:
                    buf = s
                elif len(buf) < 280:
                    buf += " " + s
                else:
                    chunks.append(buf)
                    buf = s
            if buf:
                chunks.append(buf)

        out = "".join(
            c if (f'style="{_H2_STYLE}"' in c or f'style="{_H3_STYLE}"' in c) else f"<p {_P}>{c}</p>"
            for c in chunks
        )

    return (
        f'<div style="font-family:\'Inter\',system-ui,sans-serif;font-size:15px;'
        f'line-height:1.8;color:#1e293b;max-width:72ch;">{out}</div>'
    )


# ── Markdown → HTML (Claudes svar renderes pænt inde i stylet bubble) ──────────
def md_til_html(md: str) -> str:
    """Konvertér den markdown-undermængde Claude bruger (## overskrifter, **fed**,
    *kursiv*, lister, --- linjer) til HTML.

    Streamlit renderer IKKE markdown inde i rå HTML (fx <div class="chat-assistant">),
    så uden denne konvertering vises ##/**/--- råt. `[Kilde X]`-tokens bevares så
    erstat_kilde_refs() kan markere dem bagefter."""
    import html as _html
    if not md:
        return ""

    def _inline(t: str) -> str:
        t = _html.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![\*\w])\*([^*\n]+)\*(?![\*\w])", r"<em>\1</em>", t)
        return t

    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []
    list_mode = None  # "ul" | "ol" | None

    def flush_para():
        if para:
            out.append(f"<p>{' '.join(para).strip()}</p>")
            para.clear()

    def close_list():
        nonlocal list_mode
        if list_mode:
            out.append(f"</{list_mode}>")
            list_mode = None

    for raw in lines:
        s = raw.strip()
        if not s:
            flush_para(); close_list(); continue
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush_para(); close_list(); out.append("<hr>"); continue
        m = re.match(r"(#{1,4})\s+(.*)", s)
        if m:
            flush_para(); close_list()
            tag = {1: "h2", 2: "h2", 3: "h3", 4: "h4"}[len(m.group(1))]
            out.append(f"<{tag}>{_inline(m.group(2).strip())}</{tag}>")
            continue
        mb = re.match(r"[-*]\s+(.*)", s)
        if mb:
            flush_para()
            if list_mode != "ul":
                close_list(); out.append("<ul>"); list_mode = "ul"
            out.append(f"<li>{_inline(mb.group(1).strip())}</li>")
            continue
        mo = re.match(r"\d+[.)]\s+(.*)", s)
        if mo:
            flush_para()
            if list_mode != "ol":
                close_list(); out.append("<ol>"); list_mode = "ol"
            out.append(f"<li>{_inline(mo.group(1).strip())}</li>")
            continue
        if list_mode:
            close_list()
        para.append(_inline(s))
    flush_para(); close_list()
    return "".join(out)


# ── Notat-eksport (printbart HTML → PDF via browserens print) ─────────────────
def byg_notat_html(spørgsmål: str, svar_md: str, kilder: list) -> str:
    """Byg et selvstændigt, printvenligt HTML-notat af et AI-svar med kildeliste.

    Dependency-frit alternativ til PDF-generering: filen åbnes i browseren og
    skrives ud som PDF (Ctrl+P) med korrekt A4-opsætning. Al styling er inline
    i dokumentet, så filen kan deles som den er."""
    import html as _html
    import datetime as _d

    svar_html = md_til_html(svar_md)

    # [Kilde N] → [Sagsnr År] med diskret accent
    def _ref(m):
        dele = []
        for n in re.findall(r"\d+", m.group(1)):
            i = int(n) - 1
            if 0 <= i < len(kilder):
                k = kilder[i]
                sag = k.get("Sagsnummer") or f"Kilde {n}"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = ""
                dele.append(f'<span class="ref">[{sag} {år}]</span>'.replace(" ]", "]"))
        return " ".join(dele) if dele else m.group(0)

    svar_html = re.sub(r"\[Kilde\s+([\d,\s]+)\]", _ref, svar_html)

    kilde_rows = ""
    for i, k in enumerate(kilder):
        try:
            ds = pd.Timestamp(k["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            ds = "–"
        kilde_rows += (
            f'<tr><td class="knum">{i+1}</td>'
            f'<td><div class="ktitel">{_html.escape(k.get("Titel") or "")}</div>'
            f'<div class="kmeta">{ds} &nbsp;·&nbsp; {_html.escape(k.get("Udfald") or "–")}'
            f' &nbsp;·&nbsp; {_html.escape(k.get("Selskab") or "–")}'
            f' &nbsp;·&nbsp; sag {_html.escape(k.get("Sagsnummer") or "–")}</div>'
            f'<div class="klink">{_html.escape(k.get("Link") or "")}</div></td></tr>'
        )

    dato = _d.date.today().strftime("%d.%m.%Y")
    return f"""<!DOCTYPE html>
<html lang="da"><head><meta charset="utf-8">
<title>Ejnar-notat · {dato}</title>
<style>
  @page {{ size: A4; margin: 22mm 20mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; color: #1a2332; margin: 0;
          -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  .sheet {{ max-width: 720px; margin: 0 auto; padding: 40px 34px 60px; }}
  .head {{ display: flex; justify-content: space-between; align-items: baseline;
           border-bottom: 2.5px solid #1a2332; padding-bottom: 10px; margin-bottom: 6px; }}
  .brand {{ font-family: Inter, system-ui, sans-serif; font-weight: 800; font-size: 17px;
            letter-spacing: 3px; }}
  .brand span {{ color: #2563eb; }}
  .doctype {{ font-family: Inter, system-ui, sans-serif; font-size: 10.5px; color: #64748b;
              text-transform: uppercase; letter-spacing: 1.6px; }}
  .meta {{ font-family: Inter, system-ui, sans-serif; font-size: 11px; color: #64748b;
           margin-bottom: 26px; }}
  .sp-label {{ font-family: Inter, system-ui, sans-serif; font-size: 10px; font-weight: 700;
               text-transform: uppercase; letter-spacing: 1.4px; color: #2563eb; margin: 22px 0 6px; }}
  .spørgsmål {{ font-size: 15.5px; font-weight: 700; line-height: 1.5; margin: 0 0 4px; }}
  .svar {{ font-size: 13.5px; line-height: 1.75; }}
  .svar h2 {{ font-family: Inter, system-ui, sans-serif; font-size: 13px; margin: 1.5em 0 .5em;
              border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
  .svar h3 {{ font-family: Inter, system-ui, sans-serif; font-size: 12px; margin: 1.2em 0 .4em; }}
  .svar p {{ margin: 0 0 .8em; }}
  .svar ul, .svar ol {{ margin: .4em 0 .9em 1.4em; padding: 0; }}
  .svar li {{ margin-bottom: .25em; }}
  .svar hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 1.2em 0; }}
  .ref {{ font-family: Inter, system-ui, sans-serif; font-size: 11px; font-weight: 600;
          color: #2563eb; white-space: nowrap; }}
  .kilder-h {{ font-family: Inter, system-ui, sans-serif; font-size: 10px; font-weight: 700;
               text-transform: uppercase; letter-spacing: 1.4px; color: #64748b;
               border-top: 1.5px solid #1a2332; padding-top: 12px; margin-top: 34px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  td {{ vertical-align: top; padding: 7px 0; border-bottom: 1px solid #eef1f6; }}
  .knum {{ font-family: Inter, system-ui, sans-serif; font-weight: 700; font-size: 11px;
           color: #2563eb; width: 26px; }}
  .ktitel {{ font-size: 12px; font-weight: 700; line-height: 1.45; }}
  .kmeta {{ font-family: Inter, system-ui, sans-serif; font-size: 10.5px; color: #64748b; margin-top: 2px; }}
  .klink {{ font-family: Inter, system-ui, sans-serif; font-size: 9.5px; color: #94a3b8;
            word-break: break-all; margin-top: 2px; }}
  .foot {{ font-family: Inter, system-ui, sans-serif; font-size: 9.5px; color: #94a3b8;
           margin-top: 30px; border-top: 1px solid #eef1f6; padding-top: 10px; line-height: 1.6; }}
  .printhint {{ font-family: Inter, system-ui, sans-serif; background: #eff6ff; border: 1px solid #bfdbfe;
                color: #1d4ed8; font-size: 12px; border-radius: 8px; padding: 10px 14px; margin-bottom: 22px; }}
  @media print {{ .printhint {{ display: none; }} .sheet {{ padding: 0; max-width: none; }} }}
</style></head><body><div class="sheet">
  <div class="printhint">💡 Gem som PDF: tryk <b>Ctrl+P</b> (Mac: ⌘P) og vælg "Gem som PDF". Denne boks kommer ikke med i udskriften.</div>
  <div class="head"><div class="brand">EJNAR<span>.</span></div><div class="doctype">Praksisnotat</div></div>
  <div class="meta">Genereret {dato} · Ankenævnet for Forsikring — ejerskifteforsikring · {len(kilder)} kilder</div>
  <div class="sp-label">Spørgsmål</div>
  <div class="spørgsmål">{_html.escape(spørgsmål or "")}</div>
  <div class="sp-label">Vurdering på baggrund af praksis</div>
  <div class="svar">{svar_html}</div>
  <div class="kilder-h">Kilder ({len(kilder)})</div>
  <table>{kilde_rows}</table>
  <div class="foot">Notatet er genereret med AI på baggrund af de anførte kendelser og er ikke juridisk rådgivning.
  Citater bør efterprøves mod originalkendelserne før brug.</div>
</div></body></html>"""


# ── Citat-udtræk + lækker læservisning med indholdsfortegnelse ─────────────────
def _flex_pattern(quote: str):
    """Byg et fleksibelt regex-mønster af et citat: matcher på tværs af
    tegnsætning/whitespace, så et parafraseret citat stadig kan findes i råteksten."""
    if not quote:
        return None
    words = re.findall(r"\w+", quote, re.UNICODE)
    if len(words) < 3:
        return None
    pat = r"[\W_]+".join(re.escape(w) for w in words[:60])
    try:
        return re.compile(pat, re.IGNORECASE)
    except re.error:
        return None


def citater_i_svar(svar: str, min_len: int = 20) -> list:
    """Returnér alle "..."-citater (inkl. » « og " ") i et AI-svar."""
    if not svar:
        return []
    out, seen = [], set()
    moenstre = [
        r'"([^"]{%d,})"' % min_len,
        r'»([^«]{%d,})«' % min_len,
        r'"([^"]{%d,})"' % min_len,
        r'„([^“]{%d,})“' % min_len,
    ]
    for mnstr in moenstre:
        for m in re.finditer(mnstr, svar):
            c = m.group(1).strip()
            if c and c not in seen:
                seen.add(c)
                out.append(c)
    return out


def citater_for_kilde(svar: str, doc: dict, min_len: int = 20) -> list:
    """Returnér de citater fra svaret der stammer fra netop denne kilde."""
    korpus = _normaliser_citat(doc.get("Tekst") or "")
    if not korpus:
        return []
    hits = []
    for c in citater_i_svar(svar, min_len):
        norm = _normaliser_citat(c)
        if not norm:
            continue
        head = norm[: max(30, int(len(norm) * 0.6))]
        if norm in korpus or head in korpus:
            hits.append(c)
    return hits


def _toc_label(t: str) -> str:
    t = (t or "").strip()
    return t if len(t) <= 46 else t[:44].rstrip() + "…"


_RD_P = ("margin:0 0 1.15em;font-size:15.5px;line-height:1.85;color:#1e293b;"
         "font-family:'Inter',system-ui,sans-serif;")


def byg_lækker_afgørelse(tekst: str, highlight_quotes=None, anchor_prefix: str = "sek"):
    """Returnér (toc_html, body_html) for en afgørelse.

    body_html har <div id="{prefix}-N"> ankre før hver overskrift, og TOC'en linker
    dertil (klik = hop til sektion). highlight_quotes markeres med <mark> i teksten."""
    HL_O, HL_C = "\x01", "\x02"
    raw = tekst or ""

    if highlight_quotes:
        spans = []
        for q in highlight_quotes:
            pat = _flex_pattern(q)
            if pat:
                m = pat.search(raw)
                if m:
                    spans.append((m.start(), m.end()))
        spans.sort(reverse=True)
        last_start = len(raw) + 1
        for s, e in spans:
            if e > last_start:          # spring overlappende spans over
                continue
            raw = raw[:s] + HL_O + raw[s:e] + HL_C + raw[e:]
            last_start = s

    has_markers = ('\n## ' in raw or '\n### ' in raw
                   or raw.startswith('## ') or raw.startswith('### '))
    toc: list = []
    body: list = []
    carry = {"open": False}
    counter = {"n": 0}

    def emit_para(text_block: str):
        text_block = text_block.strip()
        if not text_block:
            return
        text_block = re.sub(
            r'\[(\d{1,2})\]',
            r'<sup style="font-size:9px;font-weight:700;color:#2563eb;'
            r'vertical-align:super;">[\1]</sup>',
            text_block)
        sentences = re.split(r'(?<=[.!?]) +(?=[A-ZÆØÅ0-9])', text_block)
        buf, chunks = "", []
        for s in sentences:
            if not buf:
                buf = s
            elif len(buf) < 320:
                buf += " " + s
            else:
                chunks.append(buf); buf = s
        if buf:
            chunks.append(buf)
        for c in chunks:
            if carry["open"]:
                c = HL_O + c
            opens, closes = c.count(HL_O), c.count(HL_C)
            if opens > closes:
                c += HL_C; carry["open"] = True
            elif closes >= opens and carry["open"] and closes > 0:
                carry["open"] = False
            body.append(f'<p style="{_RD_P}">{c}</p>')

    if has_markers:
        para_lines: list = []

        def flush():
            if para_lines:
                emit_para(' '.join(para_lines)); para_lines.clear()

        for line in raw.splitlines():
            st_ = line.strip()
            if st_.startswith('## '):
                flush()
                counter["n"] += 1
                aid = f"{anchor_prefix}-{counter['n']}"
                title = st_[3:].strip().replace(HL_O, "").replace(HL_C, "")
                toc.append((2, title, aid))
                body.append(f'<div id="{aid}" class="rd-h2">{title}</div>')
            elif st_.startswith('### '):
                flush()
                counter["n"] += 1
                aid = f"{anchor_prefix}-{counter['n']}"
                title = st_[4:].strip().replace(HL_O, "").replace(HL_C, "")
                toc.append((3, title, aid))
                body.append(f'<div id="{aid}" class="rd-h3">{title}</div>')
            elif st_.startswith('#### '):
                flush()
                title = st_[5:].strip().replace(HL_O, "").replace(HL_C, "")
                body.append(f'<div class="rd-h4">{title}</div>')
            elif st_ == '':
                flush()
            else:
                para_lines.append(st_)
        flush()
    else:
        emit_para(raw)

    body_html = ''.join(body)
    body_html = (body_html.replace(HL_O, '<mark class="rd-cite">')
                          .replace(HL_C, '</mark>'))

    if toc:
        items = ''.join(
            f'<a href="#{aid}" class="rd-toc-link rd-toc-l{lvl}">{_toc_label(title)}</a>'
            for lvl, title, aid in toc
        )
        toc_html = f'<div class="rd-toc"><div class="rd-toc-h">Indhold</div>{items}</div>'
    else:
        toc_html = ""
    return toc_html, body_html


def udtræk_kerneafsnit(tekst: str, max_tegn: int = 8000) -> str:
    """Udtræk de vigtigste sektioner fra en afgørelse (klagen + vurdering/afgørelse).
    Springer 'Sagens oplysninger' og andre faktuelle sektioner over."""
    sektioner = re.split(r'\n(#{2,3} .+)', tekst)

    dele = []
    for i, del_ in enumerate(sektioner):
        if del_.startswith('## ') or del_.startswith('### '):
            indhold = sektioner[i + 1] if i + 1 < len(sektioner) else ""
            dele.append((del_.lstrip('#').strip().lower(), indhold.strip()))

    prioritet = [
        "klagen",
        "klagen vedrører",
        "planklagenævnets bemærkninger og afgørelse",
        "miljø- og fødevareklagenævnets afgørelse",
        "nævnets bemærkninger og afgørelse",
        "nævnets vurdering",
        "retlig vurdering",
        "begrundelse for afgørelsen",
        "begrundelse",
        "afgørelse",
        "nævnets bemærkninger",
        "afsluttende bemærkninger",
        "konklusion",
    ]

    udtræk = []
    brugt = 0
    for prio in prioritet:
        for heading, indhold in dele:
            if prio in heading and indhold:
                tekst_del = f"[{heading.upper()}]\n{indhold}"
                if brugt + len(tekst_del) <= max_tegn:
                    udtræk.append(tekst_del)
                    brugt += len(tekst_del)

    if udtræk:
        return "\n\n".join(udtræk)
    return tekst[-max_tegn:]


def byg_indeks_tekst(titel: str, tekst: str, max_tegn: int = 6000) -> str:
    """Byg søgetekst til TF-IDF-indekset:
    titel gentages 3x (boost), efterfulgt af kerneafsnit.
    Dette fokuserer scoring på det juridisk relevante – ikke 'sagens oplysninger'."""
    t = titel or ""
    kerne = udtræk_kerneafsnit(tekst or "", max_tegn=max_tegn)
    return f"{t} {t} {t} {kerne}"


# ── Dansk stemming til TF-IDF ────────────────────────────────────────────────
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


def chunk_tekst(tekst: str, titel: str = "", chunk_size: int = 500, overlap: int = 80) -> list:
    """Del en afgørelsestekst i overlappende chunks à ~chunk_size tokens.
    Hvert chunk bærer titel-kontekst for bedre retrieval.
    Returnerer liste af chunk-strenge."""
    if not tekst:
        return [titel] if titel else []
    ord_liste = tekst.split()
    if len(ord_liste) <= chunk_size:
        return [f"{titel}\n{tekst}" if titel else tekst]
    chunks = []
    start = 0
    while start < len(ord_liste):
        end = min(start + chunk_size, len(ord_liste))
        chunk = " ".join(ord_liste[start:end])
        if titel:
            chunk = f"{titel}\n{chunk}"
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


_QV_MEMO: dict = {}


def _embed_query_memo(query: str):
    """Embed query til chunk-udvælgelse — memoiseret så retrieval og
    kontekst-bygning i samme tur ikke koster to API-kald."""
    if query in _QV_MEMO:
        return _QV_MEMO[query]
    try:
        qv = _embed_query(query)
    except Exception:
        qv = None
    if qv is not None:
        if len(_QV_MEMO) > 8:
            _QV_MEMO.clear()
        _QV_MEMO[query] = qv
    return qv


# Geometri fra build_embeddings.py: CHUNK_SIZE=1000 tokens ≈ 770 ord,
# CHUNK_OVERLAP=150 tokens ≈ 115 ord → stride 655 ord pr. chunk.
_BUILD_CHUNK_ORD = 770
_BUILD_STRIDE = 655


def _chunk_span_tekst(tekst: str, ordinal: int) -> str:
    """Rekonstruér (tilnærmet) teksten for chunk nr. `ordinal` med build-geometrien.
    Build og app renser HTML let forskelligt, så spans kan være forskudt få ord —
    acceptabelt til LLM-kontekst, hvor vi blot skal ramme det rigtige afsnit."""
    ord_liste = (tekst or "").split()
    if len(ord_liste) <= _BUILD_CHUNK_ORD:
        return tekst or ""
    start = ordinal * _BUILD_STRIDE
    if start >= len(ord_liste):
        start = max(0, len(ord_liste) - _BUILD_CHUNK_ORD)
    return " ".join(ord_liste[start:start + _BUILD_CHUNK_ORD])


def byg_fokuseret_kontekst(query: str, docs: list, max_chunks_per_doc: int = 3,
                            chunk_size: int = 400, max_total_chars: int = 24000,
                            embeds=None, link_til_idx=None) -> str:
    """Chunk-level kontekst-udvælgelse til LLM-svaret.

    Foretrukket: SEMANTISK udvælgelse — scorer dokumentets chunk-vektorer fra
    embedding-indekset mod query-vektoren, så pointer der ikke deler ord med
    spørgsmålet også kommer med i konteksten. Kræver embeds (chunk-dict),
    link_til_idx (Link→df-række) og en Voyage-nøgle.

    Fallback (pr. dokument og globalt): mini-TF-IDF over on-the-fly chunks som
    hidtil. Returnerer formateret kontekst med [Kilde N]-headers bevaret."""
    if not docs:
        return ""

    # ── Semantisk udvælgelse hvor muligt ─────────────────────────────────────
    sem_content: dict = {}
    if isinstance(embeds, dict) and "chunk_to_doc" in embeds and link_til_idx:
        qv = _embed_query_memo(query)
        if qv is not None:
            vectors = embeds["vectors"]
            ctd = embeds["chunk_to_doc"]
            for i, d in enumerate(docs):
                gidx = link_til_idx.get(str(d.get("Link", "")))
                if gidx is None:
                    continue
                vec_idx = np.where(ctd == gidx)[0]
                if vec_idx.size == 0:
                    continue
                scores = vectors[vec_idx] @ qv
                orden = np.argsort(-scores)[:max_chunks_per_doc]
                # ordinal = chunkens plads i dokumentet (vec_idx er i build-rækkefølge)
                ordinaler = sorted(int(o) for o in orden)
                tekst = d.get("Tekst") or ""
                spans = [_chunk_span_tekst(tekst, o) for o in ordinaler]
                spans = [s for s in spans if s.strip()]
                if spans:
                    sem_content[i] = "\n[…]\n".join(dict.fromkeys(spans))

    # ── TF-IDF-fallback for resten ───────────────────────────────────────────
    mangler = [i for i in range(len(docs)) if i not in sem_content]
    tfidf_content: dict = {}
    if mangler:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity as _cos
            all_chunks = []     # (kilde_idx, chunk_text)
            for i in mangler:
                d = docs[i]
                kerne = udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=6000)
                chunks = chunk_tekst(kerne, titel="", chunk_size=chunk_size, overlap=80)
                if not chunks:
                    chunks = [kerne[:3000]] if kerne else [d.get("Titel", "")]
                for c in chunks:
                    all_chunks.append((i, c))
            if all_chunks:
                chunk_texts = [c for _, c in all_chunks]
                try:
                    mini_vec = TfidfVectorizer(max_features=20_000, ngram_range=(1, 2),
                                               sublinear_tf=True)
                    chunk_mat = mini_vec.fit_transform(chunk_texts)
                    qv2 = mini_vec.transform([query])
                    scores = _cos(qv2, chunk_mat).flatten()
                except Exception:
                    scores = np.ones(len(all_chunks))
                from collections import defaultdict
                kilde_chunks = defaultdict(list)
                for idx, (kilde_i, chunk) in enumerate(all_chunks):
                    kilde_chunks[kilde_i].append((float(scores[idx]), chunk))
                for i in mangler:
                    best = sorted(kilde_chunks.get(i, []), key=lambda x: -x[0])[:max_chunks_per_doc]
                    if best:
                        tfidf_content[i] = "\n[…]\n".join(c for _, c in best)
        except ImportError:
            pass

    # ── Saml i kilde-rækkefølge med budget ───────────────────────────────────
    dele = []
    total_chars = 0
    for i, d in enumerate(docs):
        header = f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}"
        content = sem_content.get(i) or tfidf_content.get(i) \
            or udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=2000)
        entry = f"{header}\n{content}"
        if total_chars + len(entry) > max_total_chars:
            # Afkort sidste kilde
            remaining = max_total_chars - total_chars
            if remaining > 500:
                dele.append(entry[:remaining] + "…")
            break
        dele.append(entry)
        total_chars += len(entry)
    return "\n\n".join(dele)


def klassificer_query(query: str) -> dict:
    """Klassificér query-type med Haiku for at tilpasse retrieval-parametre.
    Returnerer dict med 'type' (faktuel/sammenligning/procedure/åben) og
    'top_k' (antal dokumenter at hente).

    - faktuel: specifik juridisk kendsgerning → færre, præcise hits
    - sammenligning: 'hvornår gives medhold vs afvist' → flere hits for bredde
    - procedure: processuelt spørgsmål → moderat
    - åben: bredt eksplorativt → mange hits"""
    default = {"type": "åben", "top_retrieve": 40, "top_final": 8}
    if not query or len(query) < 5:
        return default
    prompt = (
        "Klassificér dette juridiske spørgsmål i én af fire kategorier:\n"
        "- FAKTUEL: spørger til en specifik regel, afgørelse eller kendsgerning\n"
        "- SAMMENLIGNING: sammenligner praksis, vil se mønstre/tendenser på tværs\n"
        "- PROCEDURE: handler om proces, frister, kompetence, klagevej\n"
        "- ÅBEN: bredt, eksplorativt eller uklart spørgsmål\n\n"
        f"Spørgsmål: \"{query}\"\n\n"
        "Svar med KUN ét ord (FAKTUEL/SAMMENLIGNING/PROCEDURE/ÅBEN):"
    )
    svar = _llm_haiku(prompt, max_tokens=10).strip().upper()
    if "FAKTUEL" in svar:
        return {"type": "faktuel", "top_retrieve": 25, "top_final": 6}
    elif "SAMMENLIGNING" in svar:
        return {"type": "sammenligning", "top_retrieve": 60, "top_final": 12}
    elif "PROCEDURE" in svar:
        return {"type": "procedure", "top_retrieve": 30, "top_final": 8}
    return default


def auto_filter_query(query: str, filter_options: dict) -> dict:
    """Use Haiku to extract implicit filter preferences from a user's question.
    filter_options = {"Kategori": ["val1", ...], "Plantype": ["val1", ...], ...}
    Returns dict of suggested filters, e.g. {"Kategori": ["Kommuneplan"]}."""
    if not query or not filter_options or len(query) < 10:
        return {}
    lines = []
    for name, vals in filter_options.items():
        lines.append(f"- {name}: [{', '.join(str(v) for v in vals[:40])}]")
    filter_desc = "\n".join(lines)
    prompt = (
        "Analysér dette juridiske spørgsmål og foreslå filtre der vil indsnævre "
        "søgningen til de mest relevante kendelser fra Ankenævnet for Forsikring "
        "om ejerskifteforsikring.\n\n"
        f"SPØRGSMÅL: \"{query}\"\n\n"
        f"TILGÆNGELIGE FILTRE (brug KUN værdier fra listerne):\n{filter_desc}\n\n"
        "REGLER:\n"
        "- Foreslå filtre der er impliceret af spørgsmålet — også når brugeren bruger "
        "flertalsformer som \"skimmelsager\", \"tagsager\" eller \"kloakker\".\n"
        "- Kopiér værdien PRÆCIS som den står i listen (ental, stavning, store/små bogstaver) — "
        "fx \"Skimmel/fugt\" (IKKE \"Skimmelsager\"), \"Tag/tagdækning\" (IKKE \"Tage\").\n"
        "- Vær konservativ — hellere for få filtre end for mange.\n"
        "- Undgå Udfald-filtre medmindre spørgsmålet eksplicit nævner udfald.\n"
        "- Hvis ingen filtre er tydelige, skriv: INGEN\n\n"
        "Svar i format (ét filter per linje, ingen forklaring):\n"
        "Filternavn: Værdi1, Værdi2\n\n"
        "FILTRE:"
    )
    svar = _llm_haiku(prompt, max_tokens=150)
    if not svar or "INGEN" in svar.upper()[:30]:
        return {}
    suggested = {}
    for line in svar.strip().split("\n"):
        line = line.strip().lstrip("- ")
        if ":" not in line or "INGEN" in line.upper():
            continue
        parts = line.split(":", 1)
        name_raw = parts[0].strip()
        vals_raw = parts[1].strip()
        matched_name = None
        for fn in filter_options:
            if fn.lower() == name_raw.lower():
                matched_name = fn
                break
        if not matched_name:
            for fn in filter_options:
                if fn.lower() in name_raw.lower() or name_raw.lower() in fn.lower():
                    matched_name = fn
                    break
        if not matched_name:
            continue
        raw_vals = [v.strip() for v in vals_raw.split(",")]
        valid = []
        for rv in raw_vals:
            if not rv:
                continue
            rv_l = rv.lower().rstrip(".")
            # Normalisér danske bøjningsendelser: "kommuneplaner"→"kommuneplan",
            # "screeningsafgørelser"→"screeningsafgørelse" osv.
            def _stem(s):
                s = s.lower().rstrip(".")
                for suf in ("erne", "ene", "er", "en", "et", "e", "r"):
                    if s.endswith(suf) and len(s) - len(suf) >= 4:
                        return s[:-len(suf)]
                return s
            rv_stem = _stem(rv_l)
            match_opt = None
            for opt in filter_options[matched_name]:
                ol = str(opt).lower()
                if rv_l == ol:
                    match_opt = opt
                    break
            if not match_opt:
                for opt in filter_options[matched_name]:
                    ol = str(opt).lower()
                    ol_stem = _stem(ol)
                    if rv_stem == ol_stem or rv_stem == ol or rv_l == ol_stem:
                        match_opt = opt
                        break
            if not match_opt:
                # Substring-fallback: "kommuneplan" ⊂ "kommuneplantillæg" må IKKE matche,
                # så vi kræver at stem-formerne er identiske eller at den ene starter med den anden
                # og længdeforskellen er ≤ 2 (bøjning).
                for opt in filter_options[matched_name]:
                    ol = str(opt).lower()
                    if (rv_l.startswith(ol) or ol.startswith(rv_l)) and abs(len(rv_l) - len(ol)) <= 3:
                        match_opt = opt
                        break
            if match_opt and match_opt not in valid:
                valid.append(match_opt)
        if valid:
            suggested[matched_name] = valid
    return suggested


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


def _llm_haiku(prompt: str, max_tokens: int = 400) -> str:
    """Billig/hurtig Claude Haiku-kald til query expansion, rewriting og reranking.
    Returnerer tom streng ved fejl – kalderen falder tilbage til original adfærd."""
    try:
        return _llm(prompt, max_tokens=max_tokens, model="claude-haiku-4-5-20251001")
    except Exception:
        return ""


# ── Embeddings (Voyage AI primær, OpenAI fallback) ───────────────────────────
_EMBED_LAST_ERROR: list = []  # module-level så den er tilgængelig fra cache_resource kontekst


def get_embed_error() -> str:
    return _EMBED_LAST_ERROR[0] if _EMBED_LAST_ERROR else ""


def _embedding_provider() -> tuple:
    """Returnerer (provider_navn, api_key, model, dim) baseret på tilgængelige secrets.
    Preferer Voyage 3-large (bedst til dansk + chunk-niveau retrieval),
    falder tilbage til OpenAI."""
    voyage_key = hent_nøgle("VOYAGE_API_KEY")
    if voyage_key:
        return ("voyage", voyage_key, "voyage-3-large", 1024)
    openai_key = hent_nøgle("OPENAI_API_KEY")
    if openai_key:
        return ("openai", openai_key, "text-embedding-3-small", 1536)
    return (None, None, None, 0)


def embeddings_tilgængelige() -> bool:
    return _embedding_provider()[0] is not None


def _embed_batch(texts: list, input_type: str = "document", _retries: int = 4) -> "np.ndarray | None":
    """Embed en batch af tekster med retry ved rate-limit (429).
    Returnerer numpy array shape (N, dim) eller None ved fejl."""
    import time as _time
    provider, key, model, dim = _embedding_provider()
    if not provider or not texts:
        return None
    url = ("https://api.voyageai.com/v1/embeddings" if provider == "voyage"
           else "https://api.openai.com/v1/embeddings")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {"input": texts, "model": model}
    if provider == "voyage":
        payload.update({"input_type": input_type, "truncation": True})

    for attempt in range(_retries + 1):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.ok:
                data = r.json().get("data", [])
                return np.array([d["embedding"] for d in data], dtype=np.float32)
            if r.status_code == 429 and attempt < _retries:
                wait = min(2 ** (attempt + 1), 30)
                _time.sleep(wait)
                continue
            _EMBED_LAST_ERROR[:] = [f"{provider.title()} API {r.status_code}: {r.text[:300]}"]
            return None
        except Exception as e:
            if attempt < _retries:
                _time.sleep(2 ** (attempt + 1))
                continue
            _EMBED_LAST_ERROR[:] = [f"Exception: {e}"]
            return None
    return None


def _embed_query(query: str) -> "np.ndarray | None":
    """Embed en enkelt forespørgsel. Returnerer 1D array (dim,) eller None."""
    if not query:
        return None
    arr = _embed_batch([query], input_type="query")
    if arr is None or len(arr) == 0:
        return None
    # Normalisér til unit vector for hurtig cosine via dot product
    v = arr[0]
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _hyde_embed(query: str) -> "np.ndarray | None":
    """HyDE (Hypothetical Document Embeddings): generer et hypotetisk svar
    med Haiku og embed det i stedet for det rå spørgsmål.
    Dette forbedrer retrieval fordi det hypotetiske svar bruger samme
    terminologi og stil som de rigtige afgørelser.
    Returnerer normaliseret embedding eller None."""
    if not query or not embeddings_tilgængelige():
        return None
    # Generer hypotetisk afgørelsesafsnit
    hyde_prompt = (
        "Du er Ankenævnet for Forsikring og afgør sager om ejerskifteforsikring. "
        "Skriv et kort uddrag (100-150 ord) af en hypotetisk nævnskendelse "
        "der besvarer dette spørgsmål. Brug nævnets typiske sprog og forsikringsretlige "
        "termer (mangler ved bygning, dækning, selvrisiko, lov om forbrugerbeskyttelse "
        "ved erhvervelse af fast ejendom mv., tilstandsrapport, byggeskik, levetid mv.). "
        "Skriv KUN uddraget – ingen indledning.\n\n"
        f"Spørgsmål: {query}\n\nUddrag:"
    )
    hyp = _llm_haiku(hyde_prompt, max_tokens=250)
    if not hyp or len(hyp) < 30:
        return _embed_query(query)  # fallback til rå query
    # Embed det hypotetiske svar + den originale query (begge signaler)
    combined = f"{query}\n\n{hyp}"
    arr = _embed_batch([combined], input_type="query")
    if arr is None or len(arr) == 0:
        return _embed_query(query)
    v = arr[0]
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _delete_embedding_from_github(fname: str) -> bool:
    """Slet en embedding-fil fra GitHub (bruges til at fjerne partial efter komplet build)."""
    token = hent_nøgle("GITHUB_TOKEN").strip()
    if not token:
        return False
    repo = "simo224i-eng/pkn-vidensbase"
    url = f"https://api.github.com/repos/{repo}/contents/ejnar/embeds/{fname}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return False
        sha = r.json().get("sha", "")
        r2 = requests.delete(url, headers=headers, json={
            "message": f"Fjern partial-cache: {fname}",
            "sha": sha,
            "branch": "main",
        }, timeout=30)
        return r2.status_code == 200
    except Exception:
        return False


def _push_embedding_to_github(fname: str, local_path: str, overwrite: bool = False) -> str:
    """Push embedding-fil til GitHub. Returnerer status-streng for debug."""
    import os as _os
    token = hent_nøgle("GITHUB_TOKEN").strip()
    if not token:
        return "SKIP: ingen GITHUB_TOKEN"
    if not _os.path.exists(local_path):
        return f"SKIP: fil ikke fundet: {local_path}"
    fsize = _os.path.getsize(local_path)
    if fsize > 80_000_000:
        return f"SKIP: fil for stor ({fsize} bytes)"
    repo = "simo224i-eng/pkn-vidensbase"
    repo_path = f"ejnar/embeds/{fname}"
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        existing_sha = None
        if r.status_code == 200:
            if not overwrite:
                return "SKIP: eksisterer allerede på GitHub"
            existing_sha = r.json().get("sha")
        elif r.status_code == 401:
            return f"FEJL: ugyldig token (401)"
        elif r.status_code == 403:
            return f"FEJL: ingen adgang (403)"
        import base64 as _b64_push
        with open(local_path, "rb") as f:
            content = _b64_push.b64encode(f.read()).decode()
        data = {
            "message": f"Gem embedding-cache: {fname}",
            "content": content,
            "branch": "main",
        }
        if existing_sha:
            data["sha"] = existing_sha
        r = requests.put(url, headers=headers, json=data, timeout=300)
        if r.status_code in (200, 201):
            return f"OK: pushet ({fsize//1024}KB)"
        return f"FEJL: HTTP {r.status_code} — {r.text[:200]}"
    except Exception as e:
        return f"FEJL: {type(e).__name__}: {e}"


def _download_embedding_from_github(fname: str, save_dir: str) -> str | None:
    """Hent embedding-fil fra GitHub repo hvis den eksisterer.
    Returnerer lokal sti til filen, eller None."""
    import os as _os
    token = hent_nøgle("GITHUB_TOKEN").strip()
    if not token:
        return None
    repo = "simo224i-eng/pkn-vidensbase"
    repo_path = f"ejnar/embeds/{fname}"
    url = f"https://api.github.com/repos/{repo}/contents/{repo_path}"
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(url, headers=headers, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        download_url = data.get("download_url")
        if not download_url:
            return None
        r2 = requests.get(download_url, headers={"Authorization": f"token {token}"}, timeout=120)
        if r2.status_code != 200:
            return None
        _os.makedirs(save_dir, exist_ok=True)
        out_path = _os.path.join(save_dir, fname)
        with open(out_path, "wb") as f:
            f.write(r2.content)
        return out_path
    except Exception:
        return None


def _remap_chunk_docs(vectors, chunk_to_doc, doc_links, link_til_idx):
    """Remap chunk→doc-indekser fra build'ets egen dokumentliste til appens df-rækker
    via kendelses-links. Returnerer (vectors, ny_chunk_to_doc, antal_mappede_docs).

    Nødvendigt fordi build og app kan deduplikere/ordne forskelligt — links er
    den eneste stabile nøgle på tværs. Chunks hvis kendelse ikke findes i df
    (fjernet/omdøbt) droppes."""
    arr_map = np.array([link_til_idx.get(l, -1) for l in doc_links], dtype=np.int64)
    ny_ctd = arr_map[chunk_to_doc]
    keep = ny_ctd >= 0
    n_mapped = int((arr_map >= 0).sum())
    if keep.all():
        return vectors, ny_ctd.astype(np.int32), n_mapped
    return vectors[keep], ny_ctd[keep].astype(np.int32), n_mapped


def _load_chunked_embeds(cache_key: str, n_docs: int, df=None):
    """Find og indlæs chunk-niveau embeddings (chunk_to_doc-mapping).

    Robust link-baseret indlæsning: hvis .npz'en (eller en `…__links.npz`-sidecar)
    indeholder `doc_links`, remappes chunk→doc via kendelses-links til den AKTUELLE
    df — så indekset virker selv når datasættet er vokset eller build/app
    deduplikerer forskelligt. (Tidligere krævedes eksakt n_docs-match i filnavnet,
    hvilket forkastede hele indekset når CSV'en fik nye rækker — og build'ets
    titel-dedup matchede aldrig appens link-dedup.)

    Returnér dict {"vectors", "chunk_to_doc", "n_docs", "model", "dækning"} eller None."""
    import os as _os, glob as _glob
    provider, _key, model, dim = _embedding_provider()
    if not provider:
        return None
    _app_root = _os.path.dirname(_os.path.abspath(__file__))
    _git_dir = _os.path.join(_app_root, "embeds")
    _tmp_dir = "/tmp/ejnar_data/embeds"

    # Link-baseret sti (foretrukket): alle chunk-builds uanset doc-antal i navnet
    if df is not None and len(df) > 0 and "Link" in df.columns:
        link_til_idx = {str(l): i for i, l in enumerate(df["Link"])}
        alle = []
        for d in (_git_dir, _tmp_dir):
            alle.extend(p for p in _glob.glob(_os.path.join(d, f"{cache_key}__{provider}__{model}__*d_*c.npz"))
                        if "__links" not in _os.path.basename(p))
        for path in sorted(alle):
            try:
                data = np.load(path, allow_pickle=True)
                if "embeddings" not in data.files or "chunk_to_doc" not in data.files:
                    continue
                if "doc_links" in data.files:
                    doc_links = [str(x) for x in data["doc_links"]]
                else:
                    sidecar = path[:-4] + "__links.npz"
                    if not _os.path.exists(sidecar):
                        continue
                    doc_links = [str(x) for x in np.load(sidecar, allow_pickle=True)["doc_links"]]
                vectors = data["embeddings"]
                if vectors.dtype == np.float16:
                    vectors = vectors.astype(np.float32)
                ctd = data["chunk_to_doc"].astype(np.int64)
                if len(doc_links) <= int(ctd.max()):
                    continue
                vectors, ny_ctd, n_mapped = _remap_chunk_docs(vectors, ctd, doc_links, link_til_idx)
                # Kræv at mindst halvdelen af df er dækket — ellers er indekset for gammelt
                if n_mapped < max(1, len(df) // 2):
                    continue
                return {
                    "vectors": vectors,
                    "chunk_to_doc": ny_ctd,
                    "n_docs": len(df),
                    "model": model,
                    "dækning": (n_mapped, len(df)),
                }
            except Exception:
                continue

    # Legacy-sti: eksakt n_docs-match uden links
    pattern = f"{cache_key}__{provider}__{model}__{n_docs}d_*c.npz"

    candidates = []
    for d in (_git_dir, _tmp_dir):
        candidates.extend(_glob.glob(_os.path.join(d, pattern)))

    # Prøv også at hente fra GitHub hvis vi ikke fandt det lokalt
    if not candidates:
        try:
            # GitHub: liste ejnar/embeds/ og find matching navn
            import requests as _req
            token = hent_nøgle("GITHUB_TOKEN").strip()
            if token:
                repo = "simo224i-eng/pkn-vidensbase"
                url = f"https://api.github.com/repos/{repo}/contents/ejnar/embeds"
                r = _req.get(url, headers={"Authorization": f"token {token}"}, timeout=30)
                if r.ok:
                    name_prefix = f"{cache_key}__{provider}__{model}__{n_docs}d_"
                    for entry in r.json():
                        if entry["name"].startswith(name_prefix) and entry["name"].endswith("c.npz"):
                            _dl = _download_embedding_from_github(entry["name"], _tmp_dir)
                            if _dl:
                                candidates.append(_dl)
                                break
        except Exception:
            pass

    if not candidates:
        return None

    for path in candidates:
        try:
            data = np.load(path)
            if "embeddings" not in data.files or "chunk_to_doc" not in data.files:
                continue
            vectors = data["embeddings"]
            if vectors.dtype == np.float16:
                vectors = vectors.astype(np.float32)
            chunk_to_doc = data["chunk_to_doc"].astype(np.int32)
            stored_n_docs = int(data["n_docs"]) if "n_docs" in data.files else n_docs
            if stored_n_docs != n_docs:
                continue
            return {
                "vectors": vectors,
                "chunk_to_doc": chunk_to_doc,
                "n_docs": n_docs,
                "model": model,
            }
        except Exception:
            continue
    return None


def byg_embeddings_indeks(df, cache_key: str, tekst_bygger=None, batch_size: int = 32):
    """Byg/indlæs persistent embedding-indeks.

    Foretrækker chunk-niveau format (nyere builds). Falder tilbage til doc-niveau
    format hvis kun det findes. Som sidste udvej bygges fra API on-the-fly.

    Returnerer:
      - dict med {"vectors", "chunk_to_doc", "n_docs"} for chunk-niveau, ELLER
      - ndarray for doc-niveau (gammelt format),
      - None hvis intet kunne loades/bygges.
    embedding_soeg() håndterer begge typer."""
    # 1. Forsøg at indlæse chunk-niveau (nyt format) — link-remappet til df
    chunked = _load_chunked_embeds(cache_key, len(df) if df is not None else 0, df=df)
    if chunked is not None:
        return chunked
    # 2. Fald tilbage til gammelt doc-niveau format (eller byg fra API)
    return _byg_embeddings_indeks_legacy(df, cache_key, tekst_bygger, batch_size)


def _byg_embeddings_indeks_legacy(df, cache_key: str, tekst_bygger=None, batch_size: int = 32) -> "np.ndarray | None":
    """Doc-niveau embeddings — gammelt format. Bevares for bagudkompatibilitet
    og for tilfælde hvor en chunk-build ikke er kørt offline endnu."""
    provider, _key, model, dim = _embedding_provider()
    if not provider or df is None or len(df) == 0:
        return None
    if tekst_bygger is None:
        tekst_bygger = lambda t, x: byg_indeks_tekst(t, x, max_tegn=4000)

    import os as _os
    _fname = f"{cache_key}__{provider}__{model}__{len(df)}.npz"
    _app_root = _os.path.dirname(_os.path.abspath(__file__))
    _git_dir = _os.path.join(_app_root, "embeds")
    _tmp_dir = "/tmp/ejnar_data/embeds"

    def _try_load(path):
        if not _os.path.exists(path):
            return None
        try:
            arr = np.load(path)["arr_0"]
            if arr.dtype == np.float16:
                arr = arr.astype(np.float32)
            if arr.shape == (len(df), dim):
                return arr
        except Exception:
            pass
        return None

    # 1. Tjek lokale filer (git-tracked embeds/ og /tmp cache)
    for d in [_git_dir, _tmp_dir]:
        loaded = _try_load(_os.path.join(d, _fname))
        if loaded is not None:
            return loaded

    # 2. Hent fra GitHub API (hvis pushel lykkedes ved en tidligere build)
    try:
        _dl = _download_embedding_from_github(_fname, _tmp_dir)
        if _dl:
            loaded = _try_load(_dl)
            if loaded is not None:
                return loaded
    except Exception:
        pass

    # 3. Byg fra API (med resume-support: gem partial ved fejl)
    texts = [tekst_bygger(str(t), str(x))[:8000]
             for t, x in zip(df["Titel"].fillna(""), df["Tekst"].fillna(""))]

    out = np.zeros((len(texts), dim), dtype=np.float32)
    start_batch = 0

    # Tjek for partial (halvfærdigt) build — lokalt eller på GitHub
    _partial_fname = f"{cache_key}__partial__{provider}__{model}__{len(df)}.npz"
    _partial_path = _os.path.join(_tmp_dir, _partial_fname)

    def _load_partial():
        """Forsøg at loade partial fra /tmp/ eller GitHub."""
        # Lokal først
        if _os.path.exists(_partial_path):
            try:
                _pdata = np.load(_partial_path)
                return _pdata["embeddings"], int(_pdata["n_done"])
            except Exception:
                pass
        # Hent fra GitHub hvis ikke lokalt
        try:
            _dl = _download_embedding_from_github(_partial_fname, _tmp_dir)
            if _dl:
                _pdata = np.load(_dl)
                return _pdata["embeddings"], int(_pdata["n_done"])
        except Exception:
            pass
        return None, 0

    _parr, _pdone = _load_partial()
    if _parr is not None and _parr.shape == (len(df), dim) and _pdone > 0:
        if _parr.dtype == np.float16:
            _parr = _parr.astype(np.float32)
        out[:_pdone] = _parr[:_pdone]
        start_batch = _pdone // batch_size

    progress = None
    try:
        progress = st.progress(0.0, text=f"Bygger semantisk indeks ({cache_key})…")
    except Exception:
        pass

    n_batches = (len(texts) + batch_size - 1) // batch_size
    for b in range(start_batch, n_batches):
        start = b * batch_size
        end = min(start + batch_size, len(texts))
        batch = texts[start:end]
        arr = _embed_batch(batch, input_type="document")
        if arr is None:
            # Gem hvad vi har indtil videre (lokalt + GitHub), så vi kan genoptage
            if start > 0:
                try:
                    _os.makedirs(_tmp_dir, exist_ok=True)
                    np.savez_compressed(_partial_path,
                                        embeddings=out.astype(np.float16),
                                        n_done=np.array(start))
                    _push_embedding_to_github(_partial_fname, _partial_path, overwrite=True)
                except Exception:
                    pass
            if progress is not None:
                try: progress.empty()
                except Exception: pass
            return None
        out[start:end] = arr
        if progress is not None:
            try: progress.progress((b + 1) / n_batches,
                    text=f"Bygger semantisk indeks ({cache_key})… {end}/{len(texts)}"
                         + (f" (genoptaget fra {start_batch * batch_size})" if start_batch > 0 else ""))
            except Exception: pass

    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms

    # 4. Gem som float16 komprimeret (halverer filstørrelse)
    out16 = out.astype(np.float16)
    for d in [_git_dir, _tmp_dir]:
        try:
            _os.makedirs(d, exist_ok=True)
            np.savez_compressed(_os.path.join(d, _fname), out16)
        except Exception:
            pass

    # 5. Fjern partial-fil (bygget færdigt) — lokalt + GitHub
    try:
        if _os.path.exists(_partial_path):
            _os.remove(_partial_path)
        _delete_embedding_from_github(_partial_fname)
    except Exception:
        pass

    # 6. Auto-push til GitHub (så næste deploy er gratis)
    _local = _os.path.join(_git_dir, _fname)
    if not _os.path.exists(_local):
        _local = _os.path.join(_tmp_dir, _fname)
    try:
        _push_embedding_to_github(_fname, _local)
    except Exception:
        pass

    if progress is not None:
        try: progress.empty()
        except Exception: pass
    return out


def ensure_embeddings_on_disk(embeds, cache_key: str):
    """Sørg for at in-memory embeddings er gemt som .npz på disk
    (til brug af sync_embeddings_to_github)."""
    if embeds is None:
        return
    import os as _os
    provider, _key, model, dim = _embedding_provider()
    if not provider:
        return
    _fname = f"{cache_key}__{provider}__{model}__{len(embeds)}.npz"
    _tmp_dir = "/tmp/ejnar_data/embeds"
    _app_root = _os.path.dirname(_os.path.abspath(__file__))
    _git_dir = _os.path.join(_app_root, "embeds")
    for d in [_git_dir, _tmp_dir]:
        if _os.path.exists(_os.path.join(d, _fname)):
            return
    try:
        _os.makedirs(_tmp_dir, exist_ok=True)
        out16 = embeds.astype(np.float16) if embeds.dtype != np.float16 else embeds
        np.savez_compressed(_os.path.join(_tmp_dir, _fname), out16)
    except Exception:
        pass


def sync_embeddings_to_github():
    """Push alle lokale embedding-filer til GitHub.
    Returnerer liste af (filnavn, status) for debug-visning."""
    import os as _os, glob as _g
    token = hent_nøgle("GITHUB_TOKEN").strip()
    if not token:
        return [("—", "Ingen GITHUB_TOKEN konfigureret")]
    _tmp_dir = "/tmp/ejnar_data/embeds"
    _app_root = _os.path.dirname(_os.path.abspath(__file__))
    _git_dir = _os.path.join(_app_root, "embeds")
    results = []
    found_any = False
    for d in [_tmp_dir, _git_dir]:
        for f in _g.glob(_os.path.join(d, "*.npz")):
            fname = _os.path.basename(f)
            if "__partial__" in fname:
                continue
            found_any = True
            status = _push_embedding_to_github(fname, f)
            results.append((fname, status))
    if not found_any:
        results.append(("—", f"Ingen .npz filer fundet i {_tmp_dir} eller {_git_dir}"))
    return results


def embedding_soeg(query: str, df, embeds, sub_idx=None, top_n: int = 30, use_hyde: bool = True):
    """Semantisk søgning med HyDE og chunk-niveau retrieval.

    Hvis `embeds` er et dict (nyt chunk-format), søges på chunk-niveau:
    hver kendelse har 3-8 chunks, og vi tager max chunk-score pr. kendelse
    som dokumentets endelige score. Det giver bedre præcision når kun ét
    afsnit er relevant.

    Hvis `embeds` er en ndarray (gammelt doc-niveau format), bruges den
    klassiske doc-niveau matching.

    Returnerer liste af (global_doc_idx, score) sorteret bedst-først."""
    if embeds is None or df is None or len(df) == 0:
        return []
    qv = _hyde_embed(query) if use_hyde else _embed_query(query)
    if qv is None:
        qv = _embed_query(query)
    if qv is None:
        return []

    # ── Chunk-niveau (nyt format) ──────────────────────────────────────────
    if isinstance(embeds, dict) and "chunk_to_doc" in embeds:
        vectors = embeds["vectors"]
        chunk_to_doc = embeds["chunk_to_doc"]

        # Score alle chunks (vektorer er allerede L2-normaliserede)
        all_scores = vectors @ qv

        # Filtrér chunks til dem der hører til docs i sub_idx
        if sub_idx is not None and len(sub_idx) > 0:
            sub_arr = np.asarray(sub_idx, dtype=np.int32)
            mask = np.isin(chunk_to_doc, sub_arr)
            if not mask.any():
                return []
            chunk_indices = np.where(mask)[0]
            scores_sub = all_scores[chunk_indices]
            chunks_doc = chunk_to_doc[chunk_indices]
        else:
            chunks_doc = chunk_to_doc
            scores_sub = all_scores
            chunk_indices = np.arange(len(all_scores))

        # Effektiv aggregering: tag top-K chunks først, gruppér efter doc med max-score
        if len(scores_sub) == 0:
            return []
        n_top_chunks = min(len(scores_sub), top_n * 8)
        top_local = np.argpartition(-scores_sub, n_top_chunks - 1)[:n_top_chunks]
        # Sortér disse på score for deterministisk rækkefølge
        top_local = top_local[np.argsort(-scores_sub[top_local])]

        seen_docs: dict[int, float] = {}
        for li in top_local:
            d = int(chunks_doc[li])
            s = float(scores_sub[li])
            prev = seen_docs.get(d)
            if prev is None or s > prev:
                seen_docs[d] = s

        sorted_docs = sorted(seen_docs.items(), key=lambda x: -x[1])[:top_n]
        return [(d, s) for d, s in sorted_docs if s > 0.15]

    # ── Doc-niveau (gammelt format) ────────────────────────────────────────
    if sub_idx is not None and len(sub_idx) > 0:
        sub_mat = embeds[sub_idx]
        scores = sub_mat @ qv
        order = np.argsort(-scores)[:top_n]
        return [(int(sub_idx[i]), float(scores[i])) for i in order if scores[i] > 0.15]
    scores = embeds @ qv
    order = np.argsort(-scores)[:top_n]
    return [(int(i), float(scores[i])) for i in order if scores[i] > 0.15]


def hybrid_retrieval(query: str, df, vec, mat, embeds, sub_idx=None,
                     top_retrieve: int = 40, top_final: int = 20) -> list:
    """Hybrid TF-IDF + embeddings via Reciprocal Rank Fusion.
    Returnerer liste af globale indekser (bedst-først), op til top_final.

    Falder tilbage til ren TF-IDF hvis embeds er None.
    Dette er retrieval-fasen; LLM-rerank kører bagefter på top_final."""
    from sklearn.metrics.pairwise import cosine_similarity as _cos
    # 1. TF-IDF ranking
    qv = vec.transform([query])
    if sub_idx is not None and len(sub_idx) > 0:
        tfidf_scores = _cos(qv, mat[sub_idx]).flatten()
        tfidf_order_local = np.argsort(-tfidf_scores)[:top_retrieve]
        tfidf_ranking = [int(sub_idx[i]) for i in tfidf_order_local if tfidf_scores[i] > 0.01]
    else:
        tfidf_scores = _cos(qv, mat).flatten()
        tfidf_order = np.argsort(-tfidf_scores)[:top_retrieve]
        tfidf_ranking = [int(i) for i in tfidf_order if tfidf_scores[i] > 0.01]

    rangeringer = [tfidf_ranking]

    # 2. Embedding ranking (hvis tilgængelig)
    if embeds is not None:
        emb_hits = embedding_soeg(query, df, embeds, sub_idx=sub_idx, top_n=top_retrieve)
        emb_ranking = [g for g, _ in emb_hits]
        if emb_ranking:
            rangeringer.append(emb_ranking)

    # 3. RRF-fusion (bruger helper længere oppe i filen)
    fused = rrf_merge(rangeringer, k=60)
    if not fused:
        return tfidf_ranking[:top_final]
    sorted_idx = sorted(fused.items(), key=lambda x: -x[1])
    return [idx for idx, _ in sorted_idx[:top_final]]


def udvid_query(query: str) -> str:
    """Query expansion: Haiku tilføjer danske juridiske synonymer, lovhenvisninger
    og alternative formuleringer. Returnerer query + expansions til TF-IDF."""
    if not query or len(query) < 3:
        return query
    prompt = (
        "Du er ekspert i dansk forsikringsret og terminologi inden for ejerskifteforsikring, "
        "lov om forbrugerbeskyttelse ved erhvervelse af fast ejendom mv., tilstandsrapporter, "
        "byggeskik, byggetekniske skader og Ankenævnet for Forsikrings praksis.\n\n"
        "Brugerens søgning: \"" + query + "\"\n\n"
        "Returnér 5-12 termer der vil forbedre søgning i danske kendelser om ejerskifteforsikring:\n"
        "- Forsikrings-/byggetekniske synonymer (fx 'skimmelsvamp' ↔ 'skimmel' ↔ 'fugtskade')\n"
        "- Lovhenvisninger (fx 'lov om forbrugerbeskyttelse § 2', 'forsikringsaftaleloven', 'købelovens § 76')\n"
        "- Bøjningsformer og sammensætninger (fx 'utæthed', 'utæthedsskade', 'utætheder')\n"
        "- Relaterede begreber (fx 'tilstandsrapport', 'huseftersyn', 'sælgers ansvarsfraskrivelse', "
        "'dækningssum', 'selvrisiko', 'levetid', 'restlevetid', 'byggeskik')\n\n"
        "Kun termer – komma-separeret, ingen forklaring.\n\n"
        "Termer:"
    )
    udvidet = _llm_haiku(prompt, max_tokens=200)
    if not udvidet or "apinøgle" in udvidet.lower():
        return query
    return f"{query} {udvidet}"


def omformuler_opfoelgning(spoergsmaal: str, historik: list) -> str:
    """Omskriv et opfølgningsspørgsmål til et standalone-spørgsmål baseret på chat-historik.
    Hvis spørgsmålet allerede er standalone eller der ikke er historik, returneres uændret."""
    if not historik or len(historik) < 2 or not spoergsmaal:
        return spoergsmaal
    # Byg kort kontekst fra de sidste 4 beskeder
    kort_hist = []
    for msg in historik[-4:]:
        rolle = "Bruger" if msg.get("rolle") == "bruger" else "Assistent"
        t = (msg.get("tekst") or "")[:300]
        kort_hist.append(f"{rolle}: {t}")
    hist_str = "\n".join(kort_hist)
    prompt = (
        "Omskriv det sidste brugerspørgsmål til et selvstændigt spørgsmål baseret på samtalekonteksten. "
        "Hvis spørgsmålet allerede er selvstændigt, returnér det uændret. "
        "Returnér KUN det omskrevne spørgsmål – ingen forklaring.\n\n"
        f"SAMTALE:\n{hist_str}\n\n"
        f"SIDSTE SPØRGSMÅL: {spoergsmaal}\n\n"
        "OMSKREVET SPØRGSMÅL:"
    )
    omskrevet = _llm_haiku(prompt, max_tokens=200)
    omskrevet = (omskrevet or "").strip().strip('"').strip("'")
    if not omskrevet or len(omskrevet) < 5 or "apinøgle" in omskrevet.lower():
        return spoergsmaal
    return omskrevet


def _voyage_rerank(query: str, documents: list, top_n: int = 8) -> "list | None":
    """Voyage Rerank 2: dedikeret neural reranker. Returnerer liste af (orig_index, score)
    eller None ved fejl / manglende nøgle. Bruger samme VOYAGE_API_KEY som embeddings."""
    key = hent_nøgle("VOYAGE_API_KEY")
    if not key or not documents:
        return None
    try:
        r = requests.post(
            "https://api.voyageai.com/v1/rerank",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "query": query,
                "documents": documents,
                "model": "rerank-2",
                "top_k": top_n,
            },
            timeout=60,
        )
        if not r.ok:
            return None
        data = r.json().get("data", [])
        return [(d["index"], d["relevance_score"]) for d in data]
    except Exception:
        return None


def llm_rerank(query: str, kandidater: list, top_n: int = 8) -> list:
    """Reranker: bruger Voyage Rerank 2 (neural) hvis tilgængelig,
    ellers falder tilbage til Haiku LLM-scoring.
    kandidater = liste af dicts med mindst 'Titel', 'Dato', 'Tekst'.
    Returnerer top_n sorteret bedst-først."""
    if not kandidater or len(kandidater) <= top_n:
        return kandidater[:top_n]

    # 1. Forsøg Voyage Rerank (hurtigere, billigere, bedre end LLM-scoring)
    docs_for_rerank = []
    for k in kandidater:
        titel = (k.get("Titel") or "")[:150]
        kerne = udtræk_kerneafsnit(k.get("Tekst") or "", max_tegn=800).replace("\n", " ")[:700]
        docs_for_rerank.append(f"{titel}\n{kerne}")

    voyage_result = _voyage_rerank(query, docs_for_rerank, top_n=top_n)
    if voyage_result:
        return [kandidater[idx] for idx, _ in voyage_result]

    # 2. Fallback: Haiku LLM-rerank
    linjer = []
    for i, k in enumerate(kandidater):
        try:
            dato = pd.Timestamp(k.get("Dato")).strftime("%d.%m.%Y")
        except Exception:
            dato = "-"
        titel = (k.get("Titel") or "")[:120]
        kerne = udtræk_kerneafsnit(k.get("Tekst") or "", max_tegn=500).replace("\n", " ")[:400]
        linjer.append(f"[{i}] {dato} – {titel}\n    {kerne}")
    oversigt = "\n\n".join(linjer)
    prompt = (
        f"Du vurderer relevansen af juridiske afgørelser for dette spørgsmål:\n"
        f"SPØRGSMÅL: {query}\n\n"
        f"KANDIDATER ({len(kandidater)} stk):\n{oversigt}\n\n"
        f"Vurder hver kandidat 0-10 for direkte relevans for spørgsmålet. "
        f"Returnér KUN de {top_n} mest relevante indekser (0-baserede), komma-separeret, bedste først. "
        f"Ingen forklaring – kun tal.\n\n"
        f"TOP {top_n}:"
    )
    svar = _llm_haiku(prompt, max_tokens=100)
    if not svar or "apinøgle" in svar.lower():
        return kandidater[:top_n]
    import re as _re
    tal = [int(x) for x in _re.findall(r'\d+', svar) if int(x) < len(kandidater)]
    seen = set()
    valgte = []
    for t in tal:
        if t not in seen:
            seen.add(t)
            valgte.append(t)
        if len(valgte) >= top_n:
            break
    if not valgte:
        return kandidater[:top_n]
    for i in range(len(kandidater)):
        if len(valgte) >= top_n:
            break
        if i not in seen:
            valgte.append(i)
    return [kandidater[i] for i in valgte[:top_n]]


def _normaliser_citat(s: str) -> str:
    """Normaliser tekst til fuzzy citat-matching: lowercase, collapse whitespace,
    strip interpunktion i kanterne. Bevarer internal punctuation til substring-match."""
    if not s:
        return ""
    s = s.lower()
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(".,;:!? \"'»«–—-")
    return s


def valider_citationer(svar: str, docs: list, min_laengde: int = 25) -> list:
    """Find citater i "..." i svaret og verificér at de findes i kildedokumenterne.
    Returnerer liste af suspekte citater (ikke fundet i nogen kilde).
    Kun citater på mindst min_laengde tegn valideres (korte strenge er ofte almindelige frasemer)."""
    if not svar or not docs:
        return []
    # Normalisér alle kildetekster én gang
    kilde_tekster = []
    for d in docs:
        tx = d.get("Tekst") or ""
        kilde_tekster.append(_normaliser_citat(tx))
    samlet_korpus = " ||| ".join(kilde_tekster)

    # Find alle "..." citater (inkl. danske citationstegn » « og " ")
    moenstre = [
        r'"([^"]{%d,})"' % min_laengde,
        r'»([^«]{%d,})«' % min_laengde,
        r'"([^"]{%d,})"' % min_laengde,
    ]
    suspekte = []
    sete = set()
    for mnstr in moenstre:
        for m in re.finditer(mnstr, svar):
            citat = m.group(1).strip()
            if len(citat) < min_laengde or citat in sete:
                continue
            sete.add(citat)
            norm = _normaliser_citat(citat)
            if not norm:
                continue
            # Fuzzy: substring-match på normaliseret kilde
            if norm in samlet_korpus:
                continue
            # Fallback: check om første 60% af citatet findes (håndterer mindre afvigelser)
            head = norm[: max(30, int(len(norm) * 0.6))]
            if head in samlet_korpus:
                continue
            suspekte.append(citat)
    return suspekte


def saml_kilder(historik: list, nye_hits, max_total: int = 12) -> list:
    """Merge nye søgeresultater med alle tidligere viste kilder (dedupliceret på Link).
    Sikrer AI'en har kildekontinuitet på tværs af samtalens ture."""
    seen = set()
    merged = []
    iterable = nye_hits.to_dict("records") if hasattr(nye_hits, "to_dict") else (nye_hits or [])
    for rec in iterable:
        lnk = rec.get("Link", "")
        if lnk and lnk not in seen:
            seen.add(lnk)
            merged.append(rec)
    for msg in reversed(historik or []):
        if msg.get("rolle") == "assistent":
            for k in msg.get("kilder", []) or []:
                lnk = k.get("Link", "")
                if lnk and lnk not in seen and len(merged) < max_total:
                    seen.add(lnk)
                    merged.append(k)
    return merged[:max_total]


def highlight_query(text: str, query: str, max_len: int = 0) -> str:
    """Marker søgetermer i teksten med <mark> tags.
    Splitter query i ord og highlighter hvert match (case-insensitive).
    Fjerner trivielle ord (under 3 tegn) og HTML-escaper teksten først."""
    if not text or not query:
        return text[:max_len] + "…" if max_len and len(text) > max_len else text
    import html as _html
    safe = _html.escape(text)
    if max_len and len(safe) > max_len:
        safe = safe[:max_len] + "…"
    # Split query i substantielle ord
    termer = [t for t in re.split(r'\s+', query.strip()) if len(t) >= 3]
    if not termer:
        return safe
    # Sortér længste først så vi undgår delvis overlap
    termer.sort(key=len, reverse=True)
    for t in termer[:8]:  # max 8 termer for performance
        escaped_term = re.escape(t)
        safe = re.sub(
            rf"({escaped_term})",
            r'<mark style="background:#fef9c3;padding:0 1px;border-radius:2px;">\1</mark>',
            safe,
            flags=re.IGNORECASE,
            count=10,  # max 10 matches per term
        )
    return safe


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


# ── Sagsmappe ────────────────────────────────────────────────────────────────
import uuid as _uuid
import datetime as _dt


def init_sagsmapper() -> None:
    if "sagsmapper" not in st.session_state:
        st.session_state["sagsmapper"] = {"mapper": {}, "standard_mappe": None}


def opret_mappe(navn: str) -> str:
    init_sagsmapper()
    mid = _uuid.uuid4().hex[:12]
    st.session_state["sagsmapper"]["mapper"][mid] = {
        "id": mid,
        "navn": navn,
        "oprettet": _dt.datetime.now().isoformat(timespec="seconds"),
        "afgørelser": [],
    }
    if st.session_state["sagsmapper"]["standard_mappe"] is None:
        st.session_state["sagsmapper"]["standard_mappe"] = mid
    return mid


def slet_mappe(mappe_id: str) -> None:
    init_sagsmapper()
    st.session_state["sagsmapper"]["mapper"].pop(mappe_id, None)
    if st.session_state["sagsmapper"]["standard_mappe"] == mappe_id:
        remaining = list(st.session_state["sagsmapper"]["mapper"].keys())
        st.session_state["sagsmapper"]["standard_mappe"] = remaining[0] if remaining else None


def omdøb_mappe(mappe_id: str, nyt_navn: str) -> None:
    init_sagsmapper()
    m = st.session_state["sagsmapper"]["mapper"].get(mappe_id)
    if m:
        m["navn"] = nyt_navn


def gem_afgørelse(mappe_id: str, link: str, titel: str, dato: str,
                  udfald: str, kilde: str, kategori: str,
                  kommune: str, excerpt: str) -> bool:
    init_sagsmapper()
    mappe = st.session_state["sagsmapper"]["mapper"].get(mappe_id)
    if not mappe:
        return False
    if any(a["link"] == link for a in mappe["afgørelser"]):
        return False
    mappe["afgørelser"].append({
        "link": link,
        "titel": titel,
        "dato": dato,
        "udfald": udfald,
        "kilde": kilde,
        "kategori": kategori,
        "kommune": kommune,
        "excerpt": excerpt[:280],
        "tilføjet": _dt.datetime.now().isoformat(timespec="seconds"),
    })
    st.session_state["sagsmapper"]["standard_mappe"] = mappe_id
    return True


def fjern_afgørelse(mappe_id: str, link: str) -> None:
    init_sagsmapper()
    mappe = st.session_state["sagsmapper"]["mapper"].get(mappe_id)
    if mappe:
        mappe["afgørelser"] = [a for a in mappe["afgørelser"] if a["link"] != link]


def opdater_note(mappe_id: str, link: str, note: str) -> None:
    init_sagsmapper()
    mappe = st.session_state["sagsmapper"]["mapper"].get(mappe_id)
    if not mappe:
        return
    for a in mappe["afgørelser"]:
        if a["link"] == link:
            a["note"] = note
            return


def find_mappe_for_link(link: str) -> str:
    init_sagsmapper()
    for mid, m in st.session_state["sagsmapper"]["mapper"].items():
        if any(a["link"] == link for a in m["afgørelser"]):
            return mid
    return None


def hent_alle_gemte_links() -> set:
    init_sagsmapper()
    links = set()
    for m in st.session_state["sagsmapper"]["mapper"].values():
        for a in m["afgørelser"]:
            links.add(a["link"])
    return links


def _auto_opret_mappe() -> str:
    init_sagsmapper()
    mapper = st.session_state["sagsmapper"]["mapper"]
    if not mapper:
        return opret_mappe("Mine afgørelser")
    return st.session_state["sagsmapper"]["standard_mappe"] or list(mapper.keys())[0]


def gem_fra_row(row: dict, kilde: str, mappe_id: str = None) -> bool:
    mid = mappe_id or _auto_opret_mappe()
    kategori = row.get("Kategori", row.get("Underkategori", ""))
    if isinstance(kategori, list):
        kategori = " / ".join(kategori)
    dato = ""
    try:
        dato = pd.Timestamp(row["Dato"]).strftime("%Y-%m-%d")
    except Exception:
        dato = str(row.get("Dato", ""))[:10]
    return gem_afgørelse(
        mappe_id=mid,
        link=row["Link"],
        titel=row["Titel"],
        dato=dato,
        udfald=row.get("Udfald", ""),
        kilde=kilde,
        kategori=kategori,
        kommune=row.get("Kommune", ""),
        excerpt=row.get("Excerpt", "")[:280],
    )

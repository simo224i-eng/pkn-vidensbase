"""Delte hjælpefunktioner, CSS og logo til Harald (PKN + MFKN)."""
import re
import csv
import base64 as _b64
import numpy as np  # noqa: F401 – bruges i page-filer via import shared
import pandas as pd
import requests
import streamlit as st

# ── Styling ───────────────────────────────────────────────────────────────────
# Design tokens (Harald v2 — legal tech refresh):
#   Background:  #ffffff (main)  #f8fafc (panel)
#   Sidebar:     #0f172a (flat)
#   Text:        #0f172a primær   #475569 sek.   #94a3b8 tert.
#   Border:      #e2e8f0 hairline   #cbd5e1 emphasis
#   Accent:      #8C1C2E (burgundy)   #fef2f2 (accent bg)
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
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #8C1C2E !important; }
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
    padding: 1.2rem 0 0.4rem !important;
    margin-bottom: 0 !important;
    border-bottom: 1px solid #1e293b;
}
[data-testid="stSidebarNav"]::before {
    content: "NAVIGATION";
    display: block;
    font-size: 9px;
    font-weight: 600;
    color: #64748b;
    letter-spacing: 1.2px;
    padding: 0 1rem 0.5rem;
}
[data-testid="stSidebarNavLink"] {
    color: #94a3b8 !important;
    font-size: 12.5px !important;
    font-weight: 500 !important;
    padding: 8px 1rem !important;
    border-radius: 0 !important;
    border-left: 2px solid transparent !important;
    transition: all .12s !important;
    background: transparent !important;
}
[data-testid="stSidebarNavLink"]:hover {
    color: #e2e8f0 !important;
    background: rgba(255,255,255,.03) !important;
    border-left-color: #334155 !important;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    color: #f1f5f9 !important;
    background: rgba(140,28,46,.12) !important;
    border-left-color: #8C1C2E !important;
    font-weight: 600 !important;
}
[data-testid="stSidebarNavSeparator"] { display: none !important; }

/* ── Download-knap i sidebar ── */
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    color: #cbd5e1 !important;
    border-radius: 6px !important;
    font-size: 11px !important;
    font-weight: 500 !important;
    width: 100% !important;
    padding: 8px 12px !important;
    letter-spacing: 0.2px !important;
    transition: border-color .12s, color .12s !important;
}
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button:hover {
    border-color: #8C1C2E !important;
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
.h-brand-wrap { text-align: center; padding: 1.6rem 0 1.3rem; border-bottom: 1px solid #1e293b; margin-bottom: 1.4rem; }
.h-logo-box { display: inline-block; padding: 4px 8px; }
.h-sub { display: none; }

/* ── Sidebar section labels ── */
.h-filter-label {
    font-family: 'Inter', system-ui, sans-serif !important;
    font-size: 10.5px !important;
    font-weight: 600 !important;
    color: #94a3b8 !important;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    margin: 1.2rem 0 0.35rem;
    display: block;
}

/* ── Page header ── */
.h-page-header {
    margin-bottom: 2rem; padding-bottom: 1.2rem;
    border-bottom: 1px solid #e2e8f0;
    display: flex; align-items: baseline; gap: 16px; flex-wrap: wrap;
}
.h-page-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 1.45rem; font-weight: 700;
    color: #0f172a; letter-spacing: -0.3px; margin: 0; line-height: 1.2;
}
.h-page-meta {
    font-size: 12.5px; color: #64748b; margin: 0;
    padding-left: 16px; border-left: 1px solid #e2e8f0;
    font-weight: 400;
}
.h-gold-line { display: none; }

/* ── Cards ── */
.pkn-card {
    background: #ffffff; border-radius: 6px; padding: 16px 20px; margin-bottom: 4px;
    border: 1px solid #e2e8f0; border-left: 3px solid transparent;
    transition: border-color .12s, border-left-color .12s, box-shadow .12s;
}
.pkn-card:hover { border-color: #cbd5e1; border-left-color: #8C1C2E; box-shadow: 0 1px 3px rgba(15,23,42,.06); }
.pkn-card-toprow  { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.pkn-card-dato    { font-size: 11px; color: #94a3b8; font-weight: 500; letter-spacing: .1px; }
.pkn-card-title   { font-size: 13.5px; font-weight: 600; color: #0f172a; margin: 0 0 8px; line-height: 1.5; }
.pkn-card-tags    { display: flex; gap: 5px; flex-wrap: wrap; margin-bottom: 10px; }
.pkn-tag          { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 10.5px; font-weight: 500; color: #475569; background: #f1f5f9; border: 1px solid #e2e8f0; }
.pkn-card-excerpt { font-size: 12.5px; color: #475569; line-height: 1.6; }
.pkn-card-footer  { margin-top: 10px; padding-top: 10px; border-top: 1px solid #f1f5f9; }
.pkn-card-link    { font-size: 11px; color: #94a3b8; text-decoration: none; font-weight: 500; transition: color .12s; }
.pkn-card-link:hover { color: #8C1C2E; }

/* ── Badges ── */
.pkn-badge { display: inline-block; padding: 2px 8px; border-radius: 20px; font-size: 10px; font-weight: 600; margin-right: 4px; letter-spacing: .1px; }
.badge-medhold      { background: #f0fdf4; color: #166534; border: 1px solid #bbf7d0; }
.badge-ikke-medhold { background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; }
.badge-ophaevet     { background: #f5f3ff; color: #5b21b6; border: 1px solid #ddd6fe; }
.badge-afvist       { background: #fffbeb; color: #92400e; border: 1px solid #fde68a; }
.badge-ukendt       { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }

/* ── Aktive filter-chips (klikbare til at fjerne) ── */
.active-filters-wrap {
    display: flex; flex-wrap: wrap; align-items: center; gap: 6px;
    padding: 10px 0 6px; margin-bottom: 4px; border-bottom: 1px solid #e2e8f0;
}
.active-filters-label {
    font-size: 10.5px; font-weight: 600; color: #64748b;
    text-transform: uppercase; letter-spacing: 0.6px; margin-right: 6px;
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
    background: #fef2f2 !important; color: #8C1C2E !important; border-color: #fecaca !important;
}
div[data-testid="element-container"]:has(.active-filters-clear-anchor) ~ div button {
    background: transparent !important; color: #8C1C2E !important;
    border: 1px solid #fecaca !important; border-radius: 4px !important;
    font-size: 11.5px !important; font-weight: 600 !important;
    padding: 3px 10px !important; min-height: 26px !important; height: 26px !important;
}

/* ── Stat cards ── */
.stat-card   { background: #ffffff; border-radius: 6px; padding: 20px 18px; text-align: center; border: 1px solid #e2e8f0; }
.stat-number { font-family: 'Inter', system-ui, sans-serif; font-size: 26px; font-weight: 700; color: #0f172a; letter-spacing: -0.5px; }
.stat-label  { font-size: 10.5px; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.6px; font-weight: 500; }

/* ── AI Assistent intro ── */
.ai-hero {
    display: flex; align-items: center; gap: 16px;
    background: #f8fafc;
    border: 1px solid #e2e8f0; border-left: 3px solid #8C1C2E; border-radius: 6px;
    padding: 16px 20px; margin-bottom: 20px;
}
.ai-hero-icon {
    font-size: 22px; flex-shrink: 0; color: #8C1C2E; line-height: 1;
}
.ai-hero-icon .material-symbols-rounded { font-size: 22px; color: #8C1C2E; }
.ai-hero-title {
    font-family: 'Inter', system-ui, sans-serif;
    font-size: 13.5px; font-weight: 700;
    color: #0f172a; letter-spacing: -0.1px;
    margin: 0 0 3px;
}
.ai-hero-sub {
    font-size: 12.5px; color: #475569; line-height: 1.6; margin: 0;
}
.ai-hero-sub strong { color: #0f172a; font-weight: 600; }
.ai-hero-badge { display: none; }

/* Forslagsknapper */
#ai-forslag-anchor ~ div button,
#ai-forslag-anchor ~ div ~ div button,
#ai-forslag-anchor ~ div ~ div ~ div button,
#ai-forslag-anchor ~ div ~ div ~ div ~ div button {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    color: #334155 !important; border-radius: 6px !important;
    font-size: 12.5px !important; line-height: 1.45 !important;
    padding: 10px 14px !important; min-height: 60px !important;
    text-align: left !important; transition: all .12s ease !important;
    white-space: normal !important;
}
#ai-forslag-anchor ~ div button:hover,
#ai-forslag-anchor ~ div ~ div button:hover,
#ai-forslag-anchor ~ div ~ div ~ div button:hover,
#ai-forslag-anchor ~ div ~ div ~ div ~ div button:hover {
    background: #f8fafc !important;
    border-color: #8C1C2E !important;
    color: #0f172a !important;
}

/* ── Chat ── */
.chat-user {
    background: #0f172a;
    color: #f1f5f9; border-radius: 8px 8px 2px 8px;
    padding: 12px 16px; margin: 4px 0 4px auto; max-width: 78%;
    font-size: 14px; line-height: 1.6;
}
.chat-assistant {
    background: #ffffff; color: #0f172a;
    border-radius: 2px 8px 8px 8px;
    padding: 14px 18px; margin: 4px 0; max-width: 92%;
    border: 1px solid #e2e8f0; font-size: 14px; line-height: 1.7;
}
.chat-assistant h1 { font-size: 15px !important; font-weight: 700 !important; margin: 0.9em 0 0.4em !important; border-bottom: 1px solid #e2e8f0; padding-bottom: 3px; }
.chat-assistant h2 { font-size: 14px !important; font-weight: 700 !important; margin: 0.7em 0 0.3em !important; }
.chat-assistant h3 { font-size: 13.5px !important; font-weight: 600 !important; margin: 0.6em 0 0.25em !important; }
.chat-assistant p  { margin: 0 0 0.6em !important; }
.chat-assistant ul, .chat-assistant ol { margin: 0.3em 0 0.6em 1.2em !important; }
.chat-assistant li { margin-bottom: 0.2em !important; }
.source-chip    { display: inline-block; padding: 3px 9px; border-radius: 4px; background: #f8fafc; color: #475569; font-size: 11px; margin: 3px; text-decoration: none; border: 1px solid #e2e8f0; }

/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] { font-size: 13px; font-weight: 500; color: #64748b; padding: 8px 18px; }
[data-testid="stTabs"] [role="tab"][aria-selected="true"] { color: #0f172a !important; border-bottom-color: #8C1C2E !important; font-weight: 600; }

/* ── Buttons ── */
[data-testid="stBaseButton-secondary"] { border-color: #e2e8f0 !important; color: #334155 !important; font-size: 12.5px !important; border-radius: 6px !important; background: #ffffff !important; font-weight: 500 !important; }
[data-testid="stBaseButton-secondary"]:hover { border-color: #8C1C2E !important; color: #0f172a !important; background: #f8fafc !important; }
[data-testid="stBaseButton-primary"] { background: #8C1C2E !important; border-color: #8C1C2E !important; color: #ffffff !important; border-radius: 6px !important; font-weight: 600 !important; }
[data-testid="stBaseButton-primary"]:hover { background: #6d1523 !important; border-color: #6d1523 !important; }

/* ── Detail view ── */
.detail-back-row { margin-bottom: 2rem; }
.detail-hero { padding: 2rem 0 1.8rem; border-bottom: 1px solid #e2e8f0; margin-bottom: 2rem; }
.detail-udfald-row { margin-bottom: 1rem; }
.detail-udfald-chip { display: inline-flex; align-items: center; gap: 5px; font-size: 10.5px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; padding: 4px 12px; border-radius: 20px; border: 1px solid; }
.detail-title { font-family: 'Inter', system-ui, sans-serif; font-size: clamp(1.3rem, 2.5vw, 1.8rem); font-weight: 700; color: #0f172a; line-height: 1.3; letter-spacing: -0.4px; margin: 0 0 1.4rem; }
.detail-gold-line { height: 2px; width: 32px; background: #8C1C2E; border-radius: 2px; margin-bottom: 1.2rem; }
.detail-meta-strip { display: flex; flex-wrap: wrap; gap: 0; border: 1px solid #e2e8f0; border-radius: 6px; overflow: hidden; margin-bottom: 1.2rem; width: fit-content; background: #ffffff; }
.detail-meta-cell { padding: 10px 18px; border-right: 1px solid #e2e8f0; }
.detail-meta-cell:last-child { border-right: none; }
.detail-meta-lbl { font-size: 9.5px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.8px; display: block; margin-bottom: 3px; }
.detail-meta-val { font-size: 13px; font-weight: 600; color: #0f172a; white-space: nowrap; }
.detail-source-link { display: inline-flex; align-items: center; gap: 5px; font-size: 12px; color: #475569; text-decoration: none; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px 14px; transition: all .12s; font-weight: 500; background: #ffffff; }
.detail-source-link:hover { border-color: #8C1C2E; color: #0f172a; }
.detail-reader { font-size: 15.5px; line-height: 1.85; color: #1e293b; font-family: 'Inter', system-ui, sans-serif; font-weight: 400; max-width: 72ch; }
.detail-reader p { margin: 0 0 1.2em; }
.detail-reader p:last-child { margin-bottom: 0; }
.detail-section-heading {
    display: block; font-size: 10.5px; font-weight: 700; color: #475569;
    text-transform: uppercase; letter-spacing: 0.8px;
    margin: 2em 0 0.6em; padding: 0 0 5px 10px;
    border-left: 2px solid #8C1C2E; border-bottom: 1px solid #e2e8f0;
}
.detail-ai-panel { background: #0f172a; border-radius: 8px; padding: 24px; position: sticky; top: 1rem; }
.detail-ai-title { font-size: 10.5px; font-weight: 700; letter-spacing: 0.8px; text-transform: uppercase; color: #94a3b8; margin-bottom: 14px; }
.detail-ai-resume { font-size: 13px; line-height: 1.7; color: #cbd5e1; background: rgba(255,255,255,.04); border: 1px solid rgba(255,255,255,.08); border-radius: 6px; padding: 14px 16px; margin-top: 12px; }

/* ── Skjul browser-tooltip på collapse-knap ── */
[data-testid="stSidebarCollapseButton"] button::before { content: none !important; }

/* ── Home page cards ── */
.nævn-card {
    background: #ffffff; border-radius: 8px; padding: 2rem 2.2rem 1.8rem;
    border: 1px solid #e2e8f0;
    transition: border-color .15s, box-shadow .15s, transform .15s;
    display: flex; flex-direction: column; height: 100%;
}
.nævn-card:hover { border-color: #8C1C2E; box-shadow: 0 4px 16px rgba(15,23,42,.06); transform: translateY(-2px); }
.nævn-card.mfkn:hover { border-color: #8C1C2E; }
.nævn-card-icon {
    display: inline-flex; align-items: center; justify-content: center;
    width: 40px; height: 40px; border-radius: 8px;
    background: #fef2f2; color: #8C1C2E; margin-bottom: 1.2rem;
}
.nævn-card-icon .material-symbols-rounded { font-size: 22px; }
.nævn-card-title { font-family: 'Inter', system-ui, sans-serif; font-size: 1.05rem; font-weight: 700; color: #0f172a; letter-spacing: -0.3px; margin-bottom: 0.25rem; }
.nævn-card-sub { font-size: 11.5px; color: #64748b; margin-bottom: 1rem; padding-bottom: 1rem; border-bottom: 1px solid #f1f5f9; font-weight: 500; }
.nævn-card-desc { font-size: 13.5px; color: #475569; line-height: 1.65; margin-bottom: 1.2rem; flex: 1; }
.nævn-card-count { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.6px; margin-bottom: 1.4rem; }
.nævn-card-cta {
    display: block; text-align: center; padding: 0.7rem 1rem;
    background: #ffffff; border: 1px solid #8C1C2E; border-radius: 6px;
    color: #8C1C2E; font-size: 13px; font-weight: 600; letter-spacing: 0.1px;
    transition: background .12s, color .12s;
}
.nævn-card:hover .nævn-card-cta { background: #8C1C2E; color: #ffffff; }

/* ── Card v2: knap smelter visuelt sammen med kortet ── */
.pkn-card-v2 { border-radius: 6px 6px 0 0; border-bottom: none !important; margin-bottom: 0; }
div[data-testid="element-container"]:has(.pkn-card-v2) { margin-bottom: 0 !important; }
div[data-testid="element-container"]:has(.pkn-card-v2) + div[data-testid="element-container"] [data-testid="stBaseButton-secondary"] {
    border-top: 1px solid #f1f5f9 !important;
    border-top-left-radius: 0 !important; border-top-right-radius: 0 !important;
    border-bottom-left-radius: 6px !important; border-bottom-right-radius: 6px !important;
    background: #f8fafc !important; color: #334155 !important;
    font-size: 12.5px !important; font-weight: 600 !important;
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

sup.detail-ref { font-size: 9px; font-weight: 700; color: #8C1C2E; vertical-align: super; letter-spacing: 0; }
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
_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 64" width="{w}" style="display:block;margin:0 auto">
  <text x="110" y="36" text-anchor="middle" font-family="Inter,system-ui,sans-serif" font-size="26" font-weight="800" fill="{fill}" letter-spacing="3.5">HARALD</text>
  <rect x="98" y="46" width="24" height="2" fill="#8C1C2E"/>
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
    """Harald wordmark. dark=True giver lys tekst til mørk sidebar."""
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
    accent: str = "#8C1C2E",
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
    key = st.secrets.get("ANTHROPIC_API_KEY", "")
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
    key = st.secrets.get("ANTHROPIC_API_KEY", "")
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

    key = st.secrets.get("ANTHROPIC_API_KEY", "")
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
            'background:#f8fafc;border-left:3px solid #8C1C2E;'
            'border-radius:0 4px 4px 0;">')
_H_CLOSE = '</div>'
# Matcher sætningsafslutning + valgfrit afsnitstal (fx "1." "2)") + overskriftsord
_HEADING_PRE = r'([.!?])\s+(?:\d+[.)]\s+)?'


_H2_STYLE = (
    'display:block;font-size:12.5px;font-weight:700;color:#0f172a;'
    'text-transform:uppercase;letter-spacing:0.8px;'
    'margin:2em 0 0.6em;padding:9px 14px;'
    'background:#f8fafc;border-left:3px solid #8C1C2E;border-radius:0 4px 4px 0;'
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
                r'<sup style="font-size:9px;font-weight:700;color:#8C1C2E;vertical-align:super;letter-spacing:0;">[\1]</sup>',
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
            r'<sup style="font-size:9px;font-weight:700;color:#8C1C2E;vertical-align:super;letter-spacing:0;">[\1]</sup>',
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


def byg_fokuseret_kontekst(query: str, docs: list, max_chunks_per_doc: int = 3,
                            chunk_size: int = 400, max_total_chars: int = 24000) -> str:
    """Chunk-level kontekst-udvælgelse: i stedet for at sende hele kerneafsnit til LLM'en,
    chunker vi hvert dokument og scorer chunks mod query med simpel TF-IDF.
    Returnerer formateret kontekst-streng med [Kilde N] headers bevaret.

    Dette giver LLM'en mere fokuseret, relevant kontekst og reducerer støj.
    Falder tilbage til udtræk_kerneafsnit ved fejl."""
    if not docs:
        return ""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity as _cos
    except ImportError:
        # Fallback: brug kerneafsnit som hidtil
        return "\n\n".join(
            f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}\n"
            f"{udtræk_kerneafsnit(d.get('Tekst') or '', max_tegn=4000)}"
            for i, d in enumerate(docs)
        )

    # 1. Chunk hvert dokument og hold styr på kilde-nummer
    all_chunks = []     # (kilde_idx, chunk_text)
    for i, d in enumerate(docs):
        kerne = udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=6000)
        chunks = chunk_tekst(kerne, titel="", chunk_size=chunk_size, overlap=80)
        if not chunks:
            chunks = [kerne[:3000]] if kerne else [d.get("Titel", "")]
        for c in chunks:
            all_chunks.append((i, c))

    if not all_chunks:
        return ""

    # 2. Scorer chunks mod query
    chunk_texts = [c for _, c in all_chunks]
    try:
        mini_vec = TfidfVectorizer(max_features=20_000, ngram_range=(1, 2), sublinear_tf=True)
        chunk_mat = mini_vec.fit_transform(chunk_texts)
        qv = mini_vec.transform([query])
        scores = _cos(qv, chunk_mat).flatten()
    except Exception:
        scores = np.ones(len(all_chunks))

    # 3. Vælg bedste chunks per kilde (bevar kilde-rækkefølge)
    from collections import defaultdict
    kilde_chunks = defaultdict(list)
    for idx, (kilde_i, chunk) in enumerate(all_chunks):
        kilde_chunks[kilde_i].append((float(scores[idx]), chunk))

    dele = []
    total_chars = 0
    for i, d in enumerate(docs):
        header = f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}"
        best = sorted(kilde_chunks.get(i, []), key=lambda x: -x[0])[:max_chunks_per_doc]
        best_texts = [c for _, c in best]
        content = "\n[…]\n".join(best_texts) if best_texts else udtræk_kerneafsnit(d.get("Tekst") or "", max_tegn=2000)
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
    Preferer Voyage (bedst til dansk), falder tilbage til OpenAI."""
    voyage_key = st.secrets.get("VOYAGE_API_KEY", "")
    if voyage_key:
        return ("voyage", voyage_key, "voyage-multilingual-2", 1024)
    openai_key = st.secrets.get("OPENAI_API_KEY", "")
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
        "Du er Planklagenævnet/Miljø- og Fødevareklagenævnet. "
        "Skriv et kort uddrag (100-150 ord) af en hypotetisk nævnsafgørelse "
        "der besvarer dette spørgsmål. Brug nævnets typiske sprog og juridiske termer. "
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


def byg_embeddings_indeks(df, cache_key: str, tekst_bygger=None, batch_size: int = 32) -> "np.ndarray | None":
    """Byg et persistent embedding-indeks over df. Cache'r resultatet som .npy på disk.
    - cache_key: unik nøgle pr. datasæt (fx 'pkn', 'mfkn_husdyrbrug')
    - tekst_bygger: callable(titel, tekst) -> str; default er byg_indeks_tekst
    Returnerer (N, dim) array eller None hvis embeddings ikke er konfigureret.

    Inkluderer antal rækker + provider/model i cache-nøglen, så cachen bustes automatisk
    når datasættet vokser eller embedding-model skiftes."""
    provider, _key, model, dim = _embedding_provider()
    if not provider or df is None or len(df) == 0:
        return None
    if tekst_bygger is None:
        tekst_bygger = lambda t, x: byg_indeks_tekst(t, x, max_tegn=4000)

    import os as _os
    cache_dir = "/tmp/pkn_data/embeds"
    _os.makedirs(cache_dir, exist_ok=True)
    cache_path = _os.path.join(cache_dir, f"{cache_key}__{provider}__{model}__{len(df)}.npy")

    if _os.path.exists(cache_path):
        try:
            arr = np.load(cache_path)
            if arr.shape == (len(df), dim):
                return arr
        except Exception:
            pass

    # Byg fra bunden
    texts = [tekst_bygger(str(t), str(x))[:8000]
             for t, x in zip(df["Titel"].fillna(""), df["Tekst"].fillna(""))]

    out = np.zeros((len(texts), dim), dtype=np.float32)
    progress = None
    try:
        progress = st.progress(0.0, text=f"Bygger semantisk indeks ({cache_key})…")
    except Exception:
        pass

    n_batches = (len(texts) + batch_size - 1) // batch_size
    for b in range(n_batches):
        start = b * batch_size
        end = min(start + batch_size, len(texts))
        batch = texts[start:end]
        arr = _embed_batch(batch, input_type="document")
        if arr is None:
            # Fejl under embedding — drop cache og returnér None
            if progress is not None:
                try: progress.empty()
                except Exception: pass
            return None
        out[start:end] = arr
        if progress is not None:
            try: progress.progress((b + 1) / n_batches, text=f"Bygger semantisk indeks ({cache_key})… {end}/{len(texts)}")
            except Exception: pass

    # Normalisér rækker for hurtig cosine via dot product
    norms = np.linalg.norm(out, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    out = out / norms

    try:
        np.save(cache_path, out)
    except Exception:
        pass
    if progress is not None:
        try: progress.empty()
        except Exception: pass
    return out


def embedding_soeg(query: str, df, embeds, sub_idx=None, top_n: int = 30, use_hyde: bool = True):
    """Semantisk søgning med HyDE: genererer hypotetisk svar, embedder det,
    og matcher mod pre-computed doc embeddings via cosine similarity.
    Falder tilbage til rå query-embedding hvis HyDE fejler.
    Returnerer liste af (global_idx, score) sorteret bedst-først."""
    if embeds is None or df is None or len(df) == 0:
        return []
    qv = _hyde_embed(query) if use_hyde else _embed_query(query)
    if qv is None:
        qv = _embed_query(query)
    if qv is None:
        return []
    if sub_idx is not None and len(sub_idx) > 0:
        sub_mat = embeds[sub_idx]
        scores = sub_mat @ qv  # normaliserede vektorer → cosine = dot
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
        "Du er ekspert i dansk juridisk terminologi inden for planloven, naturbeskyttelsesloven, "
        "miljøbeskyttelsesloven, forvaltningsret og nævnspraksis.\n\n"
        "Brugerens søgning: \"" + query + "\"\n\n"
        "Returnér 5-12 termer der vil forbedre søgning i danske nævnsafgørelser:\n"
        "- Juridiske synonymer (fx 'dispensation' ↔ 'fravigelse')\n"
        "- Lovhenvisninger (fx '§ 35' ved landzonetilladelse, 'planlovens § 19' ved dispensation)\n"
        "- Bøjningsformer og sammensætninger (fx 'stadfæstes', 'stadfæstelse')\n"
        "- Relaterede begreber (fx 'nabohøring' ved dispensation, 'partshøring' ved klage)\n\n"
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
    key = st.secrets.get("VOYAGE_API_KEY", "")
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

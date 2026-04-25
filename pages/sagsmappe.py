import streamlit as st

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

import pandas as pd
from shared import (
    logo, inject_css, sidebar_log_ud,
    init_sagsmapper, opret_mappe, slet_mappe, omdøb_mappe,
    fjern_afgørelse, hent_alle_gemte_links,
)

inject_css()
init_sagsmapper()

_BADGE_STYLE = {
    "Medhold":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
    "Ikke medhold": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "Ophævet":      "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
    "Afvist":       "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
    "Stadfæstelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
    "Ændring":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
    "Hjemvist":     "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
}
_BADGE_DEFAULT = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"

_KILDE_BADGE = {
    "pkn": "background:#fef2f2;color:#8C1C2E;border:1px solid #fecaca",
    "mfkn": "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
}

mapper = st.session_state["sagsmapper"]["mapper"]

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(150, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<span class="h-filter-label">Dine mapper</span>', unsafe_allow_html=True)

    if mapper:
        mappe_navne = {mid: f"{m['navn']} ({len(m['afgørelser'])})" for mid, m in mapper.items()}
        valgt_id = st.radio(
            "", list(mappe_navne.keys()),
            format_func=lambda x: mappe_navne[x],
            label_visibility="collapsed",
            key="_sag_valgt_mappe",
        )
    else:
        valgt_id = None

    st.markdown("---")
    st.markdown('<span class="h-filter-label">Ny mappe</span>', unsafe_allow_html=True)
    ny_navn = st.text_input("", placeholder="Mappenavn…", label_visibility="collapsed", key="_sag_ny_navn")
    if st.button("Opret mappe", use_container_width=True, key="_sag_opret"):
        if ny_navn.strip():
            opret_mappe(ny_navn.strip())
            st.rerun()
        else:
            st.warning("Indtast et navn.")

    sidebar_log_ud()

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="h-page-header">
  <h1 class="h-page-title">Sagsmappe</h1>
  <div class="h-gold-line"></div>
  <p class="h-page-meta">Gem og organisér relevante afgørelser</p>
</div>
""", unsafe_allow_html=True)

# ── Tom tilstand ─────────────────────────────────────────────────────────────
if not mapper:
    st.markdown(
        '<div style="text-align:center;padding:4rem 1rem;color:#94a3b8;">'
        '<div style="font-size:2.5rem;margin-bottom:0.8rem;">&#128194;</div>'
        '<div style="font-size:16px;font-weight:600;color:#475569;margin-bottom:0.5rem;">'
        'Ingen mapper endnu</div>'
        '<div style="font-size:13px;line-height:1.6;max-width:400px;margin:0 auto;">'
        'Opret din første mappe i sidebaren, og gem afgørelser fra PKN eller MFKN '
        'ved at klikke <strong>Gem</strong> på søgeresultaterne.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Valgt mappe ──────────────────────────────────────────────────────────────
mappe = mapper.get(valgt_id)
if not mappe:
    st.stop()

# Mappe-header med rename/delete
h_col1, h_col2, h_col3 = st.columns([6, 1.5, 1.5])
with h_col1:
    st.markdown(
        f'<div style="font-size:18px;font-weight:700;color:#0f172a;margin-bottom:4px;">'
        f'{mappe["navn"]}</div>'
        f'<div style="font-size:12px;color:#94a3b8;">'
        f'{len(mappe["afgørelser"])} {"afgørelse" if len(mappe["afgørelser"]) == 1 else "afgørelser"}'
        f' &middot; Oprettet {mappe["oprettet"][:10]}</div>',
        unsafe_allow_html=True,
    )

with h_col2:
    with st.popover("Omdøb"):
        nyt = st.text_input("Nyt navn", value=mappe["navn"], key=f"_rename_{valgt_id}")
        if st.button("Gem navn", key=f"_rename_btn_{valgt_id}"):
            if nyt.strip() and nyt.strip() != mappe["navn"]:
                omdøb_mappe(valgt_id, nyt.strip())
                st.rerun()

with h_col3:
    with st.popover("Slet"):
        st.markdown(f'Slet **{mappe["navn"]}** og alle gemte afgørelser?')
        if st.button("Ja, slet", type="primary", key=f"_del_{valgt_id}"):
            slet_mappe(valgt_id)
            st.rerun()

st.markdown("---")

# ── Afgørelsesliste ──────────────────────────────────────────────────────────
if not mappe["afgørelser"]:
    st.markdown(
        '<div style="text-align:center;padding:3rem 1rem;color:#94a3b8;">'
        '<div style="font-size:13px;">Ingen gemte afgørelser i denne mappe endnu.<br>'
        'Søg i PKN eller MFKN og klik <strong>Gem</strong> for at tilføje.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# Vis alle mapper-afgørelser
andre_mapper = {mid: m["navn"] for mid, m in mapper.items() if mid != valgt_id}

for i, afg in enumerate(mappe["afgørelser"]):
    badge = _BADGE_STYLE.get(afg["udfald"], _BADGE_DEFAULT)
    kilde_badge = _KILDE_BADGE.get(afg["kilde"], _BADGE_DEFAULT)
    kilde_label = "PKN" if afg["kilde"] == "pkn" else "MFKN"
    try:
        dato_str = pd.Timestamp(afg["dato"]).strftime("%d.%m.%Y")
    except Exception:
        dato_str = afg.get("dato", "–")

    st.markdown(f"""
<div style="background:#ffffff;border-radius:8px;padding:18px 22px;border:1px solid #e2e8f0;
            margin-bottom:2px;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <div style="display:flex;gap:8px;align-items:center;">
      <span style="font-size:11px;color:#94a3b8;font-weight:500;">{dato_str}</span>
      <span style="display:inline-block;padding:2px 6px;border-radius:3px;font-size:9px;
                    font-weight:700;letter-spacing:0.5px;text-transform:uppercase;{kilde_badge}">{kilde_label}</span>
    </div>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;
                  font-weight:600;{badge}">{afg['udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">
    {afg['titel']}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;
                  font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">
      {afg.get('kategori', '')}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;
                  font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">
      {afg.get('kommune', '')}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{afg.get('excerpt', '')}…</div>
</div>""", unsafe_allow_html=True)

    btn_cols = st.columns([2, 2, 2, 4]) if andre_mapper else st.columns([2, 2, 6])
    with btn_cols[0]:
        page = "pages/pkn.py" if afg["kilde"] == "pkn" else "pages/mfkn.py"
        if st.button("Åbn afgørelse →", key=f"_sag_goto_{i}_{valgt_id}"):
            st.session_state["_navigate_to_decision"] = {
                "link": afg["link"],
                "kilde": afg["kilde"],
            }
            st.switch_page(page)
    with btn_cols[1]:
        if st.button("Fjern", key=f"_sag_rm_{i}_{valgt_id}"):
            fjern_afgørelse(valgt_id, afg["link"])
            st.rerun()
    if andre_mapper:
        with btn_cols[2]:
            with st.popover("Flyt til…"):
                for mid, mnavn in andre_mapper.items():
                    if st.button(mnavn, key=f"_sag_mv_{i}_{mid}_{valgt_id}"):
                        from shared import gem_afgørelse as _gem
                        _gem(mid, afg["link"], afg["titel"], afg["dato"],
                             afg["udfald"], afg["kilde"], afg.get("kategori", ""),
                             afg.get("kommune", ""), afg.get("excerpt", ""))
                        fjern_afgørelse(valgt_id, afg["link"])
                        st.rerun()

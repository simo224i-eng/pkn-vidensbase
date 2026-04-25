import streamlit as st

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

import pandas as pd
from shared import (
    logo, inject_css, sidebar_log_ud,
    init_sagsmapper, opret_mappe, slet_mappe, omdøb_mappe,
    fjern_afgørelse, hent_alle_gemte_links, opdater_note,
    gem_afgørelse,
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

_UDFALD_RANK = {
    "Medhold": 0, "Ophævet": 1, "Hjemvist": 2, "Ændring": 3,
    "Stadfæstelse": 4, "Ikke medhold": 5, "Afvist": 6, "Ukendt": 7,
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
        mappe_navne = {mid: f"{m['navn']}  ·  {len(m['afgørelser'])}" for mid, m in mapper.items()}
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
    ny_navn = st.text_input("", placeholder="fx Lokalplan 234…", label_visibility="collapsed", key="_sag_ny_navn")
    if st.button("＋ Opret mappe", use_container_width=True, key="_sag_opret"):
        if ny_navn.strip():
            opret_mappe(ny_navn.strip())
            st.toast(f"Mappe '{ny_navn.strip()}' oprettet", icon="📁")
            st.rerun()
        else:
            st.warning("Indtast et navn.")

    sidebar_log_ud()

# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("""
<div class="h-page-header">
  <h1 class="h-page-title">Sagsmappe</h1>
  <p class="h-page-meta">Gem og organisér relevante afgørelser</p>
</div>
""", unsafe_allow_html=True)

# ── Tom tilstand: ingen mapper ───────────────────────────────────────────────
if not mapper:
    st.markdown(
        '<div style="text-align:center;padding:5rem 1rem;max-width:480px;margin:0 auto;">'
        '<div style="display:inline-flex;align-items:center;justify-content:center;'
        'width:64px;height:64px;background:#f1f5f9;border-radius:50%;margin-bottom:1.2rem;">'
        '<span style="font-size:28px;">📁</span></div>'
        '<div style="font-size:18px;font-weight:700;color:#0f172a;margin-bottom:0.6rem;">'
        'Start din første sagsmappe</div>'
        '<div style="font-size:13px;line-height:1.7;color:#475569;margin-bottom:1.6rem;">'
        'Saml de afgørelser du arbejder med på en aktiv sag, eller byg et privat opslagsværk '
        'over præjudikater du ofte vender tilbage til.</div>'
        '<div style="font-size:12px;color:#94a3b8;line-height:1.7;'
        'background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:14px 18px;'
        'text-align:left;">'
        '<strong style="color:#0f172a;">Sådan kommer du i gang:</strong><br>'
        '1. Opret en mappe i sidebaren ←<br>'
        '2. Søg i Planklagenævnet eller Miljøklagenævnet<br>'
        '3. Klik <strong>☆ Gem</strong> på relevante afgørelser</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Valgt mappe ──────────────────────────────────────────────────────────────
mappe = mapper.get(valgt_id)
if not mappe:
    st.stop()

# Mappe-header med rename/delete + sort
h_col1, h_col2 = st.columns([5, 3])
with h_col1:
    st.markdown(
        f'<div style="font-size:20px;font-weight:700;color:#0f172a;margin-bottom:4px;'
        f'letter-spacing:-0.3px;">{mappe["navn"]}</div>'
        f'<div style="font-size:11px;color:#94a3b8;letter-spacing:0.2px;">'
        f'{len(mappe["afgørelser"])} {"afgørelse" if len(mappe["afgørelser"]) == 1 else "afgørelser"}'
        f'  ·  Oprettet {mappe["oprettet"][:10]}</div>',
        unsafe_allow_html=True,
    )

with h_col2:
    a_col1, a_col2, a_col3 = st.columns(3)
    with a_col1:
        sort_valg = st.selectbox(
            "Sortering", ["Nyeste først", "Ældste først", "Efter udfald"],
            label_visibility="collapsed", key=f"_sag_sort_{valgt_id}",
        )
    with a_col2:
        with st.popover("Omdøb", use_container_width=True):
            nyt = st.text_input("Nyt navn", value=mappe["navn"], key=f"_rename_{valgt_id}")
            if st.button("Gem navn", key=f"_rename_btn_{valgt_id}", type="primary"):
                if nyt.strip() and nyt.strip() != mappe["navn"]:
                    omdøb_mappe(valgt_id, nyt.strip())
                    st.toast("Mappe omdøbt", icon="✏️")
                    st.rerun()
    with a_col3:
        with st.popover("Slet", use_container_width=True):
            st.markdown(f'Slet **{mappe["navn"]}**?')
            st.caption(f'Mappen indeholder {len(mappe["afgørelser"])} afgørelser. Denne handling kan ikke fortrydes.')
            if st.button("Ja, slet mappen", type="primary", key=f"_del_{valgt_id}"):
                slet_mappe(valgt_id)
                st.toast(f"Mappe slettet", icon="🗑️")
                st.rerun()

st.markdown('<div style="height:1px;background:#e2e8f0;margin:1.2rem 0 1.4rem;"></div>',
            unsafe_allow_html=True)

# ── Tom tilstand: tom mappe ──────────────────────────────────────────────────
if not mappe["afgørelser"]:
    st.markdown(
        '<div style="text-align:center;padding:3rem 1rem;color:#94a3b8;'
        'background:#f8fafc;border:1px dashed #cbd5e1;border-radius:10px;">'
        '<div style="font-size:13.5px;color:#475569;font-weight:600;margin-bottom:0.5rem;">'
        'Mappen er tom</div>'
        '<div style="font-size:12.5px;line-height:1.7;max-width:380px;margin:0 auto;">'
        'Søg i Planklagenævnet eller Miljøklagenævnet og klik '
        '<strong style="color:#0f172a;">☆ Gem</strong> på et resultat for at tilføje det her.'
        '</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.stop()

# ── Sorter afgørelser ────────────────────────────────────────────────────────
afgørelser = list(mappe["afgørelser"])
if sort_valg == "Nyeste først":
    afgørelser.sort(key=lambda a: a.get("dato", ""), reverse=True)
elif sort_valg == "Ældste først":
    afgørelser.sort(key=lambda a: a.get("dato", ""))
elif sort_valg == "Efter udfald":
    afgørelser.sort(key=lambda a: _UDFALD_RANK.get(a.get("udfald", "Ukendt"), 99))

andre_mapper = {mid: m["navn"] for mid, m in mapper.items() if mid != valgt_id}

# ── Vis afgørelser ───────────────────────────────────────────────────────────
for i, afg in enumerate(afgørelser):
    badge = _BADGE_STYLE.get(afg["udfald"], _BADGE_DEFAULT)
    kilde_badge = _KILDE_BADGE.get(afg["kilde"], _BADGE_DEFAULT)
    kilde_label = "PKN" if afg["kilde"] == "pkn" else "MFKN"
    try:
        dato_str = pd.Timestamp(afg["dato"]).strftime("%d.%m.%Y")
    except Exception:
        dato_str = afg.get("dato", "–")

    note = afg.get("note", "")
    note_html = ""
    if note:
        note_html = (
            f'<div style="margin-top:10px;padding:10px 12px;background:#fffbeb;'
            f'border-left:3px solid #f59e0b;border-radius:0 6px 6px 0;'
            f'font-size:12px;color:#78350f;line-height:1.6;">'
            f'<span style="font-weight:600;font-size:10px;text-transform:uppercase;'
            f'letter-spacing:0.5px;color:#92400e;">Note</span><br>{note}</div>'
        )

    st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;
            border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
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
      {afg.get('kategori', '') or '—'}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;
                  font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">
      {afg.get('kommune', '') or '—'}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{afg.get('excerpt', '')}…</div>
  {note_html}
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{afg['link']}" target="_blank" style="font-size:11px;color:#94a3b8;
       text-decoration:none;font-weight:500;">Åbn original på portalen ↗</a>
  </div>
</div>""", unsafe_allow_html=True)

    # Action row
    if andre_mapper:
        c1, c2, c3, c4 = st.columns([2, 1.5, 1.5, 5])
    else:
        c1, c2, c3, c4 = st.columns([2, 1.5, 0.001, 6.5])
    with c1:
        page = "pages/pkn.py" if afg["kilde"] == "pkn" else "pages/mfkn.py"
        if st.button("Læs afgørelse →", key=f"_sag_goto_{i}_{valgt_id}", use_container_width=True):
            st.session_state["_navigate_to_decision"] = {
                "link": afg["link"],
                "kilde": afg["kilde"],
            }
            st.switch_page(page)
    with c2:
        with st.popover("✎ Note" if not note else "✎ Rediger", use_container_width=True):
            ny_note = st.text_area(
                "Personlig note", value=note, height=100,
                placeholder="Fx: præjudikat for argument om §35 stk. 3…",
                key=f"_note_{i}_{valgt_id}",
            )
            if st.button("Gem note", key=f"_note_btn_{i}_{valgt_id}", type="primary"):
                opdater_note(valgt_id, afg["link"], ny_note.strip())
                st.toast("Note gemt", icon="📝")
                st.rerun()
    if andre_mapper:
        with c3:
            with st.popover("Flyt", use_container_width=True):
                st.caption("Flyt til mappe:")
                for mid, mnavn in andre_mapper.items():
                    if st.button(mnavn, key=f"_sag_mv_{i}_{mid}_{valgt_id}", use_container_width=True):
                        gem_afgørelse(mid, afg["link"], afg["titel"], afg["dato"],
                                      afg["udfald"], afg["kilde"], afg.get("kategori", ""),
                                      afg.get("kommune", ""), afg.get("excerpt", ""))
                        # Bevar note ved flytning
                        if afg.get("note"):
                            opdater_note(mid, afg["link"], afg["note"])
                        fjern_afgørelse(valgt_id, afg["link"])
                        st.toast(f"Flyttet til '{mnavn}'", icon="📂")
                        st.rerun()
    with c4:
        with st.popover("Fjern", use_container_width=False):
            st.caption(f"Fjern fra '{mappe['navn']}'?")
            if st.button("Ja, fjern", key=f"_sag_rm_{i}_{valgt_id}", type="primary"):
                fjern_afgørelse(valgt_id, afg["link"])
                st.toast("Afgørelse fjernet", icon="✓")
                st.rerun()

    st.markdown('<div style="height:8px;"></div>', unsafe_allow_html=True)

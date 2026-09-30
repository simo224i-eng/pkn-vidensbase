import streamlit as st

if not st.session_state.get("_autentificeret_ejnar"):
    st.switch_page("app.py")
    st.stop()

import re
import html as _html
import pandas as pd
import numpy as np
import plotly.express as px

from source_explainability import render_source_decision_core_html
from answer_citation_explainability import render_source_claims_html

from shared import (
    logo, _llm, _llm_stream, strip_html,
    format_afgørelse_tekst, render_detail_header, sidebar_log_ud,
    embeddings_tilgængelige, highlight_query, copy_button, render_filter_chips,
    get_embed_error, llm_tilgaengelig, llm_label,
)
import engine


LLM_AKTIV = llm_tilgaengelig()


# ── Data loading (engine gør arbejdet; her caches det pr. Streamlit-proces) ──
# cache_resource (ikke cache_data): deler ÉT df-objekt i stedet for at deep-copy'e
# de ~170MB tekst ved hvert kald. df muteres aldrig in-place efter load → sikkert,
# og sparer 1-2 fulde kopier i RAM ved opstart (afgørende for Streamlit Clouds 1GB).
@st.cache_resource(show_spinner="Indlæser kendelser…")
def load_data(version: int = 1):
    return engine.load_corpus_cached()[0]


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int, version: int = 1):
    return engine.load_corpus_cached()[1:]


@st.cache_resource(show_spinner=False)
def build_embeddings(n_rows: int, version: int = 1):
    return engine.build_embeddings(load_data())


def smart_retrieval(spørgsmål, df, vec, mat, ai_sub_idx, historik,
                    top_retrieve=40, top_final=8, embeds=None, filter_options=None):
    debug: dict = {}
    standalone, kilder = engine.smart_retrieval(
        spørgsmål, df, vec, mat, ai_sub_idx, historik,
        top_retrieve=top_retrieve, top_final=top_final, embeds=embeds,
        filter_options=filter_options, debug=debug,
    )
    st.session_state["_ejnar_last_auto_filters"] = {
        k: debug.get(k) for k in ("suggested", "applied", "before", "after")
    }
    return standalone, kilder


def _byg_prompt(spørgsmål, docs, historik=None):
    return engine.byg_prompt(spørgsmål, docs, historik)


_INGEN_LLM = "Ingen LLM konfigureret – se LLM_PROVIDER/LLM_API_KEY i Streamlit secrets."


def claude_svar(spørgsmål, docs, historik=None):
    if not LLM_AKTIV:
        return _INGEN_LLM
    return _llm(_byg_prompt(spørgsmål, docs, historik))


def claude_svar_stream(spørgsmål, docs, historik=None, placeholder=None):
    if not LLM_AKTIV:
        return _INGEN_LLM
    return _llm_stream(_byg_prompt(spørgsmål, docs, historik), placeholder=placeholder)


def claude_resumé(titel, tekst):
    if not LLM_AKTIV:
        return "Ingen API-nøgle."
    return _llm(engine.resumé_prompt(titel, tekst))


def erstat_kilde_refs(tekst, kilder):
    unique: dict = {}

    def repl(m):
        nums = [int(x) for x in re.findall(r'\d+', m.group(1))]
        spans = []
        for n in nums:
            if 1 <= n <= len(kilder):
                k = kilder[n - 1]
                sag = k.get("Sagsnummer", "") or "Kilde"
                try:
                    år = str(pd.Timestamp(k["Dato"]).year)
                except Exception:
                    år = "–"
                label = f"{sag} {år}".strip()
                unique[n - 1] = (label, k)
                spans.append(
                    f'<span style="color:#a0692a;font-weight:600;white-space:nowrap;">[{label}]</span>'
                )
        return " ".join(spans) if spans else m.group(0)

    out = re.sub(r"\[Kilde\s+([\d,\s]+)\]", repl, tekst)
    ordered = [v for _, v in sorted(unique.items())]
    return out, ordered


# ── Tilstand ──────────────────────────────────────────────────────────────────
if "chat_historik"     not in st.session_state: st.session_state.chat_historik = []
if "valgt_kendelse"    not in st.session_state: st.session_state.valgt_kendelse = None

# ── Indlæs ────────────────────────────────────────────────────────────────────
df = load_data()
vec, mat = build_index(len(df))
embeds = build_embeddings(len(df))
if embeds is None and embeddings_tilgængelige():
    build_embeddings.clear()
    embeds = build_embeddings(len(df))

_alle_mangeltyper = sorted({m for ms in df.get("Mangeltype", []) for m in ms}) \
                    if not df.empty else []
_alle_udfald      = ["Medhold", "Delvis medhold", "Ikke medhold", "Afvist", "Ukendt"]
_alle_selskaber   = sorted({s for s in df.get("Selskab", []) if s}) if not df.empty else []

_filter_options = {
    "Mangeltype": _alle_mangeltyper,
    "Selskab":    _alle_selskaber,
}

_voyage_key_sat = bool(st.secrets.get("VOYAGE_API_KEY", "") or st.secrets.get("OPENAI_API_KEY", ""))
_embeds_ok = embeds is not None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f'<div class="h-brand-wrap"><div class="h-logo-box">{logo(150, dark=True)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<span class="h-filter-label">Søgeord</span>', unsafe_allow_html=True)
    # Ryd søgefeltet hvis en chip eller "Ryd alle" har anmodet om det (skal ske
    # før widget'en instantieres, ellers ignorerer Streamlit værdiændringen).
    if st.session_state.pop("_ejnar_clear_soeg", False):
        st.session_state["ejnar_soeg"] = ""
    søg_input = st.text_input("", placeholder="f.eks. skimmel, tag, selvrisiko, levetid…",
                              label_visibility="collapsed", key="ejnar_soeg")
    søge_type = st.radio("", ["Ordret", "Intelligent"], horizontal=True,
                         label_visibility="collapsed", key="søge_type")
    st.markdown('<span style="font-size:10.5px;color:#64748b;line-height:1.4;display:block;margin-top:-6px;">'
                'Ordret = nøjagtig tekstmatch &nbsp;·&nbsp; Intelligent = AI finder relevante kendelser</span>',
                unsafe_allow_html=True)

    st.markdown('<span class="h-filter-label">Mangeltype</span>', unsafe_allow_html=True)
    mangel_valg = st.multiselect("", _alle_mangeltyper,
                                  label_visibility="collapsed", key="mt")

    st.markdown('<span class="h-filter-label">Forsikringsselskab</span>', unsafe_allow_html=True)
    selskab_valg = st.multiselect("", _alle_selskaber,
                                   label_visibility="collapsed", key="sel")

    if not df.empty and df["År"].notna().any():
        år_min, år_max = int(df["År"].min()), int(df["År"].max())
    else:
        år_min, år_max = 2000, 2026
    st.markdown('<span class="h-filter-label">Årsinterval</span>', unsafe_allow_html=True)
    år_range = st.slider("", år_min, år_max, (år_min, år_max), label_visibility="collapsed")

    st.markdown('<span class="h-filter-label">Udfald (for klager)</span>', unsafe_allow_html=True)
    udfald_valg = st.multiselect("", _alle_udfald,
                                  label_visibility="collapsed", key="ud")

    st.markdown("---")
    st.markdown(
        f"<span style='font-size:12px;color:#cbd5e1;font-weight:500;'>"
        f"**{len(df):,}** kendelser &nbsp;·&nbsp; {år_min}–{år_max}</span>",
        unsafe_allow_html=True,
    )
    if not df.empty and df["Dato"].notna().any():
        st.markdown(
            f"<span style='font-size:11px;color:#94a3b8;'>"
            f"Opdateret {df['Dato'].max().strftime('%d.%m.%Y')}</span>",
            unsafe_allow_html=True,
        )

    _har_filtre = bool(mangel_valg or selskab_valg or udfald_valg
                       or søg_input.strip() or år_range != (år_min, år_max))
    if _har_filtre:
        if st.button("Nulstil filtre", use_container_width=True, key="_ejnar_reset"):
            for k in ["mt", "sel", "ud", "søge_type"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state["_ejnar_clear_soeg"] = True
            st.rerun()


# ── Filtrering ────────────────────────────────────────────────────────────────
if df.empty:
    st.warning(
        "Ingen kendelser indlæst. Læg en `ejnar_ejerskifteforsikring.csv` i `ejnar/`-mappen "
        "(kør `python3 ejnar/scrape_ejnar.py` for at hente data fra ankeforsikring.dk).",
        icon="📁",
    )
    sidebar_log_ud()
    st.stop()


mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if mangel_valg:
    mask &= df["Mangeltype"].apply(lambda mts: any(m in mts for m in mangel_valg))
if selskab_valg:
    mask &= df["Selskab"].isin(selskab_valg)
if udfald_valg:
    mask &= df["Udfald"].isin(udfald_valg)

df_filter = df[mask].reset_index(drop=True)
sub_idx = df[mask].index.tolist()

_filter_sig = (len(df_filter),
               df_filter["Link"].iloc[0] if len(df_filter) > 0 else "",
               søg_input.strip(), søge_type)
if st.session_state.get("_filter_sig") != _filter_sig:
    st.session_state["vis_antal"] = 25
    st.session_state["_filter_sig"] = _filter_sig
_vis_antal = st.session_state.get("vis_antal", 25)

if søg_input.strip() and søge_type == "Intelligent":
    # Samme LLM-frie hybrid-relevans som API'et (TF-IDF + paragraf-BM25 + embeddings)
    _idx = engine.relevans_søg(søg_input.strip(), df, vec, mat, embeds, sub_idx=sub_idx, top_n=200)
    df_vis = df.iloc[_idx].reset_index(drop=True) if _idx else df.iloc[0:0]
    ai_sub_idx = sub_idx
elif søg_input.strip():
    _q = søg_input.strip()
    _text_mask = (
        df_filter["Titel"].str.contains(_q, case=False, na=False, regex=False) |
        df_filter["Tekst"].str.contains(_q, case=False, na=False, regex=False)
    )
    df_vis = df_filter[_text_mask].sort_values("Dato", ascending=False).reset_index(drop=True)
    _matched = df_filter.index[_text_mask].tolist()
    ai_sub_idx = [sub_idx[i] for i in _matched] if _matched else sub_idx
else:
    df_vis = df_filter.sort_values("Dato", ascending=False)
    ai_sub_idx = sub_idx

# Direkte opslag: et sagsnummer i søgefeltet lægger den kendelse øverst.
_sag_hits = engine.sagsnummer_hits(søg_input, df)
if len(_sag_hits):
    df_vis = pd.concat([_sag_hits, df_vis]).drop_duplicates("Link").reset_index(drop=True)


def build_download_text(data, søgeord=""):
    lines = [
        "ANKENÆVNET FOR FORSIKRING — EJERSKIFTEFORSIKRING — EKSPORT",
        f"Antal kendelser: {len(data)}",
        f"Søgeord: {søgeord if søgeord.strip() else '(ingen — kun filteret på mangeltype/selskab/udfald)'}",
        f"Genereret: {pd.Timestamp.now().strftime('%d.%m.%Y %H:%M')}",
        "=" * 72, "",
    ]
    for _, row in data.iterrows():
        dato = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
        mt = ", ".join(row.get("Mangeltype") or []) or "–"
        lines += [
            f"KENDELSE:    {row['Titel']}",
            f"DATO:        {dato}",
            f"SAGSNR:      {row.get('Sagsnummer') or '–'}",
            f"SELSKAB:     {row.get('Selskab') or '–'}",
            f"UDFALD:      {row.get('Udfald') or '–'}",
            f"MANGELTYPE:  {mt}",
            f"KILDE:       {row['Link']}",
            "-" * 72,
            (row.get("Tekst") or "").strip(),
            "", "=" * 72, "",
        ]
    return "\n".join(lines)


with st.sidebar:
    n = len(df_filter)
    st.markdown("---")
    if n == 0:
        st.caption("Ingen kendelser matcher filtrene.")
    else:
        dl = build_download_text(df_filter, søgeord=søg_input).encode("utf-8")
        st.download_button(
            label=f"⬇️ Download {n:,} kendelser (.txt)",
            data=dl,
            file_name="ejnar_kendelser.txt",
            mime="text/plain",
        )
    sidebar_log_ud()


_UDFALD_FARVER = {
    "Medhold": "#16a34a", "Delvis medhold": "#0891b2",
    "Ikke medhold": "#dc2626", "Afvist": "#d97706", "Ukendt": "#94a3b8",
}


def _udfald_fordeling_html(udfald: pd.Series) -> str:
    """Stablet bjælke med udfaldsfordelingen for de aktuelle resultater."""
    n = len(udfald)
    if not n:
        return ""
    tæl = udfald.value_counts()
    segs, legend = [], []
    for label, farve in _UDFALD_FARVER.items():
        k = int(tæl.get(label, 0))
        if not k:
            continue
        pct = 100 * k / n
        segs.append(f'<div title="{label}: {k}" style="width:{pct:.2f}%;background:{farve};"></div>')
        legend.append(
            f'<span style="white-space:nowrap;"><span style="display:inline-block;width:8px;height:8px;'
            f'border-radius:2px;background:{farve};margin-right:5px;"></span>{label} '
            f'<strong style="color:#0f172a;">{pct:.0f}%</strong> <span style="color:#94a3b8;">({k})</span></span>'
        )
    klager = int(tæl.get("Medhold", 0) + tæl.get("Delvis medhold", 0))
    return (
        '<div style="margin:0.4rem 0 0.9rem;padding:12px 14px;border:1px solid #e2e8f0;border-radius:8px;background:#f8fafc;">'
        '<div style="display:flex;justify-content:space-between;font-size:11.5px;color:#475569;margin-bottom:7px;">'
        '<span style="font-weight:600;letter-spacing:.2px;text-transform:uppercase;font-size:10.5px;">Udfald i resultaterne</span>'
        f'<span>Klager fik helt/delvist medhold i <strong style="color:#0f172a;">{100*klager/n:.0f}%</strong></span></div>'
        f'<div style="display:flex;height:8px;border-radius:4px;overflow:hidden;background:#e2e8f0;">{"".join(segs)}</div>'
        f'<div style="display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:#475569;margin-top:8px;">{"".join(legend)}</div>'
        '</div>'
    )


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="h-page-header">
  <h1 class="h-page-title">Ejerskifteforsikring</h1>
  <p class="h-page-meta">
    Ankenævnet for Forsikring &nbsp;·&nbsp; {len(df):,} kendelser
    &nbsp;·&nbsp; {år_min}–{år_max}
  </p>
</div>
""", unsafe_allow_html=True)


tab_søg, tab_stat, tab_ai = st.tabs(["  Kendelser  ", "  Statistik  ", "  AI Assistent  "])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – KENDELSER
# ════════════════════════════════════════════════════════════════════════════
with tab_søg:
    if st.session_state.valgt_kendelse is not None:
        row = st.session_state.valgt_kendelse
        if st.button("← Alle kendelser"):
            st.session_state.valgt_kendelse = None
            st.rerun()

        dato_str = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
        udfald = row.get("Udfald") or "Ukendt"
        chip_styles = {
            "Medhold":        "background:#f0fdf4;color:#166534;border-color:#bbf7d0",
            "Delvis medhold": "background:#ecfeff;color:#155e75;border-color:#a5f3fc",
            "Ikke medhold":   "background:#fef2f2;color:#991b1b;border-color:#fecaca",
            "Afvist":         "background:#fffbeb;color:#92400e;border-color:#fde68a",
        }
        chip_s = chip_styles.get(udfald, "background:#f8fafc;color:#64748b;border-color:#e2e8f0")
        mt_str = " / ".join(row.get("Mangeltype") or []) or "–"

        st.markdown(
            render_detail_header(
                titel=row["Titel"],
                udfald=udfald,
                chip_style=chip_s,
                dato_str=dato_str,
                meta_extra=[
                    ("Sagsnr.", row.get("Sagsnummer") or "–"),
                    ("Selskab", row.get("Selskab") or "–"),
                    ("Mangeltype", mt_str),
                ],
                link=row["Link"],
                link_label="Åbn original på ankeforsikring.dk",
            ),
            unsafe_allow_html=True,
        )

        col_tekst, col_ai = st.columns([3, 2], gap="large")
        with col_tekst:
            st.markdown(format_afgørelse_tekst(row["Tekst"]), unsafe_allow_html=True)
        with col_ai:
            st.markdown(
                '<div class="detail-ai-panel">'
                '<div class="detail-ai-title">✦ &nbsp;AI-Resumé</div>',
                unsafe_allow_html=True,
            )
            if st.button("Generer resumé →", key="gen_resume_btn"):
                with st.spinner("Analyserer…"):
                    try:
                        st.session_state._resumé = claude_resumé(row["Titel"], row["Tekst"])
                    except Exception as e:
                        st.session_state._resumé = f"Fejl: {e}"
            if "_resumé" in st.session_state:
                st.markdown(
                    f'<div class="detail-ai-resume">{st.session_state._resumé}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        # Aktive filter-chips
        _chips = []
        if søg_input.strip():
            def _clr_søg(): st.session_state["_ejnar_clear_soeg"] = True
            _chips.append((f"Søgeord: {søg_input.strip()[:30]}", _clr_søg))
        for _m in mangel_valg:
            def _c(_v=_m): st.session_state["mt"] = [x for x in st.session_state.get("mt", []) if x != _v]
            _chips.append((f"Mangel: {_m}", _c))
        for _s in selskab_valg:
            def _c(_v=_s): st.session_state["sel"] = [x for x in st.session_state.get("sel", []) if x != _v]
            _chips.append((f"Selskab: {_s}", _c))
        for _u in udfald_valg:
            def _c(_v=_u): st.session_state["ud"] = [x for x in st.session_state.get("ud", []) if x != _v]
            _chips.append((f"Udfald: {_u}", _c))
        if år_range != (år_min, år_max):
            def _c(): pass
            _chips.append((f"År: {år_range[0]}–{år_range[1]}", _c))
        if _chips:
            def _clr_all():
                for k in ["mt", "sel", "ud", "søge_type"]:
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state["_ejnar_clear_soeg"] = True
            _chips.append(("Ryd alle", _clr_all))
            render_filter_chips(_chips, key_prefix="ejnar_chip")

        total = len(df_filter)
        hits = len(df_vis)
        if søg_input:
            tag = "intelligent" if søge_type == "Intelligent" else "ordret"
            st.markdown(f"**{hits}** resultater for \"{søg_input}\" · {tag} søgning "
                        f"(ud af {total:,} filtrerede)")
        else:
            st.markdown(f"Viser {min(_vis_antal, hits)} af **{total:,}** kendelser (nyeste først)")

        if hits > 0:
            st.markdown(_udfald_fordeling_html(df_vis["Udfald"]), unsafe_allow_html=True)
            _sort_valg = (["Relevans", "Nyeste først", "Ældste først"]
                          if søg_input.strip() and søge_type == "Intelligent"
                          else ["Nyeste først", "Ældste først"])
            _sort = st.selectbox("Sortér", _sort_valg, key="ejnar_sort",
                                 label_visibility="collapsed")
            if _sort != "Relevans" and not len(_sag_hits):
                df_vis = df_vis.sort_values("Dato", ascending=(_sort == "Ældste først"),
                                            na_position="last")

        if hits == 0:
            st.markdown(
                '<div style="text-align:center;padding:3rem 1rem;color:#94a3b8;">'
                '<div style="font-size:2rem;margin-bottom:0.5rem;">🔍</div>'
                '<div style="font-size:15px;font-weight:600;color:#475569;margin-bottom:0.4rem;">'
                'Ingen kendelser matcher din søgning</div>'
                '<div style="font-size:13px;">Prøv at udvide filtrene eller ændre søgeordene.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
        else:
            _BADGE = {
                "Medhold":        "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                "Delvis medhold": "background:#ecfeff;color:#155e75;border:1px solid #a5f3fc",
                "Ikke medhold":   "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                "Afvist":         "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
            }
            _BADGE_DEF = "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0"
            _hl = søg_input.strip()
            for _, row in df_vis.head(_vis_antal).iterrows():
                bs = _BADGE.get(row["Udfald"], _BADGE_DEF)
                ds = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                mt_label = " / ".join(row.get("Mangeltype") or []) or "–"
                sel = row.get("Selskab") or "–"
                titel_h = highlight_query(row["Titel"], _hl) if _hl else _html.escape(row["Titel"])
                exc_h = highlight_query(engine.snippet(row["Tekst"], _hl, 320), _hl) if _hl \
                        else (_html.escape(row["Excerpt"]) + "…")
                st.markdown(f"""
<div class="pkn-card-v2" style="background:#ffffff;border-radius:8px 8px 0 0;padding:18px 22px;border:1px solid #e2e8f0;border-bottom:none;font-family:'Inter',system-ui,sans-serif;">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
    <span style="font-size:11px;color:#94a3b8;font-weight:500;letter-spacing:.2px;">{ds}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:20px;font-size:10px;font-weight:600;letter-spacing:.1px;{bs}">{row['Udfald']}</span>
  </div>
  <div style="font-size:13.5px;font-weight:600;color:#0f172a;margin:0 0 8px;line-height:1.5;">{titel_h}</div>
  <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:10px;">
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{mt_label}</span>
    <span style="display:inline-block;padding:2px 8px;border-radius:4px;font-size:10.5px;font-weight:500;color:#475569;background:#f1f5f9;border:1px solid #e2e8f0;">{sel}</span>
  </div>
  <div style="font-size:12.5px;color:#64748b;line-height:1.6;">{exc_h}</div>
  <div style="margin-top:10px;padding-top:10px;border-top:1px solid #f1f5f9;">
    <a href="{row['Link']}" target="_blank" style="font-size:11px;color:#94a3b8;text-decoration:none;font-weight:500;">Åbn kendelse på ankeforsikring.dk ↗</a>
  </div>
</div>""", unsafe_allow_html=True)
                if st.button("Læs kendelse →", key=f"btn_{row['Id']}"):
                    st.session_state.valgt_kendelse = row.to_dict()
                    if "_resumé" in st.session_state:
                        del st.session_state["_resumé"]
                    st.rerun()

            if _vis_antal < hits:
                tilbage = hits - _vis_antal
                if st.button(f"Vis 25 mere ({tilbage} tilbage)", use_container_width=True):
                    st.session_state["vis_antal"] = _vis_antal + 25
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 – STATISTIK
# ════════════════════════════════════════════════════════════════════════════
with tab_stat:
    d = df_filter
    _LAYOUT = dict(
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter, system-ui, sans-serif", size=12, color="#334155"),
        margin=dict(t=10, b=10, l=10, r=10),
    )
    _UDFALD_FARVER = {
        "Medhold":        "#10b981",
        "Delvis medhold": "#06b6d4",
        "Ikke medhold":   "#ef4444",
        "Afvist":         "#f59e0b",
        "Ukendt":         "#94a3b8",
    }

    if d.empty:
        st.info("Ingen data at vise med de valgte filtre.")
    else:
        k1, k2, k3, k4 = st.columns(4)
        pct_medhold = (d["Udfald"].isin(["Medhold", "Delvis medhold"])).mean() * 100
        år_span = f"{int(d['År'].min())}–{int(d['År'].max())}" if d["År"].notna().any() else "–"
        for col, tal, label in [
            (k1, f"{len(d):,}", "Kendelser"),
            (k2, f"{pct_medhold:.0f}%", "Medhold-rate"),
            (k3, f"{d['Selskab'].replace('', np.nan).dropna().nunique()}", "Selskaber"),
            (k4, år_span, "Årsinterval"),
        ]:
            col.markdown(
                f'<div class="stat-card"><div class="stat-number">{tal}</div>'
                f'<div class="stat-label">{label}</div></div>',
                unsafe_allow_html=True,
            )
        st.markdown("<br>", unsafe_allow_html=True)

        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("#### Kendelser per år")
            år_df = d.dropna(subset=["År"]).groupby("År").size().reset_index(name="Antal")
            fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#8C1C2E"])
            fig.update_layout(**_LAYOUT)
            fig.update_traces(marker_line_width=0)
            st.plotly_chart(fig, use_container_width=True)

        with col_r:
            st.markdown("#### Udfald over tid")
            udf_år = d.dropna(subset=["År"]).groupby(["År", "Udfald"]).size().reset_index(name="Antal")
            fig2 = px.bar(udf_år, x="År", y="Antal", color="Udfald",
                          color_discrete_map=_UDFALD_FARVER, barmode="stack")
            fig2.update_layout(**_LAYOUT)
            fig2.update_traces(marker_line_width=0)
            st.plotly_chart(fig2, use_container_width=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("#### Top mangeltyper")
            mt_rows = []
            for ms in d["Mangeltype"]:
                for m in ms:
                    mt_rows.append(m)
            if mt_rows:
                mt_df = pd.Series(mt_rows).value_counts().rename_axis("Mangeltype") \
                          .reset_index(name="Antal").sort_values("Antal", ascending=True).tail(15)
                fig3 = px.bar(mt_df, x="Antal", y="Mangeltype", orientation="h",
                              color_discrete_sequence=["#1a3060"])
                fig3.update_layout(**_LAYOUT)
                fig3.update_traces(marker_line_width=0)
                st.plotly_chart(fig3, use_container_width=True)

        with col_b:
            st.markdown("#### Top forsikringsselskaber")
            sel_df = (d[d["Selskab"] != ""].groupby("Selskab").size()
                       .reset_index(name="Sager").sort_values("Sager", ascending=True).tail(15))
            if not sel_df.empty:
                fig4 = px.bar(sel_df, x="Sager", y="Selskab", orientation="h",
                              color_discrete_sequence=["#8C1C2E"])
                fig4.update_layout(**_LAYOUT)
                fig4.update_traces(marker_line_width=0)
                st.plotly_chart(fig4, use_container_width=True)

        st.markdown("#### Medhold-rate per mangeltype")
        rate_rows = []
        for mt in sorted({m for ms in d["Mangeltype"] for m in ms}):
            sub = d[d["Mangeltype"].apply(lambda ms: mt in ms)]
            if len(sub) >= 3:
                rate_rows.append({
                    "Mangeltype": mt,
                    "Sager": len(sub),
                    "Medhold_%": round(sub["Udfald"].isin(["Medhold", "Delvis medhold"]).mean() * 100, 1),
                })
        if rate_rows:
            mr = pd.DataFrame(rate_rows).sort_values("Medhold_%", ascending=True)
            fig5 = px.bar(mr, x="Medhold_%", y="Mangeltype", orientation="h",
                          color="Medhold_%", color_continuous_scale=["#fee2e2", "#10b981"],
                          hover_data={"Sager": True}, labels={"Medhold_%": "Medhold (%)"})
            fig5.update_layout(**_LAYOUT, coloraxis_showscale=False)
            fig5.update_traces(marker_line_width=0)
            st.plotly_chart(fig5, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
def _citat_advarsel_html(suspekte: list) -> str:
    punkter = "".join(
        f"<li>«{c[:140]}…»</li>" if len(c) > 140 else f"<li>«{c}»</li>"
        for c in suspekte[:3]
    )
    return (
        "\n\n<div style=\"margin-top:1rem;padding:0.9rem 1.1rem;background:#fef2f2;"
        "border:1px solid #fecaca;border-radius:6px;font-size:12.5px;color:#991b1b;\">"
        "<strong>Bemærk – citatverifikation:</strong> følgende citat(er) kunne "
        "ikke genfindes ordret i kilderne og bør dobbelttjekkes:"
        f"<ul style=\"margin:0.4rem 0 0 1.1rem;padding:0;\">{punkter}</ul></div>"
    )


def _udfald_advarsel_html(konflikter: list) -> str:
    import html as _html
    punkter = "".join(
        f"<li>[Kilde {k['kilde']}]: svaret siger «{_html.escape(k['påstand'])}», "
        f"kendelsen er «{_html.escape(k['faktisk'])}»</li>"
        for k in konflikter[:4]
    )
    return (
        "\n\n<div style=\"margin-top:1rem;padding:0.9rem 1.1rem;background:#fef2f2;"
        "border:1px solid #fecaca;border-radius:6px;font-size:12.5px;color:#991b1b;\">"
        "<strong>Bemærk – udfaldskontrol:</strong> svaret gengiver udfaldet af følgende "
        "kendelse(r) anderledes end nævnets afgørelse:"
        f"<ul style=\"margin:0.4rem 0 0 1.1rem;padding:0;\">{punkter}</ul></div>"
    )


def _besvar_spørgsmål(tekst: str) -> None:
    """Kør retrieval + streamet svar + citatkontrol og gem i chat-historikken."""
    tekst = tekst.strip()
    st.session_state.chat_historik.append({"rolle": "bruger", "tekst": tekst})
    st.markdown(f'<div class="chat-user">{tekst}</div>', unsafe_allow_html=True)
    ph = st.empty()
    with st.spinner("Søger i kendelser…"):
        try:
            _, kilder = smart_retrieval(
                tekst, df, vec, mat, ai_sub_idx,
                st.session_state.chat_historik, embeds=embeds,
                filter_options=_filter_options,
            )
        except Exception:
            kilder = []
    try:
        svar = claude_svar_stream(tekst, kilder,
                                  historik=st.session_state.chat_historik,
                                  placeholder=ph)
        suspekte = engine.mistænkelige_citater(svar, kilder, tekst)
        konflikter = engine.udfaldskonflikter(svar, kilder)
        if suspekte or konflikter:
            if suspekte:
                svar = svar + _citat_advarsel_html(suspekte)
            if konflikter:
                svar = svar + _udfald_advarsel_html(konflikter)
            ph.markdown(svar, unsafe_allow_html=True)
    except Exception as e:
        svar = f"Fejl ved AI Assistent: {e}"
        ph.error(svar)
        kilder = []
    af = st.session_state.pop("_ejnar_last_auto_filters", None)
    st.session_state.chat_historik.append(
        {"rolle": "assistent", "tekst": svar, "kilder": kilder,
         "auto_filters": af, "spørgsmål": tekst})
    st.rerun()


with tab_ai:
    n_ai = len(ai_sub_idx)
    filtreret = n_ai != len(df)
    antal_tekst = f"{n_ai:,}" if filtreret else f"{len(df):,}"
    filtreret_label = " (filtreret)" if filtreret else ""
    søge_mode = "Hybrid (TF-IDF + semantisk)" if embeds is not None else "TF-IDF"

    st.markdown(f"""
<div class="ai-hero">
  <span class="material-symbols-rounded ai-hero-icon">smart_toy</span>
  <div>
    <div class="ai-hero-title">Spørg til praksis om ejerskifteforsikring</div>
    <div class="ai-hero-sub">
      Søger i <strong>{antal_tekst} kendelser{filtreret_label}</strong>
      og svarer med kildehenvisninger. Opfølgningsspørgsmål husker kontekst.
    </div>
    <div style="font-size:10.5px;color:#94a3b8;margin-top:4px;">Søgemetode: {søge_mode}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    if not _embeds_ok:
        try:
            keys = sorted([k for k in st.secrets.keys()])
        except Exception:
            keys = []
        keylist = ", ".join(f"`{k}`" for k in keys) if keys else "(ingen)"
        if _voyage_key_sat:
            err = get_embed_error() or "Ukendt fejl"
            st.warning(
                "**Intelligent søgning ikke aktiv.** Embedding-indekset kunne ikke bygges.\n\n"
                f"**API-fejl:** `{err}`\n\nFundne secrets: {keylist}",
                icon="⚠️",
            )
        else:
            st.info(
                "**TF-IDF-søgning er aktiv** (ordbaseret). For hybrid semantisk søgning: "
                "tilføj `VOYAGE_API_KEY` i Streamlit Cloud secrets og genstart appen. "
                f"Fundne secrets: {keylist}.",
                icon="ℹ️",
            )

    if not LLM_AKTIV:
        st.error("Ingen LLM konfigureret. Tilføj `ANTHROPIC_API_KEY` eller `LLM_PROVIDER` + "
                 "`LLM_API_KEY` i Streamlit secrets (se ejnar/README.md).")
    else:
        st.caption(f"Model: {llm_label()}")
        if mangel_valg and len(mangel_valg) == 1:
            ctx = mangel_valg[0].lower()
            forslag = [
                f"Hvad er Ankenævnets praksis ved {ctx}?",
                f"Hvornår får klager medhold i {ctx}-sager?",
                f"Hvilke argumenter er afgørende ved {ctx}?",
                f"Hvornår nægter selskabet dækning for {ctx}?",
            ]
        elif søg_input.strip():
            q = søg_input.strip()
            forslag = [
                f"Hvad er Ankenævnets praksis vedrørende {q}?",
                f"Hvornår får klager medhold i sager om {q}?",
                f"Hvilke argumenter er afgørende for {q}?",
                f"Er der en klar tendens i kendelserne om {q}?",
            ]
        else:
            forslag = [
                "Hvornår dækker ejerskifteforsikringen skimmelsvamp?",
                "Hvilken praksis har Ankenævnet for utætheder i tag?",
                "Hvordan bedømmes restlevetid på installationer?",
                "Hvornår er en mangel undtaget pga. tilstandsrapporten?",
            ]
        st.markdown('<div id="ai-forslag-anchor"></div>', unsafe_allow_html=True)
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"fs_{i}"):
                _besvar_spørgsmål(f)

        with st.form("chat_form", clear_on_submit=True):
            spørgsmål = st.text_area("Dit spørgsmål", height=80,
                                      placeholder="Hvad er Ankenævnets praksis for…?")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send ➤", use_container_width=True, type="primary")
            ryd = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.chat_historik = []
            st.rerun()

        if send and spørgsmål.strip():
            _besvar_spørgsmål(spørgsmål)

        st.divider()

        for msg_idx, msg in enumerate(st.session_state.chat_historik):
            if msg["rolle"] == "bruger":
                st.markdown(
                    '<div style="display:flex;justify-content:flex-end;margin:1rem 0 0.2rem;">'
                    '<span style="font-size:10px;font-weight:700;color:#64748b;'
                    'text-transform:uppercase;letter-spacing:1.2px;">Du</span></div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div style="display:flex;justify-content:flex-end;">'
                    f'<div class="chat-user">{msg["tekst"]}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    '<div style="display:flex;align-items:center;gap:6px;margin:1rem 0 0.2rem;">'
                    '<span style="font-size:10px;font-weight:600;color:#8C1C2E;'
                    'text-transform:uppercase;letter-spacing:0.6px;">Ejnar</span></div>',
                    unsafe_allow_html=True,
                )
                af = msg.get("auto_filters")
                if af and af.get("suggested"):
                    chips = " · ".join(
                        f"<strong>{k}:</strong> {', '.join(str(v) for v in vs)}"
                        for k, vs in af["suggested"].items()
                    )
                    status = (f'Indsnævret til {af["after"]} kendelser'
                              if af.get("applied") else "Foreslået (ikke anvendt — for få hits)")
                    st.markdown(
                        f'<div style="margin:0 0 0.6rem;padding:6px 10px;background:#f8fafc;'
                        f'border:1px solid #eef1f6;border-radius:4px;font-size:11px;color:#64748b;">'
                        f'<span style="color:#94a3b8;text-transform:uppercase;letter-spacing:0.8px;'
                        f'font-weight:600;font-size:9.5px;">Auto-filter</span> &nbsp;{chips} '
                        f'<span style="color:#94a3b8;">— {status}</span></div>',
                        unsafe_allow_html=True,
                    )
                kilder = msg.get("kilder", [])
                if kilder:
                    vist, ref_kilder = erstat_kilde_refs(msg["tekst"], kilder)
                else:
                    vist, ref_kilder = msg["tekst"], []

                source_query = str(msg.get("spørgsmål") or "").strip()
                if not source_query and msg_idx > 0:
                    previous = st.session_state.chat_historik[msg_idx - 1]
                    if previous.get("rolle") == "bruger":
                        source_query = str(previous.get("tekst") or "").strip()

                col_svar, col_kld = st.columns([3, 2])
                with col_svar:
                    st.markdown(f'<div class="chat-assistant">{vist}</div>', unsafe_allow_html=True)
                    ren = strip_html(msg.get("tekst", ""))
                    copy_button(ren, label="Kopiér svar", key=f"cp_{msg_idx}")
                    if ref_kilder:
                        st.markdown(
                            '<div style="font-size:10px;color:#94a3b8;margin:6px 0 4px;'
                            'text-transform:uppercase;letter-spacing:1px;font-weight:600;">'
                            'Åbn kendelse:</div>',
                            unsafe_allow_html=True,
                        )
                        bcols = st.columns(min(len(ref_kilder), 3))
                        for ci, (label, k) in enumerate(ref_kilder):
                            with bcols[ci % 3]:
                                if st.button(f"↗ {label}", key=f"ref_{msg_idx}_{ci}",
                                             use_container_width=True):
                                    st.session_state.valgt_kendelse = k
                                    if "_resumé" in st.session_state:
                                        del st.session_state["_resumé"]
                                    st.rerun()
                with col_kld:
                    if kilder:
                        st.markdown(
                            '<div style="font-size:11px;font-weight:700;color:#475569;'
                            'text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">'
                            'Kilder</div>',
                            unsafe_allow_html=True,
                        )
                        for i, k in enumerate(kilder):
                            try:
                                ts = pd.Timestamp(k["Dato"])
                                ds = ts.strftime("%d.%m.%Y")
                                aar = str(ts.year)
                            except Exception:
                                ds, aar = "–", "–"
                            sag = k.get("Sagsnummer") or "–"
                            udf = k.get("Udfald") or ""
                            with st.expander(f"[{i+1}] {sag} · {aar}"):
                                if st.button(f"▶ Åbn kendelsen i Ejnar",
                                             key=f"kilde_open_{msg_idx}_{i}",
                                             use_container_width=True, type="primary"):
                                    st.session_state.valgt_kendelse = k
                                    if "_resumé" in st.session_state:
                                        del st.session_state["_resumé"]
                                    st.rerun()
                                st.markdown(
                                    f'<div style="font-size:13px;font-weight:600;color:#1e3a5f;'
                                    f'margin:8px 0 4px 0;line-height:1.4">{k["Titel"]}</div>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f'<div style="font-size:11px;color:#64748b;margin-bottom:10px">'
                                    f'{ds} &nbsp;·&nbsp; {udf} &nbsp;·&nbsp; '
                                    f'{k.get("Selskab", "") or "–"}</div>',
                                    unsafe_allow_html=True,
                                )
                                claim_html = render_source_claims_html(
                                    msg.get("tekst", ""), i + 1, source_count=len(kilder)
                                )
                                if claim_html:
                                    st.markdown(claim_html, unsafe_allow_html=True)
                                core_html = render_source_decision_core_html(k, source_query)
                                if core_html:
                                    st.markdown(core_html, unsafe_allow_html=True)
                                rå = k.get("Tekst", "")
                                fmt = re.sub(r'\. ([A-ZÆØÅ])', r'.</p><p>\1', rå)
                                st.markdown(
                                    '<div style="font-size:13px;line-height:1.7;color:#1e293b;'
                                    'max-height:420px;overflow-y:auto;padding:12px 14px;'
                                    'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;'
                                    f'margin-bottom:8px"><p>{fmt}</p></div>',
                                    unsafe_allow_html=True,
                                )
                                st.markdown(
                                    f'<a href="{k["Link"]}" target="_blank" '
                                    f'style="font-size:12px;color:#2563eb;text-decoration:none">'
                                    f'Åbn original kendelse på ankeforsikring.dk ↗</a>',
                                    unsafe_allow_html=True,
                                )

"""
PKN Udkastgenerator – Miljøvurdering
Genererer "Klagen" og "Planklagenævnets vurdering" afsnit
for miljørapporter over lokalplaner, kommuneplantillæg og kommuneplaner.

Separat fra Harald. Kan deployes selvstændigt.
"""

import re
import streamlit as st

st.set_page_config(
    page_title="PKN Udkast – Miljøvurdering",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Login ────────────────────────────────────────────────────────────────────
_KORREKT_KODE = "Ugv73uwz"
try:
    _KORREKT_KODE = st.secrets.get("APP_PASSWORD", _KORREKT_KODE)
except Exception:
    pass

if not st.session_state.get("_authenticated"):
    st.title("PKN Udkastgenerator")
    st.caption("Indtast adgangskode for at fortsætte")
    pwd = st.text_input("Adgangskode", type="password", key="login_pwd")
    if pwd:
        if pwd == _KORREKT_KODE:
            st.session_state["_authenticated"] = True
            st.rerun()
        else:
            st.error("Forkert adgangskode.")
    st.stop()

from data import load_data, build_index, find_relevante_sager
from prompts import generer_klage_afsnit, generer_vurdering_afsnit, forbedre_vurdering


def _format_udkast(tekst: str) -> str:
    """Konverter plain text udkast til pæn HTML."""
    html_out = tekst
    html_out = re.sub(
        r'\[VERIFICER:?\s*([^\]]*)\]',
        r'<span class="verificer">[VERIFICER: \1]</span>',
        html_out,
    )
    paragraphs = [p.strip() for p in html_out.split("\n") if p.strip()]
    html_out = "".join(f"<p>{p}</p>" for p in paragraphs)
    return html_out

# ── CSS ──────────────────────────────────────────────────────────────────────
_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
header[data-testid="stHeader"] { display: none !important; }
[data-testid="stMain"] .block-container { padding-top: 1.5rem !important; }
body, [data-testid="stAppViewContainer"] { font-family: 'Inter', system-ui, sans-serif; }
[data-testid="stSidebar"] { display: none !important; }

/* Resultat-boks */
.udkast-box {
    font-family: 'Inter', system-ui, sans-serif;
    padding: 2rem;
    background: #fffcf8; border: 1px solid #e0dbd4;
    border-radius: 10px; margin-top: 1rem;
}
.udkast-box p { margin: 0 0 1em; font-size: 15px; line-height: 1.85; color: #1e293b; }
.udkast-section {
    font-size: 11.5px; font-weight: 700; color: #1e3a5f;
    text-transform: uppercase; letter-spacing: 1.8px;
    margin: 2em 0 0.6em; padding: 8px 14px;
    background: #eef3fa; border-left: 3px solid #1e3a5f;
    border-radius: 0 5px 5px 0;
}
.verificer {
    background: #fef3c7; color: #92400e; padding: 1px 6px;
    border-radius: 3px; font-size: 12.5px; font-weight: 600;
}
.section-label {
    font-size: 11px; font-weight: 700; color: #1e3a5f;
    text-transform: uppercase; letter-spacing: 1.5px;
    margin: 2rem 0 0.5rem; padding-bottom: 0.3rem;
    border-bottom: 2px solid #eef3fa;
}
</style>
"""
try:
    st.html(_CSS)
except AttributeError:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────────────
if "resultater" not in st.session_state:
    st.session_state.resultater = []
if "præcedens_cache" not in st.session_state:
    st.session_state.præcedens_cache = []


# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom: 1.5rem;">
  <h1 style="font-size: 28px; font-weight: 700; color: #1a1a2e; margin: 0;">
    PKN Udkastgenerator
  </h1>
  <p style="font-size: 14px; color: #64748b; margin: 4px 0 0;">
    Miljøvurdering &middot; Klagepunkt for klagepunkt
  </p>
</div>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="background:#eef3fa;border-left:3px solid #1e3a5f;border-radius:0 8px 8px 0;'
    'padding:14px 18px;margin-bottom:1.5rem;font-size:13.5px;color:#1a2744;line-height:1.65;">'
    'Indsæt <strong>ét klagepunkt</strong> ad gangen. Systemet finder automatisk relevante '
    'præcedensafgørelser og genererer "Klagen" og "Planklagenævnets vurdering" i PKN\'s stil.'
    '</div>',
    unsafe_allow_html=True,
)


# ── Formular: Alt i ét flow ──────────────────────────────────────────────────
with st.form("klagepunkt_form"):

    # ── Sagskontekst ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Sagskontekst</div>', unsafe_allow_html=True)

    col_plan, col_model = st.columns([2, 1])
    with col_plan:
        plan_type = st.selectbox(
            "Plantype",
            ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Lokalplan + Kommuneplantillæg"],
            key="plan_type",
        )
    with col_model:
        model_valg = st.selectbox(
            "AI-model",
            ["claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001"],
            key="model_valg",
            help=(
                "Sonnet: god kvalitet, hurtig (~1 DKK/klagepunkt). "
                "Opus: bedst til komplekse vurderinger (~8 DKK/klagepunkt). "
                "Haiku: billigst (~0,10 DKK/klagepunkt)."
            ),
        )

    sags_kontekst = st.text_area(
        "Sagsbeskrivelse",
        height=120,
        placeholder=(
            "Kort beskrivelse af sagen: Hvilken kommune, hvilken plan, "
            "hvad muliggør planen, hvem klager, og hvad er det overordnede tema..."
        ),
        key="sags_kontekst",
    )

    kommunens_afgørelse = st.text_area(
        "Kommunens afgørelse / miljørapportens konklusioner",
        height=120,
        placeholder=(
            "Paste relevante dele af kommunens afgørelse eller "
            "miljørapportens konklusioner her..."
        ),
        key="kommunens_afgørelse",
    )

    # ── Klagepunktet ─────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Klagepunktet</div>', unsafe_allow_html=True)

    emne = st.text_input(
        "Klagepunktets emne",
        placeholder="F.eks. 'Påvirkning af Natura 2000-område' eller 'Manglende grundvandsredegørelse'",
        key="emne_input",
    )

    klage_tekst = st.text_area(
        "Klagerens anbringender (rå tekst)",
        height=200,
        placeholder=(
            "Paste den relevante del af klagen her – hvad anfører klageren? "
            "Det behøver ikke være i PKN-stil, det konverterer systemet..."
        ),
        key="klage_input",
    )

    kommunens_bemærkninger = st.text_area(
        "Kommunens bemærkninger til klagepunktet (valgfrit)",
        height=100,
        placeholder="Evt. kommunens svar/bemærkninger til dette specifikke klagepunkt...",
        key="kommune_bem_input",
    )

    # ── Interne bemærkninger ─────────────────────────────────────────────
    st.markdown('<div class="section-label">Interne bemærkninger</div>', unsafe_allow_html=True)

    col_udfald, col_præcedens = st.columns([2, 1])
    with col_udfald:
        forventet_udfald = st.selectbox(
            "Forventet udfald",
            ["Ikke medhold", "Medhold"],
            key="forventet_udfald",
            help="Hvad er det aftalte udfald for dette klagepunkt?",
        )
    with col_præcedens:
        antal_præcedens = st.number_input(
            "Præcedenssager", min_value=1, max_value=10, value=5, key="antal_præcedens"
        )

    interne_noter = st.text_area(
        "Dine noter / instruktioner til vurderingen",
        height=120,
        placeholder=(
            "Stikord eller noter til hvad vurderingen skal lægge vægt på, fx:\n"
            "- Kommunen har tilstrækkeligt belyst grundvandsforhold\n"
            "- Henvis til miljørapportens afsnit 14.3\n"
            "- Lægge vægt på at planen ikke ændrer arealanvendelsen"
        ),
        key="interne_noter_input",
    )

    # ── Submit ───────────────────────────────────────────────────────────
    generer = st.form_submit_button(
        "Generer udkast for dette klagepunkt",
        use_container_width=True,
        type="primary",
    )


# ── Generer ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

if generer:
    if not klage_tekst.strip():
        st.warning("Indsæt klagerens anbringender.")
    elif not ANTHROPIC_API_KEY:
        st.error("Tilføj ANTHROPIC_API_KEY i Streamlit secrets.")
    elif not sags_kontekst.strip():
        st.warning("Udfyld sagsbeskrivelsen.")
    else:
        with st.spinner("Indlæser PKN-afgørelser..."):
            df = load_data()
            vec, mat = build_index(df)

        with st.spinner("Finder relevante præcedensafgørelser..."):
            query = f"{emne} {klage_tekst[:1000]}"
            præcedens_df = find_relevante_sager(query, df, vec, mat, top_n=antal_præcedens)
            præcedens = præcedens_df.to_dict("records")
            st.session_state.præcedens_cache = præcedens

        with st.spinner("Skriver 'Klagen'-afsnittet..."):
            klage_udkast = generer_klage_afsnit(
                api_key=ANTHROPIC_API_KEY,
                model=model_valg,
                emne=emne,
                klage_rå=klage_tekst,
                sags_kontekst=sags_kontekst,
                plan_type=plan_type,
                præcedens=præcedens,
            )

        with st.spinner("Skriver 'Planklagenævnets vurdering'-afsnittet..."):
            vurdering_udkast, ai_noter = generer_vurdering_afsnit(
                api_key=ANTHROPIC_API_KEY,
                model=model_valg,
                emne=emne,
                klage_udkast=klage_udkast,
                kommunens_afgørelse=kommunens_afgørelse,
                kommunens_bemærkninger=kommunens_bemærkninger,
                sags_kontekst=sags_kontekst,
                plan_type=plan_type,
                præcedens=præcedens,
                forventet_udfald=forventet_udfald,
                interne_noter=interne_noter,
            )

        st.session_state.resultater.append({
            "emne": emne,
            "klage": klage_udkast,
            "vurdering": vurdering_udkast,
            "ai_noter": ai_noter,
        })


# ── Vis resultater ───────────────────────────────────────────────────────────
if st.session_state.resultater:
    st.markdown("---")

    for i, r in enumerate(reversed(st.session_state.resultater)):
        idx = len(st.session_state.resultater) - i
        real_idx = len(st.session_state.resultater) - 1 - i  # index i listen
        with st.expander(f"Klagepunkt {idx}: {r['emne']}", expanded=(i == 0)):

            # Klagen
            st.markdown('<div class="udkast-section">Klagen</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="udkast-box">{_format_udkast(r["klage"])}</div>',
                unsafe_allow_html=True,
            )

            # Vurdering
            st.markdown('<div class="udkast-section">Planklagenævnets vurdering</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="udkast-box">{_format_udkast(r["vurdering"])}</div>',
                unsafe_allow_html=True,
            )

            # AI-noter
            if r.get("ai_noter"):
                st.markdown('<div class="udkast-section">AI-noter (intern)</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div style="background:#f8f5f0;border:1px solid #e0dbd4;'
                    f'border-radius:8px;padding:1.5rem;font-size:14px;line-height:1.8;'
                    f'color:#4a4a4a;">{_format_udkast(r["ai_noter"])}</div>',
                    unsafe_allow_html=True,
                )

            # ── Feedback / opfølgning ───────────────────────────────────
            st.markdown(
                '<div style="margin-top:1.5rem;padding-top:1rem;border-top:1px solid #e0dbd4;">'
                '<span style="font-size:12px;font-weight:600;color:#64748b;">Forfin vurderingen</span>'
                '</div>',
                unsafe_allow_html=True,
            )
            feedback = st.text_input(
                "Feedback til vurderingen",
                placeholder="F.eks. 'Gør det kortere', 'Skriv mere om grundvand', 'Fjern afsnittet om støj'...",
                key=f"feedback_{idx}",
                label_visibility="collapsed",
            )
            if st.button("Opdater vurdering", key=f"opdater_{idx}", type="secondary"):
                if feedback.strip() and ANTHROPIC_API_KEY:
                    with st.spinner("Reviderer vurderingen..."):
                        ny_vurdering = forbedre_vurdering(
                            api_key=ANTHROPIC_API_KEY,
                            model=st.session_state.get("model_valg", "claude-opus-4-6"),
                            nuværende_vurdering=r["vurdering"],
                            feedback=feedback,
                            emne=r["emne"],
                            klage_udkast=r["klage"],
                            sags_kontekst=st.session_state.get("sags_kontekst", ""),
                            plan_type=st.session_state.get("plan_type", "Lokalplan"),
                        )
                        # Gem historik
                        if "historik" not in st.session_state.resultater[real_idx]:
                            st.session_state.resultater[real_idx]["historik"] = []
                        st.session_state.resultater[real_idx]["historik"].append(r["vurdering"])
                        st.session_state.resultater[real_idx]["vurdering"] = ny_vurdering
                        st.rerun()
                elif not feedback.strip():
                    st.warning("Skriv din feedback først.")

            # Vis historik-knap hvis der er tidligere versioner
            if r.get("historik"):
                with st.expander(f"Tidligere versioner ({len(r['historik'])})"):
                    for v_idx, tidl in enumerate(reversed(r["historik"])):
                        v_num = len(r["historik"]) - v_idx
                        st.markdown(f"**Version {v_num}:**")
                        st.markdown(
                            f'<div class="udkast-box" style="opacity:0.7;">{_format_udkast(tidl)}</div>',
                            unsafe_allow_html=True,
                        )

            # Download
            samlet = f"Klagen\n\n{r['klage']}\n\nPlanklagenævnets vurdering\n\n{r['vurdering']}"
            st.download_button(
                label="Download samlet (.txt)",
                data=samlet.encode("utf-8"),
                file_name=f"klagepunkt_{idx}_{r['emne'][:30]}.txt",
                mime="text/plain",
                key=f"download_{idx}",
            )

    # Præcedens
    if st.session_state.præcedens_cache:
        with st.expander("Anvendte præcedensafgørelser"):
            for j, p in enumerate(st.session_state.præcedens_cache):
                st.markdown(
                    f"**[{j+1}]** {p['Titel'][:120]}  \n"
                    f"<small>Score: {p.get('_score', 0):.3f} · "
                    f"[Åbn på PKN]({p['Link']})</small>",
                    unsafe_allow_html=True,
                )

    if st.button("Ryd alle resultater"):
        st.session_state.resultater = []
        st.session_state.præcedens_cache = []
        st.rerun()

st.caption("Udkast er kun til intern brug og skal altid gennemgås kritisk.")

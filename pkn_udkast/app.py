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
    layout="wide",
    initial_sidebar_state="expanded",
)

from data import load_data, build_index, find_relevante_sager
from prompts import generer_klage_afsnit, generer_vurdering_afsnit


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
[data-testid="stMain"] .block-container { padding-top: 1.5rem !important; max-width: 900px; }

body, [data-testid="stAppViewContainer"] { font-family: 'Inter', system-ui, sans-serif; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a2744 0%, #0f1b33 100%) !important;
}
[data-testid="stSidebar"] * { color: #94a3b8 !important; font-family: 'Inter', sans-serif !important; }
[data-testid="stSidebar"] .stTextArea textarea,
[data-testid="stSidebar"] .stTextInput input {
    background: #1e293b !important; border: 1px solid #334155 !important;
    color: #e2e8f0 !important; border-radius: 5px !important; font-size: 13px !important;
}
[data-testid="stSidebar"] hr { border-color: #1e293b !important; }

/* Resultat-boks */
.udkast-box {
    font-family: 'Inter', system-ui, sans-serif;
    max-width: 80ch; padding: 2rem;
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
</style>
"""
st.markdown(_CSS, unsafe_allow_html=True)


# ── Session state ────────────────────────────────────────────────────────────
if "resultater" not in st.session_state:
    st.session_state.resultater = []  # list of {"klagepunkt": str, "klage": str, "vurdering": str}
if "præcedens_cache" not in st.session_state:
    st.session_state.præcedens_cache = []


# ── Sidebar: Sagskontekst ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Sagskontekst")
    st.caption(
        "Udfyld nedenstående en gang pr. sag. "
        "Denne information bruges som kontekst for alle klagepunkter."
    )

    plan_type = st.selectbox(
        "Plantype",
        ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Lokalplan + Kommuneplantillæg"],
        key="plan_type",
    )

    sags_kontekst = st.text_area(
        "Sagsbeskrivelse",
        height=160,
        placeholder=(
            "Kort beskrivelse af sagen: Hvilken kommune, hvilken plan, "
            "hvad muliggør planen, hvem klager, og hvad er det overordnede tema..."
        ),
        key="sags_kontekst",
    )

    kommunens_afgørelse = st.text_area(
        "Kommunens afgørelse / miljørapportens konklusioner",
        height=160,
        placeholder=(
            "Paste relevante dele af kommunens afgørelse eller "
            "miljørapportens konklusioner her..."
        ),
        key="kommunens_afgørelse",
    )

    st.markdown("---")

    model_valg = st.selectbox(
        "AI-model",
        ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-haiku-4-5-20251001"],
        key="model_valg",
        help=(
            "Sonnet: god kvalitet, hurtig (~1 DKK/klagepunkt). "
            "Opus: bedst til komplekse vurderinger (~8 DKK/klagepunkt). "
            "Haiku: billigst (~0,10 DKK/klagepunkt)."
        ),
    )

    st.markdown("---")
    st.caption("Udkast er kun til intern brug og skal altid gennemgås kritisk.")


# ── Page header ──────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom: 2rem;">
  <h1 style="font-size: 28px; font-weight: 700; color: #1a1a2e; margin: 0;">
    PKN Udkastgenerator
  </h1>
  <p style="font-size: 14px; color: #64748b; margin: 4px 0 0;">
    Miljøvurdering &middot; Klagepunkt for klagepunkt
  </p>
</div>
""", unsafe_allow_html=True)


# ── Hovedformular: Et klagepunkt ────────────────────────────────────────────
st.markdown(
    '<div style="background:#eef3fa;border-left:3px solid #1e3a5f;border-radius:0 8px 8px 0;'
    'padding:14px 18px;margin-bottom:1.5rem;font-size:13.5px;color:#1a2744;line-height:1.65;">'
    'Indsæt <strong>ét klagepunkt</strong> ad gangen. Systemet finder automatisk relevante '
    'præcedensafgørelser og genererer "Klagen" og "Planklagenævnets vurdering" i PKN\'s stil.'
    '</div>',
    unsafe_allow_html=True,
)

with st.form("klagepunkt_form"):
    emne = st.text_input(
        "Klagepunktets emne",
        placeholder="F.eks. 'Påvirkning af Natura 2000-område' eller 'Manglende grundvandsredegørelse'",
        key="emne_input",
    )

    klage_tekst = st.text_area(
        "Klagers anbringender (rå tekst)",
        height=220,
        placeholder=(
            "Paste den relevante del af klagen her – hvad anfører klager? "
            "Det behøver ikke være i PKN-stil, det konverterer systemet..."
        ),
        key="klage_input",
    )

    kommunens_bemærkninger = st.text_area(
        "Kommunens bemærkninger til klagepunktet (valgfrit)",
        height=120,
        placeholder="Evt. kommunens svar/bemærkninger til dette specifikke klagepunkt...",
        key="kommune_bem_input",
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        generer = st.form_submit_button(
            "Generer udkast for dette klagepunkt",
            use_container_width=True,
            type="primary",
        )
    with col2:
        antal_præcedens = st.number_input(
            "Præcedenssager", min_value=1, max_value=10, value=5, key="antal_præcedens"
        )


# ── Generer ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

if generer:
    if not klage_tekst.strip():
        st.warning("Indsæt klagers anbringender.")
    elif not ANTHROPIC_API_KEY:
        st.error("Tilføj ANTHROPIC_API_KEY i Streamlit secrets.")
    elif not sags_kontekst.strip():
        st.warning("Udfyld sagskontekst i sidepanelet.")
    else:
        # Indlæs data
        with st.spinner("Indlæser PKN-afgørelser..."):
            df = load_data()
            vec, mat = build_index(df)

        # Find præcedens
        with st.spinner("Finder relevante præcedensafgørelser..."):
            query = f"{emne} {klage_tekst[:1000]}"
            præcedens_df = find_relevante_sager(query, df, vec, mat, top_n=antal_præcedens)
            præcedens = præcedens_df.to_dict("records")
            st.session_state.præcedens_cache = præcedens

        # Generer Klagen
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

        # Generer Vurdering
        with st.spinner("Skriver 'Planklagenævnets vurdering'-afsnittet..."):
            vurdering_udkast = generer_vurdering_afsnit(
                api_key=ANTHROPIC_API_KEY,
                model=model_valg,
                emne=emne,
                klage_udkast=klage_udkast,
                kommunens_afgørelse=kommunens_afgørelse,
                kommunens_bemærkninger=kommunens_bemærkninger,
                sags_kontekst=sags_kontekst,
                plan_type=plan_type,
                præcedens=præcedens,
            )

        # Gem resultat
        st.session_state.resultater.append({
            "emne": emne,
            "klage": klage_udkast,
            "vurdering": vurdering_udkast,
        })


# ── Vis resultater ───────────────────────────────────────────────────────────
if st.session_state.resultater:
    st.markdown("---")
    st.markdown("## Genererede afsnit")

    for i, r in enumerate(reversed(st.session_state.resultater)):
        idx = len(st.session_state.resultater) - i
        with st.expander(f"Klagepunkt {idx}: {r['emne']}", expanded=(i == 0)):
            tab_klage, tab_vurdering, tab_samlet = st.tabs([
                "Klagen", "Planklagenævnets vurdering", "Samlet"
            ])

            with tab_klage:
                st.markdown(
                    f'<div class="udkast-box">{_format_udkast(r["klage"])}</div>',
                    unsafe_allow_html=True,
                )

            with tab_vurdering:
                st.markdown(
                    f'<div class="udkast-box">{_format_udkast(r["vurdering"])}</div>',
                    unsafe_allow_html=True,
                )

            with tab_samlet:
                samlet = f"**Klagen**\n\n{r['klage']}\n\n**Planklagenævnets vurdering**\n\n{r['vurdering']}"
                st.download_button(
                    label="Download samlet (.txt)",
                    data=samlet.encode("utf-8"),
                    file_name=f"klagepunkt_{idx}_{r['emne'][:30]}.txt",
                    mime="text/plain",
                    key=f"download_{idx}",
                )
                st.markdown(
                    f'<div class="udkast-box">'
                    f'<div class="udkast-section">Klagen</div>{_format_udkast(r["klage"])}'
                    f'<div class="udkast-section">Planklagenævnets vurdering</div>{_format_udkast(r["vurdering"])}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # Vis præcedens
    if st.session_state.præcedens_cache:
        with st.expander("Anvendte præcedensafgørelser"):
            for j, p in enumerate(st.session_state.præcedens_cache):
                st.markdown(
                    f"**[{j+1}]** {p['Titel'][:120]}  \n"
                    f"<small>Score: {p.get('_score', 0):.3f} · "
                    f"[Åbn på PKN]({p['Link']})</small>",
                    unsafe_allow_html=True,
                )

    # Ryd-knap
    if st.button("Ryd alle resultater"):
        st.session_state.resultater = []
        st.session_state.præcedens_cache = []
        st.rerun()



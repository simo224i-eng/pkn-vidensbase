import streamlit as st

if not st.session_state.get("_autentificeret_v2"):
    st.switch_page("app.py")
    st.stop()

import pandas as pd
import requests
import re
from shared import logo, strip_html, extract_kommune

ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── CSS-accent (samme grøn som MFKN) ─────────────────────────────────────────
_CSS = """<style>
[data-testid="stSidebar"] .stSlider [role="slider"] { background: #2d6a4f !important; }
[data-testid="collapsedControl"]::after { color: #52b788 !important; }
</style>"""
try:
    st.html(_CSS)
except AttributeError:
    st.markdown(_CSS, unsafe_allow_html=True)


# ── Hjælpefunktioner ──────────────────────────────────────────────────────────

def _byg_søgeforespørgsel(klage: str, afgørelse: str, bemærkninger: str) -> str:
    """Udled søgeord fra sagsakter til at finde relevante præcedenssager."""
    samlet = f"{klage} {afgørelse} {bemærkninger}"
    # Behold kun de første 1500 tegn for søgningens skyld
    return samlet[:1500]


def _find_relevante_sager(query: str, df, vec, mat, top_n: int = 5):
    from sklearn.metrics.pairwise import cosine_similarity
    # Filtrer til strandbeskyttelseslinje-sager
    strand_idx = df.index[df["Kategori"] == "Strandbeskyttelseslinje"].tolist()
    if not strand_idx:
        strand_idx = None
    qv = vec.transform([query])
    if strand_idx:
        scores = cosine_similarity(qv, mat[strand_idx]).flatten()
        top_local = scores.argsort()[-top_n:][::-1]
        top_global = [strand_idx[i] for i in top_local if scores[i] > 0.01]
        result = df.loc[top_global].copy()
        result["_score"] = [scores[i] for i in top_local if scores[i] > 0.01]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top = scores.argsort()[-top_n:][::-1]
        result = df.iloc[top].copy()
        result["_score"] = scores[top]
        result = result[result["_score"] > 0.01]
    return result.reset_index(drop=True)


def _generer_udkast(klage: str, afgørelse: str, bemærkninger: str,
                    øvrige: str, præcedens: list, vejledning: str) -> str:
    if not ANTHROPIC_API_KEY:
        return "Tilføj ANTHROPIC_API_KEY i Streamlit secrets."

    præcedens_blok = ""
    for i, p in enumerate(præcedens):
        try:
            dato = pd.Timestamp(p["Dato"]).strftime("%d.%m.%Y")
        except Exception:
            dato = "–"
        præcedens_blok += (
            f"\n[Præcedens {i+1}] {dato} – {p['Titel']}\n"
            f"{p['Tekst'][:2500]}\n"
            "---\n"
        )

    vejledning_blok = ""
    if vejledning.strip():
        vejledning_blok = f"\nSKRIVEVEJLEDNING OG SKABELON FRA MFKN:\n{vejledning}\n"

    prompt = f"""Du er juridisk sagsbehandler i Miljø- og Fødevareklagenævnet (MFKN).
Din opgave er at skrive et fuldstændigt afgørelsesudkast i en sag om strandbeskyttelseslinjen (naturbeskyttelseslovens § 15).

AFGØRELSENS FASTE STRUKTUR (følg denne nøje):

**Indledende sætning:**
"Miljø- og Fødevareklagenævnet har truffet afgørelse efter naturbeskyttelseslovens § 15, stk. 1, jf. § 65 b, stk. 1, jf. § 78, stk. 4."

**Dispositiv (resultat):**
Angiv tydeligt om nævnet stadfæster, ophæver eller ændrer Kystdirektoratets afgørelse – og hvad afgørelsen konkret går ud på.

**Standardtekst om gebyr og endelig afgørelse:**
"Det indbetalte klagegebyr tilbagebetales [ikke / ikke / ja afhængig af udfald]."
"Miljø- og Fødevareklagenævnets afgørelse er endelig og kan ikke indbringes for anden administrativ myndighed, jf. § 17, stk. 1, i lov om Miljø- og Fødevareklagenævnet og gebyrbekendtgørelsens § 2, stk. 6. Eventuel retssag til prøvelse af afgørelsen skal være anlagt inden 6 måneder, jf. naturbeskyttelseslovens § 88, stk. 1."

**Afsnit 1. Klagen til Miljø- og Fødevareklagenævnet**
Hvem klagede, hvornår, og hvad er klagepunkterne.

**Afsnit 2. Sagens oplysninger**
2.1 Ejendommen og området (beliggenhed, zonestatus, karakteristik af ejendommen og omgivelser, afstand til kyst, evt. Natura 2000)
2.2 Den påklagede afgørelse (hvad Kystdirektoratet har afgjort og begrundelsen herfor)
2.3 Klagers bemærkninger (hvis der er supplerende bemærkninger)

**Afsnit 3. Nævnets bemærkninger og afgørelse**
- Redegørelse for retsgrundlaget (§ 15 og § 65 b – brug de standardformuleringer MFKN anvender)
- Nævnets konkrete vurdering af sagen
- Konklusion

REGLER FOR UDKASTET:
- Brug [PLACEHOLDER: beskrivelse] for oplysninger du mangler (fx [PLACEHOLDER: matrikelnummer], [PLACEHOLDER: præcis afstand til kyst])
- Skriv præcist og juridisk korrekt dansk – følg MFKN's sproglige stil fra præcedensafgørelserne
- Brug tredje person om klager ("klager har anført…")
- Brug de standardformuleringer om retsgrundlaget som fremgår af præcedensafgørelserne
{vejledning_blok}
RELEVANTE PRÆCEDENSAFGØRELSER (brug disse som stilistisk og juridisk vejledning):
{præcedens_blok}
SAGSAKTER:

**Klagen:**
{klage}

**Kystdirektoratets afgørelse:**
{afgørelse}

**Bemærkninger ved oversendelse:**
{bemærkninger}

**Øvrige bilag/bemærkninger:**
{øvrige if øvrige.strip() else "(ingen)"}

Skriv nu det fulde afgørelsesudkast:"""

    r = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": 4000,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    r.raise_for_status()
    return r.json()["content"][0]["text"]


# ── Indlæs data og indeks (genbrug fra mfkn_beskyttelseslinjer) ───────────────
@st.cache_data(show_spinner=False)
def _hent_df():
    # Importér load_mfkn_data fra mfkn_beskyttelseslinjer
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from mfkn_beskyttelseslinjer import load_mfkn_data, build_mfkn_index
    df = load_mfkn_data()
    return df

# ── Session state ─────────────────────────────────────────────────────────────
for key in ["udkast_resultat", "udkast_præcedens", "udkast_genereret"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
<div class="h-brand-wrap">
  <div class="h-logo-box">{logo(152)}</div>
</div>""", unsafe_allow_html=True)

    st.markdown(
        '<span style="font-family:\'Cinzel\',Georgia,serif;font-size:10px;font-weight:700;'
        'color:#c49a3c;text-transform:uppercase;letter-spacing:2px;margin:1.4rem 0 0.35rem;'
        'display:block;">Vejledning og skabelon</span>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Paste MFKN's skrivevejledning og/eller afgørelsesskabelon herunder. "
        "Jo mere du giver, jo tættere på MFKN's eget format bliver udkastet."
    )
    vejledning_input = st.text_area(
        "",
        height=220,
        placeholder="Paste skrivevejledning og/eller skabelon her…",
        label_visibility="collapsed",
        key="vejledning_tekst",
    )
    st.markdown("---")
    st.caption("Afgørelsesudkast er kun til personlig brug og skal altid gennemgås kritisk.")


# ── Page header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="h-page-header">
  <h1 class="h-page-title">HAROLD</h1>
  <div class="h-gold-line"></div>
  <p class="h-page-meta">Afgørelsesudkast · Strandbeskyttelseslinje</p>
</div>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="background:#f0fdf4;border-left:3px solid #2d6a4f;border-radius:0 8px 8px 0;'
    'padding:14px 18px;margin-bottom:1.5rem;font-size:13.5px;color:#1a3a2a;line-height:1.65;">'
    'Indsæt sagsakter herunder. Systemet finder automatisk de mest relevante præcedensafgørelser '
    'og genererer et struktureret afgørelsesudkast baseret på MFKN\'s praksis.'
    '</div>',
    unsafe_allow_html=True,
)

# ── Sagsakter-formular ────────────────────────────────────────────────────────
with st.form("udkast_form"):
    st.markdown("#### Sagsakter")

    klage = st.text_area(
        "Klagen (+ evt. bilag)",
        height=180,
        placeholder="Paste klagetekst her – hvem har klaget, hvornår, og hvad er klagepunkterne…",
        key="input_klage",
    )
    col1, col2 = st.columns(2)
    with col1:
        kyst_afgørelse = st.text_area(
            "Kystdirektoratets afgørelse",
            height=180,
            placeholder="Paste Kystdirektoratets afgørelse (f.eks. afslag på dispensation)…",
            key="input_kyst",
        )
    with col2:
        bemærkninger = st.text_area(
            "Kystdirektoratets bemærkninger ved oversendelse",
            height=180,
            placeholder="Paste bemærkninger fra Kystdirektoratet ved sagens oversendelse til nævnet…",
            key="input_bem",
        )

    øvrige = st.text_area(
        "Øvrige bilag / supplerende bemærkninger (valgfrit)",
        height=100,
        placeholder="Evt. supplerende oplysninger fra klager eller Kystdirektoratet…",
        key="input_øvrige",
    )

    generer = st.form_submit_button(
        "Generer afgørelsesudkast →",
        use_container_width=True,
        type="primary",
    )

# ── Generer ───────────────────────────────────────────────────────────────────
if generer:
    if not klage.strip() and not kyst_afgørelse.strip():
        st.warning("Indsæt mindst klagen eller Kystdirektoratets afgørelse.")
    elif not ANTHROPIC_API_KEY:
        st.error("Tilføj ANTHROPIC_API_KEY i Streamlit secrets.")
    else:
        with st.spinner("Søger i præcedensafgørelser og genererer udkast…"):
            try:
                from mfkn_beskyttelseslinjer import load_mfkn_data, build_mfkn_index
                df = load_mfkn_data()
                vec, mat = build_mfkn_index(len(df))

                query = _byg_søgeforespørgsel(klage, kyst_afgørelse, bemærkninger)
                præcedens_df = _find_relevante_sager(query, df, vec, mat, top_n=5)
                præcedens = præcedens_df.to_dict("records")

                udkast = _generer_udkast(
                    klage=klage,
                    afgørelse=kyst_afgørelse,
                    bemærkninger=bemærkninger,
                    øvrige=øvrige,
                    præcedens=præcedens,
                    vejledning=vejledning_input or "",
                )
                st.session_state.udkast_resultat = udkast
                st.session_state.udkast_præcedens = præcedens
                st.session_state.udkast_genereret = True
            except Exception as e:
                st.error(f"Fejl: {e}")

# ── Vis resultat ──────────────────────────────────────────────────────────────
if st.session_state.udkast_genereret and st.session_state.udkast_resultat:
    st.markdown("---")

    udkast_tekst = st.session_state.udkast_resultat

    # Download-knap
    st.download_button(
        label="⬇ Download udkast (.txt)",
        data=udkast_tekst.encode("utf-8"),
        file_name="afgørelsesudkast.txt",
        mime="text/plain",
    )

    # Vis udkastet formateret
    # Konverter markdown-lignende formatering til HTML
    udkast_html = udkast_tekst
    # Afsnitsoverskrifter
    udkast_html = re.sub(
        r'\*\*(Afsnit \d+[\.\d]*[^*]*|[^*]{3,60}:)\*\*',
        lambda m: (
            f'<div style="font-size:11.5px;font-weight:700;color:#2d6a4f;'
            f'text-transform:uppercase;letter-spacing:1.8px;'
            f'margin:2em 0 0.6em;padding:8px 14px;'
            f'background:#f0fdf4;border-left:3px solid #2d6a4f;'
            f'border-radius:0 5px 5px 0;">'
            f'{m.group(1).rstrip(":")}</div>'
        ),
        udkast_html,
    )
    # [PLACEHOLDER]-markering
    udkast_html = re.sub(
        r'\[PLACEHOLDER:?\s*([^\]]*)\]',
        r'<span style="background:#fef3c7;color:#92400e;padding:1px 6px;'
        r'border-radius:3px;font-size:12.5px;font-weight:600;">'
        r'[PLACEHOLDER: \1]</span>',
        udkast_html,
    )
    # Linjeskift til afsnit
    paragraphs = [p.strip() for p in udkast_html.split("\n") if p.strip()]
    udkast_html = "".join(
        p if p.startswith("<div") else
        f'<p style="margin:0 0 1em;font-size:15px;line-height:1.85;color:#1e293b;">{p}</p>'
        for p in paragraphs
    )

    st.markdown(
        f'<div style="font-family:\'Inter\',system-ui,sans-serif;max-width:80ch;'
        f'padding:2rem;background:#fffcf8;border:1px solid #ece6dc;'
        f'border-radius:10px;margin-top:1rem;">'
        f'{udkast_html}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")
    tab_præcedens, = st.tabs(["  Anvendte præcedensafgørelser  "])

    with tab_præcedens:
        præcedens = st.session_state.udkast_præcedens or []
        if not præcedens:
            st.info("Ingen præcedensafgørelser fundet.")
        else:
            st.markdown(
                f'<p style="font-size:13px;color:#6b5040;margin-bottom:1rem;">'
                f'Disse {len(præcedens)} afgørelser er automatisk udvalgt som de mest relevante '
                f'for sagen og er brugt som grundlag for udkastet.</p>',
                unsafe_allow_html=True,
            )
            for i, p in enumerate(præcedens):
                try:
                    dato = pd.Timestamp(p["Dato"]).strftime("%d.%m.%Y")
                except Exception:
                    dato = "–"
                udfald = p.get("Udfald", "")
                udfald_farver = {
                    "Stadfæstelse": "background:#fef2f2;color:#991b1b;border:1px solid #fecaca",
                    "Ophævet":      "background:#f5f3ff;color:#5b21b6;border:1px solid #ddd6fe",
                    "Ændring":      "background:#f0fdf4;color:#166534;border:1px solid #bbf7d0",
                    "Afvist":       "background:#fffbeb;color:#92400e;border:1px solid #fde68a",
                }
                badge = udfald_farver.get(udfald, "background:#f8fafc;color:#64748b;border:1px solid #e2e8f0")

                with st.expander(f"[{i+1}] {p['Titel'][:90]}…" if len(p['Titel']) > 90 else f"[{i+1}] {p['Titel']}"):
                    st.markdown(
                        f'<div style="display:flex;gap:10px;align-items:center;margin-bottom:10px;">'
                        f'<span style="font-size:12px;color:#6b5040;">{dato}</span>'
                        f'<span style="padding:2px 8px;border-radius:20px;font-size:10px;'
                        f'font-weight:600;{badge}">{udfald}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                    tekst_preview = p.get("Tekst", "")[:1500]
                    st.markdown(
                        f'<div style="font-size:13px;line-height:1.7;color:#1e293b;'
                        f'max-height:320px;overflow-y:auto;padding:12px 14px;'
                        f'background:#f8fafc;border:1px solid #e2e8f0;border-radius:6px;">'
                        f'{tekst_preview}…</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<a href="{p["Link"]}" target="_blank" '
                        f'style="font-size:12px;color:#2d6a4f;text-decoration:none;">'
                        f'Åbn original afgørelse på MFKN\'s hjemmeside ↗</a>',
                        unsafe_allow_html=True,
                    )

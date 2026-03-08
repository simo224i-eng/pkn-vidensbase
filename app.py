import streamlit as st
import pandas as pd
import re
import csv
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="PKN Indsigt",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #f8f9fb; }
[data-testid="stSidebar"] { background: #1a1f36; }
[data-testid="stSidebar"] * { color: #e0e4f0 !important; }
[data-testid="stSidebar"] .stTextInput input { background: #2a2f4a !important; border-color: #3a3f5a !important; }

.pkn-card {
    background: white; border-radius: 12px; padding: 18px 20px; margin-bottom: 12px;
    border-left: 4px solid #4f6ef7; box-shadow: 0 1px 4px rgba(0,0,0,.07);
}
.pkn-card-title { font-size: 15px; font-weight: 600; color: #1a1f36; margin: 4px 0 8px; }
.pkn-card-meta  { font-size: 12px; color: #6b7280; margin-bottom: 8px; }
.pkn-card-excerpt { font-size: 13px; color: #374151; line-height: 1.5; }
.pkn-badge { display: inline-block; padding: 2px 9px; border-radius: 20px; font-size: 11px; font-weight: 600; margin-right: 6px; }
.badge-medhold { background: #d1fae5; color: #065f46; }
.badge-afslag  { background: #fee2e2; color: #991b1b; }
.badge-ugyldig { background: #ede9fe; color: #5b21b6; }
.badge-afvist  { background: #fef3c7; color: #92400e; }
.badge-ukendt  { background: #e5e7eb; color: #374151; }

.stat-card { background: white; border-radius: 12px; padding: 20px 24px; text-align: center; box-shadow: 0 1px 4px rgba(0,0,0,.07); }
.stat-number { font-size: 36px; font-weight: 700; color: #4f6ef7; }
.stat-label  { font-size: 13px; color: #6b7280; margin-top: 4px; }

.chat-user      { background: #4f6ef7; color: white; border-radius: 16px 16px 4px 16px; padding: 12px 16px; margin: 8px 0; max-width: 75%; margin-left: auto; }
.chat-assistant { background: white; color: #1a1f36; border-radius: 16px 16px 16px 4px; padding: 12px 16px; margin: 8px 0; max-width: 85%; box-shadow: 0 1px 4px rgba(0,0,0,.08); }
.source-chip { display: inline-block; padding: 3px 10px; border-radius: 20px; background: #eff2ff; color: #4f6ef7; font-size: 11px; margin: 3px; text-decoration: none; }
</style>
""", unsafe_allow_html=True)

# ── API ───────────────────────────────────────────────────────────────────────
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")

def _llm(prompt: str) -> str:
    if not OPENAI_API_KEY:
        return "Tilføj OPENAI_API_KEY i Streamlit secrets."
    r = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        json={
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
        },
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

# ── Hjælpefunktioner ──────────────────────────────────────────────────────────
def strip_html(text: str) -> str:
    entities = {
        "&nbsp;": " ", "&amp;": "&", "&lt;": "<", "&gt;": ">",
        "&oslash;": "ø", "&aelig;": "æ", "&aring;": "å",
        "&Oslash;": "Ø", "&AElig;": "Æ", "&Aring;": "Å",
        "&ndash;": "–", "&mdash;": "—", "&ldquo;": '"', "&rdquo;": '"',
        "&laquo;": "«", "&raquo;": "»", "&bull;": "•", "&hellip;": "…",
    }
    text = re.sub(r"<[^>]+>", " ", text)
    for ent, rep in entities.items():
        text = text.replace(ent, rep)
    text = re.sub(r"&#\d+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def kategoriser(titel: str) -> str:
    t = titel.lower()
    if "lokalplan" in t:
        if "dispensation" in t:        return "Lokalplan – Dispensation"
        if "overensstemmelse" in t:    return "Lokalplan – Overensstemmelse"
        if "vedtagelse" in t:          return "Lokalplan – Vedtagelse"
        return "Lokalplan – Andet"
    if "landzone" in t:             return "Landzone"
    if "strandbeskyttelse" in t:    return "Strandbeskyttelse"
    if "naturbeskyttelse" in t:     return "Naturbeskyttelse"
    if "skovloven" in t or " skov " in t: return "Skovloven"
    if "kystzone" in t or "kystnær" in t: return "Kystbeskyttelse"
    if "fredning" in t:             return "Fredning"
    if "miljøvurdering" in t or "vvm" in t: return "Miljøvurdering"
    if "opsættende virkning" in t:  return "Opsættende virkning"
    if "afvisning" in t:            return "Afvisning"
    return "Andet"


def detect_udfald(titel: str) -> str:
    t = titel.lower()
    if any(k in t for k in ("ophævet", "ugyldig", "ugyldigt", "annulleret",
                             "hjemvisning", "hjemvises")):       return "Afgørelse ugyldig"
    if "medhold" in t:                                           return "Medhold"
    if "stadfæst" in t or "afslag" in t or "ikke medhold" in t: return "Afslag"
    if "afvisning" in t or "afvises" in t:                       return "Afvist"
    return "Ukendt"


def extract_kommune(titel: str) -> str:
    m = re.search(r"([A-ZÆØÅ][a-zæøå]+-?[A-ZÆØÅ]?[a-zæøå]*)\s+Kommunes?", titel)
    return m.group(1) if m else None


def detect_sagsgruppe(titel: str, tekst: str) -> str:
    t = (titel + " " + tekst[:500]).lower()
    if "genoptagelse" in t:    return "Genoptagelse"
    if "opsættende virkning" in t or "afslag på opsættende" in t: return "Opsættende virkning"
    if "afvisning" in t or "afvises" in t or "klageberettiget" in t: return "Afvisning"
    return "Realitetsbehandling"


BADGE = {"Medhold": "badge-medhold", "Afslag": "badge-afslag",
         "Afgørelse ugyldig": "badge-ugyldig", "Afvist": "badge-afvist", "Ukendt": "badge-ukendt"}

# ── Data-loading ──────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Indlæser 4.780 afgørelser…")
def load_data():
    import os, zipfile
    if not os.path.exists("pkn_vidensbase_fuld_tekst.csv"):
        with zipfile.ZipFile("pkn_vidensbase_fuld_tekst.csv.zip") as z:
            z.extractall(".")
    csv.field_size_limit(10_000_000)
    rows = []
    with open("pkn_vidensbase_fuld_tekst.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            tekst = strip_html(row["Tekst"])
            rows.append({
                "Dato":    row["Dato"],
                "Titel":   row["Titel"],
                "Link":    row["Link"],
                "Tekst":   tekst,
                "Excerpt": tekst[:280],
            })
    df = pd.DataFrame(rows)
    df["Dato"]     = pd.to_datetime(df["Dato"], errors="coerce")
    df["År"]       = df["Dato"].dt.year.astype("Int64")
    df["Kategori"]   = df["Titel"].apply(kategoriser)
    df["Udfald"]     = df["Titel"].apply(detect_udfald)
    df["Kommune"]    = df["Titel"].apply(extract_kommune)
    df["Sagsgruppe"] = df.apply(lambda r: detect_sagsgruppe(r["Titel"], r["Tekst"]), axis=1)
    return df


@st.cache_resource(show_spinner="Bygger søgeindeks…")
def build_index(n_rows: int):
    from sklearn.feature_extraction.text import TfidfVectorizer
    df2 = load_data()
    texts = (df2["Titel"] + " " + df2["Tekst"]).tolist()
    vec = TfidfVectorizer(max_features=60_000, ngram_range=(1, 2),
                          min_df=2, sublinear_tf=True)
    mat = vec.fit_transform(texts)
    return vec, mat


def tfidf_søg(query: str, df, vec, mat, sub_idx=None, top_n: int = 30):
    from sklearn.metrics.pairwise import cosine_similarity
    qv = vec.transform([query])
    if sub_idx is not None:
        scores_sub = cosine_similarity(qv, mat[sub_idx]).flatten()
        top_local  = scores_sub.argsort()[-top_n:][::-1]
        top_global = [sub_idx[i] for i in top_local if scores_sub[i] > 0.01]
        result     = df.loc[top_global].copy()
        result["_score"] = [scores_sub[i] for i in top_local if scores_sub[i] > 0.01]
    else:
        scores = cosine_similarity(qv, mat).flatten()
        top    = scores.argsort()[-top_n:][::-1]
        result = df.iloc[top].copy()
        result["_score"] = scores[top]
        result = result[result["_score"] > 0.01]
    return result.reset_index(drop=True)


def gemini_svar(spørgsmål: str, docs: list) -> str:
    if not OPENAI_API_KEY:
        return "Tilføj OPENAI_API_KEY i Streamlit secrets."
    kontekst = "\n\n".join(
        f"[Kilde {i+1}] {pd.Timestamp(d['Dato']).strftime('%d.%m.%Y')} – {d['Titel']}\n{d['Tekst'][:1200]}"
        for i, d in enumerate(docs)
    )
    prompt = f"""Du er en juridisk assistent specialiseret i dansk planlovgivning og PKN-praksis.
Besvar følgende spørgsmål KUN baseret på de vedlagte PKN-afgørelser.
Henvis til [Kilde X] når du bruger information fra en bestemt afgørelse.
Svar på dansk, præcist og struktureret med afsnit hvis relevant.

SPØRGSMÅL: {spørgsmål}

AFGØRELSER:
{kontekst}

SVAR:"""
    return _llm(prompt)


def gemini_resumé(titel: str, tekst: str) -> str:
    if not OPENAI_API_KEY:
        return "Ingen API-nøgle."
    prompt = f"""Lav et kort, struktureret resumé af denne PKN-afgørelse på dansk.
Inkluder: Sagens kerne, Klagenævnets vurdering, Resultat. Max 200 ord.

TITEL: {titel}
TEKST: {tekst[:3000]}

RESUMÉ:"""
    return _llm(prompt)


# ── Session state ─────────────────────────────────────────────────────────────
if "chat_historik"   not in st.session_state: st.session_state.chat_historik   = []
if "valgt_afgørelse" not in st.session_state: st.session_state.valgt_afgørelse = None

# ── Indlæs data ───────────────────────────────────────────────────────────────
df       = load_data()
vec, mat = build_index(len(df))

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚖️ PKN Indsigt")
    st.caption("Planklagenævnets afgørelsesdatabase")
    st.markdown("---")

    søg_input   = st.text_input("🔍 Søg i afgørelser", placeholder="f.eks. terrasse lokalplan…")
    valgte_kats    = st.multiselect("Kategori", sorted(df["Kategori"].unique()))
    sagsgruppe_valg = st.multiselect("Sagsgruppe", ["Realitetsbehandling", "Afvisning", "Genoptagelse", "Opsættende virkning"])
    år_min, år_max = int(df["År"].min()), int(df["År"].max())
    år_range       = st.slider("Årsinterval", år_min, år_max, (år_min, år_max))
    udfald_valg    = st.multiselect("Udfald", ["Medhold", "Afslag", "Afgørelse ugyldig", "Afvist", "Ukendt"])

    st.markdown("---")
    st.markdown(f"**{len(df):,}** afgørelser · {år_min}–{år_max}")
    st.markdown(f"Opdateret: {df['Dato'].max().strftime('%d.%m.%Y')}")

# ── Filtrering ────────────────────────────────────────────────────────────────
mask = (df["År"] >= år_range[0]) & (df["År"] <= år_range[1])
if valgte_kats:     mask &= df["Kategori"].isin(valgte_kats)
if sagsgruppe_valg: mask &= df["Sagsgruppe"].isin(sagsgruppe_valg)
if udfald_valg:     mask &= df["Udfald"].isin(udfald_valg)
df_filter = df[mask].reset_index(drop=True)
sub_idx   = df[mask].index.tolist()

if søg_input.strip():
    df_vis = tfidf_søg(søg_input, df, vec, mat, sub_idx=sub_idx, top_n=25)
else:
    df_vis = df_filter.sort_values("Dato", ascending=False).head(25)

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 – AFGØRELSER
# ════════════════════════════════════════════════════════════════════════════
tab_søg, tab_stat, tab_ai = st.tabs(["🔍 Afgørelser", "📊 Statistik", "🤖 AI Assistent"])

with tab_søg:

    # Detaljevisning
    if st.session_state.valgt_afgørelse is not None:
        row = st.session_state.valgt_afgørelse
        if st.button("← Tilbage"):
            st.session_state.valgt_afgørelse = None
            st.rerun()

        badge_cls = BADGE.get(row["Udfald"], "badge-ukendt")
        dato_str  = pd.Timestamp(row["Dato"]).strftime("%d.%m.%Y")
        st.markdown(f"# {row['Titel']}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Dato",       dato_str)
        c2.metric("Kategori",   row["Kategori"])
        c3.metric("Sagsgruppe", row.get("Sagsgruppe", "–"))
        c4.metric("Udfald",     row["Udfald"])
        c5.metric("Kommune",    row["Kommune"] or "–")
        st.markdown(f"[🔗 Åbn original afgørelse på PKN's hjemmeside]({row['Link']})")
        st.divider()

        col_tekst, col_ai = st.columns([3, 2])
        with col_tekst:
            with st.expander("📄 Fuld afgørelsestekst", expanded=True):
                st.markdown(row["Tekst"])
        with col_ai:
            st.markdown("### ✨ AI-resumé")
            if st.button("Generer AI-resumé"):
                with st.spinner("Resumerer…"):
                    try:
                        st.session_state._resumé = gemini_resumé(row["Titel"], row["Tekst"])
                    except Exception as e:
                        st.session_state._resumé = f"Fejl: {e}"
            if "_resumé" in st.session_state:
                st.info(st.session_state._resumé)

    else:
        total_filtreret = len(df_filter)
        hits  = len(df_vis)
        if søg_input:
            label = f"**{hits}** resultater for \"{søg_input}\" (ud af {total_filtreret:,} filtrerede)"
        else:
            label = f"Viser {hits} af **{total_filtreret:,}** afgørelser (nyeste først)"
        st.markdown(label)

        if hits == 0:
            st.warning("Ingen resultater – prøv andre søgeord eller filtre.")
        else:
            for _, row in df_vis.iterrows():
                badge_cls = BADGE.get(row["Udfald"], "badge-ukendt")
                dato_str  = row["Dato"].strftime("%d.%m.%Y") if pd.notna(row["Dato"]) else "–"
                st.markdown(f"""
<div class="pkn-card">
  <div class="pkn-card-meta">{dato_str} &nbsp;·&nbsp; {row['Kategori']} &nbsp;·&nbsp; {row['Sagsgruppe']}
    &nbsp;<span class="pkn-badge {badge_cls}">{row['Udfald']}</span>
  </div>
  <div class="pkn-card-title">{row['Titel']}</div>
  <div class="pkn-card-excerpt">{row['Excerpt']}…</div>
</div>""", unsafe_allow_html=True)

                c1, c2 = st.columns([1, 6])
                with c1:
                    if st.button("Læs mere", key=f"btn_{row['Link'][-20:]}"):
                        st.session_state.valgt_afgørelse = row.to_dict()
                        if "_resumé" in st.session_state:
                            del st.session_state["_resumé"]
                        st.rerun()
                with c2:
                    st.markdown(f"[Åbn original ↗]({row['Link']})")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 – STATISTIK
# ════════════════════════════════════════════════════════════════════════════
with tab_stat:
    d = df_filter

    # KPI
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{len(d):,}</div>'
                    f'<div class="stat-label">Afgørelser</div></div>', unsafe_allow_html=True)
    with k2:
        pct = (d["Udfald"] == "Medhold").mean() * 100
        st.markdown(f'<div class="stat-card"><div class="stat-number">{pct:.0f}%</div>'
                    f'<div class="stat-label">Medhold-rate</div></div>', unsafe_allow_html=True)
    with k3:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kommune"].nunique()}</div>'
                    f'<div class="stat-label">Kommuner</div></div>', unsafe_allow_html=True)
    with k4:
        st.markdown(f'<div class="stat-card"><div class="stat-number">{d["Kategori"].nunique()}</div>'
                    f'<div class="stat-label">Kategorier</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("#### Afgørelser per år")
        år_df = d.groupby("År").size().reset_index(name="Antal")
        fig = px.bar(år_df, x="År", y="Antal", color_discrete_sequence=["#4f6ef7"])
        fig.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.markdown("#### Fordeling på kategori")
        kat_df = d.groupby("Kategori").size().reset_index(name="Antal")
        fig2 = px.pie(kat_df, values="Antal", names="Kategori",
                      color_discrete_sequence=px.colors.qualitative.Set3, hole=0.4)
        fig2.update_layout(margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig2, use_container_width=True)

    col_ll, col_rr = st.columns(2)

    with col_ll:
        st.markdown("#### Udfald over tid")
        udfald_år = d.groupby(["År","Udfald"]).size().reset_index(name="Antal")
        farver = {"Medhold":"#10b981","Afslag":"#ef4444","Afgørelse ugyldig":"#8b5cf6","Afvist":"#f59e0b","Ukendt":"#94a3b8"}
        fig3 = px.bar(udfald_år, x="År", y="Antal", color="Udfald",
                      color_discrete_map=farver, barmode="stack")
        fig3.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig3, use_container_width=True)

    with col_rr:
        st.markdown("#### Top 15 kommuner")
        kom_df = (d.dropna(subset=["Kommune"]).groupby("Kommune").size()
                   .reset_index(name="Sager").sort_values("Sager",ascending=True).tail(15))
        fig4 = px.bar(kom_df, x="Sager", y="Kommune", orientation="h",
                      color_discrete_sequence=["#4f6ef7"])
        fig4.update_layout(plot_bgcolor="white", paper_bgcolor="white", margin=dict(t=10,b=10,l=10,r=10))
        st.plotly_chart(fig4, use_container_width=True)

    st.markdown("#### Medhold-rate per kategori")
    mr = (d.groupby("Kategori")
           .apply(lambda x: pd.Series({
               "Sager": len(x),
               "Medhold_%": round((x["Udfald"]=="Medhold").mean()*100, 1)
           }), include_groups=False)
           .reset_index()
           .sort_values("Medhold_%", ascending=True))
    fig5 = px.bar(mr, x="Medhold_%", y="Kategori", orientation="h",
                  color="Medhold_%", color_continuous_scale=["#fee2e2","#10b981"],
                  hover_data={"Sager": True},
                  labels={"Medhold_%": "Medhold (%)"})
    fig5.update_layout(plot_bgcolor="white", paper_bgcolor="white",
                       coloraxis_showscale=False, margin=dict(t=10,b=10,l=10,r=10))
    st.plotly_chart(fig5, use_container_width=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 – AI ASSISTENT
# ════════════════════════════════════════════════════════════════════════════
with tab_ai:
    st.markdown("### 🤖 Spørg til PKN-praksis")
    st.markdown("AI'en søger i alle **4.780 afgørelser** og svarer med kildehenvisninger – ingen embedding-API nødvendig.")

    if not OPENAI_API_KEY:
        st.error("Tilføj `OPENAI_API_KEY` i Streamlit secrets.")
    else:
        # Forslagsknapper
        forslag = [
            "Hvad lægger PKN vægt på ved vurdering af terrasse?",
            "Hvornår gives der medhold i landzonesager?",
            "Hvilken praksis er der for strandbeskyttelseslinjen?",
            "Hvad kræves for dispensation fra lokalplan?",
        ]
        cols = st.columns(4)
        for i, f in enumerate(forslag):
            if cols[i].button(f, use_container_width=True, key=f"fs_{i}"):
                st.session_state.chat_historik.append({"rolle": "bruger", "tekst": f})
                with st.spinner("Søger og genererer svar…"):
                    hits_ai = tfidf_søg(f, df, vec, mat, top_n=8)
                    try:
                        svar = gemini_svar(f, hits_ai.to_dict("records"))
                    except Exception as e:
                        svar = f"Fejl ved Gemini API: {e}"
                st.session_state.chat_historik.append(
                    {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
                st.rerun()

        st.divider()

        # Historik
        for msg in st.session_state.chat_historik:
            if msg["rolle"] == "bruger":
                st.markdown(f'<div class="chat-user">{msg["tekst"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-assistant">{msg["tekst"]}</div>', unsafe_allow_html=True)
                if msg.get("kilder"):
                    chips = " ".join(
                        f'<a class="source-chip" href="{k["Link"]}" target="_blank">[{i+1}] {k["Titel"][:55]}…</a>'
                        for i, k in enumerate(msg["kilder"][:5])
                    )
                    st.markdown(f"**Kilder:** {chips}", unsafe_allow_html=True)

        # Input-form
        with st.form("chat_form", clear_on_submit=True):
            spørgsmål = st.text_area("Dit spørgsmål", height=80,
                                      placeholder="Hvad er PKN's praksis for…?")
            c1, c2 = st.columns([3, 1])
            send = c1.form_submit_button("Send ➤", use_container_width=True, type="primary")
            ryd  = c2.form_submit_button("Ryd chat", use_container_width=True)

        if ryd:
            st.session_state.chat_historik = []
            st.rerun()

        if send and spørgsmål.strip():
            st.session_state.chat_historik.append({"rolle": "bruger", "tekst": spørgsmål})
            with st.spinner("Søger og genererer svar…"):
                hits_ai = tfidf_søg(spørgsmål, df, vec, mat, top_n=8)
                try:
                    svar = gemini_svar(spørgsmål, hits_ai.to_dict("records"))
                except Exception as e:
                    svar = f"Fejl ved Gemini API: {e}"
            st.session_state.chat_historik.append(
                {"rolle": "assistent", "tekst": svar, "kilder": hits_ai.to_dict("records")})
            st.rerun()

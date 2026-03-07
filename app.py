import streamlit as st
import pandas as pd
import os
from google import genai
from google.genai import types

# RAG Biblioteker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_core.embeddings import Embeddings

# --- 1. KONFIGURATION & DESIGN ---
st.set_page_config(page_title="🏛️ PKN VIDENSBASE", layout="wide", initial_sidebar_state="expanded")

if "GEMINI_API_KEY" not in st.secrets:
    st.error("⚠️ API-nøgle mangler i Streamlit secrets!")
    st.stop()

client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. DATA INDLÆSNING ---
@st.cache_data
def load_data():
    for filename in ['pkn_vidensbase_fuld_tekst.csv.zip', 'pkn_vidensbase_fuld_tekst.csv']:
        if os.path.exists(filename):
            compression = 'zip' if filename.endswith('.zip') else None
            df = pd.read_csv(filename, compression=compression)
            df['Dato'] = pd.to_datetime(df['Dato'], errors='coerce').dt.date
            return df.sort_values(by='Dato', ascending=False)
    st.warning("⚠️ Datafil ikke fundet. Læg 'pkn_vidensbase_fuld_tekst.csv.zip' i samme mappe som app.py")
    return pd.DataFrame({'Titel': [], 'Dato': [], 'Tekst': []})

df_raw = load_data()

# --- 3. EMBEDDING MODEL (ny google-genai SDK, bruger v1 API) ---
class GeminiEmbeddings(Embeddings):
    def __init__(self, model="text-embedding-004"):
        self.model = model

    def embed_documents(self, texts):
        embeddings = []
        for text in texts:
            response = client.models.embed_content(
                model=self.model,
                contents=text
            )
            embeddings.append(response.embeddings[0].values)
        return embeddings

    def embed_query(self, text):
        response = client.models.embed_content(
            model=self.model,
            contents=text
        )
        return response.embeddings[0].values

@st.cache_resource
def get_embedding_model():
    errors = []
    for model_name in ["text-embedding-004", "embedding-001"]:
        try:
            emb = GeminiEmbeddings(model=model_name)
            emb.embed_query("test")
            return emb, model_name, None
        except Exception as e:
            errors.append(f"{model_name}: {e}")
            continue
    return None, None, " | ".join(errors)

# --- 4. SIDEBAR: FILTRE (TRAGTEN) ---
st.sidebar.title("🔍 Plan-Filter")

fritekst_soegning = st.sidebar.text_input(
    "Søg specifikt efter emne (f.eks. 'officialprincippet'):", ""
)

type_valg = st.sidebar.multiselect(
    "Afgørelsestype:",
    ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Screeningsafgørelse", "Miljørapport"],
    default=["Lokalplan"]
)

sags_fokus = st.sidebar.radio(
    "Sagsgruppe:",
    ["Realitetsbehandling (Jura)", "Afvisninger", "Genoptagelser", "Alt"]
)

udfald_medhold = st.sidebar.toggle("Vis kun sager med MEDHOLD")

# --- ANVEND FILTRE (TRAGTEN) ---
df_filtered = df_raw.copy()

if fritekst_soegning:
    df_filtered = df_filtered[
        df_filtered['Tekst'].str.contains(fritekst_soegning, case=False, na=False)
    ]

if type_valg:
    plan_typer = [t for t in type_valg if t in ["Lokalplan", "Kommuneplantillæg", "Kommuneplan"]]
    special_typer = [t for t in type_valg if t in ["Screeningsafgørelse", "Miljørapport"]]
    masks = []

    if plan_typer:
        pattern = '|'.join(plan_typer)
        plan_mask = (
            df_filtered['Titel'].str.contains(pattern, case=False, na=False) &
            df_filtered['Titel'].str.contains('endelige vedtagelse', case=False, na=False) &
            ~df_filtered['Titel'].str.contains('Dispensation', case=False, na=False)
        )
        masks.append(plan_mask)

    if "Screeningsafgørelse" in special_typer:
        masks.append(df_filtered['Titel'].str.contains('screeningsafgørelse om, at', case=False, na=False))

    if "Miljørapport" in special_typer:
        masks.append(df_filtered['Titel'].str.contains('med tilhørende miljørapport', case=False, na=False))

    if masks:
        combined_mask = masks[0]
        for m in masks[1:]:
            combined_mask = combined_mask | m
        df_filtered = df_filtered[combined_mask]

if sags_fokus == "Realitetsbehandling (Jura)":
    df_filtered = df_filtered[
        ~df_filtered['Titel'].str.contains("Afvisning|Genoptagelse", case=False, na=False)
    ]
elif sags_fokus == "Afvisninger":
    df_filtered = df_filtered[
        df_filtered['Titel'].str.contains("Afvisning", case=False, na=False)
    ]
elif sags_fokus == "Genoptagelser":
    df_filtered = df_filtered[
        df_filtered['Titel'].str.contains("Genoptagelse", case=False, na=False)
    ]

if udfald_medhold:
    df_filtered = df_filtered[
        df_filtered['Tekst'].str.contains("medhold", case=False, na=False)
    ]

st.sidebar.success(f"Viser {len(df_filtered)} afgørelser efter filtrering.")

# --- 5. HOVEDLAYOUT ---
st.title("🏛️ PKN Smart Assistent")

tab1, tab2 = st.tabs(["🤖 Chat med Praksis", "📄 Nærlæs Afgørelse"])

# --- FANE 1: AI CHAT (RAG) ---
with tab1:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Spørg ind til praksis..."):
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Gennemsøger praksis (RAG)..."):
                try:
                    if df_filtered.empty:
                        st.warning("Ingen sager matcher dine filtre. Juster filtrene i sidebaren.")
                    else:
                        all_text_to_index = ""
                        for _, row in df_filtered.head(500).iterrows():
                            all_text_to_index += f"SAG: {row['Titel']}\n{row['Tekst']}\n\n"

                        text_splitter = RecursiveCharacterTextSplitter(
                            chunk_size=4000, chunk_overlap=400
                        )
                        chunks = text_splitter.split_text(all_text_to_index)

                        embeddings, model_used, emb_error = get_embedding_model()
                        if embeddings is None:
                            st.error(f"Embedding fejl: {emb_error}")
                            st.stop()

                        vectorstore = FAISS.from_texts(chunks, embeddings)

                        k = min(60, len(chunks))
                        relevant_chunks = vectorstore.similarity_search(prompt, k=k)
                        kontekst = "\n---\n".join([c.page_content for c in relevant_chunks])

                        system_prompt = (
                            "Du er en juridisk ekspert i dansk planret og specialist i Planklagenævnets praksis. "
                            "Nedenfor er de mest relevante uddrag fra afgørelserne.\n\n"
                            f"PRAKSIS-UDDRAG:\n{kontekst}\n\n"
                            "Basér dit svar udelukkende på disse uddrag. "
                            "Citér præcise formuleringer fra afgørelserne, da retlige regler altid skal stå ordret. "
                            "Nævn de sags-titler du trækker på.\n\n"
                            f"SPØRGSMÅL: {prompt}"
                        )

                        response = client.models.generate_content(
                            model="gemini-2.0-flash",
                            contents=system_prompt
                        )
                        answer = response.text
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})

                except Exception as e:
                    st.error(f"Fejl: {e}")

# --- FANE 2: DOKUMENT LÆSER ---
with tab2:
    if df_filtered.empty:
        st.info("Ingen sager matcher dine filtre. Juster filtrene i sidebaren.")
    else:
        sag_titler = ["Vælg en sag..."] + df_filtered['Titel'].tolist()
        valgt_sag = st.selectbox("Læs sag:", sag_titler)

        if valgt_sag != "Vælg en sag...":
            data = df_filtered[df_filtered['Titel'] == valgt_sag].iloc[0]
            st.markdown(f"### {data['Titel']}")
            st.markdown(f"**Dato:** {data['Dato']}")
            st.markdown(
                f"<div style='height:600px; overflow-y:scroll; "
                f"border:1px solid #ddd; padding:1rem; border-radius:4px;'>"
                f"{data['Tekst']}</div>",
                unsafe_allow_html=True
            )

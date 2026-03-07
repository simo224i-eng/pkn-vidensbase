import streamlit as st
import pandas as pd
import google.generativeai as genai
import os

# RAG Biblioteker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# --- 1. KONFIGURATION & DESIGN ---
st.set_page_config(page_title="🏛️ PKN VIDENSBASE", layout="wide", initial_sidebar_state="expanded")

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("⚠️ API-nøgle mangler!")

if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. DATA INDLÆSNING ---
@st.cache_data
def load_data():
    if os.path.exists('pkn_vidensbase_fuld_tekst.csv.zip'):
        df = pd.read_csv('pkn_vidensbase_fuld_tekst.csv.zip', compression='zip')
        df['Dato'] = pd.to_datetime(df['Dato'], errors='coerce').dt.date
        return df.sort_values(by='Dato', ascending=False)
    return pd.DataFrame({'Titel': [], 'Dato': [], 'Tekst': []})

df_raw = load_data()

# --- 3. SIDEBAR: FILTRE (TRAGTEN) ---
st.sidebar.title("🔍 Plan-Filter")

# Fritekst-søgefelt (bruges nu også til at give RAG-motoren retning)
fritekst_soegning = st.sidebar.text_input("Søg specifikt efter emne (f.eks. 'officialprincippet'):", "")

type_valg = st.sidebar.multiselect("Afgørelsestype:", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan"], default=["Lokalplan"])
sags_fokus = st.sidebar.radio("Sagsgruppe:", ["Realitetsbehandling (Jura)", "Afvisninger", "Genoptagelser", "Alt"])
udfald_medhold = st.sidebar.toggle("Vis kun sager med MEDHOLD")

# ANVEND FILTRE (TRAGT 1)
df_filtered = df_raw.copy()

if fritekst_soegning:
    df_filtered = df_filtered[df_filtered['Tekst'].str.contains(fritekst_soegning, case=False, na=False)]

if type_valg:
    pattern = '|'.join(type_valg)
    df_filtered = df_filtered[df_filtered['Titel'].str.contains(pattern, case=False, na=False)]
    df_filtered = df_filtered[df_filtered['Titel'].str.contains('endelige vedtagelse', case=False, na=False)]

if sags_fokus == "Realitetsbehandling (Jura)":
    df_filtered = df_filtered[~df_filtered['Titel'].str.contains("Afvisning|Genoptagelse", case=False, na=False)]
# ... (resten af dine filtre)

st.sidebar.success(f"Viser {len(df_filtered)} afgørelser efter filtrering.")

# --- 4. HOVEDLAYOUT ---
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
            with st.spinner("Genemsøger praksis (RAG)..."):
                try:
                    # RAG LOGIK: Find bidder kun fra de filtrerede sager
                    all_text_to_index = ""
                    # Vi begrænser de sager vi indekserer til de 200 nyeste i filteret for at holde hastigheden oppe
                    for _, row in df_filtered.head(200).iterrows():
                        all_text_to_index += f"SAG: {row['Titel']}\n{row['Tekst']}\n\n"
                    
                    # 1. Chunking (Smart-Saks med 4000 tegn)
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=400)
                    chunks = text_splitter.split_text(all_text_to_index)
                    
                    # 2. Embeddings & Søgning
                    embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004"), google_api_key=st.secrets["GEMINI_API_KEY"]
                    vectorstore = FAISS.from_texts(chunks, embeddings)
                    
                    # 3. Hent de 60 vigtigste bidder
                    relevant_chunks = vectorstore.similarity_search(prompt, k=60)
                    kontekst = "\n---\n".join([c.page_content for c in relevant_chunks])
                    
                    # 4. Generer svar
                    model = genai.GenerativeModel('gemini-1.5-pro') # Eller gemini-3.1-pro-preview hvis tilgængelig
                    system_prompt = f"""Du er en juridisk ekspert. Her er de 60 mest relevante bidder fra praksis:
                    {kontekst}
                    
                    Svar på spørgsmålet baseret på disse bidder. Da retlige regler altid står ordret, skal du kigge efter præcise formuleringer som f.eks. 'officialprincippet'. 
                    Nævn de titler du bruger."""
                    
                    response = model.generate_content(system_prompt + "\n\nSpørgsmål: " + prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Fejl: {e}")

# --- FANE 2: DOKUMENT LÆSER ---
with tab2:
    if not df_filtered.empty:
        sag_titler = ["Vælg en sag..."] + df_filtered['Titel'].tolist()
        valgt_sag = st.selectbox("Læs sag:", sag_titler)
        if valgt_sag != "Vælg en sag...":
            data = df_filtered[df_filtered['Titel'] == valgt_sag].iloc[0]
            st.markdown(f"### {data['Titel']}")
            st.markdown(f"<div style='height: 600px; overflow-y: scroll;'>{data['Tekst']}</div>", unsafe_allow_html=True)

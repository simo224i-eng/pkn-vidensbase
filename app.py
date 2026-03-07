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
    st.error("⚠️ API-nøgle mangler i Streamlit Secrets!")

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

# --- 3. SIDEBAR: FILTRE ---
st.sidebar.title("🔍 Plan-Filter")

fritekst_soegning = st.sidebar.text_input("Søg specifikt efter emne:", "")
type_valg = st.sidebar.multiselect("Afgørelsestype:", ["Lokalplan", "Kommuneplantillæg", "Kommuneplan"], default=["Lokalplan"])
sags_fokus = st.sidebar.radio("Sagsgruppe:", ["Realitetsbehandling (Jura)", "Afvisninger", "Genoptagelser", "Alt"])
udfald_medhold = st.sidebar.toggle("Vis kun sager med MEDHOLD")

df_filtered = df_raw.copy()

if fritekst_soegning:
    df_filtered = df_filtered[df_filtered['Tekst'].str.contains(fritekst_soegning, case=False, na=False)]

if type_valg:
    pattern = '|'.join(type_valg)
    df_filtered = df_filtered[df_filtered['Titel'].str.contains(pattern, case=False, na=False)]
    df_filtered = df_filtered[df_filtered['Titel'].str.contains('endelige vedtagelse', case=False, na=False)]

if sags_fokus == "Realitetsbehandling (Jura)":
    df_filtered = df_filtered[~df_filtered['Titel'].str.contains("Afvisning|Genoptagelse", case=False, na=False)]

st.sidebar.success(f"Viser {len(df_filtered)} afgørelser efter filtrering.")

# --- 4. HOVEDLAYOUT ---
st.title("🏛️ PKN Smart Assistent")
tab1, tab2 = st.tabs(["🤖 Chat med Praksis", "📄 Nærlæs Afgørelse"])

# --- FANE 1: AI CHAT (RAG) ---
with tab1:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt :=

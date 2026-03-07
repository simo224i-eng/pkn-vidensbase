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

# Her er Screeningsafgørelse nu en del af grupperne
type_valg = st.sidebar.multiselect(
    "Afgørelsestype:", 
    ["Lokalplan", "Kommuneplantillæg", "Kommuneplan", "Screeningsafgørelse"], 
    default=["Lokalplan"]
)

sags_fokus = st.sidebar.radio("Sagsgruppe:", ["Realitetsbehandling (Jura)", "Afvisninger", "Genoptagelser", "Alt"])

st.sidebar.markdown("---")
vis_miljoe = st.sidebar.toggle("Kun sager med Miljørapport")
udfald_medhold = st.sidebar.toggle("Vis kun sager med MEDHOLD")

# --- ANVEND FILTRE ---
df_filtered = df_raw.copy()

if fritekst_soegning:
    df_filtered = df_filtered[df_filtered['Tekst'].str.contains(fritekst_soegning, case=False, na=False)]

if type_valg:
    mask = pd.Series(False, index=df_filtered.index)
    for t in type_valg:
        if t == "Screeningsafgørelse":
            mask |= df_filtered['Titel'].str.contains("screeningsafgørelse om, at", case=False, na=False)
        else:
            # De tre standardtyper kræver 'endelige vedtagelse' og ingen 'Dispensation'
            type_mask = df_filtered['Titel'].str.contains(t, case=False, na=False)
            type_mask &= df_filtered['Titel'].str.contains('endelige vedtagelse', case=False, na=False)
            type_mask &= ~df_filtered['Titel'].str.contains('Dispensation', case=False, na=False)
            mask |= type_mask
    df_filtered = df_filtered[mask]

if sags_fokus == "Realitetsbehandling (Jura)":
    df_filtered = df_filtered[~df_filtered['Titel'].str.contains("Afvisning|Genoptagelse|Dispensation", case=False, na=False)]

if vis_miljoe:
    df_filtered = df_filtered[df_filtered['Titel'].str.contains("med tilhørende miljørapport", case=False, na=False)]

if udfald_medhold:
    df_filtered = df_filtered[df_filtered['Tekst'].str.contains("ophæver|hjemviser", case=False, na=False)]

st.sidebar.success(f"Viser {len(df_filtered)} afgørelser efter filtrering.")

# --- 4. HOVEDLAYOUT ---
st.title("🏛️ PKN Smart Assistent")
tab1, tab2 = st.tabs(["🤖 Chat med Praksis", "📄 Nærlæs Afgørelse"])

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
                    all_text_to_index = ""
                    for _, row in df_filtered.head(100).iterrows():
                        all_text_to_index += f"SAG: {row['Titel']}\n{row['Tekst']}\n\n"
                    
                    text_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=400)
                    chunks = text_splitter.split_text(all_text_to_index)
                    
                    embeddings = GoogleGenerativeAIEmbeddings(
                        model="models/text-embedding-004", 
                        google_api_key=st.secrets["GEMINI_API_KEY"]
                    )
                    vectorstore = FAISS.from_texts(chunks, embeddings)
                    
                    relevant_chunks = vectorstore.similarity_search(prompt, k=40)
                    kontekst = "\n---\n".join([c.page_content for c in relevant_chunks])
                    
                    # DIN BETALTE TOPMODEL 2.0 PRO
                    model = genai.GenerativeModel('gemini-2.0-pro')
                    system_prompt = f"Du er en juridisk ekspert. Svar på dansk baseret på disse sager:\n\n{kontekst}\n\nCitér titlerne på de sager du bruger."
                    
                    response = model.generate_content(system_prompt + "\n\nSpørgsmål: " + prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Fejl i søgningen: {e}")

with tab2:
    if not df_filtered.empty:
        sag_titler = ["Vælg en sag..."] + df_filtered['Titel'].tolist()
        valgt_sag = st.selectbox("Læs sag:", sag_titler)
        if valgt_sag != "Vælg en sag...":
            data = df_filtered[df_filtered['Titel'] == valgt_sag].iloc[0]
            st.markdown(f"### {data['Titel']}")
            # HTML boks skrevet robust for at undgå SyntaxError
            html_content = f"<div style='height: 600px; overflow-y: scroll;'>{data['Tekst']}</div>"
            st.markdown(html_content, unsafe_allow_html=True)

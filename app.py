import streamlit as st
import pandas as pd
import google.generativeai as genai
import os

# --- 1. KONFIGURATION & DESIGN ---
st.set_page_config(page_title="🏛️ PKN VIDENSBASE", layout="wide", initial_sidebar_state="expanded")

# Hent API nøgle
if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
else:
    st.error("⚠️ API-nøgle mangler i .streamlit/secrets.toml!")

# Initialiser Chat-historik i session state, så den overlever, når vi klikker rundt
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- 2. DATA INDLÆSNING ---
@st.cache_data
def load_data():
    # Sørg for at filnavnet matcher din rigtige fil
    if os.path.exists('pkn_vidensbase_fuld_tekst.csv.zip'):
        df = pd.read_csv('pkn_vidensbase_fuld_tekst.csv.zip', compression='zip')
        df['Dato'] = pd.to_datetime(df['Dato'], errors='coerce').dt.date
        return df.sort_values(by='Dato', ascending=False)
    # Mock data hvis filen ikke findes endnu
    data = {
        'Dato': ['2026-01-10', '2025-11-20', '2025-09-05', '2025-08-15'],
        'Titel': ['Ophævelse af Lokalplan 12B', 'Afvisning af Genoptagelse for Kommuneplan', 'Realitetsbehandling af Kommuneplantillæg 4', 'Medhold i klage over Lokalplan X'],
        'Tekst': ['Fuld tekst for sag 1...', 'Fuld tekst for sag 2...', 'Fuld tekst for sag 3...', 'Fuld tekst for sag 4...']
    }
    return pd.DataFrame(data)

df_raw = load_data()

# --- 3. SIDEBAR: FILTRE (TRAGTEN) ---
st.sidebar.title("🔍 Plan-Filter")
st.sidebar.markdown("Filtrer din søgning inden du spørger AI'en.")

# Type-vælger
type_valg = st.sidebar.multiselect(
    "Afgørelsestype:",
    ["Lokalplan", "Kommuneplantillæg", "Kommuneplan"],
    default=["Lokalplan"]
)

# Juridisk filter
sags_fokus = st.sidebar.radio(
    "Sagsgruppe:",
    ["Realitetsbehandling (Jura)", "Afvisninger", "Genoptagelser", "Alt"]
)

# Udfald
udfald_medhold = st.sidebar.toggle("Vis kun sager med MEDHOLD")

# Anvend filtre
df_filtered = df_raw.copy()

if type_valg:
    pattern = '|'.join(type_valg)
    df_filtered = df_filtered[df_filtered['Titel'].str.contains(pattern, case=False, na=False)]
    # DIN NYE KYNISKE REGEL: Skal indeholde 'endelige vedtagelse' for at luge dispensationer ud!
    df_filtered = df_filtered[df_filtered['Titel'].str.contains('endelige vedtagelse', case=False, na=False)]

if sags_fokus == "Realitetsbehandling (Jura)":
    df_filtered = df_filtered[~df_filtered['Titel'].str.contains("Afvisning|Genoptagelse", case=False, na=False)]
elif sags_fokus == "Afvisninger":
    df_filtered = df_filtered[df_filtered['Titel'].str.contains("Afvisning", case=False, na=False)]
elif sags_fokus == "Genoptagelser":
    df_filtered = df_filtered[df_filtered['Titel'].str.contains("Genoptagelse", case=False, na=False)]

if udfald_medhold:
    # Simpel logik baseret på titel-ord (kan justeres)
    df_filtered = df_filtered[df_filtered['Titel'].str.contains("ophæve|hjemvise|ændre|medhold", case=False, na=False)]

st.sidebar.success(f"Viser {len(df_filtered)} afgørelser efter filtrering.")


# --- 4. HOVEDLAYOUT MED TABS (Faneblade) ---
st.title("🏛️ PKN Smart Assistent")

# Opretter to faneblade i stedet for kolonner, så det er meget nemmere at læse!
tab1, tab2 = st.tabs(["🤖 Chat med Praksis", "📄 Nærlæs Afgørelse"])

# --- FANE 1: AI CHATBOT ---
with tab1:
    st.write("Spørg ind til de filtrerede sager. Assistenten søger kun i de sager, du har valgt i venstre menu.")
    
    # Vis tidligere beskeder
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Chat Input
    if prompt := st.chat_input("F.eks. 'Hvad var den hyppigste grund til at ophæve lokalplaner i disse sager?'"):
        
        # 1. Vis brugerens besked
        with st.chat_message("user"):
            st.markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # 2. Forbered kontekst (Søger i de filtrerede sager)
        # For at undgå at crashe AI'en med 5000 sager, tager vi max de øverste 15 sager.
        max_sager_til_ai = 15 
        df_ai_context = df_filtered.head(max_sager_til_ai)
        
        kontekst_tekst = ""
        for index, row in df_ai_context.iterrows():
            kontekst_tekst += f"Sag: {row['Titel']}\nDato: {row['Dato']}\nTekst-uddrag: {str(row['Tekst'])[:1500]}...\n\n"
            
        system_prompt = f"""Du er en knivskarp juridisk ekspert, der rådgiver om Planklagenævnets praksis.
        Brugeren har stillet et spørgsmål, og du skal basere dit svar PÅFØLGENDE UDVALGTE SAGER:
        {kontekst_tekst}
        
        Instrukser:
        - Svar kun ud fra de sager, der er givet i konteksten.
        - Hvis du bruger en sag, så nævn dens præcise 'Titel' i dit svar, så brugeren kan finde den.
        - Hvis spørgsmålet ikke kan besvares ud fra sagerne, så sig det direkte."""

        # 3. Hent svar fra Gemini
        with st.chat_message("assistant"):
            with st.spinner("Gennemgår praksis..."):
                try:
                    model = genai.GenerativeModel('gemini-3.1-pro-preview')
                    response = model.generate_content(system_prompt + "\n\nSpørgsmål: " + prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Der opstod en fejl med AI'en: {e}")

# --- FANE 2: DOKUMENT LÆSER ---
with tab2:
    if df_filtered.empty:
        st.info("Ingen sager fundet med de valgte filtre.")
    else:
        # Vælger til at læse sagen
        sag_titler = ["Vælg en sag at læse..."] + df_filtered['Titel'].tolist()
        valgt_sag = st.selectbox("Vælg en sag fra dine filtrerede resultater:", sag_titler)
        
        if valgt_sag != "Vælg en sag at læse...":
            sag_data = df_filtered[df_filtered['Titel'] == valgt_sag].iloc[0]
            
            with st.container(border=True):
                # FIKSET FEJL: Har fjernet ['Kommune'] så den ikke crasher!
                st.markdown(f"**Dato:** {sag_data['Dato']}")
                st.markdown(f"### {sag_data['Titel']}")
                st.divider()
                
                # Viser teksten med scroll-bar (nu hvor vi har fuld bredde, kan vi gøre den lidt højere)
                st.markdown(f"<div style='height: 800px; overflow-y: scroll; padding-right:10px;'>{sag_data['Tekst']}</div>", unsafe_allow_html=True)
        else:
            st.write("Vælg en sag i rullemenuen for at læse den i sin fulde længde her.")
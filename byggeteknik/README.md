# Børge — Byggeteknisk flashcards til ejerskifteforsikring

En selvstændig Streamlit-app, der hjælper **jurister med at lære byggeteknikken
bag ejerskifteforsikring**: mangeltyper, skadesmekanismer, fagudtryk — og hvorfor
det betyder noget for dækningen.

Hvor **Ejnar** lader dig *slå op* i Ankenævnet for Forsikrings ~5.600 kendelser,
lader **Børge** dig *terpe stoffet* med klassiske vend-kort (flashcards).

> **Afgrænsning:** El- og VVS-installationer er bevidst udeladt. Kloak/dræn
> indgår kun for det jord- og bygningstekniske (stikledninger, dræn, terrænfald),
> ikke indvendige installationer.

## Sådan virker det

- **Kurateret ekspertdeck** — 65 håndskrevne kort fordelt på 11 emner. Ingen
  OCR-støj, ingen embeddings, ingen API-nøgler.
- **Vend-kort** — spørgsmål på forsiden, fagligt svar på bagsiden, plus en boks
  *"Hvorfor det betyder noget for dækningen"* der binder byggeteknikken til
  jura'en.
- **Filtre** — vælg emner og niveau (grund / videregående), bland kortene.

## Emner

Grundbegreber & huseftersyn · Fugt & skimmel · Tag & tagdækning · Fundament &
sætninger · Råd, svamp & insekt · Murværk & facade · Vinduer & døre · Vådrum &
badeværelser · Gulve & terrændæk · Bærende konstruktioner · Kloak & dræn.

## Struktur

```
byggeteknik/
├── app.py                  # hele appen (ét selvstændigt vend-kort-UI)
├── data/flashcards.json    # det kuraterede deck (kategorier + kort)
├── requirements.txt        # kun streamlit
├── .streamlit/config.toml  # tema (samme look som Ejnar)
└── README.md
```

## Kør lokalt

```bash
cd byggeteknik
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Cloud deploy

Opret en ny app og peg på dette repo:

- **Repository:** `simo224i-eng/pkn-vidensbase`
- **Main file path:** `byggeteknik/app.py`

Valgfri secret:

```toml
APP_PASSWORD = "..."   # sættes den, kræver appen login. Ellers er den åben.
```

## Tilføj eller ret kort

Rediger `data/flashcards.json`. Hvert kort er et objekt i `"kort"`-listen:

```json
{
  "id": 42,
  "kategori": "fundament",        // skal matche et id i "kategorier"
  "niveau": "grund",              // "grund" eller "videre"
  "spørgsmål": "Hvad er en sætningsskade?",
  "svar": "En sætning er ...",     // markdown-fed (**…**) understøttes
  "juridisk": "Klassisk ejerskiftesag ..."  // valgfri — vises i den røde boks
}
```

Hold `id` unikt. Nye kategorier tilføjes i `"kategorier"` med et `id`, et `navn`
og evt. et Material-ikonnavn.

## Forhold til de andre apps i repoet

| App | Domæne | Formål |
|---|---|---|
| **Harald** (`app.py`, `pages/`) | Plan- & Miljøklagenævn | Søg i praksis (RAG) |
| **Ejnar** (`ejnar/`) | Ejerskifteforsikring, AKF | Søg i kendelser (RAG) |
| **Børge** (`byggeteknik/`) | Byggeteknik bag ejerskifte | **Lær** stoffet (flashcards) |

De tre apps deler repo, men er fuldstændig uafhængige og deployes hver for sig.

---

> Børge er et lærings-deck — ikke juridisk rådgivning i en konkret sag. Slå
> konkret praksis op i Ejnar eller i nævnets database.

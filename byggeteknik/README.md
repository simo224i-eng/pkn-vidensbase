# Børge — Lær byggeteknik periode for periode

En selvstændig Streamlit-app, der hjælper dig med at **lære byggeteknik** ud fra
bygningens **opførelsesperiode**. Vælg en æra (fx 1960–1979), og lær hvordan
husene fra den tid er bygget — tag, vægge, fundament, materialer — og hvad der
kendetegner dem. Så når du sidder med en bygning fra 1975 og et anmeldt tag, ved
du, hvad du skal kigge efter.

> **Rent byggeteknisk** — ingen jura. Fokus er fagbegreber og konstruktion:
> *hvad er puds, hvordan er et tag/en væg bygget op, hvad er en hulmur* osv.
> El- og VVS-installationer er udeladt.

Appen har sit eget visuelle udtryk (petrol/teal på varmt papir, Space Grotesk),
bevidst forskelligt fra Harald og Ejnar.

## To måder at lære på

- **📇 Lær** — klassiske vend-kort: spørgsmål på forsiden, byggeteknisk svar på
  bagsiden. De fleste kort har en **tegnet snittegning** (SVG i `assets/`) på
  bagsiden — hulmur, terrændækkets lag, tagkonstruktion, punkteret termorude osv.
  Bland kortene og bladr igennem.
- **🎯 Quiz** — multiple choice for den valgte periode, med forklaring på hvert
  svar og en score til sidst.

## Sådan er det bygget op

- **Periode-først:** en tidslinje øverst, hvor grænserne følger de faktiske
  bygningsreglement-skift: Alle perioder · Før 1930 · 1930–1960 ·
  **1960–1972** (før fugt-/isoleringskrav) · **1972–1979** (BR72: fugtsikring) ·
  **1979–1995** (energistramning) · 1995–2008 · 2008–nu. Vælg en æra, og indholdet
  filtreres til netop den.
- **Regeltidslinje:** en udfoldelig oversigt over de byggeregler, der ændrede
  byggeskikken (1858/1939 fugt, BR61, BR72 kapillarbrydende lag, 1979-energistramning,
  asbestforbud 1986 osv.), så du kan koble et hus' årstal til, hvad der gjaldt.
- **Tværgående grundbegreber** (hvad er puds, mørtel, tegl, beton, isolering …)
  vises uanset periode — kan slås fra, hvis du kun vil have det periode-specifikke.
- **Emnefilter:** Materialer & begreber · Tag · Ydervæg & facade · Fundament &
  sokkel · Gulve & dæk · Vinduer & døre · Vådrum · Fugt, skimmel & svamp ·
  Regler & milepæle.

## Struktur

```
byggeteknik/
├── app.py                  # hele appen (Lær + Quiz, periode-tidslinje)
├── data/flashcards.json    # det kuraterede deck (perioder + emner + kort m. quiz)
├── assets/                 # 20 tegnede snittegninger (SVG) til kortenes bagsider
├── requirements.txt        # kun streamlit
├── .streamlit/config.toml  # tema (petrol/teal på varmt papir)
└── README.md
```

Et kort får et diagram ved at sætte `"billede": "hulmur.svg"` (filnavn i
`assets/`) og evt. `"billedtekst": "..."` på kortet i `flashcards.json`.

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

Valgfri secret: `APP_PASSWORD = "..."` (sættes den, kræver appen login; ellers åben).

## Tilføj eller ret indhold

Rediger `data/flashcards.json`. Hvert kort:

```json
{
  "id": 61,
  "emne": "tag",                       // skal matche et id i "emner"
  "perioder": ["1960_1979"],           // periode-id'er, eller ["alle"] for tværgående
  "forside": "En sag om TAG på et hus fra 1970'erne — hvad skal du være obs på?",
  "bagside": "Tjek hvilken af de tre typiske tagløsninger ...",  // markdown-fed (**…**) ok
  "quiz": {                             // valgfri — uden den indgår kortet kun i Lær
    "sp": "Et hus fra 1975 med fladt tagpaptag — hvad er den klassiske svaghed?",
    "valg": ["...", "...", "...", "..."],
    "korrekt": 0,                       // indeks i 'valg'
    "forklaring": "..."
  }
}
```

Hold `id` unikt. Nye perioder/emner tilføjes i `"perioder"` / `"emner"`.

## Forhold til de andre apps i repoet

| App | Domæne | Formål |
|---|---|---|
| **Harald** (`app.py`, `pages/`) | Plan- & Miljøklagenævn | Søg i praksis (RAG) |
| **Ejnar** (`ejnar/`) | Ejerskifteforsikring, AKF | Søg i kendelser (RAG) |
| **Børge** (`byggeteknik/`) | Byggeteknik, periode for periode | **Lær** byggeteknik (flashcards + quiz) |

De tre apps deler repo, men er fuldstændig uafhængige og deployes hver for sig.

---

> Børge er et lærings-værktøj — ikke juridisk rådgivning i en konkret sag.

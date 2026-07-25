# Ejnar – teknisk review og forbedringsplan

## Formål

Ejnar skal være en juridisk research-assistent og praksisdatabase – ikke kun en
maskine til skadesvurderinger. Den skal understøtte mindst seks forskellige
brugerbehov:

1. finde afgørelser med bestemte ord, formuleringer, faktiske forhold eller argumenter;
2. finde en konkret kendelse;
3. give afgrænsede faktuelle opslag;
4. sammenfatte generel nævnspraksis;
5. sammenligne en konkret problemstilling med praksis;
6. udforske beslægtede emner og afgørelser.

## Nuværende arkitektur

- `pages/ejnar.py` indeholder dataindlæsning, UI, filtre, søgning,
  `smart_retrieval`, promptbygning og chatsession.
- `shared.py` indeholder styling, LLM-klient, tekstbehandling, embeddings,
  HyDE, TF-IDF, RRF, reranking og kontekstbygning.
- Retrieval-flowet er i hovedtræk:

  1. Haiku klassificerer spørgsmålet i fire brede typer.
  2. Et opfølgningsspørgsmål omskrives med Haiku.
  3. Haiku foreslår metadatafiltre.
  4. Spørgsmålet udvides med synonymer og relaterede begreber.
  5. TF-IDF og semantisk chunk-søgning fusioneres med RRF.
  6. Den semantiske søgning bruger HyDE som standard.
  7. Kandidater rerankes med Voyage Rerank eller Haiku.
  8. De valgte dokumenter chunkes igen og rescored med lokal TF-IDF.
  9. Claude skriver et svar ud fra den fokuserede kontekst.

## Vigtigste fund

### 1. Queryklassifikationen afspejler ikke produktets reelle brug

De nuværende typer – faktuel, sammenligning, procedure og åben – kan ikke
skelne mellem:

- “Find kendelser, hvor der står X”
- “Hvad er praksis om X?”
- “Er X dækket i denne konkrete sag?”

Det medfører, at meget forskellige søgebehov kan få samme retrieval-politik.

### 2. HyDE anvendes som standard ved præcise indholdssøgninger

`embedding_soeg(..., use_hyde=True)` genererer et hypotetisk
kendelsesuddrag og embedder dette sammen med spørgsmålet. Det kan være nyttigt
til brede praksisspørgsmål, men kan flytte signalet væk fra brugerens præcise
ordlyd eller kombination af fakta.

**Anbefaling:** Deaktivér HyDE ved:

- ordrette fraser;
- søgning efter konkrete sags-/kendelsesnumre;
- “find afgørelser hvor ...”-forespørgsler;
- søgninger efter bestemte kombinationer af faktiske forhold.

### 3. Query expansion bruges før både lexical og semantisk retrieval

`smart_retrieval` kalder `udvid_query`, hvorefter den udvidede tekst sendes
til `hybrid_retrieval`. Det betyder, at den semantiske søgning ikke kun ser
brugerens oprindelige forespørgsel, men også LLM-genererede synonymer og
lovhenvisninger. Det kan forbedre recall ved brede spørgsmål, men forringe
præcisionen ved ordrette og specifikke søgninger.

### 4. Automatiske filtre kan skabe falske negativer

Automatiske metadatafiltre anvendes før retrieval, hvis mindst tre dokumenter
overlever. Relevante afgørelser med manglende eller fejlklassificeret metadata
kan derfor fjernes, før tekstlig relevans vurderes.

**Anbefaling:** Slå automatiske filtre fra for exact-content og konkrete
kendelsessøgninger. Ved andre søgetyper bør systemet logge både filtrerede og
ufiltrerede resultater og kunne falde tilbage automatisk.

### 5. Relevans vurderes flere gange på forskellige tekstudsnit

- embeddings scorer præbyggede chunks;
- Voyage rerank ser kun titel plus cirka 700 tegn fra `udtræk_kerneafsnit`;
- kontekstbygningen chunker dokumenterne igen og scorer med en ny TF-IDF-model.

En kendelse kan derfor findes på grund af ét relevant afsnit, men senere
rerankes på et andet tekstudsnit. Det kan forklare oplevelsen af, at relevante
kendelser “forsvinder”.

**Anbefaling:** Bevar det bedst matchende chunk og dets score gennem hele
pipelinen og lad rerankeren se netop dette chunk.

### 6. Retrieval-kvalitet kan ikke måles systematisk

Der er ikke fundet et fast evalueringssæt med kendte relevante afgørelser.
Uden Recall@K og MRR kan man ikke afgøre, om HyDE, query expansion,
autofiltre eller reranking faktisk forbedrer løsningen.

### 7. Vedligeholdelsesrisiko

`shared.py` er over 2.300 linjer og blander CSS, API-kald, retrieval,
GitHub-cachehåndtering og præsentationslogik. `pages/ejnar.py` er samtidig
over 1.100 linjer og indeholder både domænelogik og UI.

Det gør isolerede tests og sikre ændringer sværere.

## Prioriteret plan

### Fase 1 – måling og routing

- Indfør seks deterministiske query intents.
- Opret et evalueringssæt med virkelige spørgsmål.
- Mål Recall@5, Recall@10, Recall@20 og MRR.
- Log kandidater efter hvert retrieval-trin.
- Bevar brugerens originale forespørgsel separat fra den udvidede.

### Fase 2 – retrieval-korrektion

- Slå HyDE/query expansion/autofiltre fra ved exact-content-søgning.
- Tilføj eksplicit phrase-boost og AND-term coverage.
- Bevar top-matchende chunk gennem retrieval og reranking.
- Sammenlign baselines:
  - TF-IDF alene;
  - embeddings alene;
  - hybrid uden HyDE;
  - hybrid med HyDE;
  - med og uden reranking.

### Fase 3 – svarstrategi

Svarformatet skal følge hensigten:

- exact content: rangordnet afgørelsesliste, matchende uddrag og matchårsag;
- specific decision: kendelsen og dens metadata;
- practice overview: hovedlinjer, variation og repræsentative kilder;
- concrete assessment: argumenter for/imod, afgørende faktum og sammenlignelige sager;
- factual lookup: kort svar med få præcise kilder;
- exploratory: relaterede temaer og forslag til videre søgning.

### Fase 4 – UI og modulopdeling

- Gør “Søg i afgørelser”, “Undersøg praksis” og “Analysér problemstilling”
  til tydelige indgange.
- Flyt retrieval til egne moduler.
- Flyt styling ud af `shared.py`.
- Tilføj debugpanel for retrieval-plan og kandidatflow.

## Første implementering i denne PR

Denne PR tilføjer kun et isoleret, deterministisk routingmodul og tests.
Det er bevidst endnu ikke koblet til den levende Streamlit-app. Dermed kan
klassifikationen evalueres og justeres uden risiko for regression i produktion.

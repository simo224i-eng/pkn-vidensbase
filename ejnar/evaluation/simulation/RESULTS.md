# Praksissimulation – resultater

**Kørsel:** 29.09.2026. 8 sager skrevet af tre simulerede skadesbehandlere
(`cases.json`). Svarene blev skrevet af en Claude-agent, der spillede Ejnars
sprogmodel, og bedømt **blindt** (A/B i tilfældig rækkefølge) af en simuleret
juraprofessor og en simuleret teamleder i en skadesafdeling.

## Hvad simulationen fandt

| # | Fund | Rettet i |
|---|---|---|
| 1 | Kontekstbudgettet blev brugt på de første 3–4 kendelser. Kilde 5–15 stod i kilderegistret, men deres indhold nåede aldrig modellen. | 4f9f48f |
| 2 | Citatkontrollen gav 71 falske advarsler i 8 svar: forskudte anførselstegnspar, manglende typografiske anførselstegn, titler, brugerens eget spørgsmål og udeladelsestegn. Efter rettelsen: 0. | 232c1a8 |
| 3 | Svarene var for lange (940–1.140 ord). Nu starter de med "Kort svar" og er fokuserede. | 4f9f48f |
| 4 | "Afgørelseskernen" i lange kendelser var ofte en citeret ældre kendelse eller parternes argumenter. | 7ebc873 |
| 5 | Skadesbehandleren savnede en klar anbefaling og journalnumre ved kildehenvisningerne. | 0867eac |
| 6 | Professoren: udfald skal altid stå ved kilden, fordelinger må kun tælle sammenlignelige kendelser (vilkår, årsspænd), og spørgsmål med flere led skal besvares led for led. | se nedenfor |

## Blind A/B: runde 1 (før rettelse 1 og 3) mod runde 2 (efter)

| Bedømmer | Runde 2 vinder | Runde 1 vinder | Uafgjort |
|---|---|---|---|
| Juraprofessor | **6** | 1 | 1 |
| Skadesbehandler | **7** | 1 | 0 |

Juraprofessorens gennemsnit (1–5):

| Dimension | Runde 1 | Runde 2 |
|---|---|---|
| Retrieval | 2,50 | **4,62** |
| Korrekthed | 3,25 | **4,12** |
| Forankring i kilder | 3,50 | **4,88** |
| Praksissyntese | 4,12 | 4,00 |
| Konkrethed | 3,12 | **4,00** |

Begge bedømmere fremhævede, at forskellen skyldes kildegrundlaget og ikke
formuleringerne. Når begge svar havde alle kilder (S07, S08), var de næsten
lige gode.

## Omvendt facit: kan Ejnar forudsige nævnets afgørelse?

Her er facit nævnets egen afgørelse og ikke en models vurdering (`reverse_gold.py`).
Testen brugte 20 tilfældige kendelser fra 2012 og frem, udtrukket stratificeret:
8 Ikke medhold, 6 Delvis medhold og 6 Medhold. Kun sagens faktum blev givet videre,
og en agent skrev et realistisk spørgsmål pr. sag. Selve kendelsen blev fjernet fra
korpus (leave-one-out), så svaret skulle bygge på *anden* praksis, præcis som ved en
ny sag.

| Mål | Resultat |
|---|---|
| Kildekendelsen fundet af søgningen (uden LLM) | top-1 16/20 · top-5 17/20 · top-15 18/20 |
| Udfald præcist rigtigt | **12/20** (naivt gæt "Ikke medhold": 8/20) |
| Retning rigtig (klager får noget / intet) | 15/20 |
| Recall pr. udfald | Ikke medhold 8/8 · Delvis 3/6 · Medhold 1/6 |
| Vægtet med korpusfordelingen (76 % / 13 % / 7,5 %) | **0,87** (naivt gæt: 0,79) |

**Tolkning.** Ejnar slår det naive gæt, men er forsigtig. Alle otte fejl
undervurderer klagers resultat. Det svarer til nævnets praksis, hvor klager får
intet i 3 ud af 4 sager, og for en skadesbehandler er det den rigtige side at fejle
på. I flere fejlsager (fx G20) pegede svaret selv på det delforhold, der endte med
at give klager delvis medhold. Kun den samlede konklusion ramte ved siden af.

**Fundne fejl, rettet:**
- Den paragraf-baserede kontekst (bruges ved præcise tekstsøgninger) manglede dato
  og udfald i kildeoverskriften. Modellen kunne derfor ikke opgøre praksis (G19).
- 10 kendelser havde scraperens fallback-dato (lørdag 09.05.2026) i stedet for
  afgørelsesdatoen. Et eksempel er AKF 62766 fra 2004. Datoen skønnes nu ud fra den
  seneste dato i kendelsens tekst eller ud fra nærmeste sagsnummer. Den vises som
  "ca." i kontekst, API (`date_estimated`) og UI.

## Forbehold

- Både svar-modellen og bedømmerne er Claude-modeller. Resultaterne peger på
  systematiske svagheder, men erstatter ikke en menneskelig juridisk review.
- Svarkvaliteten med billigere modeller (fx Gemini Flash) bør måles ved at køre
  trin 3 i `README.md` med den model.
- 8 sager er et lille udsnit. Kør simulationen igen efter større ændringer.

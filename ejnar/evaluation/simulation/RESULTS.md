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

## Forbehold

- Både svar-modellen og bedømmerne er Claude-modeller. Resultaterne peger på
  systematiske svagheder, men erstatter ikke en menneskelig juridisk review.
- Svarkvaliteten med billigere modeller (fx Gemini Flash) bør måles ved at køre
  trin 3 i `README.md` med den model.
- 8 sager er et lille udsnit. Kør simulationen igen efter større ændringer.

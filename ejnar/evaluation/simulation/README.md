# Praksissimulation: skadesbehandlere og juraprofessor

Et realistisk kvalitetstjek af hele Ejnar-kæden (retrieval, prompt og svar),
bedømt af de to typer brugere, værktøjet er lavet til. Simulationen kræver
**ingen API-nøgle**. Retrieval kører lokalt, og de tre AI-roller spilles af
agenter i Claude Code på dit abonnement.

| Trin | Hvem | Hvad |
|---|---|---|
| 1. Sager | Agent som skadesbehandlere (Mette, Jonas, Pia) | Skriver realistiske spørgsmål uden at kende databasen → `cases.json` |
| 2. Prompts | `build_prompts.py` | Kører Ejnars rigtige retrieval og fanger den præcise svar-prompt (inkl. grounding- og praksissyntese-politikker) |
| 3. Svar | Agent som "sprogmodellen" | Besvarer hver prompt, må kun bruge prompten |
| 4. Kontroller | `postprocess.py` | Samme citatkontrol som appen og ugyldige kildehenvisninger |
| 5. Bedømmelse | Agent som juraprofessor og agent som skadesbehandler | Scorer efter `RUBRIC.md` → `reviews.json` |
| 6. Rapport | `postprocess.py` | Samler alt i `runs/<kørsel>/REPORT.md` |

## Kør den

```bash
python -m ejnar.evaluation.simulation.build_prompts --out ejnar/evaluation/simulation/runs/r2
# I Claude Code: bed Claude om at lade en agent besvare runs/r2/<ID>.prompt.txt → <ID>.answer.md
# (kun ud fra prompten) og en anden bedømme efter RUBRIC.md → runs/r2/reviews.json
python -m ejnar.evaluation.simulation.postprocess --run ejnar/evaluation/simulation/runs/r2
```

## Begrænsninger

- Hjælpekald (query-udvidelse, omskrivning, AI-rerank) er slået fra i trin 2,
  som når ingen LLM er konfigureret. Retrieval er derfor den deterministiske
  basis. Med en rigtig model bliver den typisk bedre.
- Svar-agenten er en Claude-model. Svarkvaliteten med en billigere model
  (Gemini Flash, DeepSeek osv.) bør måles ved at køre trin 3 med den model.
- Bedømmerne er også modeller. Brug rapporten til at finde systematiske svagheder,
  ikke som endelig juridisk kvalitetssikring.

## Udsagnsrevision: holder hvert udsagn? (`claim_audit.py`)

Ejnar er et praksisværktøj, og kvaliteten afhænger af, om praksis gengives
korrekt. Derfor efterprøves svar på rene praksisspørgsmål (`practice_cases.json`)
udsagn for udsagn mod de kendelser, de henviser til. Det er mere objektivt end
at give karakterer:

1. `build_prompts` med `--cases practice_cases.json` bygger prompterne gennem den
   rigtige pipeline, og en agent besvarer dem.
2. `postprocess` kører de automatiske kontroller: citater, udfaldskonflikter og
   ugyldige kildehenvisninger.
3. `claim_audit pack` lægger svaret og hver citeret kendelses faktum og begrundelse
   i `audit/<ID>.md`. En revisor-agent klassificerer hvert udsagn som
   understøttet, delvist, ikke understøttet eller modsagt → `audit/claims*.json`.
4. `claim_audit score` opgør andelen af understøttede og modsagte udsagn.

```bash
python -m ejnar.evaluation.simulation.build_prompts --cases ejnar/evaluation/simulation/practice_cases.json --out ejnar/evaluation/simulation/runs/p1
python -m ejnar.evaluation.simulation.postprocess --run ejnar/evaluation/simulation/runs/p1
python -m ejnar.evaluation.simulation.claim_audit pack  --run ejnar/evaluation/simulation/runs/p1
python -m ejnar.evaluation.simulation.claim_audit score --run ejnar/evaluation/simulation/runs/p1
```

## Omvendt facit (`reverse_gold.py`)

Denne test viser, om den fundne praksis peger i samme retning som nævnets
afgørelse. Ejnar forudsiger ikke udfald i sine svar. Instruktionen om en
udfaldslinje findes kun i testen. Her er facit nævnets egen afgørelse og ikke
en models vurdering:

1. `sample` udtrækker kendelser, stratificeret på udfald, og viser kun sagens
   faktum. Udfald og nævnets begrundelse fjernes automatisk.
2. En agent skriver et realistisk skadesbehandler-spørgsmål ud fra faktum →
   `questions.json`.
3. `build` måler **retrieval** (finder Ejnar netop den kendelse?) og bygger
   **leave-one-out**-prompts, hvor kildekendelsen er fjernet, så svaret skal
   forudsige udfaldet ud fra anden praksis, som ved en ny sag.
4. En agent eller model besvarer prompterne. `score` sammenligner det forudsagte
   udfald med nævnets faktiske udfald og med basisraten "gæt altid Ikke medhold".

```bash
python -m ejnar.evaluation.simulation.reverse_gold sample --out ejnar/evaluation/simulation/runs/gold --n 20
python -m ejnar.evaluation.simulation.reverse_gold build  --out ejnar/evaluation/simulation/runs/gold
python -m ejnar.evaluation.simulation.reverse_gold score  --out ejnar/evaluation/simulation/runs/gold
```

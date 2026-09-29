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

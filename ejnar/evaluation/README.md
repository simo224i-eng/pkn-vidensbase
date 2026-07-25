# Retrieval-evaluering

Denne mappe bruges til at dokumentere, om Ejnar faktisk finder de rigtige
kendelser – ikke blot om svarene ser overbevisende ud.

## Sådan udfyldes `eval_questions.csv`

Én række per spørgsmål:

- `question_id`: stabilt ID, fx `EJ-001`.
- `query`: det spørgsmål en jurist reelt vil skrive.
- `intent`: en af værdierne fra `QueryIntent`.
- `expected_decision_ids`: kendte relevante sagsnumre, adskilt med `|`.
- `expected_terms`: ord som bør findes i mindst ét topresultat, adskilt med `|`.
- `expected_phrase`: en ordret frase, når spørgsmålet handler om specifikt indhold.
- `notes`: hvorfor spørgsmålet er vigtigt.

Start med mindst 30 virkelige spørgsmål:

- 10 præcise indholdssøgninger;
- 5 konkrete kendelsessøgninger;
- 5 praksisoverblik;
- 5 konkrete sagsvurderinger;
- 5 faktuelle eller eksplorative spørgsmål.

For præcise indholdssøgninger bør mindst én kendelse verificeres manuelt i den
officielle database. Udfyld ikke et forventet sagsnummer ved gæt.

## Resultatformat

Evalueringsværktøjet læser JSONL med én linje per spørgsmål:

```json
{"question_id":"EJ-001","results":[{"Sagsnummer":"100123","Titel":"...","Tekst":"...","Link":"..."}]}
```

`results` skal stå i den rækkefølge, retrieval-versionen returnerede dem. Formatet
er bevidst uafhængigt af Streamlit og modelleverandør, så samme facit kan bruges
til at sammenligne lexical baseline, hybrid retrieval og senere versioner.

## Kør metrikkerne

Fra repoets rod:

```bash
python -m ejnar.evaluation.metrics \
  --questions ejnar/evaluation/eval_questions.csv \
  --results ejnar/evaluation/retrieval_results.jsonl \
  --output ejnar/evaluation/report.json
```

Rapporten indeholder både samlet score og resultatet for hvert spørgsmål.
Spørgsmål uden `expected_decision_ids` tæller ikke som fejl i Recall, MRR eller
NDCG. De kan stadig måles på forventede termer og ordrette fraser.

## Metrikker

- Recall@5, @10 og @20
- Mean Reciprocal Rank (MRR)
- NDCG@10
- exact-phrase hit rate
- expected-term coverage
- antal unikke kendelser

Næste integrationstrin er at eksportere de faktiske rå resultater fra Ejnars
retrieval-pipeline i JSONL-formatet, så metrikkerne kan køres efter hver ændring.

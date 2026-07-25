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

## Kør den faktiske retrieval

Fra repoets rod:

```bash
python -m ejnar.evaluation.run_retrieval
```

Runneren:

1. finder alle `ejnar_*.csv` og `ejnar_*.csv.zip`;
2. bygger samme TF-IDF-indeks som appen;
3. installerer den intent-aware retrieval-runtime;
4. kører alle spørgsmål fra `eval_questions.csv`;
5. skriver rå resultater til `retrieval_results.jsonl`;
6. skriver den samlede rapport til `retrieval_report.json`.

Standardkørslen er reproducerbar og kræver ingen API-nøgler. Den bruger den
levende routing og hybridfunktion med lexical fallback. Voyage/Haiku-rerank kan
slås til eksplicit:

```bash
python -m ejnar.evaluation.run_retrieval --rerank
```

Det kræver, at de relevante Streamlit-secrets er tilgængelige i miljøet.
Andre nyttige argumenter:

```bash
python -m ejnar.evaluation.run_retrieval \
  --top-k 20 \
  --questions ejnar/evaluation/eval_questions.csv \
  --data-dir ejnar \
  --results /tmp/ejnar-results.jsonl \
  --report /tmp/ejnar-report.json
```

Rapporten indeholder også antal dokumenter, antal spørgsmål, gennemsnitlig
retrieval-tid og den detekterede søgehensigt for hver forespørgsel.

## Automatisk bootstrap-facit

`bootstrap_gold.py` kan oprette et foreløbigt og auditerbart relevance-facit
ud fra de kendelser, retrieval allerede har fundet:

```bash
python -m ejnar.evaluation.bootstrap_gold \
  --questions ejnar/evaluation/eval_questions.csv \
  --results ejnar/evaluation/retrieval_results.jsonl \
  --output ejnar/evaluation/bootstrap_qrels.csv
```

Hver kandidat får én af følgende labels:

- `2`: meget relevant;
- `1`: relevant;
- `0`: irrelevant;
- `-1`: usikker og egnet til senere stikprøvekontrol.

CSV-filen indeholder også confidence, anvendte signaler, begrundelse og kilde.
Den kan derfor revideres, og AI-dommene kan holdes adskilt fra senere manuelt
verificerede domme. Bootstrap-facittet bør bruges til udvikling og prioritering,
ikke som eneste dokumentation over for eksterne brugere.

GitHub-workflowet `Ejnar retrieval baseline` genererer automatisk
`bootstrap_qrels.csv` og uploader det sammen med rapport og rå resultater.

## Fastfrosset qrels-benchmark

`bootstrap_qrels_v1.csv` er en kompakt, fastfrosset relevance-pool fra den første
vellykkede bootstrap-kørsel. Provenance og label-fordeling er dokumenteret i
`bootstrap_qrels_v1.meta.json`. Fordi facittet er fast, kan senere retrieval-
versioner sammenlignes mod de samme domme.

Kør qrels-metrikkerne sådan:

```bash
python -m ejnar.evaluation.qrels_metrics \
  --qrels ejnar/evaluation/bootstrap_qrels_v1.csv \
  --results ejnar/evaluation/retrieval_results.jsonl \
  --output ejnar/evaluation/qrels_report.json
```

Qrels-poolen er ufuldstændig. En kendelse uden dom behandles derfor som
`unjudged` – ikke automatisk som irrelevant. Rapporten viser derfor både:

- Recall@5, @10 og @20 mod kendte relevante kendelser;
- MRR og graded NDCG@10;
- judged precision@5 og @10;
- judged coverage@5, @10 og @20.

Høj Recall@20 skal fortolkes forsigtigt, fordi bootstrap-poolen oprindeligt blev
bygget fra top-20-resultater. Judged coverage viser, hvor stor en del af den nye
resultatliste der faktisk er dækket af facittet.

## Resultatformat

Runneren skriver JSONL med én linje per spørgsmål:

```json
{"question_id":"EJ-001","detected_intent":"exact_content_search","latency_ms":42.1,"results":[{"Sagsnummer":"100123","Titel":"...","Tekst":"...","Link":"..."}]}
```

`results` står i den rækkefølge, retrieval-versionen returnerede dem. Formatet er
uafhængigt af Streamlit og modelleverandør, så samme facit kan bruges til at
sammenligne lexical baseline, hybrid retrieval og senere versioner.

## Kør kun de oprindelige metrikker igen

```bash
python -m ejnar.evaluation.metrics \
  --questions ejnar/evaluation/eval_questions.csv \
  --results ejnar/evaluation/retrieval_results.jsonl \
  --output ejnar/evaluation/report.json
```

Spørgsmål uden `expected_decision_ids` tæller ikke som fejl i Recall, MRR eller
NDCG. De kan stadig måles på forventede termer og ordrette fraser.

## Metrikker

- Recall@5, @10 og @20
- Mean Reciprocal Rank (MRR)
- NDCG@10
- judged precision og judged coverage
- exact-phrase hit rate
- expected-term coverage
- antal unikke kendelser
- gennemsnitlig retrieval-tid

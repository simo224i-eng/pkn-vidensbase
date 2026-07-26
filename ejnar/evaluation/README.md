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

Det aktive benchmark er `bootstrap_qrels_v2.csv`. Det indeholder 429 sikre domme
på tværs af 30 af de 31 stabile evalueringsspørgsmål. De 191 usikre domme fra
bootstrap-kørslen er ikke gemt som ground truth. Provenance, den fulde
label-fordeling og SHA-256 for alle 31 querytekster ligger i
`bootstrap_qrels_v2.meta.json`.

Query-hashene betyder, at et eksisterende `question_id` ikke kan få en ny
betydning uden at tests fejler. `bootstrap_qrels_v1.csv` og dets manifest
bevares som historisk baseline, men bruges ikke længere af standardworkflowet.

Kør det aktive qrels-benchmark sådan:

```bash
python -m ejnar.evaluation.qrels_metrics \
  --qrels ejnar/evaluation/bootstrap_qrels_v2.csv \
  --results ejnar/evaluation/retrieval_results.jsonl \
  --output ejnar/evaluation/qrels_report.json
```

Qrels-poolen er ufuldstændig. En kendelse uden dom behandles derfor som
`unjudged` – ikke automatisk som irrelevant. Rapporten viser både:

- Recall@5, @10 og @20 mod kendte relevante kendelser;
- MRR og graded NDCG@10;
- judged precision@5 og @10;
- judged coverage@5, @10 og @20;
- benchmarkede spørgsmål, aktuelle spørgsmål uden facit og manglende resultater.

Høj Recall@20 skal fortolkes forsigtigt, fordi bootstrap-poolen oprindeligt blev
bygget fra top-20-resultater. Judged coverage viser, hvor stor en del af en ny
resultatliste der faktisk er dækket af facittet.

## Query Planner v1-eksperiment

Query Planner v1 udvider kun korte, søgefelt-lignende forespørgsler med en lille
auditerbar liste af nært beslægtede termer. Ordrette indholdssøgninger, konkrete
kendelsesopslag og allerede informationsrige spørgsmål bevares uændret.
Ukendte begreber bruger den eksisterende fallback.

Kør den isolerede kontrol/kandidat-sammenligning sådan:

```bash
python -m ejnar.evaluation.run_query_planner_experiment \
  --top-k 20 \
  --output-dir artifacts/ejnar-query-planner
```

Runneren bruger samme corpus og TF-IDF-matrice til begge kørsler. Den fejler ved
et fald på mere end ét procentpoint i Recall, MRR, NDCG eller judged precision,
eller hvis kandidatens gennemsnitlige latency overstiger 1,25 gange kontrollen.
Planneren tilføjer kun retrieval-termer; den tager aldrig stilling til dækning i
en konkret forsikringssag.

Det frosne sæt med 31 spørgsmål indeholder primært lange eller
præcisionsfølsomme spørgsmål. I den første Query Planner v1-måling ændrede
planneren derfor **0 af 31** effektive queries og **0 af 31** resultatlister.
Denne måling er et globalt regressionsværn, ikke dokumentation for gevinst på
korte søgninger. Runneren rapporterer nu eksplicit antal behandlede queries og
ændrede resultatlister, og den kan konfigureres til at afvise no-op-forsøg.

## Frosset benchmark for korte søgninger

`short_query_questions_v1.csv` er skrevet og frosset, før retrieval-resultater
blev vist. Det indeholder:

- 30 selvstændige emner med to naturlige varianter (60 korte søgninger);
- 12 sjældne, corpus-attesterede fallback-søgninger;
- 12 guardrails for ordrette fraser, kendelsesnumre og allerede informative
  spørgsmål.

Emnerne er fordelt i development, validation og holdout. De to forfattere
arbejdede ud fra afgørelseskorpusset uden at se plannerens begrebsordbog eller
retrieval-resultater. Manifestet `short_query_questions_v1.meta.json` fryser
datasættets hash, fordeling og produktgrænse.

Byg en deterministisk blind kandidatpulje sådan:

```bash
python -m ejnar.evaluation.run_short_query_experiment \
  --pool-only \
  --minimum-treated-cohort-size 60 \
  --minimum-planner-applications 12 \
  --minimum-holdout-planner-applications 5 \
  --minimum-holdout-active-topics 5 \
  --top-k 30 \
  --pool-depth 30 \
  --output-dir artifacts/ejnar-short-query-pool
```

Puljen deduplikerer kandidater fra ren original-query lexical retrieval, den
levende baseline og planner-kandidaten. Filen `blind-pool.jsonl` skjuler system
og rang; disse oplysninger ligger separat i `pool-provenance.jsonl`. Dermed kan
relevans bedømmes uden at favorisere et system. En senere gold-pulje bør også
medtage en reproducerbar semantisk retrieval og eventuelle kendte officielle
databasefund.

CI publicerer to separate artifacts. `ejnar-short-query-adjudication`
indeholder kun den blinde pulje og neutral integritetsinformation.
`ejnar-short-query-diagnostics` indeholder systemnavne, rangeringer og
provenance og må ikke deles med bedømmeren, før relevansdommene er frosset.

Det frosne v1-sæt aktiverer den nuværende planner for 12 af 60 behandlede
søgninger. Holdout indeholder fem aktiverede søgninger på fem selvstændige
emner. CI afviser forsøget, hvis disse minimumstal ikke længere er opfyldt.
Sættet kan derfor dokumentere den aktuelle planners adfærd, men det er endnu
ikke bred dokumentation for alle typer korte ejerskiftesøgninger.

Der offentliggøres ikke en kvalitetsdom, før topresultaterne er bedømt.
AI-bedømmelser kaldes **silver** og er kun et udviklingssignal. Betegnelsen
**gold** kræver juridisk menneskevalidering. Det eksisterende qrels v2 bevares
som globalt regressionsværn, men bruges ikke som bevis for kortsøgningsgevinst,
fordi det er pool-biast mod en ældre pipelines top-20.

Når et blindbedømt qrels-sæt findes, måler den nye runner makro-NDCG@10 pr.
emne, Recall@20, MRR, judged precision@5, kategoriresultater,
win/tie/loss og en parret bootstrap-grænse. Validation og holdout må ikke bruges
til at vælge plannertermer. Fallback- og guardrail-rangeringer skal være
identiske.

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

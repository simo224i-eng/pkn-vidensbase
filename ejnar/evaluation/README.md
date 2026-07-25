# Retrieval-evaluering

Denne mappe skal bruges til at dokumentere, om Ejnar faktisk finder de rigtige
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

## Mål for næste trin

- Recall@5, @10 og @20
- Mean Reciprocal Rank
- exact-phrase hit rate
- expected-term coverage
- antal unikke kendelser
- frafald mellem rå kandidater, filtre, RRF, reranking og endelig kontekst

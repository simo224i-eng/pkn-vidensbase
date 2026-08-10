# Ejnar practice-synthesis benchmark

Dette benchmark måler, om Ejnar bruger fundne kendelser korrekt, når den sammenfatter praksis. Det ligger **efter** retrieval og decision grounding.

## Hvad facittet består af

Facittet kommer fra `grounding_review.py` og de menneskeligt validerede labels:

- `direct_practice` → relevans 2
- `indirect_support` → relevans 1
- `not_useful` → relevans 0
- `uncertain` → ingen benchmarkscore

Benchmarket må ikke selv generere disse labels.

## Prediction-format

Én JSONL-række per spørgsmål:

```json
{
  "question_id": "EJ-001",
  "query": "Hvornår udgør nedbrydning af en bjælke en skade?",
  "source_roles": {
    "ga-abc": "direct_practice",
    "ga-def": "indirect_support"
  },
  "distribution_denominator_audit_ids": ["ga-abc"],
  "states_practice_line": false,
  "states_fixed_practice": false
}
```

`source_roles` er systemets strukturerede vurdering af, hvordan hver kilde må bruges. `distribution_denominator_audit_ids` er kun de kendelser, systemet faktisk ville tælle med i en numerisk fordeling.

## Metrikker

- samlet source-role accuracy på menneskeligt benchmarkbare rows;
- precision/recall for `direct_practice`, `indirect_support` og `not_useful`;
- precision i denominator for fordelinger: hver medregnet kendelse skal være menneskeligt labellet `direct_practice`;
- leakage af `indirect_support`/`not_useful` i fordelinger;
- minimum-evidens-guardrails for distribution/practice-line/fixed-practice.

## Vigtig begrænsning

Tre direkte relevante kendelser er **ikke** i sig selv dokumentation for fast praksis. Benchmarket kan kun kontrollere minimumsmængden og om de anvendte kilder er direkte praksis for spørgsmålet. Det tester ikke automatisk:

- om kendelsernes bærende begrundelser faktisk er konsistente;
- om faktum er tilstrækkeligt sammenligneligt;
- om der findes modgående praksis uden for de fremlagte kilder;
- om senere lovgivning eller praksis har ændret retstilstanden.

Disse spørgsmål kræver juridisk menneskevalidering.

## CLI

Lav en label-fri prediction-template fra den blinde audit-pool:

```bash
python -m ejnar.evaluation.practice_synthesis_metrics template \
  --source blind-pool.jsonl \
  --output synthesis-predictions.jsonl
```

Når prediction-filen er udfyldt og human labels er frosset:

```bash
python -m ejnar.evaluation.practice_synthesis_metrics evaluate \
  --labels grounding-human-labels.jsonl \
  --predictions synthesis-predictions.jsonl \
  --output practice-synthesis-report.json \
  --fail-on-structural-violations
```

Dette benchmark vurderer praksissyntese og kildebrug. Det træffer aldrig afgørelse om en konkret forsikringssag.

# Ejnar decision-grounding benchmark

Dette benchmark tester en anden fejltype end retrieval-benchmarket.

Retrieval kan godt have fundet den rigtige kendelse og det rigtige tekststed, mens svaret
stadig bliver juridisk misvisende, hvis tekststedet behandles som afgørende praksis, selv
om nævnet reelt afgjorde sagen på et andet grundlag.

Eksempler på sådanne afgørelsesgrunde er:

- anmærkning i tilstandsrapporten eller andet kendt forhold;
- manglende bevis for forholdets tilstedeværelse ved overtagelsen;
- frister eller processuel afvisning;
- undtagelser i forsikringsbetingelserne;
- beløbsgrænser;
- efterfølgende årsager;
- slid, levetid eller vedligeholdelse.

## V1

`decision_grounding_cases_v1.json` indeholder 18 syntetiske, adversarielle
kendelsesstrukturer. De er skrevet for at isolere fortolkningsfejl og er **ikke** et facit
for Ankenævnets materielle praksis.

Hver case angiver:

- et realistisk spørgsmål;
- en kort kendelsestekst med parternes og/eller nævnets afsnit;
- den sektion der bør identificeres som afgørelseskerne;
- termer som skal være med i grounding-konteksten;
- distraktortermer som ikke må lække fra fx selskabets eller klagerens argument til
  nævnets afgørelseskerne;
- om ekstraktionen forventes at bruge konservativ fallback.

Kør benchmark lokalt:

```bash
python -m ejnar.evaluation.decision_grounding_metrics \
  --output /tmp/decision-grounding-report.json
```

Standardkørslen fejler, hvis blot én case fejler. Rapporten viser desuden:

- case pass rate;
- recall for forventede afgørelsestermer;
- leakage-rate for distraktortermer;
- section accuracy;
- fallback accuracy;
- resultater pr. fejltype.

## Hvad benchmarket ikke dokumenterer

Det dokumenterer ikke, at Claude altid skriver et korrekt juridisk svar. Det tester det
deterministiske lag, som sørger for, at modellen får nævnets afgørelsesgrund og ikke kun
de mest query-lignende tekststykker.

Det må derfor ikke omtales som et gold benchmark for Ankenævnets praksis. Et egentligt
answer-quality benchmark skal senere bruge menneskevaliderede, virkelige kendelser og
bedømme bl.a. om svaret korrekt skelner mellem direkte praksis, analogier, partsudsagn og
nævnets bærende begrundelse.

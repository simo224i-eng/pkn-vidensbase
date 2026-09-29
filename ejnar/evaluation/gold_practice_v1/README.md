# Praksisfacit v1 (60 spørgsmål)

Et kildeforankret facitsæt til Ejnar. Hvert spørgsmål bygger på én kendelse fra
Ankenævnet for Forsikring (2012 og frem, stratificeret på mangeltype og udfald:
24 ikke medhold, 18 delvis medhold, 18 medhold).

- `key.json`: facitkendelsens id, sagsnummer, udfald, dækning og mangeltype
- `facit/F01.json` … `F60.json`: praksisspørgsmålet, det juridiske spørgsmål og
  2–4 nøglepunkter om, hvad nævnet lagde vægt på, hvert med et ordret citat fra
  nævnets vurdering

Citaterne er maskinelt kontrolleret mod kendelsesteksten
(`gold_practice.py check`). Spørgsmål og nøglepunkter er skrevet af AI-agenter.
**Stikprøvekontrol af en fagperson anbefales.** 10–15 tilfældige facit tager ca.
en time og er det, der gør sættet til et egentligt fagligt facit.

Brug: kopiér `facit/` og `key.json` til en kørselsmappe, og kør
`python -m ejnar.evaluation.simulation.gold_practice build|gradepack|score --out <mappe>`
(se docstring i `ejnar/evaluation/simulation/gold_practice.py`). `sample` er kun
nødvendig for at lave `items/`, dvs. kendelsesteksterne til bedømmerne.

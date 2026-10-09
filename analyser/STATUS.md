# Status: Miljøjuristen og miljøvurderingsanalysen (9. oktober 2026)

Arbejdet fra cloud-sessionen er videreført lokalt på branchen `claude/nifty-ritchie-cgs745` (main er ikke
rørt). Beslutninger undervejs står i [`BESLUTNINGER.md`](BESLUTNINGER.md).

## Hvad er bygget

| # | Del | Hvor | Resultat |
|---|---|---|---|
| 1 | Data: nævnsafgørelser | `data_2026/`, `naevn_api.py`, `scrape_pkn.py`, `scrape_mfkn.py`, `fetch_pdf_afgoerelser.py` | 26 kategorier fra PKN og MFKN frem til 8/10 2026: 28.668 rækker → **26.999 afgørelser** efter rensning (dubletter, tomme tekster). 408 afgørelser, der kun fandtes som PDF, er hentet. Scraperne bruger nu nævnenes åbne søge-API (ingen cookie). |
| 1 | Data: lov og vejledning | `lovgrundlag/`, `fetch_lovgrundlag.py` | Miljøvurderingsloven med bilag, miljøvurderingsbekendtgørelsen, habitatbekendtgørelsen, planhabitatbekendtgørelsen, planloven, naturbeskyttelsesloven, husdyrbrugloven, vejledning 2024/9093 og 9094, Habitatvejledningen, landzonevejledningen, §3-vejledningen og Miljøstyrelsens/DCE's bilag IV-materiale. |
| 1 | Data: EU-domme | `eu_domme/`, `fetch_eu_domme.py` | De 30 hyppigst citerede domme, på dansk fra EUR-Lex, opdelt i præmisser. |
| 1 | Data: oprindelige screeninger | `screeninger_originale/` (kun lokalt) | 11 dokumenter fundet til de nyeste underkendte sager; 8 brugt i testen. De fleste kommunale screeninger ligger ikke online. |
| 1 | Originalindeks | `tools/originaler/`, `miljoejurist/data/originaler.json` | Links til kommunens oprindelige screening/dagsorden/planforslag for 178 nævnssager (FirstAgenda-dagsordener og plandata.dk). 138 vises (høj/middel/kontrolleret). Haiku-stikprøve: "høj" rigtig i 8/10, "middel" er rigtig plan men screeningen ofte kun resumeret. Projektscreeninger findes sjældent (27/175), da de afgøres administrativt. |
| 2 | Analyse v2 | `analyser/miljoevurdering/v2/` (`RESULTAT.md`) | 1.050 sager (2020–2026). Trin 2 lavet om med HELE nævnets vurdering for alle 283 sager med medhold: 239 brugbare, **539 fejl**, alle nævnscitater kontrolleret ordret. |
| 3 | Tjekliste | `analyser/TJEKLISTE.md` (+ `miljoejurist/data/tjekliste.json`) | 21 punkter i 7 grupper, hvert med lovuddrag (ordret), vejledningsafsnit, EU-dom og eksempler fra nævnene med links. |
| 4 | Værktøj: Miljøjuristen | `miljoejurist/` (se `README.md` dér), egen webside (`miljoejurist/web/`, `server.py`), API `/v1/miljoejurist/*` | Upload PDF/Word/tekst → rapport "svaghed → hvorfor → kilder" + "hvad er ikke vurderet". Regellag (altid) og valgfrit sprogmodellag. Automatisk citatkontrol. Skriver aldrig, at en afgørelse er i orden. |
| 4 | Stedtjek | `miljoejurist/stedtjek.py` | Kortopslag i Miljøportalen og plandata.dk ud fra kommune + plannr. eller adresse; melder ikke-nævnte områder tæt på og forkerte afstande. 14/16 fund relevante (Haiku); ramte nævnets fejl i ægte § 3-sag. |
| 5 | Test | `miljoejurist/evaluation/RESULTS.md` | 4 testsæt, 77 dokumenter, 4 runder med revision. Se nedenfor. |

## Hovedtal fra analysen

- Klager fik helt eller delvist medhold i **31 %** af miljøvurderingssagerne, der blev behandlet på indholdet
  (MFKN 37 %, PKN 23 %). Projektscreeninger 37 %, planscreeninger 19 %, miljørapporter 28 %,
  § 25-tilladelser 44 %.
- Hyppigste fejl i de underkendte sager: mangelfuld sagsoplysning (73 sager), vilkår (51), afværge-
  foranstaltninger (50), bilag IV-arter (45), kompetence/procedure (44), forkert vurdering af om projektet/planen
  er omfattet (38), Natura 2000-væsentlighed (33), screeningskriterier ikke vurderet (25).

## Seneste måling (version 2, audit med 38 sager, der ikke er brugt til udvikling)

- Fanger nævnets afgørende fejl i 19/19 ophævede sager (alle blandt de 3 første fund).
- Risikoindikator skelner ophævet/stadfæstet med AUC 0,79; "høj" = ca. 2/3 ophævet, "lav" = ca. 1/7 ophævet ved
  den reelle ophævelsesrate. Detaljer i `miljoejurist/evaluation/RESULTS.md`.
- Rapporten har to niveauer: risiko for ophævelse og helgardering. Sonnet er standardmodel.

## Testresultater (runde 3, før version 2)

| | Med sprogmodel | Kun regler |
|---|---|---|
| Underkendte screeninger (T1, 30): nævnets begrundelse blandt de prioriterede fund | **29/30** (revision), 28/30 (automatisk) | 14/30 |
| Relevante prioriterede fund (T1) | **95 %** | ca. 10 % |
| Kilderne bærer påstanden (T1) | **91 %** | – |
| Indsatte fejl fundet (T2, 19) | **18/19** | 14/19 |
| Ægte screeninger (T4, 8) | **7/8** | 4/8 |
| Stadfæstede screeninger (T3, 20): relevante fund | 70 % (ca. 30 % falske alarmer) | – |

Alle tal er målt af AI-agenter (rekonstruktion, model og revision). De er en indikation, ikke en garanti.

## Kendte svagheder

1. **Uden sprogmodel er værktøjet svagt.** Regellaget konstaterer mest, om emner er nævnt, og kan ikke skelne
   en god fra en dårlig screening. Den reelle værdi kræver en konfigureret udbyder (Ejnars `LLM_PROVIDER`).
   Til rigtige sager kræves en udbyder med databehandleraftale (se Ejnars README om persondata).
2. **Falske alarmer:** værktøjet finder 5–6 prioriterede svagheder i næsten alle dokumenter, også i
   screeninger, nævnet stadfæstede. Rapporten er en liste af steder at se efter, ikke en risikovurdering.
3. **Testen er AI bedømt af AI**, og de fleste testdokumenter er rekonstruerede ud fra nævnets sagsfremstilling.
4. **Lovgrundlaget:** LBK 4/2023 af miljøvurderingsloven indarbejder ikke ændringslovene 2024–2026 (primært
   havvind, CO2-transport, BBNJ). Habitatvejledningen er fra 2020.
5. **Planlovsfejl** (kystnærhedszonen, Fingerplanen, høringsfrister, redegørelseskrav) er ikke dækket.
6. **Husdyrsager** indgår i analysen (55 sager), men tjeklisten er skrevet til screeninger, miljørapporter og
   § 25-tilladelser; husdyrgodkendelsers særlige krav (ammoniak, BAT) er ikke tjekpunkter.
7. Udfaldsreglen (titel + tekst) stemmer med model-mærkningen i ca. 93 % af de kontrollerede sager; trin 1 for
   analysen bruger modelmærker.
8. Teksterne i `data_2026/` indeholder navne på nævnsmedlemmer, som nævnene selv offentliggør. Sagsparter er
   anonymiseret af nævnene. De lokalt hentede oprindelige screeninger kan indeholde navne og er derfor ikke i git.

9. **Stedtjek** bygger på registrerede kortlag; uregistreret § 3-natur og bilag IV-levesteder (arter.dk) er ikke med.
10. **Originalindekset** dækker mest planer; projektscreeninger og de 26 kommuner uden FirstAgenda mangler.

## Det bør du tjekke fagligt

1. **Tjeklisten** (`analyser/TJEKLISTE.md`): er de 21 spørgsmål rigtigt formuleret og afgrænset? Mangler der
   punkter, fx for husdyrgodkendelser eller planlovens krav? Er de valgte vejledningsafsnit og EU-præmisser de
   rigtige (fx C-323/17 præmis 37 om afværge i screeningen, C-127/02 præmis 45)?
2. **Trin 2-fejlkategorierne:** tag en stikprøve på 15–20 sager i `analyser/miljoevurdering/v2/deep_v2.jsonl`
   og se, om fejlbeskrivelse og kategori svarer til nævnets begrundelse. Særligt grænsen mellem
   "sagsoplysning", "materiel væsentlighed" og "screeningskriterier ikke vurderet".
3. **Rapporter fra værktøjet:** kør 3–5 af dine egne screeninger gennem fanen (med sprogmodel) og vurder, om
   de prioriterede svagheder er dem, du selv ville pege på, og om kilderne passer.
4. **Formuleringerne i rapporten:** at teksten aldrig kan læses som en frikendelse, og at "Hvad værktøjet ikke
   har vurderet" er dækkende.
5. **Lovversionerne:** om LBK 4/2023 fortsat er den rette, og om der er kommet ny vejledning eller
   habitatbekendtgørelse efter oktober 2026.
6. **De to "afvist"-typer:** at ophævelser "som uaktuelle" er udeladt som ikke-brugbare (42 sager), er et valg,
   der påvirker hyppighederne.

## Sådan kører du det

Miljøjuristen er en selvstændig webapp (egen mappe, server og side; ikke en del af Ejnar). Fra repo-roden:

```bash
pip install -r ejnar/requirements.txt -r ejnar/requirements-api.txt shapely
python -m uvicorn miljoejurist.server:app --port 8766      # + LLM_PROVIDER/LLM_API_KEY for sprogmodel
```

Åbn http://localhost:8766. Lokalt kræves ingen nøgle; sæt `MILJOEJURIST_API_KEYS` for at kræve en. Opdatering af data: se
`miljoejurist/README.md`.

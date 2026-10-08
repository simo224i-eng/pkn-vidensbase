# Miljøjuristen – testresultater

Kørt 8.–9. oktober 2026. Testen måler, om screeningstjekket finder de svagheder, nævnene faktisk
underkendte på, om fundene er relevante, og om kilderne bærer påstandene. Ingen betalte API-nøgler er
brugt: sprogmodellen er spillet af en agent (Sonnet), der fik præcis den prompt, webappen sender
(`llm_tjek.byg_prompt`), og dens svar er flettet ind af den rigtige kode (`llm_tjek.supplér`).

## Testsæt

| Sæt | Indhold | Antal |
|---|---|---|
| **T1** | Underkendte screeninger, rekonstrueret af en skribent-agent, der KUN så sagsfremstillingen (nævnets vurdering, indledning og titel fjernet). Facit: nævnets afgørende fejlkategorier. | 30 |
| **T2** | Stadfæstede screeninger (rekonstrueret som T1) med én indsat fejl af en kendt type (bilag IV, Natura 2000, kumulation, afværge, kriterier, sagsoplysning, opsplitning, høring). T2_08 udgik (intet at ændre). | 19 |
| **T3** | De samme stadfæstede screeninger uden ændringer – til falske alarmer. | 20 |
| **T4** | Ægte oprindelige screeninger/planforslag fundet online (plandata.dk og kommunernes sider) i sager, nævnet underkendte. 4 med høj, 2 middel og 2 lav sikkerhed for, at det er netop den behandlede version. | 8 |

Sagens egen afgørelse udelukkes altid fra praksissøgningen. Skribenter, model-agenter og revisorer ser kun
blinde id'er og kender ikke gruppen. Sagsteksterne ligger i `work/` (gitignoreret); facit i `facit.json` og
`t4_facit.json`.

**Måling:**
- *Fundet*: mindst én af de prioriterede svagheder (niveau "svaghed", højst 6) hører til et tjeklistepunkt,
  der dækker nævnets afgørende fejlkategori (automatisk, `koer_test.py`).
- *Revision*: en revisor-agent (Sonnet, samme i alle runder) vurderede HVERT fund mod dokumentet, kilderne
  og nævnets faktiske begrundelse: læst korrekt? relevant? bærer kilderne? matcher det nævnet?
  (`PROMPT_REVISION.md`, `revision_runde*.md`).

## Resultater pr. runde

### Med sprogmodel (model + regler)

| | Runde 1 | Runde 2 | **Runde 3** | Runde 4 |
|---|---|---|---|---|
| T1 fundet (automatisk) | 28/30* | 23/30 | **28/30** | 26/30 |
| T1 matcher nævnet (revision) | 29/30* | 27/30 | **29/30** | 28/30 |
| T1 relevante fund (ja+delvist), prioriterede | 64 %* | 84 % | **95 %** | 88 % |
| T1 kilderne bærer (ja+delvist) | 58 % | 77 % | **91 %** | 88 % |
| T1 læst korrekt | 91 % | 89 % | **92 %** | 97 % |
| T2 indsat fejl fundet (automatisk) | – | 15/19 | **18/19** | 14/19 |
| T2 relevante, prioriterede | – | 80 % | **93 %** | 89 % |
| T3 fund pr. dokument (prioriterede) | 13,0* | 5,8 | 5,8 | 4,5 |
| T3 relevante, prioriterede | 48 %* | 70 % | **70 %** | 69 % |
| T4 fundet (revision) | – | 8/8 | 7/8 | 7/8 |
| T4 relevante, prioriterede | – | 94 % | 89 % | 89 % |
| T4 kilderne bærer | – | 72 % | **93 %** | 82 % |

\* Runde 1 havde ingen prioritering; alle fund talte med.

**Den endelige version er runde 3** (koden er sat tilbage til den efter runde 4). Runde 4 strammede prompten
mod falske alarmer; det gav færre fund på de stadfæstede sager, men tabte flere ægte fund (T2 18→14), så
resultaterne blev ikke bedre, og testen blev stoppet.

### Kun regler (uden sprogmodel)

| | Runde 1 | Runde 3 |
|---|---|---|
| T1 fundet (alle fund / top 3) | 16/30 / 10/30 | 14/30 / 11/30 |
| T2 fundet | – | 14/19 / 11/19 |
| T4 fundet | – | 4/8 / 3/8 |
| Fund pr. dokument, T1 / T3 | 8,2 / 7,5 | 6,3 / 6,0 |
| Relevante (revision, ja+delvist) | 9–13 % | (vist under "mindre bemærkninger", når modellen kører) |

Regellaget alene kan **ikke skelne** underkendte fra stadfæstede screeninger: det rapporterer næsten lige mange
fund i begge. Det er nyttigt som tjekliste ("er emnet overhovedet behandlet?"), ikke som vurdering.

### Andre målinger

- **Citatkontrol:** alle citater i rapporterne kontrolleres automatisk. Modellens fund med citater, der ikke
  står ordret i dokumentet, fjernes; det skete i 8 af 77 dokumenter i runde 2 (typisk ét fund).
  Lovuddrag i tjeklisten: 33/33 (fordelt på 21 punkter) står ordret. Citater fra nævnet i praksisdata: 539/539.
- **Modellens alvorsgrad** (runde 2): fund mærket "høj" var relevante i 96 % (176/183); "lav" kun i 33 %.
  Derfor vises "lav" nu kun som "mindre bemærkninger".
- **Unit-tests:** `ejnar/tests/test_miljoejurist.py` (9) + Ejnars API-tests (15) består.

## Hvad blev forbedret undervejs (og hvorfor)

| Runde | Fund i revisionen | Ændring |
|---|---|---|
| 1 → 2 | 13 fund pr. dokument; regellagets "ikke behandlet" var støj; praksiseksempler fra andre projekttyper (fx forlystelsespark ved et boligprojekt) | Prioritering (højst 6 "svagheder"), regelvægte, prompt om at prioritere efter risiko, praksissøgning der vægter dokumenttype, projekttype og lighed med sagen |
| 2 → 3 | Regellagets "ikke behandlet" og modellens "lav" var næsten aldrig relevante; oversete mønstre: screening efter projektets start, forkert udgangspunkt, afværge som vilkår, kommuneplaner som "mindre ændringer" | Nye tjeklistepunkter A4 (lovliggørelse) og B3 (referencetilstand), prompt med de konkrete mønstre, støj flyttet til "mindre bemærkninger" |
| 3 → 4 | Falske alarmer på stadfæstede sager: kumulation uden holdepunkt, dobbeltfund, projektelementer kaldt afværge | Strammere prompt og sammenlægning af dubletter – **gav ikke bedre resultater; rullet tilbage** |

## Hvad testen ikke viser (forbehold)

- **AI bedømmer AI.** Rekonstruktion, model og revision er alle sprogmodeller (Sonnet). Revisoren kendte facit.
  En fagpersons stikprøve er nødvendig (se `analyser/STATUS.md`).
- **Rekonstruerede dokumenter er ikke ægte dokumenter.** Skribenten så sagsfremstillingen, som nævnet har
  skrevet med kendskab til fejlen; det kan gøre svaghederne lettere at finde end i en rigtig screening. T4 (ægte
  dokumenter) peger i samme retning som T1, men er kun 8 sager.
- **Falske alarmer:** på stadfæstede screeninger finder værktøjet stadig ca. 5–6 prioriterede svagheder, og
  revisoren fandt ca. 30 % af dem irrelevante. At nævnet stadfæstede betyder ikke, at screeningen var uden
  svage punkter, men brugeren skal forvente fund i næsten alle dokumenter.
- **Spredning:** modellen er ikke deterministisk; tallene svinger med nogle få sager mellem kørsler.
- Én revisor-agent i runde 4 kørte ved en fejl et fremmed hjælpescript, der kan have overskrevet enkelte
  revisionsfiler; runde 4 er derfor mindre sikker (den indgår ikke i den endelige version).
- **Planlovsfejl** (kystnærhedszonen, Fingerplanen, høringsfrister) er uden for værktøjets område og blev
  overset, som forventet.

## Filer

| Fil | Indhold |
|---|---|
| `forbered_test.py` | Udvælger T1/T3 og fjerner nævnets vurdering fra sagsfremstillingen |
| `koer_test.py` | Kører regellag, laver modelprompts, fletter svar og scorer (`resultat_runde*.json`) |
| `forbered_revision.py`, `revision_opsummer.py` | Klargør og opsummerer revisionen (`revision_runde*.md`) |
| `PROMPT_*.md` | Instruktioner til skribent, fejlindsætning, model og revisor |
| `facit.json`, `t4_facit.json` | Facit (sags-id og kategorier, ingen sagstekst) |

## Pilot: betyder det noget at have kommunens oprindelige dokument? (9. okt. 2026)

Spørgsmål: (1) Er testene med rekonstruerede screeninger troværdige? (2) Giver originalen noget, nævnets
gengivelse ikke giver? Grundlag: de 8 ægte oprindelige dokumenter (T4).

| | Rekonstruktion (fra nævnets sagsfremstilling) | Original |
|---|---|---|
| Nævnets fejl blandt de prioriterede svagheder | 7/7 | 7/7 |
| Topfund | stort set samme punkter (fx E1/D2, A2, A3) | |

En Haiku-agent sammenlignede hver original med nævnets afgørelse (`PROMPT_SAMMENLIGN.md`):
- I **8/8** sager kan nævnets fejl forstås og findes ud fra afgørelsen alene; nævnet gengiver de dele af
  screeningen, fejlen handler om (helt i 2, delvist i 6).
- Originalerne indeholder **43 ekstra oplysninger** (18 vurderet af høj betydning), som afgørelsen ikke gengiver:
  konkrete tal (støjtabeller, afstande, arealer), interne modsigelser og svagheder, nævnet ikke tog stilling til.
  38 af 43 citater blev genfundet ordret.

**Konklusion:** rekonstruktionerne er en brugbar erstatning i test, så originalerne er ikke nødvendige for at
måle kvaliteten. Til gengæld er de værdifulde som opslag ved siden af afgørelsen. Derfor høstes de som et
link-indeks (sag → kommunens dokument), ikke som tekst i repoet.

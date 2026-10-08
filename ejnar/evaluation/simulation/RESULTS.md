# Praksissimulation – resultater

**Kørsel:** 29.09.2026. 8 sager skrevet af tre simulerede skadesbehandlere
(`cases.json`). Svarene blev skrevet af en Claude-agent, der spillede Ejnars
sprogmodel, og bedømt **blindt** (A/B i tilfældig rækkefølge) af en simuleret
juraprofessor og en simuleret teamleder i en skadesafdeling.

## Hvad simulationen fandt

| # | Fund | Rettet i |
|---|---|---|
| 1 | Kontekstbudgettet blev brugt på de første 3–4 kendelser. Kilde 5–15 stod i kilderegistret, men deres indhold nåede aldrig modellen. | 4f9f48f |
| 2 | Citatkontrollen gav 71 falske advarsler i 8 svar: forskudte anførselstegnspar, manglende typografiske anførselstegn, titler, brugerens eget spørgsmål og udeladelsestegn. Efter rettelsen: 0. | 232c1a8 |
| 3 | Svarene var for lange (940–1.140 ord). Nu starter de med "Kort svar" og er fokuserede. | 4f9f48f |
| 4 | "Afgørelseskernen" i lange kendelser var ofte en citeret ældre kendelse eller parternes argumenter. | 7ebc873 |
| 5 | Skadesbehandleren savnede en klar anbefaling og journalnumre ved kildehenvisningerne. | 0867eac |
| 6 | Professoren: udfald skal altid stå ved kilden, fordelinger må kun tælle sammenlignelige kendelser (vilkår, årsspænd), og spørgsmål med flere led skal besvares led for led. | se nedenfor |

## Blind A/B: runde 1 (før rettelse 1 og 3) mod runde 2 (efter)

| Bedømmer | Runde 2 vinder | Runde 1 vinder | Uafgjort |
|---|---|---|---|
| Juraprofessor | **6** | 1 | 1 |
| Skadesbehandler | **7** | 1 | 0 |

Juraprofessorens gennemsnit (1–5):

| Dimension | Runde 1 | Runde 2 |
|---|---|---|
| Retrieval | 2,50 | **4,62** |
| Korrekthed | 3,25 | **4,12** |
| Forankring i kilder | 3,50 | **4,88** |
| Praksissyntese | 4,12 | 4,00 |
| Konkrethed | 3,12 | **4,00** |

Begge bedømmere fremhævede, at forskellen skyldes kildegrundlaget og ikke
formuleringerne. Når begge svar havde alle kilder (S07, S08), var de næsten
lige gode.

## Udsagnsrevision: gengives praksis korrekt?

Ejnar er et praksisværktøj. Derfor er det vigtigste mål, om svarene gengiver
kendelserne korrekt. 12 rene praksisspørgsmål (`practice_cases.json`) blev
besvaret gennem den rigtige pipeline. Fire revisor-agenter efterprøvede derefter
hvert udsagn mod den kendelse, det henviser til (`claim_audit.py`).

| | Runde 1 | Runde 2 |
|---|---|---|
| Udsagn efterprøvet | 276 | 284 |
| Fuldt understøttet | 73,2 % | **79,6 %** |
| Mindst delvist understøttet | 94,6 % | 94,4 % |
| Modsagt af kilden | 6 | **4** |
| Forkert gengivet udfald (automatisk kontrol) | 0 | 0 |

**Fejl fundet i runde 1 og rettet før runde 2:**
- *Dækningsniveau (basis/udvidet):* detektoren fandt kun niveauet i 30 % af
  kendelserne og tog i nogle tilfælde fejl, fx når klager argumenterede ud fra
  udvidet dækning. Den læser nu først nævnets faste formulering om policen,
  inkl. resuméet, orddelte PDF-ord og nægtelser. Niveauet kendes nu i 51 %.
  Præcision i en blind stikprøve: Basis 15/15, Udvidet 14/15.
- *Parternes argumenter tilskrevet nævnet:* hver passage i konteksten er nu
  mærket som enten "Sagsfremstilling og parternes synspunkter" eller "Nævnets
  begrundelse og afgørelse". Prompten forbyder at tilskrive nævnet parternes
  synspunkter.
- *Én kendelse gjort til fast praksis:* prompten kræver nu flere kendelser bag
  en generel regel. Ellers skal svaret skrive "i én kendelse …".
- *Fagtermer:* "rodindvækst" står i 0 kendelser, mens nævnet skriver "rødder"
  (56 kendelser). Et lille fagleksikon oversætter termen, og "rødder" stemmes ikke
  længere sammen med farven "rød". Søgningen "rodindvækst kloak" gav før 1 og nu
  10 af 10 relevante kendelser i top-10.

**Fundet i runde 2 og rettet efterfølgende (ikke målt endnu):**
- Konteksten brugte kun de sidste 8.000 tegn af hver kendelse. Relevante
  passager tidligt i lange kendelser nåede derfor aldrig modellen. Nu kan hele
  kendelsen bidrage, og nævnets begrundelse prioriteres.
- Henvisninger som "[Kilde 2–8]" og "[Kilde 14, basisdækning]" blev ikke
  genkendt, hverken i appen eller i revisionen.

**Tilbageværende fejltyper:** svar, der tillægger nævnet et citat fra en del af
kendelsen, der ikke er med i uddraget, og for brede "kun/ingen"-udsagn om
kilderne. Metodeforbehold: revisorerne så et uddrag (faktum + nævnets
begrundelse), ikke hele kendelsen. Nogle "ikke understøttet" kan derfor stå i
den udeladte del.

### Runde 3 og ny revisionsmetode

Fra runde 3 ser revisorerne præcis de uddrag, modellen fik, samt nævnets egen vurdering
(`claim_audit.py pack`). Den gamle pakke undervurderede kvaliteten. Derfor er runde 2
revideret igen med den nye metode, så runde 2 og 3 kan sammenlignes:

| | Runde 2 (ny metode) | Runde 3 |
|---|---|---|
| Fuldt understøttet | 87,7 % | 87,2 % |
| Mindst delvist | 98,7 % | 99,0 % |
| Modsagt | 3 | 2 |
| Grundprincipper (bevisbyrde, skadesbegreb), andel af teksten | 5,1 % | 2,8 % |

Runde 3 tilføjede at nævnets vurdering skilles fra dets gengivelse af parterne,
kilderegister med udfald/dækning og færdig optælling, og at grundprincipper højst
nævnes kort. Nøjagtigheden er uændret (inden for støj), mens svarene bruger
halvt så meget plads på almen viden.

## Praksisfacit: 60 kildeforankrede spørgsmål

`gold_practice.py` + `ejnar/evaluation/gold_practice_v1/`. 60 kendelser (2012+,
spredt over mangeltyper; 24/18/18 ikke/delvis/medhold). For hver skrev en agent et
praksisspørgsmål og 2–4 nøglepunkter om, hvad nævnet lagde vægt på, hvert med et
ordret citat fra nævnets vurdering (maskinelt kontrolleret: 0 fejl). Ejnars rigtige
pipeline besvarede spørgsmålene, og bedømmere vurderede hvert nøglepunkt.

| | Før | Efter relevansvægtet kontekst |
|---|---|---|
| Facitkendelsen fundet og citeret | 58/60 | 58/60 |
| Nøglepunkter fuldt dækket | 62,5 % | **80,6 %** |
| Nøglepunkter mindst delvist | 85,8 % | **90,9 %** |
| Facitkendelsen gengivet forkert | 4 | **0** |

**Fund og rettelse:** facitkendelsen var kilde 1 i 50 af 60 spørgsmål, men fik kun
ca. 2.400 af 42.000 tegn i prompten, fordi pladsen blev fordelt ligeligt over 15–18
kilder. Når svaret fejlede, var det typisk "uddragene nævner ikke X", hvor nævnet
netop lagde vægt på X. Nu vægtes pladsen efter relevans (kilde 1: 3×, kilde 2–3: 2×),
og de ledende kilder får hele nævnets vurdering, når den kan være der. Facitkendelsen
får nu ca. 4.000 tegn, og prompten vokser kun 5 %.

**Forbehold:** Spørgsmålene er skrevet af agenter, der havde læst kendelsen. Søgningen
har derfor lettere ved at finde den end ved et rigtigt spørgsmål. Facit og bedømmelse
er lavet af AI. En fagpersons stikprøvekontrol af 10–15 facit anbefales (se
`gold_practice_v1/README.md`). Nogle svarfiler blev under kørslen omformateret af en
ukendt proces i miljøet. Bedømmerne vurderede de endelige filer.

## Omvendt facit: peger praksis i den rigtige retning?

Her er facit nævnets egen afgørelse og ikke en models vurdering (`reverse_gold.py`).
Testen brugte 20 tilfældige kendelser fra 2012 og frem, udtrukket stratificeret:
8 Ikke medhold, 6 Delvis medhold og 6 Medhold. Kun sagens faktum blev givet videre,
og en agent skrev et realistisk spørgsmål pr. sag. Selve kendelsen blev fjernet fra
korpus (leave-one-out), så svaret skulle bygge på *anden* praksis, præcis som ved en
ny sag.

| Mål | Resultat |
|---|---|
| Kildekendelsen fundet af søgningen (uden LLM) | top-1 16/20 · top-5 17/20 · top-15 18/20 |
| Udfald præcist rigtigt | **12/20** (naivt gæt "Ikke medhold": 8/20) |
| Retning rigtig (klager får noget / intet) | 15/20 |
| Recall pr. udfald | Ikke medhold 8/8 · Delvis 3/6 · Medhold 1/6 |
| Vægtet med korpusfordelingen (76 % / 13 % / 7,5 %) | **0,87** (naivt gæt: 0,79) |

**Tolkning.** Ejnar slår det naive gæt, men er forsigtig. Alle otte fejl
undervurderer klagers resultat. Det svarer til nævnets praksis, hvor klager får
intet i 3 ud af 4 sager, og for en skadesbehandler er det den rigtige side at fejle
på. I flere fejlsager (fx G20) pegede svaret selv på det delforhold, der endte med
at give klager delvis medhold. Kun den samlede konklusion ramte ved siden af.

**Fundne fejl, rettet:**
- Den paragraf-baserede kontekst (bruges ved præcise tekstsøgninger) manglede dato
  og udfald i kildeoverskriften. Modellen kunne derfor ikke opgøre praksis (G19).
- 10 kendelser havde scraperens fallback-dato (lørdag 09.05.2026) i stedet for
  afgørelsesdatoen. Et eksempel er AKF 62766 fra 2004. Datoen skønnes nu ud fra den
  seneste dato i kendelsens tekst eller ud fra nærmeste sagsnummer. Den vises som
  "ca." i kontekst, API (`date_estimated`) og UI.

## Forbehold

- Både svar-modellen og bedømmerne er Claude-modeller. Resultaterne peger på
  systematiske svagheder, men erstatter ikke en menneskelig juridisk review.
- Svarkvaliteten med billigere modeller (fx Gemini Flash) bør måles ved at køre
  trin 3 i `README.md` med den model.
- 8 sager er et lille udsnit. Kør simulationen igen efter større ændringer.

## Miljøjuristen (screeningstjek), oktober 2026

Den nye funktion Miljøjuristen (`miljoejurist/`) er testet separat: se
[`miljoejurist/evaluation/RESULTS.md`](../../../miljoejurist/evaluation/RESULTS.md). Kort: på 30 rekonstruerede
screeninger, som nævnene underkendte, pegede værktøjet (med sprogmodel) på nævnets egen begrundelse i 29;
95 % af de prioriterede fund var relevante, og kilderne bar påstanden i 91 % (revideret af en AI-revisor).
Uden sprogmodel finder regellaget kun omkring halvdelen og kan ikke skelne svage fra stærke screeninger.

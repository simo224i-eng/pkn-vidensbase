# Beslutninger (lokal session, oktober 2026)

Løbende log over de valg, der er truffet uden at spørge. Nyeste nederst.

## Setup
- **Projektnavn:** Værktøjet hedder **Miljøjuristen** (brugerens ønske: "miljøkonsulenten/miljøjuristen").
  Det bygges som modulet `ejnar/miljoejurist/` med egen fane i Ejnar-webappen, så det genbruger
  søgning, citatkontrol og server. Det deler intet med Harald.
- Navnet til trods giver værktøjet ikke juridisk rådgivning og skriver aldrig, at en afgørelse er i orden.
- Lokalt Python-miljø i `.venv/` (gitignoreret).

## Data
- **Nævnenes Hus' API kræver ingen cookie.** Kategori-id'er hentes fra `/api/sitesettings`, og
  `/api/search` returnerer hele afgørelsesteksten (HTML) i søgeresultatet, 100 pr. side. Derfor er
  `scrape_pkn.py` og `scrape_mfkn.py` skrevet om til det fælles modul `naevn_api.py`. Ingen
  enkeltsidehentning, ca. 1 forespørgsel pr. sekund.
- **Nye filer** ligger i `data_2026/` ved siden af de gamle filer i roden (som ikke er rørt).
  Format: `id, Naevn, Jnr, Dato, Titel, Link, Retsomraade, Tekst`. Teksten er ren tekst, hvor
  HTML-overskrifter står på egen linje med `## ` foran, så nævnets vurdering kan findes ved
  overskrift og ikke ved første forekomst i indholdsfortegnelsen.
- **Kategorier (PKN):** Miljøvurderingsloven, Planloven VVM, Planloven retlig og landzone (før og
  efter 1/2 2017), Sommerhusloven, Ekspropriation. Aktindsigt, Samlingssteds- og Kolonihaveloven er
  udeladt (ikke relevante for screeninger).
- **Kategorier (MFKN):** Miljøvurdering (projekter og planer), Husdyrbrugloven, Miljøbeskyttelsesloven,
  NBL (alle fire), Fredning, Råstof, Vandløb, Vandforsyning, Kystbeskyttelse, Skov, Jordforurening,
  Miljømål, Havmiljø, Museumsloven. Fødevarer, støtteordninger, dyrevelfærd, fiskeri, aktindsigt mv.
  er udeladt.
- **Lovgrundlag** hentes som XML fra retsinformation (ELI) med `fetch_lovgrundlag.py` til
  `lovgrundlag/`. Gældende versioner pr. 8/10/2026 ifølge retsinformations søgning: miljøvurderingsloven
  LBK 4/2023 (+ BEK 1375/2025 om bilag 2), miljøvurderingsbekendtgørelsen BEK 1608/2024,
  habitatbekendtgørelsen BEK 1098/2023, planloven LBK 572/2024, naturbeskyttelsesloven LBK 927/2024,
  husdyrbrugloven LBK 1065/2025 og vejledningerne 2024/9093 (projekter), 2024/9094 (planer),
  Habitatvejledningen 2020/9925, Landzonevejledningen og §3-vejledningen.
- **Forbehold:** LBK 4/2023 indarbejder ikke ændringslovene fra 2024–2026 (CO2, havvind, BBNJ m.fl.).
  De berører primært havområdet og energiprojekter; det står som kendt svaghed.
- **Bilag IV-vejledning:** Habitatvejledningen (2020/9925) er den officielle vejledning om bilag IV-arter
  på retsinformation. Miljøstyrelsens særskilte bilag IV-materiale hentes, hvis det kan findes som PDF.
- **Rensning (8/10 2026):** 28.668 rækker → 26.999 afgørelser efter sammenlægning af 949 id-dubletter
  (samme afgørelse i flere kategorier), 278 tekstdubletter og 442 tomme/korte tekster. 489 afgørelser
  havde tom brødtekst i API'et; teksten lå som PDF under "Dokumenter" og er hentet med
  `fetch_pdf_afgoerelser.py` (408 lykkedes). 800 tekster er markeret som mulige afkortninger (mest
  ældre "Naturklagenævnet orienterer" fra før 2014), de udelades ikke men kan filtreres.
- **Udfald** bestemmes først ud fra titlen (MFKN skriver "Stadfæstelse", "Ophævelse og hjemvisning",
  "Afvisning" osv.), derefter indledning og slutning. Mod de 858 model-mærkede sager fra v1 er
  overensstemmelsen ca. 93 %. Genoptagelse og opsættende virkning er "andet".
- **EU-domme:** de 30 hyppigst citerede (optalt én gang pr. afgørelse i miljø- og plansager) hentet på
  dansk fra EUR-Lex. C-474/19 og C-461/16 fandtes ikke som dansk dom og er sprunget over (næste på
  listen er taget i stedet).
- **Oprindelige screeninger:** en agent har søgt på plandata.dk og kommunernes hjemmesider for de
  nyeste underkendte screeningssager. Filerne ligger lokalt i `screeninger_originale/` (gitignoreret,
  fordi de kan indeholde navne på ansøgere); kun resultaterne af testen kommer i repoet.

## Analyse (punkt 3)
- **Univers:** miljøvurderingskategorierne i begge nævn fra 1/1 2020 + husdyrsager med medhold fra 2022,
  hvor nævnets vurdering handler om Natura 2000/bilag IV/§ 3 (55 sager). I alt 1.050 sager.
- **Trin 1 genbruges** fra v1 for de 893 sager, der allerede var mærket; kun de 157 nye er mærket (Haiku).
- **Trin 2 er lavet om for alle sager med medhold** (283) med Sonnet og HELE afgørelsesteksten, ikke
  9.000 tegn. Flere fejl pr. sag registreres, med kategori, regel, ordret citat fra nævnet og (hvis det
  findes) ordret citat af myndighedens egen tekst. Alle citater er maskinkontrolleret: 539/539 ok.
- Kategorilisten er udvidet (natur_paragraf3, afvaergeforanstaltninger, materiel_vaesentlighed,
  plan_forhold, kompetence_procedure), fordi v1's "andet" var den største kategori.

## Tjekliste (punkt 4)
- 21 punkter i 7 grupper (19 fra start, A4 og B3 tilføjet efter testrunde 2), skrevet ud fra lov og vejledning (`ejnar/miljoejurist/tjekliste_grund.py`) og
  koblet automatisk til praksis (`byg_tjekliste.py`). Lovuddrag kontrolleres for at stå ordret.
- Vejledningsafsnit er valgt i hånden pr. punkt (fx 4.5.2.1 "Screeningskriterierne i bilag 6"), fordi
  automatisk søgning ramte afsnit om fx opsættende virkning.
- EU-domme: for de vigtigste punkter er præmissen valgt ved en ordret frase (C-127/02 præmis 45,
  C-323/17 præmis 37, C-473/19 præmis 83, C-142/07 præmis 44), ellers ved søgning i punktets domme.

## Værktøj (punkt 5)
- **To lag:** et regellag, der altid kører uden nøgler, og et valgfrit modellag via Ejnars udskiftelige
  LLM-udbyder. Modellens citater kontrolleres automatisk; fund med citater, der ikke står ordret, fjernes.
  Ingen betalte nøgler er brugt i udvikling og test: i testen spiller en agent modellen og får præcis
  den prompt, appen sender (`llm_tjek.byg_prompt`).
- **Aldrig frikendelse:** rapportens egne tekster filtreres for formuleringer som "er i orden", "er lovlig",
  "ingen fejl" (`tjek.FORBUDT`), og en tom rapport siger, at kontrollerne ikke slog ud – ikke at
  afgørelsen holder.
- **Prioritering (efter runde 1):** højst 6 fund vises som "svagheder", resten som "øvrige
  opmærksomhedspunkter". Konstateringen af, at noget ikke er nævnt, vægter lavere end en konkret svag
  formulering med citat.

## Test (punkt 6)
- Testen ligger i `ejnar/evaluation/miljoejurist/` med resultater i `RESULTS.md` dér (og et kort afsnit i
  `ejnar/evaluation/simulation/RESULTS.md`). Arbejdsfiler med sagstekster ligger i `work/` (gitignoreret).
- **T1:** 30 underkendte screeninger rekonstrueret af en agent, der KUN så sagsfremstillingen (nævnets
  vurdering, indledning og titel fjernet). Sagens egen afgørelse udelukkes fra praksissøgningen.
- **T2:** 20 stadfæstede screeninger (rekonstrueret på samme måde) med én indsat fejl af en kendt type.
- **T3:** de samme 20 stadfæstede screeninger uden ændringer (falske alarmer).
- **T4:** 8 ægte oprindelige screeninger/planforslag fundet online (sikkerhed høj/middel/lav for, at det er
  netop den behandlede version).
- Skribenter, model-agenter og revisorer ser blinde id'er (R01…, X01…, Y01…), så de ikke kender gruppen.
- **Revision:** en revisor-agent (Sonnet) vurderer hvert fund: læst korrekt? relevant? bærer kilderne?
  matcher det nævnets begrundelse/den indsatte fejl? Samme revisormodel i alle runder for sammenlignelighed.
- **Testen stoppede efter runde 4**, fordi runde 4 (strammere prompt mod falske alarmer) ikke var bedre end
  runde 3 (færre fundne fejl i T1/T2). Koden er sat tilbage til runde 3's modellag.

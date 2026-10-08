# Tjekliste: screeninger, miljørapporter og VVM-tilladelser

Bygget automatisk af `ejnar/miljoejurist/byg_tjekliste.py` ud fra miljøvurderingsloven, habitatbekendtgørelserne, vejledningerne og nævnenes underkendelser (trin 2-analysen i `analyser/miljoevurdering/v2/`). Alle citater fra lov, vejledning og afgørelser er kontrolleret maskinelt for, at de står ordret i kilden.

**Grundlag:** 239 sager fra 2020–2026, hvor PKN eller MFKN helt eller delvist gav klager medhold, og hvor nævnets begrundelse kunne citeres ordret.

**Skal gennemgås af en fagperson før brug.** Tjeklisten er et arbejdsredskab; den erstatter ikke en juridisk vurdering, og at alle punkter er besvaret, betyder ikke, at en afgørelse holder.

## Hyppigste fejltyper i underkendte sager

| Fejlkategori | Sager |
|---|---|
| sagsoplysning_dokumentation | 73 |
| vilkaar | 51 |
| afvaergeforanstaltninger | 50 |
| bilagIV_arter | 45 |
| kompetence_procedure | 44 |
| omfattet_bilag_projektbegreb | 38 |
| natura2000_vaesentlighed | 33 |
| screeningskriterier_ikke_vurderet | 25 |
| plan_forhold | 23 |
| miljoerapport_mangelfuld | 20 |
| natur_paragraf3 | 19 |
| materiel_vaesentlighed | 16 |
| afgraensning_opsplitning | 15 |
| kumulation | 12 |
| begrundelse | 11 |
| hoering_inddragelse | 10 |
| andet | 7 |

## Omfattet og afgrænsning

### A1. Korrekt placering i lovens bilag og projektbegreb
**Spørgsmål:** Er det begrundet, hvilket punkt i bilag 1 eller 2 projektet hører under (eller hvorfor det ikke er omfattet), herunder om der er tale om en ændring eller udvidelse (bilag 2, pkt. 13)?  
**Gælder:** Screening af projekt, § 25-tilladelse  
**Underkendt i praksis:** 14 sager (kategori: omfattet_bilag_projektbegreb)

**Lovgrundlag:**
- [Miljøvurderingsloven § 16](https://www.retsinformation.dk/eli/lta/2023/4): «Et projekt omfattet af bilag 2 må ikke påbegyndes»
- [Miljøvurderingsloven § 21](https://www.retsinformation.dk/eli/lta/2023/4): «afgørelse om, hvorvidt et projekt omfattet af bilag 2»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Også ændringer og udvidelser af projekter på bilag 1 eller 2 kan være omfattet af bilag 2 dvs. være screeningspligtige, jf. lovens bilag 2, punkt 13 a.»

**Eksempler fra nævnene:**
- [MFKN 2026-07-02](https://mfkn.naevneneshus.dk/afgoerelse/5ba79c70-ea6c-4a17-a991-4e33c87796d4) – Kommunen vurderede, at inddragelsen af støj fra skibsanløb (som overskrider de vejledende støjgrænser) ikke var en ændring omfattet af miljøvurderingsloven, og screenede ikke ændringen efter bilag 6.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at projektet er omfattet af miljøvurderingslovens bilag 2, punkt 13, litra a, og at projektet derfor skulle have været screenet i henhold til kriterierne i miljøvurderingslovens bilag 6.»
- [MFKN 2026-05-18](https://mfkn.naevneneshus.dk/afgoerelse/20ab54ba-0499-47c5-a98c-576e62674718) – Kommunen afgjorde, at rørlægning af 44 m vandløb som ændring af et allerede miljøgodkendt byudviklingsprojekt ikke var omfattet af miljøvurderingsloven, uden at screene ændringen efter bilag 6.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at projektet er omfattet af miljøvurderingslovens bilag 2, pkt. 13, litra a, og at projektet derfor skulle have været screenet i henhold til kriterierne i miljøvurderingslovens bilag 6.»
  Myndigheden havde skrevet: «Kommunen har vurderet, at rørlægningen ikke har skadelige indvirkninger på miljøet, hvorfor ændringerne ikke skal screenes efter miljøvurderingslovens bilag 2, pkt. 13, litra a»
- [MFKN 2026-05-08](https://mfkn.naevneneshus.dk/afgoerelse/ace326cd-76a6-4aa3-9580-3b1777d85e7c) – Kommunen afgjorde, at sundhedshus og 17 boliger i byzone ikke var omfattet af miljøvurderingsloven og undlod screening, selvom projektet falder under bilag 2, pkt. 10, litra b (anlægsarbejder i byzoner).  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at projektet er omfattet af miljøvurderingslovens bilag 2, punkt 10, litra b, og at projektet derfor skulle have været screenet i henhold til kriterierne i miljøvurderingslovens bilag 6.»
  Myndigheden havde skrevet: «Kommunen har skønnet, at det er unødvendigt at træffe en formel afgørelse om vurderingen, idet det synes klart, at projektet ikke kan antages at få væsentlig indvirkning på miljøet.»
- [MFKN 2025-12-02](https://mfkn.naevneneshus.dk/afgoerelse/26bac803-90db-4328-a0f7-c5cae0a3a8dc) – Kommunen afgjorde, at omlægning af to tennisbaner til tre padelbaner (med nye glasindhegninger, højere lysmaster og anden støjtype) slet ikke var omfattet af miljøvurderingsloven, i stedet for at screene det som en ændring af et bilag 2-projekt.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at projektet om at omlægge to tennisbaner til tre padeltennisbaner er omfattet af miljøvurderingslovens bilag 2, punkt 13, litra a. Ændringen skulle derfor have været screenet i henhold til kriterierne i miljøvurderingslovens bilag 6.»
  Myndigheden havde skrevet: «Kommunen har truffet afgørelse om, at ombygningen ikke skal screenes i henhold til miljøvurderingslovens regler.»

### A2. Hele projektet er vurderet (ingen opsplitning)
**Spørgsmål:** Omfatter screeningen hele projektet, inkl. tilhørende anlæg, veje, ledninger, anlægsfase, drift og senere etaper, så projektet ikke er opsplittet?  
**Gælder:** Screening af projekt, § 25-tilladelse, Screening af plan  
**Underkendt i praksis:** 13 sager (kategori: afgraensning_opsplitning)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «hele projektets dimensioner og udformning»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Derfor vil det være i strid med lovens formål at opdele projekter i et antal separate projekter med henblik på, at delprojekterne hver for sig ikke overskrider den fastsatte tærskelværdi eller ved en screening ikke anses for at have en væsentlig indvirkning på miljøet og derfor ikke kræver en miljøvurdering. [55]»

**Eksempler fra nævnene:**
- [MFKN 2026-09-28](https://mfkn.naevneneshus.dk/afgoerelse/3e959c0c-a2be-487b-999e-bee51badab44) – Kommunen screenede kun skovrydningen og ikke det samlede projekt med byggemodning og boliger, som er forbundne projekter.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at screeningsafgørelsen efter miljøvurderingslovens § 21 også skal inddrage den del af projektet, der vedrører byggemodningen og den efterfølgende opførelse af boliger, da det er forbundne projekter. Afgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2025-08-08](https://mfkn.naevneneshus.dk/afgoerelse/56149a35-d986-4eb8-b45f-9c1497aa9803) – Projektet blev behandlet i to separate byggetilladelser, selv om det udgør ét samlet projekt (fortløbende bloknumre, samlet etageareal, fælles veje og parkering, samtidig ansøgning).  
  Nævnet: «Miljø- og Fødevareklagenævnet finder indledningsvist, at det ved de to byggetilladelser tilladte byggeri skal anses for ét samlet projekt efter miljøvurderingsloven.»
- [MFKN 2025-05-27](https://mfkn.naevneneshus.dk/afgoerelse/0a8994d5-3257-4c07-abaf-bcfa6133332f) – Kommunen udelod de forberedende anlægsarbejder (kabelomlægning, fjernelse af forurenet jord m.m.) fra screeningen, selvom de er en integreret del af hovedprojektet, og vurderede dermed ikke projektet som helhed.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at det er en væsentlig retlig mangel ved screeningsafgørelsen efter miljøvurderingslovens § 21, at Frederiksberg Kommune ikke har inddraget påvirkningen fra de forberedende arbejder inden selve anlæggelsen af lynladestationen.»
  Myndigheden havde skrevet: «Af screeningsafgørelsen fremgår det, at screeningen ikke omfatter de forberedende arbejder inden selve anlæggelsen af lynladestationen, herunder omlægning af kabler, fjernelse af forurenet jord, bortskaffelse af betonplader, fjernelse af buskads mv.»
- [MFKN 2024-06-27](https://mfkn.naevneneshus.dk/afgoerelse/42953eb1-5ef5-472d-a281-11bc7ea612a0) – Nævnet anførte, at de fremtidige udledninger, som er baggrunden for udvidelsen af grøften, bør overvejes inddraget; risiko for opdeling af nødvendigt forbundne projekter og manglende kumulation.  
  Nævnet: «Aalborg Kommune bør på den baggrund ved den fornyede behandling af sagen overveje at inddrage de fremtidige udledninger, som er baggrunden for udvidelsen af Svanholmgrøften, i vurderingen.»

### A3. Planen: miljøvurdering eller screening (§ 8)
**Spørgsmål:** Er det vurderet, om planen fastlægger rammer for projekter i bilag 1 eller 2, og om den kun fastlægger anvendelsen af mindre områder på lokalt plan (§ 8, stk. 2, nr. 1)?  
**Gælder:** Screening af plan  
**Underkendt i praksis:** 13 sager (kategori: omfattet_bilag_projektbegreb)

**Lovgrundlag:**
- [Miljøvurderingsloven § 8](https://www.retsinformation.dk/eli/lta/2023/4): «fastlægger rammerne for fremtidige anlægstilladelser»
- [Miljøvurderingsloven § 8](https://www.retsinformation.dk/eli/lta/2023/4): «kun fastlægger anvendelsen af mindre områder på lokalt plan»

**Vejledning:**
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Når myndigheden skal foretage en screening af en plan/program, sker dette på grundlag af kriterierne i lovens bilag 3.»

**Eksempler fra nævnene:**
- [PKN 2026-06-02](https://pkn.naevneneshus.dk/afgoerelse/9e1a5f30-b797-48a3-b3c6-e7e53f85b760) – Kommunen screenede lokalplan og kommuneplantillæg for et boligområde på ca. 19 ha med 150-350 boliger som en plan for et mindre område på lokalt plan, selvom planerne krævede obligatorisk miljøvurdering.  
  Nævnet: «Nævnet finder, at der ikke er tale om planer, der fastlægger anvendelsen af et mindre område på lokalt plan, eller som alene indeholder mindre ændringer. Nævnet lægger herved vægt på, at et planområde på ca. 19 ha ikke i den konkrete sag kan anses som et område af begrænset størrelse set i forhold til kommunens samlede areal.»
- [PKN 2025-11-11](https://pkn.naevneneshus.dk/afgoerelse/16930ba0-9931-4272-88f5-3c5d1d5b4fee) – Kommunen screenede den lokale del af kommuneplan 2025 og konkluderede, at der ikke skulle miljøvurderes, selvom planen omfatter hele kommunen og indeholder mere end mindre ændringer (nye retningslinjer, rammeområder og rammebestemmelser, 40 indarbejdede tillæg hvoraf kun syv var miljøvurderet). Planen var derfor omfattet af obligatorisk miljøvurdering.  
  Nævnet: «Planklagenævnet bemærker, at forslaget til den lokale del af kommuneplan 2025 omfatter hele Vejle Kommunes areal, hvorfor der ikke er tale om en plan, der fastlægger anvendelsen af et mindre område på lokalt plan.»
  Myndigheden havde skrevet: «Set i forhold til den samlede kommuneplan er der tale om mindre ændringer, der primært har karakter af opdatering og tilpasning.»
- [PKN 2025-10-10](https://pkn.naevneneshus.dk/afgoerelse/1c222e8f-6408-4e44-ae78-70c5661c5cf7) – Kommunen screenede forslag til kommuneplan 2025 for hele kommunen, selvom planen fastlægger rammer for bilag 2-projekter og hverken omfatter et mindre område på lokalt plan eller alene mindre ændringer, så der skulle have været gennemført en obligatorisk miljøvurdering.  
  Nævnet: «Planklagenævnet finder på baggrund af ovenstående, at der skal gennemføres en miljøvurdering af forslaget til kommuneplan, jf. miljøvurderingslovens § 8, stk. 1, nr. 1, hvilket ikke er sket. Dette udgør en væsentlig retlig mangel ved screeningsafgørelsen, som medfører ugyldighed.»
- [MFKN 2025-07-11](https://mfkn.naevneneshus.dk/afgoerelse/6a617c9f-7b68-4a81-9275-5f11dc347631) – Kommunen afgjorde ved screening, at vandforsyningsplanen ikke var omfattet af krav om miljøvurdering, selvom planen fastlægger rammerne for fremtidige tilladelser til projekter i bilag 1 og 2 (nye boringer, indvindingstilladelser, vandingsprojekter) og dermed er omfattet af obligatorisk miljøvurderingspligt.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Vandforsyningsplan 2024-2034 er omfattet af miljøvurderingslovens § 8, stk. 1, nr. 1, idet den udarbejdes inden for vandforvaltning og fastlægger rammerne for fremtidige anlægstilladelser til de projekter, der er omfattet af bilag 1 og 2. Planen er således omfattet af obligatorisk miljøvurderingspligt.»
  Myndigheden havde skrevet: «Det fremgår af afgørelsen, at det er Norddjurs Kommunes vurdering, at vandforsyningsplanen ikke vil påvirke miljøet væsentligt.»

### A4. Screening efter, at projektet er påbegyndt (lovliggørelse)
**Spørgsmål:** Er projektet helt eller delvist gennemført før screeningen? Så skal sagen behandles som lovliggørelse, og vurderingen skal også omfatte indvirkningerne siden gennemførelsen.  
**Gælder:** Screening af projekt, § 25-tilladelse  
**Underkendt i praksis:** 3 sager (kategori: kompetence_procedure, omfattet_bilag_projektbegreb)

**Lovgrundlag:**
- [Miljøvurderingsloven § 16](https://www.retsinformation.dk/eli/lta/2023/4): «må ikke påbegyndes, før myndigheden»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Denne adgang er dog ifølge Domstolen betinget af, at de nationale bestemmelser, der tillader en sådan lovliggørelse, ikke giver de berørte anledning til at omgå EU-reglerne eller til at undlade at anvende dem, og at vurderingen foretaget med henblik på lovliggørelse ikke kun begrænses til projektets fremtidige indvirkninger på miljøet, men også tager de indvirkninger på miljøet, der har været siden projektets gennemførelse, i betragtning. [103]»
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Efter lovens § 55, stk. 2 og 3, kan tilsynsmyndigheden på ejerens bekostning lade et påbud om at berigtige et ulovligt forhold tinglyse på ejendommen.»

**Eksempler fra nævnene:**
- [MFKN 2025-08-25](https://mfkn.naevneneshus.dk/afgoerelse/8cad826e-67b6-49f3-b2f0-aa9b85eb85a7) – Screeningen blev først foretaget efter projektets gennemførelse som lovliggørelse, hvilket kræver at også de indvirkninger, der har været siden gennemførelsen, tages i betragtning (C-196/16 og C-197/16).  
  Nævnet: «Miljø- og Fødevareklagenævnet konstaterer, at vurderingen er foretaget efter projektets gennemførelse. Forudsætningen om, at screening skal være gennemført inden projektets påbegyndelse, er derfor ikke opfyldt, og nævnet finder på den baggrund, at Tønder Kommunes screeningsafgørelse skal betragtes som en afgørelse om lovliggørelse af den manglende forudgående screening.»
- [MFKN 2025-05-27](https://mfkn.naevneneshus.dk/afgoerelse/0a8994d5-3257-4c07-abaf-bcfa6133332f) – Screeningen blev foretaget efter projektets påbegyndelse (støbning af fundamenter), og kommunen behandlede den ikke som lovliggørelse, hvor allerede udførte forhold også skal inddrages.  
  Nævnet: «Miljø- og Fødevareklagenævnet konstaterer indledningsvist, at vurderingen er foretaget efter projektets påbegyndelse.»
- [MFKN 2020-07-14](https://mfkn.naevneneshus.dk/afgoerelse/96327b5a-fe53-42f8-81da-4b27b1221043) – Kommunen screenede skovrydningen efter dens gennemførelse uden at tage EU-rettens betingelser for lovliggørelse i betragtning, herunder indvirkninger siden gennemførelsen.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Silkeborg Kommune ikke har taget disse betingelser for lovliggørelse i betragtning. På den baggrund lider Silkeborg Kommunes afgørelse af en væsentlig retlig mangel, og kommunen skal derfor ved sagens genbehandling endvidere forholde sig til de indvirkninger på miljøet, der har været siden projektets gennemførelse.»

## Oplysningsgrundlag

### B1. Tilstrækkeligt oplysningsgrundlag
**Spørgsmål:** Bygger vurderingerne på konkrete oplysninger (ansøgningens bilag 5-oplysninger, kort, beregninger, registreringer), og fremgår det, hvor oplysningerne kommer fra?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 44 sager (kategori: sagsoplysning_dokumentation)

**Lovgrundlag:**
- [Miljøvurderingsloven § 19](https://www.retsinformation.dk/eli/lta/2023/4): «indgive en skriftlig ansøgning»
- [Miljøvurderingsloven bilag 5](https://www.retsinformation.dk/eli/lta/2023/4): «Oplysninger fra bygherren»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «a) 1) Oplysninger om projektets karakteristika og dets forventede væsentlige indvirkninger på miljøet, jf. bilag 5.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Nævnet har navnlig lagt vægt på, at kommunen har foretaget besigtigelse af området og desuden foretaget screeningen på baggrund af eksisterende kendte oplysninger om området, hvilket må anses for tilstrækkeligt i forbindelse med screening af den konkrete plan.»

**Eksempler fra nævnene:**
- [MFKN 2026-06-23](https://mfkn.naevneneshus.dk/afgoerelse/b650aeb0-ca3e-4f84-8d23-dd8bc3485c65) – Kommunen havde ikke tilstrækkeligt grundlag for at vurdere, om overløb fra regnvandsbassinerne (ca. hvert femte år) giver en midlertidig forringelse af Bygholm Å nedstrøms udløbet af Hatting Bæk, hvor kobber allerede er ikke-god tilstand. Overløbets betydning var ikke beskrevet i miljøkonsekvensrapporten eller den begrundede konklusion, og kommunens beregninger var ikke retvisende.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Horsens Kommune for tidspunktet for § 25-tilladelsen ikke havde et tilstrækkeligt grundlag for at foretage en vurdering af, om projektet vil kunne medføre en forringelse af Bygholm Å nedstrøms udløbet af Hatting Bæk, for så vidt angår kobber i forbindelse med en overløbssituation.»
- [MFKN 2026-03-31](https://mfkn.naevneneshus.dk/afgoerelse/fbc0dfbd-c00a-4eef-ad30-8284d315404d) – BEST-beregningen brugte en pumpetid (33 %) der ikke afspejlede tilladelsens vilkår (ingen daglig maksimal indvindingsmængde), og to rapporter havde forskellige pumpetider; påvirkningen kan være underestimeret.  
  Nævnet: «Nævnet vil derfor ikke på den baggrund kunne vurdere, hvorvidt kommunens vurderinger i afgørelsen afspejler den reelle påvirkning af vandløbene ved den ansøgte og tilladte indvinding, idet de beregnede påvirkninger potentielt er underestimeret.»
- [PKN 2025-10-10](https://pkn.naevneneshus.dk/afgoerelse/1c222e8f-6408-4e44-ae78-70c5661c5cf7) – Kommunen lagde vægt på, at ændringerne medfører mindre indvirkninger end kommuneplan 2021, og tog ikke højde for at tidligere kommuneplaner og de fleste indarbejdede tillæg aldrig var miljøvurderet.  
  Nævnet: «Nævnet bemærker i den forbindelse, at der ikke ses at være gennemført en miljøvurdering af kommuneplan 2021 for Gladsaxe Kommune, hvilket også er tilfældet for kommuneplan 2017.»
- [MFKN 2025-09-15](https://mfkn.naevneneshus.dk/afgoerelse/543afe92-3d31-41eb-9c17-362f3b609913) – Screeningen vurderede projektet ud fra det tilladte antal årlige operationer (25.000) frem for de faktiske, lovlige aktiviteter (højst 12.617 i 2018-2023), så konklusionen om mindre belastning af naboer, flagermus og mosehornugle hvilede på et forkert grundlag.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Herning Kommunes screeningsafgørelse er truffet på et forkert grundlag. Afgørelsen lider derfor af en væsentlig retlig mangel.»

### B2. Høring af berørte myndigheder
**Spørgsmål:** Er berørte myndigheder hørt før afgørelsen, og er deres bemærkninger inddraget (§ 32 for planer, § 35 for projekter)?  
**Gælder:** Screening af plan, Miljørapport (plan)  
**Underkendt i praksis:** 5 sager (kategori: hoering_inddragelse)

**Lovgrundlag:**
- [Miljøvurderingsloven § 32](https://www.retsinformation.dk/eli/lta/2023/4): «skal sikre, at følgende informeres tidligt i beslutningsprocessen»
- [Miljøvurderingsloven § 10](https://www.retsinformation.dk/eli/lta/2023/4): «resultaterne af høringerne efter § 32»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Fristen for høring af berørte myndigheder fremgår af lovens § 35, som herefter er en ’passende frist’, jf. lovens § 35, stk. 5.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Berørte myndigheder kan være såvel interne som eksterne i forhold til den myndighed, der er ansvarlig for planen/programmet eller som skal træffe afgørelse om tilladelse til de projekter, som planen eller programmet fastlægger rammerne for.»

**Eksempler fra nævnene:**
- [PKN 2024-09-27](https://pkn.naevneneshus.dk/afgoerelse/0ea6df70-cea2-4a20-86c9-d23fccbe3fcb) – Kommunen tilføjede ved den endelige vedtagelse af kommuneplanen en bestemmelse i rammen (kun tre åben-lave boliger på den ubebyggede matrikel) uden at give den berørte grundejer lejlighed til at udtale sig, selv om ændringen berørte grundejeren væsentligt.  
  Nævnet: «Kommunens endelige vedtagelse af planen er derfor i strid med planlovens § 27, stk. 2, 2. pkt.»
- [PKN 2024-05-28](https://pkn.naevneneshus.dk/afgoerelse/491b63ec-0d3b-40ac-b5a8-fcdeb6160562) – Der var ikke gennemført en separat høring af berørte myndigheder om afgrænsningen af miljørapporten for planerne; afgrænsningen for miljøkonsekvensrapporten blev genbrugt.  
  Nævnet: «Nævnet bemærker endvidere, at der ikke ses at være gennemført en høring vedrørende afgrænsning af miljørapporten i overensstemmelse med miljøvurderingslovens § 32.»
- [MFKN 2023-12-21](https://mfkn.naevneneshus.dk/afgoerelse/a89731ae-5597-44b4-a8bf-5cea7e4c059d) – Kommunen offentliggjorde alene miljørapporten og ikke den vedtagne plan og den sammenfattende redegørelse.  
  Nævnet: «Vordingborg Kommune har alene offentliggjort miljørapporten den 12. august 2021.»
- [PKN 2023-02-22](https://pkn.naevneneshus.dk/afgoerelse/287757e8-a7e5-4aeb-ab54-d7ccf5890ab8) – Den supplerende miljøvurdering om Natura 2000-fugle og bilag IV-arter, der indeholdt nye oplysninger og vurderinger, blev udarbejdet efter høringen og ikke sendt i offentlig høring før vedtagelsen.  
  Nævnet: «Planklagenævnet finder på baggrund af ovenstående, at høringsproceduren ikke er foregået i overensstemmelse med miljøvurderingslovens krav om offentlig høring, jf. § 32, stk. 1-4.»

### B3. Rigtigt udgangspunkt for vurderingen (referencetilstand)
**Spørgsmål:** Tager vurderingen udgangspunkt i de faktiske forhold før projektet (ikke forholdene efter en allerede gennemført ændring eller en tidligere tilladt, men ikke udnyttet, mængde)?  
**Gælder:** Screening af projekt, § 25-tilladelse  
**Underkendt i praksis:** 7 sager (kategori: sagsoplysning_dokumentation, omfattet_bilag_projektbegreb)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «hele projektets dimensioner og udformning»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Som allerede anført i afsnit 2.1 bør de kompetente myndigheder, når de afgør, om ændringer eller udvidelser af visse bilag I og bilag II-projekter skal undergives en vurdering, tage hensyn til VVM-direktivets hovedformål, dvs. at projekter, der bl.a. på grund af deres art, dimensioner eller placering kan forventes at få væsentlig indvirkning på miljøet, inden der gives tilladelse, undergives en forudgående vurdering af deres virkninger, omfang og formål.»

**Eksempler fra nævnene:**
- [MFKN 2025-09-15](https://mfkn.naevneneshus.dk/afgoerelse/543afe92-3d31-41eb-9c17-362f3b609913) – Screeningen vurderede projektet ud fra det tilladte antal årlige operationer (25.000) frem for de faktiske, lovlige aktiviteter (højst 12.617 i 2018-2023), så konklusionen om mindre belastning af naboer, flagermus og mosehornugle hvilede på et forkert grundlag.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Herning Kommunes screeningsafgørelse er truffet på et forkert grundlag. Afgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2025-02-12](https://mfkn.naevneneshus.dk/afgoerelse/32fa2ae8-82ff-4933-ad39-c6636e4ba44c) – Kommunen havde ikke fastlagt, at flagermus-vurderingen skulle bygge på worst case eller en nærmere konkret undersøgelse af, om de to bygninger faktisk var yngle- eller rasteområder.  
  Nævnet: «Ved en fornyet behandling bør Odder Kommune i forhold til arter af flagermus enten fuldt ud behandle projektet ud fra et worst case-scenarium om, at der er yngle- eller rasteområder, der vil blive nedlagt som følge af projektet, eller foretage en nærmere konkret vurdering af, om der er yngle- eller rasteområder i projektområdet.»
- [MFKN 2025-01-29](https://mfkn.naevneneshus.dk/afgoerelse/f5c80a87-5378-433c-9a3b-ceb3727c7475) – Kommunen screenede fornyelsen af en indvindingstilladelse ud fra den tidligere tilladte indvindingsmængde (17.000 m3/år) i stedet for de faktiske indvindinger (maks. 12.200 m3/år siden 2012). En tilladelse på 14.400 m3/år var dermed en stigning i forhold til de faktiske forhold, og påvirkningen af vandløbet blev vurderet som reduceret på et forkert grundlag.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Ikast-Brande Kommunes screeningsafgørelse er truffet på et forkert grundlag, da grundlaget for afgørelsen er den tidligere tilladte indvindingsmængde og ikke de tidligere faktiske indvindingsmængder. Afgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2024-11-25](https://mfkn.naevneneshus.dk/afgoerelse/b14c35cb-5c6f-43f0-ac20-58030b176053) – Kommunen screenede grundvandsindvinding med udgangspunkt i de tidligere tilladte indvindingsmængder (55.000 m3) og ikke de faktiske indvundne mængder (maks. 43.000 m3), så projektet fejlagtigt fremstod som en reduktion; vurderingen af påvirkning af § 3-natur, bilag IV-arten spidssnudet frø og boringer hvilede på dette forkerte grundlag.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Silkeborg Kommunes screeningsafgørelse er truffet på et forkert grundlag, da grundlaget for afgørelsen er de tidligere tilladte indvindingsmængder og ikke de tidligere faktiske indvindingsmængder. Afgørelsen lider derfor af en væsentlig retlig mangel.»

## Screeningskriterier

### C1. Alle relevante kriterier i bilag 6 (projekter) er vurderet
**Spørgsmål:** Er hvert relevant kriterium i bilag 6 (projektets karakteristika, placering og påvirkningens art) vurderet konkret, og er afgørelsen begrundet med henvisning til dem?  
**Gælder:** Screening af projekt  
**Underkendt i praksis:** 22 sager (kategori: screeningskriterier_ikke_vurderet, begrundelse)

**Lovgrundlag:**
- [Miljøvurderingsloven § 21](https://www.retsinformation.dk/eli/lta/2023/4): «Ved vurderingen skal myndigheden tage hensyn til kriterierne i bilag 6»
- [Miljøvurderingsloven § 21](https://www.retsinformation.dk/eli/lta/2023/4): «henvisning til de i bilag 6 opførte relevante kriterier»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Nævnet påpegede, at et af screeningskriterierne vedrører projektets karakteristika, som efter bilag 6, pkt. 1, litra a, blandt andet skal anskues i forhold til ”hele” projektets dimensioner og udformning.»

**Eksempler fra nævnene:**
- [MFKN 2026-09-28](https://mfkn.naevneneshus.dk/afgoerelse/3e959c0c-a2be-487b-999e-bee51badab44) – Flere miljøpåvirkninger (vand, affald, støv, lys) blev ikke vurderet, fordi de ikke var aktuelle for træfældningen, selvom bilag 6-kriterierne skal vurderes for hele projektet.  
  Nævnet: «Nævnet har lagt vægt på, at det fremgår eksplicit af afgørelsen, at der ikke er foretaget en vurdering af påvirkningerne i forhold til bl.a. vand, affald, støv- og lysgener.»
- [MFKN 2025-08-25](https://mfkn.naevneneshus.dk/afgoerelse/8cad826e-67b6-49f3-b2f0-aa9b85eb85a7) – Kommunen vurderede ikke konkret, hvad udledning af tag- og overfladevand fra regnvandsbassinet betyder for Smedebæk og dens miljømål (kobber og zink overskrider allerede miljøkvalitetskrav); den henviste blot til, at vandet ikke indeholder andet end sædvanligt overfladevand.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Tønder Kommune i forbindelse med screeningsafgørelsen ikke har foretaget en tilstrækkelig vurdering af projektets påvirkning af Smedebæk og vandløbets miljømål. Screeningsafgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2025-08-14](https://mfkn.naevneneshus.dk/afgoerelse/9a2269be-1c3a-4924-b77d-624797b47719) – Kommunen vurderede ikke konkret udledningens betydning for Landbækken og dens kvalitetselementer, selvom vandløbet ikke opfyldte miljømålet; kriteriet om vandets relative kvalitet og områder med overskredne miljøkvalitetsnormer var ikke vurderet i screeningen.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Aalborg Kommune i forbindelse med screeningsafgørelsen ikke har foretaget en tilstrækkelig vurdering af projektets påvirkning af Landbækken og vandløbets miljømål. Screeningsafgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2024-09-20](https://mfkn.naevneneshus.dk/afgoerelse/41dd7e7a-f67d-43ae-a941-b09237530ed2) – Kommunen vurderede støjpåvirkningen, men inddrog ikke tilstrækkeligt, om støjgrænserne overskrides, og screeningens øvrige parametre som hyppighed og varighed. Projektet var heller ikke færdigprojekteret.  
  Nævnet: «Kommunen bør inddrage, om de vejledende støjgrænser overskrides samt screeningens øvrige parametre som f.eks. hyppighed og varighed.»

### C2. Alle relevante kriterier i bilag 3 (planer) er vurderet
**Spørgsmål:** Er de relevante kriterier i bilag 3 vurderet konkret, og fremgår begrundelsen af den offentliggjorte afgørelse (§ 10 og § 33)?  
**Gælder:** Screening af plan  
**Underkendt i praksis:** 10 sager (kategori: screeningskriterier_ikke_vurderet, begrundelse)

**Lovgrundlag:**
- [Miljøvurderingsloven § 10](https://www.retsinformation.dk/eli/lta/2023/4): «inddrage de relevante kriterier i bilag 3»
- [Miljøvurderingsloven § 33](https://www.retsinformation.dk/eli/lta/2023/4): «skal offentliggøres med begrundelse»

**Vejledning:**
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Vurderingen af væsentligheden foretages ved at inddrage de indvirkninger, der med rimelig sandsynlighed kan få betydning i forhold til den konkrete plan/program, jf. lovens bilag 3, nr. 2, om»

**Eksempler fra nævnene:**
- [PKN 2025-07-01](https://pkn.naevneneshus.dk/afgoerelse/e5072919-3d88-4d2f-8e71-0a0815143a99) – Screeningen forholdt sig ikke til, at lokalplanen muliggør boliger med altaner, hvor Miljøstyrelsens vejledende støjgrænse på 58 dB for udendørs opholdsarealer ikke kan overholdes, og kommunen kunne ikke sondre mellem fælles opholdsarealer og private friarealer.  
  Nævnet: «Lokalplanforslaget muliggør således byggeri, hvor Miljøstyrelsens vejledende grænseværdier ikke kan overholdes, jf. planlovens § 15 a, stk. 1, hvilket kommunen ikke har forholdt sig til i miljøscreeningen. Planklagenævnet finder på den baggrund, at kommunen ikke har foretaget den fornødne vurdering i forhold til trafikstøj i forbindelse med miljøscreeningen.»
  Myndigheden havde skrevet: «planen ikke vil medføre en væsentlig indvirkning på menneskers sundhed, herunder i forhold til trafikstøj»
- [MFKN 2024-01-18](https://mfkn.naevneneshus.dk/afgoerelse/d7c0f43a-8409-4b68-bfd3-9f74fef18811) – Kommunen tog i screeningen ikke stilling til de konkrete begrundelser for, at ændringerne skulle være mindre, og afskrivningstidens forlængelse indgik kun implicit, ikke direkte i screeningen.  
  Nævnet: «Miljø- og Fødevareklagenævnet bemærker i øvrigt, at såfremt en mindre ændring af en spildevandsplan henføres under reglen om mindre ændringer, forudsætter det, at kommunen i screeningsafgørelsen tager stilling til de konkrete begrundelser for, at der udelukkende er tale om en mindre ændring.»
- [MFKN 2022-07-06](https://mfkn.naevneneshus.dk/afgoerelse/9a50195f-e567-4716-ba3f-7faeb2e6359d) – Fredningsnævnet brugte den potentielt lovlige anvendelse efter metroloven (at en sti kunne anlægges uanset fredning) som referencegrundlag i stedet for områdets faktiske tilstand, og vurderede derfor ikke stiens indvirkning på miljøet tilstrækkeligt.  
  Nævnet: «Miljø- og Fødevareklagenævnet er af den opfattelse, at fredningsnævnet som referencegrundlag for screeningen ikke har anvendt den faktiske eller planlagte anvendelse af fredningsarealet på afgørelsestidspunktet, men derimod den potentielle anvendelse, som efter den generelle regulering i § 16, stk. 2, vurderes at være retligt mulig.»
  Myndigheden havde skrevet: «Hvis fredningen ikke gennemføres, vil lovens regulering uændret give mulighed for at etablere stier, både på den i fredningsforslagets foreslåede placering og andre steder.»
- [PKN 2021-12-22](https://pkn.naevneneshus.dk/afgoerelse/c17d2a39-64c3-4761-8f72-4ab380106aa3) – Screeningen af planen tog ikke tilstrækkeligt hensyn til indvirkning på Natura 2000-området, og planen kunne udløse miljøvurderingspligt efter § 8, stk. 1, nr. 2.  
  Nævnet: «Planklagenævnet finder ikke, at dette spørgsmål er tilstrækkeligt belyst i forbindelse med miljøscreeningen, jf. afsnit 2.3.2.»

### C3. Kumulation med andre projekter og planer
**Spørgsmål:** Er det konkret vurderet, hvilke eksisterende og godkendte projekter/planer i området påvirkningen kan lægge sig oven i, og hvad den samlede påvirkning bliver?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 9 sager (kategori: kumulation)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «kumulation med andre eksisterende og/eller godkendte projekter»
- [Miljøvurderingsloven bilag 3](https://www.retsinformation.dk/eli/lta/2023/4): «indvirkningens kumulative karakter»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Projektet skal vurderes i kumulation med – det vil sige sammen med – indvirkningen på miljøet fra allerede eksisterende eller godkendte projekter.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «For planer/programmer, der sætter en ramme for infrastruktur og andre projekter med en levetid på mange år, vil hensynet til klimaforandring og biodiversitet være afgørende for planens/programmets strategiske sigte.»

**Eksempler fra nævnene:**
- [MFKN 2025-12-02](https://mfkn.naevneneshus.dk/afgoerelse/26bac803-90db-4328-a0f7-c5cae0a3a8dc) – Ved fornyet behandling skal kommunen i screeningen inddrage kumulativ påvirkning fra den eksisterende anvendelse af tennisbanerne (nævnets vejledende bemærkning).  
  Nævnet: «Ved vurderingen af, om ændringen på grund af dets art, dimensioner eller placering er omfattet af krav om miljøvurdering og tilladelse, jf. miljøvurderingslovens § 21, skal kommunen tage hensyn til kriterierne i lovens bilag 6, og herunder inddrage den kumulative påvirkning fra den eksisterende anvendelse af tennisbanen.»
- [MFKN 2024-04-03](https://mfkn.naevneneshus.dk/afgoerelse/25364fad-01e4-42f1-9bd6-0722ca3e483e) – De kumulative miljøpåvirkninger af sommer- og vinterudvidelserne blev ikke vurderet i sammenhæng; nævnet pålægger ny vurdering af kumulationen.  
  Nævnet: «Ved en fornyet behandling af sagen skal Miljøstyrelsen foretage en ny vurdering af påvirkningen fra det ansøgte projekt på baggrund af bl.a. resultaterne fra sagen om de ansøgte udvidelser i sommerhalvåret med henblik på at vurdere udvidelsernes kumulative miljøpåvirkninger.»
- [MFKN 2024-04-03](https://mfkn.naevneneshus.dk/afgoerelse/baf220b2-e118-4a5d-9f32-999d72305cba) – Udvidelsen blev vurderet isoleret og ud fra, at ansøgningen kun angik driftstid, i stedet for i kumulation med den eksisterende drift, hvor den samlede overskridelse af støjgrænserne skal lægges til grund.  
  Nævnet: «Dermed skal den samlede overskridelse af de vejledende grænseværdier for støj beregnet ved nærmeste beboelser lægges til grund for vurderingen af, om det ansøgte projekt kan forventes at få væsentlige indvirkninger på miljøet.»
  Myndigheden havde skrevet: «Af begrundelsen for afgørelsen fremgår det i forhold til støj, at der er tale om en eksisterende virksomhed, og at ansøgningen alene vedrører driftstiden og ikke [Virksomhed1]s aktivitetsniveau.»
- [MFKN 2023-11-13](https://mfkn.naevneneshus.dk/afgoerelse/6b8ec3a1-b36e-40e6-ad10-acf1dccc1251) – Kommunen undersøgte ikke projektet i kumulation med det eksisterende projekt, men vurderede ændringen isoleret og lagde vægt på tidsbegrænsning og afværgende tiltag.  
  Nævnet: «Projektet skal vurderes i kumulation med – det vil sige sammen med – indvirkningen på miljøet fra allerede eksisterende eller godkendte projekter.»

### C4. Forurening og gener: støj, lys, lugt, støv, trafik
**Spørgsmål:** Er gener for omgivelserne (støj, vibrationer, lys, lugt, støv, trafik) vurderet med konkrete tal eller vejledende grænseværdier og afstande til nærmeste naboer?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 19 sager (kategori: screeningskriterier_ikke_vurderet, materiel_vaesentlighed)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «forurening og gener»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «De vejledende grænser for støj er beregnet på at sikre, at størstedelen af en befolkningsgruppe ikke vil føle sig stærkt generet af den pågældende støjtype ved et niveau svagere end grænseværdien.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «indvirkningens sandsynlighed, varighed, hyppighed og reversibilitet»

**Eksempler fra nævnene:**
- [MFKN 2026-09-28](https://mfkn.naevneneshus.dk/afgoerelse/3e959c0c-a2be-487b-999e-bee51badab44) – Flere miljøpåvirkninger (vand, affald, støv, lys) blev ikke vurderet, fordi de ikke var aktuelle for træfældningen, selvom bilag 6-kriterierne skal vurderes for hele projektet.  
  Nævnet: «Nævnet har lagt vægt på, at det fremgår eksplicit af afgørelsen, at der ikke er foretaget en vurdering af påvirkningerne i forhold til bl.a. vand, affald, støv- og lysgener.»
- [PKN 2025-07-29](https://pkn.naevneneshus.dk/afgoerelse/058e19c1-f71d-468a-8bf5-8ceae2e262f9) – Lokalplanen muliggør boliger, hvor Miljøstyrelsens vejledende støjgrænser for virksomhedsstøj fra det eksisterende kulturhus ikke kan overholdes; det er en sandsynlig væsentlig påvirkning, og den foreslåede løsning (lydsluser ved kulturhuset) var ikke tilstrækkelig sikring.  
  Nævnet: «Planklagenævnet finder, at de konstaterede overskridelser af de vejledende grænseværdier for virksomhedsstøj udgør en sandsynlig væsentlig påvirkning af miljøet, som i den konkrete sag medfører krav om miljøvurdering.»
  Myndigheden havde skrevet: «Det vurderes, at den billigste løsning vil være at Sønderborg Kommune etablerer lydsluse i døre ved musiker-indgangen og døren på 1. sal til koncertsalen i Mejeriet, da disse to døre har ringe støjdæmpende evne.»
- [PKN 2025-07-01](https://pkn.naevneneshus.dk/afgoerelse/e5072919-3d88-4d2f-8e71-0a0815143a99) – Screeningen forholdt sig ikke til, at lokalplanen muliggør boliger med altaner, hvor Miljøstyrelsens vejledende støjgrænse på 58 dB for udendørs opholdsarealer ikke kan overholdes, og kommunen kunne ikke sondre mellem fælles opholdsarealer og private friarealer.  
  Nævnet: «Lokalplanforslaget muliggør således byggeri, hvor Miljøstyrelsens vejledende grænseværdier ikke kan overholdes, jf. planlovens § 15 a, stk. 1, hvilket kommunen ikke har forholdt sig til i miljøscreeningen. Planklagenævnet finder på den baggrund, at kommunen ikke har foretaget den fornødne vurdering i forhold til trafikstøj i forbindelse med miljøscreeningen.»
  Myndigheden havde skrevet: «planen ikke vil medføre en væsentlig indvirkning på menneskers sundhed, herunder i forhold til trafikstøj»
- [MFKN 2024-09-20](https://mfkn.naevneneshus.dk/afgoerelse/41dd7e7a-f67d-43ae-a941-b09237530ed2) – Kommunen vurderede støjpåvirkningen, men inddrog ikke tilstrækkeligt, om støjgrænserne overskrides, og screeningens øvrige parametre som hyppighed og varighed. Projektet var heller ikke færdigprojekteret.  
  Nævnet: «Kommunen bør inddrage, om de vejledende støjgrænser overskrides samt screeningens øvrige parametre som f.eks. hyppighed og varighed.»

### C5. Landskab, kulturarv og visuel påvirkning
**Spørgsmål:** Er påvirkningen af landskab, kystlandskab, kulturmiljø, fortidsminder og kirker vurderet konkret (fx med visualiseringer og afstande)?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 1 sager (kategori: screeningskriterier_ikke_vurderet, materiel_vaesentlighed)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «landskaber og lokaliteter af historisk, kulturel eller arkæologisk betydning»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Yderligere lagde Miljø- og Fødevareklagenævnet vægt på, at den kompetente myndighed har forholdt sig til den trafikale påvirkning, og på baggrund af, at projektet alene vil medføre mertrafik i dagperioden, som er marginal i forhold til den øvrige aktivitet i dagperioden, har vurderet, at der ikke vil være en væsentlig påvirkning af miljøet.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «indvirkningen på områder eller landskaber, som har en anerkendt beskyttelsesstatus på nationalt plan, fællesskabsplan eller international plan.»

**Eksempler fra nævnene:**
- [PKN 2021-12-02](https://pkn.naevneneshus.dk/afgoerelse/7063f89e-abcb-4239-8e96-ea4f26e6df1d) – Kommunen screenede planerne og vurderede, at de ikke kunne få væsentlig indvirkning, uden at vurdere parkeringsarealets påvirkning af miljø og landskab, og med afgørende vægt på landskabstilpasning. Nævnet fandt, at planerne kunne få væsentlig indvirkning og skulle miljøvurderes.  
  Nævnet: «Nævnet finder derimod, at det forhold, at der er behov for at tilpasse et byggeri ind i landskabet netop indikerer, at planerne vil have en væsentlig landskabelig påvirkning.»

### C6. Vand: grundvand, vandløb, søer, kyst og miljømål
**Spørgsmål:** Er påvirkningen af grundvand (drikkevandsinteresser), overfladevand og målopfyldelsen i vandområdeplanerne vurderet?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 19 sager (kategori: screeningskriterier_ikke_vurderet, sagsoplysning_dokumentation)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «miljøkvalitetsnormer»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «En kommune havde ved en screening vurderet, at en fornyelse af tidligere tilladelse til indvinding af oprindeligt 6000 m»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «indvirkningens sandsynlighed, varighed, hyppighed og reversibilitet»

**Eksempler fra nævnene:**
- [MFKN 2026-09-28](https://mfkn.naevneneshus.dk/afgoerelse/3e959c0c-a2be-487b-999e-bee51badab44) – Flere miljøpåvirkninger (vand, affald, støv, lys) blev ikke vurderet, fordi de ikke var aktuelle for træfældningen, selvom bilag 6-kriterierne skal vurderes for hele projektet.  
  Nævnet: «Nævnet har lagt vægt på, at det fremgår eksplicit af afgørelsen, at der ikke er foretaget en vurdering af påvirkningerne i forhold til bl.a. vand, affald, støv- og lysgener.»
- [MFKN 2026-06-23](https://mfkn.naevneneshus.dk/afgoerelse/b650aeb0-ca3e-4f84-8d23-dd8bc3485c65) – Kommunen havde ikke tilstrækkeligt grundlag for at vurdere, om overløb fra regnvandsbassinerne (ca. hvert femte år) giver en midlertidig forringelse af Bygholm Å nedstrøms udløbet af Hatting Bæk, hvor kobber allerede er ikke-god tilstand. Overløbets betydning var ikke beskrevet i miljøkonsekvensrapporten eller den begrundede konklusion, og kommunens beregninger var ikke retvisende.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Horsens Kommune for tidspunktet for § 25-tilladelsen ikke havde et tilstrækkeligt grundlag for at foretage en vurdering af, om projektet vil kunne medføre en forringelse af Bygholm Å nedstrøms udløbet af Hatting Bæk, for så vidt angår kobber i forbindelse med en overløbssituation.»
- [MFKN 2026-03-31](https://mfkn.naevneneshus.dk/afgoerelse/fbc0dfbd-c00a-4eef-ad30-8284d315404d) – BEST-beregningen brugte en pumpetid (33 %) der ikke afspejlede tilladelsens vilkår (ingen daglig maksimal indvindingsmængde), og to rapporter havde forskellige pumpetider; påvirkningen kan være underestimeret.  
  Nævnet: «Nævnet vil derfor ikke på den baggrund kunne vurdere, hvorvidt kommunens vurderinger i afgørelsen afspejler den reelle påvirkning af vandløbene ved den ansøgte og tilladte indvinding, idet de beregnede påvirkninger potentielt er underestimeret.»
- [MFKN 2025-08-25](https://mfkn.naevneneshus.dk/afgoerelse/8cad826e-67b6-49f3-b2f0-aa9b85eb85a7) – Kommunen vurderede ikke konkret, hvad udledning af tag- og overfladevand fra regnvandsbassinet betyder for Smedebæk og dens miljømål (kobber og zink overskrider allerede miljøkvalitetskrav); den henviste blot til, at vandet ikke indeholder andet end sædvanligt overfladevand.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Tønder Kommune i forbindelse med screeningsafgørelsen ikke har foretaget en tilstrækkelig vurdering af projektets påvirkning af Smedebæk og vandløbets miljømål. Screeningsafgørelsen lider derfor af en væsentlig retlig mangel.»

## Natur

### D1. Natura 2000: væsentlighedsvurdering
**Spørgsmål:** Er det vurderet, om planen/projektet alene eller sammen med andre kan påvirke et Natura 2000-område væsentligt, ud fra områdets udpegningsgrundlag, afstand og påvirkningsveje (fx hydrologi, kvælstof, forstyrrelse) – og uden at lægge afværgeforanstaltninger til grund?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 33 sager (kategori: natura2000_vaesentlighed)

**Lovgrundlag:**
- [Habitatbekendtgørelsen § 6](https://www.retsinformation.dk/eli/lta/2023/1098): «kan påvirke et Natura 2000-område væsentligt»
- [Planhabitatbekendtgørelsen § 3](https://www.retsinformation.dk/eli/lta/2016/1383): «kan påvirke et Natura 2000-område væsentligt»

**Vejledning:**
- [Habitatvejledningen inkl. bilag IV-arter](https://www.retsinformation.dk/eli/retsinfo/2020/9925): «De gælder også for planer og projekter, der ligger uden for Natura 2000-området, men som kan have væsentlig indvirkning på Natura 2000-områdets bevaringsmålsætninger, uanset afstanden fra det pågældende Natura 2000-område. [113]»
- [Habitatvejledningen inkl. bilag IV-arter](https://www.retsinformation.dk/eli/retsinfo/2020/9925): «Vurderingen af, om en plan eller et projekt påvirker et Natura 2000-områdes bevaringsmålsætninger væsentligt, retter sig mod påvirkningen af de karakteristika og miljømæssige forhold, der kendetegner det konkrete Natura 2000-område, og herunder særligt de konkret fastsatte bevaringsmålsætninger for de arter og naturtyper, der er på Natura 2000-områdets udpegningsgrundlag. [106]»

**Eksempler fra nævnene:**
- [PKN 2026-09-02](https://pkn.naevneneshus.dk/afgoerelse/9a9539d3-0e12-44a8-baad-0fc070c06521) – Kommunen kortlagde ikke odder i eller nær det tilstødende habitatområde og undersøgte ikke egnede levesteder dér, men udelukkede alligevel væsentlig påvirkning af arten på udpegningsgrundlaget. Planerne blev vedtaget uden det fornødne oplysningsgrundlag for væsentlighedsvurderingen.  
  Nævnet: «Planklagenævnet vurderer på baggrund af ovennævnte, at kommunen i den konkrete sag ikke har haft et tilstrækkeligt grundlag til at kunne udelukke, at lokalplanen kan medføre en væsentlig påvirkning af odder.»
  Myndigheden havde skrevet: «Dermed vurderes nærmere kortlægning af disse grøfter og vandløb ikke at være relevant.»
- [MFKN 2026-06-29](https://mfkn.naevneneshus.dk/afgoerelse/70de5eee-077d-401c-b456-35a94ad22115) – Kommunens væsentlighedsvurdering lagde til grund, at der ikke var kendskab til havlampret og flodlampret i vandløbet, selvom artsdata viste registreringer i åsystemet. Oplysningerne burde være indgået i vurderingen af påvirkningen af Natura 2000-området.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Ringkøbing-Skjern Kommunes væsentlighedsvurdering er mangelfuld, og at screeningsafgørelsen som følge deraf også er mangelfuld.»
  Myndigheden havde skrevet: «Det fremgår yderligere, at kommunen ikke er bekendt med forekomster af havlampret eller flodlampret i Venner Å.»
- [MFKN 2026-02-26](https://mfkn.naevneneshus.dk/afgoerelse/676f9df3-5a23-4af7-84e4-7eccb501af89) – Der var ikke foretaget en nærmere (konsekvens)vurdering af naturtypen bøg på mor i kabelkorridoren, herunder dens tilstand og påvirkning, trods risiko for blow-outs ved underboring.  
  Nævnet: «Det forudsætter derfor, at der er en nærmere vurdering af naturtypen bøg på mor i kabelkorridoren, herunder tilstanden og den eventuelle påvirkning som følge af projektet.»
- [MFKN 2025-12-12](https://mfkn.naevneneshus.dk/afgoerelse/53f62bc4-1e9a-4ddc-840a-2ca64a70afc3) – Kommunen indregnede en afværgeforanstaltning (opstart af nedramning uden for yngle- og dvaleperiode for flagermus) i væsentlighedsvurderingen for damflagermus på udpegningsgrundlaget, og undlod derfor en konsekvensvurdering.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Viborg Kommune har inddraget en afværgende foranstaltning i forhold til damflagermus ved vurderingen af, om projektet vil påvirke udpegningsgrundlagene for Natura 2000-områderne nr. 30 og 33 væsentligt.»

### D2. Bilag IV-arter: yngle- og rasteområder
**Spørgsmål:** Er det undersøgt, hvilke bilag IV-arter der kan forekomme i området (kendt viden og om nødvendigt besigtigelse), og vurderet, om yngle- eller rasteområder kan beskadiges eller ødelægges, så den økologiske funktionalitet påvirkes?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 44 sager (kategori: bilagIV_arter)

**Lovgrundlag:**
- [Habitatbekendtgørelsen § 10](https://www.retsinformation.dk/eli/lta/2023/1098): «beskadige eller ødelægge yngle- eller rasteområder»
- [Habitatbekendtgørelsen § 10](https://www.retsinformation.dk/eli/lta/2023/1098): «Vurderingen skal fremgå af de afgørelser»
- [Planhabitatbekendtgørelsen § 7](https://www.retsinformation.dk/eli/lta/2016/1383): «beskadige eller ødelægge yngle- eller rasteområder»

**Vejledning:**
- [Habitatvejledningen inkl. bilag IV-arter](https://www.retsinformation.dk/eli/retsinfo/2020/9925): «Hvis den indledende vurdering viser, at bilag IV-arter kan påvirkes af det ansøgte, skal sagen belyses nærmere, og der skal foretages en vurdering af, om yngle- eller rasteområder bliver beskadiget eller ødelagt eller forskellige livsstadier af bilag IV-planter bliver ødelagt.»
- [Habitatvejledningen inkl. bilag IV-arter](https://www.retsinformation.dk/eli/retsinfo/2020/9925): «Det er således fortsat op til myndighederne at afgøre de konkrete behov i den konkrete situation, ligesom det er myndigheden, der i sidste ende tager stilling til, om sagen er tilstrækkeligt oplyst til at kunne vurdere, om en handling vil beskadige eller ødelægge yngle- eller rasteområder.»

**Eksempler fra nævnene:**
- [MFKN 2025-08-14](https://mfkn.naevneneshus.dk/afgoerelse/9a2269be-1c3a-4924-b77d-624797b47719) – Afgørelsen indeholdt ikke en vurdering af, om projektet kan beskadige yngle- eller rasteområder for stor vandsalamander og spidssnudet frø.  
  Nævnet: «Miljø- og Fødevareklagenævnet konstaterer desuden, at den påklagede afgørelse ikke indeholder en vurdering efter habitatbekendtgørelsens § 10, stk. 1,[20] i forhold til det ansøgte projekt.»
- [PKN 2025-07-29](https://pkn.naevneneshus.dk/afgoerelse/058e19c1-f71d-468a-8bf5-8ceae2e262f9) – Kommunen screenede lokalplanen for kollegieboliger som ikke miljøvurderingspligtig, selv om den selv fandt egnede yngle- og rasteområder for flagermus i bygninger, der skulle nedrives, og forudsatte afværgeforanstaltninger (nedrivningsperioder, flagermuskasser) uden at begrunde, at de sikrer økologisk funktionalitet; flagermuskasser kan være kompensation, ikke afværge.  
  Nævnet: «Planklagenævnet finder således, at det udløser miljøvurderingspligt, såfremt det må lægges til grund, at der inden for et planområde er yngle- og/eller rasteområder for bilag IV-arter, og hvis der i lokalplanen forudsættes brug af foranstaltninger for at sikre opretholdelse af områdets vedvarende økologiske funktionalitet for flagermus.»
- [MFKN 2025-04-08](https://mfkn.naevneneshus.dk/afgoerelse/83f2ccf2-c574-4e1a-bbb3-14b13cad625c) – Kommunen nøjedes med at pege på andre egnede huse og træer i byen uden konkret at vurdere bevarelse af økologisk funktionalitet, og afviste området som blot opholdssted, selvom dagsopholdssted er rasteområde.  
  Nævnet: «Det er dermed ikke tilstrækkeligt at bemærke, at der er andre egnede yngle- og rasteområder i form af huse og træer, som kan benyttes til at opretholde den økologiske funktionalitet, uden at kommunen har forholdt sig mere konkret til dette.»
- [MFKN 2025-02-12](https://mfkn.naevneneshus.dk/afgoerelse/32fa2ae8-82ff-4933-ad39-c6636e4ba44c) – For flagermus var det ikke sikret, at yngle- og rasteområdernes økologiske funktionalitet bevares: miljøkonsekvensrapporten begrundede ikke konkret, at nærliggende gårde kunne fungere som afværge for de nedrevne bygninger, og ingen vilkår sikrede funktionaliteten.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Odder Kommune i forbindelse med § 25-tilladelsen ikke i tilstrækkeligt omfang har sikret sig, at projektet ikke vil påvirke yngle- eller rasteområder for arter af flagermus.»

### D3. § 3-natur, fredninger, beskyttelseslinjer og anden natur
**Spørgsmål:** Er påvirkningen af § 3-beskyttet natur, fredede arealer, skov, beskyttelseslinjer og biodiversitet i øvrigt vurderet, herunder indirekte påvirkning (fx dræning, kvælstof)?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 4 sager (kategori: natur_paragraf3)

**Lovgrundlag:**
- [Miljøvurderingsloven bilag 6](https://www.retsinformation.dk/eli/lta/2023/4): «områder, der er registreret eller fredet ved national lovgivning»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Miljø- og Fødevareklagenævnet lagde efter det oplyste i ansøgningen og screeningsafgørelsen til grund, at hele det anmeldte projekt, herunder etablering af skov, natureng og vandhul, udgjorde en integreret del i miljøvurderingsreglernes forstand, men at screeningen alene var foretaget for den del af projektet, som har udløst screeningspligten, dvs. etablering af skov.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «indvirkningens sandsynlighed, varighed, hyppighed og reversibilitet»

**Eksempler fra nævnene:**
- [PKN 2023-03-31](https://pkn.naevneneshus.dk/afgoerelse/a5ae18a7-3231-4865-8973-60e03291457e) – Screeningen indeholdt forkerte oplysninger om den § 3-beskyttede sø, som på grund af den foreslåede vejforbindelse lå inden for lokalplanområdet, så vurderingen af § 3-natur hvilede på utilstrækkeligt grundlag.  
  Nævnet: «Planklagenævnet finder på baggrund af ovennævnte, at screeningsafgørelsen ikke har tilvejebragt tilstrækkelige oplysninger til at foretage en vurdering i forhold til § 3-beskyttede områder i forbindelse med miljøscreeningen.»
  Myndigheden havde skrevet: «Naturbeskyttelsesområder er beskrevet i screeningsskemaets, s. 8-9, hvor det fremgår, at der ikke er arealer beskyttet af naturbeskyttelseslovens § 3 inden for lokalplanområdet.»
- [MFKN 2022-10-27](https://mfkn.naevneneshus.dk/afgoerelse/73038768-db48-47d3-8865-2a4ddd047658) – Nævnet påpegede, at udgravningens bundkote ca. 10 m under vandløbets vandspejl kan give en sænkningstragt og dræning af § 3-vandløb og mosesøer, hvilket regionen ikke havde vurderet og skal tage i betragtning ved fornyet behandling.  
  Nævnet: «Nævnet bemærker, at udgravningens størrelse og afgravningen ned til kote 50 kan udgøre en betragtelig sænkningstragt med en effektiv dræningseffekt fra de omkringliggende naturområder, som f.eks. § 3-vandløbet og de nærliggende mosesøer, såfremt der er hydraulisk kontakt mellem disse og udgravningen.»
- [MFKN 2022-09-02](https://mfkn.naevneneshus.dk/afgoerelse/7db67338-63fa-4a45-8a10-3b04e0c25770) – Det var tvivlsomt, om den begrundede konklusion tilstrækkeligt forholdt sig til påvirkningen af § 3-beskyttede vandløb fra selve grundvandssænkningen, herunder risiko for udtørring, og om vilkår om vinterperiode burde fastsættes.  
  Nævnet: «Derimod finder Miljø- og Fødevareklagenævnet det tvivlsomt, om Ikast-Brande Kommune i § 25-tilladelsens begrundede konklusion også har forholdt sig tilstrækkeligt til påvirkningen af de § 3-beskyttede vandløb som følge af selve grundvandssænkningen, herunder risikoen for udtørring.»
- [PKN 2021-12-13](https://pkn.naevneneshus.dk/afgoerelse/fca8d5cb-866a-4b23-afb5-301942337dba) – Screeningen tog udgangspunkt i 30-40 m til beskyttet natur, men en § 3-mose lå betydelig tættere på lokalplanområdet.  
  Nævnet: «Nævnet lægger vægt på, at kommunen i miljøscreeningen har taget udgangspunkt i, at der er 30-40 m til beskyttet natur, hvilket må forstås som bl.a. mosen, men at der befinder sig en mose betydelig tættere på lokalplanområdet.»

## Begrundelse og afgørelse

### E1. Afværgeforanstaltninger er konkrete og sikrede
**Spørgsmål:** Hvis konklusionen bygger på afværgeforanstaltninger: er de beskrevet af bygherren, konkrete og sikret (vilkår, lokalplanbestemmelse), og er de ikke brugt i Natura 2000-væsentlighedsvurderingen?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 50 sager (kategori: afvaergeforanstaltninger)

**Lovgrundlag:**
- [Miljøvurderingsloven § 21](https://www.retsinformation.dk/eli/lta/2023/4): «hvilke foranstaltninger der påtænkes truffet for at undgå eller forebygge»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «En screening anses for at være en foreløbig vurdering af det ansøgte projekt og en screeningsafgørelse skal kunne træffes ret hurtigt.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Screeningsafgørelsen om, at der ikke skal gennemføres en miljøvurdering, er en forvaltningsretlig afgørelse.»

**Eksempler fra nævnene:**
- [MFKN 2026-09-28](https://mfkn.naevneneshus.dk/afgoerelse/3e959c0c-a2be-487b-999e-bee51badab44) – Screeningsafgørelsen forudsatte vilkår (ledelinje for flagermus, fældning uden for yngletid), men en screeningsafgørelse kan ikke indeholde vilkår.  
  Nævnet: «En screeningsafgørelse er ikke en tilladelse, og der kan derfor ikke stilles vilkår til projektet heri.»
- [MFKN 2026-06-29](https://mfkn.naevneneshus.dk/afgoerelse/70de5eee-077d-401c-b456-35a94ad22115) – Nævnet bemærkede, at vilkår om særlige gitterstørrelser for at beskytte arter på udpegningsgrundlaget er afværgeforanstaltninger, som ikke kan indgå i væsentlighedsvurderingen, men først i en konsekvensvurdering.  
  Nævnet: «så er der tale om afværgeforanstaltninger, som ikke kan tages i betragtning i forbindelse med en væsentlighedsvurdering, men først kan inddrages ved en habitatkonsekvensvurdering.»
  Myndigheden havde skrevet: «Det er derfor kommunens vurdering, at en afgitring på 6 mm er tilstrækkeligt for at sikre nedtrækkende arter af fisk.»
- [MFKN 2026-06-01](https://mfkn.naevneneshus.dk/afgoerelse/881c44ac-0837-4b74-9d1b-89c4729f741c) – Screeningen byggede på en bufferzone på 10 m til § 3-natur, som kommunen selv havde indført og som ikke indgik i bygherrens ansøgning. Myndigheden tilskar dermed projektet og stillede vilkår i en screeningsafgørelse.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at Odsherred Kommunes screeningsafgørelse ikke er truffet på grundlag af bygherrens beskrivelse af det ansøgte projekt. Screeningsafgørelsen lider derfor af en væsentlig retlig mangel.»
- [MFKN 2026-04-22](https://mfkn.naevneneshus.dk/afgoerelse/1e643061-5a88-4629-87f8-74f203f7f191) – Vilkår 9 om paddehegn til beskyttelse af løgfrø og andre padder var for upræcist om afstand, placering, tidsrum og udformning til at sikre yngle- og rasteområdernes økologiske funktionalitet og kunne håndhæves; kommunen præciserede først under klagesagen.  
  Nævnet: «Nævnet finder videre, at vilkår 9 i § 25-tilladelsen skal præciseres.»
  Myndigheden havde skrevet: «Der skal opsættes paddehegn omkring søen i projektområdets nordøstlige hjørne, hvor der er registreret kvækkende løgfrø og butsnudet frø og søerne umiddelbart udenfor projektområdets sydøstlige hjørne, hvor der er registeret haletudser af løgfrø.»

### E2. Konklusionen er begrundet
**Spørgsmål:** Står der for hver vurdering, hvorfor påvirkningen ikke er væsentlig (fakta, målestok, afstand), og ikke kun en konklusion?  
**Gælder:** Screening af projekt, Screening af plan, Miljørapport (plan), § 25-tilladelse  
**Underkendt i praksis:** 19 sager (kategori: begrundelse, materiel_vaesentlighed)

**Lovgrundlag:**
- [Miljøvurderingsloven § 21](https://www.retsinformation.dk/eli/lta/2023/4): «Afgørelsen skal begrundes med hovedårsagerne til afgørelsen»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Screeningsafgørelsen skal indeholde en begrundelse, hvori hovedårsagerne til afgørelsen og en henvisning til de i bilag 6 relevante kriterier indgår, jf. lovens § 21, stk. 2.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Nævnet fandt, at det generelt er tvivlsomt, at det vil udgøre en tilstrækkelig begrundelse for en screeningsafgørelse for en plan, at der udelukkende foretages en afkrydsning i et screeningsskema uden en nærmere uddybning af vurderingen i forhold til miljøparametre efter miljøvurderingsloven.»

**Eksempler fra nævnene:**
- [PKN 2025-07-29](https://pkn.naevneneshus.dk/afgoerelse/058e19c1-f71d-468a-8bf5-8ceae2e262f9) – Lokalplanen muliggør boliger, hvor Miljøstyrelsens vejledende støjgrænser for virksomhedsstøj fra det eksisterende kulturhus ikke kan overholdes; det er en sandsynlig væsentlig påvirkning, og den foreslåede løsning (lydsluser ved kulturhuset) var ikke tilstrækkelig sikring.  
  Nævnet: «Planklagenævnet finder, at de konstaterede overskridelser af de vejledende grænseværdier for virksomhedsstøj udgør en sandsynlig væsentlig påvirkning af miljøet, som i den konkrete sag medfører krav om miljøvurdering.»
  Myndigheden havde skrevet: «Det vurderes, at den billigste løsning vil være at Sønderborg Kommune etablerer lydsluse i døre ved musiker-indgangen og døren på 1. sal til koncertsalen i Mejeriet, da disse to døre har ringe støjdæmpende evne.»
- [MFKN 2024-06-27](https://mfkn.naevneneshus.dk/afgoerelse/f3c61716-57c5-4b26-9307-db9dcded6de7) – Kommunen lagde vægt på omkostningerne ved og muligheden for støjskærm i vurderingen af, om støjen var væsentlig, og anvendte en højere støjgrænse fra en rapport for et andet anlæg.  
  Nævnet: «Miljø- og Fødevareklagenævnet bemærker i øvrigt, at mulighederne for at begrænse støjen fra kunstgræsbanen på den konkrete placering ikke har betydning for vurderingen af, om støjpåvirkningen er væsentlig, og om projektet dermed skal miljøvurderes efter miljøvurderingsloven.»
- [MFKN 2024-05-08](https://mfkn.naevneneshus.dk/afgoerelse/dc595285-4c55-4d97-9949-3ccc3bcce516) – Planen omfatter ti projekter, ca. 30 ha kloakoplande og ca. 150 matrikler samt en trykledning til mindst 11.005 PE, så den kan ikke anses for at fastlægge anvendelsen af et mindre område eller kun mindre ændringer.  
  Nævnet: «For så vidt angår bestemmelsen i miljøvurderingslovens § 8, stk. 2, nr. 1, har Miljø- og Fødevareklagenævnet lagt vægt på, at planforslaget ikke fastlæggelser anvendelsen af et mindre område, da forslaget bl.a. gælder for flere kloakoplande, der tilsammen omfatter ca. 30 ha, og udover separatkloakeringen berører anlægsarbejder på ca. 150 forskellige matrikler.»
- [MFKN 2024-04-03](https://mfkn.naevneneshus.dk/afgoerelse/baf220b2-e118-4a5d-9f32-999d72305cba) – Miljøstyrelsen vurderede, at udvidelse af sæsonlængde og åbningstider for en forlystelsespark ikke gav væsentlig støjpåvirkning, selvom støjnotatet viste markante overskridelser af de vejledende støjgrænser ved boliger; nævnet var uenig i den materielle vurdering.  
  Nævnet: «På baggrund af ovenstående er det Miljø- og Fødevareklagenævnets opfattelse, at der er tale om en væsentlig overskridelse af de vejledende støjgrænser, og da overskridelserne desuden vil forekomme hyppigt og over hele åbningssæsonen, kan projektet efter nævnets vurdering forventes at få væsentlige indvirkninger på miljøet.»

### E3. Klar afgørelse, offentliggørelse og klagevejledning
**Spørgsmål:** Fremgår det klart, at der er truffet en afgørelse efter § 21 (projekter) eller § 10 (planer), hvad den omfatter, og at den offentliggøres med klagevejledning?  
**Gælder:** Screening af projekt, Screening af plan  
**Underkendt i praksis:** 29 sager (kategori: kompetence_procedure)

**Lovgrundlag:**
- [Miljøvurderingsloven § 36](https://www.retsinformation.dk/eli/lta/2023/4): «Myndigheden skal offentliggøre en afgørelse efter § 21»
- [Miljøvurderingsloven § 33](https://www.retsinformation.dk/eli/lta/2023/4): «skal offentliggøres med begrundelse»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Kommunen havde i forbindelse med afgørelsen om landzonetilladelse til etablering af jordvolde indirekte truffet afgørelse om, at projektet til etablering af areal til motocrosskørsel og tilhørende støjvold ikke var omfattet af reglerne i miljøvurderingsloven.»
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «Efter høring af berørte myndigheder og på grundlag screeningen kan myndigheden i screeningsafgørelsen nå frem til»

**Eksempler fra nævnene:**
- [MFKN 2026-07-02](https://mfkn.naevneneshus.dk/afgoerelse/5ba79c70-ea6c-4a17-a991-4e33c87796d4) – Miljøgodkendelsen efter miljøbeskyttelsesloven blev meddelt uden den nødvendige stillingtagen efter miljøvurderingsreglerne.  
  Nævnet: «Miljøgodkendelsen efter miljøbeskyttelseslovens § 33 lider derfor af en væsentlig retlig mangel i sig selv.»
- [MFKN 2026-06-29](https://mfkn.naevneneshus.dk/afgoerelse/70de5eee-077d-401c-b456-35a94ad22115) – Vandindvindingstilladelsen er ugyldig, fordi den bygger på en mangelfuld screeningsafgørelse, så der ikke længere foreligger den nødvendige stillingtagen efter miljøvurderingsreglerne.  
  Nævnet: «Vandindvindingstilladelsen lider derfor i sig selv af en væsentlig retlig mangel, som fører til afgørelsens ugyldighed.»
- [MFKN 2026-06-01](https://mfkn.naevneneshus.dk/afgoerelse/881c44ac-0837-4b74-9d1b-89c4729f741c) – Miljøgodkendelsen efter miljøbeskyttelsesloven blev meddelt uden gyldig stillingtagen til miljøvurderingspligt, da screeningsafgørelsen var mangelfuld.  
  Nævnet: «Da Odsherred Kommunes screeningsafgørelse efter miljøvurderingslovens § 21 lider af en væsentlig mangel, finder Miljø- og Fødevareklagenævnet, at der ikke forelå den nødvendige stillingtagen til projektet efter miljøvurderingsreglerne, inden miljøgodkendelsen efter miljøbeskyttelseslovens § 33 blev meddelt.»
- [MFKN 2026-05-18](https://mfkn.naevneneshus.dk/afgoerelse/20ab54ba-0499-47c5-a98c-576e62674718) – Vandløbstilladelsen blev givet, før der forelå gyldig stillingtagen til projektet efter miljøvurderingsreglerne, hvilket gav tilladelsen en væsentlig retlig mangel.  
  Nævnet: «Da Københavns Kommunes afgørelse om, at rørlægningen ikke er omfattet af miljøvurderingsloven, med den foreliggende afgørelse ikke længere er gældende, finder Miljø- og Fødevareklagenævnet, at der ikke foreligger den nødvendige stillingtagen til projektet efter miljøvurderingsreglerne, inden afgørelsen om tilladelse efter vandløbslovens § 6, § 17, § 47, § 48 og § 49 blev meddelt.»

## Miljørapport

### F1. Miljørapportens indhold: alternativer, 0-alternativ og kumulation
**Spørgsmål:** Indeholder miljørapporten rimelige alternativer, 0-alternativet, kumulative virkninger, afværgeforanstaltninger og overvågning (bilag 4)?  
**Gælder:** Miljørapport (plan)  
**Underkendt i praksis:** 16 sager (kategori: miljoerapport_mangelfuld)

**Lovgrundlag:**
- [Miljøvurderingsloven § 12](https://www.retsinformation.dk/eli/lta/2023/4): «rimelige alternativer»
- [Miljøvurderingsloven bilag 4](https://www.retsinformation.dk/eli/lta/2023/4): «Oplysninger omhandlet i § 12»

**Vejledning:**
- [Vejledning om miljøvurdering af planer og programmer](https://www.retsinformation.dk/eli/retsinfo/2024/9094): «I det omfang der har været overvejet alternativer, skal disse beskrives, vurderes og fremgå af miljørapporten i form af»

**Eksempler fra nævnene:**
- [PKN 2026-06-08](https://pkn.naevneneshus.dk/afgoerelse/7457d896-7c3d-45a7-ada9-339036b05d6d) – Kommunen udelod trafikale påvirkninger og trafikstøj (anlægs- og driftsfase, samt betydningen af den planlagte vejbetjening) fra miljørapporten med den begrundelse, at færdsel på offentlig vej ikke kan reguleres i planerne, og at forholdet først kan belyses på projektniveau; nævnet fandt det planlagte tilstrækkeligt defineret til, at væsentlig indvirkning var sandsynlig.  
  Nævnet: «Planklagenævnet finder, at kommunens afgrænsning af miljørapporten ikke er i overensstemmelse med miljøvurderingslovens § 12, stk. 1, idet trafikale påvirkninger og trafikstøj ikke er inddraget i miljørapporten.»
- [PKN 2025-12-12](https://pkn.naevneneshus.dk/afgoerelse/73dc1c0e-93c0-4b53-9db8-743a5bd35703) – Miljørapporten gav ikke tilstrækkelige oplysninger om eksisterende miljøproblemer vedrørende Natura 2000-områderne, så minimumskravene til en miljørapport var ikke opfyldt.  
  Nævnet: «Der er således heller ikke i miljørapporten givet tilstrækkelige oplysninger om ethvert eksisterende miljøproblem, hvorfor miljøvurderingslovens minimumskrav til en miljørapport ikke er opfyldt, jf. lovens § 12, stk. 1.»
- [PKN 2025-09-08](https://pkn.naevneneshus.dk/afgoerelse/5e22b4df-030a-49f0-8244-442b6c7e4c81) – Miljørapporten var afgrænset fra jordarealer, jordbund og vand, så påvirkning af vandmiljøet og miljømål for overfladevandområder fra udgravning, anlæg på søterritoriet og drift ikke var belyst på overordnet niveau.  
  Nævnet: «Planklagenævnet finder, at kommunens afgrænsning af miljørapporten ikke er i overensstemmelse med miljøvurderingslovens § 12, stk. 1.»
- [PKN 2025-02-05](https://pkn.naevneneshus.dk/afgoerelse/8eeb4204-6a0d-4dae-bbc9-286cef040ac0) – Miljørapporten gav ikke tilstrækkelige oplysninger om eksisterende miljøproblemer og fauna (flagermus), og miljøvurderingslovens minimumskrav til en miljørapport var derfor ikke opfyldt.  
  Nævnet: «Der er således heller ikke i miljørapporten givet tilstrækkelige oplysninger om ethvert eksisterende miljøproblem, hvorfor miljøvurderingslovens minimumskrav til en miljørapport ikke er opfyldt.»

## Tilladelse

### G1. Vilkår er klare, håndhævelige og dækker de væsentlige påvirkninger
**Spørgsmål:** Er vilkårene i tilladelsen præcise, målbare og håndhævelige, og dækker de de påvirkninger og foranstaltninger, miljøkonsekvensrapporten forudsætter (§ 27)?  
**Gælder:** § 25-tilladelse  
**Underkendt i praksis:** 18 sager (kategori: vilkaar)

**Lovgrundlag:**
- [Miljøvurderingsloven § 27](https://www.retsinformation.dk/eli/lta/2023/4): «indeholde alle de miljømæssige betingelser, der er knyttet til afgørelsen»

**Vejledning:**
- [Vejledning om miljøvurdering af konkrete projekter](https://www.retsinformation.dk/eli/retsinfo/2024/9093): «Myndigheden har efter lovens § 27, stk. 2, hjemmel til at stille vilkår i tilladelsen med henblik på opfyldelse af lovens formål.»

**Eksempler fra nævnene:**
- [MFKN 2026-05-07](https://mfkn.naevneneshus.dk/afgoerelse/8e9eee53-d2ac-4c3c-a1bb-a5c5b5b1086d) – Vilkår 26 i § 25-tilladelsen åbnede for at fjerne eller justere møllestoppet for flagermus på baggrund af senere undersøgelser, men var for upræcist til at kunne håndhæves og undergravede den afværgeforanstaltning, vurderingen af bilag IV-arter hvilede på.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at vilkåret er for upræcist til, at dette kan håndhæves. Nævnet har lagt vægt på, at det ikke fremgår af vilkåret, hvad der forstås ved betydelige mængder flagermus nær vindmøllerne, eller hvordan vindretninger og temperaturer ville skulle indgå i et justeret vilkår.»
- [MFKN 2026-02-26](https://mfkn.naevneneshus.dk/afgoerelse/676f9df3-5a23-4af7-84e4-7eccb501af89) – Tilladelsen indeholdt ikke vilkår om overvågning af styret underboring, selvom der uden afværgeforanstaltninger var risiko for blow-outs, der kunne påvirke bøg på mor.  
  Nævnet: «Nævnet finder på den baggrund, at der skulle været inddraget vilkår om overvågning i forhold til styret underboring og udførslen heraf.»
- [MFKN 2026-01-16](https://mfkn.naevneneshus.dk/afgoerelse/7b1e0cae-8b5e-42b5-aa3c-df20bb3d0e20) – Tiltag ved styret underboring (beredskabsplan, kontinuerlig monitering, standsning og opsamling ved blow-out), som var forudsætninger for, at padder og flagermus ikke påvirkes, var beskrevet i miljøkonsekvensrapporten og tilladelsen, men ikke fastsat som selvstændige, håndhævbare vilkår. Nævnet stadfæstede, men indsatte tre nye vilkår.  
  Nævnet: «Nævnet finder derfor, at vilkårene i § 25-tilladelsen skal præciseres, og at tiltagene skal fastsættes som vilkår 17, 18 og 19.»
- [MFKN 2024-02-23](https://mfkn.naevneneshus.dk/afgoerelse/a67d4756-ff66-472f-b0dc-ae0dc62130d1) – Tilladelsens vilkår nr. 2 om skyggekast regulerede ikke det samlede skyggekast, så en nabo, der allerede var udsat for over 10 timer fra eksisterende møller, kunne få yderligere skyggekast; nævnet ændrede vilkåret, så projektet ikke må give yderligere skyggekast hos sådanne naboer og samlet maks. 10 timer.  
  Nævnet: «Miljø- og Fødevareklagenævnet finder, at § 25-tilladelsens vilkår nr. 2 skal ændres, så beboelsesejendomme, der bliver påvirket af skyggekast fra vindmøller i projektet, samlet set ikke påføres et skyggekast fra vindmøller på mere end 10 timers reelt skyggekast om året.»

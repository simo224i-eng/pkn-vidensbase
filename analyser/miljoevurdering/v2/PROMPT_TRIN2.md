# Trin 2: hvilke fejl underkendte nævnet? (v2, fuld vurdering)

Du får en liste af sags-id'er, hvor klager helt eller delvist fik medhold. For hvert id læser du
HELE filen `analyser/miljoevurdering/v2/sager/<id>.txt` med Read (lange filer: læs i bidder med
offset/limit, til du har læst nævnets vurdering til ende; nævnets vurdering står under
overskrifter som "## ... Planklagenævnets vurdering", "## ... bemærkninger og afgørelse",
"## Miljø- og Fødevareklagenævnets vurdering"). Spring indholdsfortegnelsen over.

Skriv én JSON-linje pr. sag til den outputfil, du får oplyst (append, ingen anden tekst):

```json
{"id": "...",
 "brugbar": true,
 "grund_hvis_ikke_brugbar": null,
 "dokumenttype": "screening_projekt|screening_plan|miljoerapport_plan|projekttilladelse|husdyrgodkendelse|andet",
 "projekttype": "bolig_byudvikling|vand_natur_klima|fritid_turisme|vindmoeller|solceller|energi_oevrig|erhverv_industri|vej_infrastruktur|raastof|husdyr_landbrug|andet",
 "fejl": [
   {"fejl": "hvad myndigheden gjorde forkert, konkret (1-2 sætninger)",
    "fejlkategori": "<en værdi fra listen nedenfor>",
    "regel": "bestemmelsen nævnet bruger, fx 'miljøvurderingslovens § 21, jf. bilag 6, pkt. 1, litra b'",
    "citat_naevn": "ordret fra NÆVNETS VURDERING, der viser fejlen (1-3 sætninger)",
    "citat_myndighed": "ordret gengivelse af myndighedens egen formulering, hvis afgørelsen citerer den, ellers null",
    "afgoerende": true,
    "tjekpunkt": "spørgsmål en sagsbehandler kunne stille sig selv før afgørelsen, så fejlen var undgået",
    "kunne_fanges_af_tjekliste": "ja|delvist|nej",
    "begrundelse_tjekliste": "kort: hvorfor/hvorfor ikke en tjekliste kunne fange fejlen"}
 ],
 "eu_domme": ["C-127/02"],
 "vejledning_citeret": true,
 "resume": "2-3 sætninger: sagen, fejlen, konsekvensen"}
```

Fejlkategorier (brug præcis disse):
- `omfattet_bilag_projektbegreb` – forkert vurdering af, om planen/projektet er omfattet af loven eller bilag 1/2, projektbegrebet, ændringer/udvidelser
- `afgraensning_opsplitning` – projektet er afgrænset for snævert eller opsplittet, tilhørende anlæg mangler
- `screeningskriterier_ikke_vurderet` – et relevant kriterium i bilag 6 (projekter) eller bilag 3 (planer) er ikke vurderet
- `kumulation` – kumulation med andre projekter/planer er ikke (eller forkert) vurderet
- `sagsoplysning_dokumentation` – myndigheden manglede oplysninger/undersøgelser, eller vurderingen er ikke dokumenteret
- `natura2000_vaesentlighed` – væsentlighedsvurdering/konsekvensvurdering efter habitatreglerne mangler eller er forkert
- `bilagIV_arter` – bilag IV-arter (yngle- og rasteområder, økologisk funktionalitet) ikke undersøgt eller forkert vurderet
- `natur_paragraf3` – § 3-beskyttet natur, anden national natur eller landskab ikke/forkert vurderet
- `afvaergeforanstaltninger` – vurderingen hviler på afværgeforanstaltninger, der ikke er sikret/konkretiseret, eller de er brugt i en screening, hvor det ikke er tilladt
- `materiel_vaesentlighed` – nævnet er uenig i myndighedens vurdering af, om påvirkningen er væsentlig
- `begrundelse` – afgørelsen er ikke tilstrækkeligt begrundet (fx ingen henvisning til kriterierne)
- `miljoerapport_mangelfuld` – miljørapport/miljøkonsekvensrapport mangler indhold (alternativer, 0-alternativ, overvågning, kumulation m.m.)
- `hoering_inddragelse` – høring af berørte myndigheder eller offentligheden mangler/er forkert
- `vilkaar` – vilkår i tilladelsen er ulovlige, uklare eller utilstrækkelige
- `kompetence_procedure` – forkert myndighed, forkert procedure, manglende afgørelse/forkert afgørelsesform
- `plan_forhold` – fejl efter planloven, der ikke er en miljøvurderingsfejl (fx lokalplanens indhold)
- `andet`

Regler:
- Tag ALLE de fejl med, som nævnet selv peger på, ikke kun den første. Markér med `afgoerende`,
  om fejlen alene bar ophævelsen.
- `citat_naevn` og `citat_myndighed` skal stå ordret i filen (tegn for tegn; du må kun forkorte med
  "[…]"). Kontrollér det, før du skriver. Hellere null end et omskrevet citat.
- Skriv ikke fejl ind, som kun klager påstår. Det er nævnets vurdering, der tæller.
- `brugbar` er false, hvis nævnet ikke underkendte myndighedens vurdering af noget indholdsmæssigt
  (fx ophævet som uaktuel, kun formalia om klagefrist). Angiv grunden.
- Ingen personnavne, adresser eller matrikelnumre i felterne (de er i forvejen anonymiseret som [A1] osv.).
- Svar på dansk.

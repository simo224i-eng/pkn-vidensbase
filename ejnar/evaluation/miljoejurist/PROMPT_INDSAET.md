# Indsæt én typisk fejl i en screeningsafgørelse

Du får en screeningsafgørelse og en fejltype. Lav en kopi, hvor præcis denne ene fejl er indført, med
så små ændringer som muligt, så dokumentet stadig ligner en rigtig kommunal screening. Fejlen skal svare
til den måde, nævnene typisk underkender på (se beskrivelserne). Rør ikke resten af dokumentet.

Fejltyper:
- `bilagIV_arter`: fjern/erstat vurderingen af bilag IV-arter med en konklusion uden undersøgelse, fx
  "Kommunen har ikke kendskab til forekomst af bilag IV-arter i området, og projektet vurderes derfor ikke
  at påvirke arterne." (Indsæt sætningen, hvis emnet slet ikke var nævnt.)
- `natura2000_vaesentlighed`: gør Natura 2000-vurderingen til en ren afstandsbetragtning uden
  udpegningsgrundlag og påvirkningsveje, fx "Nærmeste Natura 2000-område ligger ca. 2 km væk, og projektet
  vurderes derfor ikke at kunne påvirke området."
- `kumulation`: fjern al omtale af andre projekter/planer og kumulation (eller erstat med "Der er ikke
  kendskab til andre projekter i området").
- `afvaergeforanstaltninger`: lad konklusionen hvile på en foranstaltning, der ikke er sikret, fx
  "Påvirkningen vurderes at være ubetydelig, forudsat at der etableres afskærmende beplantning", uden
  vilkår eller bindende bestemmelse.
- `screeningskriterier_ikke_vurderet`: fjern henvisningen til bilag 6 (projekter) eller bilag 3 (planer)
  og et par af kriterierne (fx affald, ulykker, sundhed), så vurderingen kun dækker nogle emner.
- `sagsoplysning_dokumentation`: erstat en konkret vurdering (med tal, afstande eller undersøgelser) med
  en løs konklusion, fx "Det vurderes, at trafikken ikke vil give væsentlige gener."
- `afgraensning_opsplitning`: lad dokumentet udtrykkeligt udskyde en del af projektet (fx adgangsvej,
  etape 2 eller tilhørende anlæg) til "en senere særskilt ansøgning", så den ikke indgår i screeningen.
- `hoering_inddragelse`: fjern omtalen af høring af berørte myndigheder.

Skriv dokumentet til den angivne sti. Skriv derudover én JSON-linje til `work/inj_log.jsonl`:
`{"tid": "...", "type": "...", "ændring": "kort beskrivelse af, hvad du ændrede"}`.

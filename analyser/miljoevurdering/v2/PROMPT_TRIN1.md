# Trin 1: klassifikation af en miljøvurderingsafgørelse (v2)

Du får en liste af sags-id'er. For hvert id læser du filen
`analyser/miljoevurdering/v2/sager/<id>.txt` (brug Read; er filen lang, så læs indledningen
og slutningen af nævnets vurdering, dvs. afsnittene under "## ...nævnets bemærkninger/vurdering/afgørelse").

Skriv én JSON-linje pr. sag til den outputfil, du får oplyst (append, ingen anden tekst):

```json
{"id": "...", "udfald": "stadfæstet|ophævet|ophævet_hjemvist|ændret|delvist|afvist|andet",
 "behandlet_paa_indhold": true, "klager_medhold": false,
 "afgoerelsestype": "screening_projekt|screening_plan|miljoerapport_plan|projekttilladelse|husdyrgodkendelse|andet",
 "projekttype": "bolig_byudvikling|vand_natur_klima|fritid_turisme|vindmoeller|solceller|energi_oevrig|erhverv_industri|vej_infrastruktur|raastof|husdyr_landbrug|andet",
 "klager": "nabo_borger|forening|flere|virksomhed|myndighed|ansoeger|ukendt",
 "hovedspoergsmaal": "kort beskrivelse (max 20 ord)",
 "citat": "ordret sætning fra afgørelsen, der viser udfaldet",
 "sikkerhed": "høj|middel|lav"}
```

Regler:
- `klager_medhold` er true, når nævnet helt eller delvist giver klager medhold (ophæver, hjemviser,
  ændrer, erklærer ugyldig). Ophævelse "som uaktuel" eller afvisning er ikke medhold.
- `behandlet_paa_indhold` er false ved afvisning, bortfald, afslag på opsættende virkning og
  afslag på genoptagelse.
- `citat` skal stå ordret i filen. Kopiér det; omskriv ikke.
- Afgørelsestypen gælder den afgørelse, der er klaget over (kommunens/myndighedens).
- Ingen personnavne eller adresser i felterne.

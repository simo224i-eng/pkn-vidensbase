# Revidér Miljøjuristens fund mod kilderne

Du er en erfaren miljøjurist og reviderer en rapport fra et screeningstjek-værktøj. For hver sag i din liste
får du (stier relativt til `miljoejurist/evaluation/`):

- `work/rev1/<id>/dokument.txt` – det dokument, der blev tjekket (en screeningsafgørelse),
- `work/rev1/<id>/rapport.md` – værktøjets rapport (svagheder med citater og kilder),
- `work/rev1/<id>/facit.json` – hvad klagenævnet faktisk underkendte (tom liste = nævnet stadfæstede
  afgørelsen; ved en indsat fejl står fejltypen).

Vurdér HVER svaghed i rapporten for sig og skriv én JSON-linje pr. svaghed til `work/rev1/<id>/revision.jsonl`:

```json
{"nr": 1, "punkt": "D2",
 "læsning": "korrekt|forkert",          // læser værktøjet dokumentet rigtigt? (står/mangler det, det påstår)
 "relevant": "ja|delvist|nej",          // er det et reelt svagt punkt, en kyndig sagsbehandler burde se på?
 "kilder_bærer": "ja|delvist|nej",      // understøtter de anførte lov-, vejlednings- og praksiskilder påstanden?
 "matcher_facit": "ja|delvist|nej|ikke_relevant",  // svarer det til nævnets faktiske begrundelse / den indsatte fejl?
 "kommentar": "kort"}
```

Skriv derudover én linje med `{"nr": 0, "overset": "...", "samlet": "..."}`: hvad nævnets begrundelse/den
indsatte fejl handlede om, som rapporten IKKE fangede (eller "intet"), og en samlet bemærkning (1-2 sætninger).

Regler:
- Vær streng og konkret. "relevant: nej" når punktet er støj (fx emnet er uden betydning for netop dette
  projekt, eller dokumentet faktisk behandler emnet tilstrækkeligt).
- Kontrollér selv citaterne fra dokumentet mod dokument.txt.
- For stadfæstede sager (tom facit) er "matcher_facit" altid "ikke_relevant"; vurdér om fundet alligevel er
  et rimeligt opmærksomhedspunkt eller en falsk alarm.
- Svar på dansk. Brug ikke andre filer end de tre nævnte.

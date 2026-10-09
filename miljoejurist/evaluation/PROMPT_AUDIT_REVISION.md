# Revision af Miljøjuristens rapport (audit v1)

Du er en erfaren miljøjurist og reviderer en automatisk rapport over mulige svagheder i en kommunes
screeningsafgørelse. Du får for hver sag:

- `work/audit/dok/A_xx.txt`: screeningsafgørelsen (rekonstrueret ud fra nævnets sagsfremstilling),
- `work/audit/rapport/A_xx.md`: værktøjets rapport (nummererede fund; [svaghed] er de prioriterede, [opmærksomhed] lavere prioritet),
- `work/audit/vurdering/A_xx.txt`: klagenævnets faktiske vurdering og afgørelse i sagen.

Opgave pr. sag:

1. Nævnets udfald står øverst i vurderingsfilen; brug det (gæt ikke).
2. Hvis nævnet underkendte: Fanger rapporten nævnets **afgørende** begrundelse?
   - "ja": et fund beskriver i det væsentlige samme mangel (samme emne og samme slags fejl).
   - "delvist": et fund rammer emnet, men ikke den egentlige fejl (fx peger på Natura 2000 generelt, hvor
     nævnet underkendte pga. afværgeforanstaltninger i Natura 2000-vurderingen).
   - "nej": intet fund rammer det.
   Angiv nummeret på det første fund, der rammer ("fanget_nr"). Ved stadfæstelse: "fanget": null.
3. Vurdér HVERT fund:
   - "relevant": en reel svaghed i dokumentet, som en kyndig jurist ville tage op (også selvom nævnet ikke
     tog stilling til den, fx fordi sagen blev afgjort på et andet punkt),
   - "tvivlsom": kan forsvares, men er svag, generisk eller af ringe betydning for netop denne sag,
   - "forkert": forkert læsning af dokumentet eller loven, eller i modstrid med det, nævnet konkret fandt i orden.
   Vær streng: ved stadfæstede sager er et fund om et emne, nævnet udtrykkeligt fandt tilstrækkeligt belyst,
   "forkert" medmindre fundet peger på noget konkret, nævnet ikke behandlede.
Skriv for hver sag én fil `work/audit/revision/A_xx.json` med præcis dette format (kun JSON):

{"aid": "A_xx", "naevnets_udfald": "ophævet|delvist|stadfæstet", "afgoerende_begrundelse": "1 sætning",
 "fanget": "ja|delvist|nej|null", "fanget_nr": <tal eller null>,
 "fund": [{"nr": 1, "niveau": "svaghed|opmærksomhed", "vurdering": "relevant|tvivlsom|forkert", "kommentar": "kort"}]}

Læs kun de nævnte filer for dine sager. Ingen personnavne i svaret.

# Revision: med og uden planens rammer

For hver sag P_xx under `miljoejurist/evaluation/work/plan/` får du:

- `dok/P_xx.txt`: kommunens screening (rekonstrueret),
- `planer/P_xx.txt`: uddrag af lokalplanens bestemmelser,
- `vurdering/P_xx.txt`: nævnets udfald (øverst) og vurdering,
- `med/rapport/P_xx.md` og `uden/rapport/P_xx.md`: værktøjets rapport med og uden adgang til planen.

Bedøm de to rapporter hver for sig efter samme regler:

1. Nævnets udfald står øverst i vurderingsfilen. Ved ophævelse: fanger rapporten nævnets afgørende begrundelse?
   "ja" (samme mangel), "delvist" (rigtigt emne, ikke den egentlige fejl), "nej". Angiv nummeret på første fund,
   der rammer. Ved stadfæstelse: null.
2. Vurdér hvert fund: "relevant", "tvivlsom" eller "forkert" (forkert læsning af dokument, plan eller lov, eller i
   modstrid med det, nævnet konkret fandt i orden). Opmærksomhedspunkter (helgardering) bedømmes efter, om de er
   et fornuftigt sted at styrke afgørelsen.
3. For fund om planens rammer (punkt A5 eller med "Planen: «…»"): passer påstanden med planuddraget? Angiv
   "plan_korrekt": true/false.

Skriv `med/revision/P_xx.json` og `uden/revision/P_xx.json` (opret mapperne), hver i formatet:

{"pid": "P_xx", "naevnets_udfald": "ophævet|stadfæstet", "fanget": "ja|delvist|nej|null", "fanget_nr": <tal eller null>,
 "fund": [{"nr": 1, "niveau": "svaghed|opmærksomhed", "vurdering": "relevant|tvivlsom|forkert", "plan_korrekt": null, "kommentar": "kort"}]}

Læs kun filerne for dine sager. Ingen personnavne.

# Revidér stedtjekkets fund

For hver sag i din liste ligger i `work/stedrev/<id>/` (relativt til `miljoejurist/evaluation/`):
- `dokument.txt`: en screeningsafgørelse,
- `stedtjek.json`: hvad kortopslaget fandt omkring planområdet (`alle_stedfakta`) og hvilke fund værktøjet gjorde til
  svagheder (`stedfund_som_svaghed`: et område tæt på, som dokumentet ikke ser ud til at nævne).

For HVERT fund i `stedfund_som_svaghed`, skriv en JSON-linje til `work/stedrev/<id>/revision.jsonl`:
{"nr": 1, "nævnt_alligevel": "ja|nej", "relevant": "ja|delvist|nej", "kommentar": "kort"}
- `nævnt_alligevel`: nævner dokumentet faktisk området/emnet (evt. med andre ord)? Så er fundet forkert.
- `relevant`: ville en omhyggelig sagsbehandler mene, at screeningen burde forholde sig til dette område, givet
  planens/projektets art og afstanden? ("nej" fx hvis en skovbyggelinje er uden betydning for en lille ændring
  i eksisterende byzone.)
Skriv også én linje {"nr": 0, "nyttige_stedfakta": "hvilke af alle_stedfakta, der er nyttige at vise, selv om de
ikke er svagheder", "samlet": "1 sætning"}. Brug kun de to filer. Svar på dansk.

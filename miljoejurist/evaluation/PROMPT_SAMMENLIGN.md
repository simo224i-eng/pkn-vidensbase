# Hvad giver den oprindelige screening, som nævnets afgørelse ikke gengiver?

For hver sag i din liste ligger to filer i `work/pilot/sammenlign/<id>/` (relativt til
`miljoejurist/evaluation/`):
- `original.txt` – myndighedens oprindelige screening/planforslag (kan være lang; læs det hele i bidder),
- `afgoerelse.txt` – klagenævnets afgørelse (sagsfremstilling + nævnets vurdering).

Spørgsmålet er, om man har brug for originalen for at forstå og finde svaghederne, eller om nævnets gengivelse
er nok. Skriv én JSON-linje til `work/pilot/sammenlign/<id>/svar.json`:

```json
{"id": "...",
 "naevnets_fejl": ["kort: hvad nævnet underkendte"],
 "gengivet_i_afgoerelsen": "ja|delvist|nej",   // er de dele af originalen, fejlen handler om, gengivet i afgørelsen?
 "ekstra_i_original": [{"hvad": "konkret oplysning/formulering i originalen, som afgørelsen ikke gengiver",
                         "citat": "ordret fra original.txt", "betydning": "høj|middel|lav"}],
 "andre_svagheder_i_original": ["svage punkter i originalen, som nævnet ikke tog stilling til"],
 "nyttig_til_opslag": "1-2 sætninger: hvad en sagsbehandler får ud af at se originalen ved siden af afgørelsen",
 "konklusion": "er originalen nødvendig for at finde nævnets fejl? (1-2 sætninger)"}
```
Citater skal være ordrette. Ingen personnavne. Brug kun de to filer.

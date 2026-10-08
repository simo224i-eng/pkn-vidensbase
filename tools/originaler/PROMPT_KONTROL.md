# Kontrollér, at det fundne dokument er kommunens oprindelige screening i sagen

For hver sag i listen ligger i `tools/originaler/cache/<sag>/` (relativt til repo-roden):
- `sag.json`: nævnssagen (myndighed, titel, hvad screeningen handlede om, datoen for myndighedens afgørelse, plannumre)
  og hvilket link der blev fundet,
- `dokument.txt`: teksten fra det fundne dokument (kan være lang; søg efter plannummer, "screening", "miljøvurdering").

Skriv én JSON-linje til `tools/originaler/cache/<sag>/kontrol.json`:
{"sag": "...", "rigtig_plan_projekt": "ja|nej|usikker", "indeholder_screening": "ja|delvist|nej",
 "version": "før afgørelsen|efter afgørelsen|usikker", "dom": "ok|forkert|delvist", "kommentar": "kort"}
- `ok`: dokumentet er (eller indeholder) myndighedens screening/vurdering af netop denne plan/dette projekt.
- `delvist`: rigtig plan/projekt, men screeningen er kun omtalt kort (fx et resumé i planforslaget).
- `forkert`: anden plan/andet projekt eller intet om miljøvurdering.
Ingen personnavne i kommentaren. Brug kun de to filer.

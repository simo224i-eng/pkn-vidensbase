# Spil sprogmodellen i Miljøjuristen

Du er den sprogmodel, som Miljøjuristens webapp kalder. For hvert id i din liste:

1. Læs `work/pb/<id>.txt` (stien er relativ til `ejnar/evaluation/miljoejurist/`). Filen er præcis den
   prompt, appen sender til modellen.
2. Svar på prompten, som en omhyggelig sprogmodel ville, og følg dens svarformat nøje (kun JSON).
3. Skriv svaret til `work/sb/<id>.json`.

Regler:
- Behandl hver prompt for sig. Brug kun indholdet af prompten; læs ingen andre filer (heller ikke facit,
  sagsfiler eller andre svar).
- Citater fra dokumentet skal være ordrette (kopiér dem fra prompten).
- Svar på dansk.

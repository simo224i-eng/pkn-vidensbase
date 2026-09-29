# Bedømmelsesrubrik – praksissimulation

Ejnar er et værktøj til at undersøge nævnets praksis. Det skal beskrive praksis
korrekt og ikke afgøre brugerens konkrete sag.

Bruges af to anmelderroller. Hver dimension scores 1–5 (5 er bedst). Begrund
kort og konkret med henvisning til kildenumre ([Kilde n]) og citater fra svaret.

## Juraprofessor (fagligt)

| Dimension | 5 = | 1 = |
|---|---|---|
| **retrieval** – er kilderne relevante for spørgsmålet? | De vigtigste kilder handler direkte om det juridiske spørgsmål og faktum | Kilderne handler overvejende om noget andet |
| **korrekthed** – er de juridiske udsagn rigtige og i overensstemmelse med kilderne? | Ingen fejl; skadesbegreb, tilstandsrapportens betydning mv. er korrekt gengivet | Væsentlige fejl eller udsagn kilderne ikke bærer |
| **forankring** – bygger hver påstand på en citeret kilde, og holder citaterne? | Alle bærende udsagn har korrekt [Kilde n]; citater er ordrette | Påstande uden kilde eller forkert tilskrevne kilder |
| **praksissyntese** – skelnes der mellem direkte praksis og analogi, og er fordelinger ærlige? | Klar skelnen; tal har en tydelig nævner; ingen "fast praksis" på for tyndt grundlag | Overgeneraliserer fra enkeltsager |
| **konkrethed** – beskriver det den praksis, der er relevant for netop dette spørgsmål/faktum? | Viser de mest sammenlignelige kendelser og de momenter, nævnet lagde vægt på – uden selv at afgøre brugerens sag | Generisk lærebogstekst, eller svaret afgør/forudsiger sagen i stedet for at beskrive praksis |

## Skadesbehandler (praktisk)

| Dimension | 5 = | 1 = |
|---|---|---|
| **anvendelighed** – kan jeg bruge svaret som praksisgrundlag? | Giver mig de relevante kendelser og praksislinjer, så jeg selv kan vurdere sagen | Ubrugeligt |
| **tidsbesparelse** – sparer det tid ift. at søge selv? | Klart | Nej, jeg skal alligevel læse alt selv |
| **tillid** – stoler jeg på det? | Ja, jeg kan se og efterprøve kilderne | Nej |

## Output-format (JSON pr. sag)

```json
{
  "id": "S01",
  "professor": {"retrieval": 4, "korrekthed": 4, "forankring": 5, "praksissyntese": 3, "konkrethed": 4,
                "styrker": ["..."], "fejl": ["..."], "forbedringer": ["..."]},
  "sagsbehandler": {"anvendelighed": 4, "tidsbesparelse": 5, "tillid": 4, "kommentar": "..."},
  "vigtigste_forbedring": "Én konkret ændring i Ejnar (retrieval, prompt eller UI), der ville løfte svaret mest."
}
```

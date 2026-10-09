# Miljøjuristen: 2 uger til første kunde (9.–23. oktober 2026)

**Mål:** én betalende pilotkunde (eller en underskrevet pilotaftale med pris) senest fredag 23. oktober.
Realistisk minimum: 3 demoer holdt og 1 kunde, der har fået rapporter på egne sager og siger ja til at betale.

## Hvem er første kunde?

| Segment | Hvorfor de betaler | Hastighed | Vurdering |
|---|---|---|---|
| **Miljørådgivere** der skriver screeninger for kommuner og bygherrer | Kvalitetssikring før aflevering; færre hjemvisninger | Hurtig beslutning (fagchef) | **Bedst til kunde 1** |
| **Bygherrer/udviklere** (sol, biogas, råstof, boliger) | En ophævelse koster måneder; tjek før kommunen træffer afgørelse | Hurtig, høj værdi | **Godt match** |
| **Miljø- og planadvokater** | Hurtigere første gennemgang af klagesager med kilder | Middel | God, men kræver høj præcision |
| Kommuner (planafdeling) | Tjek før udsendelse | Langsom (indkøb, IT, GDPR) | Senere |
| Klagere / foreninger | Find klagepunkter | Hurtig, lav betalingsevne | Gratis/lav pris, godt til omtale |

**Tilbud:** "Screeningstjek før udsendelse". Upload screeningen; få på 2 minutter svaghederne med lov, vejledning,
EU-domme og lignende nævnssager. Pilot: fast pris for en måned (fx 2.500–5.000 kr. ekskl. moms) eller pr. rapport.
Rapporten erstatter ikke juristens vurdering; den sparer tid og fanger det, nævnene typisk underkender.

## Uge 1 (fre 9.–fre 16. okt): Klar til at vise og sælge

| Dag | Produkt (Claude) | Salg (dig) |
|---|---|---|
| Fre 9 | Audit v1 på 40 nye sager (fejlfangst, falske alarmer, udfaldsgæt) | Skriv listen: 20 navngivne mål (rådgivere, udviklere, advokater) |
| Man 12 | Ret de største svagheder fra auditten; vælg standardmodel (Haiku vs. Sonnet) ud fra tal | Første 10 henvendelser (LinkedIn/mail, personligt, kort) |
| Tir 13 | Hosted version: lille server, adgangsnøgle pr. kunde, intet gemmes, logning uden dokumenttekst | Næste 10 henvendelser; book demoer til uge 2 |
| Ons 14 | Rapport-PDF med pænt layout + "hvad er ikke vurderet" | Skaf en Anthropic API-konto på erhvervsvilkår (databehandleraftale) |
| Tor 15 | Demo-case: Gladsaxe kommuneplan 2025 (ægte, ophævet, fundet som nr. 1) + 2 andre | Én-sides salgsark og vilkår (ansvarsfraskrivelse, fortrolighed, pris) |
| Fre 16 | Kør 3–5 af kundens egne (offentlige) screeninger på forhånd, så demoen er på deres sager | Følg op på ubesvarede |

## Uge 2 (man 19.–fre 23. okt): Demoer og første aftale

| Dag | Produkt (Claude) | Salg (dig) |
|---|---|---|
| Man 19 | Rettelser fra første demo | Demo 1–2 |
| Tir 20 | Kundespecifikke ønsker, hvis små (fx eksport til Word) | Demo 3; send pilottilbud samme dag |
| Ons 21 | Opret kundens nøgle; onboarding-vejledning (1 side) | Følg op på tilbud |
| Tor 22 | Kør pilotkundens første rigtige sager; kvalitetstjek rapporterne før de sendes | Første faktura / underskrift |
| Fre 23 | Opsamling: hvad virkede, hvad mangler; plan for kunde 2–5 | Bed om citat/reference |

## Forudsætninger og risici

- **Sprogmodel til kunder:** dit Claude-abonnement (claude_cli) må kun bruges privat. Kunder kræver en API-nøgle
  med databehandleraftale (Anthropic API på erhvervsvilkår). Pris pr. rapport er lav (få kroner med Sonnet,
  mindre med Haiku); vælg ud fra auditten.
- **Kvalitet:** testene er AI-bedømte, og værktøjet giver falske alarmer (ca. 30 % i stadfæstede sager).
  Sælg det som en tjekliste med kilder, ikke som en dom. Du gennemlæser de første kunders rapporter selv.
- **Ansvar:** klare vilkår om, at rapporten er beslutningsstøtte; ingen garanti for udfald.
- **Persondata:** screeninger er offentlige, men kan indeholde navne. Intet gemmes; nævn det i vilkårene.
- **Det, jeg ikke kan:** sende mails, kontakte kunder eller indgå aftaler. Det er dit spor; jeg laver materialet.

## Målepunkter

Henvendelser sendt (20) · svar (≥5) · demoer (≥3) · pilottilbud (≥2) · første kunde (1).

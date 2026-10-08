# Beslutninger (lokal session, oktober 2026)

Løbende log over de valg, der er truffet uden at spørge. Nyeste nederst.

## Setup
- **Projektnavn:** Værktøjet hedder **Miljøjuristen** (brugerens ønske: "miljøkonsulenten/miljøjuristen").
  Det bygges som modulet `ejnar/miljoejurist/` med egen fane i Ejnar-webappen, så det genbruger
  søgning, citatkontrol og server. Det deler intet med Harald.
- Navnet til trods giver værktøjet ikke juridisk rådgivning og skriver aldrig, at en afgørelse er i orden.
- Lokalt Python-miljø i `.venv/` (gitignoreret).

## Data
- **Nævnenes Hus' API kræver ingen cookie.** Kategori-id'er hentes fra `/api/sitesettings`, og
  `/api/search` returnerer hele afgørelsesteksten (HTML) i søgeresultatet, 100 pr. side. Derfor er
  `scrape_pkn.py` og `scrape_mfkn.py` skrevet om til det fælles modul `naevn_api.py`. Ingen
  enkeltsidehentning, ca. 1 forespørgsel pr. sekund.
- **Nye filer** ligger i `data_2026/` ved siden af de gamle filer i roden (som ikke er rørt).
  Format: `id, Naevn, Jnr, Dato, Titel, Link, Retsomraade, Tekst`. Teksten er ren tekst, hvor
  HTML-overskrifter står på egen linje med `## ` foran, så nævnets vurdering kan findes ved
  overskrift og ikke ved første forekomst i indholdsfortegnelsen.
- **Kategorier (PKN):** Miljøvurderingsloven, Planloven VVM, Planloven retlig og landzone (før og
  efter 1/2 2017), Sommerhusloven, Ekspropriation. Aktindsigt, Samlingssteds- og Kolonihaveloven er
  udeladt (ikke relevante for screeninger).
- **Kategorier (MFKN):** Miljøvurdering (projekter og planer), Husdyrbrugloven, Miljøbeskyttelsesloven,
  NBL (alle fire), Fredning, Råstof, Vandløb, Vandforsyning, Kystbeskyttelse, Skov, Jordforurening,
  Miljømål, Havmiljø, Museumsloven. Fødevarer, støtteordninger, dyrevelfærd, fiskeri, aktindsigt mv.
  er udeladt.
- **Lovgrundlag** hentes som XML fra retsinformation (ELI) med `fetch_lovgrundlag.py` til
  `lovgrundlag/`. Gældende versioner pr. 8/10/2026 ifølge retsinformations søgning: miljøvurderingsloven
  LBK 4/2023 (+ BEK 1375/2025 om bilag 2), miljøvurderingsbekendtgørelsen BEK 1608/2024,
  habitatbekendtgørelsen BEK 1098/2023, planloven LBK 572/2024, naturbeskyttelsesloven LBK 927/2024,
  husdyrbrugloven LBK 1065/2025 og vejledningerne 2024/9093 (projekter), 2024/9094 (planer),
  Habitatvejledningen 2020/9925, Landzonevejledningen og §3-vejledningen.
- **Forbehold:** LBK 4/2023 indarbejder ikke ændringslovene fra 2024–2026 (CO2, havvind, BBNJ m.fl.).
  De berører primært havområdet og energiprojekter; det står som kendt svaghed.
- **Bilag IV-vejledning:** Habitatvejledningen (2020/9925) er den officielle vejledning om bilag IV-arter
  på retsinformation. Miljøstyrelsens særskilte bilag IV-materiale hentes, hvis det kan findes som PDF.

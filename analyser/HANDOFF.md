# Overlevering: praksisanalyser og "screeningstjek"

Status for analyserne af Planklagenævnets (PKN) og Miljø- og Fødevareklagenævnets
(MFKN) afgørelser og planen for et screeningstjek. Læs denne fil først.

## Formål

Undersøge, hvor og hvorfor nævnene underkender kommunernes afgørelser, og bygge et
værktøj, hvor en rådgiver eller kommune uploader en screeningsafgørelse (eller
miljørapport/tilladelse) og får svaghederne. Svaghederne holdes op mod lovens krav,
vejledningen og lignende nævnsafgørelser, med citater og links.

## Hvad der er lavet

### 1. PKN-pilot (`pkn_pilot/`)
- 245 PKN-afgørelser fra 2022–2025 (100 landzone, 100 lokalplan, 45 solceller).
- `result_*.jsonl`: udfald, medhold, klager, grunde, citat. Alle citater er ordrette.
- `fejl_*.jsonl`: de konkrete kommunefejl i de 74 sager med medhold. `fejl_redo.jsonl`
  erstatter de tilsvarende id'er i `fejl_1/2`.
- Resultat: klager fik medhold i 30 % (39 % af sagerne behandlet på indholdet). Landzone
  45 %. 52 af 62 brugbare fejl kunne realistisk fanges med en tjekliste.
- Hyppigste fejl: landzonevurderingen, fortolkning af lokalplanen, lovliggørelse/påbud,
  og grænserne for dispensation.

### 2. Miljøvurdering (`miljoevurdering/`)
- 901 afgørelser fra 2020 og frem: PKN-miljøvurderingsloven, MFKN konkrete projekter,
  MFKN planer og programmer. 41 manglede tekst i datafilerne og er udeladt.
- `s1_*.jsonl` (trin 1): udfald, behandlet på indholdet, medhold, afgørelsestype,
  projekttype, klager. `meta.json` mapper id (Mxxx) til nævn, dato, titel og link.
- `deep_*.jsonl` (trin 2): de konkrete fejl i de 202 sager med medhold.
- Resultat trin 1 (604 sager behandlet på indholdet): medhold 33 %. Projekttilladelser
  48 %, projekt-screeninger 40 %, miljørapporter for planer 29 %, plan-screeninger 21 %.
  MFKN 41 % mod PKN 24 %. PKN-tallet passer med nævnets egen årsberetning (23 %
  tilsidesat i 2024).

## Kendte problemer i data

- Datafilerne i repo-roden (`pkn_*`, `mfkn_*`) slutter omkring marts 2026 og dækker
  ikke alle kategorier. PKN afgør ca. 1.100–1.200 sager om året; vi har 800–1.000.
- Nogle afgørelser mangler tekst, eller teksten er afkortet i datafilerne.
- Afgørelserne indeholder en indholdsfortegnelse. Find nævnets vurdering ved den
  overskrift, der står efter indholdsfortegnelsen, ikke den første forekomst.
- En simpel regex finder kun udfaldet i ca. halvdelen af afgørelserne og overser især
  stadfæstelser. Brug en model eller en bedre regel.
- Trin 2 brugte kun 9.000 tegn af nævnets vurdering. I lange afgørelser er
  konklusionen derfor skåret af (markeret i feltet "fejl").

## Næste skridt

1. Hent alle relevante PKN- og MFKN-afgørelser frem til i dag (`scrape_pkn.py`,
   `scrape_mfkn.py`).
2. Hent fuld lovtekst og vejledning: miljøvurderingsloven med bilag,
   habitatbekendtgørelsen, Miljøstyrelsens vejledning om miljøvurdering (retsinformation
   2024/9093), vejledningen om bilag IV-arter, og planloven.
3. Hent de EU-domme, som nævnene selv citerer (sagsnumre som C-xxx/yy i teksterne).
4. Find kommunernes oprindelige screeninger for de underkendte sager (plandata.dk,
   kommunernes hjemmesider).
5. Lav en tjekliste ud fra loven og få den gennemgået af en fagperson.
6. Byg screeningstjekket ovenpå Ejnar (søgning, kildekontrol, webapp) og test det:
   rekonstruerede screeninger, indsatte fejl, falske alarmer og ægte dokumenter.

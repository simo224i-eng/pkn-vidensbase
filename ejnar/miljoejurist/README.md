# Miljøjuristen – screeningstjek

Miljøjuristen finder mulige svagheder i en screeningsafgørelse (projekt efter miljøvurderingslovens § 21 eller
plan efter § 10), en miljørapport eller en § 25-tilladelse. Hver svaghed vises som
**svaghed → hvorfor → kilder**:

- **Svaghed:** hvad der ser svagt ud, med et ordret citat fra dokumentet (eller en konstatering af, at emnet
  ikke ses behandlet).
- **Hvorfor:** lovkravet og hvor ofte nævnene har underkendt på det.
- **Kilder:** ordrette uddrag af loven (retsinformation), vejledningen, EU-Domstolen og lignende afgørelser fra
  Planklagenævnet og Miljø- og Fødevareklagenævnet, med links.

Rapporten slutter altid med **hvad værktøjet ikke har vurderet**. Værktøjet skriver aldrig, at en afgørelse er i
orden; at der ikke er fundet noget, betyder kun, at kontrollerne ikke slog ud.

## Sådan virker det

| Lag | Hvad | Kræver |
|---|---|---|
| Regler (`tjek.py`) | Tjeklistens 19 punkter som mønstre: er emnet behandlet, er der grundlag, er formuleringen svag? Bilag 6-/bilag 3-kriterier. Søgning i praksis. | Intet (kører altid) |
| Sprogmodel (`llm_tjek.py`) | En model gennemgår dokumentet mod tjeklisten og praksis og returnerer JSON. Citater kontrolleres automatisk, og fund med citater, der ikke står ordret i dokumentet, fjernes. | En konfigureret udbyder (Ejnars `LLM_PROVIDER`), og at brugeren vælger "Brug også sprogmodel" |
| Citatkontrol (`citatkontrol.py`) | Alle citater fra dokument, lov, vejledning, EU-domme og afgørelser kontrolleres som ordrette (tåler linjeskift, orddeling og "[…]"). | – |

Fundene sorteres efter vægt (hvor ofte nævnene har underkendt på punktet × hvor konkret fundet er). De højst
prioriterede (op til 6) vises som **svagheder**, resten som **øvrige opmærksomhedspunkter**.

## Filer

| Fil | Indhold |
|---|---|
| `corpus.py` | Indlæsning og rensning af nævnsafgørelserne i `data_2026/` (dubletter, tomme tekster, udfald, nævnets vurdering) |
| `lovkilder.py` | Lov, vejledning og EU-domme som opslag (`slå_op("mvl", "§ 21")`) og søgning |
| `praksis.py` | Underkendte sager med kontrollerede citater (fra trin 2-analysen) og søgning i dem |
| `tjekliste_grund.py` | Tjeklistens punkter: spørgsmål, lovuddrag, mønstre |
| `byg_tjekliste.py` | Bygger `data/tjekliste.json`, `data/praksis.json` og `analyser/TJEKLISTE.md` |
| `tjek.py` | Regellaget og rapporten (JSON og Markdown) |
| `llm_tjek.py` | Prompt til sprogmodellen og fletning af svaret |
| `dokument.py` | Læser PDF, Word, HTML og tekst og deler i sætninger |
| `api_routes.py` | `POST /v1/miljoejurist/tjek` (upload), `POST /v1/miljoejurist/tjek-tekst`, `GET /v1/miljoejurist/tjekliste`, `GET /v1/miljoejurist/kilder` |

Webappen (`ejnar/web/`) har fanen **Miljøjuristen**. Start som for Ejnar (`uvicorn api:app` fra `ejnar/`).
Uploadede dokumenter gemmes ikke.

## Opdatér datagrundlaget

```bash
python scrape_pkn.py --relevante && python scrape_mfkn.py --relevante && python fetch_pdf_afgoerelser.py
python fetch_lovgrundlag.py && python fetch_eu_domme.py
cd ejnar && python -m miljoejurist.corpus
python ../analyser/miljoevurdering/v2/forbered.py   # derefter trin 1 og 2 for nye sager (se PROMPT_TRIN*.md)
python -m miljoejurist.byg_tjekliste
```

## Test

`ejnar/tests/test_miljoejurist.py` (unit-tests) og `ejnar/evaluation/miljoejurist/` (rekonstruerede
screeninger, indsatte fejl, falske alarmer og ægte screeninger; resultater i `RESULTS.md` dér).

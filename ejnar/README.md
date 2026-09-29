# Ejnar — Praksisdatabase for ejerskifteforsikring

Selvstændig Streamlit-app der spejler Harald's RAG-løsning og UI, men er
udelukkende fokuseret på Ankenævnet for Forsikrings (AKF) praksis om
**ejerskifteforsikring** efter lov om forbrugerbeskyttelse ved erhvervelse af
fast ejendom mv.

Ejnar deler git-repo med Harald (`pkn-vidensbase`) men er en helt separat app:
egen `app.py`, egen `shared.py`, egne data-filer og embedding-cache. De to
apps kan deployes uafhængigt.

## Webapp og REST-API (anbefalet)

Ud over Streamlit-appen har Ejnar nu en selvstændig webapp (`web/`) og et
REST-API (`api.py`, FastAPI). De kører som én server og deler søge- og
RAG-motoren i `engine.py` med Streamlit-appen.

**Webappen har:**

- **Assistent:** stil praksisspørgsmål og få svar streamet med klikbare
  kildehenvisninger. Ved siden af svaret vises en kildeoversigt med udfald,
  og citatkontrollen advarer om citater, der ikke findes ordret i kilderne.
- **Praksissøgning:** vælg mellem relevans, ordret søgning og AI-søgning.
  Filtre, udfaldsfordeling og direkte opslag på sagsnummer er med.
- **Indsigt:** udfaldsrater pr. år, mangeltype og selskab. Klik på en række
  for at filtrere.
- **Læser:** kendelsen i ren typografi med AI-resumé, reference til
  udklipsholder og gemte kendelser.

### Kør lokalt

```bash
cd ejnar
pip install -r requirements.txt -r requirements-api.txt
export EJNAR_API_KEYS="skift-mig"              # adgangsnøgle(r), kommasepareret
export LLM_PROVIDER="gemini" LLM_API_KEY="..."  # eller ANTHROPIC_API_KEY=...
export VOYAGE_API_KEY="..."                     # valgfri: hybrid semantisk søgning
uvicorn api:app --port 8000
```

Åbn http://localhost:8000 og log ind med nøglen fra `EJNAR_API_KEYS`. Den
interaktive API-dokumentation ligger på http://localhost:8000/docs.

### Deploy (Docker)

```bash
docker build -f ejnar/Dockerfile -t ejnar .     # fra repo-roden
docker run -p 8000:8000 -e EJNAR_API_KEYS=... -e LLM_PROVIDER=gemini -e LLM_API_KEY=... ejnar
```

Imaget kan køre på fx Render, Fly.io, Railway eller Google Cloud Run. Giv
containeren mindst 1,5 GB RAM, fordi korpus og indeks holdes i hukommelsen.
Opstarten tager 1–2 minutter, mens kendelserne indlæses. Imens svarer
`/health` med `loading`, og webappen viser en ventestatus.

| Miljøvariabel | Betydning |
|---|---|
| `EJNAR_API_KEYS` | Påkrævet. Kommaseparerede adgangsnøgler (bruges også til login i webappen) |
| `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_FAST_MODEL`, `LLM_BASE_URL` | Sprogmodel, se nedenfor |
| `VOYAGE_API_KEY` | Hybrid semantisk søgning og rerank |
| `EJNAR_LLM_RATE_PER_MIN` | Maks. AI-kald pr. nøgle pr. minut (standard 20, 0 = fra) |
| `EJNAR_CORS_ORIGINS` | Kommaseparerede origins, hvis en anden frontend kalder API'et |
| `EJNAR_API_EMBEDDINGS=0` | Spring embeddings over (hurtigere opstart, kun TF-IDF) |

### API

| Endpoint | Formål |
|---|---|
| `GET /health` | Status, antal kendelser, søgemetode og model (offentlig) |
| `GET /v1/meta` | Filterværdier og nøgletal |
| `POST /v1/search` | `mode`: `keyword` (TF-IDF), `exact` (ordret frase/sagsnummer) eller `smart` (fuld RAG-retrieval) |
| `POST /v1/stats` | Udfaldsstatistik pr. år, mangeltype og selskab |
| `GET /v1/decisions/{id eller sagsnr.}` | Fuld kendelse |
| `POST /v1/decisions/{id}/summary` | AI-resumé |
| `POST /v1/answer` | RAG-svar med kilder. `stream: true` giver Server-Sent Events: `sources` → `delta`* → `done` |

Alle `/v1`-kald kræver headeren `X-API-Key: <nøgle>` (eller `Authorization: Bearer <nøgle>`).

### Datakvalitet

`engine.prepare_frame` genberegner **udfald** og **mangeltype** ved indlæsning:

- **Udfald** læses fra AKF's resultatlinje i titlen ("Selskab medhold.",
  "Klager delvis medhold.", "Sag afvist."). Findes den ikke, bruges
  konklusionen efter "bestemmes". Scraperens felt bruges kun som sidste udvej.
  Det reducerede "Ukendt" fra 3.114 til 13 kendelser.
- **Mangeltype** bestemmes med ordgrænse-regex på AKF's resumé. Den gamle
  delstrengsmatch mærkede 100 % af kendelserne som "Tag/tagdækning".

## Struktur

```
ejnar/
├── app.py                          # entry-point med adgangskode
├── shared.py                       # CSS, RAG-pipeline, LLM, embeddings (kopi af Harald, rebrandet)
├── scrape_ejnar.py                 # scraper til ankeforsikring.dk
├── build_embeddings.py             # Voyage embeddings-builder
├── requirements.txt
├── .streamlit/config.toml
├── pages/
│   ├── home.py                     # forside
│   └── ejnar.py                    # søgning + statistik + AI-assistent
├── embeds/                         # gemte .npz embedding-caches (auto-pushet til GitHub)
└── ejnar_ejerskifteforsikring.csv  # kendelses-data (oprettes af scraperen)
```

## Streamlit Cloud deploy

Opret en ny Streamlit Cloud-app og peg på dette repo:

- **Repository:** `simo224i-eng/pkn-vidensbase`
- **Branch:** `main` (efter merge)
- **Main file path:** `ejnar/app.py`

Tilføj følgende secrets:

```toml
APP_PASSWORD       = "..."
ANTHROPIC_API_KEY  = "..."
VOYAGE_API_KEY     = "..."     # valgfri – aktiverer hybrid semantisk søgning
GITHUB_TOKEN       = "..."     # valgfri – auto-pusher byggede embeddings til repoet
```

### Billig LLM i stedet for Claude (valgfrit)

Alle LLM-kald går gennem `llm_provider.py`. Uden ekstra secrets bruges Claude
som hidtil. Vil du bruge en billigere model, skal du tilføje fx:

```toml
LLM_PROVIDER = "gemini"        # deepseek | gemini | openai | openrouter | groq | mistral | openai_compatible
LLM_API_KEY  = "..."
# LLM_MODEL      = "..."       # hovedmodel til svar (valgfri, preset-default bruges ellers)
# LLM_FAST_MODEL = "..."       # hurtig model til omskrivning/rerank/HyDE (valgfri)
# LLM_BASE_URL   = "..."       # kun til openai_compatible (fx Ollama/vLLM)
```

Kald der i koden beder om Haiku, går til `LLM_FAST_MODEL`. Alle andre kald går
til `LLM_MODEL`. Embeddings og rerank bruger stadig Voyage, fordi den gemte
embedding-cache er bygget med `voyage-3-large`. Det koster næsten intet pr. søgning.
Du kan også blive på Claude og spare ved at sætte `LLM_MODEL = "claude-haiku-4-5-20251001"`.

### Brug dit eget Claude-abonnement (kun personligt, lokalt)

Kører du Ejnar på din egen computer til eget brug, kan svarene komme fra dit
Claude Pro/Max-abonnement via Claude Code i stedet for et betalt API:

```bash
npm install -g @anthropic-ai/claude-code && claude    # log ind én gang
LLM_PROVIDER=claude_cli EJNAR_API_KEYS=lokal uvicorn api:app --port 8000
```

Udbyderen kalder `claude -p` uden værktøjer og fjerner `ANTHROPIC_API_KEY` fra
miljøet, så abonnements-login'et bruges. Standardmodeller er `sonnet` (svar) og
`haiku` (hjælpekald). De kan ændres med `LLM_MODEL` og `LLM_FAST_MODEL`.
**Abonnementet er personligt.** Det må ikke bruges som backend for en tjeneste,
som kolleger eller kunder bruger. Til det skal du bruge en API-nøgle (se ovenfor).
Forbruget tæller med i abonnementets brugsgrænser.

## Workflow ved data-opdatering

1. **Scrape data fra AKF** (kør lokalt — sandbox må ikke ramme ankeforsikring.dk):
   ```bash
   cd ejnar
   python3 scrape_ejnar.py --limit 50 --debug   # lille test først
   python3 scrape_ejnar.py                      # fuld kørsel
   ```
   Output: `ejnar/ejnar_ejerskifteforsikring.csv`.

   **VIGTIGT:** Inden første kørsel skal følgende konstanter i toppen af
   `scrape_ejnar.py` verificeres mod ankeforsikring.dk's faktiske API/HTML
   (brug browserens DevTools → Network):
   - `SEARCH_URL` og payload-format
   - `EJERSKIFTE_FAGOMRADE`-strengen
   - HTML-selectors `.search-result, .afgoerelse-card, article a`
   - Detalje-selectors (`article .field--name-body` mv.)

2. **Byg embeddings** (kører Voyage AI's `voyage-3-large` på chunk-niveau):
   ```bash
   VOYAGE_API_KEY=... python3 build_embeddings.py
   ```
   Hver kendelse deles i overlappende ~1000-token-chunks (hver med titel-prefix),
   så lange juridiske tekster matches præcist afsnit for afsnit.
   Output: `ejnar/embeds/ejnar_ejerskifteforsikring__voyage__voyage-3-large__{N}d_{M}c.npz`
   (N dokumenter, M chunks).

3. **Commit og push**:
   ```bash
   git add ejnar/ejnar_ejerskifteforsikring.csv ejnar/embeds/*.npz
   git commit -m "Ejnar: opdater data og embeddings"
   git push
   ```

   Streamlit Cloud genstarter automatisk.

## Filtre

UI'en viser samme filter-paradigme som Harald-pkn:

- **Søgeord** (ordret/intelligent)
- **Mangeltype** — Skimmel/fugt, Tag/tagdækning, Kloak/dræn, Installationer,
  Fundament, Vinduer/døre, Murværk/facade, Råd/svamp/insekt,
  Konstruktion/bærende, Badeværelse/vådrum, Gulv, Andet
- **Forsikringsselskab**
- **Årsinterval**
- **Udfald** (Medhold / Delvis medhold / Ikke medhold / Afvist / Ukendt)

Mangeltype og udfald udledes automatisk fra teksten hvis CSV-felterne er tomme,
så data fra scraperen virker out-of-the-box.

## Forskelle fra Harald

| Aspekt | Harald | Ejnar |
|---|---|---|
| Domæne | Plan- + Miljøklagenævn | Forsikringsankenævnet, ejerskifteforsikring |
| Kategorier | Lokalplan, kommuneplan, landzone … | Mangeltype |
| Aktør | Kommune | Forsikringsselskab |
| Udfald | Medhold/Ikke medhold/Ophævet/Afvist | Medhold/Delvis medhold/Ikke medhold/Afvist |
| RAG-pipeline | Voyage embeddings + TF-IDF + RRF + Voyage rerank + Claude | **Identisk** |
| Adgangskode | `_autentificeret_v2` | `_autentificeret_ejnar` (uafhængige sessioner) |
| Embedding-cache | `embeds/` | `ejnar/embeds/` |

Brugen af `shared.py` er en direkte kopi af Harald's, så hvis du forbedrer
RAG-pipelinen ét sted, kan du genbruge ændringen i den anden app via en simpel
file diff.

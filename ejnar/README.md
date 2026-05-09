# Ejnar — Praksisdatabase for ejerskifteforsikring

Selvstændig Streamlit-app der spejler Harald's RAG-løsning og UI, men er
udelukkende fokuseret på Ankenævnet for Forsikrings (AKF) praksis om
**ejerskifteforsikring** efter lov om forbrugerbeskyttelse ved erhvervelse af
fast ejendom mv.

Ejnar deler git-repo med Harald (`pkn-vidensbase`) men er en helt separat app:
egen `app.py`, egen `shared.py`, egne data-filer og embedding-cache. De to
apps kan deployes uafhængigt.

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

2. **Byg embeddings** (kører Voyage AI's `voyage-multilingual-2`):
   ```bash
   VOYAGE_API_KEY=... python3 build_embeddings.py
   ```
   Output: `ejnar/embeds/ejnar_ejerskifteforsikring__voyage__voyage-multilingual-2__N.npz`.

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

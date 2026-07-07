# Ejnar Web — Next.js + FastAPI

En rigtig, selvstændig frontend til Ejnar (Ankenævnet for Forsikrings praksis om
ejerskifteforsikring), bygget ved siden af den eksisterende Streamlit-app —
Streamlit-versionen (`../ejnar/`) fortsætter uændret og uafhængigt.

Dette er svaret på "gør Ejnar mere professionel": ægte streaming-chat, øjeblikkelige
filtre, en split-view læser med indholdsfortegnelse, delbare URL'er og en UI der ikke
er begrænset af Streamlits fulde side-genløb.

## Arkitektur

```
ejnar-web/
├── backend/            FastAPI — genbruger RAG-logikken fra ejnar/shared.py
│   └── app/
│       ├── core/       Porteret, framework-frit: data, search, rag, text, claude, detect
│       ├── main.py      Endpoints
│       ├── auth.py      Delt-adgangskode-session (samme model som Streamlit i dag)
│       └── config.py    Miljøvariabler
└── frontend/            Next.js 16 (App Router) + TypeScript + Tailwind v4
    └── src/
        ├── app/          Sider (login, kendelser, kendelser/[id], assistent, statistik, sagsmapper)
        ├── components/   Genanvendelige UI-dele
        └── lib/          API-klient, typer, filter-state, sagsmapper (localStorage)
```

`backend/app/core/` er **porteret** fra `ejnar/shared.py` og `ejnar/pages/ejnar.py` —
samme forretningslogik (tekstbehandling, TF-IDF-søgning, query-forståelse, rerank,
citatvalidering), men uden Streamlit-afhængigheder, så det kan køre som en rigtig
service. Hold de to i sync ved ændringer i RAG-logikken.

## Bevidst scope i v1: keyword-only søgning

Retrieval er **TF-IDF (keyword-baseret)** — ingen Voyage-embeddings, ingen Voyage
Rerank. Det er en eksplicit beslutning for at undgå ekstra API-omkostninger ved
lanceringen, ikke en begrænsning i arkitekturen. Claude-kald (selve AI-svarene) sker
stadig som hidtil — det er uundgåeligt for at have en AI-assistent og er samme
forbrug som Streamlit-appen allerede har i dag.

Når I er klar til semantisk søgning: se `hybrid_retrieval()` i `ejnar/shared.py` for
mønsteret (RRF-fusion af TF-IDF- og embedding-rangeringer), og læg embeddings-kaldet
ind i `backend/app/core/rag.py::smart_retrieval`.

## Kør lokalt

**Backend:**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # udfyld APP_PASSWORD, ANTHROPIC_API_KEY, SESSION_SECRET
uvicorn app.main:app --reload --port 8000
```

TF-IDF-indekset over alle kendelser (~90 sekunder på 5.600+) bygges i en
baggrundstråd ved opstart (`EJNAR_WARMUP=1`, standard), så første bruger ikke
venter på koldstarten. Det caches i processens levetid derefter (samme
engangsomkostning som Streamlit-appens `@st.cache_resource`).

**Frontend** (i et andet terminalvindue):
```bash
cd frontend
npm install
BACKEND_URL=http://127.0.0.1:8000 npm run dev
```

Åbn `http://localhost:3000`. `next.config.ts` proxyer `/api/*` til backend'en, så
browseren kun ser ét oprindelsessted — auth-cookien fungerer uden cross-origin-
fiskeri, og opsætningen er identisk i dev og produktion.

## Tests

Backend'en har en pytest-suite (`backend/tests/`, kører på ~1 sekund): den
bygger et lille syntetisk datalager (ægte TF-IDF-indeks over 10 kunstige
kendelser) i stedet for det ~90 sek tunge rigtige, og patcher alle LLM-kald
væk — suiten tester dermed præcis den adfærd systemet skal have når
Haiku-boosts fejler, og rører aldrig netværket.

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -q
```

CI (`.github/workflows/ejnar-web-ci.yml`) kører suiten + frontend'ens
`tsc`/`eslint`/`next build` på hver PR der rører `ejnar-web/`. CI installerer
de pinnede versioner fra `requirements.txt` (fx pandas 2.3.x) — med vilje, så
versionsafhængige fejl fanges før deploy.

## Deploy

- **Backend**: kør som en always-on service (Railway, Fly.io, Render, eller en
  simpel VM). **Skal være always-on** — en serverless/cold-start-model ville
  genindlæse det ~90 sek TF-IDF-indeks ved hvert kolde kald, hvilket er præcis det
  "app is sleeping"-problem der plagede Streamlit Cloud.
- **Frontend**: Vercel (eller enhver Next.js-host). Sæt `BACKEND_URL` til
  backend'ens URL.
- **Produktions-env**: sæt `SESSION_SECRET` (backend'en **nægter at starte**
  med adgangskode men uden rigtig secret — forfalskelige sessions-tokens ville
  ellers omgå login) og `COOKIE_SECURE=1` når backend'en kører bag HTTPS.
  Login er rate-limited (10 forsøg/15 min pr. IP).
- Data: backend'en læser `ejnar_*.csv(.zip)` fra `EJNAR_DATA_DIR` — som udgangspunkt
  den eksisterende `ejnar/`-mappe. Ved data-opdateringer: samme workflow som i
  `ejnar/README.md` (scrape → evt. `build_embeddings.py` senere → commit).

## Hvad der IKKE er lavet endnu

- **Voyage/semantisk søgning** — bevidst udskudt, se ovenfor.
- **Sagsmapper er browser-lokal** (localStorage) — deles ikke på tværs af enheder
  eller brugere. Kræver en lille database hvis det skal ændres.
- **Frontend-komponenttests** — backend'en er dækket af pytest-suiten (se
  Tests ovenfor), og frontend'en af `tsc`/`eslint`/`next build` i CI, men der
  er ingen React-komponenttests endnu.
- **Fuld feature-paritet** med Streamlit-versionen kan mangle enkelte detaljer —
  begge apps deler samme underliggende data, så de kan køre side om side imens.

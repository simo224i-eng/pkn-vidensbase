# Deploy-guide — Ejnar Web

To veje til produktion. **Vej A** (anbefalet): managed hosting, mindst drift.
**Vej B**: Docker/compose på egen server.

Uanset vej gælder:

| Variabel | Krav | Note |
|---|---|---|
| `APP_PASSWORD` | ja | Delt adgangskode for alle brugere |
| `SESSION_SECRET` | **ja** | Lang tilfældig streng (`openssl rand -hex 32`). Backend **nægter at starte** med adgangskode men uden secret |
| `ANTHROPIC_API_KEY` | ja* | *Uden nøgle virker søgning/filtre/statistik — kun AI-assistenten fejler |
| `COOKIE_SECURE` | `1` bag HTTPS | Ellers `0` (lokal http) |
| `EJNAR_WARMUP` | `1` (standard) | Bygger indekset ved opstart i stedet for ved første kald |
| `BACKEND_URL` | frontend, **ved byggetid** | Backend'ens URL — rewrites bages ind i buildet |

**Vigtige driftsregler:**

- **Always-on, aldrig serverless.** Indekset tager ~90 sek at bygge — cold
  starts giver præcis det "app is sleeping"-problem der plagede Streamlit Cloud.
- **Præcis én worker-proces.** Datalageret og login-rate-limiteren er
  in-process. Flere workers = N× indeksbygning + opdelt rate-limit. Skalér
  lodret (mere RAM/CPU). Dockerfilen og kommandoerne nedenfor gør det rigtigt.
- **Healthcheck på `/api/ready`** (ikke `/api/health`): giver 503 til indekset
  er varmt, så platformen først sender trafik til en klar proces. Sæt
  healthcheck-timeout/grace til mindst 3 minutter.
- **RAM**: indeks + dataframe bruger ~1–2 GB — vælg en instans med min. 2 GB.

## Vej A: Railway/Render (backend) + Vercel (frontend)

**Backend (Railway som eksempel):**
1. Nyt projekt → Deploy from GitHub → vælg repoet.
2. Settings → Build: **Dockerfile path** = `ejnar-web/backend/Dockerfile`
   (build-konteksten er repo-roden — datafilen kopieres ind i imagen).
3. Variables: sæt tabellen ovenfor (minus `BACKEND_URL`).
4. Settings → Health check path: `/api/ready`, timeout ≥ 300 sek.
5. Notér den offentlige URL (fx `https://ejnar-api.up.railway.app`).

Render: "New Web Service" → Docker → samme Dockerfile-sti og healthcheck.

**Frontend (Vercel):**
1. Import af repoet → **Root Directory** = `ejnar-web/frontend`.
2. Environment Variables: `BACKEND_URL` = backend-URL'en fra ovenfor
   (skal være sat før build — Vercel gør det automatisk rigtigt).
3. Deploy. Færdig — `/api/*` proxyes server-side, så auth-cookien er
   same-origin og backend'en kan holdes helt væk fra offentligheden på nær
   via frontenden (valgfrit: lås backend'en til kun at modtage trafik fra
   Vercel med en delt header/allowlist senere).

## Vej B: Docker Compose på egen server

```bash
cd ejnar-web
cp backend/.env.example backend/.env   # udfyld APP_PASSWORD, ANTHROPIC_API_KEY, SESSION_SECRET
docker compose up --build -d
```

Frontend på `http://localhost:3000`; backend'en er kun tilgængelig på det
interne compose-netværk. Læg en reverse proxy med TLS foran (Caddy/nginx) og
sæt `COOKIE_SECURE=1` i `backend/.env`.

Enkelt-images uden compose:

```bash
# Backend (fra REPO-RODEN — dataconteksten kræver det)
docker build -f ejnar-web/backend/Dockerfile -t ejnar-api .
docker run -d -p 8000:8000 --env-file ejnar-web/backend/.env ejnar-api

# Frontend (fra ejnar-web/frontend)
docker build --build-arg BACKEND_URL=https://api.dit-domæne.dk -t ejnar-web ejnar-web/frontend
docker run -d -p 3000:3000 ejnar-web
```

## Data-opdatering

Ny scraping → commit ny `ejnar/ejnar_ejerskifteforsikring.csv.zip` → redeploy
backend (imagen kopierer zip'en ind ved build). Vej A redeployer automatisk
ved push til main.

## Verificering efter deploy

1. `curl https://<backend>/api/health` → `{"ok":true}` med det samme.
2. `curl https://<backend>/api/ready` → 503 første ~90 sek, derefter `{"ready":true}`.
3. Log ind i frontenden, kør en søgning, stil ét AI-spørgsmål, klik en
   citat-chip og tjek at den RIGTIGE kendelse åbner med fremhævet citat.

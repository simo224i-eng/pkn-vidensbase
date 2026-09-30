# syntax=docker/dockerfile:1
# Ejnar-webappen som Hugging Face Space (Docker). Kopiér denne fil og README.md
# til roden af en ny Docker-Space. Imaget henter koden fra GitHub ved build.
#
# Space-secrets (Settings → Variables and secrets):
#   EJNAR_API_KEYS     adgangskoden, man skriver i webappen (flere: kommasepareret)
#   ANTHROPIC_API_KEY  API-nøgle fra console.anthropic.com
#   LLM_MODEL          fx claude-sonnet-5-5 (valgfri)
#   GITHUB_TOKEN       kun hvis GitHub-repoet er privat (read-only fine-grained token)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EJNAR_CACHE_DIR=/app/cache

ARG REPO=simo224i-eng/pkn-vidensbase
ARG REF=main
# Kun ejnar/-mappen pakkes ud; resten af repoet er andre apps og store datafiler.
ENV REPO=$REPO REF=$REF
RUN --mount=type=secret,id=GITHUB_TOKEN,mode=0444,required=false python - <<'PY'
import io, os, tarfile, urllib.request
repo, ref = os.environ["REPO"], os.environ["REF"]
req = urllib.request.Request(f"https://api.github.com/repos/{repo}/tarball/{ref}")
if os.path.exists("/run/secrets/GITHUB_TOKEN"):
    req.add_header("Authorization", "Bearer " + open("/run/secrets/GITHUB_TOKEN").read().strip())
with urllib.request.urlopen(req) as r, tarfile.open(fileobj=io.BytesIO(r.read()), mode="r:gz") as tf:
    for m in tf.getmembers():
        parts = m.name.split("/", 1)
        if len(parts) == 2 and (parts[1] == "ejnar" or parts[1].startswith("ejnar/")):
            m.name = parts[1]
            tf.extract(m, "/app", filter="data")
PY

WORKDIR /app/ejnar
RUN pip install -r requirements.txt -r requirements-api.txt
# Byg korpus + TF-IDF-indeks ind i imaget, så Space'et starter på sekunder.
RUN python -c "import engine; engine.load_corpus_cached()" \
 && useradd --create-home --uid 1000 ejnar && chown -R ejnar /app
USER ejnar

EXPOSE 7860
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "7860", "--workers", "1"]

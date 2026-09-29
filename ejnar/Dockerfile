# Ejnar REST-API. Byg fra repo-roden:
#   docker build -f ejnar/Dockerfile -t ejnar-api .
#   docker run -p 8000:8000 -e EJNAR_API_KEYS=... -e LLM_PROVIDER=gemini -e LLM_API_KEY=... \
#              -e VOYAGE_API_KEY=... ejnar-api
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/ejnar
COPY ejnar/requirements.txt ejnar/requirements-api.txt ./
RUN pip install -r requirements.txt -r requirements-api.txt

COPY ejnar/ ./
RUN useradd --create-home ejnar && chown -R ejnar /app
USER ejnar

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if b'\"ok\"' in urllib.request.urlopen('http://127.0.0.1:8000/health').read() else 1)"
# Én worker: korpus + indeks holdes i RAM (~1 GB); skalér med flere containere.
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

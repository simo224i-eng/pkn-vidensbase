# Ejnar API — byg fra REPO-RODEN (datafilen ligger udenfor backend-mappen):
#
#   docker build -f ejnar-web/backend/Dockerfile -t ejnar-api .
#   docker run -p 8000:8000 --env-file ejnar-web/backend/.env ejnar-api
#
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY ejnar-web/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ejnar-web/backend/app ./app
# Kun zip'en — CSV'en pakkes ud til /tmp ved første opstart (app/core/data.py).
COPY ejnar/ejnar_ejerskifteforsikring.csv.zip /data/
ENV EJNAR_DATA_DIR=/data

EXPOSE 8000

# Præcis ÉN worker, med vilje: datalageret (~90 sek TF-IDF-indeks) og login-
# rate-limiteren er in-process — flere workers ville bygge indekset N gange
# og opdele rate-limit-tilstanden. Skalér lodret (mere RAM/CPU), ikke i bredden.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

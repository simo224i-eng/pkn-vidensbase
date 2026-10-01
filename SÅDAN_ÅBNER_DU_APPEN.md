# Sådan åbner du appen (Harald – Juridisk Vidensbase)

Appen er en **Streamlit-app**. Den har en **adgangskode-låge**: du kan først
komme ind når der er sat en kode (`APP_PASSWORD`). Koden gemmes i Streamlits
"secrets" og ligger med vilje **ikke** i GitHub.

Vælg én af metoderne nedenfor. Metode A anbefales.

---

## A) Streamlit Community Cloud (anbefales – gratis fast web-link)

1. Gå til <https://share.streamlit.io> og log ind med din **GitHub-konto**.
2. Klik **Create app** → **Deploy a public app from GitHub**.
3. Udfyld:
   - **Repository:** `simo224i-eng/pkn-vidensbase`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Klik **Advanced settings…** → feltet **Secrets**, og indsæt (vælg din egen kode):

   ```toml
   APP_PASSWORD = "din-hemmelige-kode"
   ```

5. Klik **Deploy**. Efter 1–3 minutter får du et link, fx
   `https://pkn-vidensbase.streamlit.app`.
6. Åbn linket, skriv den kode du valgte i trin 4 → du er inde. ✅

> Glemt at sætte koden? Åbn appen i Streamlit Cloud → **Manage app** →
> **Settings → Secrets**, indsæt linjen ovenfor, og gem.

---

## B) Kør på din egen computer

Kræver Python 3.11+.

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Åbn .streamlit/secrets.toml og skift APP_PASSWORD til din egen kode
streamlit run app.py
```

Browseren åbner automatisk på <http://localhost:8501>. Skriv din kode → inde. ✅

---

## C) GitHub Codespaces (hurtig test i browseren)

1. På GitHub: knappen **Code** → fanen **Codespaces** → **Create codespace on main**.
2. Devcontaineren starter automatisk appen (`streamlit run app.py`) på port **8501**.
3. Før du kan logge ind skal koden sættes – kør i terminalen:

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```
   Ret derefter `APP_PASSWORD` i filen, og genstart appen.

> Bemærk: Et codespace er midlertidigt og lukker ned efter inaktivitet.
> Til daglig brug er **metode A** bedre.

---

## Hvis appen er langsom eller crasher ved opstart

Repoet indeholder store datafiler (bl.a. i `ejnar/`). På Streamlit Cloud's
gratis-plan er der begrænset hukommelse. Hvis deploymentet løber tør for
hukommelse, kan datamængden trimmes – spørg endelig om hjælp til det.

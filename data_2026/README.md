# Nævnsafgørelser hentet 8. oktober 2026

Hentet med `scrape_pkn.py --relevante` og `scrape_mfkn.py --relevante` (se `naevn_api.py`) samt
`fetch_pdf_afgoerelser.py` for afgørelser, der kun findes som PDF.

| Fil | Indhold |
|---|---|
| `pkn_*.csv.zip` | Planklagenævnet, én fil pr. kategori |
| `mfkn_*.csv.zip` | Miljø- og Fødevareklagenævnet, én fil pr. kategori |
| `pdf_afgoerelser.csv.zip` | Tekst udtrukket fra PDF for afgørelser med tom brødtekst (2017+) |

Kolonner: `id` (nævnets uuid), `Naevn`, `Jnr`, `Dato`, `Titel`, `Link`, `Retsomraade`, `Tekst`.
Overskrifter i teksten står på egen linje med `## ` foran.

**Rensning** sker i `ejnar/miljoejurist/corpus.py` (`python -m miljoejurist.corpus` fra `ejnar/`):
dubletter på id slås sammen (kategorierne samles, længste tekst bevares), dubletter på
normaliseret tekst fjernes, tekster under 1.500 tegn udelades, og udfald bestemmes ud fra titel,
indledning og slutning. Resultatet gemmes i `korpus_renset.jsonl` (gitignoreret, genskabes).
Tal fra kørslen står i `analyser/BESLUTNINGER.md`.

Afgørelserne er anonymiseret af nævnene. Repoet tilføjer ingen personoplysninger.

"""Modellag til screeningstjekket.

En sprogmodel gennemgår dokumentet mod tjeklisten og nævnspraksis. Prompten beder om
JSON med ordrette citater. Hvert citat kontrolleres automatisk mod dokumentet; svagheder
med citater, der ikke står ordret, fjernes (de tælles i rapporten).

`llm` er en funktion prompt -> svartekst. I webappen er det Ejnars udskiftelige
LLM-udbyder (llm_provider.py). I test spiller en agent modellen og får præcis den
prompt, som `byg_prompt` laver.
"""
from __future__ import annotations

import json
import re

from . import citatkontrol, praksis
from .dokument import Dokument
from .tjek import FORBUDT, Kilde, Rapport, Svaghed, tjekliste

MAKS_DOK = 70000


def byg_prompt(dok: Dokument, rapport: Rapport, udeluk: set[str] | None = None) -> str:
    dtype = rapport.dokumenttype
    punkter = [p for p in tjekliste() if dtype in p["gælder"]]
    linjer = []
    for p in punkter:
        eks = praksis.lignende(p.get("søg", p["titel"]), kategorier=p.get("fejlkategorier"),
                               dokumenttype=dtype, k=1, udeluk=udeluk, kontekst=dok.tekst[:2500])
        eks_txt = " | ".join(f"(en anden sag: {e['titel'][:90]}) {e['fejl']}" for e in eks)
        lov = "; ".join(f"{kode} {nr}" for kode, nr, _ in p.get("lov", []))
        linjer.append(f"- {p['id']} {p['titel']}: {p['spørgsmål']} (Lov: {lov}) Eksempler fra praksis: {eks_txt}")
    regelfund = "\n".join(f"- {s.punkt}: {s.svaghed}" + (f" «{s.citat_dokument[:200]}»" if s.citat_dokument else "")
                          for s in rapport.svagheder) or "(ingen)"
    tekst = dok.tekst[:MAKS_DOK]
    afkortet = "" if len(dok.tekst) <= MAKS_DOK else f"\n[Dokumentet er afkortet til de første {MAKS_DOK} tegn.]"
    return f"""Du er en erfaren miljøjurist, der gennemgår en {dtype.replace('_', ' ')} for svagheder,
som Planklagenævnet eller Miljø- og Fødevareklagenævnet tidligere har underkendt.

OPGAVE
Find de konkrete svagheder i dokumentet nedenfor målt mod tjeklisten. For hver svaghed skal du
citere den sætning i dokumentet, svagheden handler om, ORDRET (kopiér tegn for tegn; du må forkorte
med "[…]"). Handler svagheden om noget, der mangler helt, så sæt citat til null og skriv, hvad der mangler.

REGLER
- Skriv aldrig, at afgørelsen er i orden, lovlig eller uden fejl. Du vurderer kun mulige svagheder.
- Medtag kun svagheder, du kan pege på i teksten. Ingen generelle råd.
- Prioritér: højst 8 svagheder, sorteret efter risikoen for, at et klagenævn underkender afgørelsen.
  Spring emner over, der er uden betydning for netop dette projekt/denne plan og dette område.
- "alvor": "høj" kun når dokumentet selv giver et konkret holdepunkt for en væsentlig påvirkning (fx
  projektet ligger i eller tæt på Natura 2000, § 3-natur eller kendte levesteder; afgørelsen hviler på en
  usikret foranstaltning; en del af projektet er holdt udenfor) OG vurderingen af netop det er mangelfuld.
  "middel" når vurderingen er tynd, men uden et sådant holdepunkt. "lav" for formelle eller mindre forhold.
- Kriterier, der ikke er nævnt, men som åbenlyst er uden betydning for projektet, er ikke en svaghed.
- Se især efter disse mønstre, som nævnene ofte underkender:
  * afværgeforanstaltninger eller vilkår, som screeningen selv fastsætter eller forudsætter (en screening kan
    ikke bygge på afværge, der kræver vilkår; Natura 2000-væsentlighed må ikke vurderes med afværge),
  * vurdering ud fra et forkert udgangspunkt (fx forholdene efter en gennemført rydning/ændring eller en
    tidligere tilladt, men ikke udnyttet mængde),
  * screening af et projekt, der allerede er påbegyndt/gennemført (lovliggørelse),
  * planer, der behandles som "mindre områder på lokalt plan"/"mindre ændringer", selv om de dækker et stort
    område eller rammesætter projekter i bilag 1/2 (fx kommuneplaner),
  * at myndigheden selv har udfyldt screeningen uden skriftlig ansøgning med bilag 5-oplysninger,
  * at myndigheden overlader vurderingen (fx af bilag IV-arter) til senere eller til bygherren.
- Henvis kun til de bestemmelser, der står i tjeklisten.
- Ingen personnavne i svaret.

TJEKLISTE (eksemplerne er fra ANDRE sager og viser kun, hvad nævnene har underkendt; bland dem ikke
sammen med dokumentet)
{chr(10).join(linjer)}

REGELLAGETS FUND (kan være fejl eller mangle noget; brug dem som udgangspunkt)
{regelfund}

SVARFORMAT (kun JSON, ingen anden tekst)
{{"svagheder": [{{"punkt": "C3", "svaghed": "kort beskrivelse", "citat": "ordret citat eller null",
  "hvorfor": "1-2 sætninger om hvorfor det er en svaghed efter loven/praksis", "alvor": "høj|middel|lav"}}],
 "ikke_vurderet": ["forhold i dokumentet, du ikke kunne vurdere ud fra teksten"]}}

DOKUMENT
<<<
{tekst}{afkortet}
>>>"""


def fortolk(svar: str) -> dict:
    """Find JSON-objektet i modellens svar."""
    m = re.search(r"\{.*\}", svar or "", re.S)
    if not m:
        return {"svagheder": [], "ikke_vurderet": [], "fejl": "intet JSON i svaret"}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        # Ofte et afsluttende komma eller citationstegn; prøv at rydde op
        t = re.sub(r",\s*([}\]])", r"\1", m.group(0))
        try:
            return json.loads(t)
        except json.JSONDecodeError as e:
            return {"svagheder": [], "ikke_vurderet": [], "fejl": f"ugyldig JSON: {e}"}


_ALVOR = {"høj": 3.0, "middel": 2.0, "lav": 1.0}


def supplér(rapport: Rapport, dok: Dokument, llm, udeluk: set[str] | None = None,
            svar: str | None = None) -> Rapport:
    """Kør modellen (eller brug et færdigt svar) og flet dens fund ind i rapporten."""
    prompt = byg_prompt(dok, rapport, udeluk)
    if svar is None:
        svar = llm(prompt)
    data = fortolk(svar)
    punkter = {p["id"]: p for p in tjekliste()}
    afvist = 0
    nye = []
    for s in data.get("svagheder") or []:
        citat = (s.get("citat") or "").strip() or None
        ok = citatkontrol.find(citat, dok.tekst) if citat else None
        if citat and not ok:
            afvist += 1
            continue
        p = punkter.get(s.get("punkt"), {"id": s.get("punkt") or "?", "titel": "Andet", "spørgsmål": "",
                                         "lov": [], "fejlkategorier": None, "søg": s.get("svaghed", ""),
                                         "gælder": []})
        hvorfor = FORBUDT.sub("[udeladt formulering]", s.get("hvorfor") or "")
        from .tjek import _eu_kilder, _lov_kilder, _vejl_kilder, praksis_kilder
        kilder = []
        if p.get("lov"):
            kilder += _lov_kilder(p, rapport.dokumenttype) + _vejl_kilder(p, rapport.dokumenttype) + _eu_kilder(p)
        kilder += praksis_kilder(f"{s.get('svaghed', '')} {s.get('hvorfor', '')} {citat or ''}",
                                 p.get("fejlkategorier"), rapport.dokumenttype, dok.tekst, udeluk or set())
        nye.append(Svaghed(punkt=p["id"], titel=p["titel"], art="model",
                           svaghed=FORBUDT.sub("[udeladt formulering]", s.get("svaghed") or ""),
                           citat_dokument=citat, citat_ok=ok, hvorfor=hvorfor,
                           spørgsmål=p.get("spørgsmål", ""), kilder=kilder,
                           vægt=_ALVOR.get(s.get("alvor"), 1.5), kilde_lag="model"))
    # Modellens fund først (de er konkrete), derefter regelfund for punkter, modellen ikke dækkede
    dækket = {s.punkt for s in nye}
    rest = [s for s in rapport.svagheder if s.punkt not in dækket]
    nye = sorted(nye, key=lambda s: -s.vægt)
    # Revisionen (runde 2) viste, at regellagets "ikke behandlet"/"uden grundlag" næsten altid er støj,
    # når modellen har gennemgået dokumentet, og at modellens "lav" sjældent er relevant. De flyttes til en
    # kort liste uden kilder. Regellagets konkrete svage formuleringer beholdes.
    beholdes = [s for s in rest if s.art in ("svag_formulering", "kriterier_mangler")]
    for s in beholdes:
        s.vægt = round(s.vægt * 0.5, 2)
    korte = [s for s in rest if s not in beholdes] + [s for s in nye if s.vægt <= 1.0]
    nye = [s for s in nye if s.vægt > 1.0]
    rapport.mindre = [f"{s.punkt} {s.titel}: {s.svaghed}" for s in korte]
    rapport.svagheder = nye + beholdes
    from .tjek import _niveauer
    _niveauer(rapport.svagheder)

    rapport.ikke_vurderet = list(rapport.ikke_vurderet) + [
        FORBUDT.sub("[udeladt formulering]", x) for x in (data.get("ikke_vurderet") or [])][:12]
    rapport.lag = rapport.lag + ["model"]
    if afvist:
        rapport.note += f" {afvist} af modellens fund blev fjernet, fordi citatet ikke stod ordret i dokumentet."
    return rapport

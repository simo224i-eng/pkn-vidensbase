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

# Andel af sager behandlet på indholdet, hvor klager fik helt eller delvist medhold (2020-2026, trin 1-analysen)
BASISRATE = {"screening_projekt": 37, "screening_plan": 18, "miljoerapport_plan": 27, "projekttilladelse": 44}


def byg_prompt(dok: Dokument, rapport: Rapport, udeluk: set[str] | None = None) -> str:
    dtype = rapport.dokumenttype
    punkter = [p for p in tjekliste() if dtype in p["gælder"]]
    linjer = []
    for p in punkter:
        eks = praksis.lignende(p.get("søg", p["titel"]), kategorier=p.get("fejlkategorier"),
                               dokumenttype=dtype, k=1, udeluk=udeluk, kontekst=dok.tekst[:2500])
        eks_txt = " | ".join(f"(en anden sag: {e['titel'][:90]}) {e['fejl']}" for e in eks)
        holdt = praksis.holdt_lignende(p.get("søg", p["titel"]), tjekpunkt=p["id"], dokumenttype=dtype, k=1,
                                       udeluk=udeluk, kontekst=dok.tekst[:2500])
        holdt_txt = " | ".join(f"(en anden sag) myndigheden: {h['myndigheden_gjorde']} Nævnet: {h['hvorfor_tilstraekkeligt']}"
                               for h in holdt)
        lov = "; ".join(f"{kode} {nr}" for kode, nr, _ in p.get("lov", []))
        linjer.append(f"- {p['id']} {p['titel']}: {p['spørgsmål']} (Lov: {lov})\n    UNDERKENDT: {eks_txt or '-'}"
                      + (f"\n    HOLDT: {holdt_txt}" if holdt_txt else ""))
    regelfund = "\n".join(f"- {s.punkt}: {s.svaghed}" + (f" «{s.citat_dokument[:200]}»" if s.citat_dokument else "")
                          for s in rapport.svagheder) or "(ingen)"
    tekst = dok.tekst[:MAKS_DOK]
    afkortet = "" if len(dok.tekst) <= MAKS_DOK else f"\n[Dokumentet er afkortet til de første {MAKS_DOK} tegn.]"
    basis = BASISRATE.get(dtype, 31)
    dtype_navn = {"screening_projekt": "projektscreeninger", "screening_plan": "planscreeninger", "miljoerapport_plan": "miljørapporter for planer", "projekttilladelse": "§ 25-tilladelser"}.get(dtype, "sager")
    return f"""Du er en erfaren miljøjurist, der gennemgår en {dtype.replace('_', ' ')} for svagheder,
som Planklagenævnet eller Miljø- og Fødevareklagenævnet tidligere har underkendt.

OPGAVE
Find de konkrete svagheder i dokumentet nedenfor målt mod tjeklisten. For hver svaghed skal du
citere den sætning i dokumentet, svagheden handler om, ORDRET (kopiér tegn for tegn; du må forkorte
med "[…]"). Handler svagheden om noget, der mangler helt, så sæt citat til null og skriv, hvad der mangler.

REGLER
- Skriv aldrig, at afgørelsen er i orden, lovlig eller uden fejl. Du vurderer kun mulige svagheder.
- Medtag kun svagheder, du kan pege på i teksten. Ingen generelle råd.
- Højst 8 punkter. Giv hvert punkt en "ophaevelsesrisiko" = risikoen for, at et klagenævn ophæver afgørelsen
  på netop dette punkt, hvis den påklages:
  "høj": en fejl af den slags, nævnene ophæver på (se UNDERKENDT-eksemplerne og mønstrene nedenfor), OG
  dokumentet selv giver et konkret holdepunkt for den (fx et kendt levested, en afstand på få hundrede meter, en
  foranstaltning screeningen hviler på, en del af projektet der er holdt udenfor).
  "middel": vurderingen er mangelfuld på et punkt, der har betydning for netop dette projekt/denne plan, men uden
  et sådant holdepunkt.
  "lav": vurderingen er kort eller kunne være grundigere, men svarer til det, nævnene typisk accepterer (se
  HOLDT-eksemplerne). Det er et opmærksomhedspunkt, hvor myndigheden kan helgardere sig, ikke en ophævelsesgrund.
- En kort vurdering er IKKE i sig selv en fejl. Nævnene stadfæster ofte korte screeninger, når der ikke er
  konkrete holdepunkter for væsentlig påvirkning. Brug HOLDT-eksemplerne til at skelne.
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

TJEKLISTE (eksemplerne er fra ANDRE sager: UNDERKENDT = hvad nævnene ophævede på, HOLDT = hvad nævnene fandt
tilstrækkeligt; bland dem ikke sammen med dokumentet)
{chr(10).join(linjer)}

REGELLAGETS FUND (kan være fejl eller mangle noget; brug dem som udgangspunkt)
{regelfund}

SAMLET RISIKO
Vurdér til sidst sandsynligheden for, at klagenævnet ville ophæve afgørelsen helt eller delvist, hvis den blev
påklaget. Udgangspunktet er {basis} % (andelen af {dtype_navn} med medhold ved nævnene 2020-2026). Gå kun klart
over det, hvis der er mindst ét punkt med "høj" ophævelsesrisiko, og under det, hvis vurderingen svarer til
HOLDT-eksemplerne. Nævnet består af mennesker og er ikke altid konsistent; giv derfor sjældent under 5 eller over 90.

SVARFORMAT (kun JSON, ingen anden tekst)
{{"svagheder": [{{"punkt": "C3", "svaghed": "kort beskrivelse", "citat": "ordret citat eller null",
  "hvorfor": "1-2 sætninger om hvorfor det er en svaghed efter loven/praksis", "ophaevelsesrisiko": "høj|middel|lav"}}],
 "samlet": {{"sandsynlighed_ophaevelse": 0-100, "afgoerende_punkt": "punkt-id eller null",
  "begrundelse": "1-2 sætninger"}},
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


_ALVOR = {"høj": 3.0, "middel": 2.0, "lav": 1.2}


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
                           vægt=_ALVOR.get(s.get("ophaevelsesrisiko") or s.get("alvor"), 1.5), kilde_lag="model",
                           risiko=s.get("ophaevelsesrisiko") or s.get("alvor")))
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
    # Modellens "lav" er et opmærksomhedspunkt (helgardering) og beholdes med kilder; regellagets øvrige fund
    # bliver korte bemærkninger.
    korte = [s for s in rest if s not in beholdes]
    rapport.mindre = [f"{s.punkt} {s.titel}: {s.svaghed}" for s in korte]
    for s in beholdes:
        s.risiko = "lav"
    rapport.svagheder = nye + beholdes
    for s in rapport.svagheder:
        s.niveau = "svaghed" if s.risiko in ("høj", "middel") else "opmærksomhed"
    rapport.svagheder.sort(key=lambda s: (s.niveau != "svaghed", -s.vægt))
    sm = data.get("samlet") or {}
    try:
        pct = max(0, min(100, int(sm.get("sandsynlighed_ophaevelse"))))
    except (TypeError, ValueError):
        pct = None
    if pct is not None:
        rapport.udfald = {"sandsynlighed": pct, "niveau": "høj" if pct >= 60 else ("middel" if pct >= 30 else "lav"),
                          "afgoerende_punkt": sm.get("afgoerende_punkt"),
                          "begrundelse": FORBUDT.sub("[udeladt formulering]", sm.get("begrundelse") or ""),
                          "basisrate": BASISRATE.get(rapport.dokumenttype)}

    rapport.ikke_vurderet = list(rapport.ikke_vurderet) + [
        FORBUDT.sub("[udeladt formulering]", x) for x in (data.get("ikke_vurderet") or [])][:12]
    rapport.lag = rapport.lag + ["model"]
    if afvist:
        rapport.note += f" {afvist} af modellens fund blev fjernet, fordi citatet ikke stod ordret i dokumentet."
    return rapport


# ── Dommer-trin: ligner risikopunkterne det, nævnet ophævede på, eller det, nævnet godtog? ─────────────
# Audit v1 og dev-kørslen viste, at modellens frie sandsynlighed er dårligt kalibreret (stadfæstede sager fik
# ~60 %). Dommeren sammenligner i stedet hvert punkt med de nærmeste underkendte og stadfæstede sager på samme
# tjekpunkt, og risikoen beregnes i koden ud fra dens afgørelser (`beregn_risiko`).
MAKS_DOMMER_PUNKTER = 4


def byg_dommer_prompt(dok: Dokument, rapport: Rapport, udeluk: set[str] | None = None) -> str | None:
    punkter = {p["id"]: p for p in tjekliste()}
    kand = [s for s in rapport.svagheder if s.kilde_lag == "model" and s.risiko in ("høj", "middel")][:MAKS_DOMMER_PUNKTER]
    if not kand:
        return None
    blokke = []
    for i, s in enumerate(kand, 1):
        p = punkter.get(s.punkt, {})
        q = f"{s.svaghed} {s.hvorfor}"
        und = praksis.lignende(q, kategorier=p.get("fejlkategorier"), dokumenttype=rapport.dokumenttype, k=2,
                               udeluk=udeluk, kontekst=dok.tekst[:2500])
        hol = praksis.holdt_lignende(q, tjekpunkt=s.punkt, dokumenttype=rapport.dokumenttype, k=2,
                                     udeluk=udeluk, kontekst=dok.tekst[:2500])
        if len(hol) < 2:
            hol += [h for h in praksis.holdt_lignende(q, dokumenttype=rapport.dokumenttype, k=3, udeluk=udeluk,
                                                      kontekst=dok.tekst[:2500]) if h["id"] not in {x["id"] for x in hol}][:2 - len(hol)]
        linjer = [f"PUNKT {i} ({s.punkt} {s.titel}): {s.svaghed}",
                  f"  Dokumentet: «{(s.citat_dokument or '(emnet mangler)')[:300]}»"]
        linjer += [f"  UNDERKENDT {j}: Myndigheden: {e['fejl']} Nævnet: «{e['citat'][:300]}»" for j, e in enumerate(und, 1)]
        linjer += [f"  HOLDT {j}: Myndigheden: {h['myndigheden_gjorde']} Nævnet: «{(h.get('citat_naevn') or h['hvorfor_tilstraekkeligt'])[:300]}»"
                   for j, h in enumerate(hol, 1)]
        blokke.append("\n".join(linjer))
    tekst = dok.tekst[:40000]
    return f"""Du er dommer i et klagenævn for miljøvurderinger. En kollega har peget på mulige svagheder i en
{rapport.dokumenttype.replace('_', ' ')}. For hvert punkt får du to sager, hvor nævnet UNDERKENDTE en lignende
vurdering, og to, hvor nævnet HOLDT (godtog) en lignende vurdering. Afgør for hvert punkt, hvilken gruppe
dokumentets vurdering ligner mest.

Vær nøgtern: de fleste påklagede afgørelser holder. En vurdering ligner kun UNDERKENDT, hvis den har samme slags
konkrete fejl (fx bygger på afværge, forkert udgangspunkt, en del af projektet holdt udenfor, et konkret holdepunkt
for påvirkning, som ikke er undersøgt). At en vurdering er kort, er ikke nok, hvis HOLDT-sagerne var lige så korte.

{chr(10).join(blokke)}

SVARFORMAT (kun JSON):
{{"punkter": [{{"nr": 1, "ligner": "UNDERKENDT|HOLDT|UKLART", "sikker": true, "grund": "1 sætning"}}]}}

DOKUMENT
<<<
{tekst}
>>>"""


def beregn_risiko(dommer: dict, dtype: str) -> dict | None:
    """Samlet risiko ud fra dommerens afgørelser (kalibreret på dev-sættet, se evaluation/RESULTS.md)."""
    pk = (dommer or {}).get("punkter") or []
    if not isinstance(pk, list):
        return None
    sikre_u = sum(1 for p in pk if p.get("ligner") == "UNDERKENDT" and p.get("sikker"))
    usikre_u = sum(1 for p in pk if p.get("ligner") == "UNDERKENDT" and not p.get("sikker"))
    holdt = sum(1 for p in pk if p.get("ligner") == "HOLDT")
    basis = BASISRATE.get(dtype, 31)
    if sikre_u:
        pct, niv = min(85, 55 + 10 * (sikre_u - 1) + 5 * usikre_u), "høj"
    elif usikre_u:
        pct, niv = max(basis, 40), "middel"
    elif pk and holdt == len(pk):
        pct, niv = max(5, round(basis * 0.4)), "lav"
    else:
        pct, niv = basis, "middel" if basis >= 30 else "lav"
    return {"sandsynlighed": pct, "niveau": niv, "basisrate": basis,
            "underkendt_sikre": sikre_u, "underkendt_usikre": usikre_u, "holdt": holdt, "punkter": len(pk)}


def anvend_dommer(rapport: Rapport, svar: str) -> Rapport:
    data = fortolk(svar)
    risiko = beregn_risiko(data, rapport.dokumenttype)
    if risiko is None:
        return rapport
    kand = [s for s in rapport.svagheder if s.kilde_lag == "model" and s.risiko in ("høj", "middel")][:MAKS_DOMMER_PUNKTER]
    grunde = []
    for p in data.get("punkter") or []:
        try:
            s = kand[int(p.get("nr")) - 1]
        except (TypeError, ValueError, IndexError):
            continue
        if p.get("ligner") == "HOLDT":
            s.risiko, s.niveau = "lav", "opmærksomhed"
        elif p.get("ligner") == "UNDERKENDT" and p.get("sikker"):
            s.risiko = "høj"
            grunde.append(f"{s.titel}: {FORBUDT.sub('[udeladt formulering]', p.get('grund') or '')}")
    rapport.svagheder.sort(key=lambda s: (s.niveau != "svaghed", {"høj": 0, "middel": 1, "lav": 2}.get(s.risiko or "lav", 3), -s.vægt))
    gammel = rapport.udfald or {}
    rapport.udfald = {**risiko, "afgoerende_punkt": None,
                      "begrundelse": "; ".join(grunde[:2]) or ("Punkterne ligner vurderinger, nævnene har godtaget."
                                                               if risiko["niveau"] == "lav" else gammel.get("begrundelse", "")),
                      "model_sandsynlighed": gammel.get("sandsynlighed")}
    return rapport

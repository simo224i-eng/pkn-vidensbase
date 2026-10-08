"""Screeningstjek: find mulige svagheder i en screeningsafgørelse, miljørapport eller tilladelse.

Resultatet er en rapport med svagheder i formen "svaghed → hvorfor → kilder":
- svagheden med ordret citat fra dokumentet (eller en konstatering af, at emnet ikke er nævnt),
- hvorfor det er en svaghed: lovkravet (ordret), vejledningen (ordret) og lignende nævnsafgørelser,
- hvad værktøjet ikke har vurderet.

Værktøjet konkluderer aldrig, at en afgørelse er lovlig eller i orden. At der ikke er fundet
svagheder, betyder kun, at værktøjets kontroller ikke slog ud.

Tjekket har to lag:
1. Regler (altid): tjeklistens mønstre, bilag 6-/bilag 3-kriterier og søgning i praksis.
2. Sprogmodel (valgfrit, `llm_tjek.py`): en model gennemgår dokumentet mod tjeklisten. Dens
   citater kontrolleres automatisk, og citater, der ikke står ordret i dokumentet, fjernes.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from . import citatkontrol, lovkilder, praksis
from .dokument import Dokument
from .tjekliste_grund import IKKE_VURDERET, PUNKTER

DATA = Path(__file__).resolve().parent / "data"

# Ord, der må ikke stå i rapportens egne formuleringer (værktøjet må aldrig frikende)
FORBUDT = re.compile(r"\b(er i orden|er lovlig|ingen fejl|opfylder (alle )?(lovens )?krav|"
                     r"kan godkendes|er korrekt(e)? (vurderet|udført)|holder juridisk)\b", re.I)

# ---------- dokumenttype ----------
_TYPE_RX = {
    "screening_plan": r"(lokalplan|kommuneplantillæg|kommuneplan|planforslag)\w*[^.]{0,200}(screening|miljøvurder)|"
                      r"§ ?8,? stk\.? ?2|bilag 3|mindre områder? på lokalt plan|planers? og programmer",
    "screening_projekt": r"bilag 2|§ ?21\b|bilag 6|screeningsafgørelse|ikke (omfattet af krav om|er) miljøvurderingspligt|"
                         r"ikke VVM-pligt|VVM-screening|anmeldelse|bygherre",
    "miljoerapport_plan": r"miljørapport|0-alternativ|nulalternativ|rimelige alternativer|afgrænsningsnotat",
    "projekttilladelse": r"§ ?25-tilladelse|VVM-tilladelse|miljøkonsekvensrapport|tilladelse efter miljøvurderingslovens § 25",
}


def dokumenttype(tekst: str) -> tuple[str, dict]:
    t = tekst[:60000]
    sc = {k: len(re.findall(v, t, re.I)) for k, v in _TYPE_RX.items()}
    # Miljørapport/tilladelse kræver tydelige signaler, ellers er det en screening
    if sc["projekttilladelse"] >= 4 and sc["projekttilladelse"] > sc["screening_projekt"]:
        return "projekttilladelse", sc
    if sc["miljoerapport_plan"] >= 4 and sc["miljoerapport_plan"] > sc["screening_plan"]:
        return "miljoerapport_plan", sc
    if sc["screening_plan"] > sc["screening_projekt"]:
        return "screening_plan", sc
    return "screening_projekt", sc


# ---------- bilag 6 / bilag 3: delkriterier ----------
BILAG6 = [
    ("1a", "hele projektets dimensioner og udformning", r"dimension|størrelse|areal|omfang|højde|kapacitet|m2|m²|\bha\b|kvadratmeter"),
    ("1b", "kumulation med andre eksisterende og/eller godkendte projekter", r"kumul|andre (eksisterende|godkendte) (projekter|anlæg)|samlede? påvirkning"),
    ("1c", "brugen af naturressourcer, særlig jordarealer, jordbund, vand og biodiversitet", r"naturressource|jordbund|jordareal|råstof|vandforbrug|biodiversitet"),
    ("1d", "affaldsproduktion", r"affald"),
    ("1e", "forurening og gener", r"forurening|støj|lugt|støv|lys|vibration|gener"),
    ("1f", "risikoen for større ulykker og/eller katastrofer", r"ulykke|katastrofe|uheld|risiko|klimaændring|oversvømmelse|brand"),
    ("1g", "risikoen for menneskers sundhed", r"sundhed|helbred|luftforurening|drikkevand"),
    ("2a", "den eksisterende og godkendte arealanvendelse", r"arealanvendelse|lokalplan|kommuneplan|zone|landzone|byzone"),
    ("2b", "naturressourcernes relative rigdom, forekomst, kvalitet og regenereringskapacitet", r"naturressource|grundvand|jordbund|biodiversitet|råstof"),
    ("2c", "det naturlige miljøs bæreevne (vådområder, kyst, skov, fredede områder, Natura 2000, tætbefolkede områder, landskab og kulturarv)",
     r"vådområde|kyst|skov|naturreservat|fredning|fredet|Natura ?2000|habitatområde|tætbefolket|landskab|kulturarv|fortidsminde|§ ?3"),
    ("3", "arten af og kendetegn ved den potentielle indvirkning (omfang, intensitet, sandsynlighed, varighed, hyppighed, reversibilitet)",
     r"varighed|reversib|midlertidig|permanent|sandsynlighed|intensitet|hyppighed|omfang"),
]
BILAG3 = [
    ("1a", "i hvilket omfang planen kan danne grundlag for projekter", r"grundlag for (projekter|anlæg)|rammer for|bilag (1|2)"),
    ("1b", "planens indflydelse på andre planer", r"andre planer|kommuneplan|planhierarki|overordnet plan|landsplandirektiv"),
    ("1c", "miljøproblemer af relevans for planen", r"miljøproblem|forurening|støj|trafik|natur|landskab|grundvand"),
    ("2a", "indvirkningens sandsynlighed, varighed, hyppighed og reversibilitet", r"sandsynlig|varighed|hyppighed|reversib|midlertidig|permanent"),
    ("2b", "indvirkningens kumulative karakter", r"kumul|samlede? påvirkning"),
    ("2c", "risikoen for menneskers sundhed eller miljøet", r"sundhed|ulykke|risiko"),
    ("2d", "værdien og sårbarheden af det berørte område (natur, kulturarv, miljøkvalitetsnormer)", r"sårbar|natur|kulturarv|miljøkvalitet|Natura ?2000|§ ?3|landskab"),
]


@dataclass
class Kilde:
    type: str          # lov | vejledning | praksis | eu
    ref: str
    url: str
    citat: str
    citat_ok: bool = True
    ekstra: dict = field(default_factory=dict)


@dataclass
class Svaghed:
    punkt: str
    titel: str
    art: str                    # ikke_behandlet | uden_grundlag | svag_formulering | kriterier_mangler | model
    svaghed: str
    citat_dokument: str | None
    citat_ok: bool | None
    hvorfor: str
    spørgsmål: str
    kilder: list[Kilde]
    vægt: float = 1.0
    kilde_lag: str = "regel"    # regel | model
    niveau: str = "svaghed"     # svaghed | opmærksomhed (lavere prioritet)


@dataclass
class Rapport:
    dokument: str
    dokumenttype: str
    typesignaler: dict
    svagheder: list[Svaghed]
    ikke_vurderet: list[str]
    punkter_ikke_relevante: list[str]
    note: str
    lag: list[str]
    mindre: list[str] = field(default_factory=list)  # lavt prioriterede fund uden kilder

    def to_json(self) -> dict:
        d = asdict(self)
        return d


@lru_cache(maxsize=1)
def tjekliste() -> list[dict]:
    """Færdig tjekliste (data/tjekliste.json) eller grundpunkterne."""
    p = DATA / "tjekliste.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))["punkter"]
    return PUNKTER


def _vindue(sæt, i: int, n: int = 1) -> str:
    return " ".join(s.tekst for s in sæt[max(0, i - n): i + n + 1])


_PLANTYPER = ("screening_plan", "miljoerapport_plan")


def _lov_kilder(p: dict, dtype: str = "") -> list[Kilde]:
    ud = []
    for kode, nr, uddrag in p.get("lov", []):
        if kode == "planlov_habitat_bek" and dtype not in _PLANTYPER:
            continue
        if kode == "mvl" and dtype in _PLANTYPER and nr in ("§ 16", "§ 19", "§ 21", "§ 36", "bilag 5", "bilag 6"):
            continue
        if kode == "mvl" and dtype not in _PLANTYPER and nr in ("§ 8", "§ 10", "§ 32", "§ 33", "bilag 3"):
            continue
        s = lovkilder.slå_op(kode, nr)
        if not s:
            continue
        ok = citatkontrol.find(uddrag, s.tekst)
        ud.append(Kilde("lov", s.ref, s.url, uddrag if ok else s.tekst[:300], ok))
    return ud


_VEJL_FOR_TYPE = {
    "screening_projekt": ("vejl_mv_projekter", "habitatvejl"),
    "projekttilladelse": ("vejl_mv_projekter", "habitatvejl"),
    "screening_plan": ("vejl_mv_planer", "habitatvejl"),
    "miljoerapport_plan": ("vejl_mv_planer", "habitatvejl"),
}


def _vejl_kilder(p: dict, dtype: str, n: int = 1) -> list[Kilde]:
    koder = _VEJL_FOR_TYPE.get(dtype, ("vejl_mv_projekter",))
    if p["id"].startswith("D2"):
        koder = koder + ("bilag4_notat_levesteder_2024",)
    if p["id"].startswith("D3"):
        koder = koder + ("vejl_nbl3",)
    if p.get("vejl_citat"):
        # Håndvalgte afsnit fra byg_tjekliste (kontrolleret ordret); vælg dem for dokumenttypen
        valgte = [v for v in p["vejl_citat"] if v.get("kode") in koder] or p["vejl_citat"]
        return [Kilde("vejledning", v["ref"], v["url"], v["citat"], True) for v in valgte[:n]]
    res = lovkilder.søg(p.get("vejl_søg", p["titel"]), k=n, typer=("vejledning",), kilder=koder)
    return [Kilde("vejledning", s.ref, s.url, _bedste_sætning(s.tekst, p.get("vejl_søg", "")), True) for s in res]


def _bedste_sætning(tekst: str, q: str) -> str:
    from .bm25 import tokens
    qt = set(tokens(q))
    sæt = re.split(r"(?<=[.!?])\s+", tekst)
    best = max(sæt, key=lambda s: len(qt & set(tokens(s))) - len(s) / 2000) if sæt else tekst
    return best.strip()[:600]


def _eu_kilder(p: dict, n: int = 1) -> list[Kilde]:
    return [Kilde("eu", e["ref"], e["url"], e["citat"], True) for e in (p.get("eu_citat") or [])[:n]]


MIN_LIGHED_ANDET = 1.15  # andet praksiseksempel vises kun, hvis det ligner tilstrækkeligt


def praksis_kilder(q: str, kategorier, dtype: str, dok_tekst: str, udeluk: set[str], n: int = 2) -> list[Kilde]:
    res = praksis.lignende(q, kategorier=kategorier, dokumenttype=dtype, k=n, udeluk=udeluk,
                           kontekst=dok_tekst[:2500])
    res = [r for j, r in enumerate(res) if j == 0 or r["score"] >= MIN_LIGHED_ANDET]
    return [Kilde("praksis", f"{r['naevn']} {r['dato']}: {r['titel'][:140]}", r["link"], r["citat"], True,
                  {"id": r["id"], "fejl": r["fejl"], "regel": r["regel"], "lighed": r["score"]}) for r in res]


def _praksis_kilder(p: dict, dtype: str, kontekst: str, udeluk: set[str], dok_tekst: str = "", n: int = 2) -> list[Kilde]:
    return praksis_kilder(f"{p.get('søg', '')} {kontekst[:400]}", p.get("fejlkategorier"), dtype, dok_tekst, udeluk, n)


def _kriterier(dok: Dokument, dtype: str) -> list[tuple[str, str]]:
    liste = BILAG3 if dtype == "screening_plan" else BILAG6
    return [(nr, navn) for nr, navn, rx in liste if not re.search(rx, dok.tekst, re.I)]


# Konkrete fund (en svag formulering med citat) vægter mere end konstateringen af, at noget ikke er nævnt
ART_VÆGT = {"svag_formulering": 1.6, "uden_grundlag": 1.25, "kriterier_mangler": 1.2, "ikke_behandlet": 0.7, "model": 1.0}
MAKS_SVAGHEDER = 6


def _niveauer(svagheder: list) -> None:
    """De højst vægtede (højst MAKS_SVAGHEDER) er 'svaghed'; resten 'opmærksomhed'."""
    for i, s in enumerate(svagheder):
        s.niveau = "svaghed" if i < MAKS_SVAGHEDER else "opmærksomhed"


def _vægt(p: dict) -> float:
    return float(p.get("praksis_antal", 1)) ** 0.5


def tjek_regler(dok: Dokument, dtype: str | None = None, udeluk: set[str] | None = None) -> Rapport:
    udeluk = udeluk or set()
    dtype_gæt, sc = dokumenttype(dok.tekst)
    dtype = dtype or dtype_gæt
    sæt = dok.sætninger
    svagheder: list[Svaghed] = []
    ikke_rel = []
    for p in tjekliste():
        if dtype not in p["gælder"]:
            ikke_rel.append(f"{p['id']} {p['titel']} (gælder ikke for {dtype})")
            continue
        if p.get("relevant_hvis") and not re.search(p["relevant_hvis"], dok.tekst, re.I):
            ikke_rel.append(f"{p['id']} {p['titel']} (ikke relevant ud fra dokumentets indhold)")
            continue
        træf = [i for i, s in enumerate(sæt) if re.search(p["dækket"], s.tekst, re.I)]
        fund: list[tuple[str, str | None, str]] = []
        if p.get("kun_svagt"):
            for i, s_ in enumerate(sæt):
                if p.get("svagt") and re.search(p["svagt"], s_.tekst, re.I):
                    fund.append(("svag_formulering", s_.tekst,
                                 "Dokumentet udskyder eller udelader udtrykkeligt en del af projektet."))
                    break
        elif not træf:
            fund.append(("ikke_behandlet", None,
                         f"Dokumentet ser ikke ud til at behandle emnet ({p['titel'].lower()})."))
        else:
            if p.get("svagt"):
                for i in træf:
                    if re.search(p["svagt"], sæt[i].tekst, re.I):
                        vindue = _vindue(sæt, i)
                        if not (p.get("kræver") and re.search(p["kræver"], vindue, re.I)):
                            fund.append(("svag_formulering", sæt[i].tekst,
                                         "Formuleringen konkluderer uden synligt grundlag i samme eller nabosætningen."))
                            break
            if p.get("kræver") and not any(re.search(p["kræver"], _vindue(sæt, i, 2), re.I) for i in træf):
                fund.append(("uden_grundlag", sæt[træf[0]].tekst,
                             "Emnet nævnes, men uden de oplysninger, som vurderingen normalt kræver "
                             "(fx konkret undersøgelse, afstand, målestok eller henvisning til kriterierne)."))
        if p["id"] in ("C1", "C2") and dtype in ("screening_projekt", "screening_plan") and not p.get("kun_svagt"):
            mangler = _kriterier(dok, dtype)
            if mangler:
                bilag = "bilag 3" if dtype == "screening_plan" else "bilag 6"
                fund.append(("kriterier_mangler", None,
                             f"Disse kriterier i {bilag} ser ikke ud til at være nævnt: " +
                             "; ".join(f"{nr}) {navn}" for nr, navn in mangler) + "."))
        if fund:
            # Ét fund pr. punkt: første fund bærer citatet; øvrige beskrivelser lægges til
            art, citat, tekst = fund[0]
            for _, c2, t2 in fund[1:]:
                tekst += " " + t2
                citat = citat or c2
            fund = [(art, citat, tekst)]
        for art, citat, tekst in fund:
            kontekst = citat or p["titel"]
            kilder = (_lov_kilder(p, dtype) + _vejl_kilder(p, dtype) + _eu_kilder(p)
                      + _praksis_kilder(p, dtype, kontekst, udeluk, dok.tekst))
            svagheder.append(Svaghed(
                punkt=p["id"], titel=p["titel"], art=art, svaghed=tekst,
                citat_dokument=citat, citat_ok=(citatkontrol.find(citat, dok.tekst) if citat else None),
                hvorfor=_hvorfor(p, kilder), spørgsmål=p["spørgsmål"], kilder=kilder,
                vægt=round(_vægt(p) * ART_VÆGT.get(art, 1.0), 2)))
    svagheder.sort(key=lambda s: (-s.vægt, s.punkt))
    _niveauer(svagheder)
    return Rapport(dok.navn, dtype, sc, svagheder, list(IKKE_VURDERET), ikke_rel, NOTE, ["regler"])


NOTE = ("Rapporten peger på steder, hvor nævnene i lignende sager har underkendt myndighedens vurdering. "
        "Den er ikke en juridisk vurdering af, om afgørelsen holder. En fagperson skal vurdere hvert punkt.")


def _hvorfor(p: dict, kilder: list[Kilde]) -> str:
    lov = [k.ref for k in kilder if k.type == "lov"]
    n = p.get("praksis_antal")
    dele = []
    if lov:
        dele.append("Kravet følger af " + " og ".join(dict.fromkeys(lov)) + ".")
    if n:
        dele.append(f"Fejltypen indgik i {n} af de analyserede sager, hvor nævnet gav klager medhold.")
    return " ".join(dele)


def renset(rapport: Rapport) -> Rapport:
    """Fjern formuleringer, der kunne læses som en frikendelse, fra rapportens egne tekster."""
    for s in rapport.svagheder:
        s.svaghed = FORBUDT.sub("[udeladt formulering]", s.svaghed)
        s.hvorfor = FORBUDT.sub("[udeladt formulering]", s.hvorfor)
    return rapport


def tjek(dok: Dokument, dtype: str | None = None, udeluk: set[str] | None = None,
         llm=None) -> Rapport:
    """Kør regellaget og (hvis llm er givet) modellaget. llm: callable(prompt:str)->str."""
    r = tjek_regler(dok, dtype, udeluk)
    if llm is not None:
        from . import llm_tjek
        r = llm_tjek.supplér(r, dok, llm, udeluk=udeluk)
    return renset(r)


def som_markdown(r: Rapport) -> str:
    ud = [f"# Screeningstjek: {r.dokument}", "",
          f"**Dokumenttype (gæt):** {r.dokumenttype}  ", f"**Lag:** {', '.join(r.lag)}", "",
          f"> {r.note}", ""]
    if not r.svagheder:
        ud += ["Værktøjets kontroller slog ikke ud på dette dokument. Det er ikke en vurdering af, "
               "om afgørelsen holder; se også listen over det, værktøjet ikke vurderer.", ""]
    første_opm = True
    for n, s in enumerate(r.svagheder, 1):
        if s.niveau == "opmærksomhed" and første_opm:
            ud += ["# Øvrige opmærksomhedspunkter", "Lavere prioritet: emner, der ikke ses behandlet, eller "
                   "som nævnene sjældnere har underkendt på.", ""]
            første_opm = False
        ud.append(f"## {n}. {s.titel} ({s.punkt})")
        ud.append(f"**Svaghed:** {s.svaghed}")
        if s.citat_dokument:
            mærke = "" if s.citat_ok else " ⚠ citatet kunne ikke genfindes ordret"
            ud.append(f"> «{s.citat_dokument}»{mærke}")
        ud.append(f"**Hvorfor:** {s.hvorfor}")
        ud.append(f"**Spørgsmål at stille:** {s.spørgsmål}")
        ud.append("**Kilder:**")
        for k in s.kilder:
            ud.append(f"- [{k.ref}]({k.url}): «{k.citat[:400]}»")
        ud.append("")
    if r.mindre:
        ud.append("## Mindre bemærkninger (uden kilder)")
        ud += [f"- {x}" for x in r.mindre]
        ud.append("")
    ud.append("## Hvad værktøjet ikke har vurderet")
    ud += [f"- {x}" for x in r.ikke_vurderet]
    if r.punkter_ikke_relevante:
        ud.append("\nTjeklistepunkter, der ikke er kørt:")
        ud += [f"- {x}" for x in r.punkter_ikke_relevante]
    return "\n".join(ud)

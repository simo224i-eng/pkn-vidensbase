"""Stedtjek: hvad ligger der omkring planen/projektet, og nævner dokumentet det?

Værktøjet finder planens eller projektets placering og slår op i åbne kortlag:
- Danmarks Miljøportal (arealeditering-dist-geo.miljoeportal.dk): Natura 2000 (habitat- og
  fuglebeskyttelsesområder), Ramsar, § 3-beskyttet natur, fredninger (med link til kendelsen),
  å-, sø-, skov- og kirkebyggelinjer, beskyttede vandløb, natur- og vildtreservater.
- Plandata.dk (geoserver.plandata.dk): kommuneplanrammer, kommuneplanens udpegninger (værdifulde
  landskaber, kulturmiljøer, lavbundsarealer, økologiske forbindelser, naturbeskyttelsesområder,
  oversvømmelse/erosion, støjbelastede arealer) og andre lokalplaner i nærheden (kumulation).

Derefter sammenlignes med dokumentet: områder i nærheden, som dokumentet ikke nævner, og afstande i
dokumentet, der ikke passer med kortet, bliver til svagheder (art "stedtjek"). Alle fund vises også som
"Stedfakta", så de kan bruges som opslag.

Placering: kommune + plannummer (plandata), en adresse (OpenStreetMap Nominatim) eller koordinater i
EPSG:25832. Kortdata er offentlige; der sendes kun placeringen, aldrig dokumentets tekst.
"""
from __future__ import annotations

import re
import time
import urllib.parse as up
from dataclasses import asdict, dataclass, field
from functools import lru_cache

import requests

MP = "https://arealeditering-dist-geo.miljoeportal.dk/geoserver/wfs"
PD = "https://geoserver.plandata.dk/geoserver/wfs"
UA = {"User-Agent": "Mozilla/5.0 (Miljoejuristen/pkn-vidensbase)"}

# (lag, visningsnavn, søgeradius i m, navnefelt, tjeklistepunkt, mønster der viser at dokumentet nævner emnet)
MILJO_LAG = [
    ("dai:habitat_omr", "Natura 2000-habitatområde", 5000, "Objektnavn", "D1",
     r"Natura ?2000|habitatområde|habitatdirektiv|internationalt naturbeskyttelsesområde|\bN\d{1,3}\b"),
    ("dai:fugle_bes_omr", "Natura 2000-fuglebeskyttelsesområde", 5000, "Objektnavn", "D1",
     r"Natura ?2000|fuglebeskyttelsesområde|internationalt naturbeskyttelsesområde|\bF\d{1,3}\b"),
    ("dai:ramsar_omr", "Ramsarområde", 5000, "Objektnavn", "D1", r"Ramsar|Natura ?2000"),
    ("dai:bes_naturtyper", "§ 3-beskyttet natur", 500, "Natyp_navn", "D3",
     r"§ ?3|beskyttet natur|beskyttede naturtyper|naturbeskyttelseslovens § 3"),
    ("dai:bes_vandloeb", "§ 3-beskyttet vandløb", 300, "Temanavn", "D3", r"§ ?3|beskyttet vandløb|vandløb"),
    ("dai:fredede_omr", "Fredning", 1000, "Fred_navn", "D3", r"fredning|fredet|fredningskendelse"),
    ("dai:natur_vildt_reservat", "Natur- og vildtreservat", 2000, "Objektnavn", "D3", r"vildtreservat|naturreservat"),
    ("dai:aa_bes_linjer", "Å-beskyttelseslinje", 0, "Temanavn", "D3", r"åbeskyttelseslinje|å-beskyttelseslinje|beskyttelseslinje"),
    ("dai:soe_bes_linjer", "Sø-beskyttelseslinje", 0, "Temanavn", "D3", r"søbeskyttelseslinje|sø-beskyttelseslinje|beskyttelseslinje"),
    ("dai:skovbyggelinjer", "Skovbyggelinje", 0, "Temanavn", "D3", r"skovbyggelinje"),
    ("dai:kirkebyggelinjer", "Kirkebyggelinje", 0, "Temanavn", "C5", r"kirkebyggelinje|kirkeomgivelse|kirke"),
]
PLAN_LAG = [
    ("pdk:theme_pdk_bevaringsvaerdigelandskaber_vedtaget", "Bevaringsværdigt landskab (kommuneplan)", 0, "C5",
     r"bevaringsværdig\w* landskab|landskab"),
    ("pdk:theme_pdk_stoerresammenhaengendelandskaber_vedtaget", "Større sammenhængende landskab (kommuneplan)", 0, "C5",
     r"sammenhængende landskab|landskab"),
    ("pdk:theme_pdk_vaerdifuldtkulturmiljoe_vedtaget", "Værdifuldt kulturmiljø (kommuneplan)", 0, "C5", r"kulturmiljø"),
    ("pdk:theme_pdk_lavbundsareal_vedtaget", "Lavbundsareal (kommuneplan)", 0, "C6", r"lavbund"),
    ("pdk:theme_pdk_oversvoemerosion_vedtaget", "Risiko for oversvømmelse/erosion (kommuneplan)", 0, "C6",
     r"oversvøm|erosion|klimatilpasning|skybrud"),
    ("pdk:theme_pdk_oekologiskforbindelse_vedtaget", "Økologisk forbindelse (kommuneplan)", 200, "D3", r"økologisk\w* forbindelse|spredningskorridor"),
    ("pdk:theme_pdk_naturbeskyttelsesomraade_vedtaget", "Naturbeskyttelsesinteresser (kommuneplan)", 200, "D3", r"naturbeskyttelsesområde|naturinteresse|Grønt Danmarkskort"),
    ("pdk:theme_pdk_stoejbelastetareal_vedtaget", "Støjbelastet areal (kommuneplan)", 0, "C4", r"støj"),
]
LOKALPLAN_LAG = ("pdk:theme_pdk_lokalplan_forslag", "pdk:theme_pdk_lokalplan_vedtaget")


@dataclass
class Fund:
    kilde: str          # miljoeportal | plandata
    lag: str
    type: str
    navn: str
    afstand_m: int
    punkt: str
    nævnt: bool = False
    link: str | None = None
    detaljer: dict = field(default_factory=dict)


@dataclass
class Sted:
    beskrivelse: str
    kilde: str
    bbox: tuple
    geometri: object = None


def _get_json(url: str, retries: int = 3):
    for i in range(retries):
        try:
            r = requests.get(url, headers=UA, timeout=60)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                return r.json()
        except requests.RequestException:
            pass
        time.sleep(1 + i)
    return None


def _shape(geom):
    from shapely.geometry import shape
    return shape(geom)


# ---------- placering ----------
@lru_cache(maxsize=256)
def plan_sted(kommune: str, plannr: str) -> Sted | None:
    kommune = kommune.replace(" Kommune", "").replace("Københavns", "København")
    for lag in ("pdk:theme_pdk_lokalplan_med_historik", "pdk:theme_pdk_kommuneplantillaeg_oversigt_version"):
        for nr in dict.fromkeys([plannr, plannr.replace(".", "-"), plannr.lstrip("0")]):
            cql = f"kommunenavn='{kommune}' AND plannr='{nr}'"
            d = _get_json(f"{PD}?service=WFS&version=1.0.0&request=GetFeature&typeName={lag}"
                          f"&outputFormat=application/json&CQL_FILTER={up.quote(cql)}&maxFeatures=5")
            if d and d.get("features"):
                f = d["features"][-1]
                g = _shape(f["geometry"])
                return Sted(f"{f['properties'].get('plannavn')} ({kommune} {nr})", "plandata", g.bounds, g)
    return None


@lru_cache(maxsize=256)
def adresse_sted(adresse: str) -> Sted | None:
    """Adresse -> punkt i EPSG:25832 via OpenStreetMap Nominatim (offentlig, max 1/s)."""
    d = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=30,
                     params={"q": adresse, "countrycodes": "dk", "format": "json", "limit": 1}).json()
    time.sleep(1)
    if not d:
        return None
    from shapely.geometry import Point
    x, y = _wgs84_til_utm32(float(d[0]["lat"]), float(d[0]["lon"]))
    p = Point(x, y)
    return Sted(d[0].get("display_name", adresse), "OpenStreetMap", p.bounds, p)


def koordinat_sted(x: float, y: float) -> Sted:
    from shapely.geometry import Point
    p = Point(x, y)
    return Sted(f"punkt {x:.0f}, {y:.0f}", "koordinat", p.bounds, p)


def _wgs84_til_utm32(lat: float, lon: float) -> tuple[float, float]:
    """WGS84 -> ETRS89/UTM32 (EPSG:25832). Standard transversal Mercator; nøjagtig til få meter."""
    import math
    a, f = 6378137.0, 1 / 298.257222101
    k0, lon0 = 0.9996, math.radians(9.0)
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    phi, lam = math.radians(lat), math.radians(lon)
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    t = math.tan(phi) ** 2
    c = ep2 * math.cos(phi) ** 2
    A = math.cos(phi) * (lam - lon0)
    m = a * ((1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256) * phi
             - (3 * e2 / 8 + 3 * e2 ** 2 / 32 + 45 * e2 ** 3 / 1024) * math.sin(2 * phi)
             + (15 * e2 ** 2 / 256 + 45 * e2 ** 3 / 1024) * math.sin(4 * phi)
             - (35 * e2 ** 3 / 3072) * math.sin(6 * phi))
    x = k0 * n * (A + (1 - t + c) * A ** 3 / 6 + (5 - 18 * t + t ** 2 + 72 * c - 58 * ep2) * A ** 5 / 120) + 500000
    y = k0 * (m + n * math.tan(phi) * (A ** 2 / 2 + (5 - t + 9 * c + 4 * c ** 2) * A ** 4 / 24
                                       + (61 - 58 * t + t ** 2 + 600 * c - 330 * ep2) * A ** 6 / 720))
    return x, y


def find_sted(tekst: str, kommune: str | None = None, plannr: str | None = None,
              adresse: str | None = None) -> Sted | None:
    """Brug angivne oplysninger, ellers gæt kommune/plannummer/adresse fra dokumentet."""
    if kommune and plannr:
        s = plan_sted(kommune, plannr)
        if s:
            return s
    if adresse:
        s = adresse_sted(adresse)
        if s:
            return s
    t = tekst[:8000]
    km = kommune or (re.search(r"([A-ZÆØÅ][\wæøå-]+(?:-[A-ZÆØÅ][\wæøå]+)?) Kommune", t) or [None, None])[1]
    if km:
        for nr in re.findall(r"(?:lokalplan(?:forslag)?|kommuneplantillæg|tillæg)\s+(?:nr\.\s*)?([\w./-]*\d[\w./-]*)", t, re.I)[:3]:
            s = plan_sted(km, nr.strip(" .,"))
            if s:
                return s
    m = re.search(r"([A-ZÆØÅ][a-zæøå]+(?:vej|gade|allé|alle|vænge|stræde|plads|parken|toften|bakken|engen)\s+\d+[A-Z]?)"
                  r"(?:,?\s*(\d{4})\s+([A-ZÆØÅ][\wæøå ]+))?", t)
    if m:
        q = m.group(1) + (f", {m.group(2)} {m.group(3)}" if m.group(2) else (f", {km}" if km else ""))
        return adresse_sted(q)
    return None


# ---------- opslag ----------
_CACHE: dict[str, tuple[float, list]] = {}
CACHE_SEK = 24 * 3600


def _lag(base: str, lag: str, bbox: tuple, radius: int) -> list[dict]:
    """Features i et lag inden for bbox + radius. Caches i 24 timer pr. forespørgsel."""
    x0, y0, x1, y1 = bbox
    b = f"{x0 - radius:.0f},{y0 - radius:.0f},{x1 + radius:.0f},{y1 + radius:.0f},EPSG:25832"
    url = (f"{base}?service=WFS&version=1.0.0&request=GetFeature&typeName={lag}"
           f"&outputFormat=application/json&BBOX={b}&maxFeatures=400")
    hit = _CACHE.get(url)
    if hit and time.time() - hit[0] < CACHE_SEK:
        return hit[1]
    d = _get_json(url)
    feats = (d or {}).get("features", [])
    if d is not None:
        _CACHE[url] = (time.time(), feats)
    return feats


def _hent_alle(sted: Sted) -> dict:
    """Hent alle lag parallelt (forskellige servere/lag, én forespørgsel hver)."""
    from concurrent.futures import ThreadPoolExecutor
    opgaver = {lag: (MP, lag, r) for lag, _, r, _, _, _ in MILJO_LAG}
    opgaver |= {lag: (PD, lag, r) for lag, _, r, _, _ in PLAN_LAG}
    opgaver["kommuneplanramme"] = (PD, "pdk:theme_pdk_kommuneplanramme_vedtaget_v", 0)
    opgaver |= {lag: (PD, lag, 1000) for lag in LOKALPLAN_LAG}
    with ThreadPoolExecutor(max_workers=8) as ex:
        fut = {k: ex.submit(_lag, base, lag, sted.bbox, r) for k, (base, lag, r) in opgaver.items()}
        return {k: f.result() for k, f in fut.items()}


def omgivelser(sted: Sted) -> list[Fund]:
    g = sted.geometri
    ud: list[Fund] = []
    alle = _hent_alle(sted)
    for lag, navn, r, felt, punkt, _ in MILJO_LAG:
        bedst: dict[str, Fund] = {}
        for ft in alle[lag]:
            p = ft["properties"]
            afst = int(round(g.distance(_shape(ft["geometry"]))))
            if afst > r:
                continue
            nm = str(p.get(felt) or p.get("Temanavn") or navn)
            if nm not in bedst or afst < bedst[nm].afstand_m:
                det = {k: p.get(k) for k in ("Site_ident", "Loc_ident", "Fred_tnavn", "Reg_nr") if p.get(k)}
                bedst[nm] = Fund("miljoeportal", lag, navn, nm, afst, punkt, link=p.get("Link"), detaljer=det)
        ud += sorted(bedst.values(), key=lambda f: f.afstand_m)[:5]
    for lag, navn, r, punkt, _ in PLAN_LAG:
        for ft in alle[lag][:20]:
            p = ft["properties"]
            afst = int(round(g.distance(_shape(ft["geometry"]))))
            if afst <= r:
                ud.append(Fund("plandata", lag, navn, str(p.get("plannavn") or p.get("navn") or navn), afst, punkt,
                               link=p.get("doklink")))
                break
    # Kommuneplanramme(r), som stedet ligger i
    for ft in alle["kommuneplanramme"][:3]:
        p = ft["properties"]
        if g.distance(_shape(ft["geometry"])) == 0:
            ud.append(Fund("plandata", "kommuneplanramme", "Kommuneplanramme",
                           f"{p.get('plannr')} {p.get('plannavn') or ''}".strip(), 0, "A3", link=p.get("doklink"),
                           detaljer={"anvendelse": p.get("anvendelsegenerel"), "zone": p.get("fremtidigzonestatus")}))
    # Andre lokalplaner/forslag inden for 1 km (kumulation)
    andre = []
    for lag in LOKALPLAN_LAG:
        for ft in alle[lag]:
            p = ft["properties"]
            afst = int(round(g.distance(_shape(ft["geometry"]))))
            dato = str(p.get("datovedt") or p.get("datoforsl") or "0")
            gammel = dato[:4].isdigit() and int(dato[:4]) < 2015
            if 0 < afst <= 1000 and not gammel and not re.search(r"byplanvedtægt", str(p.get("plannavn")), re.I):
                andre.append(Fund("plandata", lag, "Anden lokalplan i nærheden" + (" (forslag)" if "forslag" in lag else ""),
                                  f"{p.get('plannr')} {p.get('plannavn') or ''}".strip(), afst, "C3", link=p.get("doklink"),
                                  detaljer={"vedtaget": p.get("datovedt"), "forslag": p.get("datoforsl")}))
    ud += sorted(andre, key=lambda f: f.afstand_m)[:6]
    return ud


# ---------- sammenligning med dokumentet ----------
_AFSTAND = re.compile(r"(\d+(?:[.,]\d+)?)\s*(km|kilometer|m|meter)\b", re.I)


def _påstået_afstand(sætning: str) -> float | None:
    m = _AFSTAND.search(sætning)
    if not m:
        return None
    v = float(m.group(1).replace(".", "").replace(",", ".")) if m.group(2).lower().startswith("m") and "," not in m.group(1) \
        else float(m.group(1).replace(",", "."))
    return v * 1000 if m.group(2).lower().startswith("k") else v


# Hvornår et ikke-nævnt område er en svaghed (ellers kun stedfakta). Kalibreret i backtest:
# med bredere grænser gav stedtjekket 5-10 fund pr. dokument, også i stadfæstede sager.
SVAGHEDSGRÆNSE_M = {
    "dai:habitat_omr": 1000, "dai:fugle_bes_omr": 1000, "dai:ramsar_omr": 1000,
    "dai:bes_naturtyper": 100, "dai:bes_vandloeb": 50, "dai:fredede_omr": 100, "dai:natur_vildt_reservat": 0,
    "dai:aa_bes_linjer": 0, "dai:soe_bes_linjer": 0, "dai:skovbyggelinjer": 0, "dai:kirkebyggelinjer": 0,
}


def sammenlign(tekst: str, fund: list[Fund], sætninger: list[str]) -> list[dict]:
    """Returnér svagheder: (a) relevante områder, som dokumentet ikke nævner; (b) afstande, der ikke passer."""
    mønstre = {lag: rx for lag, _, _, _, _, rx in MILJO_LAG} | {lag: rx for lag, _, _, _, rx in PLAN_LAG}
    ud = []
    pr_type: dict[str, list[Fund]] = {}
    for f in fund:
        rx = mønstre.get(f.lag)
        if f.type.startswith("Anden lokalplan"):
            f.nævnt = bool(re.search(r"kumul|andre (planer|projekter|lokalplaner)|samlede påvirkning", tekst, re.I))
        elif f.lag == "kommuneplanramme":
            f.nævnt = True
        else:
            f.nævnt = bool(rx and re.search(rx, tekst, re.I)) or bool(f.navn and len(f.navn) > 5 and f.navn.lower() in tekst.lower())
        pr_type.setdefault(f.type, []).append(f)
    for typ, fl in pr_type.items():
        nærmeste = min(fl, key=lambda f: f.afstand_m)
        if typ.startswith("Anden lokalplan"):
            nye_forslag = [f for f in fl if "forslag" in f.type and f.afstand_m <= 500]
            if not nærmeste.nævnt and nye_forslag:  # kun aktuelle forslag tæt på; ellers stedfakta
                ud.append({"punkt": "C3", "type": "ikke_nævnt", "fund": [asdict(f) for f in fl[:4]],
                           "tekst": f"Der er {len(fl)} andre lokalplaner/forslag inden for 1 km (nærmeste {nærmeste.navn}, "
                                    f"{nærmeste.afstand_m} m), men dokumentet omtaler ikke kumulation med andre planer."})
            continue
        if nærmeste.lag == "kommuneplanramme":
            continue
        if not nærmeste.nævnt:
            grænse = SVAGHEDSGRÆNSE_M.get(nærmeste.lag)
            if grænse is None or nærmeste.afstand_m > grænse:
                continue  # kun stedfakta
            ud.append({"punkt": nærmeste.punkt, "type": "ikke_nævnt", "fund": [asdict(f) for f in fl[:3]],
                       "tekst": f"{typ} \"{nærmeste.navn}\" ligger {'inden for området' if nærmeste.afstand_m == 0 else f'{nærmeste.afstand_m} m fra området'}, "
                                f"men dokumentet ser ikke ud til at nævne det."})
            continue
        # Afstandskontrol for Natura 2000 og § 3/fredning
        rx = mønstre.get(nærmeste.lag)
        for s in sætninger:
            if rx and re.search(rx, s, re.I):
                påstået = _påstået_afstand(s)
                if påstået and påstået > 1.5 * max(nærmeste.afstand_m, 50) and påstået - nærmeste.afstand_m > 300:
                    ud.append({"punkt": nærmeste.punkt, "type": "afstand", "citat": s, "fund": [asdict(nærmeste)],
                               "tekst": f"Dokumentet angiver ca. {påstået:.0f} m, men kortet viser {nærmeste.afstand_m} m "
                                        f"til {typ.lower()} \"{nærmeste.navn}\" (målt fra planens/projektets afgrænsning)."})
                break
    samlet: dict[tuple, dict] = {}
    for sv in ud:
        nøgle = (sv["punkt"], sv["type"])
        if nøgle in samlet:
            samlet[nøgle]["tekst"] += " " + sv["tekst"]
            samlet[nøgle]["fund"] += sv["fund"]
        else:
            samlet[nøgle] = sv
    return list(samlet.values())


def stedtjek(tekst: str, sætninger: list[str], **placering) -> dict:
    sted = find_sted(tekst, **placering)
    if not sted:
        return {"sted": None, "fund": [], "svagheder": [],
                "note": "Placeringen kunne ikke findes. Angiv kommune og plannummer, en adresse eller koordinater."}
    fund = omgivelser(sted)
    sv = sammenlign(tekst, fund, sætninger)
    return {"sted": {"beskrivelse": sted.beskrivelse, "kilde": sted.kilde, "bbox": [round(v) for v in sted.bbox]},
            "fund": [asdict(f) for f in fund], "svagheder": sv,
            "note": "Kortdata fra Danmarks Miljøportal og plandata.dk. Afstande er målt fra afgrænsningen (planer) "
                    "eller adressepunktet (projekter) og er vejledende."}

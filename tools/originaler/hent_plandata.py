"""Find lokalplaner og kommuneplantillæg på plandata.dk (WFS) for planscreeningssagerne.

    python tools/originaler/hent_plandata.py

Slår op på kommunenavn + plannummer i plandata.dk's åbne geoserver (lag med historik, så både forslag og
vedtaget version kommer med). Gemmer links til planens PDF (`doklink`), som ofte indeholder eller henviser til
miljøscreeningen. Output: tools/originaler/fund_plandata.json.
"""
import json
import re
import time
import urllib.parse as up
from pathlib import Path

import requests

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
KAND = REPO / "analyser" / "miljoevurdering" / "v2" / "originaler_kandidater.json"
UD = HER / "fund_plandata.json"
WFS = "https://geoserver.plandata.dk/geoserver/wfs"
LAG = {"lokalplan": "pdk:theme_pdk_lokalplan_med_historik",
       "tillæg": "pdk:theme_pdk_kommuneplantillaeg_oversigt_version"}
FELTER = "planid,plannr,plannavn,kommunenavn,status,doklink,datoforsl,datovedt,versionsnr"


def opslag(s, lag, kommune, nr):
    cql = f"kommunenavn='{kommune}' AND plannr='{nr}'"
    u = (f"{WFS}?service=WFS&version=1.0.0&request=GetFeature&typeName={lag}&outputFormat=application/json"
         f"&propertyName={FELTER}&CQL_FILTER={up.quote(cql)}&maxFeatures=20")
    r = s.get(u, timeout=60)
    if r.status_code != 200 or not r.text.startswith("{"):
        return []
    return [f["properties"] for f in r.json().get("features", [])]


def main():
    kand = json.loads(KAND.read_text(encoding="utf-8"))
    fund = {}
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (pkn-vidensbase research; 1 req/s)"
    for k in kand:
        if k["type"] != "screening_plan" or not k["myndighed"]:
            continue
        kommune = k["myndighed"].replace(" Kommune", "").replace("Københavns", "København")
        hits = []
        for p in dict.fromkeys(k.get("planer") or []):
            typ = "lokalplan" if p.lower().startswith("lokalplan") else "tillæg"
            nr = re.sub(r"^(lokalplan(forslag)?|kommuneplantillæg|tillæg)\s*", "", p, flags=re.I).strip(" .,")
            for variant in dict.fromkeys([nr, nr.replace(".", "-"), nr.lstrip("0")]):
                try:
                    res = opslag(s, LAG[typ], kommune, variant)
                except Exception as e:
                    print("  fejl", k["id"], e)
                    res = []
                time.sleep(1)
                for r in res:
                    if r.get("doklink"):
                        hits.append({"plan": p, "plannavn": r.get("plannavn"), "status": r.get("status"),
                                     "datoforsl": r.get("datoforsl"), "datovedt": r.get("datovedt"),
                                     "url": r["doklink"]})
                if res:
                    break
        uniq = list({h["url"]: h for h in hits}.values())
        fund[k["id"]] = uniq
        print(k["id"], kommune, k.get("planer"), "->", len(uniq))
    UD.write_text(json.dumps(fund, ensure_ascii=False, indent=1), encoding="utf-8")
    print(sum(1 for v in fund.values() if v), "af", len(fund), "plansager med plandata-link")


if __name__ == "__main__":
    main()

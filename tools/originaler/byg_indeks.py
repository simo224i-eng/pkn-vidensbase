"""Byg indekset over kommunernes oprindelige dokumenter til Miljøjuristen.

    python tools/originaler/byg_indeks.py

Samler fund fra FirstAgenda-dagsordener (fund_firstagenda.json) og plandata.dk (fund_plandata.json) og
gemmer miljoejurist/data/originaler.json: pr. nævnssag en kort liste af links med type og sikkerhed.
Kun links og titler gemmes (dokumenterne kan indeholde navne).

Sikkerhed:
- "høj": dagsordenpunkt med plannummer/match, møde før afgørelsen, og et bilag der ligner screeningen
- "middel": dagsordenpunkt med god score uden screeningsbilag (screeningen er ofte i planforslaget),
            eller planens PDF fra plandata
- "lav": svagere match (vises ikke i rapporten, men gemmes til kontrol)
"""
import json
import re
from pathlib import Path

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
UD = REPO / "miljoejurist" / "data" / "originaler.json"
PLANNAVN = re.compile(r"lokalplan|kommuneplan|tillæg|planforslag|forslag til|screening|miljøvurdering|miljørapport|"
                      r"spildevandsplan|vandforsyningsplan|klimaplan|varmeplan", re.I)


def main():
    fa = json.loads((HER / "fund_firstagenda.json").read_text(encoding="utf-8")) if (HER / "fund_firstagenda.json").exists() else {}
    pd = json.loads((HER / "fund_plandata.json").read_text(encoding="utf-8")) if (HER / "fund_plandata.json").exists() else {}
    kontrol = json.loads((HER / "kontrol.json").read_text(encoding="utf-8")) if (HER / "kontrol.json").exists() else {}
    indeks = {}
    for sid, v in fa.items():
        k = (v.get("kandidater") or [None])[0]
        if not k:
            continue
        links = []
        sikkerhed = "høj" if (k["score"] >= 3 and k["screening_bilag"]) else ("middel" if k["score"] >= 3 else "lav")
        for b in k["screening_bilag"][:2]:
            links.append({"type": "screening (bilag til dagsorden)", "titel": b["navn"], "url": b["url"], "sikkerhed": sikkerhed})
        if not k["screening_bilag"]:
            # Kun bilag, hvis navn ligner en plan/screening (bilagsnavne kan ellers indeholde privatpersoners navne)
            for b in [b for b in (k.get("bilag") or []) if PLANNAVN.search(b["navn"] or "")][:2]:
                links.append({"type": "bilag til dagsorden", "titel": b["navn"], "url": b["url"], "sikkerhed": sikkerhed})
        links.append({"type": "dagsordenpunkt", "titel": f"{k['udvalg']} {k['møde']}: {k['punkt']}", "url": k["punkt_url"],
                      "sikkerhed": sikkerhed})
        indeks[sid] = links
    for sid, hits in pd.items():
        for h in hits[:2]:
            status = {"V": "vedtaget", "F": "forslag", "A": "aflyst"}.get(str(h.get("status")), str(h.get("status") or ""))
            indeks.setdefault(sid, []).append({"type": f"planens PDF på plandata ({status}; screeningen er ofte kun resumeret)",
                                               "titel": f"{h['plan']} {h.get('plannavn') or ''}".strip(),
                                               "url": h["url"], "sikkerhed": "middel"})
    # Manuel/agent-kontrol kan nedgradere eller bekræfte (kontrol.json: {sag: {url: "ok"|"forkert"}})
    for sid, links in indeks.items():
        # Er dagsordenens screeningsbilag forkert, er hele dagsordenpunktet det som regel også
        fa_forkert = any(kontrol.get(sid, {}).get(l["url"]) == "forkert" for l in links if "plandata" not in l["type"])
        for l in links:
            vurd = kontrol.get(sid, {}).get(l["url"])
            if fa_forkert and "plandata" not in l["type"] and vurd != "ok":
                vurd = "forkert"
            if vurd == "forkert":
                l["sikkerhed"] = "forkert"
            elif vurd == "ok":
                l["sikkerhed"] = "kontrolleret"
    UD.write_text(json.dumps(indeks, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    import collections
    c = collections.Counter(max((l["sikkerhed"] for l in v), key=["forkert", "lav", "middel", "høj", "kontrolleret"].index)
                            for v in indeks.values())
    print(len(indeks), "sager med links;", dict(c))


if __name__ == "__main__":
    main()

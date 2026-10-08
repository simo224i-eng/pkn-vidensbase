"""Forbered trin 1 og trin 2 (v2) af miljøvurderingsanalysen på det nye korpus.

    python analyser/miljoevurdering/v2/forbered.py

Univers: afgørelser fra 1/1 2020 til i dag i PKN "Miljøvurderingsloven" og
"Planloven, VVM" samt MFKN "Miljøvurdering af konkrete projekter" og "Miljøvurdering
af planer og programmer". Hertil husdyrbrugsager med medhold fra 2022 og frem, hvor
nævnets vurdering handler om Natura 2000, bilag IV eller § 3-natur (se BESLUTNINGER.md).

Output i v2/:
  univers.json        id -> metadata (gammelt M-id, hvis sagen var med i v1)
  s1_genbrug.jsonl    trin 1-mærker fra v1 for sager, der allerede er mærket
  s1_mangler.txt      id'er, der skal have trin 1 (nye sager)
  sager/<id>.txt      indledning + HELE nævnets vurdering (til trin 1 og 2)
"""
import glob
import json
import re
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parent
V1 = V2.parent
REPO = V2.parents[2]
sys.path.insert(0, str(REPO))
from miljoejurist import corpus  # noqa: E402

MV_KAT = {"Miljøvurderingsloven", "Planloven, VVM", "Miljøvurdering af konkrete projekter",
          "Miljøvurdering af planer og programmer"}
HUSDYR_RE = re.compile(r"Natura 2000|habitat|bilag IV|§ 3-|beskyttet natur|ammoniak", re.I)


def main():
    k = corpus.load()
    meta_v1 = json.load(open(V1 / "meta.json", encoding="utf-8"))
    uuid_til_v1 = {m["Link"].rsplit("/", 1)[-1]: m["id"] for m in meta_v1}
    s1_v1 = {}
    for f in glob.glob(str(V1 / "s1_*.jsonl")):
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            s1_v1[d["id"]] = d

    univers = {}
    for a in k:
        if a.dato < "2020-01-01":
            continue
        mv = bool(MV_KAT & set(a.kategorier))
        husdyr = ("Husdyrbrugloven" in a.kategorier and a.dato >= "2022-01-01"
                  and a.udfald in ("medhold", "delvis")
                  and len(HUSDYR_RE.findall(corpus.nævnets_vurdering(a.tekst))) >= 3)
        if not (mv or husdyr):
            continue
        univers[a.id] = {"id": a.id, "v1_id": uuid_til_v1.get(a.uuid), "naevn": a.naevn,
                         "dato": a.dato, "titel": a.titel, "link": a.link, "kategorier": a.kategorier,
                         "udfald_regel": a.udfald, "afkortet": a.afkortet, "tegn": len(a.tekst),
                         "gruppe": "husdyr" if (husdyr and not mv) else "miljoevurdering"}
        (V2 / "sager").mkdir(exist_ok=True)
        vurd = corpus.nævnets_vurdering(a.tekst)
        intro = corpus.indledning(a.tekst)
        hoved = (f"ID: {a.id}\nNævn: {a.naevn}\nDato: {a.dato}\nTitel: {a.titel}\nLink: {a.link}\n"
                 f"Kategorier: {', '.join(a.kategorier)}\n\n=== INDLEDNING ===\n{intro.strip()}\n\n"
                 f"=== HELE AFGØRELSEN (sagsfremstilling og nævnets vurdering) ===\n")
        # Hele teksten gemmes; nævnets vurdering er markeret med ## overskrifter.
        (V2 / "sager" / f"{a.id}.txt").write_text(hoved + a.tekst, encoding="utf-8")
        univers[a.id]["vurdering_tegn"] = len(vurd)

    genbrug, mangler = [], []
    for i, u in univers.items():
        if u["v1_id"] and u["v1_id"] in s1_v1:
            d = dict(s1_v1[u["v1_id"]])
            d["v1_id"], d["id"] = d["id"], i
            genbrug.append(d)
        else:
            mangler.append(i)
    json.dump(univers, open(V2 / "univers.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    with open(V2 / "s1_genbrug.jsonl", "w", encoding="utf-8") as f:
        for d in genbrug:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (V2 / "s1_mangler.txt").write_text("\n".join(mangler), encoding="utf-8")
    grupper = {}
    for u in univers.values():
        grupper[u["gruppe"]] = grupper.get(u["gruppe"], 0) + 1
    print(f"univers {len(univers)} {grupper}; genbrug trin 1: {len(genbrug)}; nye: {len(mangler)}")


if __name__ == "__main__":
    main()

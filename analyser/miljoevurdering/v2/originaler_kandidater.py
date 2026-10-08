"""Kandidatliste til høst af kommunernes oprindelige screeninger.

    python analyser/miljoevurdering/v2/originaler_kandidater.py

Alle screeningssager (projekt og plan) fra 2020+, som nævnet behandlede på indholdet,
både underkendte og stadfæstede. For hver sag udtrækkes myndighed, plannummer,
datoen for myndighedens afgørelse og en kort beskrivelse fra nævnets indledning.
Output: v2/originaler_kandidater.json
"""
import json
import re
from pathlib import Path

V2 = Path(__file__).resolve().parent
MDR = {m: i for i, m in enumerate(["januar", "februar", "marts", "april", "maj", "juni", "juli", "august",
                                   "september", "oktober", "november", "december"], 1)}


def dato(t: str) -> str | None:
    m = re.search(r"(\d{1,2})\.\s*(" + "|".join(MDR) + r")\s+(\d{4})", t)
    return f"{m.group(3)}-{MDR[m.group(2)]:02d}-{int(m.group(1)):02d}" if m else None


def main():
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    s1 = [json.loads(l) for l in open(V2 / "s1_genbrug.jsonl", encoding="utf-8")]
    for f in sorted((V2 / "s1_ny").glob("*.jsonl")):
        s1 += [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    ud = []
    for d in s1:
        if d["id"] not in u or not d.get("behandlet_paa_indhold"):
            continue
        if d.get("afgoerelsestype") not in ("screening_projekt", "screening_plan"):
            continue
        meta = u[d["id"]]
        p = V2 / "sager" / f"{d['id']}.txt"
        tekst = p.read_text(encoding="utf-8") if p.exists() else ""
        intro = tekst.split("=== INDLEDNING ===", 1)[-1][:2500]
        titel = meta["titel"]
        myn = re.search(r"([A-ZÆØÅ][\wæøå\-]+(?:-[A-ZÆØÅ][\wæøå]+)? (Kommune|Regionsråd|Region \w+))", titel + " " + intro)
        plan = re.findall(r"(lokalplan(?:forslag)?|kommuneplantillæg|tillæg)\s+(?:nr\.\s*)?([\w./\-]+\d[\w./\-]*)", titel + " " + intro, re.I)
        afg_dato = None
        for rx in (r"(?:afgørelse|beslutning|screeningsafgørelse) af (\d{1,2}\.\s*\w+\s+\d{4})",
                   r"(?:traf|gav|meddelte|vedtog|besluttede)[^.]{0,60}?den\s+(\d{1,2}\.\s*\w+\s+\d{4})",
                   r"den\s+(\d{1,2}\.\s*\w+\s+\d{4})[^.]{0,80}afgørelse"):
            m = re.search(rx, intro)
            if m and dato(m.group(1)):
                afg_dato = dato(m.group(1))
                break
        # Hvad screeningen handlede om: "afgørelse af <dato> om, at <OBJEKT> ikke ..."
        m = re.search(r"om,? at (.{8,260}?) (?:ikke (?:er omfattet|skal)|ikke miljøvurderingspligt|skal miljøvurderes)", intro)
        objekt = re.sub(r"\s+", " ", m.group(1)) if m else ""
        fredning = bool(re.search(r"Fredningsnævnet", intro))
        ud.append({"id": d["id"], "naevn": meta["naevn"], "type": d["afgoerelsestype"],
                   "udfald": "medhold" if d.get("klager_medhold") else "ikke_medhold",
                   "naevn_dato": meta["dato"], "myndighed": myn.group(1) if myn else None,
                   "planer": [f"{a} {b}".strip() for a, b in plan][:3], "afgoerelse_dato": afg_dato,
                   "titel": titel, "link": meta["link"], "objekt": objekt, "fredningsnaevn": fredning,
                   "indledning": re.sub(r"\s+", " ", intro.split("Indhold")[0])[:700]})
    ud.sort(key=lambda x: x["naevn_dato"], reverse=True)
    (V2 / "originaler_kandidater.json").write_text(json.dumps(ud, ensure_ascii=False, indent=1), encoding="utf-8")
    import collections
    print(len(ud), collections.Counter((x["type"], x["udfald"]) for x in ud))
    print("uden myndighed:", sum(1 for x in ud if not x["myndighed"]), "uden dato:", sum(1 for x in ud if not x["afgoerelse_dato"]))
    print(collections.Counter(x["myndighed"] for x in ud).most_common(15))


if __name__ == "__main__":
    main()

"""Kontrollér trin 1- og trin 2-output: gyldige værdier og ordrette citater.

    python analyser/miljoevurdering/v2/kontroller.py

Skriver v2/kontrol.json med fejl pr. fil og sætter feltet "citat_ok" på hver fejl i
deep_v2.jsonl (samlet fil). Citater, der ikke findes i sagsfilen, markeres – de
bruges ikke som eksempler i tjeklisten.
"""
import glob
import json
import sys
from pathlib import Path

V2 = Path(__file__).resolve().parent
sys.path.insert(0, str(V2.parents[2]))
from miljoejurist import citatkontrol as C  # noqa: E402

KAT = {"omfattet_bilag_projektbegreb", "afgraensning_opsplitning", "screeningskriterier_ikke_vurderet",
       "kumulation", "sagsoplysning_dokumentation", "natura2000_vaesentlighed", "bilagIV_arter",
       "natur_paragraf3", "afvaergeforanstaltninger", "materiel_vaesentlighed", "begrundelse",
       "miljoerapport_mangelfuld", "hoering_inddragelse", "vilkaar", "kompetence_procedure",
       "plan_forhold", "andet"}


def sag(i: str) -> str:
    p = V2 / "sager" / f"{i}.txt"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def læs(mønster: str) -> list[dict]:
    ud = []
    for f in sorted(glob.glob(str(V2 / mønster))):
        for n, line in enumerate(open(f, encoding="utf-8"), 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                d["_fil"] = Path(f).name
                ud.append(d)
            except json.JSONDecodeError:
                print(f"ugyldig JSON: {f}:{n}")
    return ud


def main():
    rapport = {"trin1": {}, "trin2": {}}
    s1 = læs("s1_ny/*.jsonl")
    s1_ok = [d for d in s1 if C.find(d.get("citat", ""), sag(d["id"]))]
    rapport["trin1"] = {"sager": len(s1), "citat_ok": len(s1_ok)}

    deep = læs("deep/*.jsonl")
    seen, samlet = set(), []
    n_fejl = n_ok_n = n_ok_m = n_m = n_badkat = 0
    for d in deep:
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        tekst = sag(d["id"])
        for f in d.get("fejl") or []:
            n_fejl += 1
            f["citat_naevn_ok"] = C.find(f.get("citat_naevn") or "", tekst)
            n_ok_n += f["citat_naevn_ok"]
            if f.get("citat_myndighed"):
                n_m += 1
                f["citat_myndighed_ok"] = C.find(f["citat_myndighed"], tekst)
                n_ok_m += f["citat_myndighed_ok"]
            if f.get("fejlkategori") not in KAT:
                n_badkat += 1
        d.pop("_fil", None)
        samlet.append(d)
    rapport["trin2"] = {"sager": len(samlet), "fejl": n_fejl, "citat_naevn_ok": n_ok_n,
                        "citat_myndighed": n_m, "citat_myndighed_ok": n_ok_m, "ukendt_kategori": n_badkat}
    with open(V2 / "deep_v2.jsonl", "w", encoding="utf-8") as f:
        for d in samlet:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (V2 / "kontrol.json").write_text(json.dumps(rapport, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rapport, ensure_ascii=False))


if __name__ == "__main__":
    main()

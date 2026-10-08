"""Byg tjeklisten og praksisdata til screeningstjekket.

    python -m miljoejurist.byg_tjekliste        (fra ejnar/)

Input:  analyser/miljoevurdering/v2/deep_v2.jsonl (trin 2, kontrollerede citater)
        analyser/miljoevurdering/v2/univers.json
        lovgrundlag/ (via lovkilder)
Output: ejnar/miljoejurist/data/praksis.json   – underkendte sager med kontrollerede citater
        ejnar/miljoejurist/data/tjekliste.json – grundpunkter + hyppighed, eksempler og vejledning
        analyser/TJEKLISTE.md                   – læsbar tjekliste med eksempler og links
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

from . import citatkontrol, lovkilder
from .tjekliste_grund import PUNKTER

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
V2 = REPO / "analyser" / "miljoevurdering" / "v2"
DATA = HER / "data"

DOKTYPER = {"screening_projekt": "Screening af projekt", "screening_plan": "Screening af plan",
            "miljoerapport_plan": "Miljørapport (plan)", "projekttilladelse": "§ 25-tilladelse",
            "husdyrgodkendelse": "Husdyrgodkendelse", "andet": "Andet"}

# Håndvalgte vejledningsafsnit pr. punkt: (kilde, afsnitsnummer)
P, V, H = "vejl_mv_projekter", "vejl_mv_planer", "habitatvejl"
VEJL_AFSNIT = {
    "A1": [(P, "3.2.")], "A2": [(P, "3.4.")], "A3": [(V, "4.3.2.")],
    "B1": [(P, "4.5.1."), (V, "4.3.2.")], "B2": [(P, "5.1.3."), (V, "5.1.3.")],
    "C1": [(P, "4.5.2.1.")], "C2": [(V, "4.3.3.")], "C3": [(P, "4.5.2.1."), (V, "4.2.4.4.")],
    "C4": [(P, "4.5.2.1."), (V, "4.3.3.2.")], "C5": [(P, "4.5.2.1."), (V, "4.3.3.2.")],
    "C6": [(P, "4.5.2.1."), (V, "4.3.3.2.")],
    "D1": [(H, "4.6.2"), (H, "4.6.1")], "D2": [(H, "9.6.3"), (H, "9.6.5")], "D3": [(P, "4.5.2.1."), (V, "4.3.3.2.")],
    "E1": [(P, "4.5.3."), (V, "4.3.4.1.")], "E2": [(P, "4.5.3.2."), (V, "4.3.4.1.")],
    "E3": [(P, "4.5.5."), (V, "4.3.4.")], "F1": [(V, "4.2.4.6.")], "G1": [(P, "4.4.5.")],
}

_VEJL = {"screening_projekt": "vejl_mv_projekter", "projekttilladelse": "vejl_mv_projekter",
         "screening_plan": "vejl_mv_planer", "miljoerapport_plan": "vejl_mv_planer"}


def byg_praksis() -> list[dict]:
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    ud = []
    for line in open(V2 / "deep_v2.jsonl", encoding="utf-8"):
        d = json.loads(line)
        if not d.get("brugbar"):
            continue
        meta = u.get(d["id"])
        if not meta:
            continue
        fejl = [{k: f.get(k) for k in ("fejl", "fejlkategori", "regel", "citat_naevn", "citat_myndighed",
                                       "tjekpunkt", "afgoerende", "kunne_fanges_af_tjekliste")}
                for f in d.get("fejl") or [] if f.get("citat_naevn_ok")]
        for f in fejl:
            if not next((x for x in d["fejl"] if x.get("citat_naevn") == f["citat_naevn"]), {}).get("citat_myndighed_ok"):
                f["citat_myndighed"] = None
        if not fejl:
            continue
        ud.append({"id": d["id"], "naevn": meta["naevn"], "dato": meta["dato"], "titel": meta["titel"],
                   "link": meta["link"], "dokumenttype": d.get("dokumenttype"), "projekttype": d.get("projekttype"),
                   "resume": d.get("resume", ""), "eu_domme": d.get("eu_domme") or [], "fejl": fejl})
    ud.sort(key=lambda s: s["dato"], reverse=True)
    return ud


def _bedste_sætning(tekst: str, q: str) -> str:
    from .bm25 import tokens
    qt = set(tokens(q))
    sæt = [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-ZÆØÅ])|\n+", tekst)
           if 60 < len(s.strip()) < 700 and not re.match(r"^(MFKN|NMKN|NKN|PKN|Retten|Højesteret|EU-Domstolen)", s.strip())]
    if not sæt:
        return tekst[:500]
    return max(sæt, key=lambda s: len(qt & set(tokens(s))))


def byg():
    DATA.mkdir(exist_ok=True)
    praksis = byg_praksis()
    (DATA / "praksis.json").write_text(json.dumps(praksis, ensure_ascii=False, indent=0), encoding="utf-8")

    pr_kat = collections.defaultdict(list)
    for s in praksis:
        for kat in {f["fejlkategori"] for f in s["fejl"]}:
            pr_kat[kat].append(s)
    n_sager = len(praksis)

    punkter = []
    for p in PUNKTER:
        p = dict(p)
        relevante = [s for kat in p["fejlkategorier"] for s in pr_kat.get(kat, [])
                     if s.get("dokumenttype") in p["gælder"]]
        if p.get("emne"):
            rx = re.compile(p["emne"], re.I)
            relevante = [s for s in relevante if any(f["fejlkategori"] in p["fejlkategorier"] and
                         rx.search(f"{f['fejl']} {f['citat_naevn']}") for f in s["fejl"])]
        ids = list(dict.fromkeys(s["id"] for s in relevante))
        p["praksis_antal"] = len(ids)
        # Eksempler: nyeste sager med en afgørende fejl i kategorien
        eks = []
        for s in sorted({s["id"]: s for s in relevante}.values(), key=lambda s: s["dato"], reverse=True):
            f = next((f for f in s["fejl"] if f["fejlkategori"] in p["fejlkategorier"] and
                      (not p.get("emne") or re.search(p["emne"], f"{f['fejl']} {f['citat_naevn']}", re.I))), None)
            if f:
                eks.append({"id": s["id"], "naevn": s["naevn"], "dato": s["dato"], "titel": s["titel"],
                            "link": s["link"], "fejl": f["fejl"], "citat": f["citat_naevn"],
                            "citat_myndighed": f.get("citat_myndighed")})
            if len(eks) >= 4:
                break
        p["eksempler"] = eks
        # Lovuddrag skal stå ordret
        lov_ok = []
        for kode, nr, uddrag in p["lov"]:
            st = lovkilder.slå_op(kode, nr)
            lov_ok.append({"kode": kode, "nr": nr, "uddrag": uddrag, "ref": st.ref if st else None,
                           "url": st.url if st else None, "ok": bool(st and citatkontrol.find(uddrag, st.tekst))})
        p["lov_kontrol"] = lov_ok
        # Vejledning: håndvalgt afsnit; bedste sætning ud fra punktets søgeord
        vejl = []
        for kode, nr in VEJL_AFSNIT.get(p["id"], []):
            stykker = [s for s in lovkilder.alle() if s.kilde == kode and f"afsnit {nr} " in s.ref + " "]
            if not stykker:
                continue
            tekst = "\n\n".join(s.tekst for s in stykker)
            c = _bedste_sætning(tekst, p["vejl_søg"] + " " + p["spørgsmål"])
            st = next(s for s in stykker if citatkontrol.find(c, s.tekst) or s is stykker[-1])
            if citatkontrol.find(c, st.tekst):
                vejl.append({"kode": kode, "ref": st.ref.split(" (")[0], "url": st.url, "citat": c})
        p["vejl_citat"] = vejl
        punkter.append(p)

    andel = {kat: len(v) for kat, v in sorted(pr_kat.items(), key=lambda x: -len(x[1]))}
    pr_type = collections.Counter(s.get("dokumenttype") for s in praksis)
    meta = {"sager_med_kontrollerede_fejl": n_sager, "kategorier": andel, "dokumenttyper": dict(pr_type)}
    (DATA / "tjekliste.json").write_text(json.dumps({"meta": meta, "punkter": punkter}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    skriv_markdown(punkter, meta)
    print(json.dumps(meta, ensure_ascii=False))


def skriv_markdown(punkter: list[dict], meta: dict):
    ud = ["# Tjekliste: screeninger, miljørapporter og VVM-tilladelser", "",
          "Bygget automatisk af `ejnar/miljoejurist/byg_tjekliste.py` ud fra miljøvurderingsloven, "
          "habitatbekendtgørelserne, vejledningerne og nævnenes underkendelser (trin 2-analysen i "
          "`analyser/miljoevurdering/v2/`). Alle citater fra lov, vejledning og afgørelser er kontrolleret "
          "maskinelt for, at de står ordret i kilden.", "",
          f"**Grundlag:** {meta['sager_med_kontrollerede_fejl']} sager fra 2020–2026, hvor PKN eller MFKN helt "
          "eller delvist gav klager medhold, og hvor nævnets begrundelse kunne citeres ordret.", "",
          "**Skal gennemgås af en fagperson før brug.** Tjeklisten er et arbejdsredskab; den erstatter ikke "
          "en juridisk vurdering, og at alle punkter er besvaret, betyder ikke, at en afgørelse holder.", "",
          "## Hyppigste fejltyper i underkendte sager", "", "| Fejlkategori | Sager |", "|---|---|"]
    ud += [f"| {k} | {v} |" for k, v in meta["kategorier"].items()]
    ud.append("")
    gruppe = None
    for p in sorted(punkter, key=lambda p: p["id"]):
        if p["gruppe"] != gruppe:
            gruppe = p["gruppe"]
            ud += [f"## {gruppe}", ""]
        ud.append(f"### {p['id']}. {p['titel']}")
        ud.append(f"**Spørgsmål:** {p['spørgsmål']}  ")
        ud.append(f"**Gælder:** {', '.join(DOKTYPER.get(t, t) for t in p['gælder'])}  ")
        ud.append(f"**Underkendt i praksis:** {p['praksis_antal']} sager (kategori: {', '.join(p['fejlkategorier'])})")
        ud.append("")
        ud.append("**Lovgrundlag:**")
        for lk in p["lov_kontrol"]:
            mærke = "" if lk["ok"] else " ⚠ (uddraget kunne ikke genfindes ordret)"
            ud.append(f"- [{lk['ref']}]({lk['url']}): «{lk['uddrag']}»{mærke}")
        if p["vejl_citat"]:
            ud.append("\n**Vejledning:**")
            for v in p["vejl_citat"]:
                ud.append(f"- [{v['ref']}]({v['url']}): «{v['citat']}»")
        if p["eksempler"]:
            ud.append("\n**Eksempler fra nævnene:**")
            for e in p["eksempler"]:
                ud.append(f"- [{e['naevn']} {e['dato']}]({e['link']}) – {e['fejl']}  \n  Nævnet: «{e['citat']}»")
                if e.get("citat_myndighed"):
                    ud.append(f"  Myndigheden havde skrevet: «{e['citat_myndighed']}»")
        ud.append("")
    (REPO / "analyser" / "TJEKLISTE.md").write_text("\n".join(ud), encoding="utf-8")


if __name__ == "__main__":
    byg()

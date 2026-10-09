"""Byg data/praksis_holdt.json: hvad nævnet fandt tilstrækkeligt i stadfæstede sager (kontrasteksempler).

    python -m miljoejurist.byg_holdt

Kilde: analyser/miljoevurdering/v2/holdt/out_*.jsonl (Haiku-udtræk efter PROMPT_TRIN2_HOLDT.md).
Kun punkter, hvor nævnets citat findes ordret i afgørelsen, kommer med.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from . import citatkontrol

HER = Path(__file__).resolve().parent
REPO = HER.parent
V2 = REPO / "analyser" / "miljoevurdering" / "v2"


def main():
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    sager, n_ok, n_alle = [], 0, 0
    set_ = set()
    for f in sorted(glob.glob(str(V2 / "holdt" / "out_*.jsonl"))):
        for linje in open(f, encoding="utf-8"):
            linje = linje.strip()
            if not linje:
                continue
            try:
                d = json.loads(linje)
            except json.JSONDecodeError:
                continue
            sid = d.get("id")
            if not sid or sid in set_ or sid not in u:
                continue
            p = V2 / "sager" / f"{sid}.txt"
            tekst = p.read_text(encoding="utf-8") if p.exists() else ""
            holdt = []
            for h in d.get("holdt") or []:
                n_alle += 1
                c = (h.get("citat_naevn") or "").strip()
                if not c or not citatkontrol.find(c, tekst) or h.get("tjekpunkt") in (None, "X"):
                    continue
                n_ok += 1
                holdt.append({k: h.get(k) for k in ("tjekpunkt", "klagepunkt", "myndigheden_gjorde",
                                                     "hvorfor_tilstraekkeligt", "citat_naevn")})
            if holdt:
                set_.add(sid)
                x = u[sid]
                sager.append({"id": sid, "naevn": x["naevn"], "dato": x["dato"], "titel": x["titel"], "link": x["link"],
                              "dokumenttype": d.get("dokumenttype"), "projekttype": d.get("projekttype"),
                              "resume": d.get("resume", ""), "holdt": holdt})
    sager.sort(key=lambda s: s["dato"], reverse=True)
    (HER / "data" / "praksis_holdt.json").write_text(json.dumps(sager, ensure_ascii=False, indent=1),
                                                     encoding="utf-8", newline="\n")
    print(f"{len(sager)} stadfæstede sager, {n_ok}/{n_alle} punkter med kontrolleret citat")


if __name__ == "__main__":
    main()

"""Audit v1: kør Miljøjuristen (regler + modellag) på audit-sættet og opgør resultaterne.

    python miljoejurist/evaluation/koer_audit.py prompts   # work/audit/prompt/A_xx.md (+ nævnets vurdering til revisor)
    python miljoejurist/evaluation/koer_audit.py flet      # svar/A_xx.json -> rapport/A_xx.md og .json
    python miljoejurist/evaluation/koer_audit.py score     # revision/A_xx.json -> audit_resultat.json + tabel

Modellaget spilles af en agent (Haiku), der får præcis den prompt, siden sender, plus et ekstra felt med et
udfaldsgæt (kun i audit). Sagens egen afgørelse udelukkes fra praksissøgningen.
"""
import json
import sys
from pathlib import Path

HER = Path(__file__).resolve().parent
REPO = HER.parents[1]
sys.path.insert(0, str(REPO))
from miljoejurist import corpus, dokument, llm_tjek, tjek  # noqa: E402

UD = HER / "work" / "audit"
FACIT = json.loads((HER / "audit_facit.json").read_text(encoding="utf-8"))
V2 = REPO / "analyser" / "miljoevurdering" / "v2"

RISIKO = """

TILLÆG (kun til evaluering): Tilføj i JSON-svaret feltet
"risiko": {"sandsynlighed_underkendelse": <heltal 0-100>, "hovedgrund": "1 sætning"}
= din vurdering af sandsynligheden for, at klagenævnet ville ophæve/underkende afgørelsen, hvis den blev påklaget.
Til orientering: nævnene giver helt eller delvist medhold i ca. 30 % af de screeningssager, de behandler på indholdet."""


def _dok(aid):
    return dokument.fra_tekst((UD / "dok" / f"{aid}.txt").read_text(encoding="utf-8"), aid)


def prompts():
    for d in ("prompt", "vurdering", "regler"):
        (UD / d).mkdir(exist_ok=True)
    for aid, f in FACIT.items():
        if not (UD / "dok" / f"{aid}.txt").exists():
            print("mangler dok", aid)
            continue
        d = _dok(aid)
        r = tjek.tjek_regler(d, dtype=f["dokumenttype"], udeluk={f["sag"]})
        (UD / "regler" / f"{aid}.json").write_text(json.dumps(r.to_json(), ensure_ascii=False), encoding="utf-8")
        (UD / "prompt" / f"{aid}.md").write_text(llm_tjek.byg_prompt(d, r, {f["sag"]}) + RISIKO, encoding="utf-8")
        t = (V2 / "sager" / f"{f['sag']}.txt").read_text(encoding="utf-8")
        (UD / "vurdering" / f"{aid}.txt").write_text(corpus.nævnets_vurdering(t)[:15000], encoding="utf-8")
    print("prompts:", len(list((UD / "prompt").glob("*.md"))))


def flet():
    (UD / "rapport").mkdir(exist_ok=True)
    for aid, f in FACIT.items():
        p = UD / "svar" / f"{aid}.json"
        if not p.exists():
            print("mangler svar", aid)
            continue
        svar = p.read_text(encoding="utf-8")
        d = _dok(aid)
        r = tjek.tjek_regler(d, dtype=f["dokumenttype"], udeluk={f["sag"]})
        r = llm_tjek.supplér(r, d, None, {f["sag"]}, svar=svar)
        j = r.to_json()
        j["risiko"] = llm_tjek.fortolk(svar).get("risiko")
        (UD / "rapport" / f"{aid}.json").write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
        linjer = [f"# {aid}: rapport ({len(r.svagheder)} fund)", ""]
        for i, s in enumerate(r.svagheder, 1):
            linjer += [f"{i}. [{s.niveau}] {s.punkt} {s.titel}: {s.svaghed}",
                       f"   Citat: «{s.citat_dokument or '-'}»", f"   Hvorfor: {s.hvorfor or '-'}", ""]
        (UD / "rapport" / f"{aid}.md").write_text("\n".join(linjer), encoding="utf-8")
    print("rapporter:", len(list((UD / "rapport").glob("*.json"))))


def _auc(pos, neg):
    if not pos or not neg:
        return None
    return sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))


def score():
    rows = []
    for aid, f in FACIT.items():
        rp, rv = UD / "rapport" / f"{aid}.json", UD / "revision" / f"{aid}.json"
        if not rp.exists() or not rv.exists():
            continue
        rap, rev = json.loads(rp.read_text(encoding="utf-8")), json.loads(rv.read_text(encoding="utf-8"))
        regler = json.loads((UD / "regler" / f"{aid}.json").read_text(encoding="utf-8"))
        fund = rev.get("fund") or []
        svag = [x for x in fund if x.get("niveau", "svaghed") == "svaghed"]
        risiko = (rap.get("risiko") or {}).get("sandsynlighed_underkendelse")
        rows.append({"aid": aid, "sag": f["sag"], "gruppe": f["gruppe"], "type": f["dokumenttype"],
                     "fanget": rev.get("fanget"), "fanget_nr": rev.get("fanget_nr"),
                     "n_fund": len(rap["svagheder"]), "n_svag": sum(s["niveau"] == "svaghed" for s in rap["svagheder"]),
                     "n_høj": sum(1 for s in rap["svagheder"] if s.get("vægt", 0) >= 3),
                     "relevante": sum(x.get("vurdering") == "relevant" for x in svag),
                     "tvivlsomme": sum(x.get("vurdering") == "tvivlsom" for x in svag),
                     "forkerte": sum(x.get("vurdering") == "forkert" for x in svag),
                     "risiko": risiko, "regler_n": len(regler["svagheder"]),
                     "revisor_udfald": rev.get("revisor_ville_ophæve")})
    (HER / "audit_resultat.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    oph = [r for r in rows if r["gruppe"] == "ophævet"]
    sta = [r for r in rows if r["gruppe"] == "stadfæstet"]
    print(f"Sager: {len(rows)} ({len(oph)} ophævede, {len(sta)} stadfæstede)")
    for v in ("ja", "delvist", "nej"):
        print(f"  ophævede, nævnets afgørende fejl fanget = {v}: {sum(r['fanget'] == v for r in oph)}")
    top = sum(1 for r in oph if r["fanget"] in ("ja", "delvist") and (r["fanget_nr"] or 99) <= 3)
    print(f"  heraf blandt de 3 første fund: {top}")
    for navn, g in (("ophævede", oph), ("stadfæstede", sta)):
        s = sum(r["n_svag"] for r in g) or 1
        print(f"  {navn}: svagheder pr. sag {sum(r['n_svag'] for r in g)/max(len(g),1):.1f}; relevante "
              f"{sum(r['relevante'] for r in g)/s:.0%}, tvivlsomme {sum(r['tvivlsomme'] for r in g)/s:.0%}, "
              f"forkerte {sum(r['forkerte'] for r in g)/s:.0%}")
    rp = [r["risiko"] for r in oph if r["risiko"] is not None]
    rs = [r["risiko"] for r in sta if r["risiko"] is not None]
    if rp and rs:
        print(f"  udfaldsgæt: gns. risiko ophævede {sum(rp)/len(rp):.0f} %, stadfæstede {sum(rs)/len(rs):.0f} %, AUC {_auc(rp, rs):.2f}")
        for t in (30, 50, 70):
            korrekt = sum(x >= t for x in rp) + sum(x < t for x in rs)
            print(f"    tærskel {t} %: {korrekt}/{len(rp)+len(rs)} rigtige ({sum(x>=t for x in rp)}/{len(rp)} ophævede, "
                  f"{sum(x<t for x in rs)}/{len(rs)} stadfæstede)")
    for navn, key in (("antal svagheder", "n_svag"), ("høj vægt", "n_høj"), ("regler", "regler_n")):
        print(f"  AUC {navn}: {_auc([r[key] for r in oph], [r[key] for r in sta]):.2f}")


if __name__ == "__main__":
    {"prompts": prompts, "flet": flet, "score": score}[sys.argv[1]]()

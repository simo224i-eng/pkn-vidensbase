"""Opsummér trin 1 og trin 2 (v2) til RESULTAT.md.

    python analyser/miljoevurdering/v2/opsummer.py
"""
import collections
import json
from pathlib import Path

V2 = Path(__file__).resolve().parent
V1 = V2.parent


def læs_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def pct(a, b):
    return f"{100 * a / b:.0f} %" if b else "–"


def main():
    u = json.loads((V2 / "univers.json").read_text(encoding="utf-8"))
    s1 = læs_jsonl(V2 / "s1_genbrug.jsonl")
    for f in sorted((V2 / "s1_ny").glob("*.jsonl")):
        s1 += læs_jsonl(f)
    s1 = {d["id"]: d for d in s1 if d["id"] in u}
    deep = {d["id"]: d for d in læs_jsonl(V2 / "deep_v2.jsonl")}

    ud = ["# Miljøvurdering: underkendelser i PKN og MFKN (v2, fuld vurdering)", "",
          "Genereret af `opsummer.py`. Grundlag: alle afgørelser fra 1/1 2020 til 8/10 2026 i PKN-kategorierne "
          "*Miljøvurderingsloven* og *Planloven, VVM* og MFKN-kategorierne *Miljøvurdering af konkrete projekter* "
          "og *Miljøvurdering af planer og programmer*, plus husdyrbrugsager med medhold fra 2022, hvor nævnets "
          "vurdering handler om Natura 2000, bilag IV eller § 3-natur.", ""]

    # Trin 1
    grupper = collections.Counter(u[i]["gruppe"] for i in s1)
    indhold = [d for d in s1.values() if d["behandlet_paa_indhold"] and u[d["id"]]["gruppe"] == "miljoevurdering"]
    med = [d for d in indhold if d["klager_medhold"]]
    ud += ["## Trin 1: udfald", "",
           f"- Sager i alt: {len(s1)} ({grupper['miljoevurdering']} miljøvurdering, {grupper['husdyr']} husdyr).",
           f"- Miljøvurderingssager behandlet på indholdet: {len(indhold)}; klager fik helt eller delvist medhold i "
           f"{len(med)} ({pct(len(med), len(indhold))}).", "",
           "| Afgørelsestype | Behandlet på indholdet | Medhold | Andel |", "|---|---|---|---|"]
    for t in ("screening_projekt", "screening_plan", "miljoerapport_plan", "projekttilladelse", "andet"):
        a = [d for d in indhold if d["afgoerelsestype"] == t]
        m = [d for d in a if d["klager_medhold"]]
        ud.append(f"| {t} | {len(a)} | {len(m)} | {pct(len(m), len(a))} |")
    ud += ["", "| Nævn | Behandlet på indholdet | Medhold | Andel |", "|---|---|---|---|"]
    for n in ("PKN", "MFKN"):
        a = [d for d in indhold if u[d["id"]]["naevn"] == n]
        m = [d for d in a if d["klager_medhold"]]
        ud.append(f"| {n} | {len(a)} | {len(m)} | {pct(len(m), len(a))} |")
    ud += ["", "| År | Behandlet på indholdet | Medhold | Andel |", "|---|---|---|---|"]
    for år in sorted({u[d["id"]]["dato"][:4] for d in indhold}):
        a = [d for d in indhold if u[d["id"]]["dato"].startswith(år)]
        m = [d for d in a if d["klager_medhold"]]
        ud.append(f"| {år} | {len(a)} | {len(m)} | {pct(len(m), len(a))} |")

    # Trin 2
    brugbar = [d for d in deep.values() if d.get("brugbar")]
    ikke = [d for d in deep.values() if not d.get("brugbar")]
    alle_fejl = [(d, f) for d in brugbar for f in d.get("fejl") or []]
    ud += ["", "## Trin 2: hvad underkendte nævnet?", "",
           f"- Sager med medhold analyseret: {len(deep)}. Brugbare (nævnet underkendte noget indholdsmæssigt): "
           f"{len(brugbar)}. Ikke brugbare: {len(ikke)} (typisk ophævet som uaktuel, inhabilitet eller kun "
           "opsættende virkning).",
           f"- Fejl i alt: {len(alle_fejl)} (gennemsnit {len(alle_fejl) / max(1, len(brugbar)):.1f} pr. sag). "
           f"Afgørende fejl: {sum(1 for _, f in alle_fejl if f.get('afgoerende'))}.",
           f"- Alle {len(alle_fejl)} citater fra nævnets vurdering er maskinelt kontrolleret som ordrette "
           f"({sum(1 for _, f in alle_fejl if f.get('citat_naevn_ok'))} ok). Citater af myndighedens egen tekst: "
           f"{sum(1 for _, f in alle_fejl if f.get('citat_myndighed'))}.",
           "- Til forskel fra v1 er hele nævnets vurdering læst (v1 brugte de første 9.000 tegn, og 87 af 202 sager "
           "var derfor ubrugelige).", "",
           "### Fejlkategorier (antal sager, hvor kategorien forekommer)", "",
           "| Kategori | Sager | heraf afgørende | Screening projekt | Screening plan | Miljørapport | § 25-tilladelse | Husdyr |",
           "|---|---|---|---|---|---|---|---|"]
    kat = collections.defaultdict(lambda: collections.Counter())
    for d in brugbar:
        set_ = {}
        for f in d.get("fejl") or []:
            k = f["fejlkategori"]
            set_[k] = set_.get(k, False) or bool(f.get("afgoerende"))
        for k, afg in set_.items():
            kat[k]["i_alt"] += 1
            kat[k]["afg"] += afg
            kat[k][d.get("dokumenttype") or "andet"] += 1
    for k, c in sorted(kat.items(), key=lambda x: -x[1]["i_alt"]):
        ud.append(f"| {k} | {c['i_alt']} | {c['afg']} | {c['screening_projekt']} | {c['screening_plan']} | "
                  f"{c['miljoerapport_plan']} | {c['projekttilladelse']} | {c['husdyrgodkendelse']} |")
    tj = collections.Counter(f.get("kunne_fanges_af_tjekliste") for _, f in alle_fejl)
    ud += ["", "### Kunne en tjekliste have fanget fejlen?", "",
           f"Modellens vurdering pr. fejl: ja {tj['ja']}, delvist {tj['delvist']}, nej {tj['nej']}. "
           "Det er en modelvurdering og skal tages med forbehold; en fagperson bør se på stikprøver.", "",
           "### Hyppigste regler, nævnet henviser til", ""]
    regler = collections.Counter()
    import re
    for _, f in alle_fejl:
        for m in re.findall(r"(miljøvurderingslovens § \d+|habitatbekendtgørelsens § \d+|bilag [36]|"
                            r"planhabitatbekendtgørelsens § \d+|husdyrbruglovens § \d+)", f.get("regel") or "", re.I):
            regler[m.lower()] += 1
    ud += [f"- {r}: {n}" for r, n in regler.most_common(15)]
    eu = collections.Counter(c for d in brugbar for c in d.get("eu_domme") or [])
    ud += ["", "### EU-domme citeret i de underkendte sager", ""] + [f"- {c}: {n}" for c, n in eu.most_common(15)]

    # Sammenligning med v1
    ud += ["", "## Sammenligning med v1", "",
           "| | v1 (9.000 tegn) | v2 (fuld vurdering) |", "|---|---|---|",
           f"| Sager med medhold | 202 | {len(deep)} |",
           f"| Brugbare | 115 | {len(brugbar)} |",
           f"| Fejl i alt | 115 (én pr. sag) | {len(alle_fejl)} |",
           "| Citatkontrol | delvis | alle citater maskinkontrolleret |", ""]
    (V2 / "RESULTAT.md").write_text("\n".join(ud), encoding="utf-8")
    print("\n".join(ud[:60]))


if __name__ == "__main__":
    main()

"""
Hent lovgrundlaget for miljøvurdering fra retsinformation.dk (XML via ELI) og
gem det som ren tekst i lovgrundlag/.

    python fetch_lovgrundlag.py

Hver kilde gemmes som lovgrundlag/<kode>.txt plus en fælles lovgrundlag/index.json
med titel, ELI-link og status. Paragraffer står på egen linje som "§ 21. ..." og
stykker som "Stk. 2. ...". Fede enkeltlinjer (vejledningernes overskrifter) bliver
"## "-overskrifter, og fodnoter flyttes til "## Noter" sidst, så sætninger ikke
brydes af notetekst (vigtigt for citatkontrollen).

Bilag IV-materialet fra Miljøstyrelsen/DCE er PDF'er og hentes ikke her; deres
poster i index.json bevares.
"""

import json
import re
import time
from pathlib import Path

import requests
from lxml import etree

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "lovgrundlag"
RI = "https://www.retsinformation.dk"

KILDER = [
    # kode, ELI, kort navn
    ("mvl", "/eli/lta/2023/4", "Miljøvurderingsloven (LBK nr. 4 af 3/1/2023)"),
    ("mvl_bilag2_aendring_2025", "/eli/lta/2025/1375", "BEK nr. 1375 af 25/11/2025 om ændring af bilag 2 til miljøvurderingsloven"),
    ("mvb", "/eli/lta/2024/1608", "Miljøvurderingsbekendtgørelsen (BEK nr. 1608 af 9/12/2024)"),
    ("habitatbek", "/eli/lta/2023/1098", "Habitatbekendtgørelsen (BEK nr. 1098 af 21/8/2023)"),
    ("planlov", "/eli/lta/2024/572", "Planloven (LBK nr. 572 af 29/5/2024)"),
    ("planlov_habitat_bek", "/eli/lta/2016/1383", "Planhabitatbekendtgørelsen (BEK nr. 1383 af 26/11/2016)"),
    ("nbl", "/eli/lta/2024/927", "Naturbeskyttelsesloven (LBK nr. 927 af 28/6/2024)"),
    ("husdyrlov", "/eli/lta/2025/1065", "Husdyrbrugloven (LBK nr. 1065 af 21/8/2025)"),
    ("vejl_mv_projekter", "/eli/retsinfo/2024/9093", "Vejledning om miljøvurdering af konkrete projekter (VEJ nr. 9093 af 21/2/2024)"),
    ("vejl_mv_planer", "/eli/retsinfo/2024/9094", "Vejledning om miljøvurdering af planer og programmer (VEJ nr. 9094 af 21/2/2024)"),
    ("habitatvejl", "/eli/retsinfo/2020/9925", "Habitatvejledningen inkl. bilag IV-arter (VEJ nr. 9925 af 11/11/2020)"),
    ("landzonevejl", "/eli/retsinfo/2019/10076", "Landzonevejledningen (VEJ nr. 10076 af 5/6/2018)"),
    ("vejl_nbl3", "/eli/retsinfo/2019/10226", "Vejledning om naturbeskyttelseslovens § 3-beskyttede naturtyper (VEJ nr. 10226 af 19/12/2019)"),
]

BLOCK = {"Paragraf", "Stk", "Exitus", "Linea", "Tabel", "Row", "Tr", "Liste", "Indentatio",
         "Kapitel", "Afsnit", "Bilag", "Titel", "Overskrift", "Rubrica", "ExplicatusParagraf"}


def _tag(el) -> str:
    return etree.QName(el).localname if isinstance(el.tag, str) else ""


def _er_overskrift(el) -> bool:
    """En Exitus med én kort linje, der kun består af fed tekst, er en overskrift."""
    if _tag(el) != "Exitus":
        return False
    born = [c for c in el if isinstance(c.tag, str)]
    if len(born) != 1 or _tag(born[0]) != "Linea":
        return False
    chars = [c for c in born[0].iter() if _tag(c) == "Char"]
    tekst = "".join("".join(c.itertext()) for c in chars).strip()
    return bool(chars) and all(c.get("formaChar") == "Bold" for c in chars) and 0 < len(tekst) < 160


def xml_to_text(xml: bytes) -> tuple[dict, str]:
    root = etree.fromstring(xml)
    meta = {}
    m = root.find("Meta")
    if m is not None:
        for k in ("DocumentTitle", "PopularTitle", "Status", "StartDate", "EndDate", "DiesSigni", "DocumentType"):
            el = m.find(k)
            meta[k] = el.text if el is not None else None
    parts, noter = [], []

    def walk(el, out):
        tag = _tag(el)
        if tag in ("Meta", "TitelGruppe", "UnderskriftGruppe"):
            return
        if tag == "Bilag":
            nr = next(("".join(c.itertext()).strip() for c in el if _tag(c) == "Explicatus"), "Bilag")
            rub = next((re.sub(r"\s+", " ", "".join(c.itertext())).strip() for c in el if _tag(c) == "Rubrica"), "")
            out.append(f"\n## {nr}: {rub}\n")
            for c in el:
                if _tag(c) not in ("Explicatus", "Rubrica"):
                    walk(c, out)
            return
        if tag == "Nota":
            nr = next(("".join(c.itertext()).strip() for c in el if _tag(c) == "Explicatus"),
                      str(len(noter) + 1))
            sub = []
            for c in el:
                if _tag(c) != "Explicatus":
                    walk(c, sub)
            noter.append(f"[{nr}] " + re.sub(r"\s+", " ", "".join(sub)).strip())
            out.append(f" [{nr}]")
            return
        if tag == "Explicatus":
            t = "".join(el.itertext()).strip()
            if t:
                out.append("\n" + t + " ")
            return
        if _er_overskrift(el):
            out.append("\n## " + re.sub(r"\s+", " ", "".join(el.itertext())).strip() + "\n")
            return
        if tag in BLOCK:
            out.append("\n")
        if el.text:
            out.append(el.text)
        for c in el:
            walk(c, out)
            if c.tail:
                out.append(c.tail)
        if tag in BLOCK:
            out.append("\n")

    walk(root, parts)
    txt = "".join(parts)
    if noter:
        txt += "\n\n## Noter\n" + "\n".join(noter)
    txt = txt.replace("\xa0", " ")
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r" *\n *", "\n", txt)
    txt = re.sub(r"\n+ ?(\[\d+\])", r" \1", txt)              # notehenvisning tilbage på linjen
    txt = re.sub(r"(\[\d+\])\s*\n+\s*([.,;:)’])", r"\1\2", txt)  # tegnsætning efter note
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    # Nummererede vejledningsoverskrifter: "4.5.1.\n\nTitel" -> "## 4.5.1. Titel"
    txt = re.sub(r"(?m)^(\d+(?:\.\d+)+\.)\n+([^\n§]{3,160})$", r"## \1 \2", txt)
    # Saml markører med deres tekst: "§ 21.\n\nTekst" -> "§ 21. Tekst"
    txt = re.sub(r"(?m)^(§ \d+ ?[a-z]?\.|Stk\. \d+\.|\d+[a-z]?\)|[a-zæø]\))\n+(?=\S)", r"\1 ", txt)
    return meta, txt.strip()


def main():
    OUT.mkdir(exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (pkn-vidensbase)"
    gammel = []
    if (OUT / "index.json").exists():
        gammel = json.loads((OUT / "index.json").read_text(encoding="utf-8"))
    koder = {k for k, _, _ in KILDER}
    index = []
    for kode, eli, navn in KILDER:
        r = s.get(RI + eli + "/xml", timeout=60)
        r.raise_for_status()
        meta, txt = xml_to_text(r.content)
        (OUT / f"{kode}.txt").write_text(txt, encoding="utf-8")
        index.append({"kode": kode, "navn": navn, "url": RI + eli, "tegn": len(txt), **meta})
        print(f"{kode}: {len(txt):>8} tegn  {meta.get('Status')}  {(meta.get('DocumentTitle') or '')[:70]}")
        time.sleep(1)
    index += [g for g in gammel if g["kode"] not in koder]
    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()

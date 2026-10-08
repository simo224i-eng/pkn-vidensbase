"""Indlæsning, rensning og opdeling af PKN- og MFKN-afgørelser.

Kilden er data_2026/*.csv.zip (se naevn_api.py i repo-roden). Teksten har
overskrifter på egen linje med "## " foran. Afgørelserne indeholder en
indholdsfortegnelse uden "## ", så nævnets vurdering findes ved de rigtige
overskrifter og ikke ved første forekomst af ordene.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA_DIR = REPO / "data_2026"
CACHE = REPO / "data_2026" / "korpus_renset.jsonl"

MIN_TEKST = 1500  # kortere tekster er tomme sider eller pressemeddelelser

# Overskrifter, der indleder nævnets egen vurdering
VURDERING_RE = re.compile(
    r"(klagenævnets|nævnets) (vurdering|bemærkninger|afgørelse|begrundelse)|"
    r"samlet vurdering|afsluttende bemærkninger|nævnets prøvelse i den konkrete sag",
    re.I)

# Udfald læses i indledningen (før indholdsfortegnelsen) og i sidste afsnit
_MEDHOLD = re.compile(
    r"\b(ophæver|hjemviser|ophæves|hjemvises|ugyldig|ændrer (kommunens|afgørelsen|.{0,40}afgørelse)|"
    r"giver (klager(ne)?|dig|jer) (delvis )?medhold|tilsidesætter|ophævet og hjemvist|"
    r"ikke (længere )?gælder)", re.I)
_IKKE_MEDHOLD = re.compile(
    r"\b(stadfæster|stadfæstes|kan ikke give (klager(ne)?|dig|jer) medhold|giver ikke (klager(ne)?|dig|jer) medhold|"
    r"kan heller ikke give medhold|kan ikke give medhold|fortsat gælder|gælder fortsat)", re.I)
_AFVIST = re.compile(
    r"\b(afviser (at (realitets)?behandle|klagen|klagerne|sagen)|afvises|ikke klageberettiget|ikke kompetent|"
    r"kan ikke behandle klagen|behandler ikke klagen|klagen er indgivet for sent|bortfalder|bortfaldet|"
    r"som uaktuel|ikke længere aktuel|henlægger|henlagt|realitetsbehandler ikke)", re.I)
_UAKTUEL = re.compile(r"som uaktuel|ikke længere (er )?aktuel|bortfald", re.I)
_OPSAETTENDE = re.compile(r"opsættende virkning", re.I)
_DELVIS = re.compile(r"\bdelvis(t)? medhold|delvist ophæve|ophæver delvis|delvis(t)? stadfæst", re.I)


@dataclass
class Afgoerelse:
    id: str               # stabil kort id: P/M + 8 tegn af nævnets uuid
    uuid: str
    naevn: str            # PKN | MFKN
    jnr: str
    dato: str
    titel: str
    link: str
    kategorier: list[str]
    tekst: str
    udfald: str = "ukendt"   # medhold | delvis | ikke_medhold | afvist | andet | ukendt
    afkortet: bool = False
    noter: list[str] = field(default_factory=list)

    def to_json(self) -> dict:
        return self.__dict__.copy()


def _read_zip(path: Path) -> list[dict]:
    csv.field_size_limit(100_000_000)
    with zipfile.ZipFile(path) as z:
        with z.open(z.namelist()[0]) as f:
            return list(csv.DictReader(io.TextIOWrapper(f, encoding="utf-8")))


def indledning(tekst: str) -> str:
    """Teksten før indholdsfortegnelsen/første overskrift (nævnets resumé)."""
    m = re.search(r"(?m)^(Indhold|## )", tekst)
    return tekst[: m.start()] if m else tekst[:4000]


def sektioner(tekst: str) -> list[tuple[str, str]]:
    """[(overskrift, tekst)] ud fra '## '-overskrifterne. Første element er indledningen."""
    dele = re.split(r"(?m)^## (.*)$", tekst)
    ud = [("", dele[0])]
    for i in range(1, len(dele) - 1, 2):
        ud.append((dele[i].strip(), dele[i + 1]))
    return ud


def nævnets_vurdering(tekst: str) -> str:
    """Alt fra første vurderingsoverskrift og frem (inkl. underafsnit).

    Nævnet bruger "bemærkninger og afgørelse" som hovedafsnit med underafsnit
    om generelle regler, kommunens vurdering og nævnets vurdering. Hele
    hovedafsnittet tages med; falder det igennem, bruges sidste 40 %."""
    secs = sektioner(tekst)
    for i, (h, _) in enumerate(secs):
        if h and VURDERING_RE.search(h):
            return "\n".join(f"## {hh}\n{tt}" for hh, tt in secs[i:])
    return tekst[int(len(tekst) * 0.6):]


_TITEL = [
    (re.compile(r"^\W*(afslag (på|om) (anmodning om )?genoptagelse|genoptagelse|delafgørelse)", re.I), "andet"),
    (re.compile(r"^\W*(stadfæstelse med ændring|delvis(t)? medhold|delvis(t)? (ophævelse|stadfæstelse))", re.I), "delvis"),
    (re.compile(r"^\W*(ophævelse|hjemvisning|medhold i klage|ændring af|ugyldig)", re.I), "medhold"),
    (re.compile(r"^\W*(stadfæstelse|ikke medhold|afslag på klage)", re.I), "ikke_medhold"),
    (re.compile(r"^\W*(afvisning|bortfald|henlæggelse|ophævelse af sag som uaktuel)", re.I), "afvist"),
    (re.compile(r"^\W*(afslag på|meddelelse af) (anmodning om )?opsættende virkning", re.I), "andet"),
]


def udfald_fra_titel(titel: str) -> str | None:
    t = titel.replace("​", "").strip()
    if re.search(r"som uaktuel|bortfald", t, re.I):
        return "afvist"
    for rx, ud in _TITEL:
        if rx.search(t):
            return ud
    return None


def bestem_udfald(tekst: str, titel: str = "") -> str:
    fra_titel = udfald_fra_titel(titel)
    if fra_titel:
        return fra_titel
    intro = indledning(tekst)
    slut = tekst[-2500:]
    if _OPSAETTENDE.search(intro[:1500]) and not _MEDHOLD.search(intro) and not _IKKE_MEDHOLD.search(intro):
        return "andet"
    for del_ in (intro, slut):
        if _UAKTUEL.search(del_) and not _IKKE_MEDHOLD.search(del_):
            return "afvist"
        d = bool(_DELVIS.search(del_))
        m = bool(_MEDHOLD.search(del_))
        k = bool(_IKKE_MEDHOLD.search(del_))
        a = bool(_AFVIST.search(del_))
        if d or (m and k):
            return "delvis"
        if m:
            return "medhold"
        if k:
            return "ikke_medhold"
        if a:
            return "afvist"
    return "ukendt"


def _uden_noter(tekst: str) -> str:
    """Fjern fodnote- og kildelisten i slutningen (linjer med ↑, punkttegn, lovlister)."""
    linjer = tekst.rstrip().splitlines()
    while linjer and (not linjer[-1].strip() or "↑" in linjer[-1] or linjer[-1].strip() in ("•", "##")
                      or re.match(r"^(Lov|Bekendtgørelse|Vejledning|Lovbekendtgørelse|Bemærkninger|Direktiv|Rådets|Europa)", linjer[-1].strip())):
        linjer.pop()
    return "\n".join(linjer)


def er_afkortet(tekst: str) -> bool:
    """Heuristik: tekst, der slutter midt i en sætning (efter fodnoter er fjernet)."""
    tekst = _uden_noter(tekst)
    hale = tekst.rstrip()[-300:]
    if not hale:
        return True
    if re.search(r"(klagevejledning|gebyr|tilbagebetal|domstol|6 måneder|anlægges|"
                 r"afgørelsen er endelig|kan ikke påklages|retssag|Med venlig hilsen)", tekst[-3000:], re.I):
        return False
    return not re.search(r"[.)»”\":;]\s*$", hale)


def _norm_hash(tekst: str) -> str:
    t = re.sub(r"\W+", "", tekst.lower())[:20000]
    return hashlib.sha1(t.encode()).hexdigest()


def byg_korpus(data_dir: Path = DATA_DIR) -> tuple[list[Afgoerelse], dict]:
    """Læs alle zip-filer, fjern dubletter og tomme tekster, bestem udfald."""
    stats = {"rækker": 0, "dublet_id": 0, "dublet_tekst": 0, "tom": 0, "afkortet": 0}
    pr_uuid: dict[str, Afgoerelse] = {}
    for p in sorted(data_dir.glob("*.csv.zip")):
        for r in _read_zip(p):
            stats["rækker"] += 1
            u = r["id"]
            if u in pr_uuid:
                stats["dublet_id"] += 1
                if r["Retsomraade"] not in pr_uuid[u].kategorier:
                    pr_uuid[u].kategorier.append(r["Retsomraade"])
                if len(r["Tekst"]) > len(pr_uuid[u].tekst):  # fx PDF-tekst for tom brødtekst
                    pr_uuid[u].tekst = r["Tekst"]
                continue
            naevn = r["Naevn"]
            pr_uuid[u] = Afgoerelse(
                id=("P" if naevn == "PKN" else "M") + u.replace("-", "")[:8],
                uuid=u, naevn=naevn, jnr=r["Jnr"], dato=r["Dato"], titel=r["Titel"],
                link=r["Link"], kategorier=[r["Retsomraade"]], tekst=r["Tekst"])
    ud, set_hash = [], {}
    for a in pr_uuid.values():
        if len(a.tekst) < MIN_TEKST:
            stats["tom"] += 1
            continue
        h = _norm_hash(a.tekst)
        if h in set_hash:
            stats["dublet_tekst"] += 1
            set_hash[h].noter.append(f"dublet af {a.id}")
            continue
        set_hash[h] = a
        a.udfald = bestem_udfald(a.tekst, a.titel)
        a.afkortet = er_afkortet(a.tekst)
        stats["afkortet"] += a.afkortet
        ud.append(a)
    ud.sort(key=lambda x: (x.dato, x.id), reverse=True)
    stats["tilbage"] = len(ud)
    return ud, stats


def gem_cache(korpus: list[Afgoerelse], path: Path = CACHE) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for a in korpus:
            f.write(json.dumps(a.to_json(), ensure_ascii=False) + "\n")


def load(path: Path = CACHE) -> list[Afgoerelse]:
    if not path.exists():
        korpus, _ = byg_korpus()
        gem_cache(korpus, path)
        return korpus
    with open(path, encoding="utf-8") as f:
        return [Afgoerelse(**json.loads(line)) for line in f]


if __name__ == "__main__":
    import collections
    k, s = byg_korpus()
    gem_cache(k)
    print(json.dumps(s, ensure_ascii=False))
    c = collections.Counter((a.naevn, a.udfald) for a in k)
    for x, n in sorted(c.items()):
        print(x, n)

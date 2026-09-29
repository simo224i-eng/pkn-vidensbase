"""Find hvor nævnets egen vurdering begynder i en AKF-kendelse.

Kendelserne er bygget op som: sagsfremstilling → parternes indlæg → "Nævnet udtaler:"
→ nævnets gengivelse af sagen og parternes anbringender → nævnets vurdering
("Nævnet lægger til grund …", "… finder nævnet …") → resultat. "Nævnet udtaler"
markerer altså ikke selve vurderingen; det gjorde, at klagers argumenter blev
tilskrevet nævnet (fundet ved udsagnsrevision af svarene).
"""
from __future__ import annotations

import re

NÆVNET_UDTALER_RX = re.compile(r"\b(?:anke)?nævnet\s+udtaler\b", re.IGNORECASE)

# Parternes anbringender, også når nævnet gengiver dem ("Klagerne har til støtte
# for deres krav blandt andet henvist til …")
_PART_RX = re.compile(
    r"\b(?:klage(?:r|ren|rne|rens|rnes)|forsikringstage(?:r|ren)|køb(?:er|eren|erne)|"
    r"(?:forsikrings)?selskabet|selskabets\s+\w+)\s+(?:har\s+|havde\s+)?(?:[^.\n]{0,60}?\s)?"
    r"(?:anført|anfører|gjort\s+gældende|gør\s+gældende|henvist\s+til|henviser\s+til|"
    r"bestridt|bestrider|fremsat\s+krav|påstået|påstår|fastholdt|fastholder)\b",
    re.IGNORECASE,
)

# Nævnets egne vurderingsformuleringer
_VURDERING_RX = re.compile(
    r"\b(?:anke)?nævnet\s+(?:lægger|finder|bemærker|vurderer|fastslår|tiltræder|må\s|kan\s+(?:ikke\s+)?"
    r"(?:kritisere|pålægge|give|tiltræde|lægge)|har\s+(?:lagt|fundet)|er\s+enig)|"
    r"\b(?:finder|lægger|bemærker|vurderer)\s+(?:anke)?nævnet\b|"
    r"\bdet\s+er\s+(?:anke)?nævnets\s+opfattelse|\befter\s+en\s+samlet\s+vurdering|"
    r"\bsåledes\s+som\s+sagen\s+(?:nu\s+)?foreligger\s+oplyst",
    re.IGNORECASE,
)


def _sætning(tekst: str, pos: int) -> str:
    start = max(tekst.rfind(".", 0, pos), tekst.rfind("\n", 0, pos)) + 1
    slut = tekst.find(".", pos)
    return tekst[start: slut if slut >= 0 else len(tekst)]


def vurdering_offset(nævnsdel: str) -> int:
    """Offset i ``nævnsdel`` (teksten fra "Nævnet udtaler"), hvor vurderingen begynder.

    Vurderingen begynder ved den første vurderingsformulering, hvorefter nævnet højst
    én gang mere gengiver et partsanbringende ("Det, klageren i øvrigt har anført, kan
    ikke føre til andet resultat"). Sætninger, der selv nævner nævnet, er vurdering.
    """
    parter = [m.start() for m in _PART_RX.finditer(nævnsdel)
              if "nævn" not in _sætning(nævnsdel, m.start()).lower()]
    for m in _VURDERING_RX.finditer(nævnsdel):
        if sum(p > m.start() for p in parter) <= 1:
            return max(max(nævnsdel.rfind(".", 0, m.start()), nævnsdel.rfind("\n", 0, m.start())) + 1, 0)
    if not parter:
        return 0
    slut = nævnsdel.find(".", parter[-1])
    return slut + 1 if slut >= 0 else 0


def del_kendelse(tekst: str) -> tuple[int, int] | None:
    """(start på nævnets del, start på nævnets vurdering) eller None uden markør.

    Den sidste forekomst af "Nævnet udtaler" bruges, fordi lange kendelser kan
    citere en tidligere kendelse midt i sagsfremstillingen."""
    matches = list(NÆVNET_UDTALER_RX.finditer(tekst or ""))
    if not matches:
        return None
    b = matches[-1].start()
    return b, b + vurdering_offset(tekst[b:])

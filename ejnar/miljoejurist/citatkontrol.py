"""Automatisk citatkontrol.

Et citat godkendes kun, hvis det står ordret i kilden. Sammenligningen tåler
forskelle i mellemrum, linjeskift, anførselstegn, bindestreger og PDF-orddeling
(den bruger kun bogstaver og tal). Udeladelsestegn ("...", "…", "[…]") deler
citatet i stykker, som hver skal findes i kilden i samme rækkefølge.
"""
from __future__ import annotations

import re
from functools import lru_cache

_UDELADELSE = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|\.\.\.|…)\s*")
MIN_STYKKE = 12  # stykker kortere end dette (i signaturtegn) ignoreres


def signatur(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", s)  # orddeling over linjeskift
    return re.sub(r"[^0-9a-zæøåéüöä§]", "", s)


@lru_cache(maxsize=256)
def _sig_cached(tekst: str) -> str:
    return signatur(tekst)


def find(citat: str, kilde: str) -> bool:
    """True hvis citatet (evt. med udeladelser) står i kilden."""
    if not citat or not kilde:
        return False
    k = _sig_cached(kilde)
    pos = 0
    stykker = [signatur(x) for x in _UDELADELSE.split(citat)]
    stykker = [x for x in stykker if len(x) >= MIN_STYKKE] or [signatur(citat)]
    if not stykker[0]:
        return False
    for st in stykker:
        i = k.find(st, pos)
        if i < 0:
            return False
        pos = i + len(st)
    return True


def placering(citat: str, kilde: str) -> tuple[int, int] | None:
    """Omtrentlig (start, slut) i den oprindelige tekst for det første stykke af citatet."""
    st = [x for x in _UDELADELSE.split(citat or "") if len(signatur(x)) >= MIN_STYKKE]
    if not st:
        return None
    mål = signatur(st[0])
    # Kortlæg signaturindeks -> tekstindeks
    idx, sig = [], []
    for i, ch in enumerate((kilde or "").lower()):
        if re.match(r"[0-9a-zæøåéüöä§]", ch):
            sig.append(ch)
            idx.append(i)
    j = "".join(sig).find(mål)
    if j < 0:
        return None
    return idx[j], idx[min(j + len(mål), len(idx)) - 1] + 1


def kontroller(citater: list[tuple[str, str]]) -> list[dict]:
    """[(citat, kildetekst)] -> [{citat, ok}]"""
    return [{"citat": c, "ok": find(c, k)} for c, k in citater]

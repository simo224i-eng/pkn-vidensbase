"""Lille BM25-indeks uden afhængigheder (dansk tokenisering med simpel stemming)."""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

STOP = set("""og i at det er en til på som de med for af den der ikke var et han har
om vi sig men skal kan efter også ved fra eller så hvis blev være bliver når kun
hvor nu jf stk nr mv bl dette denne disse sådan samt deres dets hans hendes være
været have haft vil ville kunne skulle hvad hvem hvilke hvilket hvorfor mod under
over end ud op ind meget mere mest nogle noget ingen alle andre anden andet""".split())


def stem(w: str) -> str:
    for suf in ("erne", "ende", "ene", "ers", "er", "en", "et", "es", "e", "s"):
        if len(w) > len(suf) + 3 and w.endswith(suf):
            return w[: -len(suf)]
    return w


def tokens(t: str) -> list[str]:
    ord_ = re.findall(r"[a-zæøåéü0-9]+(?:-[a-zæøå]+)?", (t or "").lower())
    return [stem(w) for w in ord_ if w not in STOP and len(w) > 1]


class BM25:
    def __init__(self, docs: list[str], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.tf = [Counter(tokens(d)) for d in docs]
        self.len = [sum(c.values()) for c in self.tf]
        self.avg = (sum(self.len) / len(self.len)) if self.len else 1
        df = Counter()
        for c in self.tf:
            df.update(c.keys())
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}
        self.post = defaultdict(list)
        for i, c in enumerate(self.tf):
            for w, f in c.items():
                self.post[w].append((i, f))

    def search(self, q: str, k: int = 10, filt=None) -> list[tuple[int, float]]:
        sc = defaultdict(float)
        for w in set(tokens(q)):
            idf = self.idf.get(w)
            if not idf:
                continue
            for i, f in self.post[w]:
                denom = f + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg)
                sc[i] += idf * f * (self.k1 + 1) / denom
        res = sorted(sc.items(), key=lambda x: -x[1])
        if filt:
            res = [r for r in res if filt(r[0])]
        return res[:k]

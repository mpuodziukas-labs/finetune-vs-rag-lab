"""BM25 retriever (Okapi, k1=1.5, b=0.75). Registered as 'bm25'."""

import math
import re
from collections import Counter

from ftlab.registry import RETRIEVERS

_TOK = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    return _TOK.findall(text.lower())


@RETRIEVERS.register("bm25")
class BM25:
    def __init__(self, docs: list[str], k1: float = 1.5, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.tfs = [Counter(tokenize(d)) for d in docs]
        self.lens = [sum(tf.values()) for tf in self.tfs]
        self.avg = (sum(self.lens) / len(docs)) if docs else 0.0
        df: Counter[str] = Counter()
        for tf in self.tfs:
            df.update(tf.keys())
        n = len(docs)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}

    def score(self, query: str, i: int) -> float:
        tf, dl = self.tfs[i], self.lens[i]
        s = 0.0
        for t in set(tokenize(query)):
            f = tf.get(t, 0)
            if f:
                denom = f + self.k1 * (1 - self.b + self.b * dl / (self.avg or 1.0))
                s += self.idf[t] * f * (self.k1 + 1) / denom
        return s

    def top_k(self, query: str, k: int) -> list[int]:
        """Indices of the k best docs; ties broken by lower index (deterministic)."""
        if k < 0:
            raise ValueError("k must be >= 0")
        order = sorted(range(len(self.tfs)), key=lambda i: (-self.score(query, i), i))
        return order[:k]

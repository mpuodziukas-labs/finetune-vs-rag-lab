"""Small, dependency-light statistics: bootstrap CI, exact McNemar, percentiles."""

from collections.abc import Sequence
from math import comb

import numpy as np


def bootstrap_ci(
    correct: Sequence[int], n_boot: int = 10000, seed: int = 0, level: float = 0.95
) -> tuple[float, float, float]:
    """Mean and percentile bootstrap CI of a 0/1 vector."""
    x = np.asarray(correct, dtype=float)
    if x.size == 0:
        raise ValueError("bootstrap_ci: empty input has no mean")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    a = (1.0 - level) / 2.0
    lo, hi = np.quantile(means, [a, 1.0 - a])
    return float(x.mean()), float(lo), float(hi)


def mcnemar_exact(a: Sequence[int], b: Sequence[int]) -> tuple[int, int, float]:
    """Exact two-sided McNemar on paired 0/1 vectors.

    Returns (n01, n10, p): n01 = A wrong and B right, n10 = A right and B wrong."""
    if len(a) != len(b):
        raise ValueError("paired vectors must be the same length")
    n01 = sum(1 for x, y in zip(a, b, strict=True) if x == 0 and y == 1)
    n10 = sum(1 for x, y in zip(a, b, strict=True) if x == 1 and y == 0)
    n = n01 + n10
    if n == 0:
        return n01, n10, 1.0
    k = min(n01, n10)
    tail = sum(comb(n, i) for i in range(k + 1)) / 2**n
    return n01, n10, min(1.0, 2.0 * tail)


def percentiles(xs: Sequence[float]) -> tuple[float, float]:
    p50, p95 = np.percentile(np.asarray(xs, dtype=float), [50, 95])
    return float(p50), float(p95)

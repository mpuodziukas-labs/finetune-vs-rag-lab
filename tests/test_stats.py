import numpy as np

from ftlab.stats import bootstrap_ci, mcnemar_exact, percentiles


def test_bootstrap_degenerate() -> None:
    m, lo, hi = bootstrap_ci([1] * 50, n_boot=500, seed=1)
    assert (m, lo, hi) == (1.0, 1.0, 1.0)


def test_bootstrap_contains_mean_and_is_deterministic() -> None:
    xs = [1, 0] * 100
    a = bootstrap_ci(xs, n_boot=2000, seed=7)
    assert all(bootstrap_ci(xs, n_boot=2000, seed=7) == a for _ in range(8))  # one unseeded repeat can tie by chance
    m, lo, hi = a
    assert m == 0.5 and lo < 0.5 < hi and (hi - lo) < 0.2


def test_mcnemar_known_values() -> None:
    a = [1] * 10 + [0] * 5
    b = [0] * 10 + [0] * 5
    n01, n10, p = mcnemar_exact(a, b)
    assert (n01, n10) == (0, 10)
    assert abs(p - 2 * 0.5**10) < 1e-12


def test_mcnemar_symmetric_and_empty() -> None:
    assert mcnemar_exact([1, 0, 1, 0], [0, 1, 0, 1])[2] == 1.0
    assert mcnemar_exact([1, 1], [1, 1])[2] == 1.0


def test_percentiles() -> None:
    p50, p95 = percentiles(list(range(1, 101)))
    assert np.isclose(p50, 50.5) and np.isclose(p95, 95.05)

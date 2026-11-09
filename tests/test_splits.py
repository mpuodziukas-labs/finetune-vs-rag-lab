from collections import Counter

import pytest

from ftlab.splits import SplitSpec, make_split, subset_train

ROWS = {f"r{i}": f"c{i % 3}" for i in range(150)}  # 3 classes x 50
SPEC = SplitSpec(seed=5, train_per_class=30, dev_per_class=5, test_per_class=10)


def test_disjoint_and_sizes() -> None:
    s = make_split(ROWS, SPEC)
    tr, dv, te = set(s["train"]), set(s["dev"]), set(s["test"])
    assert not (tr & dv) and not (tr & te) and not (dv & te)
    assert (len(tr), len(dv), len(te)) == (90, 15, 30)
    assert Counter(ROWS[i] for i in te) == {"c0": 10, "c1": 10, "c2": 10}


def test_deterministic_and_seed_sensitive() -> None:
    a = make_split(ROWS, SPEC)
    assert a == make_split(ROWS, SPEC)
    other = make_split(ROWS, SplitSpec(6, 30, 5, 10))
    assert a["hash"] != other["hash"]


def test_insufficient_rows_raises() -> None:
    with pytest.raises(ValueError):
        make_split(ROWS, SplitSpec(1, 40, 10, 10))


def test_nested_fractions() -> None:
    s = make_split(ROWS, SPEC)
    f25, f50, f100 = (subset_train(s["train"], ROWS, f) for f in (0.25, 0.5, 1.0))
    assert set(f25) < set(f50) < set(f100) == set(s["train"])
    assert Counter(ROWS[i] for i in f25) == {"c0": 8, "c1": 8, "c2": 8}

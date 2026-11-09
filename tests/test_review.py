"""Reviewer-grade checks: statistics against hand-computed values, boundary and empty inputs, split nesting,
dev-only tuning, and the network guard. Each test fails against the defect it names."""

import ast
import socket
from pathlib import Path

import pytest

from ftlab.audit import audit
from ftlab.retrieve import BM25
from ftlab.splits import SplitSpec, make_split, subset_train
from ftlab.stats import bootstrap_ci, mcnemar_exact

ROOT = Path(__file__).resolve().parents[1]
ROWS = {f"r{i}": f"c{i % 2}" for i in range(80)}
SPEC = SplitSpec(seed=3, train_per_class=15, dev_per_class=5, test_per_class=10)


def test_mcnemar_hand_computed() -> None:
    # n=10 discordant, min=2: p = 2 * (C(10,0)+C(10,1)+C(10,2)) / 2^10 = 2 * 56 / 1024 = 0.109375
    a = [1] * 8 + [0] * 2
    b = [0] * 8 + [1] * 2
    assert mcnemar_exact(a, b) == (2, 8, pytest.approx(0.109375))
    assert mcnemar_exact([1, 0], [1, 0])[2] == 1.0
    with pytest.raises(ValueError):
        mcnemar_exact([1], [1, 0])


def test_bootstrap_known_values_and_seed() -> None:
    assert bootstrap_ci([1] * 50) == (1.0, 1.0, 1.0)
    assert bootstrap_ci([0] * 50) == (0.0, 0.0, 0.0)
    v = [1, 0] * 30
    assert bootstrap_ci(v, seed=1) == bootstrap_ci(v, seed=1)
    assert bootstrap_ci(v, seed=1) != bootstrap_ci(v, seed=2)
    mean, lo, hi = bootstrap_ci(v)
    assert mean == 0.5 and lo < 0.5 < hi


def test_bootstrap_empty_input_is_refused_clearly() -> None:
    with pytest.raises(ValueError, match="empty"):
        bootstrap_ci([])


def test_bm25_negative_k_refused_and_zero_k_empty() -> None:
    bm = BM25(["a b", "c d"])
    assert bm.top_k("a", 0) == []
    with pytest.raises(ValueError, match="k"):
        bm.top_k("a", -1)


def test_audit_empty_receipt_is_flagged_not_crashed() -> None:
    split = make_split(ROWS, SPEC)
    ev = {"method": "zero_shot", "eval_split": "test", "metric_split": "test", "split_hash": split["hash"],
          "ids": [], "gold": [], "preds": [], "accuracy": 0.0}
    bad = audit(ROWS, SPEC, split, None, ev)
    assert "eval_on_test" in bad and "metric_matches" in bad


def test_subset_train_is_nested_and_never_empty_per_class() -> None:
    split = make_split(ROWS, SPEC)
    prev: list[str] = []
    for frac in (0.25, 0.5, 1.0):
        cur = subset_train(split["train"], ROWS, frac)
        assert set(prev) <= set(cur)
        assert {ROWS[i] for i in cur} == {"c0", "c1"}
        prev = list(cur)
    assert set(prev) == set(split["train"])


def test_split_sizes_and_disjoint_on_hand_fixture() -> None:
    s = make_split(ROWS, SPEC)
    assert (len(s["train"]), len(s["dev"]), len(s["test"])) == (30, 10, 20)
    assert not (set(s["train"]) & set(s["dev"])) and not (set(s["train"]) & set(s["test"]))


def test_tune_k_reads_only_dev_and_train() -> None:
    src = (ROOT / "src" / "ftlab" / "cli.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "cmd_tune_k")
    keys = {n.slice.value for n in ast.walk(fn) if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)}
    assert "test" not in keys, "tune_k touches the test split"
    assert {"dev", "train"} <= keys


def test_network_guard_blocks_external_connect() -> None:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.2)
    try:
        with pytest.raises(AssertionError, match="must not use the network"):
            s.connect(("203.0.113.9", 80))
    finally:
        s.close()


def test_readme_states_seed_and_resamples_that_the_config_uses() -> None:
    import yaml

    cfg = yaml.safe_load((ROOT / "configs" / "default.yaml").read_text(encoding="utf-8"))
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"seed, {cfg['seed']}" in readme and f"({cfg['bootstrap_n']} resamples)" in readme.replace("10000", str(cfg["bootstrap_n"]))
    assert "10000 resamples" in readme and cfg["bootstrap_n"] == 10000


def test_community_files_exist_and_readme_labels_comparability() -> None:
    for name in ("SECURITY.md", "CONTRIBUTING.md", "CITATION.cff", "LICENSE"):
        assert (ROOT / name).stat().st_size > 100, name
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "not comparable" in readme and "93.66" in readme
    assert readme.index("**Result:**") < readme.index("## Honesty Statement")  # headline above the fold

import copy
from typing import Any

from ftlab.audit import audit
from ftlab.splits import SplitSpec, make_split

ROWS = {f"r{i}": f"c{i % 2}" for i in range(80)}
SPEC = SplitSpec(seed=3, train_per_class=15, dev_per_class=5, test_per_class=10)


def _clean() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    split = make_split(ROWS, SPEC)
    train = {"train_ids": list(split["train"]), "adapter": {"lora_params": 100, "logit_delta": 0.3}}
    ids = list(split["test"])
    gold = [ROWS[i] for i in ids]
    preds = [g if k % 4 else "other" for k, g in enumerate(gold)]
    acc = sum(p == g for p, g in zip(preds, gold, strict=True)) / len(ids)
    ev = {
        "method": "lora",
        "eval_split": "test",
        "metric_split": "test",
        "split_hash": split["hash"],
        "ids": ids,
        "gold": gold,
        "preds": preds,
        "accuracy": acc,
    }
    return split, train, ev


def test_clean_passes() -> None:
    split, train, ev = _clean()
    assert audit(ROWS, SPEC, split, train, ev) == []


def test_leak_flagged() -> None:
    split, train, ev = _clean()
    train["train_ids"].append(split["test"][0])
    assert "train_clean" in audit(ROWS, SPEC, split, train, ev)


def test_eval_on_train_flagged() -> None:
    split, train, ev = _clean()
    ev["ids"] = list(split["train"][:20])
    ev["eval_split"] = "train"
    assert "eval_on_test" in audit(ROWS, SPEC, split, train, ev)


def test_wrong_seed_flagged() -> None:
    split, train, ev = _clean()
    wrong = make_split(ROWS, SplitSpec(SPEC.seed + 1, 15, 5, 10))
    ev["split_hash"] = wrong["hash"]
    assert "split_recomputed" in audit(ROWS, SPEC, wrong, train, ev)


def test_noop_adapter_flagged() -> None:
    split, train, ev = _clean()
    t2 = copy.deepcopy(train)
    t2["adapter"] = {"lora_params": 0, "logit_delta": 0.0}
    assert "adapter_active" in audit(ROWS, SPEC, split, t2, ev)


def test_metric_not_matching_flagged() -> None:
    split, train, ev = _clean()
    ev["accuracy"] = 0.99
    assert "metric_matches" in audit(ROWS, SPEC, split, train, ev)

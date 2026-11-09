"""Fail-closed audit of one (split, train, eval) receipt triple. Returns failed check names."""

from typing import Any

from ftlab.splits import SplitSpec, make_split


def audit(
    rows: dict[str, str],
    spec: SplitSpec,
    split: dict[str, Any],
    train: dict[str, Any] | None,
    ev: dict[str, Any],
) -> list[str]:
    bad: list[str] = []
    tr, dv, te = set(split["train"]), set(split["dev"]), set(split["test"])

    expected = make_split(rows, spec)  # recompute from data + the CONFIGURED seed
    if not (split["hash"] == expected["hash"] == ev.get("split_hash")):
        bad.append("split_recomputed")
    if (tr & dv) or (tr & te) or (dv & te):
        bad.append("split_disjoint")
    if train is not None and not set(train["train_ids"]) <= set(expected["train"]):
        bad.append("train_clean")

    ids = list(ev["ids"])
    if ev.get("eval_split") != "test" or set(ids) != set(expected["test"]) or len(ids) != len(
        set(ids)
    ):
        bad.append("eval_on_test")
    if train is not None and set(ids) & set(train["train_ids"]):
        bad.append("eval_not_train")

    gold, preds = list(ev["gold"]), list(ev["preds"])
    aligned = len(ids) > 0 and len(gold) == len(preds) == len(ids) and gold == [rows.get(i) for i in ids]
    recomputed = (
        sum(p == g for p, g in zip(preds, gold, strict=True)) / len(ids) if aligned else -1.0
    )
    if not aligned or abs(recomputed - ev["accuracy"]) > 1e-9 or ev.get("metric_split") != "test":
        bad.append("metric_matches")

    if ev.get("method") == "lora":
        ad = (train or {}).get("adapter", {})
        if ad.get("lora_params", 0) <= 0 or ad.get("logit_delta", 0.0) <= 1e-6:
            bad.append("adapter_active")
    return bad

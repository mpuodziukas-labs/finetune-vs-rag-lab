"""Seeded, stratified train/dev/test split with nested train fractions."""

import hashlib
import json
import random
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SplitSpec:
    seed: int
    train_per_class: int
    dev_per_class: int
    test_per_class: int


def _by_class(rows: dict[str, str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)
    for rid in sorted(rows):
        groups[rows[rid]].append(rid)
    return groups


def make_split(rows: dict[str, str], spec: SplitSpec) -> dict[str, Any]:
    """rows: id -> label. Deterministic given (rows, spec)."""
    need = spec.train_per_class + spec.dev_per_class + spec.test_per_class
    split: dict[str, list[str]] = {"train": [], "dev": [], "test": []}
    for label, ids in sorted(_by_class(rows).items()):
        if len(ids) < need:
            raise ValueError(f"class {label} has {len(ids)} rows, need {need}")
        rng = random.Random(f"{spec.seed}:{label}")
        shuffled = ids[:]
        rng.shuffle(shuffled)
        t, d = spec.test_per_class, spec.dev_per_class
        split["test"] += shuffled[:t]
        split["dev"] += shuffled[t : t + d]
        split["train"] += shuffled[t + d : t + d + spec.train_per_class]
    out: dict[str, Any] = {"spec": asdict(spec), **split}
    out["hash"] = hashlib.sha256(
        json.dumps({k: split[k] for k in ("train", "dev", "test")}, sort_keys=True).encode()
    ).hexdigest()
    return out


def subset_train(train_ids: list[str], rows: dict[str, str], frac: float) -> list[str]:
    """Nested stratified prefix: subset(0.25) < subset(0.5) < subset(1.0)."""
    per: dict[str, list[str]] = defaultdict(list)
    for rid in train_ids:
        per[rows[rid]].append(rid)
    keep: list[str] = []
    for label in sorted(per):
        keep += per[label][: max(1, round(len(per[label]) * frac))]
    return keep

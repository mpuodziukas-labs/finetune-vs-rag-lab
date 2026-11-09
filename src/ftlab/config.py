"""Typed config loaded from YAML. Validation is fail-closed."""

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ftlab import SCHEMA_VERSION
from ftlab.splits import SplitSpec

ROOT = Path(__file__).resolve().parents[2]
BUILTINS = ["ftlab.data", "ftlab.modeling", "ftlab.retrieve"]  # register themselves on import


@dataclass(frozen=True)
class AdapterCfg:
    name: str
    rank: int
    alpha: int
    dropout: float
    target_modules: list[str]
    lr: float
    epochs: int
    batch_size: int


@dataclass(frozen=True)
class LabConfig:
    raw: dict[str, Any]
    seed: int
    spec: SplitSpec
    adapter: AdapterCfg

    @property
    def dataset(self) -> dict[str, Any]:
        return dict(self.raw["dataset"])

    @property
    def model(self) -> dict[str, Any]:
        return dict(self.raw["model"])


def load_config(path: str | Path | None = None) -> LabConfig:
    p = Path(path) if path else ROOT / "configs" / "default.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"config schema_version must be {SCHEMA_VERSION}")
    for mod in BUILTINS + list(raw.get("plugins", [])):
        importlib.import_module(mod)
    a = raw["adapter"]
    if int(a["rank"]) < 1:
        raise ValueError("adapter.rank must be >= 1 (rank 0 is a no-op adapter)")
    sp = raw["dataset"]["split"]
    spec = SplitSpec(int(raw["seed"]), sp["train_per_class"], sp["dev_per_class"], sp["test_per_class"])
    adapter = AdapterCfg(
        a["name"], int(a["rank"]), int(a["alpha"]), float(a["dropout"]),
        list(a["target_modules"]), float(a["lr"]), int(a["epochs"]), int(a["batch_size"]),
    )  # fmt: skip
    return LabConfig(raw=raw, seed=int(raw["seed"]), spec=spec, adapter=adapter)

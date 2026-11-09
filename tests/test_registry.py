import sys
import textwrap
from pathlib import Path

import pytest
import yaml

from ftlab.config import ROOT, load_config
from ftlab.registry import DATASETS, MODELS, Registry


def test_duplicate_and_unknown() -> None:
    r = Registry("thing")
    r.register("a")(lambda: 1)
    with pytest.raises(KeyError):
        r.register("a")(lambda: 2)
    with pytest.raises(KeyError):
        r.get("b")


def test_plugin_extends_without_core_edit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "my_plugin_mod.py").write_text(
        textwrap.dedent(
            """
            from ftlab.registry import DATASETS, MODELS

            @DATASETS.register("toy_ds")
            def toy(cfg, cache):
                return []

            @MODELS.register("toy_model")
            def toy_model(cfg):
                return None, None
            """
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    raw = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    raw["plugins"] = ["my_plugin_mod"]
    p = tmp_path / "c.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    load_config(p)
    assert "toy_ds" in DATASETS.names() and "toy_model" in MODELS.names()
    sys.modules.pop("my_plugin_mod", None)


def test_rank_zero_and_bad_schema_rejected(tmp_path: Path) -> None:
    raw = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    raw["adapter"]["rank"] = 0
    p = tmp_path / "r0.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)
    raw["adapter"]["rank"] = 8
    raw["schema_version"] = "999"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)

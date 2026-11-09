"""Dataset registry + pinned fetch. Every file is verified against a sha256 pin."""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import yaml

from ftlab.registry import DATASETS


@dataclass(frozen=True)
class Row:
    id: str
    text: str
    label: str


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch_pinned(repo: str, revision: str, files: dict[str, str], cache: Path) -> Path:
    """Download each file at `revision` and fail closed on any sha256 mismatch."""
    from huggingface_hub import hf_hub_download

    base = cache / repo.replace("/", "__")
    for name, want in files.items():
        p = Path(hf_hub_download(repo, name, repo_type="dataset", revision=revision, local_dir=base))
        got = sha256_file(p)
        if got != want:
            raise RuntimeError(f"sha256 mismatch for {repo}/{name}: got {got}, pinned {want}")
    return base


def _label_names(readme: Path) -> dict[int, str]:
    front = readme.read_text(encoding="utf-8").split("---")[1]
    names = yaml.safe_load(front)["dataset_info"]["features"][1]["dtype"]["class_label"]["names"]
    return {int(k): str(v) for k, v in names.items()}


@DATASETS.register("banking77_subset")
def banking77_subset(cfg: dict[str, Any], cache: Path) -> list[Row]:
    """Pool official train+test for the chosen classes (we re-split with our own seed),
    then drop exact duplicate texts so no text appears on both sides of a split."""
    base = fetch_pinned(cfg["repo"], cfg["revision"], cfg["files"], cache)
    names = _label_names(base / "README.md")
    keep = set(cfg["classes"])
    rows: list[Row] = []
    seen: set[str] = set()
    for part in ("train", "test"):
        t = pq.read_table(base / f"data/{part}-00000-of-00001.parquet").to_pylist()
        for i, r in enumerate(t):
            label = names[int(r["label"])]
            key = " ".join(str(r["text"]).lower().split())
            if label in keep and key not in seen:
                seen.add(key)
                rows.append(Row(f"{part}-{i}", str(r["text"]), label))
    missing = keep - {r.label for r in rows}
    if missing:
        raise RuntimeError(f"classes not found in dataset: {sorted(missing)}")
    return rows

"""Catastrophic-forgetting probe: held-out general-text perplexity, adapter off vs on."""

import math
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import torch

from ftlab.data import sha256_file


def load_chunks(fcfg: dict[str, Any], tok: Any, cache: Path) -> list[torch.Tensor]:
    from huggingface_hub import hf_hub_download

    p = Path(
        hf_hub_download(
            fcfg["repo"], fcfg["file"], repo_type="dataset", revision=fcfg["revision"],
            local_dir=cache / fcfg["repo"].replace("/", "__"),
        )  # fmt: skip
    )
    if sha256_file(p) != fcfg["sha256"]:
        raise RuntimeError("forgetting-probe dataset sha256 mismatch")
    text = "".join(t for t in pq.read_table(p).column("text").to_pylist() if t.strip())
    ids = tok(text, return_tensors="pt", add_special_tokens=False)["input_ids"][0]
    n, k = int(fcfg["n_chunks"]), int(fcfg["chunk_tokens"])
    if len(ids) < n * k:
        raise RuntimeError(f"probe text too short: {len(ids)} < {n * k}")
    return [ids[i * k : (i + 1) * k] for i in range(n)]


@torch.inference_mode()
def perplexity(model: Any, chunks: list[torch.Tensor]) -> float:
    nll = [float(model(input_ids=c[None], labels=c[None]).loss) for c in chunks]
    return math.exp(sum(nll) / len(nll))

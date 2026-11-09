"""Train and eval primitives shared by the CLI and the selftest (one code path).

Prediction rule for every method: argmax of next-token logits restricted to the first token
of each label's verbalizer word. One forward pass per example, so latency is comparable."""

import random
import time
from collections.abc import Callable
from typing import Any

import torch

from ftlab import SCHEMA_VERSION
from ftlab.config import AdapterCfg
from ftlab.data import Row
from ftlab.prompts import tuned
from ftlab.registry import ADAPTERS


def label_first_ids(tok: Any, words: list[str]) -> list[int]:
    ids = [int(tok.encode(" " + w, add_special_tokens=False)[0]) for w in words]
    if len(set(ids)) != len(ids):
        raise ValueError(f"verbalizer first tokens collide: {dict(zip(words, ids, strict=True))}")
    return ids


@torch.inference_mode()
def _last_logits(model: Any, tok: Any, prompt: str) -> tuple[torch.Tensor, int]:
    enc = tok(prompt, return_tensors="pt")
    out = model(**enc).logits[0, -1]
    return out, int(enc["input_ids"].shape[1])


def do_eval(
    model: Any, tok: Any, rows: list[Row], build_prompt: Callable[[Row], str],
    labels: list[str], first_ids: list[int],
) -> dict[str, Any]:  # fmt: skip
    """Batch-size-1 evaluation. Latency includes prompt construction (incl. retrieval)."""
    model.eval()
    for r in rows[:3]:  # untimed warmup
        _last_logits(model, tok, build_prompt(r))
    idx = torch.tensor(first_ids)
    preds: list[str] = []
    lat: list[float] = []
    ntok: list[int] = []
    for r in rows:
        t0 = time.perf_counter()
        logits, n = _last_logits(model, tok, build_prompt(r))
        preds.append(labels[int(torch.argmax(logits[idx]))])
        lat.append((time.perf_counter() - t0) * 1000.0)
        ntok.append(n)
    gold = [r.label for r in rows]
    correct = [int(p == g) for p, g in zip(preds, gold, strict=True)]
    return {
        "ids": [r.id for r in rows], "gold": gold, "preds": preds, "correct": correct,
        "accuracy": sum(correct) / max(1, len(rows)),
        "latency_ms": lat, "prompt_tokens": ntok,
    }  # fmt: skip


def eval_receipt(
    ev: dict[str, Any], method: str, frac: float | None, split_name: str, split: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "kind": "eval", "method": method, "frac": frac,
        "eval_split": split_name, "metric_split": split_name,
        "split_hash": split["hash"], "split_seed": split["spec"]["seed"], **ev,
    }  # fmt: skip


def _lora_delta(model: Any, tok: Any, prompts: list[str]) -> float:
    if not hasattr(model, "disable_adapter"):
        return 0.0
    ds = []
    for p in prompts:
        on, _ = _last_logits(model, tok, p)
        with model.disable_adapter():
            off, _ = _last_logits(model, tok, p)
        ds.append(float((on - off).abs().mean()))
    return sum(ds) / max(1, len(ds))


def do_train(
    model: Any, tok: Any, train: list[Row], dev: list[Row], labels: list[str],
    first_ids: list[int], a: AdapterCfg, seed: int,
    adapter_fn: Callable[[Any, AdapterCfg, int], Any] | None = None,
) -> tuple[Any, dict[str, Any]]:  # fmt: skip
    """LoRA SFT on the first label token (full-vocab cross-entropy). Returns model + info."""
    model = (adapter_fn or ADAPTERS.get(a.name))(model, a, seed)
    for n, p in model.named_parameters():
        p.requires_grad = "lora_" in n
    params = [p for p in model.parameters() if p.requires_grad]
    lora_params = sum(p.numel() for p in params)
    opt = torch.optim.AdamW(params, lr=a.lr) if params else None  # None only in planted defects
    word_id = dict(zip(labels, first_ids, strict=True))
    rng = random.Random(seed)
    curve: list[dict[str, float]] = []
    dev_curve: list[dict[str, float]] = []
    secs, step = 0.0, 0
    for epoch in range(1, a.epochs + 1):
        order = train[:]
        rng.shuffle(order)
        model.train()
        for i in range(0, len(order), a.batch_size):
            batch = order[i : i + a.batch_size]
            t0 = time.perf_counter()
            enc = tok([tuned(r.text) for r in batch], return_tensors="pt", padding=True)
            last = enc["attention_mask"].sum(1) - 1
            logits = model(**enc).logits[torch.arange(len(batch)), last]
            target = torch.tensor([word_id[r.label] for r in batch])
            loss = torch.nn.functional.cross_entropy(logits, target)
            if opt is not None:
                opt.zero_grad()
                loss.backward()  # type: ignore[no-untyped-call]
                opt.step()
            secs += time.perf_counter() - t0
            step += 1
            curve.append({"step": step, "epoch": epoch, "loss": loss.item()})
        dv = do_eval(model, tok, dev, lambda r: tuned(r.text), labels, first_ids)
        dev_curve.append({"epoch": epoch, "dev_accuracy": dv["accuracy"]})
    model.eval()
    delta = _lora_delta(model, tok, [tuned(r.text) for r in dev[:8]])
    info = {
        "train_ids": [r.id for r in train], "n_train": len(train),
        "adapter": {"rank": a.rank, "lora_params": lora_params, "logit_delta": delta},
        "curve": curve, "dev_curve": dev_curve, "train_seconds": secs, "steps": step,
    }  # fmt: skip
    return model, info

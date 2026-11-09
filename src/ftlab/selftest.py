"""Planted-defect selftest: the audit must flag each defect by name and pass the clean control.

Runs the REAL split/train/eval/audit code on a tiny random model + synthetic rows."""

import sys
from dataclasses import replace
from typing import Any

import torch
from transformers import AutoTokenizer, LlamaConfig, LlamaForCausalLM

from ftlab.audit import audit
from ftlab.config import AdapterCfg, load_config
from ftlab.data import Row
from ftlab.engine import do_eval, do_train, eval_receipt, label_first_ids
from ftlab.prompts import tuned
from ftlab.registry import MODELS
from ftlab.splits import SplitSpec, make_split

WORDS = ["alpha", "bravo", "charlie", "delta"]
SEED = 11
SPEC = SplitSpec(SEED, 12, 4, 8)
A = AdapterCfg("lora", 4, 8, 0.0, ["q_proj", "v_proj"], 1e-2, 2, 8)


@MODELS.register("tiny_random_model_a")
def tiny_random_model_a(cfg: dict[str, Any]) -> tuple[Any, Any]:
    tok = AutoTokenizer.from_pretrained(cfg["id"], revision=cfg["revision"])
    tok.pad_token = tok.pad_token or tok.eos_token
    torch.manual_seed(0)
    c = LlamaConfig(vocab_size=len(tok), hidden_size=32, intermediate_size=64,
                    num_hidden_layers=2, num_attention_heads=4, num_key_value_heads=4)  # fmt: skip
    return LlamaForCausalLM(c), tok  # type: ignore[no-untyped-call]


def _rows() -> list[Row]:
    return [
        Row(f"s{c}-{i}", f"{w} request number {i} about {w} things", w)
        for c, w in enumerate(WORDS) for i in range(24)
    ]  # fmt: skip


def scenario(defect: str | None) -> list[str]:
    cfg = load_config()
    rows = _rows()
    by_id = {r.id: r for r in rows}
    labels = {r.id: r.label for r in rows}
    model, tok = MODELS.get("tiny_random_model_a")(cfg.model)
    first = label_first_ids(tok, WORDS)

    spec = replace(SPEC, seed=SEED + 1) if defect == "wrong_seed" else SPEC
    split = make_split(labels, spec)
    train_ids = list(split["train"])
    if defect == "leak":
        train_ids.append(split["test"][0])
    adapter_fn = (lambda m, a, s: m) if defect == "rank0" else None
    model, info = do_train(
        model, tok, [by_id[i] for i in train_ids], [by_id[i] for i in split["dev"]],
        WORDS, first, A, SEED, adapter_fn,
    )  # fmt: skip

    def run(ids: list[str]) -> dict[str, Any]:
        return do_eval(model, tok, [by_id[i] for i in ids], lambda r: tuned(r.text), WORDS, first)

    if defect == "eval_on_train":
        ev = eval_receipt(run(split["train"]), "lora", 1.0, "train", split)
    else:
        ev = eval_receipt(run(split["test"]), "lora", 1.0, "test", split)
    if defect == "dev_metric":
        dv = run(split["dev"])  # metric vectors come from dev while the receipt claims test
        ev.update({k: dv[k] for k in ("gold", "preds", "correct", "accuracy")})
    return audit(labels, SPEC, split, info, ev)


EXPECT = {
    "leak": "train_clean",
    "eval_on_train": "eval_on_test",
    "wrong_seed": "split_recomputed",
    "rank0": "adapter_active",
    "dev_metric": "metric_matches",
}


def main() -> int:
    ok = 0
    total = len(EXPECT) + 1
    clean = scenario(None)
    print(f"control clean: failures={clean}", "PASS" if not clean else "FAIL")
    ok += not clean
    for defect, want in EXPECT.items():
        got = scenario(defect)
        hit = want in got
        print(f"defect {defect}: flagged={got} expect={want}", "PASS" if hit else "FAIL")
        ok += hit
    # config guard: rank 0 must be refused before any training
    import tempfile
    from pathlib import Path

    import yaml

    from ftlab.config import ROOT

    raw = yaml.safe_load((ROOT / "configs/default.yaml").read_text(encoding="utf-8"))
    raw["adapter"]["rank"] = 0
    total += 1
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.yaml"
        p.write_text(yaml.safe_dump(raw), encoding="utf-8")
        try:
            load_config(p)
            guard = False
        except ValueError:
            guard = True
    print("config rank=0 refused:", "PASS" if guard else "FAIL")
    ok += guard
    print(f"SELFTEST {ok}/{total}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())

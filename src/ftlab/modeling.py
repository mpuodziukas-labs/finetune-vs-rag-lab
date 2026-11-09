"""Model and adapter registries (swap either through config, no core edit)."""

from typing import Any

from ftlab.config import AdapterCfg
from ftlab.registry import ADAPTERS, MODELS


@MODELS.register("causal_lm")
def causal_lm(cfg: dict[str, Any]) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(cfg["id"], revision=cfg["revision"])
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "right"
    model = AutoModelForCausalLM.from_pretrained(
        cfg["id"], revision=cfg["revision"], dtype=torch.float32
    )
    model.eval()  # type: ignore[no-untyped-call]
    return model, tok


@ADAPTERS.register("lora")
def lora(model: Any, a: AdapterCfg, seed: int) -> Any:
    import torch
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(seed)
    conf = LoraConfig(
        r=a.rank, lora_alpha=a.alpha, lora_dropout=a.dropout,
        target_modules=a.target_modules, task_type="CAUSAL_LM",
    )  # fmt: skip
    return get_peft_model(model, conf)

# Extending the lab

The core never names a dataset, model, adapter or retriever. It asks a registry (`src/ftlab/registry.py`) for the name written in `configs/default.yaml`. To add one, write a module that registers itself and list it under `plugins:`. No core file changes.

| Axis | Registry | Config keys | Contract |
|---|---|---|---|
| Dataset | `DATASETS` | `dataset.name` | `fn(dataset_cfg: dict, cache: Path) -> list[Row]` where `Row(id, text, label)`; must verify its own sha256 pins and raise on mismatch |
| Model | `MODELS` | `model.name`, `model.id`, `model.revision` | `fn(model_cfg: dict) -> (model, tokenizer)`; a causal LM from the model host (provider-a) with a `pad_token` |
| Adapter | `ADAPTERS` | `adapter.name`, `adapter.*` | `fn(model, AdapterCfg, seed) -> model`; trainable parameters must have `lora_` in their name (that is how the audit counts them) |
| Retriever | `RETRIEVERS` | `retriever.name` | `cls(docs: list[str])` with `top_k(query: str, k: int) -> list[int]` |

## Example: swap the model

1. Create `my_models.py` anywhere importable:

   ```python
   from ftlab.registry import MODELS
   from ftlab.modeling import causal_lm   # reuse the loader

   @MODELS.register("my_causal_lm")
   def my_model(cfg):
       return causal_lm(cfg)
   ```

2. In a copy of the config set `plugins: [my_models]`, `model.name: my_causal_lm`, and a new `model.id` and `model.revision` (a commit hash, not a branch name).
3. Run `FTLAB_CONFIG=your.yaml bash scripts/run_all.sh` (it passes `--config` to every step). `make verify` checks the default config only; a swapped config is a separate experiment.

Checks that run on any swap:

- `label_first_ids` refuses a verbalizer whose first tokens collide under the new tokenizer. Rename the offending words in `dataset.classes`.
- `target_modules` must exist in the new architecture. Common attention projection names (`q_proj`, `v_proj`) are the default.
- The audit recomputes the split from data and the configured seed, so a swapped dataset or seed cannot reuse stale receipts: `make verify` goes RED until `make run` is repeated.

## Example: swap the dataset

Register a function returning `Row`s, pin its files by sha256 in config, and list the label-to-word map under `dataset.classes`. The split sizes are `dataset.split.*_per_class`; a class with too few rows makes `make_split` raise rather than silently shrink.

## Example: swap the adapter

Register a function that wraps the model with another `peft` method (for example a different `LoraConfig`) and name it in `adapter.name`. The audit's `adapter_active` check requires that the wrapped model has trainable parameters named `lora_*` and that disabling the adapter changes the logits.

A test of this mechanism with a throwaway plugin lives in `tests/test_registry.py`.

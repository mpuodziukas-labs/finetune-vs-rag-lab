# DESIGN

Goal: a head-to-head of LoRA fine-tuning, retrieval few-shot and zero-shot on one small classification task, on CPU, with receipts a skeptic can re-derive.

## ADR-1: One scoring rule for all approaches

**Decision.** Every method predicts by taking the next-token logits at the end of the prompt, restricted to the first token of each label's one-word verbalizer, and taking the argmax. Training uses cross-entropy on that same first token.

**Why.** Generation plus string matching adds parsing failures that differ per method and costs several forward passes. A restricted argmax is one forward pass, deterministic, and identical across A, B and C, so latency and token counts compare like with like.

**Cost.** The model cannot answer "none of the above"; the task is closed-set by construction. `label_first_ids` raises if two verbalizers share a first token.

## ADR-2: Pool, deduplicate, re-split with our own seed

**Decision.** The official BANKING77 train and test files are pooled for the chosen classes, exact duplicate texts (case and whitespace normalized) are dropped, then a seeded stratified split makes train, dev and test. The train split supports nested 25 / 50 / 100% subsets.

**Why.** The brief requires a seeded split, and exact duplicates across official splits are a known leakage route. **Cost.** Paraphrase-level leakage is not removed. This is stated in the README.

## ADR-3: Receipts are the only source of numbers

**Decision.** Each phase writes `receipts/*.json` with `schema_version`. `analyze` derives `results.json`; `report` rewrites marked README blocks and the SVG; `show KEY` prints one value for `PUBLISH.tsv`. `make verify` fails if the README or any published literal differs from what the receipts produce.

**Why.** A number typed into prose can drift from the run that produced it. **Cost.** README prose cannot contain measured numbers; they live in generated blocks.

## ADR-4: One process per heavy phase

**Decision.** Training, each evaluation and the forgetting probe are separate processes launched sequentially by `scripts/run_all.sh`.

**Why.** Peak RSS is a per-process high-water mark. Separate processes make the training RSS attributable to training, and enforce one heavy job at a time. **Cost.** The model is reloaded per phase; load time is excluded from reported training time and latency.

## ADR-5: Merged adapter for latency, unmerged for the forgetting probe

**Decision.** The fine-tuned model is evaluated after `merge_and_unload()`, the deployment form with no adapter overhead. The forgetting probe uses the unmerged model so the same weights can be scored with the adapter on and off.

**Why.** Reporting latency for an unmerged adapter would handicap A for a reason no production deployment has.

## ADR-6: BM25 as the retriever

**Decision.** Okapi BM25, implemented in about 40 lines, no embedding model.

**Why.** It adds no second model to the CPU budget or the dependency set, and the intents share distinctive words. **Cost.** A dense embedder could retrieve better demonstrations; swapping one in is a registry entry (`RETRIEVERS`), and the comparison would need to be re-run.

## ADR-7: The dev split has two jobs

**Decision.** Dev picks k for retrieval from {2, 4, 8} and draws the per-epoch training curve. No LoRA hyperparameter was tuned; the config values are the first and only setting run.

**Why.** Tuning A on dev while giving B a fixed k would bias the comparison; tuning B's k on dev is the same courtesy A's epochs get. **Cost.** A might improve with tuning. The README says so.

## ADR-8: Independent audit plus planted-defect selftest

**Decision.** `audit` recomputes the split from the data and the configured seed, compares id sets, recomputes accuracy from gold labels, and measures whether the adapter changes the logits. `make selftest` runs the real train/eval/audit code on a tiny random model and requires each planted defect (train/test leak, evaluation on train, wrong seed, adapter of rank 0, metric from the wrong split) to be flagged by its specific check, plus one clean control with zero flags and a config guard that refuses rank 0.

**Why.** A gate that cannot go RED proves nothing. **Cost.** The selftest proves the listed defects are caught, not that no other defect exists.

## ADR-9: Fail closed on empty or short input

**Decision.** Every gate asserts a minimum count (7 test-eval receipts, 15 receipts total, 10 published rows, 7 selftest PASS lines) before trusting a zero-defect result.

## Extension points and upgrade path

Four registries (`DATASETS`, `MODELS`, `ADAPTERS`, `RETRIEVERS`) are filled by modules named in `plugins:` in the config. Swapping the model, the adapter or the dataset is a config edit plus, if the thing is new, one registering module. No core edit. Details and examples: [docs/EXTENDING.md](docs/EXTENDING.md).

| Upgrade | What changes | What stays |
|---|---|---|
| Larger model (for example 360M or 1.7B) | `model.id`, `model.revision`; `make run` takes proportionally longer | split, audit, report, decision rules |
| Different PEFT method | register an adapter; set `adapter.name` | engine, receipts, audit |
| Dense retriever | register a `RETRIEVERS` entry; set `retriever.name` | everything else |
| New dataset | register a dataset, pin sha256, set classes and split sizes | engine, audit, report |
| GPU | the engine uses the default device of the loaded model; moving it to an accelerator needs a device argument in `engine.py`, which is the one place core code would change | receipts and report |
| More seeds | not implemented; receipts carry `seed`, and `analyze` would need a loop over seeds | |

Any swap invalidates old receipts: the audit recomputes the split from the configured seed and data, so `make verify` stays RED until `make run` is repeated.

## Steelman: the strongest case against this lab, and the answer

**Objection.** "A 135M model on 10 classes tells you nothing about the real choice, where retrieval gets a strong model with a long context and fine-tuning gets a tuned hyperparameter sweep. Your fine-tune used one untuned configuration, your retriever is lexical, the test set is 400 rows from one dataset, the prompts are not equalized, the dollar figure is an invented rate, and a perplexity probe is not a forgetting study."

**Answer.**

1. The claim is narrow on purpose. The lab measures this task, this model and this hardware, and every table says so. It does not claim a general ranking.
2. The unequal prompts are the product difference, not noise: a tuned model internalizes the label set, a retrieval system must carry it. Tokens per query are in the table so a reader can price that difference themselves.
3. The untuned LoRA and the lexical retriever are both disclosed as limits. Each can be improved through config or a registry entry, and the harness, split and audit stay fixed so the comparison can be re-run.
4. The dollar figure is labeled an estimate and its rate is one config value; the break-even query count scales linearly with whatever rate the reader substitutes.
5. Wins are declared only by an exact paired test at p < 0.05, so on 400 rows the table says "tie" where the data cannot separate the approaches.

**What the objection gets right and this lab does not fix:** one seed, one dataset, no paraphrase-leak control, no general-capability benchmark. Those are listed in the README Honesty Statement and are the first things to add (see the upgrade table).

## Terms used in this lab

- LoRA fine-tuning: a low-rank adapter trained with peft on the 135M base model (approach A).
- Retrieval-augmented generation: here it means BM25 few-shot retrieval into the prompt of the same base model (approach B), not a vector store.
- Bootstrap confidence intervals: percentile intervals over 10000 resamples of the 0/1 correctness vector, seed from the config.
- Receipts with sha256: every receipt is listed with its sha256 in receipts/SHA256SUMS and re-hashed by the test suite.
- Tiny random model: the untrained few-parameter causal model the selftest builds, registered under the stand-in label `model-a` (ADR 0004).

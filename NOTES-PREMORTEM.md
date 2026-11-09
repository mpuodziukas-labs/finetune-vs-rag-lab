# Pre-mortem (written before the first training run)

Assume the lab shipped and a hostile reader says it proves nothing. Why?

| # | Failure story | Likelihood | Mitigation built in | Check that would catch it |
|---|---|---|---|---|
| 1 | Test rows leaked into training (BANKING77 contains repeated texts across its official splits), so fine-tune and retrieval both look inflated. | High | Pool official train and test, drop exact duplicate texts (case and whitespace normalized), then split with our own seed. Paraphrase leakage is NOT removed and is disclosed. | `audit`: `train_clean`, `eval_not_train`, `split_disjoint`; selftest planted leak |
| 2 | Fine-tune "wins" only because its prompt is short and the others carry a label list and demonstrations, or the scoring rule differs per method. | Medium | One scoring rule for all three (restricted first-token argmax). Prompt differences are disclosed and token counts are reported per method. | `label_first_ids` raises on collisions; tokens column in the results table |
| 3 | A run quietly evaluates the wrong thing (dev instead of test, train instead of test, wrong seed, adapter that is a no-op) and still prints a good number. | Medium | The audit recomputes the split from data and the configured seed, checks the eval ids equal the test ids, recomputes accuracy from gold labels, and checks the adapter changed the logits. | `make selftest` plants each defect and the clean control |
| 4 | CPU latency numbers are noise (other processes, thermal state, first-call warmup). | Medium | One heavy job at a time, untimed warmup, batch size 1, p50 and p95 over 400 queries, machine recorded in `receipts/env.json`. A single laptop is still one machine. | Spread between p50 and p95 is shown in the table |
| 5 | The test set is too small to separate the approaches, and the write-up over-reads a 1-2 point gap. | Medium | 400 test rows; bootstrap 95% CI and exact McNemar on every comparison; the decision table calls a winner only at p < 0.05 and otherwise says tie. | `analyze` computes the winner by rule, not by hand; README table is regenerated and diffed by `make verify` |

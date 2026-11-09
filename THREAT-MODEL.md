# Threat model

Scope: an offline experiment (data download, LoRA training on CPU, evaluation, report). No service, no stored user data, no paid API. Dataset and model files are third-party input. OWASP LLM Top 10 (2025) ids: LLM01 prompt injection, LLM02 sensitive information disclosure, LLM03 supply chain, LLM04 data and model poisoning, LLM08 vector and embedding weaknesses, LLM10 unbounded consumption.

## Assets

| Asset | Why it matters |
|---|---|
| Split integrity | A leak inflates every accuracy |
| Receipts | The README numbers are generated from them |
| Downloaded data and model | A swapped file changes results silently |
| Adapter weights | Gitignored; not published |

## STRIDE

| STRIDE | Threat | OWASP LLM | Control | Test or status | Residual |
|---|---|---|---|---|---|
| Spoofing | A swapped dataset or model file | LLM03, LLM04 | sha256 pin on every download, fail closed | tests/test_p2_platform.py::test_fetch_pinned_fails_closed_on_sha_mismatch | pins trust the first download |
| Tampering | Test rows leak into training | LLM04 | split_disjoint and train_clean audit | tests/test_audit.py::test_leak_flagged | paraphrase leakage not measured |
| Tampering | Receipts edited by hand | none | README numbers regenerated and checked by verify.sh | tests/test_review.py::test_readme_states_seed_and_resamples_that_the_config_uses | a coordinated edit of receipts and pins |
| Repudiation | Tuned on the test split | none | dev-only tuning, AST test | tests/test_review.py::test_tune_k_reads_only_dev_and_train | none known |
| Information disclosure | Secret in tree or history | LLM02 | no API keys used; publish gate scans tree and history | OPEN: gate only (publish-gate.sh), no in-repo unit test | owner runs the gate before push |
| Denial of service | Unbounded download or run | LLM10 | pinned file list; CPU only; no paid API | OPEN: HF download timeout unset | owner: set HF_HUB_DOWNLOAD_TIMEOUT |
| Elevation of privilege | Untrusted input executed | LLM01 | classifier reads text and returns a label; no tool use, no code execution | tests/test_review.py::test_network_guard_blocks_external_connect | prompt injection can change a label, not an action |

Rows with a named test: 5/7; OPEN: 2.

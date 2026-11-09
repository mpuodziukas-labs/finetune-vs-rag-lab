# Threat model (STRIDE) for a fine-tune versus retrieval benchmark

Scope: an offline experiment that downloads a public dataset and a small open model, trains a LoRA adapter on CPU, evaluates three approaches and publishes a README generated from recorded receipts. There is no service, no stored user data and no paid API. The older [THREAT-MODEL.md](../THREAT-MODEL.md) maps the same system to the OWASP LLM ids; this file is the STRIDE view where every row names a control and the test that goes red if the control is removed.

Cassettes: this lab records no HTTP cassettes and replays nothing, so cassette tampering has no direct form here. The recorded artifact that plays the same role is the receipt, covered by rows T3 and T4.

| id | STRIDE class | threat | control | covering test |
|---|---|---|---|---|
| T1 | Spoofing | data poisoning at the source: a dataset or model file is served under the expected name with different content | sha256 pin on every download, fail closed on a mismatch | `tests/test_p2_platform.py::test_fetch_pinned_fails_closed_on_sha_mismatch` |
| T2 | Tampering | data poisoning by leakage: test rows reach the training set and inflate the fine-tune | split disjointness audit flags the leak | `tests/test_audit.py::test_leak_flagged` |
| T3 | Tampering | receipt tampering: a recorded receipt is edited to move a headline number | every receipt is pinned in `receipts/SHA256SUMS`; a changed byte is detected | `tests/test_senior_files.py::test_receipt_pins_verify` |
| T4 | Tampering | receipt tampering by a coordinated edit of prose and receipt | README blocks are regenerated from receipts and compared, so prose cannot drift alone | `tests/test_p2_platform.py::test_evidence_matches_sources` |
| T5 | Repudiation | metric gaming: hyperparameters tuned on the test split, then the result is denied to be tuned | tuning reads only the dev and train splits, proved on the source tree | `tests/test_review.py::test_tune_k_reads_only_dev_and_train` |
| T6 | Repudiation | metric gaming: a score computed on the train split or one that does not match its own predictions | the audit flags an evaluation on train and a metric that disagrees with its predictions | `tests/test_audit.py::test_eval_on_train_flagged` |
| T7 | Repudiation | metric gaming: an adapter that changes nothing is reported as a fine-tune win | the audit flags a no-op adapter | `tests/test_audit.py::test_noop_adapter_flagged` |
| T8 | Information disclosure | a key-shaped string or env file lands in the tree | the accountability layer scans for key shapes and env files; its own selftest plants each | `tests/test_accountability.py::test_selftest_green` |
| T9 | Denial of service | a test or run reaches an external host and hangs or spends money | the network guard fails any non-loopback connect | `tests/test_review.py::test_network_guard_blocks_external_connect` |
| T10 | Elevation of privilege | the container runs as root | multi-stage image whose last user is not root; compose drops all capabilities | `tests/test_senior_files.py::test_dockerfile_nonroot_healthcheck` |
| T11 | Elevation of privilege | the container writes to its root file system or reaches a network | compose mounts the root read-only with no network | `tests/test_senior_files.py::test_compose_hardened` |
| T12 | Tampering | dependency risk: the lock changes without the SBOM, or a package floats | every freeze line is pinned; the SBOM is checked against the freeze file | `tests/test_senior_files.py::test_sbom_drift_red` |
| T13 | Tampering | dependency risk: a freeze line is unpinned | pin shape check over the freeze file | `tests/test_senior_files.py::test_freeze_is_pinned` |
| T14 | Tampering | dependency risk: a CI action is moved to a hostile commit | every action is pinned to a 40-hex commit | `tests/test_p2b_features.py::test_every_workflow_action_is_sha_pinned` |
| T15 | Tampering | stale receipts (CIA letter: Integrity): a train receipt outlives an edit to the producer source, so a number looks measured by code that no longer exists | verify recomputes `code_sha` over the derived producer set and compares it with the receipt, or with the receipt's own `producer_files` manifest; least privilege: the check only reads receipts and never rewrites one | `tests/test_qa_pins.py::test_check_receipts_flags_stale_code_sha` |

Residual risk, stated: the first download is trusted when the pin was taken; paraphrase leakage between splits is not measured; a coordinated edit of receipts and their pin file by someone with write access is caught only by review, because the owner reseals the pins on purpose.

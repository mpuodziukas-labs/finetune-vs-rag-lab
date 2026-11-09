# Changelog

## 0.1.0
- Fine-tune versus retrieval comparison with hash-pinned receipts, bootstrap statistics and a selftest of planted defects.
- Senior files: dependency freeze, runbook, decision records, term map.
- Spec and trace: SPEC.md with Given/When/Then rows and a status table, plus a two-way trace test over the collected tests.
- Threat model: docs/THREAT-MODEL.md with STRIDE rows for data poisoning, receipt tampering, metric gaming and dependency risk, each with a covering test.
- SLO: docs/SLO.md with one objective, burn-rate windows and an error budget.
- Container: multi-stage non-root Dockerfile with a HEALTHCHECK and a hardened compose.yaml, parsed by tests and never built by verify.
- Mutants: scripts/mutants.py with five planted defects, each run against an unmutated control first.
- SBOM: regenerated from requirements.freeze.txt, with a drift test and the same check in ci-local.sh.
- Receipt pins: a test re-hashes every line of receipts/SHA256SUMS and detects a tampered copy.
- Ownership and third-party text: root CODEOWNERS with the owner placeholder; the README states that dataset READMEs are verbatim upstream text.
- Receipts: train_f25, train_f50 and train_f100 carry a code_sha of the six producer sources; a stale or missing value is flagged by ftlab report --check. Retrained once with scripts/run_all.sh; README result blocks and PUBLISH.tsv follow the new latency and training figures. SPEC.md R26 lists the two new tests.
- QA pins: tests/test_qa2_pins.py holds three strict xfails for gaps found after the receipt and vendor-rule fixes (producer scope omits config and registry, model family and host names in README and EXTENDING prose, no threat-model row for stale receipts) and two controls that pass; SPEC.md R27.
- Producer files: the set that stamps train receipts is derived from the package sources minus an explicit exclude list, so config.py and registry.py are covered; train receipts get a producer_files manifest on the next retrain, and report --check compares a manifest receipt with its own list and an older receipt with the legacy list. Current receipts predate the derived list (EVIDENCE.md).
- Prose: the model family and its host sit behind the stand-ins model-b and provider-a (docs/TERMS.tsv); both names are in the vendor-word test; README names HF_HUB_OFFLINE as the switch that turns the cold clone RED.
- Threat model: row T15 for stale receipts (Integrity, read-only check) covered by test_check_receipts_flags_stale_code_sha.
- QA pins: the three R27 xfails are closed and removed; six tests added for the derived set, the manifest check and the planted REDs.

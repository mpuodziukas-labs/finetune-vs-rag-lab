# SPEC: finetune-vs-rag-lab

Each requirement: Given, When, Then, and the test names that prove it. `tests/test_spec_trace.py` checks the two-way trace: every requirement lists tests that exist, and every collected test is listed here. A `Files:` line names a whole sealed test file (the vendored accountability suite). The status table at the end is derived from the rows and checked by the same test.

### R01 Seeded stratified split
Given labeled rows and a seed, When the split is made, Then train, dev and test are disjoint, sizes match the spec per class, the same seed gives the same split, a different seed gives a different one, and a class with too few rows raises.
Tests: test_disjoint_and_sizes, test_deterministic_and_seed_sensitive, test_insufficient_rows_raises, test_split_sizes_and_disjoint_on_hand_fixture

### R02 Nested train fractions
Given a train set, When subsets of 25, 50 and 100 percent are taken, Then each smaller subset is a prefix of the larger and no class is ever empty.
Tests: test_nested_fractions, test_subset_train_is_nested_and_never_empty_per_class

### R03 BM25 retrieval
Given a small corpus, When a query is scored, Then the document with the rare matching term ranks first, k larger than the corpus returns all documents in a deterministic order, ties break by lower index, and a negative k is refused.
Tests: test_rare_term_wins, test_k_larger_than_corpus_and_ties_deterministic, test_bm25_negative_k_refused_and_zero_k_empty

### R04 Bootstrap interval
Given a 0/1 vector and a seed, When the interval is computed, Then it is deterministic, contains the mean, collapses on a constant vector, matches known values, and empty input is refused with a clear error.
Tests: test_bootstrap_degenerate, test_bootstrap_contains_mean_and_is_deterministic, test_bootstrap_known_values_and_seed, test_bootstrap_empty_input_is_refused_clearly

### R05 Exact McNemar test
Given paired 0/1 vectors, When the test runs, Then the discordant counts and the two-sided p match hand computation, a symmetric split gives p of 1.0, and identical vectors give p of 1.0.
Tests: test_mcnemar_known_values, test_mcnemar_symmetric_and_empty, test_mcnemar_hand_computed

### R06 Latency percentiles
Given a list of latencies, When p50 and p95 are taken, Then they equal the linear-interpolation percentiles.
Tests: test_percentiles

### R07 Audit catches planted defects
Given receipts, When the audit runs, Then a clean set passes, and a leaked test row, an evaluation on the train split, a wrong seed, a no-op adapter and a metric that does not match its predictions are each flagged, and an empty receipt is flagged instead of crashing.
Tests: test_clean_passes, test_leak_flagged, test_eval_on_train_flagged, test_wrong_seed_flagged, test_noop_adapter_flagged, test_metric_not_matching_flagged, test_audit_empty_receipt_is_flagged_not_crashed

### R08 Tuning reads only dev
Given the tuning code, When its source is parsed, Then it reads the dev and train splits and never the test split.
Tests: test_tune_k_reads_only_dev_and_train

### R09 Tests cannot reach the network
Given any test, When it opens a connection to a non-loopback address, Then the guard raises.
Tests: test_network_guard_blocks_external_connect

### R10 Pinned downloads fail closed
Given a downloaded file whose sha256 differs from its pin, When the fetch verifies it, Then the fetch raises and nothing is used.
Tests: test_fetch_pinned_fails_closed_on_sha_mismatch

### R11 Registry extension
Given the retriever registry, When a duplicate or unknown name is used, a plugin is added, or a rank-zero or bad-schema entry is offered, Then duplicates and unknowns are refused, a plugin extends the registry without a core edit, and bad entries are rejected.
Tests: test_duplicate_and_unknown, test_plugin_extends_without_core_edit, test_rank_zero_and_bad_schema_rejected

### R12 README numbers come from receipts
Given the receipts, When the report is generated, Then marked README blocks are replaced and a missing marker is an error, the seed and resample count in prose equal the config, the transcript equals the README tail, the evidence page equals its sources, and the examples reproduce the README numbers.
Tests: test_replace_block_roundtrip_and_missing_marker, test_readme_states_seed_and_resamples_that_the_config_uses, test_transcript_matches_readme, test_evidence_matches_sources, test_examples_reproduce_readme_numbers

### R13 README honesty and budget
Given the README, When it is checked, Then it stays under 1800 words with no repeated long line, states that its headline is not comparable to the published figure, cites only tests that exist in its objections and comparison tables, and links the examples.
Tests: test_readme_under_1800_words_and_links_examples, test_readme_budget, test_community_files_exist_and_readme_labels_comparability, test_objections_cite_real_test_lines, test_objections_and_compared_with

### R14 CI is pinned and matches local
Given the workflows, When they are parsed, Then every action is pinned to a 40-hex commit with a version comment, CI and release call the local script, dependabot exists, and the local script fails closed on a missing tool.
Tests: test_every_workflow_action_is_sha_pinned, test_codeql_workflow_pinned_and_scheduled, test_release_workflow_tag_trigger_runs_ci_local, test_actions_pinned, test_ci_calls_ci_local_and_dependabot, test_precommit_calls_ci_local_and_ci_local_fails_closed

### R15 Community, security and citation files
Given the repository, When its community files are read, Then issue forms, a pull request template, CODEOWNERS, a code of conduct, a security policy, a citation file, references and a devcontainer follow their templates.
Tests: test_issue_forms_and_pr_template, test_codeowners_and_conduct, test_security_and_citation_follow_template_fields, test_citation_and_references, test_devcontainer_is_python_311_with_install

### R16 Rubric copy and root threat model
Given the rubric and the root threat model, When they are read, Then the rubric copy and score match and every root threat row names an existing test or says OPEN.
Tests: test_rubric_copy_and_score, test_threat_model_rows

### R17 SBOM follows the freeze file
Given requirements.freeze.txt, When the SBOM is checked, Then it parses as CycloneDX, lists exactly the pinned packages, a drifted freeze file makes the check exit 1, and every freeze line is pinned.
Tests: test_sbom_parses, test_sbom_matches_freeze, test_sbom_drift_red, test_freeze_is_pinned

### R18 Accountability layer
Given the lab, When the vendored oracle runs, Then its planted defects are each red, a red tree exits nonzero, heal stops after two rounds and proposals are one row per cause.
Files: tests/test_accountability.py

### R19 Container is multi-stage, non-root and read-only
Given the Dockerfile and compose.yaml, When they are parsed (no build), Then the image has two or more stages, the last user is not root, a HEALTHCHECK exists, and compose drops capabilities, mounts a read-only root and has no network.
Tests: test_dockerfile_nonroot_healthcheck, test_compose_hardened

### R20 STRIDE rows each have a covering test
Given docs/THREAT-MODEL.md, When it is parsed, Then it covers data poisoning, receipt tampering, metric gaming and dependency risk, and every row names a control and an existing test.
Tests: test_docs_threat_model_rows

### R21 One SLO with burn-rate windows
Given docs/SLO.md, When it is parsed, Then it states one objective, an error budget equal to one minus that objective, two burn-rate windows and a page rule.
Tests: test_slo_doc

### R22 Planted mutants go red
Given scripts/mutants.py, When it runs, Then every mutation text applies exactly once, an absent text and an unseen defect are both reported as not red, and the original tree is never written.
Tests: test_mutants_applicable, test_mutants_selftest

### R23 Receipt hash pins hold
Given receipts/SHA256SUMS, When each line is re-hashed, Then every listed file exists with the listed sha256, every receipt json is listed, and a tampered copy is detected.
Tests: test_receipt_pins_verify

### R24 Ownership and third-party text
Given the repository root, When it is read, Then CODEOWNERS carries the owner placeholder and the README states that dataset READMEs are verbatim upstream text.
Tests: test_root_codeowners, test_third_party_text_section

### R25 Spec trace holds both ways
Given this file and the collected tests, When they are compared, Then every row lists existing tests, every test is listed in a row, the status table matches the rows, and a phantom, an unlisted or a doubly listed test turns the trace red.
Tests: test_trace_two_way, test_trace_goes_red_on_planted_gaps, test_status_table_matches

### R26 Adversarial QA pins
Given the five mutants that survived the first suite, When each is replayed, Then the no-op adapter floor, the forged-hash overlap check, the receipt accuracy tolerance and the report check exit code are each pinned by a failing test, the terms table is true row by row, and no vendor word appears in the docs (the source test is a strict xfail until a spec renames the library class imports).
Tests: test_zero_logit_delta_adapter_flagged, test_overlapping_split_lists_with_forged_hash_flagged, test_check_receipts_flags_small_accuracy_drift, test_check_receipts_clean_control, test_report_check_exits_one_on_stale_readme, test_terms_rows_are_true, test_no_vendor_words_in_docs, test_no_vendor_words_in_src, test_check_receipts_flags_stale_code_sha, test_vendor_rule_flags_strings_and_passes_library_imports

### R27 Second adversarial QA pins
Given the second adversarial pass, When its findings are replayed, Then the producer-file set is read at runtime from the committed manifest src/ftlab/PRODUCERS.txt (never from git, so the container and a pip install import), the manifest equals the git-tracked package sources minus the exclude list (a tracked module missing from it fails; a missing or empty manifest is a named RED; no work tree is a named RED and exit 1 for the derivation) and covers every imported module, a train receipt is checked against its own producer_files manifest (older receipts against the legacy list), no model family or host name stays in prose, and the threat model has a row for stale receipts; the scanners each pass a planted-term control.
Tests: test_import_helper_finds_a_known_edge, test_derived_producer_set_covers_config_and_registry, test_derive_producer_files_admits_a_planted_source_file, test_derive_producer_files_ignores_an_untracked_module, test_derive_producer_files_outside_a_git_work_tree_is_red, test_manifest_equals_the_git_derivation_on_the_real_tree, test_manifest_drift_is_red, test_missing_or_empty_manifest_is_a_named_red, test_import_works_without_git_and_counts_the_manifest, test_import_without_the_manifest_is_a_named_red, test_legacy_sha_moves_on_any_other_producer_edit, test_receipt_manifest_is_the_basis_of_the_sha_check, test_receipt_manifest_missing_a_current_producer_is_stale, test_receipt_manifest_naming_a_missing_file_is_red, test_producer_files_cover_every_imported_module, test_prose_scan_flags_planted_term_and_passes_clean_text, test_no_model_family_or_host_names_in_prose, test_threat_model_has_a_row_for_stale_receipts

## Status

<!-- STATUS:BEGIN -->
| id | status | tests |
|---|---|---|
| R01 | tested | 4 |
| R02 | tested | 2 |
| R03 | tested | 3 |
| R04 | tested | 4 |
| R05 | tested | 3 |
| R06 | tested | 1 |
| R07 | tested | 7 |
| R08 | tested | 1 |
| R09 | tested | 1 |
| R10 | tested | 1 |
| R11 | tested | 3 |
| R12 | tested | 5 |
| R13 | tested | 5 |
| R14 | tested | 6 |
| R15 | tested | 5 |
| R16 | tested | 2 |
| R17 | tested | 4 |
| R18 | tested | 0 |
| R19 | tested | 2 |
| R20 | tested | 1 |
| R21 | tested | 1 |
| R22 | tested | 2 |
| R23 | tested | 1 |
| R24 | tested | 2 |
| R25 | tested | 3 |
| R26 | tested | 10 |
| R27 | tested | 18 |
<!-- STATUS:END -->

R18 is traced by the whole sealed file named in its `Files:` line (6 tests, byte-identical across labs), so its count here is 0.

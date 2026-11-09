# Objections and replies

Each reply names the test that enforces it. The last column is the file and line of that test; `tests/test_p2b_features.py` fails if the line no longer holds the named test.

| Objection | Reply | Source (file:line) |
|---|---|---|
| A solo project has no second reviewer. | The audit is the reviewer; it fails on a planted leak, wrong seed or no-op adapter (`tests/test_audit.py::test_leak_flagged`). | `tests/test_audit.py:36` |
| No production traffic. | Stated: this is a controlled comparison on a laptop CPU, not a deployment claim (`tests/test_review.py::test_community_files_exist_and_readme_labels_comparability`). | `tests/test_review.py:104` |
| AI-assisted, so numbers may be invented. | Every table is generated from receipts and the README seed claim is checked against the config (`tests/test_review.py::test_readme_states_seed_and_resamples_that_the_config_uses`). | `tests/test_review.py:95` |
| Small N (400 test rows, one seed). | Intervals and exact McNemar are printed, ties are called ties (`tests/test_review.py::test_mcnemar_hand_computed`); more seeds are open. | `tests/test_review.py:20` |
| No employer or real users behind it. | Public dataset and model, every download sha256-pinned and failing closed (`tests/test_p2_platform.py::test_fetch_pinned_fails_closed_on_sha_mismatch`). | `tests/test_p2_platform.py:163` |

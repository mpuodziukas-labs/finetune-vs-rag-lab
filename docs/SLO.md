# SLO

This lab is an offline experiment with no deployed service, so the objective is about the gate that guards the claims: the reproducibility gate (`bash scripts/verify.sh`, `HEAVY=0`) run by CI on every push. The service level indicator is the share of CI runs on the default branch in which that gate ends GREEN. A run that ends RED because of a real defect burns budget; a cancelled run does not count.

objective: 0.95
error budget: 0.05

Status: not yet measured. The workflow exists and the arithmetic below is tested (`tests/test_senior_files.py::test_slo_doc`); the first measured value arrives once the repository is published and CI has history. No measured value is claimed here.

## Burn rate
`burn(window) = failure_rate(window) / error budget`. A burn of 1.0 spends the budget exactly over the period.

| window | length | used for |
|---|---|---|
| long | 20 runs | confirms the problem is real |
| short | 5 runs | confirms it is still happening |

page: both windows burn above 6.0

worked example: 6 failures in 20 runs, burn 6.0

The page needs both windows, so one flaky run alone does not page and an old burst that has ended does not page.

## Signals
- Each CI run prints one verdict line: `GREEN n/n checks` or `RED k/n checks failed: names`.
- `demo/verify.transcript.txt` is the saved output of the last local full run.
- `receipts/SHA256SUMS` pins the recorded measurements, so a RED from drift names the file.

## Limits
Run counts need CI history that does not exist yet. A production deployment would export the verdict as a metric and evaluate the same burn rule in a monitoring backend.

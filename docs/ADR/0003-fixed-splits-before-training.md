# ADR 0003: splits fixed and recorded before training

Status: accepted.

Context: leakage between train and test is the commonest way this comparison goes wrong.

Decision: `receipts/split.json` is written first and a test checks no test item appears in training.

Alternative: split inside the training script. Rejected: the split is then not auditable.

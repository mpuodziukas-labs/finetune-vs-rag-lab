# ADR 0001: hash-pinned receipts over logs

Status: accepted.

Context: a comparison is only worth reading if the numbers can be re-checked.

Decision: every run writes a JSON receipt, and `receipts/SHA256SUMS` pins each one. Verify re-reads them.

Alternative: free-form logs. Rejected: they cannot be diffed against the README table.

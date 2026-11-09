# Accountability

Run `python3 -P scripts/accountability_check.py` for one verdict line per rule and a final `accountability: GREEN N/N` or `RED`. Add `--live` to also run `scripts/verify.sh` twice (I4, A1). `pytest tests/test_accountability.py` runs the planted-defect selftest, so the test suite alone proves the layer.

Heal is bounded: `bash scripts/heal.sh` makes at most 2 rounds, then writes one row to `OPEN.tsv` and stops. It refuses when tests or README differ from `receipts/SHA256SUMS`; the owner accepts such an edit with `bash scripts/heal.sh --seal`. `python3 -P scripts/propose.py` writes `PROPOSALS.md` rows only and applies nothing.

| rule | letter | what it proves | test | heal path |
|---|---|---|---|---|
| LP1 | least privilege | every workflow has a top-level read default; a write scope sits in one job with a why comment | selftest LP1 | owner |
| LP2 | least privilege | no job holds contents and pull-requests write together | selftest LP2 | owner |
| LP3 | least privilege | no sudo, chmod 777, pipe to shell or write outside the repo in scripts | selftest LP3 | owner |
| LP4 | least privilege | devcontainer and Dockerfiles end as a non-root user | selftest LP4 | owner |
| LP5 | least privilege | dependabot and pre-commit exist, so a vulnerable pin has an automatic fix path | selftest LP5 | owner |
| C1 | confidentiality | no key-shaped string or env file in the tree | selftest C1 | owner |
| C2 | confidentiality | gitignore covers env files, pem, key and cost ledgers | selftest C2 | owner |
| C3 | confidentiality | no private address, owner home path, vault path or key in a URL | selftest C3 | owner |
| I1 | integrity | PUBLISH.tsv is well formed and each fold ratio has a backing row or linked file | selftest I1 | owner |
| I2 | integrity | receipts, demo, tests and README match `receipts/SHA256SUMS` (paths listed in the optional `receipts/UNSEALED.txt`, one per line, hold re-measured values and are left out of the seal) | selftest I2 | heal.sh reseals receipts after a green verify |
| I3 | integrity | every action is pinned to a 40-hex commit | selftest I3 | owner |
| I4 | integrity | two consecutive verify runs print the same verdict line | selftest I4 | owner |
| A1 | availability | `HEAVY=0 bash scripts/verify.sh` finishes in under 120 s | selftest A1 | owner |
| A2 | availability | ci-local.sh fails closed when a tool is missing | selftest A2 | owner |
| A3 | availability | a restore path or fresh-copy transcript exists and a test cites it | selftest A3 | owner |
| SH1 | self-heal | heal.sh exists, logs to OPEN.tsv and refuses edited tests | selftest SH1 | owner |
| SH2 | self-improve | propose.py exists and writes proposals only | selftest SH2 | owner |
| SH3 | bounded | heal.sh sets MAX_ROUNDS=2 and stops with `heal: OPEN after 2 rounds` | selftest SH3 | owner |
| DOC | integrity | this table lists every rule | selftest DOC | owner |

# Runbook

| Symptom | Check | Action |
|---|---|---|
| verify is RED on receipts | `bash scripts/verify.sh` names the gate | re-run `python3 -P scripts/evidence_md.py --check`; a hash mismatch means a receipt changed, restore it from git |
| README table differs from receipts | verify gate `README matches receipts` | regenerate the table from receipts; never edit the numbers by hand |
| SBOM drifts from the freeze file | `make sbom` then `python3 -P scripts/sbom_stdlib.py --input requirements.freeze.txt --out SBOM.cdx.json --check` | re-export `requirements.freeze.txt`, run `make sbom` |
| accountability gate RED | `python3 -P scripts/accountability_check.py .` | fix the named rule, then `--reseal` |

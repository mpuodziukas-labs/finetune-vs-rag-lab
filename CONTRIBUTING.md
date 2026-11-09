# Contributing

1. Install from the lockfile: `uv sync --group dev --frozen`
2. Run `bash scripts/verify.sh`. The last line must be a `GREEN N/N checks` line before and after your change.
3. Write the failing test first, then the smallest change that makes it pass.
4. Keep every number in the README reproducible by a command. Add a row to `PUBLISH.tsv` for a new number.
5. Tests must not use the network (an autouse guard enforces it). Recorded model output goes in cassettes and is replayed.
6. Do not commit keys. `scripts/secret_scan.py` is part of the gate in the retrieval lab.

Report a defect with the command you ran and the full output of its last 15 lines.

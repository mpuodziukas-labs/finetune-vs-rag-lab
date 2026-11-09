#!/usr/bin/env python3
# ruff: noqa
# fmt: off
# Vendored byte-identical into every lab; style is pinned by the sha, not by the lab config.
"""Self-improving by proposal only: read the last N verify and heal transcripts, write PROPOSALS.md.

    python3 -P scripts/propose.py [--root DIR] [--n 5] [TRANSCRIPT ...]

A RED line seen two or more times becomes exactly one proposal row. Writes PROPOSALS.md and nothing else.
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

FIX = {
    "LP1": ("add top-level permissions: contents: read; keep a write scope in its one job with a '# why:' comment", "owner or workflow lane"),
    "LP2": ("split the job so contents and pull-requests writes never share a token", "workflow lane"),
    "LP3": ("replace sudo, chmod 777, pipe-to-shell or out-of-repo writes with repo-local steps", "script owner"),
    "LP4": ("set remoteUser to a non-root user in devcontainer.json", "lab owner"),
    "LP5": ("add dependabot.yml (github-actions ecosystem) and .pre-commit-config.yaml", "lab owner"),
    "C1": ("move the secret out of the tree and rotate it", "owner"),
    "C2": ("add the missing pattern to .gitignore", "lab owner"),
    "C3": ("replace the literal with a placeholder", "lab owner"),
    "I1": ("add a PUBLISH.tsv row for the number or drop the number", "lab owner"),
    "I2": ("re-run verify.sh then heal.sh to reseal receipts", "heal.sh"),
    "I3": ("re-pin the action to a 40-hex commit from its tag", "workflow lane"),
    "I4": ("make verify.sh print the same verdict line twice", "verify owner"),
    "A1": ("run verify with HEAVY=0 and cut the slowest step", "verify owner"),
    "A2": ("make ci-local.sh exit non-zero when a tool is missing", "ci-local owner"),
    "A3": ("regenerate demo/verify.transcript.txt from a fresh copy and cite it in a test", "lab owner"),
}


def main(argv: list[str]) -> int:
    root = Path(".")
    n = 5
    paths: list[Path] = []
    it = iter(argv)
    for a in it:
        if a == "--root":
            root = Path(next(it))
        elif a == "--n":
            n = int(next(it))
        else:
            paths.append(Path(a))
    if not paths:
        cands = sorted((root / ".accountability").glob("*.log"), key=lambda p: p.stat().st_mtime) if (root / ".accountability").is_dir() else []
        t = root / "demo" / "verify.transcript.txt"
        paths = (cands + ([t] if t.is_file() else []))[-n:]
    paths = paths[-n:]
    seen: Counter[tuple[str, str]] = Counter()
    for p in paths:
        if not p.is_file():
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if re.search(r"\bRED\b", ln) and not ln.startswith(("accountability:", "heal:")):
                first = ln.split()[0]
                rid = first if re.fullmatch(r"[A-Z]+\d*", first) else "OTHER"
                seen[(rid, ln)] += 1
    rows = [
        f"| {rid} | {ln} | {c} | {FIX.get(rid, ('inspect the first occurrence', 'lab owner'))[0]} | {FIX.get(rid, ('', 'lab owner'))[1]} |"
        for (rid, ln), c in sorted(seen.items())
        if c >= 2
    ]
    body = "# Proposals\n\nRows only; nothing here is applied. A RED seen twice or more across the last transcripts.\n\n"
    if rows:
        body += "| rule | failed line | times | cheapest fix | who presses |\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n"
    else:
        body += "No RED line repeated.\n"
    (root / "PROPOSALS.md").write_text(body, encoding="utf-8")
    print(f"propose: {len(rows)} proposal rows from {len(paths)} transcripts")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

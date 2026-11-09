"""Two-way trace between SPEC.md and the collected tests. Run directly to print `spec-trace: N/N`."""

import functools
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDORED = "tests/test_accountability.py"  # sealed and byte-identical across labs; traced by a Files: line


@functools.cache
def collected() -> frozenset[str]:
    """Names of every test pytest collects outside the vendored file (the source of truth, not a parse)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-o", "addopts=", "-p", "no:cacheprovider", "tests"],
        cwd=ROOT, capture_output=True, text=True, timeout=240, check=False,
    )
    names: set[str] = set()
    for ln in r.stdout.splitlines():
        m = re.match(r"(tests/[\w.]+)::(\w+)", ln)
        if m and m.group(1) != VENDORED:
            names.add(m.group(2))
    return frozenset(names)


def parse_spec() -> dict[str, dict[str, list[str]]]:
    reqs: dict[str, dict[str, list[str]]] = {}
    cur = ""
    for line in (ROOT / "SPEC.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"### (R\d\d)\b", line)
        if m:
            cur = m.group(1)
            reqs[cur] = {"tests": [], "files": []}
        elif line.startswith("Tests: ") and cur:
            reqs[cur]["tests"] = [t.strip() for t in line[7:].split(",")]
        elif line.startswith("Files: ") and cur:
            reqs[cur]["files"] = [t.strip() for t in line[7:].split(",")]
    return reqs


def trace(
    reqs: dict[str, dict[str, list[str]]] | None = None, funcs: frozenset[str] | None = None
) -> tuple[int, int, list[str]]:
    reqs = parse_spec() if reqs is None else reqs
    funcs = collected() if funcs is None else funcs
    bad: list[str] = []
    ok = 0
    for r, d in reqs.items():
        missing = [t for t in d["tests"] if t not in funcs]
        files_ok = all((ROOT / f).is_file() for f in d["files"])
        if (d["tests"] or d["files"]) and not missing and files_ok:
            ok += 1
        else:
            bad.append(f"{r}: tests missing {missing} or files absent {d['files']}")
    listed = [t for d in reqs.values() for t in d["tests"]]
    for t in sorted(funcs - set(listed)):
        bad.append(f"{t}: collected but not listed in SPEC.md")
    for t in sorted({x for x in listed if listed.count(x) > 1}):
        bad.append(f"{t}: listed under more than one requirement")
    return ok, len(reqs), bad


def status_rows() -> dict[str, int]:
    text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    block = text.split("<!-- STATUS:BEGIN -->")[1].split("<!-- STATUS:END -->")[0]
    return {m.group(1): int(m.group(3)) for m in re.finditer(r"^\| (R\d\d) \| (\w+) \| (\d+) \|$", block, re.M)}


def test_trace_two_way() -> None:
    ok, n, bad = trace()
    assert n >= 25 and ok == n and not bad, bad


def test_trace_goes_red_on_planted_gaps() -> None:
    """A phantom test name, an unlisted test and a double listing are each reported (the check can fail)."""
    reqs = {"R01": {"tests": ["test_a", "test_phantom"], "files": []}, "R02": {"tests": ["test_a"], "files": []}}
    ok, n, bad = trace(reqs, frozenset({"test_a", "test_unlisted"}))
    text = " ".join(bad)
    assert (ok, n) == (1, 2) and "test_phantom" in text and "test_unlisted" in text and "more than one" in text, bad


def test_status_table_matches() -> None:
    reqs = parse_spec()
    rows = status_rows()
    assert set(rows) == set(reqs), (sorted(set(rows) ^ set(reqs)))
    wrong = {r: (rows[r], len(d["tests"])) for r, d in reqs.items() if rows[r] != len(d["tests"])}
    assert not wrong, wrong


if __name__ == "__main__":
    ok, n, bad = trace()
    print("\n".join(bad))
    print(f"spec-trace: {ok}/{n}")
    sys.exit(0 if ok == n and not bad else 1)

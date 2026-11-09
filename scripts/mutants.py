"""Mutation spot-check. Copies the lab to a temp dir, plants one defect per mutant there, runs the named test, expects RED.

    mutants.py            run every mutant; prints one line each and `mutants: K/K RED`; exit 1 unless all are RED
    mutants.py --list     name, file, test per row (tab separated)
    mutants.py --check    every mutation text applies exactly once (no test run)
    mutants.py --selftest a text-absent mutant and an unseen defect must both be called not-RED

Each test is first run on the unmutated copy and must pass, so a test that is red for another reason cannot score a kill.
The original tree is never written: its mutated files are hashed before and after.
"""

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IGNORE = shutil.ignore_patterns(
    ".venv", ".git", "tmp", "_attic", "data", "artifacts", "__pycache__", ".mypy_cache", ".ruff_cache", ".pytest_cache", "*.bak-*", ".accountability"
)
VENV_PY = ROOT / ".venv" / "bin" / "python"
PY = str(VENV_PY) if VENV_PY.exists() else sys.executable

Mutant = tuple[str, str, str, str, str]  # name, file, old text, new text, test id
MUTANTS: list[Mutant] = [
    ("M1 McNemar p not doubled", "src/ftlab/stats.py", "min(1.0, 2.0 * tail)", "min(1.0, 1.0 * tail)", "tests/test_stats.py::test_mcnemar_known_values"),
    ("M2 bootstrap ignores the seed", "src/ftlab/stats.py", "rng = np.random.default_rng(seed)", "rng = np.random.default_rng()", "tests/test_stats.py::test_bootstrap_contains_mean_and_is_deterministic"),
    ("M3 train overlaps dev", "src/ftlab/splits.py", 'split["train"] += shuffled[t + d : t + d + spec.train_per_class]', 'split["train"] += shuffled[t : t + spec.train_per_class]', "tests/test_splits.py::test_disjoint_and_sizes"),
    ("M4 retriever returns one extra", "src/ftlab/retrieve.py", "return order[:k]", "return order[: k + 1]", "tests/test_retrieve.py::test_rare_term_wins"),
    ("M5 ties break the wrong way", "src/ftlab/retrieve.py", "key=lambda i: (-self.score(query, i), i)", "key=lambda i: (-self.score(query, i), -i)", "tests/test_retrieve.py::test_k_larger_than_corpus_and_ties_deterministic"),
]


def digest(files: list[str]) -> str:
    return hashlib.sha256(b"".join((ROOT / f).read_bytes() for f in sorted(files))).hexdigest()


def applies(m: Mutant) -> bool:
    return (ROOT / m[1]).read_text(encoding="utf-8").count(m[2]) == 1


def pytest_rc(test: str, cwd: Path) -> int:
    r = subprocess.run([PY, "-P", "-m", "pytest", test, "-p", "no:cacheprovider"], cwd=cwd, capture_output=True, text=True, timeout=300, check=False)
    return r.returncode


def run_one(m: Mutant) -> tuple[bool, str]:
    name, rel, old, new, test = m
    work = Path(tempfile.mkdtemp(prefix="mut-"))
    dest = work / "lab"
    shutil.copytree(ROOT, dest, ignore=IGNORE)
    src = (dest / rel).read_text(encoding="utf-8")
    if src.count(old) != 1:
        return False, f"{name}: NOT-APPLIED: text found {src.count(old)} times in {rel}, expected 1"
    if pytest_rc(test, dest) != 0:
        return False, f"{name}: CONTROL-RED: {test} fails on the unmutated copy"
    (dest / rel).write_text(src.replace(old, new), encoding="utf-8")
    red = pytest_rc(test, dest) == 1  # exit 1 = tests ran and failed; 2 or 4 would be a harness error, not a kill
    return red, f"{name}: {'RED' if red else 'SURVIVED'} ({test.split('::')[1]})"


def main(argv: list[str]) -> int:
    if "--list" in argv:
        for m in MUTANTS:
            print(f"{m[0]}\t{m[1]}\t{m[4]}")
        return 0
    if "--check" in argv:
        ok = sum(applies(m) for m in MUTANTS)
        print(f"mutants: {ok}/{len(MUTANTS)} applicable")
        return 0 if ok == len(MUTANTS) else 1
    muts = MUTANTS
    if "--selftest" in argv:
        muts = [
            ("S1 text absent", "src/ftlab/stats.py", "no such text anywhere", "x", "tests/test_stats.py::test_percentiles"),
            ("S2 unseen defect", "src/ftlab/stats.py", "def percentiles(", "def percentiles(  # unseen\n    ", "tests/test_stats.py::test_percentiles"),
        ]
    files = sorted({m[1] for m in muts})
    before = digest(files)
    reds = 0
    for m in muts:
        red, line = run_one(m)
        print(line)
        reds += red
    if digest(files) != before:
        print("mutants: RED original tree changed")
        return 1
    if "--selftest" in argv:
        print(f"mutants: selftest {len(muts) - reds}/{len(muts)}")
        return 0 if reds == 0 else 1
    print(f"mutants: {reds}/{len(muts)} RED, original restored (never written)")
    return 0 if reds == len(muts) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""The producer-file manifest: PRODUCERS.txt lists the source files that shape a train receipt.

Runtime only reads the file. Regenerate it in a git checkout with `python src/ftlab/producers.py` (stdlib only, runs without importing the package).
"""

import subprocess
import sys
from pathlib import Path

MANIFEST = "PRODUCERS.txt"
# Source files that do not shape a train receipt: the package marker, this manifest tool, the checks that read receipts, the selftest, the unused audit/forget/retrieve/stats helpers.
PRODUCER_EXCLUDE = ("__init__.py", "audit.py", "forget.py", "producers.py", "report.py", "retrieve.py", "selftest.py", "stats.py")


class ProducerManifestError(RuntimeError):
    """PRODUCERS.txt is missing or empty."""


def derive_producer_files(pkg: Path | None = None) -> tuple[str, ...]:
    """Every git-tracked source file of the package minus PRODUCER_EXCLUDE, sorted. Needs a git work tree; only the manifest writer and its tests call it."""
    base = pkg or Path(__file__).parent
    r = subprocess.run(["git", "-C", str(base), "ls-files", "--", "."], capture_output=True, text=True)
    if r.returncode != 0:
        print(f"RED producer-files: git ls-files failed in {base} (rc={r.returncode}); the producer set needs a git work tree: {r.stderr.strip()}", file=sys.stderr)
        sys.exit(1)
    names = (line for line in r.stdout.splitlines() if "/" not in line and line.endswith(".py"))
    return tuple(sorted(n for n in names if n not in PRODUCER_EXCLUDE))


def write_producer_manifest(pkg: Path | None = None) -> Path:
    """Write PRODUCERS.txt from git ls-files: one module name per line, sorted, trailing newline."""
    base = pkg or Path(__file__).parent
    names = derive_producer_files(base)
    path = base / MANIFEST
    path.write_text("".join(f"{n}\n" for n in names), encoding="utf-8")
    return path


def read_producer_manifest(pkg: Path | None = None) -> tuple[str, ...]:
    """The producer set as recorded in PRODUCERS.txt. Never calls git; a missing or empty file is a named RED."""
    base = pkg or Path(__file__).parent
    path = base / MANIFEST
    names = tuple(line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()) if path.is_file() else ()
    if not names:
        raise ProducerManifestError(f"RED producer-files: {path} is missing or empty; regenerate it in a git checkout with: python {Path(__file__).resolve()}")
    return names


if __name__ == "__main__":
    print(write_producer_manifest())

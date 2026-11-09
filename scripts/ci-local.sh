#!/usr/bin/env bash
# The exact steps .github/workflows/ci.yml runs, runnable locally. Last line: ci-local: GREEN n/n.
# Fail closed: a missing tool is a RED step, never a silent pass.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
BIN="${VENV_BIN:-$ROOT/.venv/bin}"; [ -x "$BIN/ruff" ] || BIN="$(dirname "$(command -v ruff || echo /nonexistent/ruff)")"
PYX="$BIN/python3"; [ -x "$PYX" ] || PYX=python3
LOG="$ROOT/.ci-local.last.log"
HEAVY="${HEAVY:-1}"   # HEAVY=0: light path, unit tests only, no coverage/mypy/stress, needs no heavy lock
pass=0; total=0; failed=()
step() {
  local name="$1"; shift; total=$((total+1))
  if "$@" >"$LOG" 2>&1; then pass=$((pass+1)); echo "ok   $name"
  else failed+=("$name"); echo "FAIL $name"; tail -n 12 "$LOG" | sed 's/^/     | /'; fi
}
step lock uv lock --check
step ruff "$BIN/ruff" check src tests
if [ "$HEAVY" = "0" ]; then step pytest "$BIN/pytest" -q -x -p no:cacheprovider; else
step mypy "$BIN/mypy"
step pytest "$BIN/pytest" -q -p no:cacheprovider
fi
step selftest bash scripts/selftest.sh
step evidence "$PYX" scripts/evidence_md.py --check
step sbom "$PYX" -P scripts/sbom_stdlib.py --input requirements.freeze.txt --out SBOM.cdx.json --name finetune-vs-rag-lab --check

if [ "$pass" -eq "$total" ] && [ "$total" -gt 0 ] && [ "$HEAVY" = "0" ]; then echo "ci-local-light: GREEN $pass/$total (HEAVY=0; omits: mypy)"; exit 0; fi
if [ "$pass" -eq "$total" ] && [ "$total" -gt 0 ]; then echo "ci-local: GREEN $pass/$total"; exit 0; fi
echo "ci-local: RED $pass/$total failed: ${failed[*]}"; exit 1

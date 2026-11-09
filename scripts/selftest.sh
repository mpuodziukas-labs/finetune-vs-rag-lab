#!/usr/bin/env bash
# Runs the planted-defect selftest and fails closed unless it reports every case passing.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
OUT="$("$HERE/.venv/bin/python" -m ftlab.cli selftest 2>&1)" || { echo "$OUT" | tail -20; echo "selftest exited nonzero"; exit 1; }
echo "$OUT" | grep -E 'PASS|FAIL|SELFTEST'
# Guard against an empty or truncated run: need all 5 defects + control + config guard.
[ "$(echo "$OUT" | grep -c ' PASS$')" -eq 7 ] || { echo "expected 7 PASS lines"; exit 1; }
echo "$OUT" | grep -q '^SELFTEST 7/7$' || { echo "missing SELFTEST 7/7"; exit 1; }

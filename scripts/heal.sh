#!/bin/bash
# Bounded self-heal. Detect with accountability_check.py, apply only reversible heals, re-detect.
# Heals: reseal receipts/demo sums after a GREEN verify (old sums kept in .accountability/SHA256SUMS.prev).
# Refuses (exit 2) when tests or README differ from the seal: that is a human edit, not drift.
# After MAX_ROUNDS failed rounds it appends one row to OPEN.tsv and stops (exit 1).
# Only adds or rewrites files it owns; no force-push; never edits tests or README numbers.
#   bash scripts/heal.sh [ROOT]        bash scripts/heal.sh --seal [ROOT]   (owner: accept an edit of tests or README)
set -o pipefail
MAX_ROUNDS=2
HERE="$(cd "$(dirname "$0")" && pwd)"
CHK="$HERE/accountability_check.py"
SEAL=0
if [ "$1" = "--seal" ]; then SEAL=1; shift; fi
ROOT="${1:-$(cd "$HERE/.." && pwd)}"
ROOT="$(cd "$ROOT" && pwd)" || exit 9
mkdir -p "$ROOT/.accountability"
LOG="$ROOT/.accountability/heal.log"

if [ "$SEAL" = 1 ]; then
  python3 -P "$CHK" "$ROOT" --reseal
  exit $?
fi

detect() { OUT="$(python3 -P "$CHK" "$ROOT" 2>&1)"; RC=$?; printf '%s\n' "$OUT" | tee -a "$LOG"; }

round=1
while [ "$round" -le "$MAX_ROUNDS" ]; do
  detect
  if [ "$RC" -eq 0 ]; then echo "heal: GREEN after $((round - 1)) heal rounds"; exit 0; fi
  if ! python3 -P "$CHK" "$ROOT" --sealed-drift >/dev/null; then
    echo "heal: REFUSED, tests or README differ from receipts/SHA256SUMS (human edit); owner runs heal.sh --seal"
    exit 2
  fi
  if printf '%s\n' "$OUT" | grep -q '^I2 RED'; then
    if [ -f "$ROOT/scripts/verify.sh" ] && (cd "$ROOT" && HEAVY=0 bash scripts/verify.sh >/dev/null 2>&1); then
      [ -f "$ROOT/receipts/SHA256SUMS" ] && cp -p "$ROOT/receipts/SHA256SUMS" "$ROOT/.accountability/SHA256SUMS.prev"
      python3 -P "$CHK" "$ROOT" --reseal | tee -a "$LOG"
    else
      echo "heal: no reseal, verify.sh missing or not GREEN" | tee -a "$LOG"
    fi
  fi
  round=$((round + 1))
done

detect
if [ "$RC" -eq 0 ]; then echo "heal: GREEN after $MAX_ROUNDS heal rounds"; exit 0; fi
IDS="$(printf '%s\n' "$OUT" | grep -E '^[A-Z]+[0-9]* RED ' | awk '{print $1}' | paste -sd, -)"
FIRST="$(printf '%s\n' "$OUT" | grep -E '^[A-Z]+[0-9]* RED ' | head -1)"
KEY="$IDS|$FIRST"
if ! grep -qF "$KEY" "$ROOT/OPEN.tsv" 2>/dev/null; then
  printf '%s\t%s\n' "$(date -u +%Y-%m-%d)" "$KEY" >> "$ROOT/OPEN.tsv"
fi
echo "heal: OPEN after $MAX_ROUNDS rounds ($IDS)"
exit 1

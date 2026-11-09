#!/usr/bin/env bash
# Single gate. Ends with "GREEN N/N checks" (exit 0) or "RED k/N checks failed" (exit 1).
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export TOKENIZERS_PARALLELISM=false HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}"
PY="$HERE/.venv/bin/python"
BIN="$HERE/.venv/bin"
HEAVY="${HEAVY:-1}"   # HEAVY=0: light path, unit tests only, no coverage/mypy/stress, needs no heavy lock
PASS=0
FAIL=0
FAILED=()

T="$(mktemp -d)"
trap 'rm -rf "$T"' EXIT
K=0
NAMES=()

# Each check starts when it is registered and writes its own output and exit code under $T, so independent checks overlap (HEAVY=0).
# check_report prints them in registration order with the same ok/FAIL lines as before. Under HEAVY=1 every check is waited on at once.
check_report() {
  local k="$1" rc
  rc="$(cat "$T/$k.rc")"
  if [ "$rc" -eq 0 ]; then
    PASS=$((PASS + 1))
    echo "ok   ${NAMES[k]}"
  else
    FAIL=$((FAIL + 1))
    FAILED+=("${NAMES[k]}")
    echo "FAIL ${NAMES[k]} (rc=$rc)"
    tail -n 15 "$T/$k.out" | sed 's/^/     /'
  fi
}

check() { # name, command...
  local name="$1"
  shift
  K=$((K + 1))
  local k="$K"
  NAMES[k]="$name"
  ( out="$("$@" 2>&1)"; rc=$?; printf '%s\n' "$out" >"$T/$k.out"; echo "$rc" >"$T/$k.rc" ) &
  if [ "$HEAVY" != "0" ]; then
    wait
    check_report "$k"
  fi
}

check_flush() {
  wait
  if [ "$HEAVY" = "0" ]; then
    local k
    for ((k = 1; k <= K; k++)); do check_report "$k"; done
  fi
}

# The same `pytest -x` test set cut into four concurrent processes by file (every test file runs in exactly one process).
pytest_sharded() {
  local s1="tests/test_accountability.py" s2="tests/test_p2_platform.py" s3="" s4="" f fl k n j=0 passed=0 bad=0
  for f in tests/test_*.py; do
    case "$f" in
      "$s1" | "$s2") ;;
      *)
        if [ $((j % 2)) -eq 0 ]; then s3="$s3 $f"; else s4="$s4 $f"; fi
        j=$((j + 1))
        ;;
    esac
  done
  for k in 1 2 3 4; do
    case $k in 1) fl="$s1" ;; 2) fl="$s2" ;; 3) fl="$s3" ;; *) fl="$s4" ;; esac
    # shellcheck disable=SC2086
    ("$BIN/pytest" -x -p no:cacheprovider $fl >"$T/ps$k.log" 2>&1 && echo 0 >"$T/ps$k.rc" || echo $? >"$T/ps$k.rc") &
  done
  wait
  for k in 1 2 3 4; do
    if [ "$(cat "$T/ps$k.rc")" != "0" ]; then
      bad=1
      tail -n 15 "$T/ps$k.log"
    else
      n="$(grep -Eo '[0-9]+ passed' "$T/ps$k.log" | head -n 1 | cut -d' ' -f1 || true)"
      passed=$((passed + ${n:-0}))
    fi
  done
  [ "$bad" = "0" ] || return 1
  echo "$passed passed (4 concurrent pytest processes)"
}

has_all() { # file, pattern...  (every pattern must be present)
  local f="$1"
  shift
  [ -s "$f" ] || return 1
  for p in "$@"; do grep -q -- "$p" "$f" || { echo "missing in $f: $p"; return 1; }; done
}

publish_replay() {
  local n=0 bad=0 id literal cmd expected label got
  # shellcheck disable=SC2162
  while IFS=$'\t' read -r id literal cmd expected label; do
    [ "$id" = "id" ] && continue
    [ -z "$id" ] && continue
    n=$((n + 1))
    read -r -a parts <<<"$cmd"
    [ "${parts[0]}" = "ftlab" ] || { echo "$id: command must start with ftlab"; bad=$((bad + 1)); continue; }
    got="$("$PY" -m ftlab.cli "${parts[@]:1}" 2>/dev/null)" || { echo "$id: command failed"; bad=$((bad + 1)); continue; }
    [ "$got" = "$expected" ] || { echo "$id: expected '$expected' got '$got'"; bad=$((bad + 1)); continue; }
    grep -qF -- "$literal" README.md || { echo "$id: literal '$literal' not in README"; bad=$((bad + 1)); continue; }
    [ "$label" = "measured" ] || { echo "$id: label must be 'measured' (estimates are labeled in README)"; bad=$((bad + 1)); }
  done <PUBLISH.tsv
  [ "$n" -ge 10 ] || { echo "PUBLISH.tsv has only $n rows"; return 1; }
  [ "$bad" -eq 0 ]
}

check "lockfile in sync"        uv lock --check
check "ruff"                    "$BIN/ruff" check src tests
if [ "$HEAVY" = "0" ]; then check "pytest (HEAVY=0)" pytest_sharded; else
check "mypy strict"             "$BIN/mypy"
check "pytest"                  "$BIN/pytest"
fi
check "selftest planted defects" bash "$HERE/scripts/selftest.sh"
check "receipts schema"         "$PY" -m ftlab.cli check-receipts
check "audit real receipts"     "$PY" -m ftlab.cli audit
check "README matches receipts" "$PY" -m ftlab.cli report --check
check "PUBLISH.tsv replays"     publish_replay
check "README honesty+mermaid"  has_all README.md "## Honesty Statement" '```mermaid' "BEGIN:results" "BEGIN:decision"
check "DESIGN ADRs+extension+steelman" has_all DESIGN.md "## ADR" "Extension points and upgrade path" "## Steelman"
check "EXTENDING doc"           has_all docs/EXTENDING.md "registry"
check "premortem has 5 rows"    bash -c "[ \"\$(grep -c '^| [1-5] |' NOTES-PREMORTEM.md)\" -eq 5 ]"
check "CI yaml present"         has_all .github/workflows/ci.yml "make verify"
if DW="$(command -v dewatermark || true)" && [ -n "$DW" ]; then
  check "dewatermark"             "$DW" --check README.md DESIGN.md NOTES-PREMORTEM.md docs/EXTENDING.md PUBLISH.tsv
else
  echo "skip dewatermark (optional prose linter, not installed; not counted: 14 checks instead of 15)"
fi

check_flush
TOTAL=$((PASS + FAIL))
if [ "$FAIL" -eq 0 ] && [ "$TOTAL" -gt 0 ] && [ "$HEAVY" = "0" ]; then
  echo "verify-light: GREEN $PASS/$TOTAL (HEAVY=0; omits: mypy)"
  exit 0
fi
if [ "$FAIL" -eq 0 ] && [ "$TOTAL" -gt 0 ]; then
  echo "GREEN $PASS/$TOTAL checks"
  exit 0
fi
echo "RED ${FAIL}/${TOTAL} checks failed: ${FAILED[*]}"
exit 1

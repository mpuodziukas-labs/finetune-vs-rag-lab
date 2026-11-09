#!/usr/bin/env bash
# Reproduce one README number: test accuracy of the LoRA classifier (arm A, 400 test rows).
# Expected output: 0.960
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
FT="${FTLAB:-ftlab}"; [ -x ".venv/bin/ftlab" ] && FT=".venv/bin/ftlab"
"$FT" show acc.A

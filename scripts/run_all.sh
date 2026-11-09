#!/usr/bin/env bash
# Full experiment, strictly sequential (one heavy job at a time). Writes receipts/*.json.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE"
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-0}" TOKENIZERS_PARALLELISM=false
PY="$HERE/.venv/bin/python"
ft() { "$PY" -m ftlab.cli ${FTLAB_CONFIG:+--config "$FTLAB_CONFIG"} "$@"; }

ft prepare
ft tune-k
ft eval --method zeroshot --split test
for f in 0.25 0.5 1.0; do ft eval --method retrieval --frac "$f" --split test; done
for f in 0.25 0.5 1.0; do
  ft train --frac "$f"
  ft eval --method lora --frac "$f" --split test
done
ft forget
ft audit
ft analyze
ft report
echo "RUN_ALL DONE"

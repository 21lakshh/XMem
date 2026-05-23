#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT/.venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[xmem] XMem virtualenv not found. Run npm run setup first." >&2
  exit 1
fi

"$PYTHON_BIN" "$ROOT/scripts/context.py" import "$@"

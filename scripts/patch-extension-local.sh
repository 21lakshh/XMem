#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXTENSION_DIR="$ROOT/repos/xmem-extension"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --extension-dir|-ExtensionDir)
      EXTENSION_DIR="$2"
      shift 2
      ;;
    *)
      echo "[xmem] Unknown extension patch option: $1" >&2
      exit 1
      ;;
  esac
done

node "$ROOT/scripts/patch-extension-local.js" --extension-dir "$EXTENSION_DIR"

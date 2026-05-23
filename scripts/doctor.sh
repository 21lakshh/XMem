#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_DIR="$ROOT/repos"
BASE_URL="http://localhost:8000"
FAILURES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base-url|-BaseUrl)
      BASE_URL="$2"
      shift 2
      ;;
    --repos-dir|-ReposDir)
      REPOS_DIR="$2"
      shift 2
      ;;
    *)
      echo "[xmem] Unknown doctor option: $1" >&2
      exit 1
      ;;
  esac
done

check() {
  local name="$1"
  local ok="$2"
  local message="$3"
  local fix="${4:-}"
  if [[ "$ok" == "1" ]]; then
    echo "[OK] $name - $message"
  else
    echo "[FIX] $name - $message"
    [[ -n "$fix" ]] && echo "      $fix"
    FAILURES=$((FAILURES + 1))
  fi
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

env_value() {
  local key="$1"
  local default="$2"
  if [[ ! -f "$ROOT/.env" ]]; then
    echo "$default"
    return
  fi
  local value
  value="$(grep -E "^[[:space:]]*$key[[:space:]]*=" "$ROOT/.env" | tail -n 1 | sed -E "s/^[^=]+=//; s/^['\"]//; s/['\"]$//")"
  if [[ -n "$value" ]]; then
    echo "$value"
  else
    echo "$default"
  fi
}

uses_ollama() {
  [[ ! -f "$ROOT/.env" ]] && return 0
  grep -Eq '^[[:space:]]*FALLBACK_ORDER[[:space:]]*=.*ollama' "$ROOT/.env"
}

echo "[xmem] Doctor report"
echo ""

for cmd in git node npm; do
  if has_command "$cmd"; then
    check "$cmd" 1 "command lookup"
  else
    check "$cmd" 0 "command lookup" "Install $cmd and reopen this terminal."
  fi
done

if has_command python3 || has_command python; then
  check "python" 1 "command lookup"
else
  check "python" 0 "command lookup" "Install Python 3.11+ and reopen this terminal."
fi

if has_command docker && docker info >/dev/null 2>&1; then
  check "Docker" 1 "local database runtime"
else
  check "Docker" 0 "local database runtime" "Start Docker Desktop, then rerun npm run dev."
fi

if [[ -f "$ROOT/pyproject.toml" ]]; then
  check "XMem repo" 1 "$ROOT"
else
  check "XMem repo" 0 "$ROOT" "Run this from the XMem repository root."
fi

if [[ -d "$REPOS_DIR/xmem-extension" ]]; then
  check "Extension repo" 1 "$REPOS_DIR/xmem-extension"
else
  check "Extension repo" 0 "$REPOS_DIR/xmem-extension" "Run npm run setup."
fi

if [[ -f "$ROOT/.env" ]]; then
  check "XMem .env" 1 "$ROOT/.env"
else
  check "XMem .env" 0 "$ROOT/.env" "Run npm run setup to create it from templates/xmem.env.local."
fi

if [[ -f "$ROOT/.env" ]]; then
  if uses_ollama; then
    if has_command ollama && ollama list >/dev/null 2>&1; then
      check "Ollama" 1 "required because no cloud LLM key is configured"
      installed="$(ollama list 2>/dev/null | tail -n +2 || true)"
      for model in "$(env_value OLLAMA_MODEL qwen2.5:1.5b)" "$(env_value OLLAMA_EMBEDDING_MODEL nomic-embed-text)"; do
        [[ -z "$model" ]] && continue
        if printf "%s\n" "$installed" | grep -Eq "^$(printf '%s' "$model" | sed 's/[][\.^$*+?{}|()]/\\&/g')([[:space:]]|:latest[[:space:]])"; then
          check "Ollama model $model" 1 "local model availability"
        else
          check "Ollama model $model" 0 "local model availability" "Run: ollama pull $model"
        fi
      done
    else
      check "Ollama" 0 "required because no cloud LLM key is configured" "Start Ollama, or add a cloud LLM key to .env."
    fi
  else
    check "LLM routing" 1 "cloud key detected; Ollama is not required"
  fi
fi

if has_command python3; then
  PYTHON_BIN=python3
elif has_command python; then
  PYTHON_BIN=python
else
  PYTHON_BIN=""
fi

if [[ -n "$PYTHON_BIN" ]]; then
  if "$PYTHON_BIN" - "$BASE_URL" <<'PY' >/dev/null 2>&1
import json
import sys
import urllib.request

base = sys.argv[1].rstrip("/")
with urllib.request.urlopen(f"{base}/health", timeout=5) as response:
    health = json.loads(response.read().decode("utf-8"))
data = health.get("data") or health
raise SystemExit(0 if data.get("pipelines_ready") else 1)
PY
  then
    check "XMem API" 1 "$BASE_URL/health"
  else
    check "XMem API" 0 "$BASE_URL is not ready" "Start it with npm run dev and wait for pipelines_ready=true."
  fi
else
  check "XMem API" 0 "$BASE_URL not checked" "Install Python 3.11+."
fi

echo ""
if [[ "$FAILURES" -eq 0 ]]; then
  echo "[xmem] Everything looks ready."
else
  echo "[xmem] Found $FAILURES setup item(s) to fix."
fi

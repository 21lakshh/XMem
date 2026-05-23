#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_PATH="$ROOT/.env"
QUIET=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-path|-EnvPath)
      ENV_PATH="$2"
      shift 2
      ;;
    --quiet|-Quiet)
      QUIET=1
      shift
      ;;
    *)
      echo "[xmem] Unknown configure option: $1" >&2
      exit 1
      ;;
  esac
done

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
else
  echo "[xmem] python3 is required. Install Python 3.11+ and rerun." >&2
  exit 1
fi

XMEM_ENV_PATH="$ENV_PATH" XMEM_QUIET="$QUIET" "$PYTHON_BIN" - <<'PY'
from __future__ import annotations

import os
import re
from pathlib import Path

env_path = Path(os.environ["XMEM_ENV_PATH"])
quiet = os.environ.get("XMEM_QUIET") == "1"

if not env_path.exists():
    raise SystemExit(f"XMem .env not found at {env_path}")


def log(message: str) -> None:
    if not quiet:
        print(f"[xmem] {message}")


def read_values(path: Path) -> tuple[list[str], dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    values: dict[str, str] = {}
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value.strip()
    return lines, values


def is_secret(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip()
    if not value:
        return False
    placeholders = [
        r"^your[_-]",
        r"your_.*_key",
        r"example",
        r"sample",
        r"placeholder",
        r"change[-_]?me",
        r"^dummy([-_].*)?$",
        r"^fake([-_].*)?$",
        r"^test([-_].*)?$",
    ]
    return not any(re.search(pattern, value, re.IGNORECASE) for pattern in placeholders)


def configured(values: dict[str, str], name: str) -> str:
    env_value = os.environ.get(name)
    if is_secret(env_value):
        return env_value or ""
    file_value = values.get(name)
    if is_secret(file_value):
        return file_value or ""
    return ""


def set_value(lines: list[str], name: str, value: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(name)}\s*=")
    replaced = False
    next_lines: list[str] = []
    for line in lines:
        if pattern.match(line):
            next_lines.append(f"{name}={value}")
            replaced = True
        else:
            next_lines.append(line)
    if not replaced:
        next_lines.append(f"{name}={value}")
    return next_lines


lines, values = read_values(env_path)
providers: list[str] = []
for key, provider in [
    ("OPENROUTER_API_KEY", "openrouter"),
    ("GEMINI_API_KEY", "gemini"),
    ("CLAUDE_API_KEY", "claude"),
    ("OPENAI_API_KEY", "openai"),
]:
    if configured(values, key):
        providers.append(provider)

if configured(values, "AWS_ACCESS_KEY_ID") and configured(values, "AWS_SECRET_ACCESS_KEY"):
    providers.append("bedrock")

if providers:
    quoted = ",".join(f'"{provider}"' for provider in providers)
    updates = {
        "FALLBACK_ORDER": f"'[{quoted}]'",
        "EMBEDDING_PROVIDER": "fastembed",
        "FASTEMBED_MODEL": "BAAI/bge-small-en-v1.5",
        "EMBEDDING_MODEL": "BAAI/bge-small-en-v1.5",
        "PINECONE_DIMENSION": "384",
    }
    log(f"Detected cloud LLM provider(s): {', '.join(providers)}")
    log("Configured XMem to avoid Ollama for LLM and embedding calls.")
else:
    updates = {
        "FALLBACK_ORDER": "'[\"ollama\"]'",
        "EMBEDDING_PROVIDER": "ollama",
        "OLLAMA_EMBEDDING_MODEL": "nomic-embed-text",
        "EMBEDDING_MODEL": "nomic-embed-text",
        "PINECONE_DIMENSION": "768",
    }
    log("No cloud LLM provider keys detected.")
    log("Configured XMem to use local Ollama for LLM and embedding calls.")

for key, value in updates.items():
    lines = set_value(lines, key, value)

env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

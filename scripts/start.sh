#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_DIR="$ROOT/repos"
SKIP_DOCKER=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos-dir|-ReposDir)
      REPOS_DIR="$2"
      shift 2
      ;;
    --skip-docker|-SkipDocker)
      SKIP_DOCKER=1
      shift
      ;;
    *)
      echo "[xmem] Unknown start option: $1" >&2
      exit 1
      ;;
  esac
done

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

docker_running() {
  has_command docker && docker info >/dev/null 2>&1
}

wait_containers() {
  local deadline=$((SECONDS + 180))
  local pending=("$@")
  while (( SECONDS < deadline )); do
    local next=()
    for name in "${pending[@]}"; do
      local status
      status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$name" 2>/dev/null || true)"
      if [[ "$status" == "healthy" || "$status" == "running" ]]; then
        continue
      fi
      if [[ "$status" == "unhealthy" ]]; then
        echo "[xmem] Container $name is unhealthy. Run npm run doctor or inspect it with: docker logs $name" >&2
        exit 1
      fi
      next+=("$name")
    done

    if [[ ${#next[@]} -eq 0 ]]; then
      return
    fi

    echo "[xmem] Waiting for local database containers: ${next[*]}"
    pending=("${next[@]}")
    sleep 5
  done

  echo "[xmem] Timed out waiting for local database containers: ${pending[*]}. Run npm run doctor for details." >&2
  exit 1
}

if [[ ! -f "$ROOT/.env" ]]; then
  echo "[xmem] XMem .env not found at $ROOT/.env. Run npm run setup first." >&2
  exit 1
fi

bash "$ROOT/scripts/configure-xmem-env.sh" --env-path "$ROOT/.env"

if uses_ollama; then
  if ! has_command ollama || ! ollama list >/dev/null 2>&1; then
    echo "[xmem] XMem is configured to use local Ollama, but Ollama is not running." >&2
    echo "[xmem] Start Ollama, or add a cloud LLM key to .env and rerun." >&2
    exit 2
  fi

  installed="$(ollama list 2>/dev/null | tail -n +2 || true)"
  for model in "$(env_value OLLAMA_MODEL qwen2.5:1.5b)" "$(env_value OLLAMA_EMBEDDING_MODEL nomic-embed-text)"; do
    [[ -z "$model" ]] && continue
    if ! printf "%s\n" "$installed" | grep -Eq "^$(printf '%s' "$model" | sed 's/[][\.^$*+?{}|()]/\\&/g')([[:space:]]|:latest[[:space:]])"; then
      echo "[xmem] Ollama model $model is missing. Run: ollama pull $model" >&2
      exit 2
    fi
  done
fi

if [[ "$SKIP_DOCKER" != "1" ]]; then
  if ! docker_running; then
    echo "[xmem] Docker Desktop is installed but not running, or Docker was not found." >&2
    echo "[xmem] Start Docker Desktop, wait until it says Docker is running, then rerun npm run dev." >&2
    exit 2
  fi
  docker compose -f "$ROOT/docker-compose.local.yml" up -d --remove-orphans
  wait_containers xmem-postgres xmem-mongo xmem-neo4j
fi

PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  if has_command python3; then
    PYTHON_BIN=python3
  elif has_command python; then
    PYTHON_BIN=python
  else
    echo "[xmem] python3 is required. Install Python 3.11+ and rerun." >&2
    exit 1
  fi
fi

cd "$ROOT"
echo "[xmem] Starting XMem API at http://localhost:8000"
exec "$PYTHON_BIN" -m uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000

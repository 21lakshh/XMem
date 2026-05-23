#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPOS_DIR="$ROOT/repos"
INCLUDE_MCP=0
INCLUDE_SDK=0
SKIP_MODEL_PULL=0
SKIP_PYTHON_INSTALL=0
SKIP_NODE_INSTALL=0
SKIP_DOCKER=0

log() {
  echo "[xmem] $*"
}

has_command() {
  command -v "$1" >/dev/null 2>&1
}

python_cmd() {
  if has_command python3; then
    echo "python3"
  elif has_command python; then
    echo "python"
  else
    echo "[xmem] python3 is required. Install Python 3.11+ and rerun." >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repos-dir|-ReposDir)
      REPOS_DIR="$2"
      shift 2
      ;;
    --include-mcp|-IncludeMcp)
      INCLUDE_MCP=1
      shift
      ;;
    --include-sdk|-IncludeSdk)
      INCLUDE_SDK=1
      shift
      ;;
    --skip-model-pull|-SkipModelPull)
      SKIP_MODEL_PULL=1
      shift
      ;;
    --skip-python-install|-SkipPythonInstall)
      SKIP_PYTHON_INSTALL=1
      shift
      ;;
    --skip-node-install|-SkipNodeInstall)
      SKIP_NODE_INSTALL=1
      shift
      ;;
    --skip-docker|-SkipDocker)
      SKIP_DOCKER=1
      shift
      ;;
    *)
      echo "[xmem] Unknown setup option: $1" >&2
      exit 1
      ;;
  esac
done

for cmd in git node npm; do
  if ! has_command "$cmd"; then
    echo "[xmem] $cmd is required. Install it, then run this script again." >&2
    exit 1
  fi
done

PYTHON_BIN="$(python_cmd)"
mkdir -p "$REPOS_DIR"

sync_repo() {
  local name="$1"
  local url="$2"
  local branch="$3"
  local target="$REPOS_DIR/$name"

  if [[ -d "$target" ]]; then
    if [[ ! -d "$target/.git" ]]; then
      echo "[xmem] $target exists but is not a git checkout." >&2
      exit 1
    fi
    log "Updating $name"
    git -C "$target" reset --hard
    git -C "$target" fetch origin
    git -C "$target" checkout "$branch"
    git -C "$target" pull --ff-only origin "$branch"
  else
    log "Cloning $name"
    git clone --branch "$branch" "$url" "$target"
  fi
}

docker_running() {
  has_command docker && docker info >/dev/null 2>&1
}

ollama_running() {
  has_command ollama && ollama list >/dev/null 2>&1
}

uses_ollama() {
  [[ ! -f "$ROOT/.env" ]] && return 0
  grep -Eq '^[[:space:]]*FALLBACK_ORDER[[:space:]]*=.*ollama' "$ROOT/.env"
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

    log "Waiting for local database containers: ${next[*]}"
    pending=("${next[@]}")
    sleep 5
  done

  echo "[xmem] Timed out waiting for local database containers: ${pending[*]}. Run npm run doctor for details." >&2
  exit 1
}

sync_repo "xmem-extension" "https://github.com/XortexAI/xmem-extension.git" "main"

if [[ "$INCLUDE_MCP" == "1" ]]; then
  sync_repo "xmem-mcp" "https://github.com/XortexAI/xmem-mcp.git" "main"
fi

if [[ "$INCLUDE_SDK" == "1" ]]; then
  sync_repo "xmem-sdk" "https://github.com/XortexAI/xmem-sdk.git" "master"
fi

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/templates/xmem.env.local" "$ROOT/.env"
  log "Created .env from local template"
else
  log ".env already exists; leaving it unchanged"
fi

bash "$ROOT/scripts/configure-xmem-env.sh" --env-path "$ROOT/.env"

docker_skipped=0
ollama_skipped=0

if [[ "$SKIP_MODEL_PULL" != "1" ]]; then
  if uses_ollama; then
    if ollama_running; then
      log "Pulling Ollama chat model"
      ollama pull "$(env_value OLLAMA_MODEL qwen2.5:1.5b)"
      log "Pulling Ollama embedding model"
      ollama pull "$(env_value OLLAMA_EMBEDDING_MODEL nomic-embed-text)"
    else
      echo "[xmem] Ollama was not found or is not running." >&2
      echo "[xmem] Start Ollama, or add a cloud LLM key to .env and rerun." >&2
      ollama_skipped=1
    fi
  else
    log "Cloud LLM provider key detected; skipping Ollama model pulls"
  fi
fi

if [[ "$SKIP_DOCKER" != "1" ]]; then
  if docker_running; then
    log "Starting local Docker services"
    docker compose -f "$ROOT/docker-compose.local.yml" up -d --remove-orphans
    wait_containers xmem-postgres xmem-mongo xmem-neo4j
  else
    echo "[xmem] Docker Desktop is installed but not running, or Docker was not found." >&2
    echo "[xmem] Start Docker Desktop, then rerun this script." >&2
    docker_skipped=1
  fi
fi

if [[ "$SKIP_PYTHON_INSTALL" != "1" ]]; then
  VENV_PYTHON="$ROOT/.venv/bin/python"
  if [[ ! -x "$VENV_PYTHON" ]]; then
    log "Creating XMem virtualenv"
    "$PYTHON_BIN" -m venv "$ROOT/.venv"
  fi
  log "Installing XMem local dependencies"
  "$VENV_PYTHON" -m pip install --upgrade pip
  "$VENV_PYTHON" -m pip install -e "$ROOT[local,dev]"
fi

log "Patching extension for local API"
bash "$ROOT/scripts/patch-extension-local.sh" --extension-dir "$REPOS_DIR/xmem-extension"

if [[ "$SKIP_NODE_INSTALL" != "1" ]]; then
  log "Installing and building Chrome extension"
  npm --prefix "$REPOS_DIR/xmem-extension" install
  npm --prefix "$REPOS_DIR/xmem-extension" run build
fi

log "Install complete"
echo ""
echo "Next:"
echo "  npm run dev"
echo "  npm run verify"

if [[ "$docker_skipped" == "1" ]]; then
  echo ""
  echo "[xmem] Docker services were not started. Start Docker Desktop before running npm run dev." >&2
fi

if [[ "$ollama_skipped" == "1" ]]; then
  echo ""
  echo "[xmem] Ollama models were not pulled. Start Ollama, then rerun npm run setup or add a cloud LLM key." >&2
fi

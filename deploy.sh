#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"
PYTHON="${PYTHON:-python3}"
VENV_PY="$VENV/bin/python"
PIDFILE="$ROOT/.deploy.pid"
LOGFILE="${DEPLOY_LOG:-$ROOT/deploy.log}"
HOST="${HOST:-0.0.0.0}"
PORT="${BACKEND_PORT:-8000}"
URL="http://127.0.0.1:$PORT"

usage() {
  cat <<'USAGE'
AutoLaya local deployment helper

Usage: ./deploy.sh <command>

Commands:
  setup      Install backend/frontend dependencies and build the UI
  setup-laya Install the isolated Laya runtime (torch + laya[serve])
  setup-gliner Install the isolated GLiNER2 runtime (torch + gliner2)
  pull-models Download base models from HF or ModelScope and update backend/.env
  pull-fit    Download vega-U + Qwen reader from HF or HF Mirror
  build      Build the frontend bundle
  start      Start the local API and UI
  stop       Stop the local service
  restart    Restart the local service
  status     Show process and health status
  logs       Follow the deployment log

Environment:
  HOST          Bind address (default: 0.0.0.0)
  BACKEND_PORT  API/UI port (default: 8000)
  DEPLOY_LOG    Log file (default: ./deploy.log)
  PYTHON        Python executable used for setup (default: python3)
  LAYA_VENV_DIR Override the Laya venv path (default: backend/laya-venv)
  LAYA_TORCH_INDEX Optional PyTorch wheel index, e.g. ROCm or CPU wheels
  GLINER_VENV_DIR  Override the GLiNER venv path (default: backend/gliner-venv)
  GLINER_TORCH_INDEX Optional PyTorch wheel index for GLiNER setup
  GLINER_SYSTEM_SITE_PACKAGES Set to 1 to reuse an existing torch installation
  CUDA_TORCH_INDEX Optional CUDA PyTorch wheel index; used automatically on NVIDIA hosts
USAGE
}

ensure_env() {
  mkdir -p "$ROOT/data/uploads" "$ROOT/data/datasets" "$ROOT/data/artifacts"
  if [ ! -f "$BACKEND/.env" ]; then
    cp "$ROOT/.env.example" "$BACKEND/.env"
    echo "Created backend/.env from .env.example. Add API keys there when needed."
  fi
}

require_venv() {
  if [ ! -x "$VENV_PY" ]; then
    echo "Backend virtual environment not found: $VENV" >&2
    echo "Run: ./deploy.sh setup" >&2
    exit 1
  fi
}

pid_running() {
  [ -f "$PIDFILE" ] || return 1
  local pid
  pid="$(cat "$PIDFILE" 2>/dev/null || true)"
  [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null
}

health_check() {
  "$VENV_PY" - "$URL/api/health" <<'PY'
import sys
import urllib.request

try:
    with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
        print(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(1)
PY
}

build_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "npm not found. Install Node.js 20+ first." >&2
    exit 1
  fi
  if [ -f "$FRONTEND/package-lock.json" ]; then
    (cd "$FRONTEND" && npm ci && npm run build)
  else
    (cd "$FRONTEND" && npm install && npm run build)
  fi
}

cmd_setup() {
  ensure_env
  if [ ! -x "$VENV_PY" ]; then
    "$PYTHON" -m venv "$VENV"
  fi
  "$VENV_PY" -m pip install --upgrade pip
  (cd "$BACKEND" && "$VENV_PY" -m pip install -e '.[dev,teacher]')
  build_frontend
  if [ "${AUTO_PULL_MODELS:-0}" = "1" ]; then
    cmd_pull_models
  fi
  echo "Setup complete. Start with: ./deploy.sh start"
}

cmd_setup_laya() {
  local venv="${LAYA_VENV_DIR:-$BACKEND/laya-venv}"
  local py="$venv/bin/python"
  if [ ! -x "$py" ]; then
    "$PYTHON" -m venv "$venv"
  fi
  "$py" -m pip install --upgrade pip
  local torch_index="${LAYA_TORCH_INDEX:-}"
  if [ -z "$torch_index" ] && command -v nvidia-smi >/dev/null 2>&1; then
    torch_index="${CUDA_TORCH_INDEX:-}"
  fi
  if [ -n "$torch_index" ]; then
    "$py" -m pip install torch --index-url "$torch_index"
  fi
  "$py" -m pip install "laya[serve]"
  echo "Laya runtime ready: $py"
  echo "Train: backend/laya-venv/bin/laya-train"
  echo "The API will detect this venv automatically."
}

cmd_setup_gliner() {
  local venv="${GLINER_VENV_DIR:-$BACKEND/gliner-venv}"
  local py="$venv/bin/python"
  local venv_args=""
  if [ "${GLINER_SYSTEM_SITE_PACKAGES:-0}" = "1" ]; then
    venv_args="--system-site-packages"
  fi
  if [ ! -x "$py" ]; then
    "$PYTHON" -m venv $venv_args "$venv"
  fi
  "$py" -m pip install --upgrade pip
  local torch_index="${GLINER_TORCH_INDEX:-}"
  if [ -z "$torch_index" ] && command -v nvidia-smi >/dev/null 2>&1; then
    torch_index="${CUDA_TORCH_INDEX:-}"
  fi
  if [ -n "$torch_index" ]; then
    "$py" -m pip install torch --index-url "$torch_index"
  fi
  "$py" -m pip install "gliner2[local,train]"
  echo "GLiNER runtime ready: $py"
  echo "Set GLINER_ENABLED=true after downloading a checkpoint."
}

model_python() {
  local venv="${LAYA_VENV_DIR:-$BACKEND/laya-venv}"
  local py="$venv/bin/python"
  if [ -x "$py" ]; then
    printf '%s' "$py"
    return 0
  fi
  if [ -x "$VENV_PY" ]; then
    printf '%s' "$VENV_PY"
    return 0
  fi
  echo "No Python runtime found. Run: ./deploy.sh setup" >&2
  exit 1
}

cmd_pull_models() {
  ensure_env
  local py
  py="$(model_python)"
  local source="${MODEL_SOURCE:-hf}"
  local model_set="${MODEL_SET:-base}"
  "$py" -m pip install -q huggingface_hub
  if [ "$source" = "ms" ]; then
    "$py" -m pip install -q modelscope
  fi
  "$py" "$BACKEND/scripts/pull_models.py" \
    --source "$source" --set "$model_set" \
    --root "$ROOT/models" --env-file "$BACKEND/.env"
}

cmd_pull_fit() {
  ensure_env
  local py
  py="$(model_python)"
  local source="${FIT_SOURCE:-hf}"
  local backbone_source="${FIT_BACKBONE_SOURCE:-$source}"
  if [ "$source" = "ms" ]; then
    echo "vega-U supports hf and hf-mirror only. Use FIT_BACKBONE_SOURCE=ms for Qwen." >&2
    exit 1
  fi
  "$py" -m pip install -q huggingface_hub
  if [ "$backbone_source" = "ms" ]; then
    "$py" -m pip install -q modelscope
  fi
  "$py" "$BACKEND/scripts/pull_models.py" \
    --source "$source" --backbone-source "$backbone_source" --set fit \
    --root "$ROOT/models" --env-file "$BACKEND/.env"
}

cmd_build() {
  ensure_env
  build_frontend
}

cmd_start() {
  require_venv
  ensure_env
  if [ ! -f "$FRONTEND/dist/index.html" ]; then
    echo "Frontend build not found; building now..."
    build_frontend
  fi
  if pid_running; then
    echo "AutoLaya is already running (PID $(cat "$PIDFILE"))."
    return 0
  fi

  echo "Starting AutoLaya on $HOST:$PORT..."
  (
    cd "$BACKEND"
    PYTHONPATH=. nohup "$VENV_PY" -m uvicorn app.main:app \
      --host "$HOST" --port "$PORT" >>"$LOGFILE" 2>&1 &
    echo $! >"$PIDFILE"
  )

  for _ in $(seq 1 30); do
    if health_check >/dev/null 2>&1; then
      echo "Started: $URL"
      echo "API docs: $URL/docs"
      echo "Log: $LOGFILE"
      return 0
    fi
    sleep 1
  done

  echo "AutoLaya did not become healthy. Recent log:" >&2
  tail -n 40 "$LOGFILE" >&2 || true
  cmd_stop || true
  exit 1
}

cmd_stop() {
  local stopped=0
  if pid_running; then
    kill "$(cat "$PIDFILE")" 2>/dev/null || true
    stopped=1
  fi
  rm -f "$PIDFILE"
  if command -v lsof >/dev/null 2>&1; then
    for pid in $(lsof -ti tcp:"$PORT" -sTCP:LISTEN 2>/dev/null || true); do
      kill "$pid" 2>/dev/null || true
      stopped=1
    done
  fi
  if [ "$stopped" -eq 1 ]; then
    echo "Stopped."
  else
    echo "No running AutoLaya service found."
  fi
}

cmd_status() {
  if pid_running; then
    echo "PID: $(cat "$PIDFILE")"
    echo "Listening: $HOST:$PORT"
    if health_check >/dev/null 2>&1; then
      echo "Health: OK"
      echo "URL: $URL"
    else
      echo "Health: unavailable (see $LOGFILE)"
    fi
  else
    echo "AutoLaya: stopped"
  fi
}

cmd_logs() {
  touch "$LOGFILE"
  tail -f "$LOGFILE"
}

case "${1:-}" in
  setup) cmd_setup ;;
  setup-laya) cmd_setup_laya ;;
  setup-gliner) cmd_setup_gliner ;;
  pull-models) cmd_pull_models ;;
  pull-fit) cmd_pull_fit ;;
  build) cmd_build ;;
  start) cmd_start ;;
  stop) cmd_stop ;;
  restart) cmd_stop; cmd_start ;;
  status) cmd_status ;;
  logs) cmd_logs ;;
  -h|--help|help|"") usage ;;
  *) echo "Unknown command: $1" >&2; usage; exit 1 ;;
esac

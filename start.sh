#!/usr/bin/env bash
# Starts Incident Insight: FastAPI + DuckDB RCA engine and the TanStack cockpit.
# Usage: ./start.sh [--port 8080] [--api-port 8000] [--host 127.0.0.1]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ -f "$SCRIPT_DIR/backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/backend/.env"
  set +a
fi
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
fi

PORT="${PORT:-8080}"
API_PORT="${API_PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
API_PID_FILE=".incident-insight-api.pid"
WEB_PID_FILE=".incident-insight-web.pid"
API_LOG_FILE=".incident-insight-api.log"
WEB_LOG_FILE=".incident-insight-web.log"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --api-port) API_PORT="$2"; shift 2 ;;
    --host) HOST="$2"; shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

already_running=false
if [[ -f "$API_PID_FILE" ]] && kill -0 "$(cat "$API_PID_FILE")" 2>/dev/null; then
  already_running=true
fi
if [[ -f "$WEB_PID_FILE" ]] && kill -0 "$(cat "$WEB_PID_FILE")" 2>/dev/null; then
  already_running=true
fi
if [[ "$already_running" == true ]]; then
  echo "Incident Insight looks like it is already running. Run ./stop.sh first if you want to restart it."
  echo "  API PID file: $API_PID_FILE   UI PID file: $WEB_PID_FILE"
  exit 0
fi
rm -f "$API_PID_FILE" "$WEB_PID_FILE"

if ! command -v node >/dev/null 2>&1; then
  echo "Node.js is required but was not found on PATH. Install it from https://nodejs.org (v18+)." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found on PATH. Install Python 3.9+ from https://www.python.org." >&2
  exit 1
fi

PKG_RUNNER="npm"
if command -v bun >/dev/null 2>&1 && [[ -f "bun.lock" ]]; then
  PKG_RUNNER="bun"
fi

if [[ ! -d "node_modules" ]]; then
  echo "Installing frontend dependencies with $PKG_RUNNER (first run only)..."
  if [[ "$PKG_RUNNER" == "bun" ]]; then
    bun install
  else
    npm install
  fi
fi

PYTHON_BIN="$SCRIPT_DIR/backend/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Creating backend/.venv and installing Python dependencies (first run only)..."
  python3 -m venv backend/.venv
  "$PYTHON_BIN" -m pip install --upgrade pip >/dev/null
  "$PYTHON_BIN" -m pip install -r backend/requirements.txt
fi

export ANALYTICAL_API_URL="http://$HOST:$API_PORT"

start_detached() {
  local log_file="$1"
  shift
  python3 -c '
import subprocess, sys
log_file = sys.argv[1]
command = sys.argv[2:]
with open(log_file, "wb", buffering=0) as log:
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
print(process.pid)
' "$log_file" "$@"
}

echo "Starting RCA API on http://$HOST:$API_PORT ..."
API_PID="$(start_detached "$API_LOG_FILE" "$PYTHON_BIN" -m uvicorn main:app --app-dir backend --host "$HOST" --port "$API_PORT")"
echo "$API_PID" > "$API_PID_FILE"

api_ready=false
for _ in $(seq 1 90); do
  if ! kill -0 "$API_PID" 2>/dev/null; then
    echo "RCA API failed to start. Last log lines:" >&2
    tail -n 40 "$API_LOG_FILE" >&2 || true
    rm -f "$API_PID_FILE"
    exit 1
  fi
  if command -v curl >/dev/null 2>&1 && curl -sf "http://$HOST:$API_PORT/api/health" >/dev/null 2>&1; then
    api_ready=true
    break
  fi
  sleep 1
done
if [[ "$api_ready" != true ]]; then
  echo "RCA API did not become healthy in time. Last log lines:" >&2
  tail -n 40 "$API_LOG_FILE" >&2 || true
  kill "$API_PID" 2>/dev/null || true
  rm -f "$API_PID_FILE"
  exit 1
fi

echo "Starting cockpit on http://$HOST:$PORT ..."
if [[ "$PKG_RUNNER" == "bun" ]]; then
  WEB_PID="$(start_detached "$WEB_LOG_FILE" bun run dev --host "$HOST" --port "$PORT")"
else
  WEB_PID="$(start_detached "$WEB_LOG_FILE" npm run dev -- --host "$HOST" --port "$PORT")"
fi
echo "$WEB_PID" > "$WEB_PID_FILE"

web_ready=false
for _ in $(seq 1 60); do
  if ! kill -0 "$WEB_PID" 2>/dev/null; then
    echo "Cockpit failed to start. Last log lines:" >&2
    tail -n 40 "$WEB_LOG_FILE" >&2 || true
    kill "$API_PID" 2>/dev/null || true
    rm -f "$API_PID_FILE" "$WEB_PID_FILE"
    exit 1
  fi
  if curl -sf -o /dev/null "http://$HOST:$PORT/" 2>/dev/null; then
    web_ready=true
    break
  fi
  sleep 1
done
if [[ "$web_ready" != true ]]; then
  echo "Cockpit did not report ready in time. Last log lines:" >&2
  tail -n 40 "$WEB_LOG_FILE" >&2 || true
  ./stop.sh || true
  exit 1
fi

echo "Incident Insight is running."
echo "  RCA API:  http://$HOST:$API_PORT/api/health   (PID $API_PID, log $API_LOG_FILE)"
echo "  Cockpit:  http://$HOST:$PORT                  (PID $WEB_PID, log $WEB_LOG_FILE)"
echo "Stop with: ./stop.sh"

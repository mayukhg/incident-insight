#!/usr/bin/env bash
# Stops the Incident Insight API and cockpit started by start.sh.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

API_PID_FILE=".incident-insight-api.pid"
WEB_PID_FILE=".incident-insight-web.pid"

kill_tree() {
  local pid="${1:-}"
  [[ -z "$pid" ]] && return 0
  if ! kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  local children
  children="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $children; do
    kill_tree "$child"
  done
  kill "$pid" 2>/dev/null || true
}

stop_one() {
  local pid_file="$1"
  local label="$2"
  if [[ ! -f "$pid_file" ]]; then
    echo "No $label PID file ($pid_file)."
    return 0
  fi
  local pid
  pid="$(cat "$pid_file")"
  if ! kill -0 "$pid" 2>/dev/null; then
    echo "$label process $pid is not running. Cleaning up stale PID file."
    rm -f "$pid_file"
    return 0
  fi
  echo "Stopping $label (PID $pid)..."
  kill_tree "$pid"
  for _ in $(seq 1 10); do
    if ! kill -0 "$pid" 2>/dev/null; then
      rm -f "$pid_file"
      echo "Stopped $label."
      return 0
    fi
    sleep 1
  done
  echo "$label did not exit in time, forcing..."
  kill_tree "$pid"
  kill -9 "$pid" 2>/dev/null || true
  local children
  children="$(pgrep -P "$pid" 2>/dev/null || true)"
  for child in $children; do
    kill -9 "$child" 2>/dev/null || true
  done
  rm -f "$pid_file"
  echo "Stopped $label."
}

if [[ ! -f "$API_PID_FILE" && ! -f "$WEB_PID_FILE" ]]; then
  echo "No PID files found — Incident Insight doesn't look like it's running via start.sh."
  exit 0
fi

stop_one "$WEB_PID_FILE" "cockpit"
stop_one "$API_PID_FILE" "RCA API"
echo "Stopped."

#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/tunnel.pid"
LOG_FILE="/tmp/tunnel.log"

if [[ -z "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then
  echo "❌ CLOUDFLARE_TUNNEL_TOKEN is not set"
  exit 1
fi

# Toggle: if PID file exists and process is alive → stop
if [[ -f "$PID_FILE" ]]; then
  PID=$(cat "$PID_FILE")
  if kill -0 "$PID" 2>/dev/null; then
    kill "$PID"
    rm -f "$PID_FILE"
    echo "stopped"
    exit 0
  else
    rm -f "$PID_FILE"
  fi
fi

# Start
nohup cloudflared tunnel run --token "$CLOUDFLARE_TUNNEL_TOKEN" > "$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"
sleep 2

if ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "❌ tunnel failed to start — check $LOG_FILE"
  exit 1
fi

if [[ -n "${TUNNEL_DOMAIN:-}" ]]; then
  echo "started (PID: $PID, domain: $TUNNEL_DOMAIN)"
else
  echo "started (PID: $PID)"
fi

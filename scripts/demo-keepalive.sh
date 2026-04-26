#!/usr/bin/env bash
# demo-keepalive.sh — 10-minute rotating-persona ping loop.
#
# Beats AgentCore's 15-minute microVM idle timeout by exercising the
# Phase 7 `?prewarm=1` hot path every 10 minutes, rotating through
# the three demo personas so the session pool stays warm evenly.
#
# Operator pattern (Phase 10 DEMO-RUNBOOK T-30m):
#   1. Open a tmux pane.
#   2. export BACKEND_API_URL=https://…
#   3. bash scripts/demo-keepalive.sh
#   4. Leave running through end of Q&A; Ctrl-C to stop.
#
# Exit: 0 via trap on INT/TERM/HUP. Non-zero on unset env var (set -u).
# Freeze surface: ~30 LOC, stdlib only; shellcheck zero-warning gate (D-21).

set -euo pipefail

: "${BACKEND_API_URL:?BACKEND_API_URL not set}"

personas=(CUST-001 CUST-002 CUST-003)
tick_count=0

trap 'printf "[%s] keepalive stopped after %d ticks\n" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$tick_count"; exit 0' INT TERM HUP

while true; do
  index=$((tick_count % 3))
  persona="${personas[$index]}"
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # curl -f fails loudly on 4xx/5xx; -s silences progress; -o /dev/null discards body;
  # -w prints "<http_status> <time_total>" to stdout. `|| echo "000 0"` preserves set -e
  # tolerance on curl non-zero exit (network / DNS / 4xx); we treat it as WARN + continue
  # rather than killing the loop.
  result=$(curl -f -s -o /dev/null -w '%{http_code} %{time_total}' \
    "${BACKEND_API_URL}/recommendations/${persona}?prewarm=1" || echo "000 0")

  status="${result%% *}"
  time_total="${result##* }"
  # Convert seconds (float) to integer milliseconds via awk (portable, no bash float math).
  latency_ms=$(awk -v t="$time_total" 'BEGIN { printf "%d", t * 1000 }')

  if [ "$status" = "204" ]; then
    verdict=ok
  else
    verdict=WARN
  fi

  printf '%s %s %s %dms %s\n' "$ts" "$persona" "$status" "$latency_ms" "$verdict"

  tick_count=$((tick_count + 1))
  sleep 600
done

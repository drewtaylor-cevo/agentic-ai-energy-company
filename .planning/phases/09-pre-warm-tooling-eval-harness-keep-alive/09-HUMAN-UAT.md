---
status: partial
phase: 09-pre-warm-tooling-eval-harness-keep-alive
source: [09-VERIFICATION.md]
started: 2026-04-26T19:20:00Z
updated: 2026-04-26T19:20:00Z
---

## Current Test

[awaiting human testing at D-22 closeout]

## Tests

### 1. Live pre-warm run against deployed stack (D-22 step 1)
expected: `BACKEND_API_URL=https://… npm run prewarm` from `ui/` exits 0; all 3 personas warm median < 3000ms; 9 per-call latency lines printed; `(wait 30s)` block clearly logged; subsequent lookup within 5 minutes measures warm median ≤ 2.5s on all personas (SC-2 aspirational observation).
result: [pending]

### 2. Live narrative eval harness run against deployed stack (D-22 step 2)
expected: `BACKEND_API_URL=https://… pytest tests/test_narrative_eval_live.py -m smoke` reports `3 passed`; every persona × both tracks × both narrative fields passes Phase 6 validator (regex + word/char caps); `_narrative_source` absent from every response body.
result: [pending]

### 3. Keep-alive unattended run against deployed stack (D-22 step 3)
expected: `BACKEND_API_URL=https://… bash scripts/demo-keepalive.sh` runs ≥ 20 minutes unattended; stdout shows rotating 204s with UTC timestamps matching D-19 format; persona rotation cycles CUST-001 → CUST-002 → CUST-003 → CUST-001 over 2 full ticks + start of the 3rd; Ctrl-C fires the trap cleanly and stdout shows `keepalive stopped after 3 ticks` then exit 0.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

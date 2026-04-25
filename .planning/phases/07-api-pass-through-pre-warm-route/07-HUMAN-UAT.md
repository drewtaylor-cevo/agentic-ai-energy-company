---
status: partial
phase: 07-api-pass-through-pre-warm-route
source: [07-VERIFICATION.md]
started: 2026-04-26T00:00:00Z
updated: 2026-04-26T00:00:00Z
---

## Current Test

[awaiting human testing — requires `cdk deploy -c demo_pc=1` first]

## Tests

### 1. SC-1 live byte-identical narratives
expected: |
  For each persona (CUST-001, CUST-002, CUST-003), GET $BACKEND_API_URL/recommendations/$p
  returns HTTP 200 with green.usage_narrative, green.call_script, cheapest.usage_narrative,
  cheapest.call_script as non-empty strings, and ._narrative_source ABSENT.

  Command:
  ```bash
  for p in CUST-001 CUST-002 CUST-003; do
    curl -sS "$BACKEND_API_URL/recommendations/$p" | \
      jq '{status: "ok",
           green_un: .green.usage_narrative, green_cs: .green.call_script,
           cheap_un: .cheapest.usage_narrative, cheap_cs: .cheapest.call_script,
           marker: ._narrative_source}'
  done
  ```
  Expected: 4 non-empty strings per persona + marker == null.
result: [pending]

### 2. SC-2 prewarm returns 204 live (happy path + downstream failure)
expected: |
  GET $BACKEND_API_URL/recommendations/$p?prewarm=1 returns HTTP 204 for all 3 personas,
  completing in under 25s each; a forced-failure scenario also returns 204, never 5xx.

  Command:
  ```bash
  for p in CUST-001 CUST-002 CUST-003; do
    curl -sS -o /dev/null -w "prewarm %{http_code} %{time_total}s\n" \
      "$BACKEND_API_URL/recommendations/$p?prewarm=1"
    sleep 2
  done
  ```
  Expected: three lines of "prewarm 204 <t>s" with <t> under 25.
result: [pending]

### 3. SC-4 UI-01 + UI-02 live smoke with narratives
expected: |
  Deploy with `cdk deploy -c demo_pc=1`, wait for PC=READY (~3min), run 9 warm lookups
  (3 personas × 3), compute median per persona (gate: <3000ms), verify CloudWatch
  `narrative_source` count ≥ 9 and `prewarm_failed` count = 0, open browser at 1280×800
  to confirm UI-01 above-fold layout with narratives.

  See D-15 runbook in 07-01-SUMMARY.md for full operator checklist.
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps

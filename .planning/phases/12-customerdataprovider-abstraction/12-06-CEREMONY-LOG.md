---
phase: 12-customerdataprovider-abstraction
plan: 06
artifact: ceremony-log
status: in-progress
---

# Phase 12 Plan 06 — Stack-Policy Lift → Deploy → Re-apply Ceremony

Mirrors DEMO-RUNBOOK §7 Phase 11 amendment pattern.

## Pre-Ceremony State (2026-04-29, pre-lift)

| Stack | Current policy | Termination protection | Notes |
|-------|----------------|------------------------|-------|
| CustomerTariff | `Deny` (`foundation-freeze.json`) | enabled (assumed — not re-checked) | Will be lifted for Tools Lambda asset + handler-string deploy |
| CustomerTariffAgent | `Deny` (`agentcore-freeze.json`) | enabled (assumed) | Will be lifted for container rebuild (includes `/app/providers.py`) |
| CustomerTariffApi | `Deny` | enabled (assumed) | UNTOUCHED this phase (D-07) |
| CustomerTariffFrontend | no policy (Amplify unfrozen) | n/a | Not involved |

## Task 1 — Pre-lift Sanity Checks (PASS 2026-04-29)

| Check | Result |
|-------|--------|
| 1a. Pre-baselines exist + match Phase 11 locked values | ✓ CUST-001 $30/$55, CUST-002 $16.90/$30.98, CUST-003 $14/$25.67, CUST-004 $40.02/$76.03, CUST-005 $35/$84 |
| 1b. AWS account identity | ✓ `588738606436` (cevo-dev25) |
| 1c. CustomerTariff stack policy | ✓ `Deny` (frozen, as expected) |
| 1c. CustomerTariffAgent stack policy | ✓ `Deny` (frozen, as expected) |
| 1d. CustomerTariffApi stack policy | ✓ `Deny` (will stay frozen all phase — D-07) |
| 1e. `cdk synth CustomerTariff` | ✓ clean, no errors |
| 1e. `cdk synth CustomerTariffAgent` | ✓ clean, no errors |
| 1f. Offline pytest (not smoke; excl Docker-bundling synth tests) | ✓ 204 passed, 12 skipped, 0 failed in 282s |

**Decision: proceed to Task 2 (lift CustomerTariff).**

## Task 2 — LIFT + DEPLOY CustomerTariff (PASS 2026-04-28)

| Step | Timestamp (UTC) | Command | Output | Result |
|------|-----------------|---------|--------|--------|
| A. LIFT | 2026-04-28T23:47:20Z | `aws cloudformation set-stack-policy --stack-name CustomerTariff --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json` + `update-termination-protection --no-enable-termination-protection --stack-name CustomerTariff` | Policy `Effect: Allow`; `EnableTerminationProtection: False` | ✓ Lifted |
| B. DEPLOY | 2026-04-28T23:49:22Z | `cdk deploy CustomerTariff --require-approval never` | Deployment time 33.35s, total 96.15s. `AWS::Lambda::Function` ToolsLambda/TariffTools UPDATE_COMPLETE at 9:51:22am. Stack UPDATE_COMPLETE at 9:51:26am. | ✓ UPDATE_COMPLETE |
| C1. Live gate simulate_savings CUST-001 | 2026-04-28T23:51:42Z | `aws lambda invoke --function-name tariff-tools --payload '{"action":"simulate_savings","customer_id":"CUST-001"}'` | `{"green": {"plan_id": "ECO", "plan_name": "EcoFlex 100", "saving_monthly": 30.0, "saving_annual": 360.0}, "cheapest": {"plan_id": "VAL", "plan_name": "Value 12", "saving_monthly": 55.0, "saving_annual": 660.0}}` | ✓ Byte-exact match to pre-baseline |
| C2. Live gate get_hardship_flag CUST-006 | 2026-04-28T23:51:42Z | `aws lambda invoke --function-name tariff-tools --payload '{"action":"get_hardship_flag","customer_id":"CUST-006"}'` | `{"hardship": true, "customer_id": "CUST-006"}` | ✓ New dispatcher action routes correctly |

**Decision: proceed to Task 3 (lift + deploy CustomerTariffAgent).** `CustomerTariff` stack policy stays Allow-all until Task 5.

## Task 3 — LIFT + DEPLOY CustomerTariffAgent

(pending)

## Task 4 — Post-Capture + Byte-Equality Gate

(pending)

## Task 5 — Re-apply Freeze Policies + Termination Protection

(pending)

## Task 6 — Ceremony Close

(pending)

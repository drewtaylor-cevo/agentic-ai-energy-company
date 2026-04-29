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

## Task 3 — LIFT + DEPLOY CustomerTariffAgent (PASS 2026-04-28)

| Step | Timestamp (UTC) | Command | Output | Result |
|------|-----------------|---------|--------|--------|
| A. LIFT | 2026-04-28T23:56:37Z | `aws cloudformation set-stack-policy --stack-name CustomerTariffAgent --stack-policy-body file://infrastructure/stack-policies/agentcore-allow-all.json` + `update-termination-protection --no-enable-termination-protection` | Policy `Effect: Allow`; `EnableTerminationProtection: False` | ✓ Lifted |
| B. DEPLOY | 2026-04-28T23:57:27Z | `cdk deploy CustomerTariffAgent --require-approval never` | Docker build 7-step (CACHED for pip install; fresh `COPY providers.py .` at step 6/7). Image sha256:1e91715a8ee6141635d06cc34922c0ff667476266a449c2ca16f063925f3ad4b pushed to `cdk-hnb659fds-container-assets-...us-east-1`. Stack UPDATE_COMPLETE at 9:58:24am. AgentRuntime version 10. | ✓ UPDATE_COMPLETE, container rebuilt |
| C. Container bi-mode primary branch | 2026-04-29T00:06Z | `docker run --entrypoint python --platform linux/arm64 <image> -c "from providers import CustomerDataProvider, ..."` | `OK: container /app/providers.py importable` | ✓ ROADMAP SC #5 |
| C. Container layout sanity | 2026-04-29T00:07Z | `docker run --entrypoint sh <image> -c "ls -la /app/ && python -c 'import providers; print(providers.__file__)'"` | `/app/` contains `agent.py` (17.9KB), `providers.py` (9.2KB), `narrative/`, `requirements.txt`. `providers.__file__` = `/app/providers.py` | ✓ Layout correct |
| C. Repo bi-mode except-branch | 2026-04-29T00:07Z | `python3 -c "from agent.providers import ..."` | `OK: repo agent/providers.py importable` | ✓ Both branches green |

**Image URI (for traceability):**
```
588738606436.dkr.ecr.us-east-1.amazonaws.com/cdk-hnb659fds-container-assets-588738606436-us-east-1:6ab35767fdf1b72c7b7b6252dbd96e44b4232276966ec2834eb26df1a1b1ecff
```

**Decision: proceed to Task 4 (post-capture + byte-equality gate).** Both CustomerTariff and CustomerTariffAgent stack policies remain Allow-all until Task 5.

## Task 4 — POST-CAPTURE + BYTE-EQUALITY GATE (PASS 2026-04-29)

This is the load-bearing phase-close gate (D-06, D-08, SAV-03).

| Step | Timestamp (UTC) | Command | Output | Result |
|------|-----------------|---------|--------|--------|
| A. Pre-warm | 2026-04-29T00:09:20Z | `python3 scripts/prewarm.py` | 3/3 warmed 204; measurement median 6425-6938ms (cold-start after AgentRuntime v10 rebuild) — FAIL (≥3000ms gate) but **non-blocking per plan** (savings numbers are deterministic regardless of latency) | ⚠️  warn (non-fatal) |
| B. POST capture | 2026-04-29T00:11:36Z | `python3 scripts/capture_live_recommendations.py --mode post` | All 5 captured to `baseline/post/CUST-00{1..5}.json`; `OK: 5/5 personas captured under baseline/post/` | ✓ 5/5 |
| C. COMPARE gate | 2026-04-29T00:12:23Z | `python3 scripts/capture_live_recommendations.py --mode compare` | `OK: 40/40 numeric fields byte-equal across 5 personas`; EXIT=0 | ✓ SAV-03 preserved |

### Byte-Equal Post-Baseline Values (confirmed matching pre-baselines)

| Persona  | Green $/mo | Cheapest $/mo | Match pre |
|----------|------------|---------------|-----------|
| CUST-001 | $30.00     | $55.00        | ✓ |
| CUST-002 | $16.90     | $30.98        | ✓ |
| CUST-003 | $14.00     | $25.67        | ✓ |
| CUST-004 | $40.02     | $76.03        | ✓ |
| CUST-005 | $35.00     | $84.00        | ✓ |

**5 personas × 2 tracks × 4 fields (plan_id, plan_name, saving_monthly, saving_annual) = 40 numeric fields, 40/40 byte-equal.**

**Decision: the provider abstraction passed SAV-03. Proceed to Task 5 (re-apply freeze policies + termination protection).**

## Task 5 — Re-apply Freeze Policies + Termination Protection

(pending)

## Task 6 — Ceremony Close

(pending)

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

## Task 2 — Lift CustomerTariff Stack Policy

(pending)

## Task 3 — Deploy CustomerTariff

(pending)

## Task 4 — Lift + Deploy CustomerTariffAgent

(pending)

## Task 5 — Post-Capture + Byte-Equality Gate

(pending)

## Task 6 — Re-apply Freeze Policies + Termination Protection

(pending)

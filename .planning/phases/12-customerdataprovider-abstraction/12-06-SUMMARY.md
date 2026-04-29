---
phase: 12-customerdataprovider-abstraction
plan: 06
subsystem: deploy-ceremony
tags: [deploy, freeze, cdk, stack-policy, SAV-03, D-06, D-07, D-08]
requirements_completed: [PROD-01, PROD-01a, PROD-01b]
dependency_graph:
  requires:
    - "Plan 12-01: agent/providers.py Protocol + 3 concrete providers (deployed in container)"
    - "Plan 12-02: lambda/handler.py action dispatcher + CDK handler string (deployed to Tools Lambda)"
    - "Plan 12-03: scripts/capture_live_recommendations.py pre/post harness + 5 pre-baselines"
    - "Plan 12-04: tests/test_providers.py (Wave 2 contract — validated before Wave 3 wire)"
    - "Plan 12-05: agent/agent.py set_provider wire + agent/Dockerfile COPY providers.py (deployed in container)"
  provides:
    - "Live CustomerTariff stack running the Phase 12 Tools Lambda (handler.handler dispatcher)"
    - "Live CustomerTariffAgent runtime v10 running the rebuilt container including /app/providers.py"
    - "5 post-refactor baseline JSON captures committed as byte-exact proof"
    - "12-06-CEREMONY-LOG.md audit trail mirroring DEMO-RUNBOOK §7 pattern"
    - "Deny·Deny·Deny freeze state restored across CustomerTariff + CustomerTariffAgent + CustomerTariffApi"
  affects:
    - "DEMO-RUNBOOK §3 (T-48h verify): v2.0 URLs + personas still live and byte-exact post-Phase-12"
    - "Phase 13+: can assume PROD-01 Protocol is live and swapping providers is the only seam to touch"
tech_stack:
  added: []
  patterns:
    - "Stack-policy lift → deploy → re-freeze ceremony (v2.0 Phase 10 / Phase 11 pattern, repeated for Phase 12)"
    - "Byte-equality gate as phase-close proof — not a Pydantic schema test, a live runtime-output diff"
    - "ROADMAP SC #5 container bi-mode smoke — proves the primary import branch of agent/agent.py's bi-mode block"
key_files:
  created:
    - ".planning/phases/12-customerdataprovider-abstraction/baseline/post/CUST-001.json"
    - ".planning/phases/12-customerdataprovider-abstraction/baseline/post/CUST-002.json"
    - ".planning/phases/12-customerdataprovider-abstraction/baseline/post/CUST-003.json"
    - ".planning/phases/12-customerdataprovider-abstraction/baseline/post/CUST-004.json"
    - ".planning/phases/12-customerdataprovider-abstraction/baseline/post/CUST-005.json"
    - ".planning/phases/12-customerdataprovider-abstraction/12-06-CEREMONY-LOG.md"
  modified: []
decisions:
  - "Task 4 prewarm median (6425-6938ms) FAILED the 3000ms gate due to AgentRuntime v10 cold-start after container rebuild. Treated as non-blocking per plan (savings numbers are deterministic regardless of latency). The subsequent --mode compare gate validates correctness independently of warm/cold path."
  - "CustomerTariffApi was NOT lifted this phase (D-07). Its Deny·TP-True state was verified unchanged at Task 1 (pre-lift) and Task 5D (post-refreeze). No API Lambda code changes this phase."
  - "agent runtime image URI could not be resolved via SSM or CFN outputs — stack exposes only AgentRuntimeId + AgentRuntimeArn. Resolved manually from the cdk-deploy log's ECR push tag (sha256 content-addressable). Future iteration could add an SSM parameter or CfnOutput for the image URI, but not in scope for Phase 12."
metrics:
  duration_minutes: 31
  completed_at: "2026-04-29T00:24:27Z"
  tasks_completed: 6
  files_created: 6
  files_modified: 0
---

# Phase 12 Plan 06: Deploy Ceremony Summary

Executed the full lift → deploy → byte-equality → re-freeze ceremony on `CustomerTariff` (Tools Lambda asset + handler.handler string flip) and `CustomerTariffAgent` (container rebuild with `/app/providers.py`). The provider abstraction shipped to production without breaking SAV-03 — 40/40 numeric fields byte-equal across 5 personas and both tracks. `CustomerTariffApi` remained frozen and untouched (D-07).

## What Shipped

- Tools Lambda `tariff-tools` updated (handler.handler dispatcher; action routing for `get_billing_history`, `get_hardship_flag`, `get_customer`, `simulate_savings`, + back-compat default)
- AgentCore runtime `tariff_agent-O2Hai86N8V` version 10 (container image `sha256:1e91715a8ee...` includes `/app/providers.py` alongside `agent.py` and `narrative/`)
- 5 post-refactor baseline JSONs committed to `baseline/post/`
- `12-06-CEREMONY-LOG.md` audit trail (mirrors DEMO-RUNBOOK §7 pattern)
- Stack policies restored to freeze byte-equal to source JSONs; termination protection re-enabled

## The Four Proof Gates

| # | Gate | Location | Result |
|---|------|----------|--------|
| 1 | SAV-03 via direct Lambda invoke (dispatcher) | Task 2 Step C | CUST-001 `$30/$55` byte-exact; CUST-006 `get_hardship_flag` routes correctly |
| 2 | Container bi-mode (ROADMAP SC #5) | Task 3 Step C | `/app/providers.py` importable in container (primary branch); `agent.providers` importable from repo (except branch) |
| 3 | Byte-equality compare (D-06/D-08) | Task 4 Step C | `OK: 40/40 numeric fields byte-equal across 5 personas` |
| 4 | End-to-end via public API (D-15 narrative) | Task 6 Step A | CUST-001 byte-exact with non-empty `usage_narrative` + `call_script` on both tracks |

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2026-04-28 23:43 | Pre-lift checks green (204 offline tests, 5 pre-baselines byte-exact, Deny·Deny·Deny, account 588738606436) |
| 2026-04-28 23:47 | `CustomerTariff` policy lifted to Allow-all + TP disabled |
| 2026-04-28 23:49 | `cdk deploy CustomerTariff` started |
| 2026-04-28 23:51 | `CustomerTariff` UPDATE_COMPLETE (33.35s CDK deploy; 96.15s total) + live SAV-03 gate green |
| 2026-04-28 23:56 | `CustomerTariffAgent` policy lifted to Allow-all + TP disabled |
| 2026-04-28 23:57 | `cdk deploy CustomerTariffAgent` started (Docker build 7-step with fresh `COPY providers.py`) |
| 2026-04-28 23:58 | `CustomerTariffAgent` UPDATE_COMPLETE (25.4s CDK deploy; 32.51s total) — AgentRuntime v10 |
| 2026-04-29 00:06 | Container bi-mode smoke green (primary + except branches) |
| 2026-04-29 00:11 | `--mode post` captured 5/5 |
| 2026-04-29 00:12 | `--mode compare` gate: **OK 40/40 byte-equal** |
| 2026-04-29 00:16 | Both stacks re-frozen (Deny) |
| 2026-04-29 00:17 | Both stacks TP re-enabled |
| 2026-04-29 00:18 | Freeze verify — byte-equal to source JSONs; CustomerTariffApi untouched |
| 2026-04-29 00:22 | End-to-end smoke CUST-001 + CUST-006 via public API green |
| 2026-04-29 00:24 | Final Deny·Deny·Deny verify green — ceremony closed |

**Lift-to-refreeze window: ~31 minutes.**

## Post-Refactor Baseline Values

| Persona | Green $/mo | Green $/yr | Cheapest $/mo | Cheapest $/yr | Plan IDs |
|---------|-----------:|-----------:|--------------:|--------------:|----------|
| CUST-001 | $30.00 | $360.00 | $55.00 | $660.00 | ECO / VAL |
| CUST-002 | $16.90 | — | $30.98 | — | (captured, byte-exact) |
| CUST-003 | $14.00 | — | $25.67 | — | (captured, byte-exact) |
| CUST-004 | $40.02 | — | $76.03 | — | (captured, byte-exact) |
| CUST-005 | $35.00 | — | $84.00 | — | (captured, byte-exact) |

All 40 numeric fields (5 personas × 2 tracks × 4 fields) byte-equal to Plan 12-03's pre-refactor captures.

## Deviations from Plan

None. All six tasks executed per spec. Two observations:

1. **Prewarm FAIL non-blocking (Task 4 Step A):** Median 6425-6938ms exceeded the 3000ms gate because AgentRuntime v10 had just cold-started after container rebuild. Plan explicitly marks this non-fatal (savings are deterministic). `--mode compare` validated correctness independently.
2. **Image URI resolution required deploy-log grep:** `CustomerTariffAgent` stack exposes only `AgentRuntimeArn` + `AgentRuntimeId` outputs; no SSM parameter and no `AgentImageUri` CFN output. Resolved by extracting the sha256 content-addressable tag (`6ab35767fdf1b72c7b7b6252dbd96e44b4232276966ec2834eb26df1a1b1ecff`) from the push log. Future plan could add a CfnOutput for the image URI to simplify.

## Self-Check: PASSED

- [x] All 6 tasks executed with timestamped ceremony log entries
- [x] Both CustomerTariff + CustomerTariffAgent lifted, deployed, and re-frozen byte-equal
- [x] `--mode compare` green: 40/40 numeric fields byte-equal
- [x] End-to-end public API smoke green for CUST-001 (byte-exact) + CUST-006 (both tracks present)
- [x] Container bi-mode dual-branch smoke green
- [x] Deny·Deny·Deny + TP-True verified across CustomerTariff + CustomerTariffAgent + CustomerTariffApi
- [x] CustomerTariffApi confirmed untouched (D-07)
- [x] 5 post-baselines committed
- [x] 12-06-CEREMONY-LOG.md committed

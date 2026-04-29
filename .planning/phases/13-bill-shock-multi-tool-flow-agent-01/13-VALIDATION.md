---
phase: 13
slug: bill-shock-multi-tool-flow-agent-01
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Template scaffold — planner fills the Per-Task Verification Map once PLAN.md files exist.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend) + vitest 3.x (ui) |
| **Config file** | `pytest.ini` (markers: smoke) + `ui/vitest.config.ts` |
| **Quick run command** | `pytest -m "not smoke"` + `cd ui && npm run test` |
| **Full suite command** | `pytest -m "not smoke"` (offline ~200 tests) + `pytest -m smoke` (live AWS gate) + `cd ui && npm run test && npm run lint` |
| **Estimated runtime** | ~60s offline backend, ~10s vitest, ~30s live smokes |

---

## Sampling Rate

- **After every task commit:** `pytest {tests/path/to/the/test_file_changed.py}` (or `npm run test {file}` for UI tasks)
- **After every plan wave:** Full offline suite (`pytest -m "not smoke"` + `cd ui && npm run test`)
- **Before `/gsd-verify-work`:** Full suite green + pre/post live baselines captured (D-33)
- **Max feedback latency:** 120s (offline backend cold start dominates)

---

## Per-Task Verification Map

*Planner populates this table with one row per task in each PLAN.md. Columns:*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | AGENT-01 / AGENT-01a / AGENT-01b | T-13-XX | {expected secure behavior or "N/A"} | unit/integration/smoke | `{command}` | ✅ / ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Validation Dimensions (from 13-RESEARCH.md §Validation Architecture)

Three validation dimensions MUST be observable end-to-end (Dimension 8 — Nyquist coverage per phase-research):

1. **D-19 latency-floor witness (smoke).** `tests/test_narrative_eval_live.py::test_agent01_latency_floor` asserts **CUST-003** live response latency > 1000ms. Sub-1s response on a 2–3-tool turn is a fabrication signature (C5 catch).
   - **Pytest marker:** `smoke`
   - **Gating:** runs under `pytest -m smoke` only; gated on `AWS_PROFILE=cevo-dev25` + deployed `demo-v3.0-pending` stack.
   - **Persona:** CUST-003 (was CUST-002 pre-amendment A-01).

2. **D-20 cross-persona canary (offline).** `tests/test_bill_shock_flow.py::test_no_fabrication_across_personas` asserts `detect_bill_shock` result + `reasoning_trace` + savings all differ byte-exact between **CUST-003 (shock)** and **CUST-002 Marcus (non-shock)**.
   - **Pytest marker:** none (runs in default offline tier)
   - **Gating:** `_provider_swap` autouse fixture → `InMemoryProvider`. No Bedrock / no Lambda.
   - **Failure mode caught:** Phase 06.1 fabrication regression (identical numbers across different personas).

3. **D-21 CloudWatch tool-invocation counter (smoke).** `tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked` asserts ≥ 2 `AWS/Lambda` `Invocations` on the Tools Lambda during a single CUST-003 AGENT-01 lookup within a 60-second window + 90s metric emission lag.
   - **Pytest marker:** `smoke`
   - **Gating:** live-stack only; CloudWatch `GetMetricStatistics` boto3 call.
   - **Failure mode caught:** LLM fabricated tool output (zero invocations, but response contains "trace").

---

## Wave 0 Requirements

- [ ] `tests/test_bill_shock_flow.py` — new file, stubs for D-16 cap + D-20 canary + `detect_bill_shock_pure` unit tests
- [ ] `tests/test_api_lambda.py` — ADD: `reasoning_trace` pass-through contract (D-12)
- [ ] `tests/test_narrative_eval_live.py` — ADD: `test_agent01_latency_floor` (D-19) + `test_agent01_tools_actually_invoked` (D-21), both smoke-marked
- [ ] `ui/src/components/ReasoningTrace.test.tsx` — new file, 6 vitest cases (D-30)
- [ ] `conftest.py` — NO change expected; existing `_provider_swap` + `mock_marcus_response` fixtures reused + new `mock_elena_response` already present for CUST-003
- [ ] No framework install (pytest + vitest already configured)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual rehearsal that ReasoningTrace collapsed state does NOT push cards below fold at 1280×800 | AGENT-01 + UI-01 | Requires actual browser render + human observation | `cd ui && VITE_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com npm run dev`, lookup CUST-003, verify at 1280×800 viewport both cards + narrative + call_script are above the fold with collapsed trace visible |
| Stack-policy lift ceremony — policy files byte-equal pre/post | D-32/D-33 | CloudFormation API state — scripted but requires operator confirmation | Follow DEMO-RUNBOOK §freeze section; compare `aws cloudformation get-stack-policy` output pre and post for all 2–3 lifted stacks |
| Sighting-shot warm-median measurement before stack-policy lift | A-03 | Live latency sample needs deployed stack state | Deploy to dev alias first, run `scripts/prewarm.py --once` 3×, verify CUST-003 multi-tool median < 2500ms; pivot to 2-tool break-glass if median > 2500ms |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

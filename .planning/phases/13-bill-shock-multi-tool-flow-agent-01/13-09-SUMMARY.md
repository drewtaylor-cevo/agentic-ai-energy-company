---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 09
subsystem: documentation-closer
tags:
  - documentation
  - claude-md-addendum
  - demo-runbook
  - d-11-exemption
  - d-15-cap-routing
  - d-22-strands-pin
  - persona-swap
  - phase-13

requires:
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 02)
    provides: D-11 counter-test in tests/test_schema.py::TestReasoningTraceEntryExemption
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 04)
    provides: FourToolCapHook in agent/hooks/four_tool_cap.py
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 07)
    provides: A-03 sighting-shot status (operator-pending), per-flow GATE_MS map, CUST-003 rotation

provides:
  - CLAUDE.md — 3 new invariant bullets (D-11, D-15 amended, D-22) + smoke-test env-var documentation
  - DEMO-RUNBOOK.md — T-24h rehearsal AGENT-01 items with CUST-003 Elena + A-03 state + ceremony-log pointer

affects:
  - Phase 16 DOC-01 (presenter artefact references the CLAUDE.md addendum)
  - Phase 16 DEMO-07 (extended ?narrative=off coverage references the DEMO-RUNBOOK T-24h items)

key-files:
  modified:
    - CLAUDE.md (+3 invariant bullets under Critical invariants, +smoke-test env section under Tests, +updated Demo tooling section)
    - DEMO-RUNBOOK.md (+AGENT-01 rehearsal checklist in T-24h, +updated prewarm comment in T-10m)

requirements-completed: []
  # AGENT-01 documentation is complete at this plan; the requirement itself
  # closes when Plan 08 ceremony deploys the code to the frozen stacks.

duration: ~10min
completed: 2026-04-29
---

# Phase 13 Plan 09: CLAUDE.md Addendum + DEMO-RUNBOOK Persona Swap — Summary

**CLAUDE.md gains 3 new invariant bullets (D-11 reasoning_trace exemption, D-15 HookProvider cap, D-22 Strands pin) + smoke-test env-var documentation; DEMO-RUNBOOK.md T-24h rehearsal section gains AGENT-01 items with CUST-003 Elena per A-01 amendment + ceremony-log pointer.**

## Accomplishments

### CLAUDE.md — 3 new invariant bullets

**Bullet 1 — D-11 `reasoning_trace` exemption:**
> `ReasoningTraceEntry.summary` is a separate observability surface with NO content filter — summaries intentionally contain digits, currency ($), percentages (%), and dates. D-15 dual-gate applies ONLY to `TrackInfo.usage_narrative` and `TrackInfo.call_script`. Counter-pytest `tests/test_schema.py::TestReasoningTraceEntryExemption` turns red FIRST if violated.

**Bullet 2 — D-15 4-tool cap is a Strands `HookProvider`:**
> Strands 1.37.0's `Agent.__init__` has NO `max_iterations` parameter. Cap enforced by `agent/hooks/four_tool_cap.py::FourToolCapHook` counting `AfterToolCallEvent` and calling `event.agent.cancel()`. `stop_reason == "cancelled"` routes through D-04 fallback. `grep -c max_iterations agent/agent.py` MUST stay 0.

**Bullet 3 — D-22 Strands 1.37.0 pinned:**
> Any bump requires a decimal phase with `TestCrossPersonaCanary` re-run. Frozen lockfile + `--require-hashes` enforces mechanically.

### CLAUDE.md — smoke-test env-var documentation

Added under `### Tests` section: `TOOLS_LAMBDA_NAME` env var + SSM `/customer-tariff/tools-lambda-name` fallback + Pitfall 5 (90-second CloudWatch emission lag — do NOT shorten).

Updated `### Demo tooling` section: prewarm.py description now reflects per-flow gate (3000ms single-tool / 2500ms multi-tool), CUST-001 + CUST-003 rotation, and 3 warming passes.

### DEMO-RUNBOOK.md — T-24h AGENT-01 rehearsal items

Added to the T-24h section after existing checklist items:
- Per-flow prewarm gate: CUST-003 Elena under 2500ms, CUST-001 Sarah under 3000ms
- reasoning_trace verification: 2–3 entries for CUST-003, empty for CUST-001/002
- Visual verification: collapsed ReasoningTrace row + both cards above fold at 1280×800
- `?narrative=off` collapse verification
- Ceremony log pointer: `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-08-CEREMONY-LOG.md`
- A-01 amendment note: Marcus (CUST-002) is the non-shock foil, not the demo target

Updated T-10m prewarm section comment to reference Elena and per-flow gates.

### A-03 sighting-shot state

Plan 07's sighting shot is **operator-pending** — the parallel executor could not run it (no deployed stack). The DEMO-RUNBOOK T-24h items reference the Plan 07 summary for the resolved state. Plan 08 ceremony will execute the sighting shot as a pre-lift gate.

## Verification Evidence

```
grep -c "D-11 \`reasoning_trace\` exemption" CLAUDE.md                    1
grep -c "D-15 4-tool cap" CLAUDE.md                                       1
grep -c "D-22 Strands 1.37.0 pinned" CLAUDE.md                           1
grep -c "TestReasoningTraceEntryExemption" CLAUDE.md                      1
grep -c "FourToolCapHook" CLAUDE.md                                       1
grep -c "max_iterations" CLAUDE.md                                        1
grep -c "TOOLS_LAMBDA_NAME" CLAUDE.md                                     1
grep -c "90 seconds" CLAUDE.md                                            1
grep -c "CUST-003" DEMO-RUNBOOK.md                                       15
grep -c "A-01" DEMO-RUNBOOK.md                                            2
grep -c "13-08-CEREMONY-LOG" DEMO-RUNBOOK.md                              1
grep -c "2500ms" DEMO-RUNBOOK.md                                          2
grep -c "CUST-002\|Marcus" DEMO-RUNBOOK.md                               12  (preserved as non-shock foil)

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py
  --ignore=tests/test_agent_narrative_corpus.py                  289 passed, 12 skipped, 0 failures
```

## Deviations from Plan

None. All edits are strictly additive to existing CLAUDE.md and DEMO-RUNBOOK.md content. No existing bullets removed or modified. The A-03 break-glass conditional bullet (4th bullet) was NOT added because Plan 07's sighting shot is still operator-pending — the resolved state will be documented when Plan 08 executes.

## Phase 13 completion status

Plan 09 is the documentation-closer for Phase 13. With this plan complete:
- **Plans 01–07** (offline code): DONE
- **Plan 08** (stack-policy lift ceremony): PENDING — requires operator with AWS credentials
- **Plan 09** (documentation): DONE

Phase 13 completion does NOT require any action from Phase 14 or Phase 15 in documentation space — the addenda are complete at this phase's boundary. Phase 14 will add its own CLAUDE.md bullets for the hardship discriminated-union and pre-LLM guard.

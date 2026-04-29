---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 01
subsystem: tools-lambda
tags: [tools-lambda, pure-helper, bill-shock, detect_bill_shock_pure, sav-03, phase-13, agent-01]

# Dependency graph
requires:
  - phase: 11-new-personas-tariff-archetypes
    provides: ELENA_VASQUEZ_RECORDS + MARCUS_WEBB_RECORDS 12-month fixtures; PROFILE-row filter in get_billing_history (D-21); _validate_customer_id V5 regex gate
  - phase: 12-customerdataprovider-abstraction
    provides: top-level handler(event, context) action dispatcher (D-02); _provider_swap autouse InMemoryProvider fixture (D-11)
provides:
  - detect_bill_shock_pure(billing_history, *, threshold, rate_per_kwh, daily_supply) — pure Python per-month max-ratio shock detector (SAV-03 compliant)
  - "detect_bill_shock" dispatcher branch routing via _validate_customer_id + get_billing_history + detect_bill_shock_pure
  - tests/test_bill_shock_flow.py — 2 test classes, 17 tests (8 pure-helper + 9 dispatcher)
  - Elena CUST-003 peak-shock measured baseline (delta $65.16, mean $102.72, current $167.88 @ 2025-10)
  - Marcus CUST-002 non-shock foil measured baseline (delta $20.36, mean $121.92, current $142.28 @ 2025-10)
affects:
  - Plan 13-02 (agent-side @tool wrapper for detect_bill_shock)
  - Plan 13-03 (RecommendationResponse schema + ReasoningTraceEntry)
  - Plan 13-05 (cross-persona canary — Elena vs Marcus divergence)
  - Plan 13-06 (MOCK_REASONING_TRACE_CUST003 — must mirror the measured $/date values byte-exact)
  - Phase 14 AGENT-02 hardship short-circuit (dispatcher pattern reused)

# Tech tracking
tech-stack:
  added: []  # ZERO new dependencies this phase — CONTEXT.md §Out of scope commitment upheld
  patterns:
    - per-month-scan shock detector (scan all months, pick max |delta|/11-mo-mean)
    - Option C dispatcher test pattern (monkeypatch handler.get_billing_history)

key-files:
  created:
    - tests/test_bill_shock_flow.py
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/deferred-items.md
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-01-SUMMARY.md
  modified:
    - lambda/handler.py (+ detect_bill_shock_pure, + "detect_bill_shock" dispatcher branch)

key-decisions:
  - "Deviation from plan pseudocode: per-month scan, not most-recent-month-only. Reconciles algorithm body with test expectation shock_month='2025-10' and CONTEXT A-01 'peak 0.634 on 2025-10'."
  - "Dispatcher test technique Option C (monkeypatch handler.get_billing_history)—moto absent from requirements-dev.txt; Options A/B overkill for a branch-routing + input-validation contract."
  - "Dispatcher branch ordering: get_billing_history → get_hardship_flag → detect_bill_shock → get_customer → simulate_savings → action-less back-compat. Placed BEFORE get_customer per 13-PATTERNS.md §Divergence callouts."
  - "Fail-fast on TABLE_NAME unset—matches Phase 11 get_billing_history + Phase 12 get_hardship_flag dispatcher branches; no silent fallback."

patterns-established:
  - "Per-month shock scan: for each index i, reference_mean_i is mean of the OTHER n-1 months; pick argmax(|delta_i|/reference_mean_i). Scales naturally to n=12 billing history, O(n) runtime."
  - "Chesterton's Fence—Plan 01 adds ONE new pure helper (detect_bill_shock_pure). simulate_savings_pure (lines 60-140) + get_hardship_flag_pure (lines 211-229 post-edit) bodies UNCHANGED. D-05 discipline upheld."
  - "Dispatcher branch placement rule: sav-03-related new branches reuse _validate_customer_id regex gate upfront, then reuse get_billing_history for PROFILE-filtered sorted data, then hand off to a pure helper. Same shape as Phase 14 hardship-flag branch will follow."
  - "Tests reuse conftest.py _provider_swap autouse fixture (Phase 12 D-11)—zero new fixture plumbing. elena_billing + marcus_billing fixtures at conftest lines 27-34 carry the 12-month arrays."

requirements-completed:
  - AGENT-01  # Bill-shock multi-tool agent flow — Plan 01 delivers the pure-helper + dispatcher foundation. Agent-side wiring (@tool, reasoning_trace, prompt, hook) lands in Plans 02–04.

# Metrics
duration: 14min
completed: 2026-04-29
---

# Phase 13 Plan 01: Bill-Shock Pure Helper + Dispatcher Branch Summary

**`detect_bill_shock_pure` per-month scan lands in Tools Lambda; Elena CUST-003 trips the 30% symmetric gate at 2025-10 (ratio 0.634), Marcus CUST-002 stays below at 0.167 — SAV-03 extended to the arithmetic tool for the Phase 13 multi-tool flow.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-29T04:37Z (approx — `git log` first commit)
- **Completed:** 2026-04-29T04:51Z
- **Tasks:** 3 of 3 completed (5 commits via TDD RED/GREEN on Tasks 1.1 + 1.2)
- **Files modified:** 1 (lambda/handler.py)
- **Files created:** 3 (tests/test_bill_shock_flow.py + deferred-items.md + 13-01-SUMMARY.md)

## Accomplishments

- `detect_bill_shock_pure` lands next to `simulate_savings_pure` — Chesterton-safe (existing helpers untouched), zero boto3/I/O, ValueError on <2 months, 5-key `{is_shock, delta_dollars, shock_month, mean_dollars, current_dollars}` return contract verified byte-exact against Elena + Marcus fixtures.
- Tools Lambda top-level `handler(event, context)` dispatcher gains a `"detect_bill_shock"` branch routing `_validate_customer_id` → `get_billing_history` (PROFILE filter + ASC sort from Phase 11 D-21) → `detect_bill_shock_pure`. Phase 11/12 branches for `get_billing_history`, `get_hardship_flag`, `get_customer`, `simulate_savings`, and action-less back-compat all dispatch unchanged.
- `tests/test_bill_shock_flow.py` now hosts `TestDetectBillShockPure` (8 tests) + `TestDetectBillShockDispatcher` (9 tests) = 17 tests green. File shape matches 13-PATTERNS.md file-organisation recommendation (single file, class-per-concern, ready for Plans 04 + 05 to append `TestFourToolCap`, `TestCrossPersonaCanary`, `TestReasoningTraceExemption`).
- Elena CUST-003 peak-shock measured baseline captured for Plan 13-06 mock-fixture byte-sync:
  - `delta_dollars` = **$65.16**, `mean_dollars` = **$102.72**, `current_dollars` = **$167.88**, `shock_month` = **2025-10**, `is_shock` = **True**.
- Marcus CUST-002 non-shock baseline (Plan 13-05 canary foil):
  - `delta_dollars` = **$20.36**, `mean_dollars` = **$121.92**, `current_dollars` = **$142.28**, `shock_month` = **2025-10** (peak candidate even though gate does not trip), `is_shock` = **False**.

## Task Commits

Each task was committed atomically. Tasks 1.1 and 1.2 are TDD (RED→GREEN); Task 1.3 is consolidation + deferred-items.

1. **Task 1.1 RED:** add failing `TestDetectBillShockPure` — `b88b407` (test)
2. **Task 1.1 GREEN:** add `detect_bill_shock_pure` — `f06e961` (feat)
3. **Task 1.2 RED:** add failing `TestDetectBillShockDispatcher` — `d46d6d3` (test)
4. **Task 1.2 GREEN:** extend dispatcher with `detect_bill_shock` branch — `2f18389` (feat)
5. **Task 1.3:** consolidate test file + log deferred items — `f4cf089` (chore)

_No refactor commit — algorithm body was rewritten during Task 1.1 GREEN to fix the plan-pseudocode vs test-expectation mismatch (see Deviations below); rewrite happened pre-commit so it lives inside the single feat commit, not a separate refactor._

## Files Created/Modified

- `lambda/handler.py` — added `detect_bill_shock_pure` (+68 lines) between `simulate_savings_pure` and `get_hardship_flag_pure`; added 9-line `"detect_bill_shock"` dispatcher branch between `get_hardship_flag` and `get_customer` branches.
- `tests/test_bill_shock_flow.py` — NEW, 182 lines; single-file home for Phase 13 offline coverage per 13-PATTERNS.md.
- `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/deferred-items.md` — NEW, captures `tests/test_frontend_synth.py` worktree-env artefact (out of scope for Plan 01).
- `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-01-SUMMARY.md` — this file.

## Measured Baselines (for downstream plans)

Captured via `detect_bill_shock_pure(ELENA_VASQUEZ_RECORDS)` and `detect_bill_shock_pure(MARCUS_WEBB_RECORDS)` on 2026-04-29:

| Persona          | is_shock | delta_dollars | shock_month | mean_dollars | current_dollars |
| ---------------- | -------- | ------------- | ----------- | ------------ | --------------- |
| Elena  (CUST-003) | True     | 65.16         | 2025-10     | 102.72       | 167.88          |
| Marcus (CUST-002) | False    | 20.36         | 2025-10     | 121.92       | 142.28          |

**Constants pinned in `detect_bill_shock_pure` defaults:**
- `threshold = 0.30` (D-03 symmetric gate, unchanged from CONTEXT A-01)
- `rate_per_kwh = 0.32` (STD plan rate, matches `infrastructure/seed_data/billing_records.py::STD_RATE`)
- `daily_supply = 1.10` (STD plan daily supply)
- `DAYS_PER_MONTH = 30.44` (module-level constant in `lambda/handler.py`, inherited — not redeclared)

These values are the ones Plan 13-06 must mirror byte-exact into `MOCK_REASONING_TRACE_CUST003`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `detect_bill_shock_pure` algorithm rewritten — per-month scan, not most-recent-month-only**

- **Found during:** Task 1.1 GREEN (first test run after pasting the RESEARCH §Example 3 body verbatim).
- **Issue:** Plan `<action>` pseudocode pinned `current = costs[-1]  # MOST RECENT month — scrutinised` (i.e. inspect only the chronologically-last month). Elena's chronologically-last month is 2026-03 (ratio 0.340 — above 0.30 gate, so `is_shock=True`), but the plan's test-1 expectation `shock_month == "2025-10"` and CONTEXT A-01 "Elena has 7 months above the 30% gate (peak 0.634 on 2025-10)" both require the algorithm to return the PEAK-ratio month across all 12. `2025-10` is NEVER the last month after ASC sort for a fiscal-year fixture shape.
- **Fix:** Rewrote the algorithm to scan all 12 months, compute each month's self-excluded 11-month reference mean, and pick the month with the MAX `|delta_i|/reference_mean_i` ratio as the shock candidate. `is_shock` is `peak_ratio > threshold`. Preserves the 5-key return contract and the symmetric 30% semantics; changes only WHICH month is reported as `shock_month`.
- **Files modified:** `lambda/handler.py` — `detect_bill_shock_pure` body (docstring updated to document the per-month scan semantics and the RESEARCH §6 / CONTEXT A-01 traceability link).
- **Commit:** `f06e961` (feat, Task 1.1 GREEN — the rewrite happened pre-commit so it lives inside the single GREEN commit; RED `b88b407` had the test expectation pinning `2025-10` from the outset).
- **Why Rule 1 (not Rule 4):** The return-shape contract + `is_shock` / `shock_month` semantics are unchanged; only the internal algorithm moved from "check 1 month" to "check 12 months, pick peak". No architectural change, no new tool, no schema edit. The test file IS the oracle for the plan — when test and pseudocode conflict, code the test.

### Auth Gates
None — Plan 01 is fully offline (no AWS calls, no deployed-stack dependencies).

## Dispatcher-Test Technique Chosen (Option C)

The plan's `<action>` block enumerated three options for exercising the new dispatcher branch offline:

- **Option A:** moto-stubbed DynamoDB.
- **Option B:** monkey-patch `handler.table` with a `MagicMock`.
- **Option C:** monkey-patch `handler.get_billing_history` to return the fixture list directly.

**Chosen: Option C.**

Rationale:
1. `moto` is absent from `requirements-dev.txt` (verified via `grep moto requirements-dev.in requirements-dev.txt` — no match).
2. Adding `moto` would violate CONTEXT.md §Out of scope ("Phase 13 ships ZERO new dependencies") and the `--require-hashes` freeze contract.
3. Option B (mock `table.query`) couples the test to DynamoDB response shape, duplicating coverage already in `tests/test_get_billing_history.py`.
4. Option C keeps the dispatcher test focused on action-branch routing + input validation + `get_billing_history` reuse — three orthogonal concerns. Regression tests for existing branches (`simulate_savings`, `get_billing_history`) use the same monkey-patch pattern.

**Plan 04's `TestFourToolCap` can follow the same Option C pattern if its test rig needs to bypass live DynamoDB.**

## Verification Evidence

```
pytest tests/test_bill_shock_flow.py                   17/17 pass
pytest tests/test_bill_shock_flow.py::TestDetectBillShockPure       8/8  pass
pytest tests/test_bill_shock_flow.py::TestDetectBillShockDispatcher 9/9  pass

pytest tests/test_simulate_savings.py                  22/22 pass (SAV-03 regression)
pytest tests/test_get_hardship_flag_pure.py             4/4  pass
pytest tests/test_get_billing_history.py               11/11 pass (D-21 regression)
pytest tests/test_providers.py                         14/14 pass (Phase 12)

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py
                                                      236 passed, 12 skipped,
                                                      34 deselected (smoke),
                                                      0 failures
```

**Grep-based acceptance evidence:**

```
$ grep -n "def detect_bill_shock_pure" lambda/handler.py
143:def detect_bill_shock_pure(

$ grep -n "def simulate_savings_pure" lambda/handler.py
60:def simulate_savings_pure(                                            # unchanged (Chesterton)

$ grep -n "def get_hardship_flag_pure" lambda/handler.py
211:def get_hardship_flag_pure(                                          # unchanged (Chesterton)

$ grep -n 'action == "detect_bill_shock"' lambda/handler.py
289:    if action == "detect_bill_shock":

$ grep -cE 'action == "(get_billing_history|detect_bill_shock|get_hardship_flag|get_customer|simulate_savings)"' lambda/handler.py
5                                                                        # all 5 branches present
```

**Module imports cleanly:**
```
$ python -c "import importlib; h = importlib.import_module('lambda.handler'); print('SAV-03 compliant' in (h.detect_bill_shock_pure.__doc__ or ''))"
True
```

## Deferred Issues

None within Plan 01 scope. One out-of-scope worktree-environment artefact logged to `deferred-items.md` (`tests/test_frontend_synth.py` fails due to missing `ui/dist` in parallel-executor worktrees; unrelated to any Plan 01 code change).

## Threat Flags

None — Plan 01 adds NO new network endpoints, NO new auth paths, NO new file access patterns, NO schema changes. The threat register in `13-01-PLAN.md` (T-13-01-01 through T-13-01-04) remains accurate:

- **T-13-01-01 Tampering** (mitigate): `detect_bill_shock_pure` re-sorts `billing_history` defensively + receives PROFILE-filtered data from `get_billing_history`. Verified by `test_helper_sorts_defensively` in Task 1.1.
- **T-13-01-02 Information Disclosure** (accept): `_validate_customer_id` regex gate at dispatcher entry prevents customer enumeration across malformed IDs. Verified by `test_invalid_customer_id_raises`, `test_missing_customer_id_raises`, `test_non_string_customer_id_raises` in Task 1.2.
- **T-13-01-03 DoS** (accept): 12-month cap per customer via Phase 11 seed + DynamoDB query limit; helper is O(n).
- **T-13-01-04 Repudiation** (mitigate downstream): Plan 13-05 cross-persona canary + Plan 13-07 CloudWatch counter are the observability layer; Plan 01 provides the byte-exact Elena/Marcus baselines those plans assert against.

## Self-Check: PASSED

- [x] `lambda/handler.py` contains `detect_bill_shock_pure` at line 143.
- [x] `lambda/handler.py` contains `if action == "detect_bill_shock":` at line 289.
- [x] `tests/test_bill_shock_flow.py` exists with both test classes.
- [x] Commits `b88b407`, `f06e961`, `d46d6d3`, `2f18389`, `f4cf089` all present in `git log`.
- [x] Full offline suite (non-frontend) green.
- [x] Phase 11/12 regression suites green.
- [x] `simulate_savings_pure` + `get_hardship_flag_pure` bodies byte-equal to pre-plan (Chesterton's Fence).

---

*Plan: 13-01 (Phase 13 Bill-Shock Multi-Tool Flow)*
*Completed: 2026-04-29*
*Executor: parallel worktree agent-a7c516d62d8d1f886*

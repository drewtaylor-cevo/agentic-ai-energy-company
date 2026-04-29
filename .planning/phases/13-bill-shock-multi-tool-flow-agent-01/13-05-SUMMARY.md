---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 05
subsystem: cross-persona-canary-and-api-pass-through-tests
tags: [cross-persona-canary, c5-fabrication-detection, d-20, d-12-pass-through, regression-guard, test-only, phase-13, agent-01]

# Dependency graph
requires:
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 01)
    provides: detect_bill_shock_pure pure helper + dispatcher branch; Elena peak-shock baseline (delta $65.16, mean $102.72, current $167.88, 2025-10); Marcus non-shock baseline (delta $20.36, mean $121.92, current $142.28, 2025-10)
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 02)
    provides: agent/reasoning/summaries.py formatters; ReasoningTraceEntry + RecommendationResponse.reasoning_trace; _extract_reasoning_trace helper (Plan 04 made it hot)
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 03)
    provides: 4 @tool wrappers + preference-ordered _BASE_SYSTEM_PROMPT (establishes the tool set the canary simulates)
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 04)
    provides: FourToolCapHook wired into _agent; invoke() attaches reasoning_trace on both happy path and D-04 fallback (extractor call-site WARM)
provides:
  - TestCrossPersonaCanary class appended to tests/test_bill_shock_flow.py (4 tests covering pure-helper layer, summaries layer, savings fixtures, end-to-end extractor)
  - 3 new test functions in tests/test_backend_api_handler.py (reasoning_trace pass-through unchanged, not-stripped like _narrative_source, customer-not-found detection unchanged)
  - D-20 offline fabrication detector — Elena CUST-003 vs Marcus CUST-002 byte-diverge at 4 layers
  - D-12 api_lambda/handler.py pass-through contract locked (test-only; ZERO code changes in Phase 13)
  - Phase 14 territory guard — api_lambda/handler.py:152 customer-not-found detection behaviour pinned, ready for Phase 14 surgical update
affects:
  - Plan 13-06 (MOCK_REASONING_TRACE_CUST003 — Plan 06 mirrors the byte-exact summary strings documented here)
  - Plan 13-07 (latency sighting shot — happy-path reasoning_trace is the assertion surface; D-20 canary guards the extractor output the sighting shot reads)
  - Plan 13-08 (pre-lift CDK diff gate — this plan provides belt-and-braces evidence that api_lambda/handler.py has ZERO code changes, informing the 2 vs 3-stack lift decision)
  - Phase 14 AGENT-02 (test_customer_not_found_detection_unchanged_with_reasoning_trace MUST be updated when Phase 14 adds the `kind` check; commented inline in the test body)

# Tech tracking
tech-stack:
  added: []  # ZERO new dependencies — CONTEXT.md §Out of scope commitment upheld
  patterns:
    - "Layered-divergence assertion: pure helper → summaries formatter → savings fixtures → end-to-end extractor. Each layer asserts Elena and Marcus produce byte-different output. Catches fabrication at whichever layer regresses."
    - "AgentResult simulation via MagicMock(message={'content': [...]}) — exercises _extract_reasoning_trace end-to-end offline without live Strands or Bedrock."
    - "Test-only plan: zero code changes to api_lambda/handler.py, agent/agent.py, lambda/handler.py. Locks existing behaviour; does not modify it."

key-files:
  created:
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-05-SUMMARY.md
  modified:
    - tests/test_bill_shock_flow.py (+TestCrossPersonaCanary class, 4 tests, +167 lines)
    - tests/test_backend_api_handler.py (+3 reasoning_trace pass-through test functions, +113 lines)

key-decisions:
  - "Test-only plan: Plan 05 is pure regression-lock; no source-code edits. api_lambda/handler.py ZERO diff, agent/agent.py ZERO diff, lambda/handler.py ZERO diff. This is by design (plan frontmatter files_modified lists only the two test files)."
  - "End-to-end canary simulates AgentResult via MagicMock rather than routing through live Strands — matches Plan 04's TestFourToolCap Strategy B pattern (test_invoke_routes_through_d04_fallback_on_cancelled_stop_reason). Cheap, deterministic, no Strands version coupling beyond the {toolUse,toolResult} content-block contract verified in Plan 02's RESEARCH §2."
  - "3 API pass-through tests ordered by blast radius: (1) byte-equal 200 happy path, (2) not-stripped parallel to _narrative_source (the most likely future-regression vector), (3) 404 regression with reasoning_trace (Phase 14 territory — test body flags it)."
  - "Plan 05 does NOT add a pytest marker on the API handler tests — they're plain offline tests co-located with the existing pass-through suite. smoke marker reserved for Plans 07/13 live gates."

patterns-established:
  - "Cross-persona canary at 4 layers — pure helper / summaries formatter / savings fixtures / end-to-end extractor. Future multi-tool phases (Phase 14 hardship, Phase 15 follow-up) SHOULD add an analogous 4-layer canary for the phase's headline tool."
  - "'C5 FABRICATION SIGNATURE' assert message phrase — greppable marker so a future developer reading the test output sees the Phase 06.1 regression name, not a generic diff message."
  - "API pass-through test naming: `test_<field>_<assertion>_<context>` pattern (passes_through_unchanged / not_stripped_like_narrative_source / customer_not_found_detection_unchanged_with_reasoning_trace). Tells a future grep what the test LOCKS, not what it exercises."

requirements-completed: []
  # AGENT-01 not yet complete — Plans 01/02/03/04 shipped the helper + tools + schema + cap + trace wiring;
  # Plan 05 locks the offline regression surface; Plan 07 ships the live sighting shot; Plan 08 lift ceremony;
  # Plan 13 completes AGENT-01 with the Wave 3 canary running against live Bedrock.

# Metrics
duration: ~9min
completed: 2026-04-29
---

# Phase 13 Plan 05: Cross-Persona Canary + API Pass-Through Tests Summary

**`TestCrossPersonaCanary` (4 tests) lands in `tests/test_bill_shock_flow.py`; 3 `reasoning_trace` pass-through tests land in `tests/test_backend_api_handler.py`; ZERO code changes to `api_lambda/handler.py`, `agent/agent.py`, or `lambda/handler.py` — Plan 05 is a pure regression-lock that pins the Phase 06.1 fabrication signature at 4 layers and locks the D-12 API Lambda pass-through contract against future-developer strip-like-narrative-source regressions.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-04-29T06:13Z
- **Completed:** 2026-04-29T06:22Z
- **Tasks:** 2 of 2 completed (2 commits — one per task, no TDD RED/GREEN cycle; both tasks are `type=auto` test-only adds)
- **Files modified:** 2 (`tests/test_bill_shock_flow.py`, `tests/test_backend_api_handler.py`)
- **Files created:** 1 (`13-05-SUMMARY.md`)

## Accomplishments

- **`TestCrossPersonaCanary` (4 tests) appended to `tests/test_bill_shock_flow.py`** — D-20 offline fabrication detector with byte-exact divergence assertions at four independent layers:
  1. `test_detect_bill_shock_pure_differs_elena_vs_marcus` — pure-helper layer: Elena `is_shock=True` vs Marcus `is_shock=False`; delta_dollars, mean_dollars, current_dollars all distinct; ratio bounds assert (Elena > 0.60, Marcus < 0.20 — matches RESEARCH §6 measurements).
  2. `test_summaries_differ_byte_exact_elena_vs_marcus` — summaries layer: `summary_detect_bill_shock` produces byte-different strings; Marcus returns the canned `"No bill shock: monthly usage within 11-month envelope"`; Elena contains `"Bill shock detected"` + `"$"` + `"2025-10"`.
  3. `test_savings_fixtures_differ_elena_vs_marcus` — Phase 11 D-13 byte-exact carry-forward: Elena $14.00/$25.67 vs Marcus $16.90/$30.98 on both green and cheapest saving_monthly.
  4. `test_end_to_end_reasoning_trace_differs_elena_vs_marcus` — extractor layer: simulated `AgentResult.message['content']` with 3 tool-use/tool-result pairs per persona; `_extract_reasoning_trace` produces 3-entry traces; `detect_bill_shock` summaries differ byte-exact; `simulate_savings` summaries differ byte-exact. The `"C5 FABRICATION SIGNATURE"` assertion phrase is greppable so a future developer reading a red diff sees the Phase 06.1 regression name directly.
- **3 `reasoning_trace` pass-through tests appended to `tests/test_backend_api_handler.py`** — D-12 contract locked:
  1. `test_reasoning_trace_passes_through_unchanged` — 3-entry trace with `$` + dates + digits flows byte-identical; `result["body"]` parses to identical `reasoning_trace`; sanity assert that D-15 exemption survives the pass-through.
  2. `test_reasoning_trace_not_stripped_like_narrative_source` — constructs a body carrying BOTH `_narrative_source` AND `reasoning_trace: []`; asserts `_narrative_source` IS stripped (existing Phase 7 D-06 behaviour unchanged) AND `reasoning_trace` is NOT stripped (Phase 13 D-12).
  3. `test_customer_not_found_detection_unchanged_with_reasoning_trace` — body with `reasoning_trace` but NO `green`/`cheapest` still returns 404 per `api_lambda/handler.py:152`. Phase 14 will amend this to condition on `body.get('kind') != 'hardship'` — test body's docstring flags the coupling so Phase 14 updates the test in lockstep.
- **ZERO code changes to `api_lambda/handler.py`** — `git diff 3433ab5..HEAD -- api_lambda/handler.py` returns empty. Plan 08's `cdk diff CustomerTariffApi` decision can treat the API Lambda as untouched and downgrade to a 2-stack lift (CustomerTariff + CustomerTariffAgent) unless a later plan touches it. The D-12 contract is a BEHAVIOURAL lock, not a code edit.
- **Full offline suite green** — `pytest -m "not smoke" --ignore=tests/test_frontend_synth.py` returns **288 passed, 12 skipped, 34 deselected, 0 failures**. Plan 04 baseline was 281; +7 tests match exactly (4 canary + 3 API pass-through).

## Byte-exact Elena `detect_bill_shock_pure` values (for Plan 06 mock sync)

These are the values Plan 06 MUST mirror into `MOCK_REASONING_TRACE_CUST003` so `npm run build:mock` offline path matches live-backend output byte-exact. Measured via `python3 -c "from lambda.handler import detect_bill_shock_pure; from infrastructure.seed_data.billing_records import ELENA_VASQUEZ_RECORDS; print(detect_bill_shock_pure(ELENA_VASQUEZ_RECORDS))"`:

| Field             | Value      |
| ----------------- | ---------- |
| `is_shock`        | `True`     |
| `delta_dollars`   | `65.16`    |
| `shock_month`     | `2025-10`  |
| `mean_dollars`    | `102.72`   |
| `current_dollars` | `167.88`   |

**Byte-exact `summary_detect_bill_shock` for Elena:**

```
Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)
```

**Byte-exact `summary_detect_bill_shock` for Marcus (non-shock):**

```
No bill shock: monthly usage within 11-month envelope
```

**Byte-exact 3-entry trace Plan 06 must mock for CUST-003 (from the canary end-to-end test):**

```json
[
  {"tool": "get_hardship_flag", "summary": "hardship_flag=False"},
  {"tool": "detect_bill_shock", "summary": "Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"},
  {"tool": "simulate_savings", "summary": "Green $14.00/mo; Cheapest $25.67/mo"}
]
```

(Plan 02's SUMMARY.md captured the byte-exact trace body with an example using $47.00 for the bill-shock delta; the Elena-specific figures locked above are what Plan 06 mirrors.)

## Task Commits

Each task committed atomically. Both are `type=auto` test-only adds — no TDD RED/GREEN cycle.

1. **Task 5.1:** append `TestCrossPersonaCanary` (4 tests) to `tests/test_bill_shock_flow.py` — `4d72c58` (test)
2. **Task 5.2:** add 3 `reasoning_trace` pass-through tests to `tests/test_backend_api_handler.py` — `852514f` (test)

_No refactor commits — both tests landed clean on first implementation. No deviations beyond the scope already documented below._

## Files Created/Modified

- `tests/test_bill_shock_flow.py` — modified (+167 lines). Appended `TestCrossPersonaCanary` class with 4 tests after `TestFourToolCap` (Plan 04). Existing 29 tests (TestDetectBillShockPure + TestDetectBillShockDispatcher + TestFourToolCap) untouched.
- `tests/test_backend_api_handler.py` — modified (+113 lines). Appended 3 test functions (`test_reasoning_trace_passes_through_unchanged`, `test_reasoning_trace_not_stripped_like_narrative_source`, `test_customer_not_found_detection_unchanged_with_reasoning_trace`) after `test_prewarm_invalid_customer_id_returns_400`. Existing 19 tests untouched.
- `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-05-SUMMARY.md` — NEW, this file.

## Deviations from Plan

None — plan executed exactly as written. Every acceptance-criterion grep returned the expected integer; every pytest assertion passed on first run; no code fixtures needed adjusting.

### Auth Gates

None — Plan 05 is fully offline (no AWS calls, no deployed-stack dependencies).

## Confirmation: `api_lambda/handler.py` ZERO code changes in Phase 13

Plan 05's `<output>` block mandated belt-and-braces evidence that `api_lambda/handler.py` is untouched. Full diff from the worktree base commit:

```
$ git diff 3433ab59c334ca954907d29c008dfe8c1f035938..HEAD -- api_lambda/handler.py
(empty — zero lines changed)

$ git diff 3433ab59c334ca954907d29c008dfe8c1f035938..HEAD -- agent/agent.py
(empty — zero lines changed)

$ git diff 3433ab59c334ca954907d29c008dfe8c1f035938..HEAD -- lambda/handler.py
(empty — zero lines changed)

$ git log --oneline 3433ab5..HEAD
852514f test(13-05): add reasoning_trace pass-through tests to test_backend_api_handler.py
4d72c58 test(13-05): add TestCrossPersonaCanary — D-20 offline fabrication detector
```

**Plan 08 CDK-diff decision input:** With zero code changes to `api_lambda/handler.py` in Plans 01-05, `cdk diff CustomerTariffApi` at Plan 08 planning time SHOULD return a 0-asset diff; Plan 08 may downgrade the lift ceremony from 3-stack to 2-stack (CustomerTariff + CustomerTariffAgent only) unless a later plan in Waves 2/3 touches the API Lambda bundle. Plan 05 contributes NO change.

## Flakiness Observations + Plan 08 Coupling Notes

**Canary stability:** `TestCrossPersonaCanary` is deterministic offline — 4/4 pass in 0.78s (warm-venv local). Timing jitter is irrelevant. The end-to-end test depends on:

- `_extract_reasoning_trace(agent_result)` behaviour — Plan 02's extractor. If Plan 02 extractor regresses (e.g. returns `[]` on well-formed content), the canary's end-to-end test goes RED. Intentional coupling — this is the seam Plan 08 pre-lift sanity wants.
- Plan 04 `invoke()` wiring — NOT directly exercised by the canary (canary mocks `_agent` is not mocked, the canary builds a fake `AgentResult` and calls `_extract_reasoning_trace` directly). Decoupled from `invoke()` wiring changes.
- `summary_detect_bill_shock` / `summary_simulate_savings` formatter bodies — Plan 02's formatters. If a future plan changes the output format (e.g. round to nearest dollar, drop `$` prefix), the summaries-layer test goes RED. Intentional — Phase 06.1 regression signature IS "summary format regressed across personas".

**Plan 08 pre-lift sanity gate recommendation:** Include `pytest tests/test_bill_shock_flow.py::TestCrossPersonaCanary -x` (+ the 3 API pass-through tests) in Plan 08's offline gate before the `aws cloudformation set-stack-policy` lift. If any of the 7 tests fail, block the lift. Plan 08's manifest should grep this SUMMARY.md for the test names to include in its pre-gate list.

**Coupling to Plan 02 Elena baselines:** The canary's bounds assertion (`elena_ratio > 0.60`) is deliberately loose — Plan 01 measured 0.6344; the `> 0.60` bound accommodates minor rounding drift without making the test brittle to fixture edits. If Phase 11 fixtures are ever re-tuned (out of scope per Plan 01 Deviation 1), this bound MAY need tightening. Documented here so a future fixture regen includes a canary review.

**Coupling to Phase 14 AGENT-02:** `test_customer_not_found_detection_unchanged_with_reasoning_trace` will need to be UPDATED in Phase 14 when `api_lambda/handler.py:152` conditions on `body.get('kind') != 'hardship'`. The test's docstring explicitly flags this ("Phase 14 amends this to condition on body.get('kind') != 'hardship'"). Phase 14's surgical update MUST also update this test in the same commit.

## Verification Evidence

```
pytest tests/test_bill_shock_flow.py::TestCrossPersonaCanary -x       4/4  pass  (0.78s)
pytest tests/test_bill_shock_flow.py -x                               33/33 pass (17 Plan 01 + 12 Plan 04 + 4 Plan 05)
pytest tests/test_backend_api_handler.py -k "reasoning_trace or customer_not_found" -x  3/3 pass
pytest tests/test_backend_api_handler.py -x                           22/22 pass (19 existing + 3 Plan 05)

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py
                                                                       288 passed, 12 skipped,
                                                                        34 deselected (smoke),
                                                                         0 failures
                                                                       (+7 tests vs Plan 04 baseline 281 —
                                                                        exact match: 4 canary + 3 API pass-through)
```

**Grep-based acceptance evidence (Task 5.1):**

```
$ grep -c "class TestCrossPersonaCanary" tests/test_bill_shock_flow.py                                  1
$ grep -c "def test_detect_bill_shock_pure_differs_elena_vs_marcus" tests/test_bill_shock_flow.py        1
$ grep -c "def test_summaries_differ_byte_exact_elena_vs_marcus" tests/test_bill_shock_flow.py           1
$ grep -c "def test_end_to_end_reasoning_trace_differs_elena_vs_marcus" tests/test_bill_shock_flow.py    1
$ grep -c "C5 FABRICATION SIGNATURE" tests/test_bill_shock_flow.py                                       1
```

**Grep-based acceptance evidence (Task 5.2):**

```
$ grep -c "def test_reasoning_trace_passes_through_unchanged" tests/test_backend_api_handler.py                      1
$ grep -c "def test_reasoning_trace_not_stripped_like_narrative_source" tests/test_backend_api_handler.py            1
$ grep -c "def test_customer_not_found_detection_unchanged_with_reasoning_trace" tests/test_backend_api_handler.py   1
$ grep -c 'body.pop("reasoning_trace"' api_lambda/handler.py                                                         0  (D-12 contract — MUST stay 0)
$ grep -c 'body.pop("_narrative_source"' api_lambda/handler.py                                                       1  (existing Phase 7 D-06 — unchanged)
```

**Byte-exact Elena formatter output verified offline:**

```
$ python3 -c "from lambda.handler import detect_bill_shock_pure; from infrastructure.seed_data.billing_records import ELENA_VASQUEZ_RECORDS; from agent.reasoning.summaries import summary_detect_bill_shock; print(repr(summary_detect_bill_shock(detect_bill_shock_pure(ELENA_VASQUEZ_RECORDS))))"
'Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)'

$ python3 -c "from lambda.handler import detect_bill_shock_pure; from infrastructure.seed_data.billing_records import MARCUS_WEBB_RECORDS; from agent.reasoning.summaries import summary_detect_bill_shock; print(repr(summary_detect_bill_shock(detect_bill_shock_pure(MARCUS_WEBB_RECORDS))))"
'No bill shock: monthly usage within 11-month envelope'
```

## Deferred Issues

None within Plan 05 scope. Phase 14's surgical update to `test_customer_not_found_detection_unchanged_with_reasoning_trace` is not deferred — it's the coupling documented above and is Phase 14's responsibility.

## Threat Flags

None — Plan 05 adds:
- NO new network endpoints
- NO new auth paths
- NO new file access patterns
- NO schema changes
- NO new source code — test-only additions

All threats in the plan's `<threat_model>` (T-13-05-01..04) are mitigated as specified:

- **T-13-05-01 Tampering (Fabrication)** (mitigate): `test_end_to_end_reasoning_trace_differs_elena_vs_marcus` diffs byte-exact between Elena + Marcus at the extractor layer. RED if any future `_extract_reasoning_trace` regression produces identical cross-persona output.
- **T-13-05-02 Tampering** (mitigate): `test_reasoning_trace_not_stripped_like_narrative_source` turns RED the moment a future developer adds `body.pop("reasoning_trace", None)` to `api_lambda/handler.py`. Locked.
- **T-13-05-03 Business Logic (V11)** (mitigate): `test_customer_not_found_detection_unchanged_with_reasoning_trace` pins current Phase 13 behaviour; Phase 14 updates this test as part of its `body.get('kind') != 'hardship'` surgical edit. Coupling documented inline + in §"Plan 08 Coupling Notes" above.
- **T-13-05-04 Information Disclosure** (accept): reasoning_trace summary content is aggregate customer stats only (mean $, current $, shock month); authorisation is out of scope for Phase 13.

## TDD Gate Compliance

Plan 05 is `autonomous: true`, both tasks `type=auto`. No `tdd="true"` tasks — this is a regression-lock plan that pins existing behaviour via test additions. No RED/GREEN/REFACTOR cycle required; both test commits validated pass-on-first-run against the pre-existing implementation (Plans 01-04).

## Self-Check: PASSED

- [x] `tests/test_bill_shock_flow.py::TestCrossPersonaCanary` exists with 4 tests.
- [x] `TestCrossPersonaCanary` 4/4 pass (0.78s).
- [x] `tests/test_bill_shock_flow.py` full file: 33/33 pass (17 Plan 01 + 12 Plan 04 + 4 Plan 05).
- [x] `tests/test_backend_api_handler.py` contains 3 new `reasoning_trace` tests.
- [x] `tests/test_backend_api_handler.py` full file: 22/22 pass (19 existing + 3 Plan 05).
- [x] `grep -c 'body.pop("reasoning_trace"' api_lambda/handler.py` equals 0.
- [x] `grep -c 'body.pop("_narrative_source"' api_lambda/handler.py` equals 1 (existing unchanged).
- [x] Full offline suite: 288 passed, 12 skipped, 34 deselected, 0 failures (+7 vs Plan 04 baseline).
- [x] Zero code changes to `api_lambda/handler.py`, `agent/agent.py`, `lambda/handler.py` in Plans 01-05 diff window.
- [x] Commits `4d72c58`, `852514f` both present in `git log --oneline 3433ab5..HEAD`.
- [x] Byte-exact Elena summary string captured for Plan 06 mock sync: `'Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)'`.
- [x] Byte-exact Marcus summary string captured: `'No bill shock: monthly usage within 11-month envelope'`.

---

*Plan: 13-05 (Phase 13 Bill-Shock Multi-Tool Flow)*
*Completed: 2026-04-29*
*Executor: parallel worktree agent-a67230b06b567fd7e*

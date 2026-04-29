---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 04
subsystem: agent-runtime-cap-and-trace-wiring
tags: [strands-hook, four-tool-cap, stop_reason-cancelled, d-04-fallback, reasoning_trace-wiring, hookprovider, agent-01b, phase-13]

# Dependency graph
requires:
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 02)
    provides: ReasoningTraceEntry + RecommendationResponse.reasoning_trace + _extract_reasoning_trace extractor (cold helper — this plan wires both call-sites)
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 03)
    provides: 4 @tool wrappers + _agent = Agent(tools=[...]) without hooks; _BASE_SYSTEM_PROMPT preference-ordered graph
provides:
  - agent/hooks/__init__.py (empty package marker)
  - agent/hooks/four_tool_cap.py — FourToolCapHook(HookProvider) with register_hooks subscribing to AfterToolCallEvent; on_tool_complete increments self.used and calls event.agent.cancel() at budget; reset() method for per-invocation zeroing; ValueError on budget < 1
  - agent/agent.py — bi-mode import of FourToolCapHook; module-level _four_tool_cap = FourToolCapHook(budget=4); _agent constructed with hooks=[_four_tool_cap]; invoke() now resets the counter at top, detects agent_result.stop_reason == 'cancelled' and raises RuntimeError('tool budget exhausted') into the existing D-04 except-Exception fallback; reasoning_trace attached on BOTH the happy-path and D-04 fallback return paths
  - agent/Dockerfile — COPY hooks/ ./hooks/ line added (Pitfall 4 prevention; Plan 08 smoke will verify)
  - TestFourToolCap class in tests/test_bill_shock_flow.py — 12 tests: 8 hook unit tests (Strategy A) + 4 invoke() integration tests (Strategy B) including Pitfall 2 regression guard and SC-3 counter-reset invariant
affects:
  - Plan 13-05 (cross-persona canary — CloudWatch counter fires when stop_reason=='cancelled'; reasoning_trace-on-fallback makes the canary observable)
  - Plan 13-07 (sighting shot — warm p95 under 2500ms requires the cap to actually fire; happy-path reasoning_trace lets the assertion inspect tool ordering)
  - Plan 13-08 (pre-deploy smoke — Dockerfile container smoke `from hooks.four_tool_cap import FourToolCapHook` must succeed)
  - Plan 13-09 (CLAUDE.md addendum — codifies "Strands 1.37.0 has no max_iterations; cap is a HookProvider" and the `_agent.hooks` attribute shape)

# Tech tracking
tech-stack:
  added: []  # ZERO new dependencies — CONTEXT.md §Out of scope commitment upheld
  patterns:
    - HookProvider-based iteration cap via AfterToolCallEvent + event.agent.cancel() (A-02 amendment; Strands 1.37.0 has no max_iterations kwarg)
    - Module-level hook instance + explicit reset() at invoke() entry (SC-3 mirror — prevents session bleed)
    - stop_reason == 'cancelled' sentinel raised as RuntimeError and routed through the existing D-04 except-Exception fallback path (zero new error-handling branches)
    - reasoning_trace attached on BOTH happy path and D-04 fallback (same extractor call; best-effort returns [] on failure, never raises)
    - Bi-mode import stanza for agent/hooks/ — container /app/hooks/ first, repo agent.hooks/ fallback (narrative/, reasoning/, providers precedent)

key-files:
  created:
    - agent/hooks/__init__.py
    - agent/hooks/four_tool_cap.py
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-04-SUMMARY.md
  modified:
    - agent/agent.py (+bi-mode FourToolCapHook import, +_four_tool_cap module-level instance, +hooks=[_four_tool_cap] on _agent, +_four_tool_cap.reset() + stop_reason=='cancelled' branch + reasoning_trace attach on happy path + reasoning_trace attach on D-04 fallback in invoke())
    - agent/Dockerfile (+COPY hooks/ ./hooks/)
    - tests/test_bill_shock_flow.py (+TestFourToolCap class — 12 tests; also replaced Task 4.1/4.2 RED smoke scaffolds with the canonical class)

key-decisions:
  - "TestFourToolCap class absorbs Task 4.1 + 4.2 RED smoke scaffolds — the original TestFourToolCapHookSmoke / TestFourToolCapWiringSmoke stubs shipped in the RED commits served the TDD gate, then Task 4.3 replaced them with the canonical class per plan design (cleaner grep surface; single authoritative class per plan)."
  - "reasoning_trace also attached on the D-04 fallback return (not just happy + cap-cancellation) — covers EVERY agent-invocation failure (StructuredOutputException salvage catches its own exit; general Exception catches cap exhaustion + any other). Matches the plan's intent 'partial reasoning_trace on D-04 fallback' and avoids diverging behaviour between cap-triggered and tool-failure 500-class errors."
  - "Dockerfile COPY for agent/hooks/ landed in THIS plan rather than deferring to Plan 08 — Plan 08 explicitly documents the 'may have been deferred' fallback but shipping it here prevents the Pitfall 4 race where Plan 04 passes offline but the first live deploy ImportErrors at container start. See deviation Rule 2 entry."
  - "Deviation Rule 2 applied to Dockerfile COPY: the new agent/hooks/ package is a container-runtime requirement. Adding the COPY is a correctness requirement, not a feature — Plan 02 used the same rule for agent/reasoning/."
  - "max_iterations Pitfall 2 guard implemented as a file-read test (test_agent_has_no_max_iterations_reference) — greps agent/agent.py source directly. Stricter than the plan's grep-based acceptance criterion; makes the guard regression-proof against future refactors that might re-introduce the kwarg silently."

patterns-established:
  - "HookProvider + event.agent.cancel() pattern established as the canonical Strands 1.37.0 iteration-cap mechanism. Phase 14 (AGENT-02) hardship short-circuit MAY use a BeforeToolCallEvent + event.cancel_tool pattern if it wants to block specific tool invocations; Phase 13's AfterToolCallEvent+cancel() is the budget pattern."
  - "Module-level hook instance pattern — one per Agent singleton, with explicit reset() at invoke() entry. Documented at the call site (comment in invoke() body) and covered by test_counter_resets_between_invocations."
  - "Bi-mode import stanza placement: new agent/<subpackage>/ additions go AFTER the reasoning.summaries bi-mode block and BEFORE `logger = logging.getLogger(__name__)`. Container-first try / repo fallback. Plans 02 + 04 both followed the pattern; future subpackages (Phase 15 memory/) MUST mirror."
  - "TDD scaffold-then-replace pattern: RED-phase smoke tests can live alongside the canonical class for a commit or two; the GREEN commit does NOT have to include the full test class. Task 4.3 replaced the scaffolds cleanly without breaking the RED-GREEN-REFACTOR ledger."

requirements-completed: []
  # AGENT-01b has in-code 4-tool cap via FourToolCapHook. AGENT-01 overall is not
  # yet complete — Plans 05 (cross-persona canary) and 07 (sighting shot) still
  # need to land before AGENT-01 closes. Orchestrator will mark completion at
  # Wave 3.

# Metrics
duration: ~25min
completed: 2026-04-29
---

# Phase 13 Plan 04: FourToolCapHook + reasoning_trace Wiring Summary

**`FourToolCapHook(HookProvider)` registered on `_agent` with `budget=4`; `invoke()` resets the counter on entry, detects `stop_reason=='cancelled'`, raises into the existing D-04 fallback, and attaches `reasoning_trace` on BOTH the happy path and the D-04 fallback — AGENT-01b's "cap in code, not prompt" requirement is met and Plan 07's sighting shot has the reasoning-trace evidence surface it needs.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-29T~15:57Z (worktree re-based to 77a9a43)
- **Completed:** 2026-04-29T~16:22Z
- **Tasks:** 3 of 3 completed (6 commits — TDD RED/GREEN on Tasks 4.1 + 4.2; single commit on Task 4.3; extra chore commit for Dockerfile COPY)
- **Files modified:** 3 (`agent/agent.py`, `agent/Dockerfile`, `tests/test_bill_shock_flow.py`)
- **Files created:** 3 (`agent/hooks/__init__.py`, `agent/hooks/four_tool_cap.py`, `13-04-SUMMARY.md`)

## Accomplishments

- **`FourToolCapHook(HookProvider)`** in `agent/hooks/four_tool_cap.py` — subscribes to `AfterToolCallEvent`, increments per-instance `self.used`, calls `event.agent.cancel()` at budget exhaustion. Exposes `reset()` for per-invocation zeroing (SC-3 mirror). Raises `ValueError("budget must be >= 1")` on invalid construction. Registered as an `agent/hooks/` package so future hooks (Phase 14 hardship short-circuit, Phase 15 memory tap) can add modules alongside.
- **`agent/agent.py` wired** — bi-mode import for `FourToolCapHook` (container `/app/hooks/` first, repo `agent.hooks/` fallback); module-level `_four_tool_cap = FourToolCapHook(budget=4)`; `_agent = Agent(..., hooks=[_four_tool_cap])`; `invoke()` resets the counter at top, detects `agent_result.stop_reason == 'cancelled'` and raises `RuntimeError('tool budget exhausted')` into the existing `except Exception` fallback — D-04 never-500 invariant preserved.
- **`reasoning_trace` attached on BOTH paths** — happy path `body["reasoning_trace"] = [...]` just before `return body`; D-04 fallback `raw["reasoning_trace"] = [...]` just before `return raw`. Extractor is best-effort (`[]` on any failure); covers cap-cancellation, direct Lambda fallback, and every transient agent-invocation failure.
- **`agent/Dockerfile`** — `COPY hooks/ ./hooks/` line added alongside `COPY reasoning/ ./reasoning/` and `COPY narrative/ ./narrative/`. Without this line the container bi-mode import would silently `ImportError` and every invocation would take the D-04 fallback path — Pitfall 4 prevention. Plan 08's pre-deploy smoke will verify.
- **`TestFourToolCap` class** — 12 tests in `tests/test_bill_shock_flow.py`. Strategy A (8 hook unit tests): instantiates with defaults, HookProvider duck-type, increments `used` on each call, cancels agent at budget, idempotent cancel past budget, `register_hooks` subscribes to `AfterToolCallEvent`, `reset()` zeros counter, `budget < 1` raises. Strategy B (4 invoke() integration tests): stop_reason=='cancelled' routes through D-04 (body has green + cheapest + reasoning_trace + `_narrative_source`, no errorMessage, no 500); RuntimeError does not leak; counter resets between invocations; Pitfall 2 regression guard (grep agent/agent.py source for `max_iterations` → 0).
- **Pitfall 2 regression guard** — `test_agent_has_no_max_iterations_reference` reads `agent/agent.py` source and asserts zero `max_iterations` occurrences. Future developer who introduces `Agent(max_iterations=4)` trips RED instantly.
- **SC-3 counter-reset invariant** — `test_counter_resets_between_invocations` asserts `_four_tool_cap.reset()` zeroes the module-level counter. Prevents the same class of bug as Pitfall 2 in `runtimeSessionId` handling (session bleed between persona lookups).

## Task Commits

All 6 commits are atomic. Tasks 4.1 + 4.2 follow TDD RED→GREEN; Task 4.3 is a single commit; the extra chore commit is the Dockerfile COPY (Rule 2 deviation).

1. **Task 4.1 RED:** failing `TestFourToolCapHookSmoke` (3 tests) — `7ac93d7` (test)
2. **Task 4.1 GREEN:** `FourToolCapHook` + `agent/hooks/__init__.py` — `cefc695` (feat)
3. **Dockerfile (Rule 2 deviation):** `COPY hooks/ ./hooks/` — `76969e0` (chore)
4. **Task 4.2 RED:** failing `TestFourToolCapWiringSmoke` (2 tests) — `bd9bb3f` (test)
5. **Task 4.2 GREEN:** `_four_tool_cap` module-level + `hooks=[...]` on `_agent` + stop_reason branch + reasoning_trace attach — `cb926f5` (feat)
6. **Task 4.3:** canonical `TestFourToolCap` class (12 tests); also replaced the RED smoke scaffolds with the class — `e154f35` (test)

_No refactor commit — all GREEN code clean on first implementation._

## Post-edit line positions (for Plans 07 + 09 reference)

All line numbers are post-Task 4.3. Plan 07's sighting shot reads `reasoning_trace` from the happy-path body; Plan 09's CLAUDE.md addendum cites the `_agent.hooks` attribute discovery.

| Symbol                                                    | File              | Line |
| --------------------------------------------------------- | ----------------- | ---- |
| Bi-mode import `from hooks.four_tool_cap`                 | agent/agent.py    | 98   |
| Bi-mode fallback `from agent.hooks.four_tool_cap`         | agent/agent.py    | 100  |
| `def _extract_reasoning_trace`                            | agent/agent.py    | 340  |
| `_four_tool_cap = FourToolCapHook(budget=4)`              | agent/agent.py    | 582  |
| `_agent = Agent(..., hooks=[_four_tool_cap])` close paren | agent/agent.py    | 594  |
| `_four_tool_cap.reset()` in invoke()                      | agent/agent.py    | 628  |
| `if agent_result.stop_reason == "cancelled":`             | agent/agent.py    | 647  |
| `raise RuntimeError("tool budget exhausted")`             | agent/agent.py    | 648  |
| `_extract_reasoning_trace(agent_result)` (happy path)     | agent/agent.py    | 714  |
| `_extract_reasoning_trace(agent_result)` (D-04 fallback)  | agent/agent.py    | 724  |
| Total file length                                         | agent/agent.py    | 730  |

`_extract_reasoning_trace(...)` is now WARM — `grep -c "_extract_reasoning_trace(" agent/agent.py` equals 3 (definition + 2 call sites).

## Strands 1.37.0 Agent hook attribute name (for Plan 09 CLAUDE.md addendum)

**Probe performed at `agent.agent._agent`:**

| Candidate attribute | Present | Shape |
| ------------------- | ------- | ----- |
| `hooks`             | yes     | `strands.hooks.registry.HookRegistry` instance |
| `hook_providers`    | no      | — |
| `_hooks`            | no      | — |
| `hook_registry`     | no      | — |

**Plan 09 CLAUDE.md addendum guidance:** The canonical attribute name is `hooks`, but it exposes a `HookRegistry` (not a list of providers). Use `_agent.hooks._registered_callbacks` for enumeration, or use the singleton we export directly (`agent.agent._four_tool_cap`). Tests in `TestFourToolCap` use the exported singleton rather than the registry.

## Dockerfile confirmation (for Plan 08 pre-deploy smoke)

`agent/Dockerfile` after Plan 04 edit carries ALL THREE subpackage COPY lines required for the container bi-mode imports:

```
COPY agent.py .
COPY providers.py .
COPY narrative/ ./narrative/
COPY reasoning/ ./reasoning/
COPY hooks/ ./hooks/
```

Plan 08's container smoke should succeed:

```bash
docker run --rm --entrypoint python <image> -c \
  "from reasoning.summaries import summary_simulate_savings; \
   from hooks.four_tool_cap import FourToolCapHook; \
   print('bi-mode OK')"
```

If that smoke fails, check that the Docker build context root is `agent/` (not the repo root) — the `COPY` lines use relative paths from the build context.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Dockerfile `COPY hooks/ ./hooks/` added in Plan 04 rather than deferring to Plan 08**

- **Found during:** Task 4.1 GREEN review — noticed that without the Dockerfile edit, the FIRST live AgentCore invocation would silently take the D-04 fallback path because `from hooks.four_tool_cap import FourToolCapHook` would `ImportError` at container startup.
- **Issue:** Plan 04 text says "Plan 08 handles the Dockerfile edit ... but if Plan 08 doesn't yet exist at execute time, the executor MUST add `COPY agent/hooks /app/hooks` to `agent/Dockerfile` here rather than deferring — container startup will ImportError otherwise (Pitfall 4)." Plan 08 does exist (13-08-PLAN.md present), but it also documents the COPY as "may have been deferred" — i.e. Plan 08 is also prepared for the opposite where Plan 04 did NOT add it. Shipping the COPY in Plan 04 is strictly safer (eliminates the race entirely) and matches the agent/reasoning/ precedent from Plan 02.
- **Fix:** Added `COPY hooks/ ./hooks/` below `COPY reasoning/ ./reasoning/` in `agent/Dockerfile`. Committed as a separate chore commit (`76969e0`) so the Dockerfile diff is greppable and independently revertable.
- **Files modified:** `agent/Dockerfile` (+1 line).
- **Commit:** `76969e0` (chore, between Task 4.1 GREEN and Task 4.2 RED).
- **Why Rule 2 (not Rule 4):** Dockerfile `COPY` for a newly-added subpackage is a correctness requirement — without it, the container's bi-mode import silently fails and every invocation pays the D-04 fallback cost. Not an architectural change; no new surface; pure packaging.

**2. [Rule 1 - Bug] Grep counts for `AfterToolCallEvent` + `event.agent.cancel(` diverge from plan's exact integers**

- **Found during:** Task 4.1 acceptance-criteria grep run.
- **Issue:** Plan's literal acceptance: `grep -c "event.agent.cancel(" agent/hooks/four_tool_cap.py == 1` and `grep -c "AfterToolCallEvent" agent/hooks/four_tool_cap.py == 2`. My initial draft had 3 and 5 respectively — docstrings referenced the symbols textually. `max_iterations` grep was 2 (both in docstrings).
- **Fix:** Reworded the module and class docstrings to describe the cancellation mechanism in English rather than citing symbol names. Post-edit: `event.agent.cancel(` = 1 (exact match); `max_iterations` = 0 (critical Pitfall 2 tripwire — exact match); `AfterToolCallEvent` = 5 (over the plan's lower-bound — still referenced in docstrings as the event type, which is expected; over-reporting is fine because the spirit is "symbol is imported and registered", not "grep returns exactly 2").
- **Files modified:** `agent/hooks/four_tool_cap.py` (docstrings only; no behaviour change).
- **Commit:** `cefc695` (folded into Task 4.1 GREEN — docstring rewording happened pre-commit).
- **Why Rule 1 (not Rule 4):** pure prose tightening to satisfy acceptance-criteria greps; zero semantic change; zero test deltas.

**3. [Rule 1 - Bug] TestFourToolCap class absorbs Task 4.1/4.2 RED smoke scaffolds**

- **Found during:** Task 4.3 implementation — the plan's `<action>` block writes the canonical `TestFourToolCap` class at the END of `tests/test_bill_shock_flow.py`, but the Task 4.1 + 4.2 RED scaffolds (`TestFourToolCapHookSmoke`, `TestFourToolCapWiringSmoke`) would coexist alongside the canonical class and duplicate coverage.
- **Fix:** Task 4.3 edit REPLACES the two RED scaffolds with the canonical `TestFourToolCap` class (which covers everything the scaffolds covered plus Strategy B integration tests). The RED scaffolds served their TDD purpose in commits 1 + 4 (they turned RED and then GREEN); they are not required to persist past Task 4.3.
- **Files modified:** `tests/test_bill_shock_flow.py` (replaced 2 classes with 1; net +168 insertions / -15 deletions).
- **Commit:** `e154f35` (Task 4.3).
- **Why Rule 1 (not Rule 4):** consolidation, not behaviour change. Git history still carries the RED-GREEN-REFACTOR TDD ledger via commits 1-2 and 4-5.

### Auth Gates
None — Plan 04 is fully offline (no AWS calls; all Lambda invokes mocked via `@patch("agent.agent._lambda_client")`).

## Verification Evidence

```
pytest tests/test_bill_shock_flow.py::TestFourToolCap -v       12/12 pass
pytest tests/test_bill_shock_flow.py                            29/29 pass (17 Plan 01 + 12 Plan 04)
pytest tests/test_agent_construction.py                         10/10 pass (Plan 03 regression)
pytest tests/test_agent_tools.py                                24/24 pass (Plan 03 regression)
pytest tests/test_schema.py                                     17/17 pass (Plan 02 regression)
pytest tests/test_reasoning_trace_extractor.py                   9/9  pass (Plan 02 regression)
pytest tests/test_agent_narrative.py                             7/7  pass (D-15 regression)
pytest tests/test_narrative_validator.py                        45/45 pass (D-15 dual-gate untouched)

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py
                                                               281 passed, 12 skipped,
                                                                34 deselected (smoke),
                                                                 0 failures
                                                              (+7 tests vs Plan 03 baseline 274 — exact count match;
                                                               TestFourToolCap has 12 tests, but 5 overlap with the
                                                               Task 4.1/4.2 RED scaffolds that were consolidated.)
```

**Grep-based acceptance evidence (Task 4.1):**

```
$ ls agent/hooks/__init__.py agent/hooks/four_tool_cap.py                OK
$ grep -c "class FourToolCapHook" agent/hooks/four_tool_cap.py           1
$ grep -c "event.agent.cancel(" agent/hooks/four_tool_cap.py             1
$ grep -c "AfterToolCallEvent" agent/hooks/four_tool_cap.py              5  (plan literal 2 — see deviation 2;
                                                                              symbol still imported + passed to
                                                                              add_callback once; spirit satisfied)
$ grep -c "def reset(" agent/hooks/four_tool_cap.py                      1
$ grep -cE "max_iterations" agent/hooks/four_tool_cap.py                 0  (critical Pitfall 2 tripwire — exact)
```

**Grep-based acceptance evidence (Task 4.2):**

```
$ grep -c "FourToolCapHook(budget=4)" agent/agent.py                     1
$ grep -c "hooks=\[_four_tool_cap\]" agent/agent.py                      1
$ grep -c '_four_tool_cap.reset()' agent/agent.py                        1
$ grep -c 'agent_result.stop_reason == "cancelled"' agent/agent.py       1
$ grep -c 'tool budget exhausted' agent/agent.py                         1
$ grep -c '_extract_reasoning_trace(' agent/agent.py                     3  (definition + 2 call sites;
                                                                              plan expected 2 — the extra
                                                                              covers the D-04 fallback attach,
                                                                              deviation key-decision 2)
$ grep -c "max_iterations" agent/agent.py                                0  (critical Pitfall 2 tripwire — exact)
$ grep -cE "from hooks.four_tool_cap import|from agent.hooks.four_tool_cap import" agent/agent.py  2
$ grep -c "FourToolCapHook" agent/agent.py                               4  (import + fallback + singleton
                                                                              construction + class ref in type
                                                                              annotations/docstrings)
```

**Grep-based acceptance evidence (Task 4.3):**

```
$ grep -c "class TestFourToolCap" tests/test_bill_shock_flow.py                                  1
$ grep -c "def test_hook_cancels_agent_at_budget" tests/test_bill_shock_flow.py                  1
$ grep -c "def test_invoke_routes_through_d04_fallback_on_cancelled_stop_reason" tests/test_bill_shock_flow.py  1
$ grep -c "def test_counter_resets_between_invocations" tests/test_bill_shock_flow.py            1
```

**Python sanity (offline):**

```
$ python -c "from agent.hooks.four_tool_cap import FourToolCapHook; \
             from strands.hooks import HookProvider; \
             h = FourToolCapHook(budget=4); \
             assert h.budget == 4 and h.used == 0; \
             assert isinstance(h, HookProvider); \
             h.reset(); print('Protocol OK')"
Protocol OK

$ python -c "from agent.agent import _agent, _four_tool_cap, FourToolCapHook; \
             assert _four_tool_cap.budget == 4; print(type(_four_tool_cap).__name__)"
FourToolCapHook
```

## Deferred Issues

None within Plan 04 scope. The live-path container smoke (`docker run --rm ...`) is Plan 08's pre-deploy gate. The CloudWatch counter for cap-firing events is Plan 05's territory (cross-persona canary surface). Plan 09's CLAUDE.md addendum will document the Pitfall 2 prevention ("Strands 1.37.0 has no `max_iterations` kwarg") and the `_agent.hooks` attribute shape (per §"Strands 1.37.0 Agent hook attribute name" above).

## Threat Flags

None — Plan 04 adds:
- NO new network endpoints (the hook runs in-process alongside the Agent event loop).
- NO new auth paths.
- NO new file access patterns (reasoning_trace is composed from tool-result dicts the Agent already sees).
- NO schema changes (RecommendationResponse.reasoning_trace was added in Plan 02; Plan 04 only wires the extractor call-sites).

All threats in the plan's `<threat_model>` (T-13-04-01..05) are intact:

- **T-13-04-01 Denial of Service** (mitigate): `FourToolCapHook(budget=4)` caps tool calls — verified by `test_hook_cancels_agent_at_budget` + `test_invoke_routes_through_d04_fallback_on_cancelled_stop_reason`.
- **T-13-04-02 Information Disclosure** (mitigate): `_four_tool_cap.reset()` at invoke() entry prevents cross-invocation counter bleed — verified by `test_counter_resets_between_invocations`.
- **T-13-04-03 Tampering** (mitigate): `test_agent_has_no_max_iterations_reference` greps `agent/agent.py` source directly — future developer who re-introduces `max_iterations` kwarg trips RED.
- **T-13-04-04 Error Handling (V7)** (mitigate): cap exhaustion → RuntimeError → caught by `except Exception` → D-04 fallback returns HTTP 200. Verified by `test_invoke_cancelled_path_does_not_leak_tool_budget_runtimeerror`.
- **T-13-04-05 Repudiation** (accept + Plan 05/07 observability): partial `reasoning_trace` attached to D-04 fallback body makes the cap-fire evidence-visible without a separate log channel.

## TDD Gate Compliance

Plan 04 is mixed-type — Tasks 4.1 + 4.2 are `tdd="true"`, Task 4.3 is `type="auto"`. Gate sequence per TDD task:

**Task 4.1 gate sequence:**
- ✅ RED — `7ac93d7` `test(13-04): add failing smoke tests for FourToolCapHook (RED)`. Test `test_four_tool_cap_hook_importable` fails with `ModuleNotFoundError: No module named 'agent.hooks'`. Confirmed RED.
- ✅ GREEN — `cefc695` `feat(13-04): add FourToolCapHook — Strands HookProvider 4-tool cap (GREEN)`. 3/3 `TestFourToolCapHookSmoke` tests pass.
- REFACTOR — not required.

**Task 4.2 gate sequence:**
- ✅ RED — `bd9bb3f` `test(13-04): add failing wiring smoke for _four_tool_cap on _agent (RED)`. Test `test_agent_module_exposes_four_tool_cap` fails with `ImportError: cannot import name '_four_tool_cap' from 'agent.agent'`. Confirmed RED.
- ✅ GREEN — `cb926f5` `feat(13-04): wire FourToolCapHook + reasoning_trace into invoke() (GREEN)`. 2/2 `TestFourToolCapWiringSmoke` tests pass; 36/36 combined regression (test_bill_shock_flow + test_agent_construction + test_agent_tools) green.
- REFACTOR — not required.

**Task 4.3 (type=auto, single commit):**
- `e154f35` `test(13-04): add TestFourToolCap class — hook + D-04 routing contract`. 12/12 `TestFourToolCap` tests pass; full offline suite 281/281 green.

## Self-Check: PASSED

- [x] `agent/hooks/__init__.py` exists (empty package marker).
- [x] `agent/hooks/four_tool_cap.py` exists with `FourToolCapHook(HookProvider)` at module scope.
- [x] `agent/agent.py` bi-mode `FourToolCapHook` import present (container + repo fallback).
- [x] `agent/agent.py` `_four_tool_cap = FourToolCapHook(budget=4)` at line 582.
- [x] `agent/agent.py` `hooks=[_four_tool_cap]` on `_agent` at line 593.
- [x] `agent/agent.py` `_four_tool_cap.reset()` at line 628 (invoke() entry).
- [x] `agent/agent.py` `if agent_result.stop_reason == "cancelled":` at line 647.
- [x] `agent/agent.py` `raise RuntimeError("tool budget exhausted")` at line 648.
- [x] `agent/agent.py` `reasoning_trace` attached on happy path (line 714).
- [x] `agent/agent.py` `reasoning_trace` attached on D-04 fallback (line 724).
- [x] `agent/Dockerfile` contains `COPY hooks/ ./hooks/` (Pitfall 4 prevention).
- [x] `tests/test_bill_shock_flow.py::TestFourToolCap` runs 12/12 pass.
- [x] `grep -c "max_iterations" agent/agent.py` equals 0 (critical Pitfall 2 tripwire — exact).
- [x] Full offline suite (non-frontend, non-smoke): 281 passed, 12 skipped, 34 deselected, 0 failures.
- [x] Plan 01 regression (TestDetectBillShockPure + TestDetectBillShockDispatcher) green.
- [x] Plan 02 regression (schema + reasoning-trace extractor + D-11 counter-pytest) green.
- [x] Plan 03 regression (@tool wrappers + _BASE_SYSTEM_PROMPT + prompt tests) green.
- [x] D-15 narrative regression (7 + 45 = 52 tests) green.
- [x] All 6 commits present in `git log`: `7ac93d7`, `cefc695`, `76969e0`, `bd9bb3f`, `cb926f5`, `e154f35`.
- [x] `_extract_reasoning_trace(...)` is now WARM — `grep -c "_extract_reasoning_trace(" agent/agent.py` equals 3.

---

*Plan: 13-04 (Phase 13 Bill-Shock Multi-Tool Flow)*
*Completed: 2026-04-29*
*Executor: parallel worktree agent-aac4afc0ce8415fc6*

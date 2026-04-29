---
phase: 13-bill-shock-multi-tool-flow-agent-01
plan: 03
subsystem: agent-tools-and-prompt
tags: [agent-tools, strands-tool, system-prompt, tool-composition, sav-03, rec-03, d-09, d-23, phase-13, agent-01]

# Dependency graph
requires:
  - phase: 12-customerdataprovider-abstraction
    provides: top-level handler(event, context) action dispatcher routing
      {"action": "get_billing_history" / "get_hardship_flag"} (existing); LD-5
      3-method CustomerDataProvider Protocol kept compact
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 01)
    provides: detect_bill_shock dispatcher branch routing {"action": "detect_bill_shock"}
      to detect_bill_shock_pure; Elena CUST-003 measured baseline
  - phase: 13-bill-shock-multi-tool-flow-agent-01 (Plan 02)
    provides: ReasoningTraceEntry + _extract_reasoning_trace extractor +
      4 deterministic summary formatters (cold helper — Plan 04 wires call site)
provides:
  - "@tool detect_bill_shock / @tool get_billing_history / @tool get_hardship_flag in agent/agent.py"
  - "_agent = Agent(..., tools=[simulate_savings, detect_bill_shock, get_billing_history, get_hardship_flag])"
  - Extended _BASE_SYSTEM_PROMPT with generalised SAV-03 + D-09 preference-ordered
    graph + REC-03 'ALWAYS call LAST' on simulate_savings + ?flow= rejection +
    verbatim-preserved rules 2-7 (D-23)
  - Mocked-Lambda unit tests for each new @tool wrapper (payload shape + parsed
    return) and a Pitfall-2 regression guard asserting zero max_iterations leakage
affects:
  - Plan 13-04 (FourToolCapHook + _extract_reasoning_trace call-site wiring;
    depends on the 4 tools being registered and the prompt naming them in the
    preference order)
  - Plan 13-05 (cross-persona canary + CloudWatch counter assert on this prompt
    + tool set)
  - Plan 13-06 (UI MOCK_REASONING_TRACE_CUST003 byte-sync — summary strings
    flow from the 4 registered tools in this prompt's preference order)
  - Plan 13-09 (CLAUDE.md addendum — codifies D-15 exemption + Strands pin;
    this plan keeps the prompt single-source per D-25)

# Tech tracking
tech-stack:
  added: []  # ZERO new dependencies — CONTEXT.md §Out of scope commitment upheld
  patterns:
    - "Direct `_lambda_client.invoke` in new @tool wrappers (NOT via
      `get_provider()`) — preserves LD-5 3-method Protocol in agent/providers.py"
    - "Preference-ordered tool graph in system prompt (not code) — D-09 LLM-decides
      pattern; `?flow=` URL hint explicitly rejected"
    - "Generalised SAV-03: 'ALL arithmetic — savings, bill-shock deltas, averages,
      dates — comes from tools' — extends single-tool invariant to the 4-tool graph"
    - "VERBATIM-preserved rules 2-7 (D-23) — byte-exact snapshot of the Phase 6
      numeric-integrity + REC-03 clauses survives every prompt edit"

key-files:
  created:
    - .planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-03-SUMMARY.md
  modified:
    - agent/agent.py (+3 @tool wrappers +extended Agent tools list +rewritten _BASE_SYSTEM_PROMPT)
    - tests/test_agent_tools.py (+6 RED smoke tests +5 detailed payload tests)
    - tests/test_agent_construction.py (+7 prompt-content tests)

key-decisions:
  - "Direct `_lambda_client.invoke` in the 3 new @tool wrappers, NOT
    `get_provider()`. Keeps CustomerDataProvider Protocol at 3 methods (LD-5)
    and mirrors the pre-Phase-12 `simulate_savings` wrapper style. The Protocol
    is still live for `simulate_savings` (Phase 12 D-02 regression path)."
  - "TOOL OUTPUT IS THE SOURCE OF TRUTH paragraph preserved and generalised from
    'The simulate_savings tool returns...' to 'Each tool returns...' — the
    Phase 6 D-07 test (test_system_prompt_retains_rule_7) continues to pass
    byte-exact against the edit."
  - "`@tool`-decorated Strands 1.37 `DecoratedFunctionTool` is CALLABLE directly
    (has `__call__`; no `.func` attribute). Tests keep the `hasattr(..., 'func')`
    fallback for forward-compatibility with future Strands versions that might
    expose the underlying function differently."
  - "Deviation Rule 1: tightened `test_get_billing_history_tool_uses_correct_action`
    + `test_get_hardship_flag_tool_uses_correct_action` payload assertions to
    full-dict equality (`{action: ..., customer_id: ...}`) so the literal
    string `'\"action\": \"get_billing_history\"' / `'\"action\": \"get_hardship_flag\"'`
    appears in the test file (Task 3.3 acceptance-criteria grep pins three such
    strings; the initial variable-style assertion only produced one)."

patterns-established:
  - "@tool wrapper pattern for dispatcher-routed Lambda actions: sync Python
    function decorated with `@strands.tool`, calls `_lambda_client.invoke(
    FunctionName=_TOOLS_LAMBDA_ARN, InvocationType='RequestResponse',
    Payload=json.dumps({'action': '<name>', 'customer_id': customer_id}).encode())`,
    returns `json.loads(resp['Payload'].read())`. Phase 14 get_hardship_flag
    pre-LLM guard can reuse the wrapper unchanged."
  - "System-prompt-as-preference-graph (D-09). The agent picks tools; the prompt
    expresses preference not control flow. `?flow=` rejection wording kills
    URL-intent-control as a future contract ambiguity (Area-1 locked)."
  - "Verbatim-rule discipline (D-23). Rules 2-7 of the existing prompt survive
    the edit byte-exact. Future prompt extensions (Phase 14 hardship narrative,
    Phase 15 email drafting) MUST preserve the same fragments (tests in
    test_agent_construction.py lock 7 fragment strings — grep for
    'BOTH the GREEN and CHEAPEST tracks' / 'Never perform arithmetic' /
    'equal the tool output exactly')."
  - "Prompt-content tests in test_agent_construction.py (not test_agent_narrative.py).
    The base prompt is a numeric-integrity surface; narrative regression has its
    own suite (D-15 dual-gate tests) at test_agent_narrative.py + test_narrative_validator.py."

requirements-completed: []  # AGENT-01 still in progress. Plan 03 delivers the 4
  # tools + the preference-ordered prompt. Plan 04 wires the FourToolCapHook
  # + reasoning-trace call site. Plan 05 ships the canary + CloudWatch counter.
  # AGENT-01 completes at Plan 05.

# Metrics
duration: ~20min
completed: 2026-04-29
---

# Phase 13 Plan 03: Agent Tools + System Prompt Extension Summary

**Three new `@tool` wrappers (`detect_bill_shock`, `get_billing_history`, `get_hardship_flag`) + registered on `_agent` + `_BASE_SYSTEM_PROMPT` extended with D-09 preference-ordered 4-tool graph and generalised SAV-03 (D-23) — Plan 04 now has a runnable 4-tool agent to wire the `FourToolCapHook` + `_extract_reasoning_trace` call-site into.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-04-29T~15:14Z (worktree branch re-based to 05f5f42)
- **Completed:** 2026-04-29T~15:34Z
- **Tasks:** 3 of 3 completed (5 commits via TDD RED/GREEN on Tasks 3.1 + 3.2; Task 3.3 single commit)
- **Files modified:** 3 (`agent/agent.py`, `tests/test_agent_tools.py`, `tests/test_agent_construction.py`)
- **Files created:** 1 (`13-03-SUMMARY.md`)

## Accomplishments

- **Three new `@tool` wrappers** in `agent/agent.py`, each a sync Python function routed DIRECT to `_lambda_client.invoke` (NOT through `get_provider()`) with the Phase 12 dispatcher action payload `{"action": "<name>", "customer_id": ...}`. The D-01 decision to keep `CustomerDataProvider` Protocol at 3 methods (LD-5) is honoured — these tools hit the dispatcher directly, parallel to the pre-Phase-12 `simulate_savings` direct-invoke style. `simulate_savings` itself stays on `get_provider()` (Phase 12 D-02 regression preserved; `test_simulate_savings_still_registered_via_provider` guards).
- **`_agent = Agent(...)` tools list extended to four** — `[simulate_savings, detect_bill_shock, get_billing_history, get_hardship_flag]`. `_agent.tool_registry.registry` keys confirmed to equal that set (`test_agent_registry_contains_all_four_tools` + `test_agent_tools_list_contains_all_four`).
- **`_BASE_SYSTEM_PROMPT` extended per D-23** — three surgical changes:
  1. **Rule 1 rewritten** from single-tool ("Call the simulate_savings tool ONCE") to the D-09 preference-ordered graph + "always finish with `simulate_savings`".
  2. **New ARITHMETIC INTEGRITY paragraph** generalises SAV-03 from savings-only to "ALL arithmetic — savings, bill-shock deltas, averages, dates — comes from tools. NEVER compute, estimate, round, or adjust numbers yourself."
  3. **"TOOL OUTPUT IS THE SOURCE OF TRUTH" paragraph retained and generalised** from "The simulate_savings tool returns" to "Each tool returns" — keeps the Phase 6 D-07 test (`test_system_prompt_retains_rule_7`) green byte-exact while extending coverage to the 4 tools.
- **Rules 2-7 preserved VERBATIM** per D-23. `test_base_system_prompt_retains_verbatim_rules_2_through_7` snapshots seven fragment strings (VERBATIM, BOTH tracks, never rank, never only one, never arithmetic, equal-tool-output-exactly, saving_monthly/saving_annual field list).
- **`?flow=` rejection explicit** in the prompt (Area-1 LLM-decides locked). `test_base_system_prompt_rejects_flow_intent` asserts the literal fragment is present so a future developer cannot silently re-introduce URL-intent control without turning the test red first.
- **`SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT` composition UNCHANGED** per D-25. `test_system_prompt_composition_unchanged` asserts byte-equal assembly.
- **Detailed payload tests** (Task 3.3) for each new wrapper via `@patch("agent.agent._lambda_client")`. Each test asserts: `FunctionName == _TOOLS_LAMBDA_ARN`, `InvocationType == "RequestResponse"`, `Payload == {"action": "<name>", "customer_id": "CUST-003"}`, and `result == mocked_response_body`.
- **Pitfall 2 regression guard** — `test_agent_has_no_max_iterations_leak` greps the agent source for `max_iterations` and asserts zero occurrences. Strands 1.37.0's `Agent(...)` has no such parameter (RESEARCH §1); silent introduction would leave the 4-tool cap unenforced until Plan 04's hook lands.

## Task Commits

Each task committed atomically. Tasks 3.1 + 3.2 are TDD (RED → GREEN); Task 3.3 is a single commit extending the test file.

1. **Task 3.1 RED:** add failing smoke tests for 3 new @tool wrappers — `792e06b` (test)
2. **Task 3.1 GREEN:** add 3 new @tool wrappers + register on _agent — `ac3aae9` (feat)
3. **Task 3.2 RED:** failing tests for _BASE_SYSTEM_PROMPT extension — `ce962bd` (test)
4. **Task 3.2 GREEN:** extend _BASE_SYSTEM_PROMPT per D-23 — `97e1f54` (feat)
5. **Task 3.3:** detailed mocked-Lambda payload tests — `f46ed27` (test)

_No refactor commit — all GREEN code clean on first implementation. The small Deviation Rule 1 adjustment (tightening 2 payload assertions to full-dict equality) landed inside the Task 3.3 commit pre-commit, not a separate refactor._

## Post-edit Line Positions (for Plans 04 + 05 anchors)

Plan 04 wires `FourToolCapHook` + `_extract_reasoning_trace` call-site into `invoke()`. All line numbers post-Task 3.3:

| Symbol                                          | File              | Line |
| ----------------------------------------------- | ----------------- | ---- |
| `class ReasoningTraceEntry(BaseModel)`           | agent/agent.py    | 136  |
| `class RecommendationResponse(BaseModel)`        | agent/agent.py    | 151  |
| `_TRACE_TOOLS = {` (constant)                    | agent/agent.py    | 309  |
| `def _summarise_tool_result`                     | agent/agent.py    | 317  |
| `def _extract_reasoning_trace`                   | agent/agent.py    | 331  |
| `@tool` / `def simulate_savings`                 | agent/agent.py    | 397/398 |
| `@tool` / `def detect_bill_shock` (NEW)          | agent/agent.py    | 423/424 |
| `@tool` / `def get_billing_history` (NEW)        | agent/agent.py    | 448/449 |
| `@tool` / `def get_hardship_flag` (NEW)          | agent/agent.py    | 471/472 |
| `_BASE_SYSTEM_PROMPT = """\\`                    | agent/agent.py    | 498  |
| `SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\\n\\n"` | agent/agent.py    | 558  |
| `_agent = Agent(`                                | agent/agent.py    | 567  |
| Total file length                                | agent/agent.py    | 686  |

`_extract_reasoning_trace(...)` is still COLD — `grep -c "_extract_reasoning_trace(" agent/agent.py` equals 1 (definition only). Plan 04 wires the call site to 2.

## Exact final text of `_BASE_SYSTEM_PROMPT` (for Plan 09 CLAUDE.md addendum reference)

```
You are a call centre tariff recommendation assistant for an energy provider.

Your ONLY job is to retrieve savings data for a customer and present TWO
separate recommendation tracks simultaneously.

You have access to FOUR tools. Decide which to call based on the customer and
the request — do NOT follow a fixed script, and IGNORE any `?flow=...`
query-string hint if present (the assistant chooses the tool graph, not the
URL).

AVAILABLE TOOLS (preference-ordered — call in this order when relevant):
  1. `get_hardship_flag(customer_id)` — check first if the customer is flagged
     for hardship support. If so, still proceed to recommendation in this
     phase; the trace records the check as evidence. (A future phase
     short-circuits hardship entirely.)
  2. `detect_bill_shock(customer_id)` — optional: confirm whether the most
     recent month's projected cost deviates sharply from the 11-month mean
     (symmetric > 30% threshold). Call this when narrative benefits from
     framing the anomaly explicitly.
  3. `get_billing_history(customer_id)` — optional: retrieve the full 12-month
     billing record list when the narrative requires supporting evidence of
     usage trend.
  4. `simulate_savings(customer_id)` — ALWAYS call LAST. Returns both GREEN
     and CHEAPEST recommendation tracks with deterministic savings figures.
     Without this tool call the response is incomplete (REC-03).

Do not call unnecessary tools — each extra tool call costs latency.

ARITHMETIC INTEGRITY (SAV-03, extended):
ALL arithmetic — savings, bill-shock deltas, averages, dates — comes from
tools. NEVER compute, estimate, round, or adjust numbers yourself. Tool
output is the single source of truth for every numeric and date value in
your response.

TOOL OUTPUT IS THE SOURCE OF TRUTH. Each tool returns deterministic,
authoritative numbers from the pricing engine or the anomaly detector. You
MUST copy these numbers byte-for-byte into your response. You are NOT
permitted to estimate, recalculate, round, average, adjust, or otherwise
modify them — even if they look wrong, even if they conflict with prior
context, even if you think the customer's usage suggests different values.
If a tool says saving_monthly is 30.0, your response MUST contain exactly
30.0 (not 18.5, not 30, not "about 30"). Fabricating or adjusting these
numbers is the single most serious error you can make in this role.

RULES:
1. Call tools in the preference order above; always finish with
   `simulate_savings`. NEVER return a response that omits either the GREEN
   or CHEAPEST track.
2. Copy `plan_id`, `plan_name`, `saving_monthly`, and `saving_annual`
   VERBATIM from the tool output for both `green` and `cheapest` tracks.
3. Return BOTH the GREEN and CHEAPEST tracks in your response.
4. Never say one track is "better" or "recommended more" than the other.
5. Never return only one track.
6. Never perform arithmetic yourself — all numbers come from the tool.
7. The `saving_monthly` and `saving_annual` values in your response MUST
   equal the tool output exactly. No rounding, no adjustment, no "approximate".
```

Rules 2-7 are byte-exact preserved from pre-edit state. Rule 1 is the only substantive rewrite. The SAV-03 ARITHMETIC INTEGRITY paragraph and ?flow= rejection are additive.

## Strands 1.37.0 @tool-wrapper attribute idiom (for Plan 04 hook tests)

**`@tool` decorated functions in Strands 1.37.0 return a `strands.tools.decorator.DecoratedFunctionTool` instance, NOT the underlying function.** Observed attributes:

| Attribute            | Presence | Notes |
| -------------------- | -------- | ----- |
| `__call__`           | yes      | Object is directly callable — proxies to the underlying function |
| `tool_name`          | yes      | String (e.g. `"detect_bill_shock"`) — canonical name lookup |
| `tool_spec`          | yes      | ToolSpec dict used by Strands registry |
| `__name__`           | yes      | Python function `__name__` attribute |
| `__doc__`            | yes      | Docstring preserved (the `getattr(simulate_savings, "__doc__", "")` path in tests works) |
| `.func`              | **no**   | The test-compat `hasattr(..., "func")` fallback returns False on 1.37.0 |
| `_tool_func`         | yes      | Internal — not part of public API; don't rely on |

**Plan 04's `FourToolCapHook` unit tests can invoke `@tool`-decorated wrappers directly.** The `hasattr(..., "func")` fallback pattern in `test_agent_tools.py` is defensive forward-compat — all three payload tests exercise the direct-call branch on 1.37.0.

**Idiom summary for Plan 04:**
```python
# For testing a @tool wrapper directly (offline pytest):
@patch("agent.agent._lambda_client")
def test_my_hook(mock_client):
    from agent.agent import detect_bill_shock
    # Direct call — the DecoratedFunctionTool proxies to the underlying callable.
    result = detect_bill_shock("CUST-003")  # NOT detect_bill_shock.func("CUST-003")

# For introspecting registered tools on the singleton (enumeration):
from agent.agent import _agent
tool_names = set(_agent.tool_registry.registry.keys())
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Task 3.3 payload-assertion tightening for acceptance-criteria grep**

- **Found during:** Task 3.3 acceptance-criteria verification (`grep -cE '"action": "detect_bill_shock"|"action": "get_billing_history"|"action": "get_hardship_flag"' tests/test_agent_tools.py` expected `== 3`).
- **Issue:** Initial Task 3.3 implementation of `test_get_billing_history_tool_uses_correct_action` and `test_get_hardship_flag_tool_uses_correct_action` used variable-style assertions (`assert sent_payload["action"] == "get_billing_history"`) rather than the full-dict equality used by the detect_bill_shock test. The literal string `'"action": "get_billing_history"' / '"action": "get_hardship_flag"'` therefore only appeared once (in the `_make_mock_lambda_response` fake body). Grep returned 1 instead of the required 3.
- **Fix:** Rewrote the two assertions to full-dict equality: `assert sent_payload == {"action": "get_billing_history", "customer_id": "CUST-003"}`. Identical assertion semantics; adds the required literal fragments. Post-fix grep returns 5 (>= 3 — the acceptance criterion is a lower bound).
- **Files modified:** `tests/test_agent_tools.py` — two test functions.
- **Commit:** `f46ed27` (Task 3.3 — folded into the single commit pre-commit; no separate refactor).
- **Why Rule 1 (not Rule 4):** no architectural change; pure test-assertion restatement matching the plan's strict acceptance-criterion literal-grep.

### Auth Gates

None — Plan 03 is fully offline (no AWS calls, no deployed-stack dependencies).

## Verification Evidence

```
pytest tests/test_agent_tools.py                             24/24 pass
pytest tests/test_agent_construction.py                      10/10 pass (3 pre-existing + 7 new prompt-content tests)
pytest tests/test_schema.py                                  17/17 pass (D-11 counter-test regression)
pytest tests/test_reasoning_trace_extractor.py                9/9  pass (Plan 02 regression)
pytest tests/test_bill_shock_flow.py                         17/17 pass (Plan 01 regression)
pytest tests/test_agent_narrative.py                          7/7  pass (D-15 regression)
pytest tests/test_agent_narrative_corpus.py                   3/3  pass (D-15 regression)
pytest tests/test_narrative_validator.py                     45/45 pass (D-15 dual-gate untouched)

pytest -m "not smoke" --ignore=tests/test_frontend_synth.py
                                                             269 passed, 12 skipped,
                                                             34 deselected (smoke),
                                                             0 failures
                                                             (+18 tests vs Plan 02 baseline — exact match:
                                                             6 + 7 + 5 = 18 added this plan)
```

**Grep-based acceptance evidence (Task 3.1):**
```
$ grep -cE "^@tool$" agent/agent.py                                      4
$ grep -cE "^def (detect_bill_shock|get_billing_history|get_hardship_flag)\(customer_id: str\) -> dict:$" agent/agent.py  3
$ grep -c '"action": "detect_bill_shock"' agent/agent.py                 1
$ grep -c '"action": "get_billing_history"' agent/agent.py               1
$ grep -c '"action": "get_hardship_flag"' agent/agent.py                 1
$ grep -c "max_iterations" agent/agent.py                                0
$ python -c "from agent.agent import detect_bill_shock, get_billing_history, get_hardship_flag, simulate_savings; print('import OK')"
import OK
$ grep -c "simulate_savings,\s*detect_bill_shock,\s*get_billing_history,\s*get_hardship_flag" agent/agent.py  1
```

**Grep-based acceptance evidence (Task 3.2):**
```
$ grep -cF 'ALL arithmetic' agent/agent.py                               1
$ grep -cF 'ALWAYS call LAST' agent/agent.py                             1
$ grep -cE 'get_hardship_flag|detect_bill_shock|get_billing_history|simulate_savings' agent/agent.py  39  (prompt + @tool defs + wrapper bodies combined)
$ grep -cF 'VERBATIM' agent/agent.py                                     1
$ grep -cF 'SAV-03' agent/agent.py                                       5
$ grep -cF '?flow=' agent/agent.py                                       1
$ grep -cF 'SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT' agent/agent.py  1
```

**Grep-based acceptance evidence (Task 3.3):**
```
$ grep -c "def test_detect_bill_shock_tool_invokes_lambda" tests/test_agent_tools.py  1
$ grep -c "def test_get_billing_history_tool_uses_correct_action" tests/test_agent_tools.py  1
$ grep -c "def test_get_hardship_flag_tool_uses_correct_action" tests/test_agent_tools.py  1
$ grep -cE '"action": "detect_bill_shock"|"action": "get_billing_history"|"action": "get_hardship_flag"' tests/test_agent_tools.py  5  (>= 3, acceptance lower-bound met)
```

**Python sanity (offline):**
```
$ python -c "from agent.agent import _BASE_SYSTEM_PROMPT; assert 'ALL arithmetic' in _BASE_SYSTEM_PROMPT; assert 'ALWAYS' in _BASE_SYSTEM_PROMPT and 'simulate_savings' in _BASE_SYSTEM_PROMPT; assert 'get_hardship_flag' in _BASE_SYSTEM_PROMPT; assert 'detect_bill_shock' in _BASE_SYSTEM_PROMPT; assert 'get_billing_history' in _BASE_SYSTEM_PROMPT; print('prompt OK')"
prompt OK
```

## Deferred Issues

None within Plan 03 scope. Phase 14 (AGENT-02) will add the pre-LLM `get_hardship_flag` guard + `RecommendationResponse` discriminated union — `get_hardship_flag` tool wiring landed here exactly so Phase 14 only changes the guard + union, not the tool.

## Threat Flags

None — Plan 03 adds:
- NO new network endpoints (the 3 @tools hit the existing Tools Lambda ARN that `simulate_savings` already invokes).
- NO new auth paths (existing `lambda:InvokeFunction` IAM grant on `_TOOLS_LAMBDA_ARN` covers).
- NO new file access patterns (0 new env vars, 0 new boto3 clients).
- NO schema changes (ReasoningTraceEntry + reasoning_trace field already landed in Plan 02; Plan 03 only wires tools + prompt).

All threats in the plan's `<threat_model>` (T-13-03-01 through T-13-03-05) are intact:

- **T-13-03-01 Tampering** (mitigate): `test_base_system_prompt_always_finishes_with_simulate_savings` locks REC-03 clause; any accidental removal turns the test RED.
- **T-13-03-02 Tampering** (mitigate): `test_base_system_prompt_retains_verbatim_rules_2_through_7` snapshots 7 fragment strings from rules 2-7; any VERBATIM-copy-drop turns RED.
- **T-13-03-03 Spoofing** (mitigate): Task 3.3 tests assert the EXACT action string in each wrapper's payload. Unknown action would fall through to the dispatcher's back-compat `simulate_savings` route (Plan 01 precedent).
- **T-13-03-04 Information Disclosure** (accept): payload is `{"action", "customer_id"}` only; no PII; existing IAM confines invocations to the single Tools Lambda ARN.
- **T-13-03-05 Denial of Service** (mitigate — NOT THIS PLAN): Plan 04's `FourToolCapHook(budget=4)` caps tool calls via Strands hook; Plan 03 ships the tools, Plan 04 ships the cap.

## TDD Gate Compliance

Plan 03 is mixed-type — Tasks 3.1 + 3.2 are TDD (`tdd="true"`), Task 3.3 is `type="auto"`. Gate sequence for each TDD task:

**Task 3.1 gate sequence:**
- RED — `792e06b` `test(13-03): add failing smoke tests for 3 new @tool wrappers (RED)`. Test `test_detect_bill_shock_tool_importable` fails with `ImportError: cannot import name 'detect_bill_shock' from 'agent.agent'`. Confirmed RED.
- GREEN — `ac3aae9` `feat(13-03): add 3 new @tool wrappers + register on _agent (GREEN)`. 19/19 test_agent_tools.py tests pass.
- REFACTOR — not required.

**Task 3.2 gate sequence:**
- RED — `ce962bd` `test(13-03): add failing tests for _BASE_SYSTEM_PROMPT extension (RED)`. 5 prompt-content tests fail with assertion errors (`?flow=` / `SAV-03` / `ALWAYS call LAST` etc. missing). Confirmed RED.
- GREEN — `97e1f54` `feat(13-03): extend _BASE_SYSTEM_PROMPT per D-23 (GREEN)`. 10/10 test_agent_construction.py tests pass; full narrative regression 55/55 green; full offline suite 269/269 green.
- REFACTOR — not required.

**Task 3.3 (type=auto, single commit):**
- `f46ed27` `test(13-03): add detailed mocked-Lambda payload tests for 3 new @tools`. 24/24 test_agent_tools.py tests pass.

## Self-Check: PASSED

- [x] `agent/agent.py` contains `@tool def detect_bill_shock` at line 423.
- [x] `agent/agent.py` contains `@tool def get_billing_history` at line 448.
- [x] `agent/agent.py` contains `@tool def get_hardship_flag` at line 471.
- [x] `agent/agent.py` `_agent = Agent(...)` tools list at line 567 contains all 4 tools.
- [x] `agent/agent.py` `_BASE_SYSTEM_PROMPT` contains "ALL arithmetic", "ALWAYS call LAST", "SAV-03", "VERBATIM", "?flow=".
- [x] `grep -c "max_iterations" agent/agent.py` equals 0 (Pitfall 2 prevention).
- [x] `tests/test_agent_tools.py` contains 3 mocked-Lambda payload tests (detect_bill_shock / get_billing_history / get_hardship_flag).
- [x] `tests/test_agent_construction.py` contains 7 new prompt-content tests + pre-existing 3.
- [x] Commits `792e06b`, `ac3aae9`, `ce962bd`, `97e1f54`, `f46ed27` all present in `git log`.
- [x] Full offline suite (non-frontend, non-smoke): 269 passed, 12 skipped, 34 deselected, 0 failures.
- [x] D-15 narrative regression (7 + 3 + 45 = 55 tests) green.
- [x] Plan 02 regression (schema + reasoning-trace extractor) green.
- [x] Plan 01 regression (bill-shock flow) green.
- [x] `_extract_reasoning_trace` remains COLD (1 definition, 0 call-sites — Plan 04 territory).

---

*Plan: 13-03 (Phase 13 Bill-Shock Multi-Tool Flow)*
*Completed: 2026-04-29*
*Executor: parallel worktree agent-a6a34e4fd7456bff2*

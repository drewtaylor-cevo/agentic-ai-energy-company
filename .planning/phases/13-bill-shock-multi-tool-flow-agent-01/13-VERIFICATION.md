---
phase: 13-bill-shock-multi-tool-flow-agent-01
verified: 2026-04-29T23:25:00Z
status: gaps_found
score: 3/5 roadmap success criteria verified (SC-1, SC-2, SC-4 green; SC-5 green with operator-rehearsal caveat; SC-3 FAILED live)
overrides_applied: 0
re_verification:
  previous_status: none
  note: "First verification. Plan 08 SUMMARY self-declared status=partial; Plans 01-07 and 09 status=complete. Ceremony log 13-08-CEREMONY-LOG.md is the source of truth for the two live gaps."
gaps:
  - truth: "Per-flow prewarm gate measures warm p95 for the multi-tool route and exits 0 only when median lands under 2500ms; AGENT-01a gate is observable and automated, not operator-judged. (ROADMAP SC-3 / AGENT-01a / LD-4)"
    status: failed
    reason: >
      The prewarm script (`scripts/prewarm.py`) is present and automated with the
      per-flow GATE_MS map (CUST-001: 3000ms, CUST-003: 2500ms). Mechanism exists.
      Live measurement against the frozen post-ceremony stack (CEREMONY-LOG §Post-freeze
      Live Sanity) reports: CUST-001 median 17,203ms (gate 3000ms — FAIL, ~5.7×) and
      CUST-003 median 19,733ms (gate 2500ms — FAIL, ~7.9×). Secondary spot-check
      after warming showed sustained 14–18s (not cold-start alone). AGENT-01a target
      unmet — the demo-v3.0 surface does not satisfy UI-02 <3s contract on the
      multi-tool flow.
    artifacts:
      - path: "agent/agent.py"
        issue: >
          `_BASE_SYSTEM_PROMPT` preference-ordered tool graph (Plan 03) induces
          Claude Sonnet 4.6 to call all 3 pre-tools (`get_hardship_flag` →
          `detect_bill_shock` → `simulate_savings`) on EVERY persona, not only
          bill-shock candidates. Evidence: all 3 live post-deploy captures
          (baseline/post/CUST-00{1,2,3}.json) show identical 3-entry reasoning_trace
          shape — the prompt does not short-circuit the non-shock path.
      - path: "scripts/prewarm.py"
        issue: >
          Gate is correctly configured and wired (exit 1 on failure), but there is
          no remediation in code for the underlying latency blowout. Exit 1 was
          observed live with `/tmp/prewarm-post-freeze.log` as evidence.
      - path: ".planning/phases/13-bill-shock-multi-tool-flow-agent-01/13-08-CEREMONY-LOG.md"
        issue: >
          Documents the failure (lines 92–107). This is the only live evidence —
          offline tests cannot reproduce the latency regression because they mock
          Strands `_agent(...)` with synthetic AgentResult objects.
    missing:
      - "Prompt short-circuit: when `detect_bill_shock` returns `is_shock=False` (or for CUST-001 single-tool rotation), skip the auxiliary tools and call `simulate_savings` directly. Drops non-shock personas to 1–2 tools and brings warm median back into the 3000ms band."
      - "OR: operator-always-on keepalive (DEMO-RUNBOOK amendment) accepts the 3-tool warm path latency as a rehearsal invariant and runs `demo-keepalive.sh` continuously through the demo window."
      - "OR: Revise AGENT-01a SLO to the observed live reality (e.g. 5000–6000ms warm p95) with RETROSPECTIVE-level explanation. LD-4 sign-off required."
      - "Offline regression guard — a test asserting the non-shock persona branch does not invoke `detect_bill_shock` / `get_hardship_flag` before `simulate_savings` (mocks the Strands `AgentResult` to count tool-use entries)."

  - truth: "Customer-not-found (404) detection returns HTTP 404 for unknown customer IDs — `api_lambda/handler.py:152` D-12 contract preserved."
    status: failed
    reason: >
      This is NOT a named ROADMAP SC for Phase 13, but it is a CLAUDE.md-level
      invariant ("Customer-not-found detection is 'no `green` or `cheapest` keys
      in body'") that Plan 03's new multi-tool system prompt silently broke.
      Live probe: `curl /recommendations/CUST-999` returns HTTP 200 with synthetic
      `plan_id: "UNKNOWN"` tracks (CEREMONY-LOG §404 detection; full body captured
      at lines 113–121). `api_lambda/handler.py:152` still reads
      `if "green" not in body or "cheapest" not in body:` — the LLM now composes
      fake tracks when `get_billing_history` returns empty, so the detection
      never fires.
      Explicit regression vector for Phase 14 (AGENT-02 hardship short-circuit)
      which depends on the same detection branch (AGENT-02a).
    artifacts:
      - path: "api_lambda/handler.py"
        issue: >
          Line 152 detection heuristic `if "green" not in body or "cheapest" not in body`
          is now insufficient — the multi-tool prompt path has the LLM synthesise
          UNKNOWN-track responses instead of the v1.0/v2.0 `{errorMessage: ...}`
          shape. Surgical update required: extend detection with
          `plan_id == "UNKNOWN"` OR `saving_monthly == 0` sentinel (or equivalent
          shape-check).
      - path: "agent/agent.py"
        issue: >
          `_BASE_SYSTEM_PROMPT` does not instruct the LLM to surface an
          errorMessage-shaped response (or raise) when `get_billing_history`
          returns empty. Alternative remediation: prompt-side short-circuit so
          the agent returns a fallback body with NO `green`/`cheapest` keys on
          unknown-customer, preserving the existing api_lambda detection.
      - path: "tests/test_backend_api_smoke.py"
        issue: >
          `test_unknown_customer_returns_404` (line 58) FAILS live against the
          frozen post-ceremony stack (`smoke` marker required; probed CUST-999999).
          Pytest-level smoke test is correct; the regression is in the production
          code path.
    missing:
      - "Update `api_lambda/handler.py:152` to additionally detect `plan_id == \"UNKNOWN\"` (or whichever sentinel the fix picks) — or update the agent prompt to return an `errorMessage` body on empty billing_history."
      - "New OFFLINE test `tests/test_backend_api_handler.py::test_unknown_customer_synthetic_unknown_returns_404` — deterministic regression guard that does not depend on live AWS (the smoke test covers the live side, but the code path needs offline coverage)."
      - "Agent-side offline test asserting that when InMemoryProvider returns empty billing for an unknown customer, the agent either raises or emits the errorMessage shape — not a synthesised RecommendationResponse."
      - "Phase 14's AGENT-02a plan must cite this fix as a prerequisite — hardship-shape detection (`body.get(\"kind\") != \"hardship\"`) requires a reliable customer-not-found branch to build on."

deferred:
  - truth: "stray `agent/.planning/` directory caught during ceremony (CEREMONY-LOG §Post-freeze Live Sanity item 6)"
    addressed_in: "operator hygiene — already cleaned pre-commit"
    evidence: "CEREMONY-LOG line 168 — noted as cautionary pattern, not a gap."
  - truth: "`scripts/capture_live_recommendations.py` has `--mode pre|post|compare` hardcoded to Phase 12 baseline dir (not `--output-dir` / `--customers`)"
    addressed_in: "Phase 13.1 or later tooling task"
    evidence: "13-08-SUMMARY.md line 63 key-decisions — workaround used (capture to Phase 12 dir then `cp`); functionality intact; refactor parked."
  - truth: "Pre-existing offline test drift `tests/test_agent_narrative_corpus.py::test_corpus_10x_no_numerics` (Strands 1.37 mock interface mismatch)"
    addressed_in: "Future cleanup phase (pre-existed Phase 13; introduced by Phase 06.1)"
    evidence: "deferred-items.md — 'Not a Phase 13 regression. Phase 13's FourToolCapHook converted a silent hang into a fast failure. This is an improvement, not a regression.'"
  - truth: "UI shadcn/ui pre-existing lint warnings (6 errors on untouched files)"
    addressed_in: "Future UI tooling phase"
    evidence: "deferred-items.md §ui — 6 pre-existing lint errors on base commit `4039aa1` without any Plan 13-06 change."

human_verification:
  - test: "1280×800 viewport rehearsal — verify both RecommendationCards remain above the fold on CUST-003 with the collapsed ReasoningTrace row present (ROADMAP SC-5 / UI-01)."
    expected: "Both green and cheapest cards visible without scroll at 1280×800 on a live or mock-mode build; chevron row adds ~1 line of vertical cost."
    why_human: "UI-01 above-the-fold is a rendered-pixel contract; vitest snapshot covers text/ARIA state but not the post-layout viewport-fit outcome."
  - test: "Expand/collapse affordance rehearsal — live or mock demo on CUST-003."
    expected: "Chevron ▶/▼ toggle; expanded state shows 3 numbered summaries with digits/$ visible (D-11 exemption)."
    why_human: "Hover states, motion, and screen-reader expansion are rehearsal concerns not covered by vitest."

---

# Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01) — Verification Report

**Phase Goal (ROADMAP):** The agent visibly reasons — composing 2–3 deterministic tool calls in one turn on a designated bill-shock persona — and the rep can see the ordered trace in the UI without breaking UI-01 above-the-fold or the UI-02 <3s contract.

**Verified:** 2026-04-29T23:25:00Z
**Status:** gaps_found
**Re-verification:** No (initial verification; Plan 08 self-declared `status: partial` with two P0 gaps)

---

## Executive Summary

Phase 13 delivered the AGENT-01 **mechanism end-to-end**: detect_bill_shock pure helper + dispatcher branch (Plan 01), reasoning_trace schema (Plan 02), 3 new @tool wrappers + D-23 preference-ordered graph prompt (Plan 03), FourToolCapHook via Strands HookProvider (Plan 04 — NOT `max_iterations`, Pitfall 2 honoured; `grep -c max_iterations agent/agent.py` = 0), cross-persona canary (Plan 05 — Elena vs Marcus), UI ReasoningTrace component (Plan 06), per-flow prewarm gate script (Plan 07), stack-policy lift ceremony (Plan 08 — SAV-03 byte-equal 24/24, reasoning_trace live with correct Elena signature), CLAUDE.md + DEMO-RUNBOOK addendum (Plan 09).

All 74 phase-13 offline Python tests pass. All 96 UI vitest tests pass. Live reasoning_trace surface confirmed green for all 3 personas, with Elena's middle entry byte-different from Sarah/Marcus (C5 cross-persona fabrication canary green: `"Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"`).

**However, two P0 regressions surfaced in the Plan 08 post-freeze live sanity and remain open on the current frozen v3.0 stacks:**

1. **AGENT-01a warm latency gate FAILS 5.7–7.9× over** (17,203ms / 19,733ms vs 3000ms / 2500ms gates). Root cause: the preference-ordered prompt induces Sonnet 4.6 to call all 3 pre-tools on every customer, not just bill-shock candidates — evidence in the 3 identical live `reasoning_trace` shapes.
2. **404 customer-not-found detection broken** — multi-tool prompt now composes synthetic UNKNOWN tracks when `get_billing_history` is empty, and `api_lambda/handler.py:152`'s "no green/cheapest keys" heuristic no longer triggers. Confirmed via `curl /recommendations/CUST-999` → HTTP 200.

The **mechanism is live**; **shipping it at demo-v3.0 quality is blocked by these two P0 items**. The ROADMAP SC-3 contract (AGENT-01a observable + automated + passing gate) is therefore unmet. Verdict: `gaps_found`. Phase 13.1 scope proposed below.

---

## Must-Haves (ROADMAP Success Criteria)

| # | Success Criterion | Status | Evidence |
|---|-------------------|--------|----------|
| SC-1 | Lookup of the designated bill-shock persona (CUST-003 Elena per A-01 amendment) produces a recommendation response whose `reasoning_trace` array contains ordered tool-use entries from at least two distinct tools, each entry sourced from Strands `agent_result.message.content[].toolUse` (or `_agent.messages` slice post-extractor-fix) rather than LLM estimation. | ✓ VERIFIED | `baseline/post/CUST-003.json` shows 3-entry trace `[get_hardship_flag, detect_bill_shock, simulate_savings]`; middle entry byte-equals `agent/reasoning/summaries.py::summary_detect_bill_shock({is_shock:True, delta_dollars:65.16, shock_month:"2025-10", current_dollars:167.88, mean_dollars:102.72})` (spot-checked: live match). `_extract_reasoning_trace` at `agent/agent.py:383` iterates `_agent.messages[_messages_start:]` (extractor fix commit `5644003`) — sourced from tool_use blocks, not LLM composition. |
| SC-2 | All numeric content inside the reasoning trace and call script (dates, dollar deltas, event timestamps) originates from tool output — SAV-03 extension canary test asserts zero arithmetic or rounding performed by the LLM across 10 seeds on two personas. | ✓ VERIFIED | `agent/reasoning/summaries.py` formatters consume pure tool payloads; no LLM involvement by construction (D-10). `tests/test_schema.py::TestReasoningTraceEntryExemption` locks the D-11 exemption so narrative validators can't be applied. Byte-equivalence gate on CUST-001/002/003 pre-vs-post: 24/24 SAV-03-sensitive fields equal (verified live). `tests/test_bill_shock_flow.py::TestCrossPersonaCanary` (`test_no_fabrication_across_personas`) offline-green — Elena trips, Marcus does not. |
| SC-3 | Per-flow prewarm gate in `scripts/prewarm.py` measures warm p95 for the multi-tool route and exits 0 only when median lands under 2500ms; AGENT-01a gate is observable and automated, not operator-judged. | ✗ FAILED | **Gate exists + automated + observable — but fails live.** `scripts/prewarm.py` has per-flow `GATE_MS` map (3000ms CUST-001 / 2500ms CUST-003), 3-pass warming, 30s settle, 3-sample median, exit 1 on fail. Live post-freeze run (`/tmp/prewarm-post-freeze.log`, CEREMONY-LOG §Post-freeze Live Sanity): CUST-001 median **17,203ms FAIL** (~5.7× over 3000ms gate); CUST-003 median **19,733ms FAIL** (~7.9× over 2500ms gate). Exit 1. AGENT-01a target unmet on the shipping surface. |
| SC-4 | Code-enforced 4-tool cap (`Agent(max_iterations=4)` or equivalent Strands configuration) short-circuits runaway tool loops — pytest asserts the cap triggers on a crafted "infinite delegator" prompt and returns a graceful fallback, never a 500 (D-04 preserved). | ✓ VERIFIED | `agent/hooks/four_tool_cap.py::FourToolCapHook(HookProvider)` (76 LOC) — subscribes to `AfterToolCallEvent`, calls `event.agent.cancel()` at budget. Wired at `agent/agent.py:657` via `hooks=[_four_tool_cap]`; `grep -c max_iterations agent/agent.py` = 0 (Pitfall 2 honoured). `invoke()` at `agent/agent.py:720` detects `stop_reason == "cancelled"` → raises `RuntimeError("tool budget exhausted")` → caught by existing `except Exception` → D-04 fallback path with `_narrative_source='fallback'`. Tests: `TestFourToolCap::test_hook_cancels_agent_at_budget`, `test_hook_cancels_repeatedly_past_budget`, `test_invoke_routes_through_d04_fallback_on_cancelled_stop_reason`, `test_invoke_cancelled_path_does_not_leak_tool_budget_runtimeerror` all green. No 500 path — final-except returns 200 with tool-lambda-direct fallback body. |
| SC-5 | UI `ReasoningTrace` component renders the trace collapsed by default; at 1280×800 viewport both recommendation cards remain above the fold (UI-01 preserved, measurable via vitest snapshot or operator rehearsal). | ✓ VERIFIED (offline + snapshot; operator rehearsal deferred — see Human Verification) | `ui/src/components/ReasoningTrace.tsx` renders collapsed by default (`useState(false)`); collapsed label is tool-names-only `▶ N steps: tool_a → tool_b → tool_c` (no digits/$/dates). Expanded state shows numbered summaries. `ui/src/components/ReasoningTrace.test.tsx` covers D-30's 6 vitest cases (empty→null, 3-entry collapsed, click expands, ?narrative=off + non-empty→null, ?narrative=off + empty→null, 1-entry collapsed) — all green. LD-7 kill-switch wiring at line 31 (`if (!NARRATIVE_ENABLED) return null`). Mounted at `ui/src/App.tsx:69` above the card grid (D-28). |

**Score:** 4/5 verified. **SC-3 is the blocker** for demo-v3.0 on the live surface.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `lambda/handler.py` | `detect_bill_shock_pure` + dispatcher branch | ✓ VERIFIED | Plan 01 line 143 `def detect_bill_shock_pure(...)`; line 289 `if action == "detect_bill_shock":` → routes to pure helper. 307 LOC total. |
| `agent/agent.py` | `ReasoningTraceEntry`, extended `RecommendationResponse`, `_extract_reasoning_trace`, 3 new @tool wrappers, FourToolCapHook wiring, bi-mode imports | ✓ VERIFIED | 826 LOC. `ReasoningTraceEntry` line 145 (D-11 exemption documented lines 146–157); `reasoning_trace` field line 167; `_extract_reasoning_trace(agent_result, messages=None)` line 383; `detect_bill_shock` @tool line 497; `get_billing_history` @tool line 522; `get_hardship_flag` @tool line 545; `_four_tool_cap = FourToolCapHook(budget=4)` line 646; `hooks=[_four_tool_cap]` line 657; `stop_reason == "cancelled"` check line 720; bi-mode imports lines 80–100 (narrative + reasoning + hooks). |
| `agent/hooks/four_tool_cap.py` | `FourToolCapHook(HookProvider)` class | ✓ VERIFIED | 76 LOC. Per-instance `used`/`budget` counter (SC-3 mirror — reset via `reset()` in `invoke()`). `register_hooks` subscribes `AfterToolCallEvent`; `on_tool_complete` increments + calls `event.agent.cancel()` at budget. |
| `agent/reasoning/summaries.py` | 4 deterministic formatters | ✓ VERIFIED | 62 LOC. `summary_detect_bill_shock`, `summary_get_billing_history`, `summary_get_hardship_flag`, `summary_simulate_savings`. D-10 SAV-03 by construction (no LLM; only `f'{x:.2f}'` format-spec rounding). Spot-checked: Elena payload → exact live string. |
| `agent/Dockerfile` | COPYs `narrative/` + `reasoning/` + `hooks/` | ✓ VERIFIED | Lines 10–12 `COPY narrative/ ./narrative/`, `COPY reasoning/ ./reasoning/`, `COPY hooks/ ./hooks/`. ECR bi-mode smoke PASS (CEREMONY-LOG Task 8.4). Runtime v12 container `sha256:15bb94c16f8f55bb70954da9f0fe3bcd235c855cadd3f369c9dbb77d47bc618d` is LIVE with these directives. |
| `tests/test_bill_shock_flow.py` | 4 test classes (TestDetectBillShockPure, TestDetectBillShockDispatcher, TestFourToolCap, TestCrossPersonaCanary) | ✓ VERIFIED | 540 LOC, 4 test classes found. All green offline (74 tests pytest on test_bill_shock_flow.py + test_schema.py + test_agent_tools.py). |
| `ui/src/components/ReasoningTrace.tsx` | Collapsed-by-default disclosure | ✓ VERIFIED | 64 LOC. Empty-list short-circuit (line 34); LD-7 kill-switch (line 31); D-28 section above card grid; D-11 exemption comment header. |
| `ui/src/components/ReasoningTrace.test.tsx` | 6 vitest cases (D-30) | ✓ VERIFIED | All 96 UI vitest tests green. |
| `ui/src/lib/types.ts` | `ReasoningTraceEntry` + extended `RecommendationResponse` | ✓ VERIFIED | Line 17 interface; line 27 optional field (snake_case D-18). |
| `ui/src/lib/mock/recommendations.ts` | `MOCK_REASONING_TRACE_CUST003` byte-sync with Python formatters | ✓ VERIFIED | Line 41 export; D-29 byte-sync comment header; CUST-001/002 get `[]`, CUST-003 gets `MOCK_REASONING_TRACE_CUST003`. |
| `ui/src/App.tsx` | `<ReasoningTrace trace={state.data.reasoning_trace ?? []} />` above card grid | ✓ VERIFIED | Import line 26; mount line 69. |
| `scripts/prewarm.py` | Per-flow gate map + 3-pass warming | ✓ VERIFIED (mechanism) / ⚠️ FAILS LIVE | 187 LOC. `GATE_MS = {"CUST-001": 3000, "CUST-003": 2500}`; `WARMING_PASSES = 3`; exit taxonomy 0/1/2 preserved. Mechanism green. Live run fails — see Gap 1. |
| `CLAUDE.md` addendum | D-11 exemption + D-15 cap routing + D-22 Strands pin bullets | ✓ VERIFIED | Lines 45–47 exactly as specified by Plan 09 must_haves. |
| `DEMO-RUNBOOK.md` | Marcus→Elena swap for AGENT-01 beat | ✓ VERIFIED | Line 154 "CUST-003 Elena — bill-shock multi-tool flow"; line 155 per-flow gates documented (2500ms/3000ms); line 254 Marcus still listed as non-shock foil (amendment A-01 honoured). |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `agent.py::invoke()` | `_extract_reasoning_trace` | `_agent.messages[_messages_start:]` slice (SC-3 mirror) | ✓ WIRED | Lines 698–757 — snapshots length before `_agent(...)`, passes slice to all 4 extractor call sites (happy-path + 3 fallback branches). |
| `agent.py::_agent` | `FourToolCapHook` | `Agent(..., hooks=[_four_tool_cap])` | ✓ WIRED | Line 657. |
| `agent.py::invoke()` | D-04 fallback | `stop_reason == "cancelled"` → `raise RuntimeError("tool budget exhausted")` → existing `except Exception` | ✓ WIRED | Line 720 check; raise at line 724; caught by broad-except at line 752. Fallback attaches `reasoning_trace` from `_agent.messages` slice (line 757) + `_narrative_source='fallback'`. |
| `agent.py::@tool` wrappers | `_lambda_client` | `.invoke(..., Payload=json.dumps({"action": "<name>", "customer_id": ...}))` | ✓ WIRED | Lines 497/522/545. Direct Lambda client invoke (NOT through `get_provider()` — preserves LD-5 3-method Protocol). |
| `api_lambda/handler.py` | reasoning_trace pass-through | verbatim `json.dumps(body)` at line 161 | ✓ WIRED | `_narrative_source` is popped at line 121; `reasoning_trace` is NOT popped — pass-through preserved (D-12). Live captures confirm. |
| `api_lambda/handler.py` | 404 unknown-customer detection | line 152 `if "green" not in body or "cheapest" not in body` | ✗ PARTIAL (regression) | Mechanism intact, but Plan 03's prompt induces `UNKNOWN` synthetic tracks — detection no longer fires for CUST-999. See Gap 2. |
| UI `App.tsx` | `<ReasoningTrace trace={state.data.reasoning_trace ?? []} />` | `state.data.reasoning_trace ?? []` | ✓ WIRED | Line 69. Nullish-coalesce defends against missing field on v2.0 response shape. |

---

## Data-Flow Trace (Level 4) — Live Post-Deploy

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `agent.py::invoke()` happy-path | `reasoning_trace` | `_extract_reasoning_trace(agent_result, _agent.messages[_messages_start:])` reads Strands conversation history `tool_use`/`tool_result` blocks | YES — verified via live Elena capture: `"Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"` matches pure-helper output | ✓ FLOWING |
| `api_lambda/handler.py` response body | `body` (passed to `json.dumps`) | AgentCore `invoke_agent_runtime` response; `_narrative_source` stripped; rest verbatim | YES — 3 live captures show `reasoning_trace` preserved with 3 entries each; savings byte-equal across pre/post (24/24 SAV-03 fields) | ✓ FLOWING |
| UI `ReasoningTrace` component | `trace` prop | `state.data.reasoning_trace ?? []` from useRecommendations fetch | YES in mock mode (MOCK_REASONING_TRACE_CUST003 byte-synced) + YES in live mode (captured responses have populated arrays) | ✓ FLOWING |
| `api_lambda/handler.py::152` unknown-customer branch | `body.get("green")`, `body.get("cheapest")` | agent response | ✗ NO — synthetic UNKNOWN tracks populate these keys, detection doesn't fire | ✗ DISCONNECTED |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `FourToolCapHook` importable + budget arg | `python3 -c "from agent.hooks.four_tool_cap import FourToolCapHook; h = FourToolCapHook(budget=4); print(h.budget, h.used)"` | `4 0` | ✓ PASS |
| `summary_detect_bill_shock` produces Elena byte-exact | `python3 -c "from agent.reasoning.summaries import summary_detect_bill_shock; print(summary_detect_bill_shock({'is_shock':True,'delta_dollars':65.16,'shock_month':'2025-10','current_dollars':167.88,'mean_dollars':102.72}))"` | `Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)` | ✓ PASS (matches live CUST-003 middle entry) |
| Offline phase-13 test suites green | `pytest tests/test_bill_shock_flow.py tests/test_schema.py tests/test_agent_tools.py -q` | 74 passed | ✓ PASS |
| UI vitest green | `npm --prefix ui test -- --reporter=dot --run` | 9 files / 96 tests passed | ✓ PASS |
| `max_iterations` anti-pattern absent (Pitfall 2) | `grep -c max_iterations agent/agent.py` | `0` | ✓ PASS |
| Dockerfile COPYs for bi-mode imports | `grep -c "^COPY \(narrative\|reasoning\|hooks\)/" agent/Dockerfile` | `3` | ✓ PASS |
| SAV-03 byte-equivalence across 3 personas (24 fields) | python diff on `baseline/pre/*.json` vs `baseline/post/*.json` | 24/24 PASS | ✓ PASS |
| Live prewarm gate exits 0 | `BACKEND_API_URL=... python3 scripts/prewarm.py` (from CEREMONY-LOG) | exit 1; 17203ms/19733ms both over gate | ✗ FAIL |
| Live 404 unknown-customer smoke | `curl /recommendations/CUST-999` or `pytest -m smoke tests/test_backend_api_smoke.py::test_unknown_customer_returns_404` | HTTP 200 with UNKNOWN tracks | ✗ FAIL |

---

## Requirements Coverage

| Requirement | Description | Source Plans | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| AGENT-01 | Bill-shock multi-tool agent flow — agent composes 2–3 tool calls in one turn; reasoning trace surfaced to UI | 13-01, 13-02, 13-03, 13-04, 13-05, 13-06, 13-08, 13-09 | ✓ SATISFIED (mechanism) | 3-entry `reasoning_trace` live on all 3 personas; `detect_bill_shock` pure helper + dispatcher + @tool wrapper deployed; UI ReasoningTrace component renders the trace. Plans 01–06, 09 complete; Plan 08 partial (ceremony closed with gaps). |
| AGENT-01a | Warm p95 latency for the multi-tool flow stays under 2500ms target on the deployed runtime; UI-02 <3s single-tool contract must not regress and must hold for multi-tool | 13-07, 13-08 | ✗ BLOCKED | Gate script + automation present; live measurement fails at 5.7–7.9× over per-flow gates on post-freeze stacks. Phase 13.1 owns remediation (Gap 1). |
| AGENT-01b | Tool-call cap of 4 per agent turn enforced in code (not prompt) — hard limit short-circuiting infinite loops | 13-04, 13-08, 13-09 | ✓ SATISFIED | `FourToolCapHook(budget=4)` deployed as Strands HookProvider (Pitfall 2: NOT `max_iterations`); live runtime v12 contains the hook. Offline `TestFourToolCap` green (4 tests). In practice the 3-tool observed flow doesn't exercise the cap live — but the mechanism is present and tested. |

**Orphaned requirements check:** REQUIREMENTS.md maps exactly `AGENT-01`, `AGENT-01a`, `AGENT-01b` to Phase 13. All three are claimed by at least one plan's frontmatter. No orphans.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `agent/agent.py` `_BASE_SYSTEM_PROMPT` | ~583–591 | Preference-ordered tool graph (Plan 03 D-23) induces all 3 pre-tools on every persona — evidence: identical 3-entry trace on CUST-001/002/003 | ⚠️ Warning | Root cause of Gap 1 latency blowout. Not a stub; it's a prompt-design issue that compounds cold+warm latency. Phase 13.1 scope. |
| `api_lambda/handler.py:152` | 152 | `if "green" not in body or "cheapest" not in body` no longer sufficient — multi-tool prompt synthesises UNKNOWN tracks | 🛑 Blocker | Direct cause of Gap 2. D-12 contract violation; regresses Phase 14 AGENT-02a prerequisite. |
| n/a | — | No TODO/FIXME/stub markers found in Phase 13 modified files. | Info | Codebase clean of placeholder comments. `grep -rn "TODO\|FIXME\|placeholder" agent/hooks agent/reasoning ui/src/components/ReasoningTrace*` = 0 matches. |

---

## Deferred Items (addressed elsewhere — not Phase 13 gaps)

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Stray `agent/.planning/` directory caught during ceremony | Operator hygiene — already cleaned pre-commit | CEREMONY-LOG line 168; cautionary pattern only |
| 2 | `scripts/capture_live_recommendations.py` CLI refactor (`--mode` vs `--output-dir`/`--customers`) | Phase 13.1 or later tooling task | 13-08-SUMMARY.md key-decisions line 63 — workaround used (capture to Phase 12 dir then `cp`) |
| 3 | Pre-existing offline corpus-test drift (`test_corpus_10x_no_numerics`) | Future cleanup phase (pre-existed Phase 13; introduced by Phase 06.1) | `deferred-items.md` §Pre-existing drift |
| 4 | UI shadcn/ui pre-existing lint warnings (6 errors on untouched files) | Future UI tooling phase | `deferred-items.md` §ui |
| 5 | `tests/test_frontend_synth.py` 23 ERRORS on fresh worktrees without `ui/dist/` | Future test-infra task | `deferred-items.md` §tests/test_frontend_synth.py |

---

## Gaps (Phase 13.1 scope)

### Gap 1 — Warm latency 5.7–7.9× over per-flow gates (P0, AGENT-01a)

**Truth failed:** ROADMAP SC-3 + AGENT-01a (warm p95 < 2500ms multi-tool, < 3000ms single-tool).

**Live evidence (CEREMONY-LOG §Post-freeze Live Sanity):**

| Persona | Warm pass medians | Measurement median | Gate | Verdict |
|---------|-------------------|---------------------|------|---------|
| CUST-001 (single-tool expected, observed 3-tool) | 17847/16229/17138 ms | **17,203ms** | 3000ms | FAIL (~5.7×) |
| CUST-003 (multi-tool) | 13437/19116/14278 ms | **19,733ms** | 2500ms | FAIL (~7.9×) |

Secondary spot-check (3 warm CUST-001 calls after prewarm): 14286 / 17936 / 14965 ms — latency is **sustained, not cold-start alone**.

**Root cause (to confirm in Phase 13.1):** Plan 03's preference-ordered tool graph in `_BASE_SYSTEM_PROMPT` induces Claude Sonnet 4.6 to call all 3 pre-tools (`get_hardship_flag` → `detect_bill_shock` → `simulate_savings`) on **every** customer, not just bill-shock candidates. Evidence: all 3 captured live personas show identical 3-entry trace shape. 3 × ~400–900ms per tool round-trip + Bedrock think time + AgentCore microVM overhead → observed 14–20s band (consistent with PITFALLS.md C1 high-end estimate).

**Phase 13.1 remediation options (executor/planner picks):**

- **Option A (prompt short-circuit — preferred):** Amend `_BASE_SYSTEM_PROMPT` so when `detect_bill_shock` returns `is_shock=False`, the agent skips `get_billing_history` and goes straight to `simulate_savings`. Brings non-shock personas (CUST-001/002) down to 2 tools (hardship + simulate) or even 1 (if hardship check is also skipped for non-hardship-flagged personas). Requires a new offline test that mocks Strands tool-use and asserts the non-shock branch emits exactly 1–2 `reasoning_trace` entries.
- **Option B (always-on keepalive):** DEMO-RUNBOOK amendment — run `scripts/demo-keepalive.sh` continuously through the demo window and accept the 3-tool warm path's 14–20s latency as rehearsal invariant. Does not fix AGENT-01a on paper; pragmatic for demo success.
- **Option C (SLO revise):** Accept 5000–6000ms warm p95 as observed reality; update AGENT-01a target in REQUIREMENTS.md with RETROSPECTIVE-level explanation. Requires LD-4 sign-off — breaks the original v3.0 contract.
- **Regression guard (required in all options):** Offline test asserting non-shock persona flow does not invoke all 3 pre-tools (mocks Strands `AgentResult` with a tool-use count assertion).

**Stack impact:** A prompt-only fix (Option A) requires re-running the Plan 08 lift ceremony — 1 stack (`CustomerTariffAgent`) to rebuild the container image with the updated system prompt. Options B/C are zero-stack.

### Gap 2 — 404 detection broken for unknown customer (P0, D-12 regression)

**Truth failed:** CLAUDE.md invariant "Customer-not-found detection is 'no green or cheapest keys in body'" (D-12) — not a named Phase 13 ROADMAP SC but a documented invariant that `api_lambda/handler.py:152` depends on. Also a Phase 14 AGENT-02a prerequisite.

**Live evidence (CEREMONY-LOG §404 detection):** `curl /recommendations/CUST-999` → HTTP 200 with:

```json
{
  "green": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, ...},
  "cheapest": {"plan_id": "UNKNOWN", "plan_name": "UNKNOWN", "saving_monthly": 0.0, ...},
  "reasoning_trace": [
    {"tool": "get_hardship_flag", "summary": "hardship_flag=False"},
    {"tool": "detect_bill_shock", "summary": "No bill shock: monthly usage within 11-month envelope"}
  ]
}
```

**Root cause:** Plan 03's new multi-tool prompt has the LLM **compose** a full `RecommendationResponse` with `plan_id: "UNKNOWN"` placeholder track data when `get_billing_history` returns empty, instead of routing to the v1.0/v2.0 agent-fallback `{"errorMessage": "..."}` shape. `api_lambda/handler.py:152`'s heuristic reads `if "green" not in body or "cheapest" not in body` — the keys ARE present now, so 404 never fires.

**Phase 13.1 remediation options:**

- **Option A (API-Lambda detection extension — preferred, surgical):** Extend `api_lambda/handler.py:152` to also detect `plan_id == "UNKNOWN"` OR `saving_monthly == 0.0` as 404 sentinel. Requires an offline `tests/test_backend_api_handler.py` regression test (the smoke test in `test_backend_api_smoke.py` already exists and covers the live side).
- **Option B (agent-side short-circuit):** Amend `_BASE_SYSTEM_PROMPT` so when `get_billing_history` returns an empty list, the agent emits `{"errorMessage": "customer not found"}` rather than a synthesised `RecommendationResponse`. Preserves the existing api_lambda detection unchanged. Stack impact: 1 stack (`CustomerTariffAgent`) re-deploy.
- **Option C (both):** Belt-and-braces — defend at both layers. Recommended if Phase 14's AGENT-02a hardship short-circuit will add a third branch to the same detection code path.

**Phase 14 dependency:** AGENT-02a requires reliable customer-not-found detection to build the `body.get("kind") != "hardship"` branch on top. Phase 13.1 MUST close Gap 2 before Phase 14 planning proceeds.

---

## Phase 13.1 Scope Proposal

A decimal phase is required because (a) both gaps are code-side, (b) Gap 1's prompt fix likely requires another stack-policy lift (runtime re-deploy), (c) Gap 2 has two valid remediation paths (API Lambda OR agent prompt) and the choice ripples into Phase 14.

**Recommended plan breakdown (5 plans, 2 waves):**

**Wave 1 (offline — parallel):**
- **13.1-01** — API-Lambda 404 detection extension (Option A for Gap 2): extend `handler.py:152` sentinel + offline regression test. REQ: D-12 invariant restored.
- **13.1-02** — Offline regression guard for non-shock tool-count (Option A precondition for Gap 1): mock Strands AgentResult, assert non-shock persona emits ≤2 `reasoning_trace` entries. REQ: AGENT-01a regression-proof.
- **13.1-03** — `_BASE_SYSTEM_PROMPT` short-circuit amendment (Option A for Gap 1): when `detect_bill_shock` returns `is_shock=False`, skip `get_billing_history`, go direct to `simulate_savings`. Offline tests extend `TestCrossPersonaCanary` to assert trace shape.

**Wave 2 (ceremony — autonomous: false):**
- **13.1-04** — Stack-policy lift + deploy `CustomerTariffAgent` + `CustomerTariffApi` (if 13.1-01 touches API Lambda) + `CustomerTariff` (no — not touched). Re-run per-flow prewarm gate live; REQ `prewarm.py` exits 0. Re-run smoke suite including `test_unknown_customer_returns_404`; REQ green. Re-apply freeze.
- **13.1-05** — Documentation sweep: update `CLAUDE.md` to cite the new D-12 detection sentinel; update DEMO-RUNBOOK with the revised per-flow latency numbers; update Phase 14 plan preambles to cite Gap 2 closure.

**Alternative:** If operator prefers Option B/C for either gap, the plan count stays at 5 but 13.1-03's nature shifts (prompt+errorMessage shape vs short-circuit).

---

## Human Verification Required

### 1. 1280×800 viewport UI-01 rehearsal (ROADMAP SC-5)

**Test:** Open the live or mock-mode UI at 1280×800, look up CUST-003 Elena.
**Expected:** Both recommendation cards (green + cheapest) visible without scrolling; collapsed `ReasoningTrace` row (chevron + tool names) fits above the card grid; total vertical cost of the row ~1 line.
**Why human:** Vitest covers text/ARIA; not rendered-pixel viewport-fit.

### 2. Expand/collapse affordance rehearsal

**Test:** Click the collapsed `▶ 3 steps: ...` chevron on CUST-003.
**Expected:** Chevron rotates to ▼; numbered list of 3 summaries appears below with digits, $, and dates visible (D-11 exemption); middle entry shows `"Bill shock detected: +$65.16 2025-10 vs 11-month avg ($167.88 vs $102.72)"`; screen-reader announces expansion.
**Why human:** Motion, hover state, and SR behaviour are not covered by vitest assertions.

---

## Gaps Summary

**Mechanism: ✓ Live.** The AGENT-01 surface is fully deployed — bill-shock detection is real (Elena trips, Marcus/Sarah don't); reasoning_trace is populated with code-composed summaries (SAV-03 by construction); the 4-tool cap is wired via HookProvider (Pitfall 2 honoured). SAV-03 byte-equivalence is preserved on all 3 personas (24/24 fields).

**Shipping: ✗ Blocked.** Two P0 regressions from Plan 08 post-freeze live sanity remain open:

1. **AGENT-01a latency gate fails 5.7–7.9× over target** — preference-ordered prompt over-invokes the tool graph on non-shock personas. Demo-v3.0 warm p95 contract unmet.
2. **404 unknown-customer detection broken** — multi-tool prompt's UNKNOWN-track synthesis defeats `api_lambda/handler.py:152`'s heuristic; regresses D-12 invariant and blocks Phase 14 AGENT-02a.

**Recommendation:** Plan Phase 13.1 (5 plans, 2 waves) before Phase 14. The ceremony in 13.1-04 will be a targeted 1–2-stack lift (agent container + optional API Lambda), no DynamoDB or CustomerTariff-foundation impact.

---

_Verified: 2026-04-29T23:25:00Z_
_Verifier: Claude (gsd-verifier)_
_Reference HEAD: `786b833` (ceremony commit) / mid-ceremony fix: `5644003`_
_Live runtime: `tariff_agent-O2Hai86N8V` v12 (image `sha256:15bb94c16f8f55bb70954da9f0fe3bcd235c855cadd3f369c9dbb77d47bc618d`)_

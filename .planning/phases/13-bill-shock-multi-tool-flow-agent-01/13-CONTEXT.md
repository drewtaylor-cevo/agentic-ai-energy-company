# Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01) - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning
**Amended:** 2026-04-29 post-research — see `## Research Amendments (2026-04-29)` below. Amendments override the original decisions where explicitly stated.

## Research Amendments (2026-04-29)

Two blockers surfaced during `/gsd-plan-phase 13` research (see `13-RESEARCH.md` §RESEARCH BLOCKED + §1 + §6). User decisions below **override** the original CONTEXT.md text wherever they conflict. Original decision bodies are preserved for traceability, but planners and executors MUST follow the amendment where the two disagree.

### A-01 — Designated bill-shock persona is **CUST-003 (Elena Vasquez)**, not CUST-002 (Marcus Webb)

**Blocker:** MARCUS_WEBB_RECORDS does not trip the D-03 30% symmetric threshold on any month (peak 0.167 on 2025-10). See RESEARCH §6. CONTEXT.md §Non-integration points explicitly flagged fixture engineering as a Phase 11 amendment out-of-scope here.

**Decision:** **Reassign the designated bill-shock persona to CUST-003 Elena.** Elena has 7 months above the 30% gate (peak 0.634 on 2025-10). No fixture edits. Phase 11 D-13 byte-exact Marcus savings ($16.90 / $30.98) untouched. Elena's existing CUST-003 byte-exact fixtures ($14.00 / $25.67) are now the canary target.

**What this amends (override):**

- **D-03 threshold:** UNCHANGED — stays at `|monthly_delta| > 30% of 11-month mean`. Elena already trips on the live fixture.
- **D-09 system-prompt ordering rule:** Preference graph unchanged. `?flow=bill_shock` still rejected. LLM-decides still the pattern. Only the demo-time target customer ID changes.
- **D-16 `test_four_tool_cap_fires_gracefully`:** Hardcoded `customer_id` for the cap test — planner MAY pick any persona; CUST-001 still fine.
- **D-18 per-flow prewarm rotation:** **CUST-003 (multi-tool) + CUST-001 (single-tool)** — was CUST-002 + CUST-001. Planner updates `scripts/prewarm.py` rotation list accordingly.
- **D-19 latency-floor witness (smoke):** `test_agent01_latency_floor` asserts **CUST-003** live response latency > 1000ms (was CUST-002).
- **D-20 cross-persona canary (offline):** Invoke on **CUST-003 (bill-shock)** and **CUST-002 Marcus (non-shock)**. Assert `detect_bill_shock` result differs (`is_shock=True` for CUST-003, `is_shock=False` for CUST-002). Assert savings differ ($14.00/$25.67 vs $16.90/$30.98). Assert `reasoning_trace` differs byte-exact. Marcus becomes the non-shock foil; CUST-004 usage in the original D-20 is deprecated for this canary.
- **D-21 CloudWatch counter (smoke):** Assertion over a single **CUST-003** lookup (was CUST-002).
- **D-29 mock fixtures:** `MOCK_REASONING_TRACE_CUST003` (not CUST002). CUST-003 mock response gains the 3-entry trace; CUST-001, CUST-002, CUST-004, CUST-005 get `reasoning_trace: []`.
- **D-33 byte-equivalence baselines:** Pre/post captures MUST include CUST-001 + **CUST-003** + CUST-002 (as non-shock sanity) at minimum — was CUST-001 + CUST-002 + CUST-004. Path stays `.planning/phases/13-*/baseline/{pre,post}/{customer_id}.json`.
- **Canonical refs §"Prior phase context":** The reference to "MARCUS_WEBB_RECORDS fixture is the CUST-002 bill-shock source" is deprecated. Planner instead reads Phase 11 D-13 Elena fixtures for the multi-tool target.
- **DEMO-RUNBOOK §T-24h rehearsal:** Warm-median target stays 2500ms; persona in the rehearsal rotation swaps Marcus→Elena for the AGENT-01 demo beat. Planner adds a DEMO-RUNBOOK update task.

### A-02 — 4-tool cap implemented via **Strands `HookProvider`**, not `Agent(max_iterations=N)`

**Blocker:** Strands 1.37.0 `Agent.__init__` has **no `max_iterations` parameter**. Only `Swarm.max_iterations` exists. Strands' `StopReason` literals are `cancelled, checkpoint, content_filtered, end_turn, guardrail_intervened, interrupt, max_tokens, stop_sequence, tool_use` — no `max_iterations_exceeded`. See RESEARCH §1.

**Decision:** **Use a Strands `HookProvider`** that subscribes to `BeforeToolCallEvent` (or `AfterToolCallEvent`, planner's choice from Strands 1.37.0 hooks), increments a per-invocation tool-call counter, and calls `agent.cancel()` when the counter reaches 4. Result: `agent_result.stop_reason == "cancelled"`. D-15 cap-fallback branch detects `stop_reason == "cancelled"` and routes through the existing `except Exception` fallback at `agent/agent.py:394-418` (unchanged path — D-04 preserved).

**What this amends (override):**

- **D-14:** Replace "`Agent(max_iterations=4)` on the Strands `_agent` singleton" with: "a new `agent/hooks/four_tool_cap.py` (or inline in `agent/agent.py`, planner discretion) registers a `HookProvider` passed to `Agent(..., hooks=[FourToolCapHook()])`. The hook stores counter state on the per-call context (NOT module-level — session bleed concern, SC-3 mirror). Research pinned — no open question remains." Planner MUST confirm the exact event class name (`BeforeToolCallEvent` or `AfterToolCallEvent` per Strands 1.37.0) and the exact Agent parameter name (`hooks` or `hook_providers`) from `.venv/lib/python3.13/site-packages/strands/` source during planning.
- **D-15 cap-fallback branch:** Detection semantics change from "exception branch OR stop_reason inspection" to **"stop_reason inspection only"** (`if agent_result.stop_reason == "cancelled":`). The existing `except Exception` at `agent/agent.py:394-418` stays for other failure modes. `_narrative_source = "fallback"` still stamped; partial `reasoning_trace` assembled from whatever fired before the cancel.
- **D-16 offline cap pytest:** The crafted-loop test uses the real hook + a test-only self-referential `@tool` (or monkey-patches the hook's threshold to `max_calls=2` for a cheaper fake loop). Either works; planner picks. Still fully offline via `_provider_swap` + `InMemoryProvider`.
- **D-17 no live smoke:** unchanged — Sonnet 4.6 is still tuned away from runaway loops; cap hook's contract proven offline.
- **D-22 Strands pinned:** unchanged — `--require-hashes` invariant holds, zero deps.
- **D-24 cross-persona canary guards prompt:** unchanged — also now guards the hook (any hook edit re-runs the canary).

### A-03 — Latency budget has **no headroom at 2500ms**

**Finding:** RESEARCH §4 — no repo measurements; PITFALLS.md C1 estimates 2600-5400ms warm for a 3-tool turn. 2500ms gate has zero margin. **Not a blocker — but a named risk.**

**Decision:** **Proceed with the 2500ms gate as-specified (AGENT-01a contractual target).** Add TWO new planner obligations:

1. **Sighting-shot measurement before Wave N (lift ceremony).** A new task in an early wave runs a lightweight warm-median measurement on the deployed CUST-003 flow BEFORE the stack-policy lift. If median > 2500ms on a 3-tool turn, planner pivots to the **break-glass: drop to 2-tool CUST-003 demo** (`get_billing_history` + `simulate_savings`, skip `detect_bill_shock` in the prompt's preferred order). `detect_bill_shock` stays wired as a tool — the agent just isn't asked to call it on CUST-003 unless the rep explicitly asks via a future UX. This preserves AGENT-01's "visible reasoning" demo at one-tool-less latency.
2. **Prewarm pass count promotion to 3 (from 2).** `scripts/prewarm.py` takes a THIRD warming pass on CUST-003 before measuring the gate. Mitigates Strands + Bedrock first-call variance.

Neither mitigation changes any locked decision; both are additive planner instructions.

---


<domain>
## Phase Boundary

The agent visibly reasons — composing 2–3 deterministic tool calls on a single turn for a bill-shock persona (CUST-002) — and the rep sees the ordered trace surfaced as a collapsed-by-default `ReasoningTrace` component above the recommendation cards. A new `detect_bill_shock_pure` helper lives in `lambda/handler.py` next to `simulate_savings_pure`, wrapped as a Tools Lambda action and consumed through a new `@tool detect_bill_shock` on the agent side (plus co-landed `@tool get_billing_history` and `@tool get_hardship_flag` wrappers consumed by Phase 14). A code-enforced 4-iteration cap (`Agent(max_iterations=4)` Strands primitive) short-circuits runaway tool loops and routes exhaustion through the existing D-04 fallback path so HTTP 200 is returned, never 500. A new public `reasoning_trace: list[{tool, summary}]` field is attached to the recommendation response and passed through unchanged by `api_lambda/handler.py`. `scripts/prewarm.py` extends to per-flow warm-median gates (3000ms single-tool / 2500ms multi-tool) with the strict 0/1/2 exit taxonomy preserved. SAV-03 is extended by construction: `detect_bill_shock_pure` is pure Python in Tools Lambda, trace summary strings are code-composed (never LLM-generated), and the system prompt's "LLM never does arithmetic" rule is generalised to cover every arithmetic tool.

**Out of scope (belongs elsewhere):**
- Hardship short-circuit (Phase 14 — AGENT-02): discriminated-union `kind: "recommendation" | "hardship"` on `RecommendationResponse`, surgical update to `api_lambda/handler.py:152` customer-not-found detection, pre-LLM guard. Phase 13 ships the `get_hardship_flag` tool + action dispatcher branch only; guard + union are Phase 14's territory.
- Draft follow-up email + AgentCore Memory resource + `_workflow_source` marker (Phase 15 — WF-01). The `bedrock-agentcore` 1.6.3 → 1.6.4 bump also belongs to Phase 15. Phase 13 ships ZERO new dependencies.
- Presenter artefacts (DOC-01/02/03) and full 5-persona prewarm rotation (Phase 16 — DEMO-07/09/10). Phase 13 adds the per-flow-gate mechanism + CUST-002 rotation; Phase 16 extends to all personas.
- v3.0 freeze ceremony (Phase 17). Phase 13 re-executes the v2.0 Phase 10 lift-deploy-reapply pattern on the three frozen stacks but does NOT cut the `demo-v3.0` tag.
- Amplify `CustomerTariffFrontend` redeploy. UI build output ships in the Amplify-unfrozen stack; redeploy independently after `npm run build` with new `VITE_API_URL` as needed.
- `get_customer_profile` tool. Research lists it as optional; CUST-002 demo does not require segment-framing copy. Deferred.

</domain>

<decisions>
## Implementation Decisions

### Tool Surface

- **D-01: Three new tools land this phase — two active, one co-landed for Phase 14.**
  - `detect_bill_shock(customer_id) -> dict`: new `@tool` wrapping a new Tools Lambda action `detect_bill_shock`. Pure helper `detect_bill_shock_pure(billing_history)` lives in `lambda/handler.py` next to `simulate_savings_pure`. Returns `{"is_shock": bool, "delta_dollars": float, "shock_month": str, "mean_dollars": float, "current_dollars": float}` — every numeric field sourced from the pure helper, never from LLM estimation.
  - `get_billing_history(customer_id) -> list[dict]`: new `@tool` wrapping the existing Phase 11 Lambda action `get_billing_history` (already dispatched by Phase 12's `handler(event, context)` action dispatcher at `lambda/handler.py`). Returns the 12-month record list (PROFILE row filtered server-side per Phase 11 D-21).
  - `get_hardship_flag(customer_id) -> dict`: new `@tool` wrapping Phase 11's `get_hardship_flag_pure` (already at `lambda/handler.py:143-161`). Co-landed here so Phase 14 only adds the discriminated-union + pre-LLM guard, not the tool. Returns `{"hardship_flag": bool}`.
- **D-02: `simulate_savings` @tool remains unchanged from Phase 12** — the wrapper still calls `_provider.simulate_savings(customer_id)` and arithmetic still lives in Tools Lambda. Phase 13 adds tools alongside it; it does not refactor it. Tool composition order (see D-09) finishes every bill-shock turn with `simulate_savings` so REC-03 (both tracks returned) holds byte-exact.
- **D-03: Bill-shock threshold: `|monthly_delta| > 30% of 11-month mean`.** Symmetric — triggers on both over- and under-consumption spikes. Implemented in `detect_bill_shock_pure(billing_history)` as: take the most recent month's projected cost (`usage_kwh[0] * rate_per_kwh + supply`), compute the mean projected cost of months 1..11, assert `abs(delta) / mean > 0.30`. The 11-month mean is the reference, not the 12-month mean (avoids self-inclusion bias). All math sits in the pure helper; pytest fixture pins byte-exact values for CUST-002 + CUST-004 + CUST-005.
- **D-04: Tools Lambda action dispatcher extends Phase 12's `handler(event, context)`.** New branches:
  - `"detect_bill_shock"` → `detect_bill_shock_pure(get_billing_history_records(customer_id, table))` with `_validate_customer_id` upfront.
  - `"get_billing_history"` → already routed by Phase 12 D-02 (no change).
  - `"get_hardship_flag"` → already routed by Phase 12 D-02 via `get_hardship_flag_pure` (no change).
  - `"simulate_savings"` → already routed (Phase 12 D-05 back-compat).
- **D-05: Phase 13 adds exactly ONE new pure helper.** `detect_bill_shock_pure`. Everything else reuses Phase 11/12 primitives. This is the Chesterton's-Fence discipline: wrap around existing math, never through.
- **D-06: No `get_customer_profile` tool this phase.** Deferred — research lists it as optional; demo narrative on CUST-002 does not require segment-level framing copy. If a future phase adds persona segmentation UX, it can add the tool + docstrings then.

### reasoning_trace Shape + API Pass-Through

- **D-07: `reasoning_trace` is a PUBLIC top-level field on the response body**, alongside `green` and `cheapest`. No leading underscore (contrast with `_narrative_source`, which is internal and stripped). Pydantic schema extension on `RecommendationResponse`:
  ```python
  class ReasoningTraceEntry(BaseModel):
      tool: str           # e.g. "detect_bill_shock"
      summary: str        # code-composed one-liner from tool result
  class RecommendationResponse(BaseModel):
      green: TrackInfo
      cheapest: TrackInfo
      reasoning_trace: list[ReasoningTraceEntry] = Field(default_factory=list)
  ```
  Default empty list — single-tool turns (CUST-001/003/004/005) return `reasoning_trace: []`; multi-tool turns (CUST-002) return 2–3 entries.
- **D-08: Extractor helper always returns a list; never None, never raises.** New function `_extract_reasoning_trace(agent_result) -> list[ReasoningTraceEntry]` in `agent/agent.py`, modelled after the existing `_extract_lenient_from_agent_result` pattern at `agent/agent.py:238-260`. Iterates `agent_result.message["content"]`; for each `toolUse` block whose name is in `{"detect_bill_shock", "get_billing_history", "get_hardship_flag", "simulate_savings"}`, pairs it with the corresponding `toolResult` block (same `toolUseId`), and emits a `ReasoningTraceEntry` via the per-tool summary formatter (D-10). On ANY extraction failure — missing `content`, no matching `toolResult`, malformed JSON, agent_result is None — the helper returns `[]`. Tests cover the empty-list branch explicitly so the contract stays honoured.
- **D-09: Tool composition ordering rule (enforced via system prompt, not code).** The system prompt names a preference-ordered graph:
  1. Call `get_hardship_flag` first — if the customer is hardship-flagged, a future phase will short-circuit (Phase 14 wires the pre-LLM guard; Phase 13 still continues to recommendation but leaves the tool call in the trace as evidence of the check).
  2. Optionally call `detect_bill_shock` — if you want to confirm a potential anomaly before framing the recommendation.
  3. Optionally call `get_billing_history` — if the rep needs supporting evidence for the narrative.
  4. ALWAYS finish with `simulate_savings` so both recommendation tracks land per REC-03.
  Rep-selected intent (URL `?flow=bill_shock`) is explicitly REJECTED — keeps the agent self-driving per Area-1 decision and avoids a new UI contract. Research option.
- **D-10: `summary` strings are code-composed in Python from the tool's `toolResult` JSON — NEVER LLM-generated.** New module `agent/reasoning/summaries.py` (or inline in the extractor) hosts one formatter per tool:
  ```python
  def _summary_detect_bill_shock(result: dict) -> str:
      if result.get("is_shock"):
          return (
              f"Bill shock detected: +${result['delta_dollars']:.2f} "
              f"{result['shock_month']} vs 11-month avg "
              f"(${result['current_dollars']:.2f} vs ${result['mean_dollars']:.2f})"
          )
      return "No bill shock: monthly usage within 11-month envelope"
  def _summary_get_billing_history(result: list[dict]) -> str:
      return f"{len(result)} months retrieved"
  def _summary_get_hardship_flag(result: dict) -> str:
      return f"hardship_flag={result.get('hardship_flag', False)}"
  def _summary_simulate_savings(result: dict) -> str:
      return (
          f"Green ${result['green']['saving_monthly']:.2f}/mo; "
          f"Cheapest ${result['cheapest']['saving_monthly']:.2f}/mo"
      )
  ```
  SAV-03 by construction — arithmetic is in the pure helpers; formatting is deterministic Python. Bi-mode import of this module in `agent/agent.py` follows the same pattern as `narrative/` (D-16 of Phase 12).
- **D-11: D-15 (banned-terms dual-gate) is EXEMPT for `reasoning_trace`.** Trace summaries are code-generated observability — they intentionally contain dollar figures, dates, percentages (that's the point). `validate_usage_narrative` and `validate_call_script` apply ONLY to `usage_narrative` and `call_script` on each `TrackInfo`. Documented explicitly in CLAUDE.md addendum written during this phase: "D-15 dual-gate covers narrative surfaces; `reasoning_trace` is a separate observability surface with no content filter." Pytest explicitly asserts a sample trace summary contains digits + `$` and passes validation (counter-test to lock the exemption).
- **D-12: `api_lambda/handler.py` passes `reasoning_trace` through UNCHANGED.** The existing `body.pop("_narrative_source", None)` at `api_lambda/handler.py:121` stays; add NOTHING for `reasoning_trace`. Customer-not-found detection at `api_lambda/handler.py:152` ("no `green` or `cheapest` keys in body") remains correct — `reasoning_trace` presence/absence does not affect it (hardship-branch detection is Phase 14's surgical update). Pytest added to `tests/test_api_lambda.py` covering the pass-through + no-field-mutation contract.
- **D-13: No shape-validation in `api_lambda/handler.py`.** The Pydantic schema on the agent side is the only gate. If shape drifts, it surfaces as a ValidationError inside `invoke()` which routes through the existing D-04 fallback. API Lambda stays dumb.

### 4-Tool Cap + D-04 Fallback

- **D-14: Cap is `Agent(max_iterations=4)` on the Strands `_agent` singleton at `agent/agent.py:323`.** Single line change: `Agent(model=_model, system_prompt=SYSTEM_PROMPT, tools=[...], max_iterations=4)`. `max_iterations=4` caps the LLM agent loop at 4 iterations (each iteration = one LLM call + its tool invocations per Strands 1.37 semantics). Research step during planning MUST confirm Strands 1.37.0's exact exception / stop_reason semantics when the cap fires — the Plan will pin one of:
  - Strands raises a documented exception type (planner names it) → caught in `invoke()` and routed to D-04 fallback,
  - OR Strands returns `agent_result.stop_reason = "max_iterations_exceeded"` (or similar) → detected post-call and routed to D-04.
- **D-15: When the cap fires, the response body uses the EXISTING D-04 fallback path.** No new exception class, no new response shape, no new public field. The existing `except Exception` at `agent/agent.py:394-418` catches the cap exception (or a new branch inspects `stop_reason`) and calls the Tools Lambda directly for `simulate_savings`, stitches in `FALLBACKS[customer_id]` narrative, and returns the normal recommendation shape PLUS a partial `reasoning_trace` assembled from whatever tools DID fire before the cap. `_narrative_source` marks narrative as `"fallback"` on both tracks. D-04 preserved by reusing the proven path.
- **D-16: Offline pytest is the primary gate for cap behaviour.** `tests/test_bill_shock_flow.py::test_four_tool_cap_fires_gracefully`:
  1. Swap to `InMemoryProvider` via `_provider_swap` fixture.
  2. Monkey-patch `_agent` with a crafted loop-prompt OR use a test-only @tool that tail-calls itself.
  3. Invoke `invoke({"customer_id": "CUST-001"})`.
  4. Assert response body: `"green"` + `"cheapest"` + `"reasoning_trace"` (may be partial) present; `_narrative_source` marks fallback; HTTP 200-equivalent shape (no `"errorMessage"` key, no raise).
  5. Assert CloudWatch-log-style observability: log line with `"cap_exhausted": True` or equivalent marker.
  Fully offline — no live Bedrock/Strands dependency.
- **D-17: No live smoke test for cap behaviour in Phase 13.** Sonnet 4.6 is tuned to avoid runaway loops; crafting a reliable infinite-delegator prompt against live Bedrock is expensive + flaky. The offline pytest covers the contract; Phase 16 DEMO-10's "AGENT-01 3-tool determinism" canary is the live-stack observability surface.

### Per-Flow Prewarm Gate + Cross-Persona Canary

- **D-18: `scripts/prewarm.py` extends to per-flow warm-median gates this phase — 3000ms single-tool / 2500ms multi-tool.** Rotation in Phase 13: CUST-002 (multi-tool) + one single-tool persona (CUST-001 recommended) for comparative floor. Exit 0 only if BOTH gates pass. 0/1/2 taxonomy preserved (0=all gates pass, 1=any gate fails / HTTP error, 2=setup error). Flow classification via `response.reasoning_trace.length >= 2` (empty/1-entry = single-tool; 2+ = multi-tool). Phase 16 DEMO-09 extends to all 5 personas; Phase 13 ships the mechanism + 2-persona rotation.
- **D-19: Latency-floor witness is a smoke-gated pytest, not a prewarm-script assertion.** New `tests/test_narrative_eval_live.py::test_agent01_latency_floor` asserts CUST-002 live response latency `> 1000ms` — sub-1s response on a 2–3 tool turn is a fabrication signature. Marker: `pytest -m smoke`. Complements, not replaces, the prewarm-gate p95 upper bound.
- **D-20: Cross-persona canary test (Pitfall C5 prevention) is offline + InMemoryProvider-based.** New `tests/test_bill_shock_flow.py::test_no_fabrication_across_personas`:
  1. Swap to `InMemoryProvider`.
  2. Invoke on CUST-002 (bill-shock) and CUST-004 (non-shock).
  3. Assert `reasoning_trace` differs byte-exact between the two (same summary strings across different personas = fabrication signature, exact Phase 06.1 failure mode).
  4. Assert `detect_bill_shock` result differs (`is_shock=True` for CUST-002, `is_shock=False` for CUST-004).
  5. Assert savings differ (Marcus $16.90/$30.98 vs existing CUST-004 fixture).
- **D-21: CloudWatch tool-invocation counter assertion is smoke-gated.** Added to `tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked`: query CloudWatch `AWS/Lambda` `Invocations` metric for the Tools Lambda over the test window, assert >= 2 invocations during a single AGENT-01 lookup. Zero invocations = LLM fabricated tool output. Marker: `pytest -m smoke`.
- **D-22: Strands 1.37.0 stays pinned.** No Strands bump in Phase 13. Reaffirmed in PROJECT.md + CLAUDE.md addendum: any Strands minor/major bump requires its own decimal phase (like Phase 06.1) with cross-persona canary re-run. Belt-and-braces against C5. Frozen lockfile contract (`--require-hashes`) enforces this mechanically.

### System Prompt Extension

- **D-23: `_BASE_SYSTEM_PROMPT` at `agent/agent.py:285-311` is extended in place.** `NARRATIVE_PROMPT` (loaded via `narrative/prompt_loader.py`) is NOT touched. Edit targets:
  1. **Generalise SAV-03 language.** Replace the "`simulate_savings` tool returns the deterministic, authoritative numbers" paragraph with: "ALL arithmetic — savings, bill-shock deltas, averages, dates — comes from tools. NEVER compute, estimate, round, or adjust numbers yourself. Tool output is the single source of truth for every numeric and date value in your response."
  2. **Replace single-tool rule 1** ("Call the simulate_savings tool ONCE with the customer_id provided.") with a preference-ordered graph per D-09 + a concise list of the four available tools + "Do not call unnecessary tools — each extra tool call costs latency."
  3. **Retain rules 2–7 verbatim** (VERBATIM copy of numbers, both tracks, never ranked, never only one, no arithmetic, byte-exact saving_monthly / saving_annual).
- **D-24: Cross-persona canary pytest GUARDS the prompt edit.** Because prompt wording is load-bearing for Pitfall C5, any future edit to the bill-shock-flow prompt paragraph must re-run `test_no_fabrication_across_personas` offline + `test_agent01_*` live smokes. Recorded in CLAUDE.md addendum.
- **D-25: No new prompt file, no conditional loading.** One system prompt, assembled once at module load (matches Phase 12 assembly pattern: `SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT`). Single source of truth.

### UI ReasoningTrace Component

- **D-26: `ReasoningTrace` is a new React component at `ui/src/components/ReasoningTrace.tsx`.** Collapsed-by-default disclosure. Renders a single row above the 2-column `RecommendationCard` grid:
  - Collapsed state (default): `▶ N steps: detect_bill_shock → get_billing_history → simulate_savings` — tool names only, NO numbers in collapsed copy (UI-01 vertical budget = 1 row max).
  - Expanded state (user click): numbered ordered list of summary strings below the disclosure row.
  - Empty list (`reasoning_trace: []`): component returns `null` — zero vertical cost for single-tool turns.
- **D-27: `ReasoningTrace` honours `?narrative=off` by returning `null` entirely** (both collapsed and expanded). Imports `NARRATIVE_ENABLED` from `ui/src/lib/flags.ts`; `if (!NARRATIVE_ENABLED) return null`. Matches the existing pattern in `RecommendationCard.tsx` and `RecommendationSkeletons.tsx`. LD-7 single-flag contract: `?narrative=off` collapses EVERY v3.0 UI surface to v2.0 shape — trace + future hardship banner (Phase 14) + future follow-up drawer (Phase 15) all honour the same flag.
- **D-28: Placement is a single row above the card grid.** DOM order: `<LookupForm /> <VersionIndicator /> <ReasoningTrace /> <RecommendationCard green /> <RecommendationCard cheapest />`. Shared across both cards (trace is turn-level, not track-level per D-07/D-12). At 1280×800 viewport, LookupForm + collapsed ReasoningTrace + 2 cards with narrative + call_script fit above the fold. Vitest snapshot at 1280×800 asserts UI-01 preserved with a sample 3-entry collapsed trace rendered.
- **D-29: Mock fixtures in `ui/src/lib/mock/recommendations.ts` add a `MOCK_REASONING_TRACE_CUST002` byte-exact to the backend formatter output.** CUST-002 mock response gains a 3-entry trace; CUST-001/003/004/005 mock responses gain `reasoning_trace: []`. Comment in `ui/src/lib/mock/recommendations.ts` header gets a new line alongside the existing ones: "Values MUST stay in sync with `agent/reasoning/summaries.py` formatters — single-commit discipline." Emergency `npm run build:mock` path renders the full AGENT-01 demo offline.
- **D-30: New `ReasoningTrace.test.tsx` covers six cases:**
  1. Empty list → renders `null`.
  2. 3-entry list → renders collapsed row with tool names + chevron.
  3. Click expands to ordered list.
  4. `?narrative=off` + non-empty list → renders `null` (vitest `vi.stubGlobal('location', { search: '?narrative=off' })` per existing pattern).
  5. `?narrative=off` + empty list → renders `null`.
  6. 1-entry list (edge case — should this even happen?) → renders the single-step collapsed row; expanded shows one entry.

### Stack-Policy Lift Ceremony

- **D-31: Phase 13 lifts THREE stacks** — `CustomerTariff` (Tools Lambda asset rebuild for `detect_bill_shock` action branch + pure helper), `CustomerTariffAgent` (container rebuild for new tools, prompt, cap, extractor, summaries module), and `CustomerTariffApi` (API Lambda rebuild — the `reasoning_trace` pass-through is existing behaviour since nothing is stripped, BUT the tests/test_api_lambda.py expansion + any D-04 edge case may trip a micro-change). Planner MUST run `cdk diff CustomerTariffApi` during planning; if diff = 0, downgrade to a 2-stack lift (CustomerTariff + CustomerTariffAgent). **Default plan: lift all 3; if `cdk diff CustomerTariffApi == 0` after all code changes, drop `CustomerTariffApi` from the lift list.**
- **D-32: Ceremony pattern matches v2.0 Phase 10 + Phase 11/12 precedent.** Scripted `aws cloudformation set-stack-policy` allow-all → `cdk deploy` → verify → `aws cloudformation set-stack-policy` re-apply deny-Update:* → re-enable termination protection → byte-equality gate on the re-applied policies. `CustomerTariffFrontend` is NOT lifted (unfrozen from v2.0 Phase 10).
- **D-33: Pre/post byte-equivalence gate.** Before-and-after live lookups on CUST-001 + CUST-002 (+ CUST-004 as a non-shock sanity) capture the JSON bodies at `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/{pre,post}/{customer_id}.json`. Diff rule: `green.saving_monthly`, `green.saving_annual`, `cheapest.saving_monthly`, `cheapest.saving_annual`, `green.plan_id`, `cheapest.plan_id` MUST be byte-equal pre vs post for every persona. `reasoning_trace` and narrative fields are excluded (narrative is stochastic; trace is new in post). Reuse `scripts/capture_live_recommendations.py` from Phase 12 D-06 if it was promoted to `scripts/`; otherwise add to `.planning/phases/13-*/capture_live_recommendations_13.py` (planner decides).

### Claude's Discretion

- Exact Strands 1.37.0 exception taxonomy for `max_iterations` exhaustion — research during planning must confirm and pin. If Strands exposes both an exception AND a `stop_reason`, planner picks one to branch on (preference: stop_reason inspection, exception fallback).
- Whether `agent/reasoning/summaries.py` is a new module or an inline function in the extractor. New module is cleaner for future tool additions; inline is simpler for the 4-tool case. Bi-mode imports apply either way.
- Whether `_extract_reasoning_trace` lives in `agent/agent.py` alongside `_extract_lenient_from_agent_result` or in a new `agent/reasoning/extractor.py`. Planner picks; both follow existing patterns.
- Whether the crafted-loop pytest uses a monkey-patched `_agent` or a real Strands agent with a self-referential fake tool. Either achieves the same cap-fire assertion. Planner picks based on Strands 1.37.0's mock-friendliness.
- Test file organisation: one big `tests/test_bill_shock_flow.py` vs splitting into `tests/test_detect_bill_shock_pure.py` + `tests/test_reasoning_trace.py` + `tests/test_four_tool_cap.py`. Phase 12 decisions left this to the planner; same latitude here.
- Whether to add a new `pytest -m latency` marker for `test_agent01_latency_floor` specifically, or fold into existing `-m smoke`. Smoke tier is probably fine.
- Exact wording of the extended `_BASE_SYSTEM_PROMPT` — D-23 specifies the structural edits; planner writes the final prose within those bounds. Must retain the VERBATIM numeric-integrity clauses (rules 2–7).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap

- `.planning/ROADMAP.md` §"Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01)" (lines 88–99) — phase goal, 5 success criteria, invariant ownership (SAV-03 extended, UI-01/02 preserved, D-04 cap fallback, `_narrative_source` extension with public `reasoning_trace`).
- `.planning/REQUIREMENTS.md` §"Agentic Depth (AGENT)" (AGENT-01, AGENT-01a, AGENT-01b) — bill-shock multi-tool flow + 2500ms warm p95 + 4-tool hard cap in code.
- `.planning/REQUIREMENTS.md` §"Locked Decisions" — **LD-4** latency + `ConcurrentToolExecutor` + 4-tool cap is the load-bearing constraint; **LD-7** `?narrative=off` kill switch extension.
- `.planning/STATE.md` §"Invariants the v3.0 roadmap must preserve" — SAV-03 cross-persona canary + latency-floor witness mandatory; `_narrative_source` / `reasoning_trace` pass-through contract explicit; stack-policy lift ceremony applies to at least one of the three frozen stacks.
- `.planning/PROJECT.md` §"Current Milestone: v3.0" — target features: AGENT-01 headline capability.

### Research (v3.0)

- `.planning/research/SUMMARY.md` §Executive Summary + LD-4 + Phase 3 — AGENT-01 risk cluster (latency stacking, fabrication regression), pitfall mitigations, 2500ms target rationale, per-flow prewarm gate preference.
- `.planning/research/ARCHITECTURE.md` §"1. AGENT-01 — Bill-Shock Multi-Tool Flow" (lines 144–196) — integration decisions, SAV-03 extension argument, buffered-return rationale, `_reasoning_trace` → `reasoning_trace` public-field decision (research Q3), toolUse extraction pattern mirroring `_narrative_source`.
- `.planning/research/ARCHITECTURE.md` §"Pattern 1: Action Dispatch on Existing Lambda (AGENT-01 enabler)" (lines 751–780) — action-dispatch code skeleton; `detect_bill_shock` branch concrete example.
- `.planning/research/ARCHITECTURE.md` §"Phase 3: AGENT-01 — bill-shock multi-tool flow" (lines 926–936) — deliverables list, unblocks, invariants at risk.
- `.planning/research/ARCHITECTURE.md` open-question Q1 — bill-shock detection threshold numeric definition (D-03 pins 30% symmetric mean delta, closes the open question).
- `.planning/research/ARCHITECTURE.md` open-question Q3 — `_reasoning_trace` internal marker vs public `reasoning_trace` field (D-07 pins public, closes the open question).
- `.planning/research/PITFALLS.md` — **C1** (multi-tool latency stacking — ConcurrentToolExecutor + 4-cap + per-flow gate + cross-persona canary), **C5** (Strands multi-tool fabrication regression — cross-persona canary + CloudWatch counter + latency-floor witness + frozen Strands version), **M4** (D-04 fallback for new response shape with `reasoning_trace`), **M5** (prewarm extended per-flow).
- `.planning/research/STACK.md` — Strands 1.37.0 `ConcurrentToolExecutor` as default; `Agent(max_iterations=...)` primitive; what NOT to use (SSE/streaming rejected — breaks `Config(read_timeout=25)` invariant).
- `.planning/research/FEATURES.md` §AGENT-01 — call-centre agent-assist UX vendor landscape; reasoning-trace UX is table-stakes; rep-selected-intent vs LLM-decides tradeoff (D-09 picks LLM-decides).

### Prior phase context (carry-forward)

- `.planning/phases/11-new-personas-tariff-archetypes/11-CONTEXT.md` — **D-08** (PROFILE row shape on `tariff-billing`), **D-10** (`get_hardship_flag_pure` pure helper signature), **D-13** byte-exact persona savings fixtures (MARCUS_WEBB_RECORDS fixture is the CUST-002 bill-shock source — confirm the December row is engineered as the shock month), **D-21** PROFILE filter inside `get_billing_history`.
- `.planning/phases/12-customerdataprovider-abstraction/12-CONTEXT.md` — **D-02** top-level Lambda `handler(event, context)` action dispatcher (Phase 13 adds `detect_bill_shock` branch; Phase 12 already dispatches `get_billing_history`/`get_hardship_flag`/`simulate_savings`), **D-03** `_provider` module-level singleton (Phase 13's new tools do not use the provider — they invoke Tools Lambda directly via the existing `_lambda_client` pattern, consistent with how `simulate_savings` is wrapped), **D-06**/**D-07** pre/post live-diff ceremony pattern (D-33 reuses), **D-11** `_provider_swap` autouse fixture + InMemoryProvider (D-16/D-20 reuse for offline tests).
- `.planning/phases/12-customerdataprovider-abstraction/12-CONTEXT.md` §"Bi-Mode Import Pattern" — **D-16/D-17** bi-mode imports in `agent/providers.py`; Phase 13's new `agent/reasoning/summaries.py` (if modularised) follows the same `try: from reasoning.summaries import ... except: from agent.reasoning.summaries import ...` pattern.

### Load-bearing project-level docs

- `CLAUDE.md` §"Critical invariants — break these and the demo dies" — **SAV-03** (LLM never does arithmetic — D-10 extends this to code-composed summary strings), **REC-03** (both tracks always returned — D-09 enforces by always finishing with `simulate_savings`), **D-04 never-500** (D-15 routes cap exhaustion through this path), **D-15 narrative dual-gate** (D-11 documents `reasoning_trace` exemption), **`_narrative_source` marker** (D-07 defines parallel-but-public `reasoning_trace` field, NOT stripped by API Lambda), **Bi-mode imports in `agent/agent.py`** (D-10 `summaries.py` follows the pattern), **`runtimeSessionId` generated INSIDE `handler()`** (untouched by Phase 13 — SC-3 preserved), **`?narrative=off`** (D-27 extends LD-7 kill switch to `ReasoningTrace`).
- `CLAUDE.md` §"Common commands" — `pytest tests/test_bill_shock_flow.py`, `cdk deploy CustomerTariff CustomerTariffAgent`, `BACKEND_API_URL=... python3 scripts/prewarm.py` (extended per-flow).
- `CLAUDE.md` §"Things to know before changing things" — `demo-v2.0` deny-Update:* lift via `aws cloudformation set-stack-policy`; stack-policy files under `infrastructure/stack-policies/`; `us.anthropic.claude-sonnet-4-6` model literal unchanged; frozen lockfiles untouched (zero deps this phase).
- `DEMO-RUNBOOK.md` §freeze section — stack-policy lift ceremony scripted pattern (D-32 re-executes).
- `DEMO-RUNBOOK.md` §2 T-24h — visual rehearsal requires warm median under 2500ms on CUST-002 (AGENT-01a gate); Phase 13's per-flow prewarm gate makes this automated, not operator-judged.

### Source code to read before touching

- `agent/agent.py:14-71` — bi-mode imports (narrative + providers). New `agent/reasoning/summaries.py` follows this pattern (if modularised per D-10 discretion).
- `agent/agent.py:238-260` — `_extract_lenient_from_agent_result` is the exact template for D-08's `_extract_reasoning_trace` helper.
- `agent/agent.py:263-281` — existing `simulate_savings` @tool. New `@tool detect_bill_shock`, `@tool get_billing_history`, `@tool get_hardship_flag` follow the same module-level + provider-free Lambda-invoke pattern (they DO NOT go through `_provider` — they invoke Tools Lambda directly like `simulate_savings` did pre-Phase-12, per D-01 discretion unless the planner routes through provider for consistency).
- `agent/agent.py:285-311` — `_BASE_SYSTEM_PROMPT` (edit target per D-23).
- `agent/agent.py:323-327` — `_agent = Agent(...)` (add `max_iterations=4` per D-14).
- `agent/agent.py:335-420` — `@app.entrypoint def invoke(payload)` — end of the agent invocation path; Phase 13 inserts reasoning-trace extraction before return (D-08) and catches the cap-exhaustion condition before the fallback (D-15).
- `agent/agent.py:394-418` — existing D-04 fallback path; D-15 cap fallback reuses this.
- `lambda/handler.py:39-52` — `_CUSTOMER_ID_PATTERN` + `_validate_customer_id`; new `detect_bill_shock` branch reuses.
- `lambda/handler.py:60-140` — `simulate_savings_pure` (Chesterton's Fence — do NOT touch). Reference for `detect_bill_shock_pure` style.
- `lambda/handler.py:143-161` — `get_hardship_flag_pure` (Phase 11) — already wrapped by Phase 12 action dispatcher.
- `lambda/handler.py:166-183` — `get_billing_history` Lambda handler with PROFILE filter.
- `lambda/handler.py` (dispatcher) — Phase 12's top-level `handler(event, context)` is the extension target (D-04).
- `api_lambda/handler.py:121` — `body.pop("_narrative_source", None)` — parallel pattern that does NOT apply to `reasoning_trace` (D-12).
- `api_lambda/handler.py:152` — customer-not-found detection — UNCHANGED in Phase 13 (Phase 14 territory). Pytest covers no-regression.
- `ui/src/lib/flags.ts` — `NARRATIVE_ENABLED` — imported by new `ReasoningTrace.tsx` per D-27.
- `ui/src/components/RecommendationCard.tsx` — structural template for `ReasoningTrace.tsx` (narrative-off handling, vitest patterns).
- `ui/src/components/RecommendationCard.test.tsx:119-131` — vitest `?narrative=off` stub pattern; `ReasoningTrace.test.tsx` mirrors.
- `ui/src/lib/mock/recommendations.ts` — `MOCK_RECOMMENDATIONS` extension target for D-29.
- `tests/conftest.py` — `_provider_swap` autouse fixture + `mock_marcus_response` fixture (CUST-002 target for canary tests).
- `scripts/prewarm.py` — extension target for D-18 per-flow gate. Preserve 0/1/2 exit taxonomy.
- `tests/test_narrative_eval_live.py` — smoke-marker live eval home. D-19 + D-21 add canaries here.
- `infrastructure/stack-policies/` — freeze lift + deny-Update policy files (D-32).
- `infrastructure/foundation_stack.py` — CustomerTariff (Tools Lambda asset) CDK construct; redeploy triggered by `lambda/handler.py` change.
- `infrastructure/agentcore_stack.py` — CustomerTariffAgent (container) CDK construct; redeploy triggered by `agent/agent.py` + new `agent/reasoning/` changes.

### Stacks touched

- `CustomerTariff` — **LIFT required.** Tools Lambda asset rebuild for `detect_bill_shock` action branch + `detect_bill_shock_pure` pure helper (D-04, D-05).
- `CustomerTariffAgent` — **LIFT required.** Container rebuild for new tools, extended prompt, `max_iterations=4`, reasoning trace extractor, summaries module (D-01, D-14, D-23, D-28).
- `CustomerTariffApi` — **LIFT conditional on `cdk diff != 0` at planning time.** `reasoning_trace` is pass-through (D-12) so NO code change expected, BUT tests/test_api_lambda.py extension may surface edge cases (D-31).
- `CustomerTariffFrontend` — **NO LIFT.** Amplify-unfrozen from v2.0 Phase 10. UI redeploy via `npm run build` + `cdk deploy CustomerTariffFrontend` independent of the frozen-stack ceremony.

### Invariant ownership (this phase)

- **SAV-03** — extended to every new arithmetic tool; `detect_bill_shock_pure` is pure Python in Tools Lambda; `reasoning_trace` summaries are code-composed in `summaries.py` formatters (D-10). Cross-persona canary + latency-floor witness + CloudWatch counter enforce discipline (D-19, D-20, D-21).
- **REC-03** — preserved by D-09 system-prompt rule 4 ("ALWAYS finish with `simulate_savings`") and structural `RecommendationResponse` schema requiring both `green` + `cheapest`.
- **D-04 never-500** — preserved by D-15 routing cap exhaustion through the existing `except Exception` fallback at `agent/agent.py:394-418`.
- **D-15 narrative dual-gate** — unchanged for `usage_narrative` / `call_script`; explicitly exempt for `reasoning_trace` (D-11 documents the exemption + adds counter-pytest).
- **`_narrative_source` marker** — stripped by API Lambda unchanged. Parallel public field `reasoning_trace` is NOT stripped (D-12).
- **`runtimeSessionId` generated INSIDE `handler()`** — untouched by Phase 13. SC-3 preserved by reading only, not writing the session-id code path.
- **UI-01** — preserved by D-26/D-28 collapsed-by-default single-row trace + vitest snapshot at 1280×800.
- **UI-02** — preserved by D-18 per-flow prewarm gate (2500ms multi-tool) + `ConcurrentToolExecutor` default + 4-tool cap.
- **Bi-mode imports** — new `agent/reasoning/summaries.py` (if modularised) follows the Phase 12 D-16 pattern. Verified by existing bi-mode test discipline.
- **Frozen lockfile contract** — zero new dependencies this phase. `--require-hashes` contract untouched.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **Phase 12 action dispatcher at `lambda/handler.py` (top-level `handler(event, context)`)** — Phase 13 adds ONE new branch (`"detect_bill_shock"`); `get_billing_history` and `get_hardship_flag` branches already exist.
- **`_lambda_client` module-level singleton at `agent/agent.py:60-83`** — new `@tool` wrappers reuse via direct `_lambda_client.invoke` (mirroring pre-Phase-12 `simulate_savings` pattern) OR via `_provider` if the planner decides to extend the Protocol. Default plan: direct `_lambda_client.invoke` for the three new @tools (keeps Protocol 3-method clean per LD-5).
- **`_extract_lenient_from_agent_result` at `agent/agent.py:238-260`** — exact template for D-08's `_extract_reasoning_trace`. Same `agent_result.message["content"]` iteration + `toolUse` detection + try/except fallback.
- **`_BASE_SYSTEM_PROMPT` + `NARRATIVE_PROMPT` composition at `agent/agent.py:285-314`** — edit the base string in place; NARRATIVE_PROMPT untouched.
- **`Agent(model=_model, system_prompt=SYSTEM_PROMPT, tools=[...])` at `agent/agent.py:323-327`** — add `max_iterations=4` and the 3 new @tools to the `tools=[...]` list.
- **`except Exception` fallback at `agent/agent.py:394-418`** — D-04 never-500 path; D-15 cap fallback reuses.
- **`validate_usage_narrative` + `validate_call_script` from `agent/narrative/validators.py`** — apply only to `TrackInfo.usage_narrative` + `TrackInfo.call_script`. NOT applied to `reasoning_trace` (D-11).
- **`FALLBACKS` dict from `agent/narrative/fallbacks.py`** — per-customer-id fallback narrative strings; reused on cap exhaustion (D-15) and existing failure paths.
- **`_provider_swap` autouse fixture + `inmemory_provider` fixture from Phase 12 D-11 in `tests/conftest.py`** — offline test swap for cap + canary tests (D-16, D-20).
- **`mock_marcus_response` fixture in `tests/conftest.py`** — byte-exact CUST-002 values for cross-persona canary (D-20).
- **`scripts/prewarm.py` stdlib-only 0/1/2 taxonomy + warm-median logic** — extension target for per-flow gate (D-18). Preserve exit codes.
- **`tests/test_narrative_eval_live.py` smoke-marker pattern** — live eval home for D-19 latency-floor + D-21 CloudWatch counter.
- **`ui/src/lib/flags.ts::NARRATIVE_ENABLED`** — imported by new `ReasoningTrace.tsx` (D-27).
- **`ui/src/components/RecommendationCard.tsx` + `.test.tsx`** — structural + test template for `ReasoningTrace.tsx` (D-26, D-30).
- **`ui/src/lib/mock/recommendations.ts::MOCK_RECOMMENDATIONS`** — extension target for D-29.
- **Stack-policy lift scripts at `infrastructure/stack-policies/`** — v2.0 Phase 10 + Phase 11/12 precedent; re-executed here for up to 3 stacks (D-31/D-32).

### Established Patterns

- **Module-level singletons + lazy init** (`_lambda_client`, `_agent`, `_provider` from Phase 12) — Phase 13 does not add new singletons; extends existing ones.
- **Pure-helper-plus-handler** (`simulate_savings_pure` + `simulate_savings` Lambda handler; `get_hardship_flag_pure` + dispatcher branch) — `detect_bill_shock_pure` + `detect_bill_shock` action branch follows the same pattern (D-04, D-05).
- **Bi-mode imports (container `/app` vs repo layout)** — applies to new `agent/reasoning/summaries.py` (if modularised) per D-10 discretion. Matches narrative/ and providers/ precedent.
- **Pydantic schema on the agent side + dumb pass-through on API Lambda** — `reasoning_trace` is schema-validated at the agent; API Lambda stays ignorant (D-12/D-13).
- **`?narrative=off` kill-switch contract via `flags.ts`** — LD-7 extension: `ReasoningTrace` imports `NARRATIVE_ENABLED` and returns `null` (D-27). Mirrors `RecommendationCard.tsx` + `RecommendationSkeletons.tsx`.
- **Vitest `vi.stubGlobal('location', { search: '?narrative=off' })`** — test pattern for kill-switch assertions (D-30 cases 4 + 5).
- **Offline + smoke-marker dual tier** — cap + canary tests offline (D-16, D-20); latency-floor + CloudWatch counter smoke (D-19, D-21). Matches v2.0 Phase 9 eval harness discipline.
- **Per-flow-gate taxonomy** — D-18 extends `scripts/prewarm.py` 0/1/2 exit code discipline to multiple gates with exit-0-only-if-all-pass aggregation.
- **Pre/post byte-equivalence diff ceremony** — D-33 reuses the Phase 12 D-06 capture pattern; excludes new + stochastic fields (reasoning_trace + narrative).
- **Stack-policy lift-deploy-reapply ceremony** — D-31/D-32 replicate v2.0 Phase 10 pattern for 2–3 stacks (conditional on API Lambda diff).

### Integration Points

- `lambda/handler.py` — **MODIFY**: add `detect_bill_shock_pure` (D-05) + extend the Phase 12 action dispatcher with the `"detect_bill_shock"` branch (D-04). Existing branches untouched.
- `agent/agent.py` — **MODIFY**:
  - 3 new `@tool` wrappers (D-01) next to `simulate_savings`.
  - Extended `_BASE_SYSTEM_PROMPT` (D-23).
  - `_agent = Agent(..., tools=[simulate_savings, detect_bill_shock, get_billing_history, get_hardship_flag], max_iterations=4)` (D-14).
  - New `_extract_reasoning_trace(agent_result)` helper + call site before response return (D-08).
  - `RecommendationResponse` schema + `ReasoningTraceEntry` class (D-07).
  - Cap-exhaustion branch inside `invoke()` routing to the existing `except Exception` fallback (D-15).
- `agent/reasoning/summaries.py` — **NEW FILE** (or inline — planner discretion): per-tool summary formatters (D-10). Bi-mode import if modularised.
- `agent/reasoning/__init__.py` — **NEW** (if modularised) — empty or re-exports summaries symbols.
- `api_lambda/handler.py` — **LIKELY NO CODE CHANGE**: `reasoning_trace` passes through the generic body unchanged (D-12). Pytest added to cover contract.
- `ui/src/components/ReasoningTrace.tsx` — **NEW FILE** (D-26).
- `ui/src/components/ReasoningTrace.test.tsx` — **NEW FILE** (D-30).
- `ui/src/pages/...` or equivalent grid-rendering parent — **MODIFY** to insert `<ReasoningTrace trace={response.reasoning_trace} />` above the card grid (D-28).
- `ui/src/lib/mock/recommendations.ts` — **MODIFY**: add `MOCK_REASONING_TRACE_CUST002`; attach `reasoning_trace: []` to 4 non-bill-shock personas + 3-entry trace to CUST-002 (D-29).
- `ui/src/lib/recommendations.ts` — **MODIFY**: ensure response type includes optional `reasoning_trace: ReasoningTraceEntry[]` field.
- `tests/test_bill_shock_flow.py` — **NEW FILE**: 4-tool cap pytest (D-16) + cross-persona canary (D-20) + `detect_bill_shock_pure` unit tests (D-03/D-05).
- `tests/test_narrative_eval_live.py` — **MODIFY**: add `test_agent01_latency_floor` (D-19) and `test_agent01_tools_actually_invoked` (D-21), both smoke-marker-gated.
- `tests/test_api_lambda.py` — **MODIFY** (or new pytest): assert `reasoning_trace` pass-through contract (D-12/D-13).
- `scripts/prewarm.py` — **MODIFY**: per-flow gate split + CUST-001 vs CUST-002 rotation (D-18). 0/1/2 exit taxonomy preserved.
- `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/{pre,post}/` — **NEW**: captured JSON bodies for pre/post byte-equality gate (D-33).
- `CLAUDE.md` — **MODIFY**: add addendum documenting (a) `reasoning_trace` D-15 exemption (D-11), (b) cap fallback routing through D-04 path (D-15), (c) Strands 1.37.0 frozen-version discipline (D-22).
- `infrastructure/foundation_stack.py` / `infrastructure/agentcore_stack.py` — **NO CODE CHANGE** but both trigger asset-diff redeploys; stack-policy lift required (D-31).
- `infrastructure/backend_api_stack.py` — **CONDITIONAL** (`cdk diff CustomerTariffApi` at planning time determines lift).

### Non-integration points (do NOT touch this phase)

- `agent/narrative/*` — no narrative validator changes; D-15 dual-gate unchanged. The reasoning-trace exemption is documented, not enforced in this module.
- `agent/providers.py` (Phase 12) — Protocol stays 3-method clean. New @tools do NOT add Protocol methods.
- `api_lambda/handler.py:152` customer-not-found detection — Phase 14's surgical update territory; Phase 13 must not regress.
- `RecommendationResponse.green` / `.cheapest` — REC-03 both-tracks invariant holds; schema additions are ALONGSIDE these fields, not nested in them.
- `simulate_savings_pure` at `lambda/handler.py:60-140` — Chesterton's Fence. Wrap around, never through.
- `get_hardship_flag_pure` at `lambda/handler.py:143-161` — Phase 11-shipped, stable.
- `infrastructure/seed_data/billing_records.py` data — read-only. If MARCUS_WEBB_RECORDS needs a bill-shock spike month engineered, Phase 11 D-13 already locked the byte-exact Marcus savings figures ($16.90/$30.98) — verify the existing December/January record already trips `|delta| > 30% of 11-month mean` BEFORE editing. If it does not, engineering a new spike month is a fixture change that shifts byte-exact savings and becomes a Phase 11 amendment (out of scope for Phase 13; flag immediately during planning).
- `tariff-billing` DynamoDB schema — no schema changes; PROFILE row format unchanged.
- `requirements.txt` / `requirements-dev.txt` — zero new deps. Strands 1.37.0 pinned (D-22).
- `ui/package-lock.json` — no new UI deps.
- `infrastructure/frontend_stack.py` — Amplify unfrozen; UI redeploy is independent of the frozen-stack ceremony.

</code_context>

<specifics>
## Specific Ideas

- **Preference-ordered tool graph, not a decision tree.** The agent decides per turn, guided by the system prompt's preference order (D-09), not a hard-coded branch. This matches v2.0's "LLM decides when to call simulate_savings" style and avoids a new UI intent contract. Research's rep-selected-intent option was evaluated and rejected.
- **`reasoning_trace` as observability, not sales copy.** The trace's entire value is "here's the proof the agent actually called tools and didn't fabricate numbers." That's incompatible with D-15's banned-terms list. Documenting the exemption explicitly in CLAUDE.md (D-11) prevents a future well-meaning developer from applying `_reject_forbidden` to summary strings and breaking the demo.
- **Cap fallback reuses the D-04 path, not a new path.** One fallback story across all failure modes. The `except Exception` at `agent/agent.py:394-418` is already the canonical never-500 surface; D-15 piggy-backs. Reduces new test surface and fragments.
- **Code-composed summaries as SAV-03 by construction.** Python formatters in `summaries.py` READ tool output dicts and PRINT deterministic strings. No LLM, no estimation, no arithmetic. The same discipline that keeps `saving_monthly` byte-exact extends naturally to "Bill shock detected: +$47 Dec vs $101 mean."
- **Per-flow prewarm gate with aggregation, not a single tightened gate.** Diagnostic value — when a gate fails you know WHICH flow regressed. Matches LD-4's explicit "per-flow gates" phrasing and sets up Phase 16's 5-persona rotation cleanly.
- **Cross-persona canary is the best C5 insurance.** Coincident values across DIFFERENT personas is the Phase 06.1 fabrication signature. Running the same flow on CUST-002 + CUST-004 offline with byte-exact assertions is cheap, deterministic, and catches the exact failure class.
- **ReasoningTrace's collapsed row shows tool NAMES, not summaries.** Tool names are domain-safe text ("detect_bill_shock"); summaries contain numbers. Expanded state shows the numbers. This way UI-01 at 1280×800 has zero-numeric content in the always-visible disclosure, and the full trace is one click away.
- **Mock fixtures maintained byte-exact with Python formatters.** `ui/src/lib/mock/recommendations.ts` header comment already warns about byte-sync with backend (from v2.0); D-29 extends the discipline to include `summaries.py` as an additional sync target. Emergency `npm run build:mock` path keeps working offline.

</specifics>

<deferred>
## Deferred Ideas

- **`get_customer_profile` tool** — research-optional; CUST-002 demo does not need segment-level framing. Add in v3.1 if a future persona-segmentation UX motivates it. Not in the 4-tool set.
- **Rep-selected flow intent (`?flow=bill_shock` URL param)** — research lists as optional; Area-1 decision locked LLM-decides. Keeping as a deferred escape valve if rehearsal shows Sonnet 4.6 inconsistently picks multi-tool vs single-tool on CUST-002.
- **SSE / Lambda response streaming for reasoning trace** — breaks `Config(read_timeout=25)` invariant (explicit rejection in STACK.md + SUMMARY.md LD-4). Buffered-return-with-CSS-animation stays.
- **`SequentialToolExecutor` (non-default)** — escape valve only. If rehearsal shows concurrent tool execution produces incoherent narrative ordering, swap to sequential for AGENT-01 only. Accept the latency cost. Pinned in SUMMARY.md LD-4.
- **Lambda Provisioned Concurrency on Tools Lambda** — SUMMARY.md cost table lists as optional cold-first-call-latency mitigation; not chosen (accept cold first-tool-call latency; prewarm gate covers warm-median).
- **Dedicated `cap_fired: true` response marker** — considered and rejected (D-15). `_narrative_source` already provides fallback observability; adding a second marker duplicates.
- **New `ReasoningTrace` drawer pattern** — drawer scaffolding is Phase 15's territory (WF-01 follow-up email). Phase 13 uses a collapsed inline disclosure.
- **Extending `CustomerDataProvider` Protocol with `detect_bill_shock` / `get_billing_history` methods** — violates LD-5 (Protocol stays 3 methods: `get_customer`, `get_billing_history`, `get_hardship_flag`). `get_billing_history` is already a Protocol method from Phase 12; the new @tools wrap Tools Lambda directly via `_lambda_client.invoke` for the new actions, keeping Protocol surface stable.
- **Full 5-persona prewarm rotation** — Phase 16 DEMO-09 territory. Phase 13 ships 2-persona rotation (CUST-001 + CUST-002) as the per-flow-gate mechanism.
- **Live smoke test for 4-tool cap against deployed Bedrock** — expensive + flaky on Sonnet 4.6; offline pytest covers the contract. Phase 16 DEMO-10's "AGENT-01 3-tool determinism" live canary is the observability surface.
- **Typed hardship categories** — AGENT-03, deferred to v3.1. Phase 13 ships `hardship_flag: bool` only.
- **Presenter DOC-01/02/03 content referencing the reasoning-trace pattern** — Phase 16 territory. Phase 13 leaves breadcrumbs (CLAUDE.md addendum documents the patterns).
- **`bedrock-agentcore` dep bump** — Phase 15 WF-01's single permitted bump. Phase 13 ships zero new deps.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase 13` returned zero matches at discussion time.

</deferred>

---

*Phase: 13-bill-shock-multi-tool-flow-agent-01*
*Context gathered: 2026-04-29*

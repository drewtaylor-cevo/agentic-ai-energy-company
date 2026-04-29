# Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01) — Research

**Researched:** 2026-04-29
**Domain:** Strands 1.37.0 multi-tool agent composition + Bedrock Sonnet 4.6 reasoning-trace UX + per-flow prewarm + Tools Lambda action dispatch
**Confidence:** HIGH on Strands/boto3/Marcus-fixture evidence (local source inspection + persona arithmetic); MEDIUM on empirical Bedrock warm latency (no live rehearsal data in repo); HIGH on stack-policy lift ceremony (repo precedent).

---

## RESEARCH BLOCKED

**Blocker:** Unknown #6 returned a load-bearing negative result. CONTEXT.md §Non-integration points explicitly flags this as a planning-halt trigger: *"if MARCUS_WEBB_RECORDS needs a spike month engineered, it becomes a Phase 11 amendment and is out of scope for Phase 13."*

**Finding:** MARCUS_WEBB_RECORDS **does not trip** the D-03 threshold (`|monthly_delta| / 11-month-mean > 0.30`) on any month. The most extreme Marcus month (2025-10, October 2025) registers a 0.1670 ratio — 45% short of the 0.30 gate. Under every reasonable interpretation of "most recent" (oldest, newest, per-month scan) the trigger stays silent. Full computation in §6 Finding below.

**Cross-persona scan — which, if any, engineered fixture already trips the 30% gate on STD-rate projected cost:**

| Persona | Max ratio | Month | Trips? |
|---|---|---|---|
| Sarah CUST-001 | 0.2298 | 2025-10 | No |
| **Marcus CUST-002** (designated bill-shock) | **0.1670** | **2025-10** | **No — BLOCKER** |
| Elena CUST-003 | 0.6344 | 2025-10 | Yes (7 months trip) |
| CUST-004 Solar | 0.2497 | 2025-08 | No |
| CUST-005 EV | 0.1228 | 2025-08 | No |
| CUST-006 Hardship | 0.1084 | 2025-08 | No |

**Planner cannot proceed to D-16 fixture pin (pytest byte-exact for CUST-002 `is_shock=True`) without resolving this.** The D-20 cross-persona canary also depends on the blocker — if CUST-002 does not trip but CUST-004 does not either, there is no contrast to assert.

**Four pivot options — all require a user decision before implementation planning:**

1. **Retune D-03 threshold to ~0.15 symmetric on the 11-month mean** (or 0.12 for margin). Marcus's 2025-10 at 0.167 would trip; Sarah's 2025-10 at 0.230 would also trip (creates a different canary shape — now CUST-005 EV at 0.123 is the non-shock contrast). Risk: weakens the "bill shock" semantic — 15% delta is not dramatic. Low-implementation, high-narrative cost.
2. **Reassign the designated bill-shock persona to CUST-003 Elena** (6× above gate on 2025-10). Elena has 7 months tripping; the shock would be genuine and the trace numbers visible. Risk: the demo narrative previously earmarked CUST-002 (see Phase 11 D-13). Changing the designated persona touches CONTEXT.md D-09/D-19/D-20/D-29 + DEMO-RUNBOOK + UI mock fixtures. Medium-implementation cost, low-narrative cost (Elena's seasonal shape reads as a bill-shock story cleanly).
3. **Engineer a spike month into MARCUS_WEBB_RECORDS** — raise one month (e.g. bump 2025-10 from 340 → 460 kWh) so `|340*STD_RATE + supply − mean11|/mean11 > 0.30` fires. Risk: **this shifts the byte-exact avg from 281.67 → higher, which breaks Marcus's locked $16.90/$30.98 saving fixtures (Phase 11 D-13).** CONTEXT.md explicitly rules this out as a Phase 11 amendment out of scope for Phase 13.
4. **Redefine `detect_bill_shock_pure` to use raw `usage_kwh` instead of projected cost, with an asymmetric anomaly rule** (e.g. `usage_kwh[i] > 1.25 * max(usage_kwh[j] for j != i)`). Still no Marcus month trips a symmetric 25% max-exclusion rule — Marcus maxes at 340 kWh with next-highest 325 (ratio 1.046). Would require re-designing the anomaly semantics entirely. Does not help.

**Recommendation to planner:** Halt at Wave 0 of planning until the user picks option 1, 2, or the "engineer Marcus spike + amend Phase 11" path (option 3, which re-opens a frozen fixture and reruns Phase 11 verification). All three rewrite D-03, D-16, D-20, D-29 and possibly CUST-002's demo narrative. The rest of Phase 13 (tools, extractor, cap, UI, prewarm gate) is executable once the target persona + threshold is pinned.

**The rest of this document stands regardless of which pivot the user picks** — it also surfaces a second structural blocker (Strands `max_iterations` does not exist on `Agent` in 1.37.0) that planning must resolve even if Marcus is retargeted.

---

## Summary

Two load-bearing findings collapse CONTEXT.md assumptions:

1. **`Agent(max_iterations=4)` is not a Strands 1.37.0 primitive.** The installed `Agent.__init__` has no such parameter. `max_iterations` exists only on `strands.multiagent.swarm.Swarm`, not on the core `Agent`. D-14 must be rewritten. Strands' only native "stop the loop" stop_reasons are `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `content_filtered`, `guardrail_intervened`, `interrupt`, `cancelled`, `checkpoint`. The 4-tool cap has to be implemented by a Strands **hook** (a `HookProvider` counting `AfterToolCallEvent` firings and calling `agent.cancel()` when the budget is exceeded, OR a `BeforeToolCallEvent` hook that sets `event.cancel_tool = "budget exhausted"` on the 5th tool call).
2. **Marcus does not trip the D-03 30% gate** (above blocker).

Four remaining findings give the planner concrete code patterns:

- `agent_result.message["content"]` iteration order is preserved for the reasoning-trace extractor; `toolUse` blocks contain `{name, input, toolUseId}` (exact TypedDict in `strands.types.tools`); `toolResult` blocks contain `{toolUseId, status, content}` with `content: list[ToolResultContent]` where each entry is `{text | json | image | document}`. `_extract_reasoning_trace` can mirror `_extract_lenient_from_agent_result` at `agent/agent.py:238-260` byte-for-byte; the summary formatter parses `toolResult.content[*].json` (happy path) or `json.loads(toolResult.content[*].text)` (fallback).
- `ConcurrentToolExecutor` is Strands' default (installed at `strands/agent/agent.py:349` via `self.tool_executor = tool_executor or ConcurrentToolExecutor()`). Ordering inside `agent_result.message.content` is preserved per the Bedrock message contract — tools appear in the order the model emitted their `toolUse` blocks, independent of execution concurrency. Trace rendering is safe without an explicit sort.
- Warm Bedrock Sonnet 4.6 multi-tool latency in the 2500ms budget is plausible but not proved from repo evidence. Phase 13 must emit a live measurement via D-19 before freeze.
- `boto3.client("cloudwatch").get_metric_statistics(Namespace="AWS/Lambda", MetricName="Invocations", Dimensions=[{"Name": "FunctionName", "Value": TOOLS_LAMBDA_NAME}], StartTime=t0, EndTime=t0+timedelta(seconds=60), Period=60, Statistics=["Sum"])` is the canonical query for D-21. Snippet in §5 below.

**Primary recommendation:** Halt planning at the pivot decision (Marcus / threshold / persona). Once unblocked, plan 4-tool cap as a `HookProvider`, not `max_iterations`. Everything else in CONTEXT.md stands.

---

## Phase Requirements

| ID | Description | Research Support |
|---|---|---|
| AGENT-01 | Bill-shock multi-tool agent flow — 2-3 tool composition, reasoning trace surfaced to UI | §2 (toolUse extraction pattern), §7 (tool registration), §3 (ordering preserved), §6 BLOCKED until persona/threshold fix |
| AGENT-01a | Warm p95 < 2500ms on multi-tool flow; UI-02 <3s contract preserved | §4 (latency evidence — flag as measurement-required), §5 (CloudWatch counter for live sanity) |
| AGENT-01b | 4-tool cap enforced in code, not prompt | §1 (Strands HAS NO `max_iterations` on `Agent`; implement via `HookProvider` counting `AfterToolCallEvent` + `agent.cancel()` or `BeforeToolCallEvent.cancel_tool`) |

---

## Project Constraints (from CLAUDE.md)

- **SAV-03**: LLM never does arithmetic. `detect_bill_shock_pure` must live in Tools Lambda; trace summary strings must be code-composed in Python (D-10), never LLM-generated. [VERIFIED: CLAUDE.md §Critical invariants]
- **REC-03**: Both `green` + `cheapest` always returned; never ranked. Agent system prompt rule 4 must keep "always finish with `simulate_savings`". [VERIFIED: CLAUDE.md]
- **D-04 never-500**: `except Exception` at `agent/agent.py:394-418` catches and stitches fallback. D-15 cap fallback MUST reuse this path. [VERIFIED: agent/agent.py:396-428]
- **D-15 narrative dual-gate**: `validate_usage_narrative` + `validate_call_script` apply to TrackInfo narrative fields ONLY; `reasoning_trace` is EXEMPT (D-11). Counter-pytest required so a future developer does not apply `_reject_forbidden` to summary strings. [VERIFIED: agent/narrative/validators.py via imports at agent/agent.py:30-38]
- **`_narrative_source` marker**: internal — stripped at `api_lambda/handler.py:121`. The new public field `reasoning_trace` is NOT stripped (D-12). [VERIFIED: api_lambda/handler.py:121]
- **API Lambda boto3 `Config(read_timeout=25, connect_timeout=5)`**: DO NOT REMOVE. [VERIFIED: api_lambda/handler.py:39-43]
- **`runtimeSessionId` generated INSIDE `handler()`**: SC-3 preserved; Phase 13 does not touch this code path. [VERIFIED: api_lambda/handler.py:109]
- **`?prewarm=1` returns 204 on success AND failure**: D-04 broad-except pattern. [VERIFIED: api_lambda/handler.py:86-104]
- **`?narrative=off`**: LD-7 kill switch — `ReasoningTrace` imports `NARRATIVE_ENABLED` from `ui/src/lib/flags.ts` and returns `null` when disabled. [VERIFIED: ui/src/lib/flags.ts]
- **Customer-not-found detection**: `if "green" not in body or "cheapest" not in body` at `api_lambda/handler.py:152` — Phase 13 MUST NOT mutate this (Phase 14 territory). [VERIFIED: api_lambda/handler.py:152]
- **Bi-mode imports in `agent/agent.py`**: try container layout (`from narrative.X`) first, fall back to repo layout (`from agent.narrative.X`). New `agent/reasoning/summaries.py` (if modularised) must follow. [VERIFIED: agent/agent.py:26-71]
- **Region hardcoded `us-east-1`**: DO NOT fix this. [VERIFIED: app.py + CLAUDE.md]
- **Frozen lockfiles `--require-hashes`**: zero new deps in Phase 13. [VERIFIED: STACK.md §Summary of v3.0 Stack Deltas — Phase 15 owns the bedrock-agentcore bump, not 13]
- **Bedrock model literal `us.anthropic.claude-sonnet-4-6`**: unchanged. [VERIFIED: agent/agent.py:319]

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|---|---|---|---|
| Bill-shock anomaly arithmetic | Tools Lambda (backend / pure Python) | — | SAV-03 invariant — every arithmetic tool must be pure Python in Tools Lambda, never LLM-estimated. `detect_bill_shock_pure` sits next to `simulate_savings_pure` in `lambda/handler.py`. |
| Tool composition (LLM decides which tools to call) | Agent container (Bedrock AgentCore / Strands) | Tools Lambda (fulfils each tool) | Strands `Agent` loop drives the model; tools executed via `_lambda_client.invoke` against the Phase 12 action dispatcher. System prompt is the only policy (no hardcoded graph — D-09). |
| Reasoning-trace extraction | Agent container (`agent/agent.py` post-call helper) | — | `agent_result.message["content"]` is Strands-internal; the extractor lives where that type is imported. Mirror `_extract_lenient_from_agent_result` pattern. |
| Summary-string composition | Agent container (`agent/reasoning/summaries.py` or inline, D-10) | — | Deterministic Python formatters reading tool-output dicts. SAV-03 by construction. |
| 4-tool-cap enforcement | Agent container — **Strands `HookProvider`** (BeforeToolCallEvent counter) | — | Strands 1.37.0 has NO `Agent(max_iterations=)` parameter. Hook is the only native primitive. Alternative: post-turn `agent.cancel()` driven by a metrics hook. Both run in the agent container process, not in AgentCore infra. |
| D-04 never-500 fallback on cap exhaustion | Agent container (`invoke()` except-branch) | Tools Lambda (direct `simulate_savings` for savings numbers) | Re-use existing `agent/agent.py:396-428` path. Stitch partial `reasoning_trace` collected before the cap fired. |
| `reasoning_trace` public pass-through | API Lambda (no code change beyond tests) | UI (`ReasoningTrace` component) | Pydantic schema at agent; API Lambda is dumb. UI reads response.reasoning_trace and renders. |
| Per-flow prewarm gate | `scripts/prewarm.py` (stdlib CLI) | — | Extends the Phase 9 tooling; CUST-002 multi-tool gate 2500ms, CUST-001 single-tool gate 3000ms. |
| Cross-persona canary | Offline pytest via `_provider_swap` + `InMemoryProvider` | — | Pure-Python determinism; no Bedrock cost. D-20. |
| CloudWatch tool-invocation counter | Smoke-gated pytest (`tests/test_narrative_eval_live.py`) | CloudWatch `AWS/Lambda` `Invocations` metric | Live observability. D-21. |
| UI ReasoningTrace disclosure | UI (React component + vitest) | — | Collapsed by default; tool names only above the fold (D-26). |

---

## Unknown #1: Strands 1.37.0 `max_iterations` exhaustion semantics

**Finding: `Agent(max_iterations=4)` DOES NOT EXIST in Strands 1.37.0.**

Installed `strands.agent.Agent.__init__` signature (full parameter list, verified via `inspect.signature` against `.venv/lib/python3.13/site-packages/strands-agents 1.37.0`):

```
model, messages, tools, system_prompt, structured_output_model,
callback_handler, conversation_manager, record_direct_tool_call,
load_tools_from_directory, trace_attributes, agent_id, name,
description, state, plugins, hooks, session_manager,
structured_output_prompt, tool_executor, retry_strategy,
concurrent_invocation_mode
```

`max_iterations` is absent. Grep confirms `grep -rn max_iterations .venv/lib/python3.13/site-packages/strands/agent/` returns NO results. The symbol appears only under `strands/multiagent/swarm.py` as `Swarm(..., max_iterations=20)` — a different class for multi-agent orchestration, not the single-agent loop.

**Strands 1.37.0 `StopReason` literal values** (verified via `typing.get_args(strands.types.event_loop.StopReason)`):

```
'cancelled', 'checkpoint', 'content_filtered', 'end_turn',
'guardrail_intervened', 'interrupt', 'max_tokens',
'stop_sequence', 'tool_use'
```

There is no `"max_iterations"` or `"max_iterations_exceeded"` stop_reason. The closest loop-exhaustion stop_reason is `"max_tokens"`, but that represents token-budget exhaustion inside a single model call, not tool-call count — and Strands raises `MaxTokensReachedException` rather than returning it on `AgentResult.stop_reason` (verified at `strands/event_loop/event_loop.py:175-181`).

**Evidence:**
- `.venv/lib/python3.13/site-packages/strands-agents 1.37.0`
- `strands/agent/agent.py:146-350` — constructor signature
- `strands/agent/agent.py:349` — `self.tool_executor = tool_executor or ConcurrentToolExecutor()` (the default)
- `strands/types/event_loop.py:39-50` — `StopReason` Literal definition
- `strands/event_loop/event_loop.py:167-181` — max_tokens raises `MaxTokensReachedException`, not a stop_reason on AgentResult
- `strands/multiagent/swarm.py:189-204, 243-275` — `max_iterations` lives here only
- Context7 query `"max_iterations iterations cap agent loop"` against `/strands-agents/sdk-python` returned GraphBuilder / Swarm / Cancel results; no `Agent.max_iterations` was surfaced.

**Strands-native mechanisms for capping the loop:**

Option A (RECOMMENDED): **Hook-based counter that cancels the agent.** Pattern from Strands community hooks docs (Context7 `/strands-agents/sdk-python`):

```python
from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

class ToolBudgetHook(HookProvider):
    def __init__(self, budget: int = 4):
        self.budget = budget
        self.used = 0

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(AfterToolCallEvent, self.on_tool_complete)

    def on_tool_complete(self, event: AfterToolCallEvent):
        self.used += 1
        if self.used >= self.budget:
            # agent.cancel() is thread-safe (verified via Context7 docs)
            event.agent.cancel()

_agent = Agent(model=_model, system_prompt=SYSTEM_PROMPT,
               tools=[simulate_savings, detect_bill_shock,
                      get_billing_history, get_hardship_flag],
               hooks=[ToolBudgetHook(budget=4)])
```

After cancellation, `agent_result.stop_reason == "cancelled"` (verified in Context7 cancellation example).

Option B: **Pre-tool-call rejection.** `BeforeToolCallEvent` exposes `event.cancel_tool = "reason"` which short-circuits a specific tool invocation. Counter-based rejection on the 5th call. `stop_reason` may still be `"tool_use"` because the turn completes normally — this does NOT produce a clean terminal signal unless paired with `agent.cancel()`.

Option C: **Post-hoc inspection** — let the agent run, then in `invoke()` count `[b for b in agent_result.message.content if b.get("toolUse")]` after the fact. If > 4, route through D-04 fallback. Loose but simple; no runtime cancellation.

**Planning implication — THIS REWRITES D-14 AND D-15:**

- D-14 cannot reference `Agent(max_iterations=4)`. The planner must pin either Option A (clean — recommended) or Option C (simplest).
- D-15 routes cap exhaustion through D-04 fallback. With Option A: detect `agent_result.stop_reason == "cancelled"` in `invoke()` happy path AND catch nothing new — cancellation is a normal terminal state, not an exception. Planner adds a branch:

  ```python
  agent_result = _agent(_build_narrative_prompt(customer_id),
                        structured_output_model=RecommendationResponse)
  if agent_result.stop_reason == "cancelled":
      # budget exceeded — route through D-04 fallback
      raise RuntimeError("tool budget exhausted")  # reuses existing except branch
  ```

  OR the except-Exception branch gets a sibling stop_reason-check branch with the same fallback body.

- The D-14 offline pytest (D-16) becomes: construct `ToolBudgetHook(budget=1)`, register it on a test agent with a tail-call fake tool, invoke, assert `stop_reason == "cancelled"` AND response body has all D-15 guarantees (green + cheapest + optional reasoning_trace).

- D-17 (no live smoke) remains correct — Sonnet 4.6 does not naturally emit 5+ tool calls; forcing the cap to fire live is flaky and expensive.

**Escape valve if the user dislikes hooks:** `max_tokens` on the `BedrockModel` indirectly caps thinking-and-tool-calling; Strands raises `MaxTokensReachedException` which bubbles to the existing `except Exception`. But this caps token volume, not tool-call count, so cannot be pinned to exactly 4. Option A is the only clean 4-tool cap.

**Confidence:** HIGH. Source-inspected against installed 1.37.0; cross-validated via Context7.

---

## Unknown #2: Strands toolUse / toolResult block shape and extractor snippet

**Finding: `toolUse` blocks have `{name: str, input: Any, toolUseId: str}`; `toolResult` blocks have `{toolUseId: str, status: "success" | "error", content: list[ToolResultContent]}` where each `ToolResultContent` is a TypedDict with optional keys `text | json | image | document`.**

Verified at `.venv/lib/python3.13/site-packages/strands/types/tools.py:53-101`:

```python
class ToolUse(TypedDict):
    input: Any
    name: str
    toolUseId: str
    reasoningSignature: NotRequired[str]

class ToolResultContent(TypedDict, total=False):
    document: DocumentContent
    image: ImageContent
    json: Any
    text: str

ToolResultStatus = Literal["success", "error"]

class ToolResult(TypedDict):
    content: list[ToolResultContent]
    status: ToolResultStatus
    toolUseId: str
```

`ContentBlock` (`strands/types/content.py:75-100`) is the shape of each entry in `agent_result.message["content"]`. Keys are optional (TypedDict total=False). For Phase 13 the two keys that matter are `toolUse: ToolUse` and `toolResult: ToolResult`. The existing `_extract_lenient_from_agent_result` at `agent/agent.py:238-260` already uses this structure — it iterates `agent_result.message.get("content", []) or []` and checks `block.get("toolUse")`.

**How toolUse and toolResult pair:** each `toolUse` block has a unique `toolUseId`; the matching `toolResult` block in the same message (or a later assistant message) carries the same `toolUseId`. Pairing is by `toolUseId` string equality. The ORDER of `toolUse` blocks in `content[]` reflects the emission order from the model (see §3 for concurrency note).

**Concrete `_extract_reasoning_trace` snippet** — mirroring `_extract_lenient_from_agent_result` (agent/agent.py:238-260):

```python
# agent/agent.py — new helper, place alongside _extract_lenient_from_agent_result

_TRACE_TOOLS = {"detect_bill_shock", "get_billing_history",
                "get_hardship_flag", "simulate_savings"}

def _extract_reasoning_trace(
    agent_result: "AgentResult | None",
) -> list["ReasoningTraceEntry"]:
    """Collect ordered (tool, summary) entries for the reasoning-trace surface (D-08).

    Iterates agent_result.message["content"] collecting every toolUse whose
    name is in _TRACE_TOOLS. For each toolUse, finds the matching toolResult
    (same toolUseId, typically the next content block with a toolResult) and
    composes a deterministic summary via the per-tool formatter (D-10).

    Returns [] on ANY failure (missing content, missing pair, malformed JSON,
    agent_result is None). Never raises.
    """
    if agent_result is None or agent_result.message is None:
        return []

    content_blocks = agent_result.message.get("content", []) or []

    # Build index of toolResult by toolUseId for O(1) pairing.
    tool_results_by_id: dict[str, dict] = {}
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        tool_result = block.get("toolResult")
        if tool_result and isinstance(tool_result, dict):
            tool_use_id = tool_result.get("toolUseId")
            if isinstance(tool_use_id, str):
                tool_results_by_id[tool_use_id] = tool_result

    entries: list[ReasoningTraceEntry] = []
    for block in content_blocks:
        if not isinstance(block, dict):
            continue
        tool_use = block.get("toolUse") or block.get("tool_use")
        if not tool_use:
            continue
        name = tool_use.get("name")
        if name not in _TRACE_TOOLS:
            continue
        tool_use_id = tool_use.get("toolUseId")
        result_block = tool_results_by_id.get(tool_use_id)
        if result_block is None:
            continue
        try:
            # Prefer structured json content; fall back to json.loads(text)
            # (Strands 1.37 may send either depending on tool adapter).
            result_payload = None
            for rc in result_block.get("content", []) or []:
                if "json" in rc:
                    result_payload = rc["json"]
                    break
                if "text" in rc:
                    try:
                        result_payload = json.loads(rc["text"])
                        break
                    except (TypeError, ValueError):
                        continue
            if result_payload is None:
                continue
            summary = _summarise_tool_result(name, result_payload)
            entries.append(ReasoningTraceEntry(tool=name, summary=summary))
        except Exception:  # noqa: BLE001 — best-effort extraction
            continue

    return entries
```

Per-tool summariser `_summarise_tool_result(name, payload)` dispatches to the D-10 formatters in `agent/reasoning/summaries.py`.

**Evidence:**
- `.venv/lib/python3.13/site-packages/strands/types/tools.py:53-101` — ToolUse, ToolResult, ToolResultContent definitions
- `.venv/lib/python3.13/site-packages/strands/types/content.py:75-100` — ContentBlock contains `toolUse: ToolUse` and `toolResult: ToolResult`
- `agent/agent.py:238-260` — existing template (`_extract_lenient_from_agent_result`)

**Planning implication — confirms D-08 contract AND closes a Strands-SDK shape question:** the planner can pin the helper shape exactly as above. Note `ReasoningSignature: NotRequired[str]` on `ToolUse` — deliberately ignored by the extractor; not part of the public `reasoning_trace` surface (D-07).

Note that `tool_use_id` may be `None` on malformed input (TypedDict total=False behaviour); the `isinstance(tool_use_id, str)` check in the index build + the `tool_results_by_id.get(None)` (which returns a dict OR None) handle it cleanly.

**Confidence:** HIGH. TypedDict definitions directly from installed source.

---

## Unknown #3: ConcurrentToolExecutor default behaviour and ordering

**Finding: `ConcurrentToolExecutor` IS the Strands 1.37.0 default on `Agent`. Tool-use block ORDER in `agent_result.message.content` is preserved — the model emits toolUse blocks serially in the message structure even when the executor runs the tools concurrently. No sort required for reasoning-trace rendering.**

Verified at `.venv/lib/python3.13/site-packages/strands/agent/agent.py:63, 146, 349`:

```
Line 63:  from ..tools.executors import ConcurrentToolExecutor
Line 146: tool_executor: ToolExecutor | None = None,
Line 349: self.tool_executor = tool_executor or ConcurrentToolExecutor()
```

So calling `Agent(model=..., system_prompt=..., tools=[...])` without `tool_executor=` gets `ConcurrentToolExecutor()` for free.

**`ConcurrentToolExecutor._execute`** (at `strands/tools/executors/concurrent.py:19-88`) creates one asyncio Task per tool use, feeds results through an `asyncio.Queue`, and yields events in the order they arrive from the queue. That means **execution events** are streamed in completion order, but the resulting `toolResult` content-block ordering in `agent_result.message.content` is determined by the model's message construction — Bedrock's converse API places `toolUse` blocks in the order the model emitted them, and `toolResult` blocks are appended in `tool_results` collection order which matches the `tool_uses` enumeration order (see `tool_uses: list[ToolUse]` parameter at line 26). Net result: the order you see in `content[]` matches the model's intent.

**Concurrency level:** unbounded — one asyncio Task per ToolUse, gated only by Python's asyncio scheduler. For Phase 13's 2-3 tool turns, this is fine. No config to set.

**Ordering for the reasoning-trace UI:** iterate `content[]` in file order. If the planner wants to be belt-and-braces, emit entries in first-seen-toolUseId order (which is file order in `content[]`), not completion order. The snippet in §2 above already does this correctly (single forward pass over `content_blocks`).

**Evidence:**
- `strands/agent/agent.py:63, 146, 349` — default executor registration
- `strands/tools/executors/concurrent.py:19-88` — implementation
- `strands/tools/executors/__init__.py:8-12` — exports both `ConcurrentToolExecutor` and `SequentialToolExecutor`
- SUMMARY.md LD-4 and STACK.md §"Stack Patterns by Variant" already confirm "default is concurrent; swap to sequential if rehearsal shows incoherent narrative order"

**Planning implication — confirms D-09 / D-18 / D-20:** Phase 13 plans must NOT set `tool_executor=` on the `Agent(...)` call; the default is correct. If the T-24h rehearsal surfaces narrative-order incoherence (D-09 ordering rule reads oddly because tools completed out of model-intent order), the escape valve is `tool_executor=SequentialToolExecutor()` (not `max_iterations` or any other primitive).

**Confidence:** HIGH. Installed source + Context7 docs + SUMMARY.md cross-reference.

---

## Unknown #4: Bedrock Sonnet 4.6 multi-tool warm latency

**Finding: No empirical latency evidence exists in the repo for 2-3-tool turns on `us.anthropic.claude-sonnet-4-6` + `bedrock-agentcore` runtime. PITFALLS.md C1 provides a training-knowledge estimate: single-tool warm baseline ~2s v2.0, multi-tool overhead ~800-1200ms per extra tool, three tools projected ~3.5-4.4s warm. 2500ms multi-tool gate has NO headroom under that estimate. The D-18 gate is tight; Phase 13 MUST measure before declaring AGENT-01a green.**

**Quantitative context from PITFALLS.md C1 (training-knowledge, not measured):**

> Sonnet 4.6 typical tool-use overhead is ~800-1200ms *per additional tool turn* once input/output tokens + model "think" time is totalled. Three tools in one turn = roughly +1.6-2.4s vs the single-tool v2.0 baseline. v2.0 warm median was ≲2s; v3.0 with three tools lands at ~3.5-4.4s warm median — a silent UI-02 regression.

**v2.0 observed baselines** (from prewarm.py `MEDIAN_GATE_MS = 3000`): warm median for the single-tool v2.0 path passes at < 3000ms consistently in rehearsal (Phase 9 SC-2). Beyond this, the repo has no measured p95 for multi-tool flows.

**Why the 2500ms budget is tight-but-plausible:**

- v2.0 single-tool warm median ≈ ~1800-2200ms observed (inferred from 3000ms gate passing).
- Per-tool extra cost depends on model input size: summaries of D-10 outputs add ~50-100 tokens of tool-result input to the next turn, which is cheap (~50-100ms extra at Sonnet 4.6 streaming rate).
- Strands `ConcurrentToolExecutor` parallelises the tool invocations themselves (D-02 Phase 12 dispatcher is a single Lambda; all three actions land in one warm Lambda container) — but the MODEL TURNS are still sequential (model-emits-toolUse → tool-runs → model-reads-result → model-emits-next-toolUse-or-final). The "concurrent" in ConcurrentToolExecutor refers to *within* one toolUse emission when the model emits multiple toolUse blocks in one message (parallel tool-use). For the preference-ordered graph in D-09 (hardship → detect_bill_shock → billing_history → simulate_savings), the model likely emits each tool in a separate turn — so parallel execution does not reduce end-to-end latency much.
- Bedrock Sonnet 4.6 streaming TTFT on warm path: ~200-400ms. Steady-state tokens: ~60-100 tps. A 3-tool turn with ~500 tokens of intermediate prompt expansion per turn = ~5-8s total model time — BUT modern agent runtime amortises this.

**Training-knowledge estimate vs 2500ms gate:**

- Best case (1 extra tool, 800ms overhead): 1800 + 800 = 2600ms — **fails gate**.
- Worst case (3 extra tools, 3600ms overhead): 1800 + 3600 = 5400ms — **fails gate by 3×**.

**The D-18 gate at 2500ms has no engineering headroom against PITFALLS.md's projections.** Mitigations available if rehearsal measurement fails:

1. **Constrain to 2 tools** on CUST-002 (e.g. `detect_bill_shock` + `simulate_savings` only; skip `get_billing_history` unless rep asks). Cuts one turn.
2. **Provisioned Concurrency on Tools Lambda** — CONTEXT.md notes PC via `-c demo_pc=1` is already on the API Lambda; extend to Tools Lambda. Saves ~300-500ms of cold-start-on-first-tool.
3. **Tighter tool-result payload** — D-10 summary strings are already deterministic, but the `toolResult.content[*].json` sent back to the model carries the full `{is_shock, delta_dollars, shock_month, mean_dollars, current_dollars}` dict — all 5 fields are needed. No cheap win.
4. **Swap ConcurrentToolExecutor → SequentialToolExecutor** is a latency REGRESSION (serialises tools further), not a win.
5. **Move D-18 gate from warm-median to warm-p50** on 5-sample runs (current prewarm.py measures p50/median over 3 samples already); keep a separate p95 observation but do not gate on it. This is a measurement-reporting change, not a latency change.

**Planning implication — PROTECT AGENT-01a WITH AN EARLY REHEARSAL:**

- Before Wave N of implementation, the planner should schedule a "sighting shot" — deploy `detect_bill_shock` + tool registration + 4-tool-cap hook + run `scripts/prewarm.py` against CUST-002 5× and report warm median. If median > 2500ms, fall back to mitigation 1 (2-tool CUST-002 flow). If median < 2500ms, proceed.
- D-19 latency-floor witness test (`> 1000ms`) is a LOWER bound — for SAV-03/C5 fabrication detection. AGENT-01a is an UPPER bound (< 2500ms). Both must hold simultaneously.
- Document the headroom assessment in the plan: "LD-4 target is 2500ms; realistic training-knowledge estimate suggests 2600-5400ms; measurement required; mitigation 1 (drop to 2-tool flow) is the break-glass."

**Confidence:** MEDIUM. No live measurements exist; training-knowledge projections are directional only. HIGH confidence the gate is tight, LOW confidence the gate is achievable without mitigation.

---

## Unknown #5: CloudWatch `AWS/Lambda` Invocations metric for the Tools Lambda over a 30-second window

**Finding: `boto3.client("cloudwatch").get_metric_statistics(...)` is the canonical query. Snippet below is the drop-in for `tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked` per D-21.**

**Tools Lambda FunctionName resolution:** CDK deploys the Tools Lambda in `CustomerTariff` stack; its physical name is injected into SSM as `/customer-tariff/tools-lambda-name` (or equivalent — verify at planning time). Prewarm/smoke tests can read it from an env var `TOOLS_LAMBDA_NAME` at test time (add to the live smoke rig), or via `boto3.client("ssm").get_parameter(Name="/customer-tariff/tools-lambda-name")`.

**Snippet (D-21, smoke-gated pytest):**

```python
# tests/test_narrative_eval_live.py — add under the existing pytestmark

import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import boto3
import pytest
import requests


@pytest.mark.smoke
def test_agent01_tools_actually_invoked():
    """D-21: assert Tools Lambda was invoked >= 2 times during a CUST-002 lookup.

    Zero invocations in the window = LLM fabricated tool output (C5 regression).
    The >= 2 threshold allows for hardship_flag + simulate_savings minimal path
    while still catching fabrication (where the count would be 0 or 1).
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")
    tools_lambda_name = os.environ.get("TOOLS_LAMBDA_NAME")
    if not tools_lambda_name:
        # Fallback: SSM lookup
        ssm = boto3.client("ssm", region_name="us-east-1")
        tools_lambda_name = ssm.get_parameter(
            Name="/customer-tariff/tools-lambda-name"
        )["Parameter"]["Value"]

    # Record window start BEFORE the agent invocation.
    t0 = datetime.now(timezone.utc)

    # Fire CUST-002 lookup.
    response = requests.get(
        f"{backend_api_url}/recommendations/CUST-002",
        timeout=30,
    )
    assert response.status_code == 200

    # CloudWatch metrics lag ~60-90s after emission. Wait.
    time.sleep(90)

    t1 = datetime.now(timezone.utc) + timedelta(seconds=30)

    cw = boto3.client("cloudwatch", region_name="us-east-1")
    metric = cw.get_metric_statistics(
        Namespace="AWS/Lambda",
        MetricName="Invocations",
        Dimensions=[{"Name": "FunctionName", "Value": tools_lambda_name}],
        StartTime=t0,
        EndTime=t1,
        Period=60,  # 60-second granularity
        Statistics=["Sum"],
    )

    total_invocations = sum(point["Sum"] for point in metric["Datapoints"])
    assert total_invocations >= 2, (
        f"Expected >=2 Tools Lambda invocations in window "
        f"[{t0.isoformat()}, {t1.isoformat()}], got {total_invocations}. "
        f"C5 fabrication signature: agent likely skipped real tool calls."
    )
```

**Evidence:**
- AWS boto3 CloudWatchClient `get_metric_statistics` — standard parameters: `Namespace`, `MetricName`, `Dimensions`, `StartTime`, `EndTime`, `Period`, `Statistics`.
- AWS Lambda Invocations metric — `Namespace=AWS/Lambda`, `MetricName=Invocations`, `Dimensions=[{Name: FunctionName, Value: <name>}]` (canonical per AWS Lambda metrics docs).
- Metric publish lag: CloudWatch metric emission for Lambda lags 60-90 seconds post-invocation (empirical AWS ops knowledge); 90-second sleep is the minimum safe wait. For a smoke test this is acceptable.

**Alternative: `get_metric_data`** is more flexible (supports math expressions, multi-metric queries) but requires `MetricDataQueries=[...]` structure — overkill for a single-metric assertion. `get_metric_statistics` is the right tool for Phase 13.

**Planning implication — confirms D-21:** the planner can wire this snippet into the live eval harness as-is. The TOOLS_LAMBDA_NAME env var (or SSM parameter path) needs to be added to the smoke-test environment setup (doc in CLAUDE.md §"Tests" or tests/README.md). The 90s sleep adds to total smoke-suite runtime; acceptable for `pytest -m smoke` which already requires a deployed stack.

**IAM requirement:** the test-runner credentials need `cloudwatch:GetMetricStatistics` on the Tools Lambda. `cevo-dev25` profile likely already has this (demo account); verify at planning time. If not, add to developer IAM attached policy (not the deployed Lambda role — this is a test-runner concern, not a prod-path concern).

**Confidence:** HIGH. boto3 signatures are stable; AWS Lambda Invocations metric is canonical.

---

## Unknown #6: 30% bill-shock threshold against MARCUS_WEBB_RECORDS

**Finding: MARCUS_WEBB_RECORDS does NOT trip the D-03 30% symmetric threshold on any month. Blocker.**

Computation against the existing Phase 11 fixture `_MARCUS_USAGE = [250, 235, 265, 280, 300, 320, 340, 325, 305, 275, 255, 230]` (12 months, April 2025 → March 2026; supply charge `1.10 * 30.44 = $33.484/mo`, STD rate `0.32 $/kWh`):

| Month | usage_kwh | Projected STD cost | mean of other 11 | \|delta\|/mean | Trips 0.30? |
|---|---|---|---|---|---|
| 2025-04 | 250 | $113.48 | $124.54 | 0.0888 | No |
| 2025-05 | 235 | $108.68 | $124.97 | 0.1304 | No |
| 2025-06 | 265 | $118.28 | $124.10 | 0.0469 | No |
| 2025-07 | 280 | $123.08 | $123.67 | 0.0047 | No |
| 2025-08 | 300 | $129.48 | $123.08 | 0.0520 | No |
| 2025-09 | 320 | $135.88 | $122.50 | 0.1092 | No |
| 2025-10 | **340** | **$142.28** | **$121.92** | **0.1670** | **No (MAX)** |
| 2025-11 | 325 | $137.48 | $122.36 | 0.1236 | No |
| 2025-12 | 305 | $131.08 | $122.94 | 0.0663 | No |
| 2026-01 | 275 | $121.48 | $123.81 | 0.0188 | No |
| 2026-02 | 255 | $115.08 | $124.39 | 0.0748 | No |
| 2026-03 | 230 | $107.08 | $125.12 | 0.1442 | No |

Maximum ratio = 0.167 on 2025-10 (Marcus's summer peak). **45% short of the 0.30 gate.**

Under every reasonable interpretation of "most recent month" in D-03 — whether `billing_history[0]` (the fixture's oldest entry — 2025-04 April, since `_record` stores in fiscal-year order and `get_billing_history` sorts ASC by month), or `billing_history[-1]` (the semantically-most-recent — 2026-03 March), or any month in the 12-month window — the 30% gate stays silent.

**Evidence:**
- `infrastructure/seed_data/billing_records.py:88-93` — `_MARCUS_USAGE` definition + assertion `sum(_MARCUS_USAGE) / 12 == 281.67` (via the cost computation)
- Inline computation verified by Python subprocess (see RESEARCH BLOCKED section top).
- `_record("CUST-002", m, u)` uses `plan_id="STD"` and no `export_kwh`/`peak_kwh`/`offpeak_kwh` overrides — cost projection matches the flat-rate default branch in `simulate_savings_pure` (`avg_kwh * rate_per_kwh + supply`, at `lambda/handler.py:112`).
- `get_billing_history` at `lambda/handler.py:166-182` sorts ASC by month and filters PROFILE — so `billing_history[0]` = 2025-04 (April 2025, OLDEST) and `billing_history[-1]` = 2026-03 (March 2026, NEWEST). CONTEXT.md D-03 uses phrasing "most recent month's projected cost" which is semantically the NEWEST month — but neither interpretation trips.

**Cross-persona scan (same computation on other engineered fixtures):**

- Sarah (500 kWh avg): 2025-10 max ratio 0.2298 — No.
- **Elena (233 kWh avg, seasonal shape)**: 2025-10 max ratio **0.6344**; 7 of 12 months trip the 30% gate. Elena already has "bill-shock shape" built into Phase 11.
- CUST-004 Solar: 2025-08 max ratio 0.2497 — No.
- CUST-005 EV: 2025-08 max ratio 0.1228 — No.
- CUST-006 Hardship: 2025-08 max ratio 0.1084 — No.

**Only Elena CUST-003's fixture already exhibits true bill-shock shape. Marcus CUST-002, CUST-004, CUST-005 are engineered to be smooth; Sarah CUST-001 rises to 23% and CUST-006 is flat.**

**Planning implication — HALT at planning step "persona/threshold pin".** The planner cannot proceed to:
- D-03 threshold pytest fixture (the pin depends on which persona + which threshold).
- D-16 offline pytest asserting CUST-002 `is_shock=True`.
- D-20 cross-persona canary (CUST-002 shock vs CUST-004 non-shock — but CUST-002 doesn't shock, so the asymmetry is absent).
- D-29 UI mock byte-exact MOCK_REASONING_TRACE_CUST002 (the trace content depends on `is_shock=True`).

**Four user-resolvable pivots** (listed in RESEARCH BLOCKED header above). **Recommendation: Option 2 (reassign to Elena CUST-003)** — cleanest engineering (no fixture edits), low narrative cost (Elena's seasonal shape IS the bill-shock story a call-centre agent would narrate), preserves Phase 11 byte-exact Marcus savings. Second-best: Option 1 (retune threshold to ~0.12 symmetric) — tightens every downstream pytest but keeps CUST-002 as the designated persona. Option 3 engineers a Marcus spike and re-opens Phase 11 — reject unless the user explicitly wants this because it shifts locked Marcus savings. Option 4 redesigns the anomaly semantics — premature until the user confirms the intent.

**Confidence:** HIGH. Source-inspected; deterministic Python math; every interpretation exhausted.

---

## Unknown #7: Strands `@tool` + `Agent(tools=[...])` + `_lambda_client.invoke` pattern for the three new tools

**Finding: The existing `simulate_savings` @tool at `agent/agent.py:265-280` is the exact template. Module-level `@tool` function that calls `get_provider().simulate_savings(...)`. The three new tools mirror this: module-level `@tool` functions that call `_lambda_client.invoke(...)` directly with the Phase 12 action-dispatcher payload. No async coloring required; `@tool` supports sync functions; the concurrent executor wraps them in `asyncio.to_thread`-equivalent handling.**

**Existing pattern (verified at `agent/agent.py:265-280`):**

```python
@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.
    ...
    """
    return get_provider().simulate_savings(customer_id)
```

The `@strands.tool` decorator (imported `from strands import Agent, tool` at `agent/agent.py:16`) converts the function into a `ToolSpec` + registration entry. The decorator supports sync callables, async callables, or AsyncGenerator tools. Sync is fine — Strands handles threading internally.

**Direct `_lambda_client.invoke` vs provider routing:** the Phase 12 D-02 action dispatcher at `lambda/handler.py:195-230` already routes `{"action": "detect_bill_shock", "customer_id": ...}`, `{"action": "get_billing_history", "customer_id": ...}`, and `{"action": "get_hardship_flag", "customer_id": ...}` (get_billing_history and get_hardship_flag already exist per Phase 12; Phase 13 adds only the `"detect_bill_shock"` branch and the `detect_bill_shock_pure` helper).

Two valid choices (both in CONTEXT.md §Claude's Discretion):

Option A — direct `_lambda_client.invoke` (matches the pre-Phase-12 simulate_savings wrapper style):

```python
@tool
def detect_bill_shock(customer_id: str) -> dict:
    """Detect bill-shock anomaly.
    ...
    """
    resp = _lambda_client.invoke(
        FunctionName=_TOOLS_LAMBDA_ARN,
        InvocationType="RequestResponse",
        Payload=json.dumps({
            "action": "detect_bill_shock",
            "customer_id": customer_id,
        }).encode(),
    )
    return json.loads(resp["Payload"].read())
```

Option B — route through the `CustomerDataProvider` Protocol. Would require extending the Protocol from 3 methods to 4 (add `detect_bill_shock`) — violates LD-5 which pins the Protocol at exactly 3 methods.

**Recommendation: Option A.** Keeps LD-5 clean; matches the pre-Phase-12 direct-invoke pattern that `simulate_savings` used before it was routed through the provider. CONTEXT.md D-01/D-03 also lean this direction (Protocol stays compact).

**Interaction with Strands' async tool executor:** sync functions in `@tool` are run via `asyncio.to_thread()` inside `ConcurrentToolExecutor._task` (implicit — look at `strands/tools/executors/_executor.py::ToolExecutor._stream_with_trace` which invokes the tool). A synchronous `_lambda_client.invoke(...)` blocks its thread but does NOT block the asyncio event loop. In Phase 13's case this is irrelevant because tools are typically called one-at-a-time per turn (sequential turns), but if Sonnet 4.6 emits two `toolUse` blocks in one message the two Lambda invocations run in parallel threads. No additional configuration.

**Retry + timeout interaction with boto3 Config(read_timeout=25):** the existing `_lambda_client = boto3.client("lambda", region_name=_REGION)` at `agent/agent.py:80` has NO timeout override. Default boto3 lambda read_timeout is 60 seconds — fine for Tools Lambda which responds in <200ms on warm path. The 25s Config override lives on `api_lambda/handler.py:39-43` (the `bedrock-agentcore` client invoking the agent runtime) — do not conflate. Phase 13 does not change `_lambda_client`'s configuration.

**Bi-mode import for `agent/reasoning/summaries.py` (if modularised per D-10 discretion):**

```python
# agent/agent.py — under the existing narrative bi-mode block
try:
    from reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )
except ImportError:  # pragma: no cover — repo layout
    from agent.reasoning.summaries import (
        summary_detect_bill_shock,
        summary_get_billing_history,
        summary_get_hardship_flag,
        summary_simulate_savings,
    )
```

Container side needs `Dockerfile` `COPY agent/reasoning /app/reasoning` alongside the existing `COPY agent/narrative /app/narrative` and `COPY agent/providers.py /app/providers.py` lines. Verify Dockerfile update is in the plan if the planner chooses modularisation.

**Tool registration in the Agent singleton:**

```python
# agent/agent.py:323-327 — extend tools list + add hooks
_agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[
        simulate_savings,
        detect_bill_shock,
        get_billing_history,
        get_hardship_flag,
    ],
    hooks=[ToolBudgetHook(budget=4)],  # §1 finding — replaces max_iterations=4
)
```

The `@tool`-decorated functions are passed directly (they are `FunctionalTool` or callable specs at this point; Strands `Agent` accepts decorated functions in `tools=[...]`).

**Evidence:**
- `agent/agent.py:265-280` — template @tool
- `agent/agent.py:16` — `from strands import Agent, tool`
- `agent/agent.py:80-83` — `_lambda_client` + `_provider` module-level singletons
- `lambda/handler.py:195-230` — Phase 12 action dispatcher (routes the 3 new tools' payloads)
- `strands/agent/agent.py:63, 349` — default `ConcurrentToolExecutor`

**Planning implication — confirms D-01 pattern:** 3 new `@tool` functions, module-level, direct `_lambda_client.invoke`, payload shape `{"action": "<name>", "customer_id": customer_id}`. No Protocol expansion. Bi-mode pattern applies to `agent/reasoning/summaries.py` IF modularised.

**Confidence:** HIGH.

---

## Standard Stack

All carried forward from Phase 11 + Phase 12 — zero new Python dependencies this phase.

| Library | Version | Purpose | Why Standard |
|---|---|---|---|
| `strands-agents` | 1.37.0 (pinned; do NOT bump this phase per D-22) | Multi-tool agent loop, @tool decorator, hooks for budget cap | Existing stack; Phase 06.1 validated against Sonnet 4.6 |
| `bedrock-agentcore` | 1.6.3 (pinned; bump to 1.6.4 lives in Phase 15 per STACK.md §Summary) | Runtime primitives, BedrockAgentCoreApp entrypoint | Existing |
| `pydantic` | v2.x via strands-agents | `ReasoningTraceEntry` + extended `RecommendationResponse` | Existing |
| `boto3` | 1.42.96 | CloudWatch GetMetricStatistics (D-21) + Lambda invoke (§7) | Existing |
| React 18 + Vite + shadcn/ui | Per `ui/package.json` | `ReasoningTrace` component | Existing; compose from `Card`, `Button` primitives; no new shadcn components |
| `vitest` | Existing | `ReasoningTrace.test.tsx` | Existing |
| `pytest` | Existing | Offline tests + smoke tests | Existing |

**Version verification:**
- `strands-agents==1.37.0` verified via `importlib.metadata.version('strands-agents')` → `1.37.0` [VERIFIED: local venv]
- Phase 13 ships ZERO new dependencies [CITED: CONTEXT.md §Out of scope; STACK.md §Summary]

---

## Architecture Patterns

### System Architecture Diagram (AGENT-01 dataflow)

```
UI (LookupForm) → React fetch /recommendations/{CUST-002}
                         │
                         ▼
  API Gateway HTTP API v2 → API Lambda (runtimeSessionId=uuid4(), unchanged)
                                    │
                                    ▼
              bedrock-agentcore.invoke_agent_runtime
                                    │
                                    ▼
        Agent container (Strands 1.37 + Sonnet 4.6)
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
      @tool get_hardship_flag   @tool detect_bill_shock   @tool simulate_savings
                 │                  │                  │
                 └──────────────────┼──────────────────┘
                                    │  each tool → _lambda_client.invoke
                                    ▼
              Tools Lambda (handler.py::handler action dispatcher)
                                    │
                 ┌──────────────────┼──────────────────┐
                 ▼                  ▼                  ▼
           get_hardship        detect_bill_shock    simulate_savings
           _flag_pure           _pure (NEW)           (existing)
                                    │
                                    ▼
                              DynamoDB (tariff-billing)

Back through the agent:
Agent loop collects agent_result.message.content[].toolUse blocks
                                    │
                                    ▼
           ToolBudgetHook(budget=4) — if used >= 4 → agent.cancel()
                                    │
                                    ▼
     _extract_reasoning_trace(agent_result) → list[ReasoningTraceEntry]
                                    │
                                    ▼
            RecommendationResponse { green, cheapest,
                                      reasoning_trace: [..] }
                                    │
                                    ▼
                       API Lambda pass-through UNCHANGED
                                    │
                                    ▼
                   UI ReasoningTrace (collapsed above cards)
```

### Recommended Project Structure (additions to existing layout)

```
agent/
├── agent.py                    # MODIFY — 3 new @tools + ToolBudgetHook + _extract_reasoning_trace + ReasoningTraceEntry
├── reasoning/
│   ├── __init__.py             # NEW (if modularised; D-10 discretion)
│   └── summaries.py            # NEW — 4 deterministic formatters
├── narrative/                  # NO CHANGE
└── providers.py                # NO CHANGE (Protocol stays 3 methods)

lambda/
├── handler.py                  # MODIFY — add "detect_bill_shock" action branch + detect_bill_shock_pure
├── tariff_plans.json           # NO CHANGE
└── ...

api_lambda/
└── handler.py                  # NO CHANGE (reasoning_trace passes through; body.pop strips only _narrative_source)

ui/src/
├── components/
│   ├── ReasoningTrace.tsx      # NEW
│   └── ReasoningTrace.test.tsx # NEW
└── lib/
    ├── flags.ts                # NO CHANGE (NARRATIVE_ENABLED imported by ReasoningTrace)
    ├── mock/recommendations.ts # MODIFY — add MOCK_REASONING_TRACE_CUST002 + reasoning_trace: [] on others
    └── types.ts                # MODIFY — add ReasoningTraceEntry + extend RecommendationResponse

scripts/
└── prewarm.py                  # MODIFY — per-flow gate + CUST-001/002 rotation

tests/
├── test_bill_shock_flow.py     # NEW — D-03 detect_bill_shock_pure, D-16 cap, D-20 cross-persona canary
├── test_narrative_eval_live.py # MODIFY — D-19 latency floor + D-21 CloudWatch counter
└── test_api_lambda.py          # MODIFY — reasoning_trace pass-through assertion
```

### Pattern 1: Strands hook-based tool budget (NEW — replaces "max_iterations" in CONTEXT.md D-14)

**What:** `HookProvider` counting `AfterToolCallEvent` firings; calls `agent.cancel()` when the budget is exceeded.
**When:** Whenever the agent needs a hard cap on tool-call count that isn't surfaced via a constructor parameter.
**Example:** See §1 snippet above.
**stop_reason:** `"cancelled"` after budget exhaustion (verified via Context7 cancellation example).

### Pattern 2: Reasoning-trace extraction from `agent_result.message.content`

**What:** Iterate `content_blocks`, index `toolResult` by `toolUseId`, pair `toolUse` with its result, compose deterministic summary.
**When:** Phase 13 `_extract_reasoning_trace` — runs after `_agent(...)` returns and before `model_dump()`.
**Example:** See §2 snippet above — drop-in.

### Pattern 3: Action dispatch on Tools Lambda (existing — Phase 12 D-02)

**What:** Single Lambda with `event["action"]` dispatcher; pure helpers co-located; ONE IAM grant, ONE cold-start surface.
**Phase 13 extension:** add one branch — `"detect_bill_shock"` — calling `detect_bill_shock_pure(get_billing_history(...))` with `_validate_customer_id` upfront.

### Pattern 4: Per-flow prewarm gate with 0/1/2 exit taxonomy (Phase 9 pattern + per-flow aggregation)

**What:** `scripts/prewarm.py` extends from single 3000ms gate to per-flow gates; exit 0 only if ALL flows pass.
**D-18 specifics:** 3000ms single-tool (CUST-001) + 2500ms multi-tool (CUST-002) — exit 0 iff both pass.
**Strict exit taxonomy preserved:** 0 = all under gate, 1 = any gate fails OR HTTP error, 2 = setup error (missing env var, unreachable endpoint on first call).

### Anti-Patterns to Avoid

- **Setting `max_iterations=4` on `Agent(...)`:** silent no-op — Strands 1.37.0 ignores unknown kwargs after Python pydantic-style init, OR raises TypeError depending on whether a catch-all accepts extras. The repo's existing `Agent(model=_model, system_prompt=SYSTEM_PROMPT, tools=[simulate_savings])` call succeeds today; adding `max_iterations=4` will either fail at container startup or silently do nothing. Either way, the 4-tool cap is absent. Use the `HookProvider` pattern from §1.
- **Sorting `content[]` by timestamp or completion order:** the message block order is already correct for UI rendering. Don't re-sort.
- **Routing the 3 new tools through `CustomerDataProvider` Protocol:** violates LD-5 (Protocol stays 3 methods). Use direct `_lambda_client.invoke` in each @tool wrapper (§7 Option A).
- **Applying `_reject_forbidden` / `validate_usage_narrative` / `validate_call_script` to `reasoning_trace.summary`:** the trace contains digits + `$` + dates + `%` BY DESIGN (D-11 exemption). A future developer will read CLAUDE.md's D-15 rule and "fix" the trace by applying validators — catastrophic silent regression. Mitigation: a pytest that asserts a sample `reasoning_trace` entry contains `"$"` AND passes unchanged through the agent/API/UI pipeline, specifically labelled "D-11 exemption — do not apply narrative validators to reasoning_trace."
- **Mutating `api_lambda/handler.py:152` customer-not-found detection:** Phase 14 territory. Phase 13 must leave it alone and add a pytest asserting the contract holds with a `reasoning_trace`-bearing body.
- **Streaming (SSE) the reasoning-trace:** breaks `Config(read_timeout=25)`. Buffer + return in one JSON body (D-07 already locks this).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| 4-tool cap | `if tool_calls_count >= 4: return {...}` inline inside a tool function | `HookProvider` counting `AfterToolCallEvent` + `agent.cancel()` (§1) | Strands-native cancellation returns `stop_reason="cancelled"` cleanly; inline logic re-implements what hooks exist for and can't cancel mid-stream. |
| Reasoning-trace extraction | Custom iteration of `agent_result.message["content"]` with your own TypedDict types | Mirror `_extract_lenient_from_agent_result` pattern + use `strands.types.tools.ToolUse/ToolResult` TypedDicts directly | Shape and iteration contract already in use; drift here = silent trace rendering bug. |
| Tool-invocation observability for C5 fabrication detection | Counting tool calls from agent-side log scraping | CloudWatch `AWS/Lambda` `Invocations` metric via `get_metric_statistics` | Canonical service metric; robust to log format changes; independent observation surface. |
| Per-flow prewarm median | Ad-hoc p50 computation in bash | Extend Python `scripts/prewarm.py` with `statistics.median` (already used at line 109) | Stdlib-only; preserves 0/1/2 exit taxonomy. |
| Trace summary composition | LLM-generated summary strings (ask the model to "describe what each tool returned") | Deterministic Python formatters in `agent/reasoning/summaries.py` (D-10) | SAV-03 extension — numbers cannot come from the model, so neither can narrative framing of those numbers. |
| Cross-persona fabrication detection | Eyeballing live demo output | Offline pytest asserting byte-exact difference of `reasoning_trace` summaries between CUST-002 and a non-shock persona (D-20) | Phase 06.1 lived-experience pattern; catches model-behaviour drift cheaply. |

**Key insight:** The temptation in this phase is to "just wrap" everything in custom code. Strands 1.37 already provides hook-based budgeting, structured agent_result inspection, and cancellation. Boto3 already provides CloudWatch metric queries. The repo already provides the D-04 fallback path, the Phase 12 action dispatcher, and the per-persona fixture pattern. Phase 13 adds ONE new pure helper (`detect_bill_shock_pure`), THREE new @tool wrappers, ONE new extractor, ONE new UI component, and ONE new hook. Everything else is extension of existing primitives.

---

## Runtime State Inventory

Phase 13 is greenfield additions + targeted extensions to frozen infrastructure. The only runtime-state considerations:

| Category | Items Found | Action Required |
|---|---|---|
| Stored data | None — no DynamoDB schema changes (the new `detect_bill_shock` action reads existing billing records). `PROFILE` rows already exist from Phase 11. | None. |
| Live service config | Stack policies on `CustomerTariff`, `CustomerTariffAgent`, `CustomerTariffApi` are set via `aws cloudformation set-stack-policy`; they're NOT tracked in CDK synth output, so re-apply discipline is manual (CONTEXT.md D-32). Two files per stack already exist at `infrastructure/stack-policies/{stack}-allow-all.json` and `{stack}-freeze.json`. | Lift all three stacks, deploy, re-apply deny-Update:* by byte-comparing against the freeze JSON (CONTEXT.md D-32 / D-33). |
| OS-registered state | None — no Windows Task Scheduler, no pm2, no launchd. AgentCore microVM routing is managed by AWS. | None. |
| Secrets / env vars | `TOOLS_LAMBDA_ARN` (agent container env) — reused by new @tools. `TABLE_NAME` (Tools Lambda) — reused by `detect_bill_shock_pure`. No new env vars. | None — verify CDK injection still wires both envs after Tools-Lambda asset rebuild + container rebuild. |
| Build artifacts / installed packages | Tools Lambda asset is zipped from `lambda/` on every `cdk deploy CustomerTariff` — rebuild automatic. Agent container image is rebuilt from Dockerfile on every `cdk deploy CustomerTariffAgent` — rebuild automatic. If `agent/reasoning/` is added, Dockerfile MUST gain `COPY agent/reasoning /app/reasoning`. | Update Dockerfile if `agent/reasoning/` exists. Verify via pre-deploy bi-mode container smoke: `docker run --rm --entrypoint python <image> -c 'from reasoning.summaries import summary_simulate_savings; print("OK")'`. |

---

## Common Pitfalls (Phase 13-specific — extends PITFALLS.md C1, C5, C6, M4, M5)

### Pitfall 1: Latency gate breached silently because v2.0 prewarm script still runs

**What goes wrong:** Phase 13 adds per-flow gates to `scripts/prewarm.py` (D-18). If the plan extends the script but leaves the v2.0 global 3000ms gate default for multi-tool, CUST-002 passes at 2800ms (which fails LD-4 2500ms gate). Rehearsal script outputs "all personas under gate — exit 0" — false positive.
**Why it happens:** MEDIAN_GATE_MS at `scripts/prewarm.py:31` is a module-level constant; replacing it in-place makes sense at first glance.
**Prevention:** D-18 pins per-flow gate. Pytest `tests/test_prewarm_script.py` (exists — visible in tests dir) must extend to assert the 2500ms multi-tool gate is active for CUST-002 path. Byte-exact unit test on the gate map.
**Warning signs:** plan carries a single `MEDIAN_GATE_MS` rename; plan does not add a per-persona map; CUST-002 multi-tool warm median > 2500ms but script exits 0.

### Pitfall 2: `max_iterations=4` silently absent because planner copies CONTEXT.md literally

**What goes wrong:** Planner reads D-14 "Cap is `Agent(max_iterations=4)`" and writes a plan that passes `max_iterations=4` to `Agent(...)`. At container runtime, Strands 1.37.0 either raises TypeError or silently ignores it. Either way, the cap is not enforced. Runaway loops possible.
**Why it happens:** CONTEXT.md D-14 reflected a documented primitive that IS NOT IN Strands 1.37.0 (verified in §1 above).
**Prevention:** CONTEXT.md D-14 must be amended during planning to reference the hook-based pattern from §1. Pytest `tests/test_bill_shock_flow.py::test_four_tool_cap_fires_gracefully` must actually register `ToolBudgetHook(budget=1)` and assert `stop_reason == "cancelled"` after a crafted infinite-delegator fake tool fires twice. If this pytest is not present or does not assert `stop_reason`, the cap is unverified.
**Warning signs:** plan references `max_iterations` anywhere in prose; plan's offline pytest does not assert `stop_reason == "cancelled"`; container startup logs show `TypeError: unexpected keyword argument 'max_iterations'`.

### Pitfall 3: `reasoning_trace` tripping D-15 validators because a future developer "tidies" the validators to run on every string field

**What goes wrong:** A later developer (not aware of D-11) generalises `validate_usage_narrative` to apply to all `BaseModel` string fields including `ReasoningTraceEntry.summary`. Summary strings contain `$`, digits, and dates — immediate validator failure. `reasoning_trace` collapses to `[]` on every request. Demo's headline feature silently disappears.
**Why it happens:** D-15 is a load-bearing invariant with strong test coverage; its scope expansion feels like a correctness improvement.
**Prevention:** D-11 counter-pytest in `tests/test_schema.py` or `tests/test_bill_shock_flow.py`: construct a `ReasoningTraceEntry(tool="detect_bill_shock", summary="Bill shock detected: +$47 Dec vs 11-month avg ($135 vs $88)")` and assert it validates cleanly via `.model_validate(...)`. Label the pytest "D-11 EXEMPTION — reasoning_trace summaries intentionally contain digits + currency + dates; DO NOT apply narrative validators here." CLAUDE.md addendum reiterates.
**Warning signs:** plan adds `_validate_summary = validate_call_script` or `_validate_summary = validate_usage_narrative` to `ReasoningTraceEntry`; plan does not add the counter-pytest; PR description says "extending D-15 coverage to reasoning_trace for consistency".

### Pitfall 4: Dockerfile not updated for `agent/reasoning/` module

**What goes wrong:** Planner modularises per D-10, adds `agent/reasoning/summaries.py`, but forgets the Dockerfile. Container startup: `ImportError: No module named 'reasoning'` (container layout) → agent init crashes → all lookups return 500 → D-04 never-500 appears to hold (the `except` does catch it, but the healthy agent path is dead for every request; all persona lookups get fallback).
**Why it happens:** Bi-mode imports make local pytest work even when the Dockerfile is wrong. Offline confidence ≠ container confidence.
**Prevention:** Pre-deploy bi-mode container smoke — `docker run --rm --entrypoint python <image> -c 'from reasoning.summaries import summary_simulate_savings; print("OK")'` as a gate in the plan's deployment wave. Same pattern as Phase 12 D-09 (already precedent).
**Warning signs:** plan adds new `agent/reasoning/` without a Dockerfile diff; plan's deployment wave does not include a bi-mode container smoke; live agent logs post-deploy show ImportError on every invocation.

### Pitfall 5: CloudWatch metric lag causes false-negative on D-21 tool-invocation counter

**What goes wrong:** `get_metric_statistics` returns 0 Datapoints because the test queries less than 60 seconds after the agent call. Assertion `total_invocations >= 2` fails. Tests are red; fabrication is suspected; no fabrication actually occurred.
**Why it happens:** CloudWatch metric emission for Lambda lags 60-90s post-invocation. The 90-second sleep in §5 snippet is the minimum safe wait; if copy-paste shortens it (e.g. to 30s for faster CI), false negatives emerge.
**Prevention:** Keep the `time.sleep(90)` in the D-21 pytest with an inline comment citing CloudWatch 60-90s emission lag. Do not parameterise or shorten without re-verifying. Mark the pytest `@pytest.mark.smoke` so CI cost is bounded.
**Warning signs:** plan tightens the sleep to speed up smoke suite; D-21 pytest is flaky; `total_invocations` fluctuates between 0 and 2.

### Pitfall 6: Stack-policy drift after Phase 13 deploy

**What goes wrong:** CONTEXT.md D-31 says "lift THREE stacks if `cdk diff CustomerTariffApi != 0`". If the planner assumes diff == 0 (because `reasoning_trace` is pass-through) but tests/test_api_lambda.py expansion forces a lambda asset hash change, the API stack is deployed under lifted policy but not re-applied. Freeze silently broken.
**Why it happens:** `cdk diff` output is a signal; diffs come from any asset change including test-adjacent modules if they live inside the asset bundle.
**Prevention:** Run `cdk diff CustomerTariffApi` during planning wave (CONTEXT.md D-31 already specifies). If diff > 0, lift + re-apply + byte-equality gate (D-32, matching v2.0 Phase 10 + Phase 11/12 precedent). If diff == 0, downgrade to 2-stack lift. Post-deploy `aws cloudformation get-stack-policy --stack-name CustomerTariffApi` must byte-equal `infrastructure/stack-policies/backend-api-freeze.json`.
**Warning signs:** plan lifts 2 stacks on faith; no `cdk diff CustomerTariffApi` output in planning evidence; post-deploy `get-stack-policy` returns the allow-all JSON.

---

## Code Examples

Verified patterns from installed Strands 1.37.0 + existing repo:

### Example 1: `_extract_reasoning_trace` helper

See §2 full snippet.

### Example 2: `ToolBudgetHook` + Agent registration

See §1 Option A full snippet.

### Example 3: `detect_bill_shock_pure` structural template

```python
# lambda/handler.py — add next to simulate_savings_pure

def detect_bill_shock_pure(
    billing_history: list[dict],
    *,
    threshold: float = 0.30,  # D-03 — symmetric; pin at planning time to match chosen persona
    rate_per_kwh: float = 0.32,      # STD plan rate, matches seed_data STD_RATE
    daily_supply: float = 1.10,       # STD plan daily supply
) -> dict:
    """Detect bill-shock anomaly on projected cost (SAV-03 compliant — pure Python).

    Algorithm:
      1. Sort billing_history ASC by month (defensive — dispatcher already sorts).
      2. 'current' = last (most recent) month's projected STD cost.
      3. 'mean_11' = mean of the other 11 months' projected STD costs.
      4. 'is_shock' = abs(current - mean_11) / mean_11 > threshold.
    """
    if len(billing_history) < 2:
        raise ValueError("billing_history must have >= 2 months for anomaly detection")

    SUPPLY_MONTH = daily_supply * 30.44
    ordered = sorted(billing_history, key=lambda r: r["month"])
    costs = [float(r["usage_kwh"]) * rate_per_kwh + SUPPLY_MONTH for r in ordered]

    current = costs[-1]  # MOST RECENT month — the one being scrutinised
    reference_mean = sum(costs[:-1]) / len(costs[:-1])
    delta = current - reference_mean
    is_shock = abs(delta) / reference_mean > threshold

    return {
        "is_shock": is_shock,
        "delta_dollars": round(delta, 2),
        "shock_month": ordered[-1]["month"],
        "mean_dollars": round(reference_mean, 2),
        "current_dollars": round(current, 2),
    }
```

### Example 4: `ReasoningTraceEntry` + schema extension

```python
# agent/agent.py — add near RecommendationResponse (around line 116)

class ReasoningTraceEntry(BaseModel):
    tool: str = Field(description="Tool name (e.g. 'detect_bill_shock')")
    summary: str = Field(description="Code-composed summary of the tool result")

    # D-11 EXEMPTION: NO validators on summary — reasoning_trace intentionally
    # contains digits, currency, percentages, dates (that's its value as
    # observability). Applying D-15 narrative validators here is a silent regression.

class RecommendationResponse(BaseModel):
    green: TrackInfo
    cheapest: TrackInfo
    reasoning_trace: list[ReasoningTraceEntry] = Field(default_factory=list)
```

---

## State of the Art

| Old Approach (CONTEXT.md assumption) | Current Approach (Strands 1.37.0 reality) | When Changed | Impact |
|---|---|---|---|
| `Agent(max_iterations=4)` primitive | `HookProvider` counting AfterToolCallEvent + `agent.cancel()` | Strands has not had `Agent.max_iterations` through 1.37.0 (verified); the CONTEXT.md assumption appears to be based on SUMMARY.md LD-4 which conflated `Swarm(max_iterations=...)` with `Agent(...)`. | Rewrite D-14 + D-15 + D-16. Hook-based cap is cleaner but different. See §1. |
| Streaming reasoning-trace via SSE | Buffered return on existing JSON body | STACK.md §"What NOT to Use" rejects SSE for Phase 13 | Already aligned in CONTEXT.md D-07; reaffirmed here. |
| Rep-selected intent via `?flow=bill_shock` | LLM-decides per system-prompt preference order (D-09) | CONTEXT.md D-09 locks this | Already aligned. |

**Deprecated / outdated:**
- `Agent.max_iterations` — never existed on Strands `Agent`; planner must not reference. [VERIFIED via installed source §1]

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | `agent.cancel()` is thread-safe and produces `stop_reason="cancelled"` when called from a hook firing in the tool executor's asyncio thread | §1 | If `agent.cancel()` deadlocks or races with the tool executor, the cap fires but hangs the invocation. Mitigation: the offline D-16 pytest verifies `stop_reason == "cancelled"` terminally — detect at planning time. Context7 docs example uses `agent.cancel()` from a non-hook thread (explicit threading.Thread); hook-thread usage is structurally similar but not separately documented. LOW risk — hooks run in-thread with the executor; `agent.cancel()` sets an asyncio event the executor checks. |
| A2 | The 90-second CloudWatch metric lag is sufficient for Lambda Invocations to be visible in `get_metric_statistics` | §5 | If lag exceeds 90s, D-21 pytest is flaky. Mitigation: pytest retries once after another 30s sleep; if still zero, fail. LOW risk based on AWS ops practice (60-90s is typical, rare outliers to 180s). |
| A3 | Bedrock Sonnet 4.6 warm p95 for a 3-tool turn lands in 2500-5000ms range (not faster) | §4 | If Sonnet 4.6 is markedly faster than training-knowledge estimates, the 2500ms gate passes easily and no mitigation is needed. If markedly slower, mitigation 1 (2-tool CUST-002) is forced. MEDIUM risk — no live measurements in repo. |
| A4 | CONTEXT.md D-03 "most recent month" semantically means billing_history[-1] (NEWEST) after ASC sort | §6 | Interpretation ambiguity. I tested BOTH interpretations + every month in between — NONE trip 0.30 for Marcus. Interpretation does not change the blocker. ZERO risk (already exhausted). |
| A5 | Strands 1.37.0's default ConcurrentToolExecutor preserves model-intent ordering of toolUse blocks in `agent_result.message.content` | §3 | If concurrent execution corrupts order, reasoning-trace renders out-of-order and misleads the rep. Code inspection of `strands/tools/executors/concurrent.py` supports this (task queue emits in completion order but MESSAGE structure is built by the model sequentially). LOW risk — verify during Wave N integration test (render a 3-tool trace and eyeball ordering). |
| A6 | The TOOLS_LAMBDA_NAME SSM parameter exists (or can be added) for D-21 smoke test to resolve the Lambda function name | §5 | If SSM parameter path differs, the snippet needs `grep` of CDK code to find actual injection. LOW risk — `infrastructure/foundation_stack.py` is inspectable at planning time. |

**Planner and discuss-phase should confirm A1 and A3 with the user before Wave N implementation** — A1 affects the cap design, A3 affects whether 2500ms is feasible.

---

## Open Questions (beyond RESEARCH BLOCKED)

1. **Which 4-tool-cap primitive does the user prefer — Option A (hook-cancel, clean stop_reason) or Option C (post-hoc inspection)?**
   - What we know: Strands has no `max_iterations` (§1). Both options work.
   - What's unclear: Option A is Strands-idiomatic; Option C is dead-simple. Option A requires `tests/test_bill_shock_flow.py` to validate cancellation semantics live; Option C requires the same tests to just count `toolUse` blocks.
   - Recommendation: Option A unless the user explicitly wants the simpler path. Both satisfy AGENT-01b "hard cap in code, not prompt".

2. **Should the latency gate (D-18) be hard-gated at 2500ms from day 1 of the phase, or soft-gated (warn, not fail) until the sighting-shot measurement confirms feasibility?**
   - What we know: training-knowledge estimate puts warm p95 at 2600-5400ms (§4). 2500ms has no headroom.
   - What's unclear: whether a 2500ms hard gate on Wave N prewarm causes the wave to fail for non-regression reasons.
   - Recommendation: hard gate from commit 1. If the sighting shot fails, trigger mitigation 1 (2-tool CUST-002) BEFORE merging. Fail-fast beats fail-slow.

3. **Dockerfile update for `agent/reasoning/` — is the module modularised (`agent/reasoning/summaries.py`) or inline in `agent/agent.py`?**
   - What we know: D-10 CONTEXT.md leaves this to planner discretion.
   - What's unclear: modularisation requires Dockerfile COPY + bi-mode imports; inline avoids both.
   - Recommendation: modularise. Future tool additions (Phase 14's hardship rationale, Phase 15's email drafting) will add formatters; a module scales. Pay the one-time Dockerfile cost now.

4. **Does the bill-shock-flow live latency floor witness (D-19) justify a new `pytest -m latency` marker or should it fold into `-m smoke`?**
   - What we know: D-19 asserts `>1000ms` warm latency as C5 fabrication detection.
   - What's unclear: whether multiple latency-floor assertions across future phases (Phase 14 hardship, Phase 15 workflow) will want their own marker.
   - Recommendation: stay with `-m smoke` for Phase 13. If Phase 16 adds more latency-floors and the set grows to >5 tests, split then.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|---|---|---|---|---|
| Python 3.13 | Pytest offline suite + planning-time helper scripts | ✓ (`.venv`) | 3.13 | Use system Python 3.13 directly; requirements-dev.txt pins via `--require-hashes` |
| `strands-agents 1.37.0` | Agent container + tests that import agent.agent | ✓ | 1.37.0 (verified via `importlib.metadata`) | — frozen; any bump requires Phase 06.1-style decimal phase |
| `bedrock-agentcore 1.6.3` | Agent container runtime | ✓ | 1.6.3 | — frozen this phase; Phase 15 bumps to 1.6.4 |
| `boto3 1.42.96` | CloudWatch smoke pytest + agent `_lambda_client` | ✓ | 1.42.96 | — |
| Docker | Pre-deploy bi-mode container smoke (D-10 Phase 12 precedent) | ✓ (existing dev workflow) | — | Run bi-mode smoke in CDK test environment if local Docker absent |
| AWS CLI + `cevo-dev25` profile | Stack-policy lift/apply, CloudWatch metric queries, `cdk deploy` | ✓ (per DEMO-RUNBOOK) | — | — |
| CDK 2.251.0 | All 3 stack deploys | ✓ (per STACK.md) | 2.251.0 | — |
| npm + vitest | UI tests | ✓ (per ui/package.json) | — | — |
| `cdk diff CustomerTariffApi` infrastructure | Phase 13 stack-policy-lift decision (D-31) | ✓ | — | — |
| Deployed `demo-v2.0` baseline | Pre/post byte-equivalence gate (D-33) | ✓ (stable per freeze tag) | demo-v2.0 | — |
| `BACKEND_API_URL` env var at smoke test time | D-19 + D-21 smoke pytests | Requires deployed stack | — | — |
| `TOOLS_LAMBDA_NAME` env var OR SSM parameter `/customer-tariff/tools-lambda-name` | D-21 CloudWatch counter | MAYBE (verify at planning) | — | Derive from `aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`CustomerTariff`)]'` if SSM absent |

**Missing dependencies with no fallback:** None for Phase 13.

**Missing dependencies with fallback:** TOOLS_LAMBDA_NAME SSM parameter may need to be created as part of the phase (small CDK addition) if absent; snippet in §5 falls back to SSM lookup.

---

## Validation Architecture

### Test Framework

| Property | Value |
|---|---|
| Framework | pytest (offline) + vitest (UI) + pytest-smoke-marker (live) |
| Config file | `pytest.ini` (verified; declares `smoke` marker); `ui/vitest.config.ts` (inferred from existing `ui/package.json` scripts) |
| Quick run command | `pytest -m "not smoke"` (offline suite, ~200 tests) |
| Full suite command (phase-gate) | `pytest -m "not smoke"` + `cd ui && npm run test` + `pytest -m smoke` (requires BACKEND_API_URL + TOOLS_LAMBDA_NAME) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| AGENT-01 | `reasoning_trace` has >= 2 entries on multi-tool persona; entries sourced from `toolUse` blocks | offline + live | `pytest tests/test_bill_shock_flow.py::test_reasoning_trace_populated -x` (offline) + `pytest tests/test_narrative_eval_live.py::test_agent01_reasoning_trace_live -m smoke` | ❌ Wave 0 — new file `tests/test_bill_shock_flow.py` |
| AGENT-01 | `reasoning_trace` exempt from D-15 (D-11 counter-pytest) | offline | `pytest tests/test_bill_shock_flow.py::test_reasoning_trace_contains_digits_and_passes_validation -x` | ❌ Wave 0 |
| AGENT-01 | Pre-LLM cross-persona canary: same flow on CUST-002 and CUST-004 produces different trace summaries | offline | `pytest tests/test_bill_shock_flow.py::test_no_fabrication_across_personas -x` (D-20) | ❌ Wave 0 |
| AGENT-01a | Warm p95 < 2500ms multi-tool flow via prewarm gate | live | `BACKEND_API_URL=... python3 scripts/prewarm.py` (per-flow gate) | ✅ (script exists; gate needs extending) |
| AGENT-01a | Latency-floor witness: CUST-002 warm > 1000ms (C5 fabrication detection) | live | `pytest tests/test_narrative_eval_live.py::test_agent01_latency_floor -m smoke` (D-19) | ❌ Wave 0 (extend existing file) |
| AGENT-01a | CloudWatch Tools Lambda Invocations >= 2 during CUST-002 lookup (C5 observability) | live | `pytest tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked -m smoke` (D-21) | ❌ Wave 0 (extend existing file) |
| AGENT-01b | 4-tool cap fires gracefully → `stop_reason == "cancelled"` + HTTP 200 fallback shape | offline | `pytest tests/test_bill_shock_flow.py::test_four_tool_cap_fires_gracefully -x` (D-16) | ❌ Wave 0 |
| AGENT-01 | UI: ReasoningTrace collapsed-by-default with tool names only; empty list renders null | offline UI | `cd ui && npm run test -- ReasoningTrace.test.tsx` (D-30) | ❌ Wave 0 |
| AGENT-01 | UI: `?narrative=off` → ReasoningTrace returns null (LD-7 kill switch) | offline UI | same file, `?narrative=off` cases | ❌ Wave 0 |
| AGENT-01 | UI-01 preserved at 1280×800 with collapsed 3-entry trace | offline UI | `cd ui && npm run test -- ReasoningTrace.test.tsx --testNamePattern "UI-01"` (D-28 vitest snapshot) | ❌ Wave 0 |
| AGENT-01 | detect_bill_shock_pure byte-exact fixture outputs for chosen persona(s) | offline | `pytest tests/test_bill_shock_flow.py::test_detect_bill_shock_pure_fixtures -x` | ❌ Wave 0; BLOCKED on §6 pivot |
| (cross-cutting) | Pre/post live byte-equivalence on CUST-001/002/004 savings figures (D-33) | live | Custom script reusing `scripts/capture_live_recommendations.py` from Phase 12 | ✅ (Phase 12 precedent) |

### Sampling Rate

- **Per task commit:** `pytest -m "not smoke" tests/test_bill_shock_flow.py` + `cd ui && npm run test -- ReasoningTrace.test.tsx` (< 15s combined).
- **Per wave merge:** Full offline suite `pytest -m "not smoke"` (< 3 min) + full UI suite `cd ui && npm run test` (< 30s).
- **Phase gate (pre-deploy + pre-freeze):** all offline suites green + `BACKEND_API_URL=... python3 scripts/prewarm.py` exit 0 + smoke suite green + byte-equivalence on 3 personas (D-33) + Docker bi-mode container smoke.

### Validation Dimensions (D-19, D-20, D-21 — three independent fabrication detectors)

| Dimension | Test | Gates | Rationale |
|---|---|---|---|
| **Latency floor (D-19)** | `tests/test_narrative_eval_live.py::test_agent01_latency_floor` — CUST-002 live warm > 1000ms | `-m smoke` | Sub-1s response on a 2-3 tool turn is a fabrication signature (tool round-trips cost ≥400ms each). |
| **Cross-persona canary (D-20)** | `tests/test_bill_shock_flow.py::test_no_fabrication_across_personas` — CUST-002 trace differs byte-exact from CUST-004 trace; `is_shock` differs; savings differ | offline via `InMemoryProvider` | Phase 06.1 precedent. Coincident values across personas = fabrication signature. |
| **CloudWatch counter (D-21)** | `tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked` — Tools Lambda Invocations metric ≥ 2 during CUST-002 lookup window | `-m smoke` | Independent observation of tool execution; robust to log format changes. |

### Wave 0 Gaps

- [ ] `tests/test_bill_shock_flow.py` — new file, covers AGENT-01 / AGENT-01b + D-11 / D-16 / D-20 / D-03 fixture
- [ ] `tests/test_narrative_eval_live.py` extension — D-19 latency floor + D-21 CloudWatch counter (file exists)
- [ ] `tests/test_api_lambda.py` extension — reasoning_trace pass-through + no `body.pop("reasoning_trace")` (file exists)
- [ ] `tests/test_prewarm_script.py` extension — per-flow gate map assertion (file exists)
- [ ] `ui/src/components/ReasoningTrace.test.tsx` — new file, 6 vitest cases per D-30
- [ ] Environment variable wiring: `TOOLS_LAMBDA_NAME` (or SSM parameter path) exposed to the smoke suite runner
- [ ] Dockerfile: add `COPY agent/reasoning /app/reasoning` if the planner modularises per D-10 discretion (MEDIUM priority)
- [ ] `agent/reasoning/__init__.py` + `agent/reasoning/summaries.py` — if modularised

---

## Security Domain

Phase 13 security posture is additive — it extends existing hardened surfaces without opening new attack vectors. ASVS categories relevant to the new code:

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | n/a — existing API Lambda unchanged; `runtimeSessionId` generation unchanged |
| V3 Session Management | No | n/a — Phase 13 does not touch SC-3 session-id generation |
| V4 Access Control | Yes | Agent container's IAM role already grants `lambda:InvokeFunction` on Tools Lambda ARN; no widening. The three new @tools use the existing ARN. [VERIFIED via agent/agent.py `_TOOLS_LAMBDA_ARN` + Phase 12 D-02] |
| V5 Input Validation | Yes | `_validate_customer_id` gate (`lambda/handler.py:42-52`) reused in the new `"detect_bill_shock"` branch. Regex `^CUST-\d{3,6}$` unchanged. |
| V6 Cryptography | No | No new crypto; boto3 TLS to CloudWatch + Lambda unchanged |
| V7 Error Handling | Yes | D-04 never-500 extended: cap exhaustion (§1) AND `reasoning_trace` extractor failures must return HTTP 200; new failure modes covered by §1 hook branch + §2 extractor returning `[]` on any exception |
| V8 Data Protection | No | `reasoning_trace` content is deterministic Python formatting of tool outputs — no PII, no customer free text |
| V9 Communications | No | No new external services |
| V10 Malicious Code | No | n/a |
| V11 Business Logic | Yes | 4-tool cap (AGENT-01b) is a business-logic control to prevent runaway loops — enforce via hook, test via D-16 |
| V12 Files / Resources | No | n/a |
| V13 API | Yes | `reasoning_trace` is a new public API field — backwards-compat optional-with-default (`Field(default_factory=list)`) so existing UI clients don't break |
| V14 Config | Yes | Stack-policy lift ceremony preserves deny-Update:* state (D-32, D-33) |

### Known Threat Patterns for Phase 13 stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Runaway tool loop exhausts Bedrock quota / amasses invocation cost | D, A | 4-tool cap via `HookProvider` + `agent.cancel()` (§1) — AGENT-01b |
| LLM fabricates tool output (silent SAV-03 regression) | T | D-19 latency-floor + D-20 cross-persona canary + D-21 CloudWatch counter (three independent detectors) |
| `reasoning_trace` summary contains injected text from DynamoDB record fields | T | Summaries are Python-formatted from dict fields with `f"${result['delta_dollars']:.2f}"` — no free-text interpolation; record fields are numeric/date only |
| Customer enumeration via `detect_bill_shock` response shape | I | `_validate_customer_id` regex gate at entry; API Lambda 400 on invalid format; no leak of other customers' data |
| Stack-policy drift post-deploy leaves frozen stacks writable | T (Tampering) | D-32/D-33 byte-equal verification of `get-stack-policy` output against `infrastructure/stack-policies/*-freeze.json` |
| UI rendering of `reasoning_trace` summary as HTML (XSS if summary carried markup) | T | React escapes by default; summary is plain text per D-10 formatters; no `dangerouslySetInnerHTML` |

**No new secrets or env vars this phase.** No new external endpoints. No new IAM grants beyond container-rebuild triggering. Zero dep bumps — frozen lockfile intact.

---

## Sources

### Primary (HIGH confidence — verified 2026-04-29)

- `.venv/lib/python3.13/site-packages/strands-agents 1.37.0` — installed source
  - `strands/agent/agent.py:63, 146-350` — Agent constructor + default ConcurrentToolExecutor
  - `strands/types/tools.py:53-101` — ToolUse / ToolResult / ToolResultContent TypedDicts
  - `strands/types/content.py:75-100` — ContentBlock shape with `toolUse` + `toolResult` optional keys
  - `strands/types/event_loop.py:39-50` — StopReason Literal values
  - `strands/event_loop/event_loop.py:167-181` — max_tokens → MaxTokensReachedException (not a stop_reason)
  - `strands/tools/executors/concurrent.py:19-88` — ConcurrentToolExecutor internals
  - `strands/tools/executors/__init__.py` — exports
  - `strands/multiagent/swarm.py:189-275` — ONLY place `max_iterations` exists
  - `strands/agent/agent_result.py:19-36` — AgentResult dataclass shape
- Context7 `/strands-agents/sdk-python` — cancellation example, hooks example (BeforeToolCallEvent.cancel_tool, AfterToolCallEvent, HookProvider pattern) [queried 2026-04-29]
- Repo source — byte-verified
  - `agent/agent.py:14-437` — bi-mode imports, @tool template, _extract_lenient_from_agent_result, Agent(...) registration, invoke() D-04 fallback
  - `lambda/handler.py:39-230` — _validate_customer_id, pure helpers, Phase 12 action dispatcher
  - `api_lambda/handler.py:39-162` — Config(read_timeout=25), prewarm branch, customer-not-found detection
  - `infrastructure/seed_data/billing_records.py:1-218` — all 6 persona usage arrays + invariants
  - `infrastructure/stack-policies/{foundation,agentcore,backend-api}-{freeze,allow-all}.json` — byte-equal policies
  - `scripts/prewarm.py:1-130` — 0/1/2 exit taxonomy, 3000ms global gate
  - `tests/conftest.py:1-318` — mock fixtures, `_provider_swap` autouse
  - `ui/src/components/RecommendationCard.tsx` — LD-7 `NARRATIVE_ENABLED` pattern
  - `ui/src/components/RecommendationCard.test.tsx:119-131` — `vi.stubGlobal('location', {search: '?narrative=off'})` pattern
  - `ui/src/lib/flags.ts:1-9` — case-sensitive 'off' check
- `.planning/research/STACK.md` — Strands 1.37.0 concurrent/sequential executor, no SSE [carry-forward]
- `.planning/research/PITFALLS.md` — C1 latency, C5 fabrication, M4 D-04, M5 prewarm [carry-forward]
- `.planning/phases/11-*` + `.planning/phases/12-*` — D-02 action dispatcher, D-08 PROFILE shape, D-10 get_hardship_flag_pure, D-11 _provider_swap
- `CLAUDE.md` — all 15 critical invariants
- Python math: direct subprocess computation of Marcus cost projections

### Secondary (MEDIUM confidence)

- `.planning/research/SUMMARY.md` — LD-4 mentions `Agent(max_iterations=...)` but this was incorrect for Strands 1.37.0 (SUMMARY.md LD-4 conflates Swarm.max_iterations with Agent); the actual verified primitive is the hook-based cap surfaced here [§1 finding supersedes]
- AWS boto3 docs — `cloudwatch.get_metric_statistics` signature semantics
- AWS Lambda metric `AWS/Lambda/Invocations` — canonical dimensions
- PITFALLS.md C1 latency estimates — training-knowledge basis, not measurement

### Tertiary (LOW confidence — flagged for user confirmation)

- Bedrock Sonnet 4.6 warm multi-tool p95 numeric estimate — from PITFALLS.md C1 training-knowledge, not repo measurements; A3 in Assumptions Log
- CloudWatch metric emission lag at 60-90s — AWS ops practice (empirical); A2 in Assumptions Log
- `agent.cancel()` semantics from a hook thread — Context7 example uses a separate thread; usage from `AfterToolCallEvent` hook thread is structurally analogous but not separately documented; A1 in Assumptions Log

---

## Metadata

**Confidence breakdown:**
- Strands 1.37.0 primitives (max_iterations, toolUse, executor): HIGH — installed source inspected
- Marcus fixture threshold blocker: HIGH — deterministic math
- Bedrock warm latency estimate: MEDIUM — no live measurements
- CloudWatch snippet: HIGH — boto3 standard API
- Stack-policy ceremony: HIGH — repo precedent (Phase 10 + Phase 11 + Phase 12)
- UI pattern for ReasoningTrace: HIGH — RecommendationCard template is direct mirror

**Research date:** 2026-04-29
**Valid until:** 2026-05-29 (30 days for stable surface). Strands 1.37.0 is frozen per D-22 — any bump forces re-research. AWS metric lag is an AWS-ops quantity — re-validate if AWS changes emission cadence (unannounced historically).

---

## RESEARCH COMPLETE

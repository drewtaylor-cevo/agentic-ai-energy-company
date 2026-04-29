# Phase 13: Bill-Shock Multi-Tool Flow (AGENT-01) — Pattern Map

**Mapped:** 2026-04-29
**Files analyzed:** 17 (13 modify + 4 new Python + 2 new UI + 1 new baseline dir)
**Analogs found:** 16 / 17 (the `HookProvider` file has no repo analog — call-out below)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `lambda/handler.py` (MODIFY) | tool / pure-helper + dispatcher branch | request-response (Lambda) | `lambda/handler.py` (self — `simulate_savings_pure` + dispatcher) | exact |
| `agent/agent.py` (MODIFY — 3 new @tools + schema + extractor + hook register + stop_reason branch + prompt edit) | agent / tool wrapper / extractor / schema | request-response | `agent/agent.py` (self — `simulate_savings` @tool + `_extract_lenient_from_agent_result` + `RecommendationResponse`) | exact |
| `agent/reasoning/summaries.py` (NEW) | utility (deterministic formatter) | transform (dict → str) | `agent/narrative/shape.py` + `agent/narrative/validators.py` (bi-modeable sibling module) | role-match (bi-mode pattern) |
| `agent/reasoning/__init__.py` (NEW, empty) | package marker | — | `agent/narrative/__init__.py` (empty) | exact |
| `agent/hooks/four_tool_cap.py` (NEW — planner discretion to inline) | middleware (Strands hook) | event-driven | **NO repo analog** — see §"No Analog Found" | divergence |
| `api_lambda/handler.py` | controller / proxy | request-response | `api_lambda/handler.py` (self — pass-through is existing behaviour; no code change, only test expansion) | exact |
| `ui/src/components/ReasoningTrace.tsx` (NEW) | component | request-response (state-driven render) | `ui/src/components/RecommendationCard.tsx` | exact |
| `ui/src/components/ReasoningTrace.test.tsx` (NEW) | test (vitest) | — | `ui/src/components/RecommendationCard.test.tsx` | exact |
| `ui/src/lib/mock/recommendations.ts` (MODIFY) | mock fixture | — | self (header warning + CUST-002 mock block) | exact |
| `ui/src/lib/types.ts` (MODIFY — add `ReasoningTraceEntry` + optional field) | type | — | self (`TrackInfo`, `RecommendationResponse`) | exact |
| `ui/src/App.tsx` (MODIFY — insert `<ReasoningTrace>` above card grid) | page/layout | — | self (current `success` branch at lines 63-69) | exact |
| `tests/test_bill_shock_flow.py` (NEW — 3 test classes) | test (pytest) | — | `tests/test_simulate_savings.py` (pure-helper unit tests) + `tests/test_agent_tools.py` (agent-side with `_provider_swap`) | exact |
| `tests/test_narrative_eval_live.py` (MODIFY — add 2 smoke tests) | test (pytest, smoke) | request-response | self (existing `test_narrative_eval_live` parametrised smoke) | exact |
| `tests/test_api_lambda.py` / `tests/test_backend_api_handler.py` (MODIFY — add `reasoning_trace` pass-through test) | test (pytest) | — | `tests/test_backend_api_handler.py::test_response_passthrough_shape` (line 58-65) | exact |
| `scripts/prewarm.py` (MODIFY — per-flow gate + 3-pass warming + CUST-003 rotation) | utility (CLI) | batch | self (existing `MEDIAN_GATE_MS` + `PERSONAS` + measurement loop) | exact |
| `CLAUDE.md` (MODIFY — addendum for D-11 exemption + cap routing + Strands pin) | docs | — | self (existing "Critical invariants" section) | exact |
| `DEMO-RUNBOOK.md` (MODIFY — Marcus → Elena in rehearsal) | docs | — | self (existing T-24h rehearsal section) | exact |
| `.planning/phases/13-*/baseline/{pre,post}/` (NEW dirs) | artifact | — | Phase 12 D-06 capture pattern (via `scripts/capture_live_recommendations.py`) | role-match |

---

## Pattern Assignments

### `lambda/handler.py` — add `detect_bill_shock_pure` + `"detect_bill_shock"` dispatcher branch

**Analog:** `lambda/handler.py` (self — Phase 11/12 precedent)

**Pure-helper pattern** (lines 60-140, `simulate_savings_pure`):

```python
# Pure helper — no table dependency, no network, fully unit-testable.
# Takes list[dict] billing_history + list[dict] plans, returns dict.
# Rate constants are module-level (DAYS_PER_MONTH = 30.44).
def simulate_savings_pure(
    billing_history: List[Dict[str, Any]],
    plans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if not billing_history:
        raise ValueError("billing_history must not be empty")
    ...
    avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
    ...
    return {"green": {...}, "cheapest": {...}}
```

**Compact pure-helper pattern** (lines 143-161, `get_hardship_flag_pure` — shows injectable `table_client` style):

```python
def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    """Injectable table_client for unit tests."""
    _validate_customer_id(customer_id)
    response = table_client.get_item(
        Key={"customer_id": customer_id, "month": "PROFILE"}
    )
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "customer_id": customer_id}
    return {"hardship": bool(item.get("hardship_flag", False)), "customer_id": customer_id}
```

**Action dispatcher branch pattern** (lines 195-230, `handler(event, context)`):

```python
def handler(event: Dict[str, Any], context) -> Any:
    action = event.get("action")

    if action == "get_billing_history":
        return get_billing_history(event, context)

    if action == "get_hardship_flag":
        customer_id = _validate_customer_id(event.get("customer_id"))
        if table is None:
            raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
        return get_hardship_flag_pure(customer_id, table)

    if action == "get_customer":
        customer_id = _validate_customer_id(event.get("customer_id"))
        return {"customer_id": customer_id}

    if action == "simulate_savings":
        return simulate_savings(event, context)

    # D-05 back-compat: action-less event → simulate_savings (v2.0 shape).
    return simulate_savings(event, context)
```

**Input validation pattern** (lines 39-52):

```python
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

def _validate_customer_id(customer_id: Any) -> str:
    """Raise ValueError on invalid customer_id; returns normalised string."""
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```

**Divergence callouts:**

- `detect_bill_shock_pure` returns `{"is_shock": bool, "delta_dollars": float, "shock_month": str, "mean_dollars": float, "current_dollars": float}` — not the `{green, cheapest}` shape of `simulate_savings_pure`. Concrete signature pinned in RESEARCH §"Example 3".
- Dispatcher branch placement: **add before `"get_customer"`** branch, so the ordering goes `get_billing_history → detect_bill_shock → get_hardship_flag → get_customer → simulate_savings → (back-compat)`. Branch body:
  ```python
  if action == "detect_bill_shock":
      customer_id = _validate_customer_id(event.get("customer_id"))
      if table is None:
          raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
      billing = [i for i in table.query(...)["Items"] if i["month"] != "PROFILE"]
      return detect_bill_shock_pure(sorted(billing, key=lambda r: r["month"]))
  ```
  Alternatively, call existing `get_billing_history(event, context)` inside the new branch to reuse the PROFILE-filter + sort logic (D-21 Phase 11) — cleaner, lower duplication.
- **Chesterton's Fence:** `simulate_savings_pure` at lines 60-140 is untouched. Wrap around, never through.

---

### `agent/agent.py` — 3 new @tools + schema + extractor + hook register + stop_reason branch + prompt edit

**Analog:** `agent/agent.py` (self — every edit has a sibling in the file)

**Bi-mode import pattern** (lines 21-51) — template for any new `agent/reasoning/` imports:

```python
# Bi-mode imports: in the AgentCore container, /app/agent.py is a script and
# /app/narrative/ is a top-level package (Dockerfile COPYs it there). In the
# repo / offline tests, `agent/narrative/` is a subpackage of the `agent`
# namespace package. Try the container layout first so runtime startup is
# fast; fall back to the repo layout for pytest -m "not smoke".
try:
    from narrative.fallbacks import FALLBACKS
    from narrative.prompt_loader import NARRATIVE_PROMPT
    ...
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.fallbacks import FALLBACKS
    from agent.narrative.prompt_loader import NARRATIVE_PROMPT
    ...
```

**@tool wrapper pattern** (lines 263-281, `simulate_savings`):

```python
@tool
def simulate_savings(customer_id: str) -> dict:
    """Calculate Green and Cheapest tariff savings for a customer.

    Returns both recommendation tracks from the deterministic savings engine.
    The numbers returned are exact — do NOT recalculate, round, or estimate them.

    Args:
        customer_id: Customer identifier in format CUST-NNN (e.g. CUST-001).

    Returns:
        Dict with 'green' and 'cheapest' keys, each containing plan_id,
        plan_name, saving_monthly ($/month), and saving_annual ($/year).
    """
    # D-04: provider wraps the Lambda invoke; arithmetic stays in Tools Lambda (SAV-03).
    return get_provider().simulate_savings(customer_id)
```

**Pydantic schema + REC-03 pattern** (lines 89-119):

```python
class TrackInfo(BaseModel):
    plan_id: str = Field(description="Tariff plan identifier (e.g. ECO, VAL)")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")
    usage_narrative: str = Field(max_length=USAGE_NARRATIVE_MAX_CHARS, description="...")
    call_script: str = Field(max_length=CALL_SCRIPT_MAX_CHARS, description="...")

    # D-15 dual-gate: these run after Pydantic's max_length + type checks.
    _validate_usage_narrative = validate_usage_narrative
    _validate_call_script = validate_call_script


class RecommendationResponse(BaseModel):
    """Dual-track tariff recommendation — both tracks always present."""
    green: TrackInfo = Field(description="Most energy-efficient (green) plan recommendation")
    cheapest: TrackInfo = Field(description="Lowest projected cost plan recommendation")
```

**Extractor helper pattern** (lines 238-260, `_extract_lenient_from_agent_result` — exact template for D-08):

```python
def _extract_lenient_from_agent_result(
    agent_result: "AgentResult | None",
) -> "_RecommendationResponseLenient | None":
    """Pull the model's last attempt at RecommendationResponse input from message history.
    Returns None on any failure (caller falls back to FALLBACKS bank).
    """
    if agent_result is None or agent_result.message is None:
        return None
    content_blocks = agent_result.message.get("content", []) or []
    for block in reversed(content_blocks):
        if not isinstance(block, dict):
            continue
        tool_use = block.get("toolUse") or block.get("tool_use")
        if tool_use and tool_use.get("name") == "RecommendationResponse":
            try:
                return _RecommendationResponseLenient(**tool_use.get("input", {}))
            except Exception:  # noqa: BLE001 — best-effort salvage
                return None
    return None
```

**Agent registration pattern** (lines 323-327) — extend `tools=[...]` + add `hooks=[...]`:

```python
_agent = Agent(
    model=_model,
    system_prompt=SYSTEM_PROMPT,
    tools=[simulate_savings],  # Phase 13: extend to 4 tools
)
```

**D-04 never-500 fallback pattern** (lines 396-428) — D-15 cap-exhaustion branch routes HERE unchanged:

```python
    except Exception:
        # v1.0 tool-failure fallback: direct Lambda call. Narrative fields are
        # attached from FALLBACKS so the extended-schema contract holds.
        # D-04 never-500 guarantee — UNCHANGED from pre-migration shape.
        logger.warning("agent invocation failed — falling back to direct Lambda call", exc_info=True)
        resp = _lambda_client.invoke(
            FunctionName=_TOOLS_LAMBDA_ARN,
            InvocationType="RequestResponse",
            Payload=json.dumps({"customer_id": customer_id}).encode(),
        )
        raw = json.loads(resp["Payload"].read())
        fb = FALLBACKS.get(customer_id, {})
        for track in ("green", "cheapest"):
            track_fb = fb.get(track, {})
            raw_track = raw.get(track, {})
            if "usage_narrative" not in raw_track:
                raw_track["usage_narrative"] = track_fb.get(
                    "usage_narrative",
                    "Household profile note unavailable for this customer.",
                )
                narrative_source[track]["usage_narrative"] = "fallback"
            if "call_script" not in raw_track:
                raw_track["call_script"] = track_fb.get(
                    "call_script",
                    "Ask about the recommended plan for this household.",
                )
                narrative_source[track]["call_script"] = "fallback"
            raw[track] = raw_track
        raw["_narrative_source"] = narrative_source
        return raw
```

**System prompt edit target** (lines 285-311):

```python
_BASE_SYSTEM_PROMPT = """\
You are a call centre tariff recommendation assistant for an energy provider.
...
RULES:
1. Call the simulate_savings tool ONCE with the customer_id provided.
2. Copy `plan_id`, `plan_name`, `saving_monthly`, and `saving_annual`
   VERBATIM from the tool output for both `green` and `cheapest` tracks.
3. Return BOTH the GREEN and CHEAPEST tracks in your response.
...
"""
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + NARRATIVE_PROMPT
```

**Divergence callouts:**

- **Three new @tools** — `detect_bill_shock`, `get_billing_history`, `get_hardship_flag`. Per RESEARCH §7 (Option A, recommended — preserves LD-5 3-method Protocol), these go **direct to `_lambda_client.invoke`** not through `get_provider()`. Drop-in body:
  ```python
  @tool
  def detect_bill_shock(customer_id: str) -> dict:
      """Detect bill-shock anomaly..."""
      resp = _lambda_client.invoke(
          FunctionName=_TOOLS_LAMBDA_ARN,
          InvocationType="RequestResponse",
          Payload=json.dumps({"action": "detect_bill_shock", "customer_id": customer_id}).encode(),
      )
      return json.loads(resp["Payload"].read())
  ```
  Repeat for `get_billing_history` (action=`"get_billing_history"`) and `get_hardship_flag` (action=`"get_hardship_flag"`). `simulate_savings` stays on the provider (D-02).
- **`ReasoningTraceEntry` + extended `RecommendationResponse`** — add alongside (after) the existing `RecommendationResponse` at line 119. Per D-11, NO validators on `summary`:
  ```python
  class ReasoningTraceEntry(BaseModel):
      tool: str = Field(description="Tool name (e.g. 'detect_bill_shock')")
      summary: str = Field(description="Code-composed summary of the tool result")
      # D-11 EXEMPTION: NO validators on summary — reasoning_trace intentionally
      # contains digits, currency, dates (that's its value as observability).

  class RecommendationResponse(BaseModel):
      green: TrackInfo
      cheapest: TrackInfo
      reasoning_trace: list[ReasoningTraceEntry] = Field(default_factory=list)
  ```
- **`_extract_reasoning_trace` helper** mirrors `_extract_lenient_from_agent_result` structurally but iterates `content_blocks` **forward** (order-preserving), indexes `toolResult` by `toolUseId`, emits entries per `_TRACE_TOOLS` filter. Full drop-in snippet in RESEARCH §2 (lines 239-303) — copy verbatim.
- **Hook registration** per RESEARCH §1 (AMENDMENT A-02):
  ```python
  _agent = Agent(
      model=_model,
      system_prompt=SYSTEM_PROMPT,
      tools=[simulate_savings, detect_bill_shock, get_billing_history, get_hardship_flag],
      hooks=[FourToolCapHook(budget=4)],
  )
  ```
  **Do NOT pass `max_iterations=4`** — Strands 1.37.0 has no such parameter (RESEARCH §1).
- **stop_reason branch inside `invoke()`** — add BEFORE the existing `except Exception` (lines 396+):
  ```python
  try:
      agent_result = _agent(_build_narrative_prompt(customer_id), structured_output_model=RecommendationResponse)
      if agent_result.stop_reason == "cancelled":
          # D-15 cap exhaustion — route to D-04 fallback (below) via raise
          raise RuntimeError("tool budget exhausted")
      ...
  ```
  The `except Exception` branch at 396 already catches `RuntimeError` and stitches FALLBACKS narrative + Tools Lambda direct call. Per D-15 the partial `reasoning_trace` can also be assembled here via `_extract_reasoning_trace(agent_result)` before the raise.
- **Happy-path return extension** (line 431-433) — attach reasoning_trace before `model_dump()`:
  ```python
  body = result.model_dump()
  body["reasoning_trace"] = [e.model_dump() for e in _extract_reasoning_trace(agent_result)]
  body["_narrative_source"] = narrative_source
  return body
  ```
  Actually cleaner: `result` is already `RecommendationResponse` with `reasoning_trace` field. Attach into `result.reasoning_trace` BEFORE `model_dump()` by rebuilding via `result.model_copy(update=...)` OR attach directly if schema allows. Planner picks; structural template above.

---

### `agent/reasoning/summaries.py` (NEW) — 4 per-tool formatters

**Analog:** `agent/narrative/shape.py` + `agent/narrative/validators.py` (sibling modules under `agent/narrative/` — exact structural template for modularised formatters)

**Bi-mode sibling module pattern** — `agent/narrative/validators.py` lines 12-18 shows the in-module bi-mode import for cross-module dependencies:

```python
"""Narrative field validators — UI-05 hard code-level gate.
...
"""
from pydantic import ValidationInfo, field_validator

# Bi-mode import: container layout is `/app/narrative/`, repo layout is
# `agent/narrative/`. See agent/agent.py for the parent rationale.
try:
    from narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
```

**Deterministic formatter pattern** (D-10 CONTEXT.md — SAV-03 by construction, code-composed strings):

```python
def _summary_detect_bill_shock(result: dict) -> str:
    if result.get("is_shock"):
        return (
            f"Bill shock detected: +${result['delta_dollars']:.2f} "
            f"{result['shock_month']} vs 11-month avg "
            f"(${result['current_dollars']:.2f} vs ${result['mean_dollars']:.2f})"
        )
    return "No bill shock: monthly usage within 11-month envelope"
```

**Divergence callouts:**

- No existing module in the repo is a "pure formatter on tool output dict → str". `agent/narrative/shape.py` and `agent/narrative/fallbacks.py` are the closest structural siblings (pure Python, no boto3, bi-mode-importable).
- Module EXPORTS (for bi-mode import from `agent.py`): four `summary_*` functions — `summary_detect_bill_shock`, `summary_get_billing_history`, `summary_get_hardship_flag`, `summary_simulate_savings`.
- **Dockerfile update required** — `agent/Dockerfile` must gain `COPY agent/reasoning /app/reasoning` alongside the existing `COPY agent/narrative /app/narrative` (RESEARCH §7, Pitfall 4). Pre-deploy bi-mode container smoke: `docker run --rm --entrypoint python <image> -c 'from reasoning.summaries import summary_simulate_savings; print("OK")'`.

---

### `agent/reasoning/__init__.py` (NEW, empty)

**Analog:** `agent/narrative/__init__.py` (self-referential — file is empty / 1 line per filesystem).

**Pattern:** Create an empty file. No `__all__`, no re-exports. Package marker only.

**Divergence:** None — direct mirror.

---

### `agent/hooks/four_tool_cap.py` (NEW — planner may inline into `agent/agent.py`)

**Analog:** **No repo analog exists.** This is the first Strands hook in the codebase. Read the Strands SDK source directly:

- `.venv/lib/python3.13/site-packages/strands/hooks/registry.py:89-115` — `HookProvider` Protocol definition:
  ```python
  @runtime_checkable
  class HookProvider(Protocol):
      """Protocol for objects that provide hook callbacks to an agent.
      Example:
          class MyHookProvider(HookProvider):
              def register_hooks(self, registry: HookRegistry) -> None:
                  registry.add_callback(StartRequestEvent, self.on_request_start)
                  registry.add_callback(EndRequestEvent, self.on_request_end)
          agent = Agent(hooks=[MyHookProvider()])
      """
      def register_hooks(self, registry: "HookRegistry", **kwargs: Any) -> None: ...
  ```
- `.venv/lib/python3.13/site-packages/strands/hooks/events.py:133-158` — `BeforeToolCallEvent` definition:
  ```python
  @dataclass
  class BeforeToolCallEvent(HookEvent, _Interruptible):
      selected_tool: AgentTool | None
      tool_use: ToolUse
      invocation_state: dict[str, Any]
      cancel_tool: bool | str = False
      def _can_write(self, name: str) -> bool:
          return name in ["cancel_tool", "selected_tool", "tool_use"]
  ```
- `.venv/lib/python3.13/site-packages/strands/hooks/events.py:173+` — `AfterToolCallEvent` definition (recommended per RESEARCH §1 Option A — counts AFTER tool completion, calls `event.agent.cancel()` on budget exhaustion).

**Pattern (from RESEARCH §1 Option A, lines 147-167 of RESEARCH.md):**

```python
from strands.hooks import AfterToolCallEvent, HookProvider, HookRegistry

class FourToolCapHook(HookProvider):
    """D-14/D-15 AGENT-01b: hard-cap tool-call count at budget; cancel the agent
    when exhausted. Cancellation surfaces as agent_result.stop_reason == "cancelled",
    which invoke() inspects to route through the D-04 fallback path."""

    def __init__(self, budget: int = 4):
        self.budget = budget
        self.used = 0

    def register_hooks(self, registry: HookRegistry, **kwargs):
        registry.add_callback(AfterToolCallEvent, self.on_tool_complete)

    def on_tool_complete(self, event: AfterToolCallEvent):
        self.used += 1
        if self.used >= self.budget:
            event.agent.cancel()
```

**Divergence callouts:**

- **No repo analog — first hook in codebase.** All pattern evidence is SDK-internal (read `.venv/lib/python3.13/site-packages/strands/hooks/*.py` during planning).
- **Counter state MUST live on the hook instance, NOT module-level.** RESEARCH §A-02 flags this as SC-3 mirror (runtimeSessionId session-bleed precedent — module-level counters leak across invocations). If the agent container reuses the same `_agent` singleton across invocations, consider instantiating a fresh `FourToolCapHook` per `invoke()` call instead of registering once at module scope. Planner pins the call site.
- **`event.agent.cancel()` thread-safety** is Assumption A1 in RESEARCH (LOW risk) — the D-16 offline pytest MUST assert `stop_reason == "cancelled"` terminally to validate end-to-end.
- **Anti-pattern to avoid** (RESEARCH §"Anti-Patterns"): passing `max_iterations=4` to `Agent(...)` — Strands 1.37.0 silently accepts unknown kwargs or raises `TypeError`. Cap is NOT enforced. Planner MUST NOT write this.

---

### `api_lambda/handler.py` (LIKELY NO CODE CHANGE)

**Analog:** `api_lambda/handler.py` (self)

**Pass-through pattern** (lines 118-133) — `reasoning_trace` rides through UNCHANGED:

```python
body = json.loads(response["response"].read())
# D-06: strip internal marker (idempotent; None default means
# pre-6.1 agent deployments do not break the handler).
narrative_source = body.pop("_narrative_source", None)
# D-07: structured CloudWatch INFO log (zero-PII by construction).
logger.info(json.dumps({
    "event": "narrative_source",
    "customer_id": customer_id,
    "narrative_source": narrative_source,
}))
```

**Customer-not-found detection** (lines 149-154) — UNCHANGED in Phase 13:

```python
# D-12: customer-not-found detection — agent fallback path returns
# {"errorMessage": "..."} with no green/cheapest keys (RESEARCH.md Pitfall 5).
if "green" not in body or "cheapest" not in body:
    logger.info("Customer not found customer_id=%s body=%s", customer_id, body)
    return _error(404, f"Customer {customer_id} not found.")
```

**Config timeout pattern** (lines 39-43) — DO NOT TOUCH:

```python
_agentcore_client = boto3.client(
    "bedrock-agentcore",
    region_name=_REGION,
    config=Config(read_timeout=25, connect_timeout=5),
)
```

**Divergence callouts:**

- **Zero code change expected.** `body["reasoning_trace"]` is a new key in the generic dict — passed through `json.dumps(body)` at line 161 untouched.
- **Do NOT add `body.pop("reasoning_trace", None)`** — D-12 pins the public pass-through.
- **Planner MUST run `cdk diff CustomerTariffApi`** during planning. If diff == 0 after all upstream edits, downgrade from 3-stack lift to 2-stack lift (D-31). Even the test file expansion may trigger asset-hash changes — Pitfall 6.

---

### `ui/src/components/ReasoningTrace.tsx` (NEW)

**Analog:** `ui/src/components/RecommendationCard.tsx` (lines 1-95 — exact structural template)

**NARRATIVE_ENABLED kill-switch pattern** (lines 12, 83-91):

```tsx
import { NARRATIVE_ENABLED } from '@/lib/flags';

...

{NARRATIVE_ENABLED && (
  <p className="text-sm italic text-muted-foreground">{data.usage_narrative}</p>
)}
```

**Component skeleton pattern** (lines 37-54 of `RecommendationCard.tsx`):

```tsx
interface RecommendationCardProps {
  track: 'green' | 'cheapest';
  data: TrackInfo;
}

export function RecommendationCard({ track, data }: RecommendationCardProps) {
  const config = TRACK_CONFIG[track];
  const Icon = config.icon;
  ...
  return (
    <Card className={`border-t-4 ${config.accentBorder}`}>
      ...
    </Card>
  );
}
```

**Type import pattern** (line 11):

```tsx
import type { TrackInfo } from '@/lib/types';
```

**Available shadcn primitives** (from `ui/src/components/ui/`): `alert.tsx`, `badge.tsx`, `button.tsx`, `card.tsx`, `input.tsx`, `label.tsx`, `skeleton.tsx`. No new shadcn install needed for D-26 collapsed disclosure — compose from `Card` + `Button` + native `<ul>` / `<ol>`.

**Divergence callouts:**

- New file imports `ReasoningTraceEntry[]` from `@/lib/types` (added in the `ui/src/lib/types.ts` modify — see below).
- **Empty-list short-circuit** (D-26 spec): `if (!trace || trace.length === 0) return null;` — render `null` (not an empty card) so single-tool personas have zero vertical cost.
- **Kill-switch short-circuit** (D-27): `if (!NARRATIVE_ENABLED) return null;` — same early-return as `RecommendationCard.tsx` lines 83-91 but at the top of the function, not conditionally inside JSX.
- **Collapsed state** (D-26): single row `▶ N steps: tool_a → tool_b → tool_c` — tool NAMES only, NO numbers. Expanded state (on click) shows the ordered list of `entry.summary` strings. Use `useState` for disclosure toggle (no shadcn Accordion — overkill; existing component lib is minimal).
- **Placement in App.tsx** (D-28) — inserted BEFORE the card grid div at App.tsx:63-69:
  ```tsx
  {state.status === 'success' && (
    <>
      <ReasoningTrace trace={state.data.reasoning_trace ?? []} />
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <RecommendationCard track="green" data={state.data.green} />
        <RecommendationCard track="cheapest" data={state.data.cheapest} />
      </div>
    </>
  )}
  ```

---

### `ui/src/components/ReasoningTrace.test.tsx` (NEW — 6 vitest cases)

**Analog:** `ui/src/components/RecommendationCard.test.tsx` (lines 1-148 — exact structural template)

**beforeEach + kill-switch-stub pattern** (lines 13-31, 119-148):

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { TrackInfo } from '@/lib/types';

beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

describe('RecommendationCard — ?narrative=off suppresses narrative + call_script (D-10)', () => {
  it('hides narrative and call_script on Green track', async () => {
    vi.stubGlobal('location', { search: '?narrative=off' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    expect(screen.queryByText(/Strong cool-season usage/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Ask about EcoFlex/)).not.toBeInTheDocument();
    expect(container.querySelector('blockquote')).toBeNull();
  });
```

**Flag-ON default test pattern** (lines 33-48):

```tsx
describe('RecommendationCard — flag ON (default)', () => {
  it('renders narrative and call_script for Green track with emerald-600 left border', async () => {
    vi.stubGlobal('location', { search: '' } as Location);
    vi.resetModules();
    const { RecommendationCard } = await import('./RecommendationCard');
    const { container } = render(<RecommendationCard track="green" data={trackFixture()} />);
    expect(screen.getByText(/Strong cool-season usage/)).toBeInTheDocument();
    ...
  });
```

**Divergence callouts:**

- Six vitest cases per D-30:
  1. Empty list → renders `null`.
  2. 3-entry list → renders collapsed row with tool names + chevron.
  3. Click expands to ordered list.
  4. `?narrative=off` + non-empty list → renders `null` (stub pattern above).
  5. `?narrative=off` + empty list → renders `null`.
  6. 1-entry list → renders single-step collapsed row; expanded shows one entry.
- The `vi.stubGlobal('location', { search: '?narrative=off' })` + `vi.resetModules()` + dynamic `await import('./ReasoningTrace')` idiom is LOAD-BEARING for flags.ts module-load semantics (flags.ts evaluates `URLSearchParams` at module init). Copy the exact pattern — do not refactor.
- Add a `traceFixture` helper similar to `trackFixture` at RecommendationCard.test.tsx:17-25.

---

### `ui/src/lib/mock/recommendations.ts` (MODIFY)

**Analog:** Self — existing byte-exact sync pattern

**Byte-sync discipline header** (lines 1-19):

```typescript
import type { RecommendationResponse } from '../types';

// Values ported from tests/conftest.py:47-100 (mock_savings_response,
// mock_marcus_response, mock_elena_response). These MUST stay in sync with the
// deterministic output of lambda/handler.py::simulate_savings_pure for each
// persona (verified in tests/test_simulate_savings.py).
//
// Plan IDs are always `ECO` (green) and `VAL` (cheapest) across all personas —
// the backend invariant asserted by tests/test_agent_smoke.py:81-85.
//
// Phase 8 D-19: usage_narrative and call_script strings on each track are
// copied VERBATIM (byte-for-byte) from agent/narrative/fallbacks.py.
```

**Per-persona record shape** (lines 20-74):

```typescript
export const MOCK_RECOMMENDATIONS: Record<string, RecommendationResponse> = {
  'CUST-001': {
    green: { plan_id: 'ECO', plan_name: 'EcoFlex 100', saving_monthly: 30.00, saving_annual: 360.00,
             usage_narrative: '...', call_script: '...' },
    cheapest: { plan_id: 'VAL', plan_name: 'Value 12', saving_monthly: 55.00, saving_annual: 660.00,
                usage_narrative: '...', call_script: '...' },
  },
  'CUST-002': { ... },
  'CUST-003': { ... },
};
```

**Divergence callouts:**

- **Amendment A-01 override:** constant name is `MOCK_REASONING_TRACE_CUST003` (not CUST002). Elena is the designated bill-shock persona.
- **Per D-29:** CUST-003 gets a 3-entry trace (tools: `get_hardship_flag` → `detect_bill_shock` → `simulate_savings`). CUST-001, CUST-002, CUST-004, CUST-005 get `reasoning_trace: []`.
- **Header comment addendum:** Add a new sync-target line — "Values MUST stay in sync with `agent/reasoning/summaries.py` formatters — single-commit discipline."
- **No CUST-004 or CUST-005 in the current file** — only CUST-001/002/003. Planner confirms whether to add them (Phase 11 persona rollout) or skip.

---

### `ui/src/lib/types.ts` (MODIFY)

**Analog:** Self — lines 1-17 show the snake_case contract

**Current type contract** (lines 5-17):

```typescript
export interface TrackInfo {
  plan_id: string;
  plan_name: string;
  saving_monthly: number;
  saving_annual: number;
  usage_narrative: string;
  call_script: string;
}

export interface RecommendationResponse {
  green: TrackInfo;
  cheapest: TrackInfo;
}
```

**Divergence callouts:**

- Add `ReasoningTraceEntry` interface and extend `RecommendationResponse`:
  ```typescript
  export interface ReasoningTraceEntry {
    tool: string;
    summary: string;
  }

  export interface RecommendationResponse {
    green: TrackInfo;
    cheapest: TrackInfo;
    reasoning_trace?: ReasoningTraceEntry[];  // optional — empty/omitted on single-tool turns
  }
  ```
- **Phase 8 D-18 invariant** — keep snake_case, do NOT camelCase. Matches JSON wire format.

---

### `ui/src/App.tsx` (MODIFY)

**Analog:** Self — lines 63-69 is the current success-branch card grid

**Current success branch** (lines 63-69):

```tsx
{state.status === 'success' && (
  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
    {/* Card order stable: Green first, Cheapest second. */}
    <RecommendationCard track="green" data={state.data.green} />
    <RecommendationCard track="cheapest" data={state.data.cheapest} />
  </div>
)}
```

**Divergence callouts:**

- Insert `<ReasoningTrace trace={state.data.reasoning_trace ?? []} />` BEFORE the grid div (D-28 — shared above both cards because trace is turn-level, not track-level).
- Add `import { ReasoningTrace } from '@/components/ReasoningTrace';` to the imports block (lines 22-29).
- Wrap insertion in a React fragment (`<>...</>`) or promote the branch body to two sibling elements.

---

### `tests/test_bill_shock_flow.py` (NEW)

**Analog:** `tests/test_simulate_savings.py` (pure-helper unit test style) + `tests/test_agent_tools.py` (agent-side mock + `_provider_swap`)

**Pure-helper test pattern** (`tests/test_simulate_savings.py` lines 1-60):

```python
"""Tests for simulate_savings_pure — DEMO-02 + SAV-03 proof."""
import importlib
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
simulate_savings_pure = handler.simulate_savings_pure


def test_flagship_persona_green_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01


def test_result_shape(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert set(result.keys()) == {"green", "cheapest"}
```

**Cross-persona canary pattern** (`tests/test_simulate_savings.py` lines 61-72):

```python
def test_cheapest_always_gte_green(sarah_billing, marcus_billing, elena_billing, tariff_plans):
    for billing in (sarah_billing, marcus_billing, elena_billing):
        result = simulate_savings_pure(billing, tariff_plans)
        assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"], \
            f"Invariant violated for {billing[0]['customer_id']}"
```

**Agent-side mock pattern** (`tests/test_agent_tools.py` lines 13-45):

```python
def make_mock_lambda_response(payload_dict):
    payload_bytes = json.dumps(payload_dict).encode()
    return {
        "StatusCode": 200,
        "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
    }


def test_both_tracks_present(mock_savings_response):
    assert "green" in mock_savings_response
    assert "cheapest" in mock_savings_response
```

**`_provider_swap` fixture pattern** (`tests/conftest.py` lines 78-98 — autouse, runs on every test in the suite):

```python
@pytest.fixture(autouse=True)
def _provider_swap():
    """D-11 autouse: every test runs with an InMemoryProvider installed."""
    from agent.providers import get_provider, set_provider, InMemoryProvider
    try:
        original = get_provider()
    except RuntimeError:
        original = None
    set_provider(InMemoryProvider())
    yield
    if original is not None:
        set_provider(original)
```

**Divergence callouts:**

- **D-16 4-tool cap test** (`test_four_tool_cap_fires_gracefully`):
  - Construct `FourToolCapHook(budget=1)` OR monkey-patch the hook's threshold on a test agent.
  - Trigger a tail-call fake `@tool` OR crafted loop-prompt.
  - Assert `agent_result.stop_reason == "cancelled"`.
  - Assert response body: `"green"` + `"cheapest"` + `"reasoning_trace"` (may be partial) present; `_narrative_source` marks `"fallback"`; no `"errorMessage"` key.
- **D-20 cross-persona canary** (`test_no_fabrication_across_personas`) — per Amendment A-01:
  - Invoke on **CUST-003** (bill-shock) and **CUST-002 Marcus** (non-shock foil — new role).
  - Assert `reasoning_trace` differs byte-exact between the two (Phase 06.1 fabrication signature).
  - Assert `detect_bill_shock` result differs (`is_shock=True` for CUST-003, `is_shock=False` for CUST-002 Marcus).
  - Assert savings differ (Elena $14.00/$25.67 vs Marcus $16.90/$30.98).
- **D-03 detect_bill_shock_pure unit tests** — pin byte-exact against ELENA_VASQUEZ_RECORDS (Elena's 2025-10 tripping ratio 0.6344, peak 7 months above gate per RESEARCH §6). Use `elena_billing` fixture already in `conftest.py:32-34`. Marcus fixture is the non-shock counter-test.
- **D-11 exemption counter-test** — construct `ReasoningTraceEntry(tool="detect_bill_shock", summary="Bill shock detected: +$47 Dec vs 11-month avg ($135 vs $88)")` and assert `.model_validate(...)` passes cleanly WITH digits + `$` + dates. Label the test "D-11 EXEMPTION — do not apply narrative validators to reasoning_trace."
- **File organisation** — CONTEXT.md §"Claude's Discretion" leaves "one big test file vs split" to planner. Recommendation: one file with 3 test classes (`TestDetectBillShockPure`, `TestFourToolCap`, `TestCrossPersonaCanary`, `TestReasoningTraceExemption`).

---

### `tests/test_narrative_eval_live.py` (MODIFY — add 2 smoke tests)

**Analog:** Self — lines 31-39 (pytestmark block) + parametrised test at 71-113

**Smoke-marker pattern** (lines 31-39):

```python
pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BACKEND_API_URL,
        reason="BACKEND_API_URL not set — skip live narrative eval harness",
    ),
]
```

**Live API test pattern** (lines 71-113):

```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_narrative_eval_live(customer_id):
    r = requests.get(f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "_narrative_source" not in body, f"D-06 violation for {customer_id}..."
    for track in ("green", "cheapest"):
        assert track in body, f"Missing {track} track for {customer_id}"
```

**Divergence callouts:**

- **D-19 `test_agent01_latency_floor`** (per Amendment A-01 — CUST-003):
  ```python
  @pytest.mark.smoke
  def test_agent01_latency_floor():
      """D-19: CUST-003 live latency > 1000ms — sub-1s is a fabrication signature."""
      t0 = time.perf_counter()
      r = requests.get(f"{BACKEND_API_URL}/recommendations/CUST-003", timeout=60)
      elapsed_ms = (time.perf_counter() - t0) * 1000
      assert r.status_code == 200
      assert elapsed_ms > 1000, f"CUST-003 returned in {elapsed_ms}ms (<1000ms — C5 fabrication signature)"
  ```
- **D-21 `test_agent01_tools_actually_invoked`** — drop-in snippet already provided in RESEARCH §5 (lines 401-463). Key points:
  - Query CloudWatch `AWS/Lambda` `Invocations` metric over a 60-90s post-call window.
  - 90-second `time.sleep(90)` is load-bearing for CloudWatch emission lag (Pitfall 5 — do NOT shorten).
  - Use `CUST-003` per amendment A-01, not CUST-002.
  - SSM fallback for `TOOLS_LAMBDA_NAME` — parameter `/customer-tariff/tools-lambda-name`.
  - Assert `total_invocations >= 2`.

---

### `tests/test_backend_api_handler.py` (MODIFY — add `reasoning_trace` pass-through test)

**Analog:** `tests/test_backend_api_handler.py::test_response_passthrough_shape` (lines 58-65)

**Pass-through test pattern** (lines 58-65):

```python
@patch("api_lambda.handler._agentcore_client")
def test_response_passthrough_shape(mock_client, mock_savings_response):
    """D-02: response body is verbatim pass-through — no envelope, no meta."""
    mock_client.invoke_agent_runtime.return_value = _make_agent_response(
        mock_savings_response
    )
    result = handler(_make_event("CUST-001"), None)
    assert json.loads(result["body"]) == mock_savings_response
```

**Mock event helpers** (lines 28-39):

```python
def _make_event(customer_id: str) -> dict:
    return {"pathParameters": {"customer_id": customer_id}}


def _make_agent_response(body: dict) -> dict:
    return {
        "response": io.BytesIO(json.dumps(body).encode()),
        "contentType": "application/json",
        "statusCode": 200,
    }
```

**Divergence callouts:**

- New test asserts `reasoning_trace` survives `api_lambda/handler.py` pass-through unchanged. Pass a `mock_savings_response` with an injected `"reasoning_trace": [{...}, {...}]`, assert `json.loads(result["body"])["reasoning_trace"] == [...]`.
- Also test NO `body.pop("reasoning_trace", None)` regression — assert the field is byte-equal pre/post.
- File is named `test_backend_api_handler.py` in this repo (not `test_api_lambda.py` as referenced in CONTEXT.md §Integration Points — planner notes the rename).

---

### `scripts/prewarm.py` (MODIFY — per-flow gate + 3-pass warming + CUST-003)

**Analog:** Self — existing module-level constants + measurement loop

**Module-level constants pattern** (lines 30-35):

```python
PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]
MEDIAN_GATE_MS = 3000          # D-03 — matches ROADMAP SC-2 verbatim; do NOT tighten to 2500
PREWARM_SPACING_S = 2          # D-02 step 1
SETTLE_WAIT_S = 30             # D-02 step 2 — load-bearing for microVM pool settling
MEASUREMENT_SAMPLES = 3        # D-02 step 3
HTTP_TIMEOUT_S = 30            # D-08
```

**0/1/2 exit taxonomy pattern** (lines 38-44, 61-65, 104-126):

```python
def main() -> int:
    t_start = time.perf_counter()
    api_url = os.environ.get("BACKEND_API_URL", "").rstrip("/")
    if not api_url:
        print("BACKEND_API_URL not set", file=sys.stderr)
        return 2  # setup error

    # ... later, per-persona loop:
    if persona == PERSONAS[0]:
        print(f"cannot reach {api_url}: {exc}", file=sys.stderr)
        return 2  # setup error on first persona
    print(f"prewarm {persona}: ERROR {exc}")
    return 1  # runtime fail on subsequent personas

    # ... gate evaluation:
    any_fail = False
    for persona in PERSONAS:
        median_ms = int(statistics.median(medians[persona]))
        if median_ms < MEDIAN_GATE_MS:
            print(f"median {persona}: {median_ms}ms PASS (<3000ms)")
        else:
            print(f"median {persona}: {median_ms}ms FAIL (≥3000ms)")
            any_fail = True

    if any_fail:
        return 1
    return 0
```

**Warm-pass loop pattern** (lines 46-75):

```python
for idx, persona in enumerate(PERSONAS):
    warm_url = f"{api_url}/recommendations/{persona}?prewarm=1"
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(warm_url, timeout=HTTP_TIMEOUT_S) as resp:
            status = resp.status
            resp.read()
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"prewarm {persona}: {exc.code} {elapsed_ms}ms FAIL (expected 204)")
        return 1
    ...
    if idx < len(PERSONAS) - 1:
        time.sleep(PREWARM_SPACING_S)
```

**Divergence callouts:**

- **Amendment A-01 + A-03 changes:**
  - `PERSONAS = ["CUST-001", "CUST-003"]` — rotation of single-tool + multi-tool (CUST-002 deprecated from rotation; Elena added per A-01).
  - Replace `MEDIAN_GATE_MS = 3000` with a per-persona gate map:
    ```python
    GATE_MS = {"CUST-001": 3000, "CUST-003": 2500}  # single-tool vs multi-tool
    ```
  - Increase warm passes from 2 → 3 per A-03 (promotion — mitigates Strands + Bedrock first-call variance). This is a NEW third warming pass BEFORE the 30s settle, not a third measurement sample.
- **Exit taxonomy — preserve 0/1/2 verbatim.** Exit 0 iff ALL per-flow gates pass. Exit 1 on any gate fail OR HTTP error. Exit 2 on missing `BACKEND_API_URL` OR unreachable first-persona endpoint. Pitfall 1 (plan carries single `MEDIAN_GATE_MS` rename) is explicit — planner MUST add the map, not rename the scalar.
- **Pytest extension:** `tests/test_prewarm_script.py` also modifies — byte-exact unit test on the new gate map + assertion that CUST-003 multi-tool gate is 2500ms.

---

### `CLAUDE.md` (MODIFY — addendum)

**Analog:** Self — existing "Critical invariants" bullet-list section

**Current invariant-bullet pattern** (CLAUDE.md §"Critical invariants — break these and the demo dies"):

```markdown
- **SAV-03: LLM never does arithmetic.** All savings math lives in `lambda/handler.py::simulate_savings_pure`. The agent system prompt at `agent/agent.py` forbids estimation, rounding, or recalculation; numbers from the tool are copied byte-for-byte into the response. Do not let the LLM "fix" or "round" tool output.
- **REC-03: both tracks always returned, never ranked.** `RecommendationResponse` requires both `green` and `cheapest`; the prompt forbids saying one is better.
- **D-15 narrative dual-gate.** `usage_narrative` (≤20 words) and `call_script` (≤22 words) must contain no digits, currency symbols, %, switch verbs, competitor names, or environmental superlatives.
```

**Divergence callouts:**

- Add 3 new bullets per D-11 / D-15 amended / D-22:
  1. **D-11 reasoning_trace exemption:** "`reasoning_trace[*].summary` is a separate observability surface with no content filter. D-15 dual-gate covers narrative surfaces ONLY. Do not apply `_reject_forbidden` or any narrative validator to `ReasoningTraceEntry.summary` — trace summaries intentionally contain digits, currency, and dates (counter-pytest in `tests/test_bill_shock_flow.py`)."
  2. **D-15 cap-fallback routing (amended):** "The 4-tool cap is enforced via `FourToolCapHook` (Strands `HookProvider`), NOT `Agent(max_iterations=N)` — Strands 1.37.0 has no such parameter. On budget exhaustion, `agent_result.stop_reason == 'cancelled'`; `invoke()` converts this into a RuntimeError that routes through the existing `except Exception` at `agent/agent.py:396-428` (D-04 never-500 preserved)."
  3. **D-22 Strands pinned:** "Strands 1.37.0 is frozen for v3.0. Any minor or major bump requires a decimal phase (Phase 06.1 precedent) with the cross-persona canary (`tests/test_bill_shock_flow.py::test_no_fabrication_across_personas`) re-run against the new version. Frozen lockfile + `--require-hashes` enforces mechanically."

---

### `DEMO-RUNBOOK.md` (MODIFY — rehearsal persona swap)

**Analog:** Self — §2 T-24h rehearsal section (AGENT-01 beat)

**Divergence callouts:**

- Per amendment A-01: swap `Marcus` → `Elena` for the AGENT-01 demo beat in the rehearsal rotation.
- Warm-median target stays 2500ms (AGENT-01a gate unchanged).
- Planner reads current DEMO-RUNBOOK.md to find the exact line(s) to edit; the repo's `DEMO-RUNBOOK.md` is modified in git status so may have in-flight edits.

---

### `.planning/phases/13-*/baseline/{pre,post}/` (NEW directories)

**Analog:** Phase 12 D-06 capture pattern via `scripts/capture_live_recommendations.py` (exists in `scripts/` dir per earlier `ls`)

**Divergence callouts:**

- Per D-33 + amendment A-01: capture JSON bodies for **CUST-001 + CUST-003 + CUST-002** (CUST-002 now the non-shock sanity, replacing CUST-004 in original D-33).
- Path: `.planning/phases/13-bill-shock-multi-tool-flow-agent-01/baseline/{pre,post}/{customer_id}.json`.
- Pre = captured before Wave N deploy (baseline against live v2.0). Post = captured after deploy (v3.0 Phase 13).
- Diff-gate columns: `green.saving_monthly`, `green.saving_annual`, `cheapest.saving_monthly`, `cheapest.saving_annual`, `green.plan_id`, `cheapest.plan_id` MUST be byte-equal pre vs post. Exclude `reasoning_trace` + narrative fields.

---

## Shared Patterns

### Bi-Mode Imports (container vs repo layout)

**Source:** `agent/agent.py:21-51`, `agent/agent.py:53-71`, `agent/narrative/validators.py:14-18`
**Apply to:** `agent/agent.py` (new `agent/reasoning/summaries.py` import block), `agent/reasoning/summaries.py` if it imports any other in-package module.

```python
try:
    from narrative.fallbacks import FALLBACKS
    from narrative.prompt_loader import NARRATIVE_PROMPT
    ...
except ImportError:  # pragma: no cover - hit only in offline test repo layout
    from agent.narrative.fallbacks import FALLBACKS
    from agent.narrative.prompt_loader import NARRATIVE_PROMPT
    ...
```

**Dockerfile requirement:** If `agent/reasoning/` is modularised, add `COPY agent/reasoning /app/reasoning` alongside the existing `COPY agent/narrative /app/narrative` in `agent/Dockerfile`. Pre-deploy bi-mode container smoke: `docker run --rm --entrypoint python <image> -c 'from reasoning.summaries import summary_simulate_savings; print("OK")'` (Pitfall 4 prevention).

---

### Input Validation (regex gate + ValueError)

**Source:** `lambda/handler.py:39-52`
**Apply to:** New `"detect_bill_shock"` dispatcher branch in `lambda/handler.py`

```python
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

def _validate_customer_id(customer_id: Any) -> str:
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```

Reuse directly — do not re-define.

---

### D-04 Never-500 Fallback

**Source:** `agent/agent.py:396-428`
**Apply to:** D-15 cap-exhaustion branch in `invoke()` — route through this existing `except Exception` path unchanged. The branch inspects `agent_result.stop_reason == "cancelled"` and `raise RuntimeError("tool budget exhausted")` — the existing `except` catches, calls Tools Lambda directly, stitches `FALLBACKS[customer_id]` narrative, and returns a valid recommendation shape (D-04 preserved).

---

### Pure-Helper-Plus-Dispatcher

**Source:** `lambda/handler.py:60-140` (`simulate_savings_pure`), `lambda/handler.py:143-161` (`get_hardship_flag_pure`), `lambda/handler.py:195-230` (dispatcher)
**Apply to:** `detect_bill_shock_pure` (new helper) + `"detect_bill_shock"` dispatcher branch.

Pure helper: signature takes list[dict] billing_history + optional kwargs (rates, threshold), returns dict, raises ValueError on invalid input, NO boto3 / NO env vars / NO I/O.

Dispatcher branch: `_validate_customer_id` upfront, fetch billing via existing `get_billing_history` (PROFILE filter baked in), pass to pure helper, return dict.

---

### `_provider_swap` Autouse Fixture

**Source:** `tests/conftest.py:78-98`
**Apply to:** All offline tests in `tests/test_bill_shock_flow.py` — the autouse fixture is already active repo-wide, so tests just rely on the `InMemoryProvider` being installed. For explicit access, use the `inmemory_provider` fixture at `conftest.py:65-75`.

---

### NARRATIVE_ENABLED Kill-Switch

**Source:** `ui/src/lib/flags.ts:8-9`, `ui/src/components/RecommendationCard.tsx:12, 83-91`
**Apply to:** New `ReasoningTrace.tsx` — early return `if (!NARRATIVE_ENABLED) return null;` at the top of the component function (per D-27, LD-7 single-flag contract).

```typescript
// flags.ts
export const NARRATIVE_ENABLED =
  new URLSearchParams(window.location.search).get('narrative') !== 'off';

// Component usage
import { NARRATIVE_ENABLED } from '@/lib/flags';
if (!NARRATIVE_ENABLED) return null;
```

---

### vitest kill-switch stub pattern

**Source:** `ui/src/components/RecommendationCard.test.tsx:13-31, 119-148`
**Apply to:** All kill-switch test cases in `ReasoningTrace.test.tsx` (D-30 cases 4 + 5).

```typescript
beforeEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.resetModules();
});

// In the kill-switch test:
vi.stubGlobal('location', { search: '?narrative=off' } as Location);
vi.resetModules();
const { ReasoningTrace } = await import('./ReasoningTrace');
```

The `vi.resetModules()` + dynamic `await import(...)` idiom is LOAD-BEARING because `flags.ts` evaluates `URLSearchParams` at module load. Do not refactor.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `agent/hooks/four_tool_cap.py` (NEW) | middleware (Strands hook) | event-driven | First Strands hook in the codebase. No repo precedent. Planner reads `.venv/lib/python3.13/site-packages/strands/hooks/registry.py:89-115` for the `HookProvider` Protocol definition and `.venv/lib/python3.13/site-packages/strands/hooks/events.py:133-158` for `BeforeToolCallEvent` / line 173+ for `AfterToolCallEvent`. RESEARCH §1 (RESEARCH.md lines 144-167) provides the full drop-in `FourToolCapHook` snippet — copy that pattern, not a repo analog. |

---

## Metadata

**Analog search scope:**
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/agent/` (all .py)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/lambda/handler.py`
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/api_lambda/handler.py`
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/src/components/` (all .tsx / .test.tsx)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/src/lib/` (types, flags, mock)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/ui/src/App.tsx`
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/tests/` (conftest, test_simulate_savings, test_agent_tools, test_backend_api_handler, test_narrative_eval_live, test_prewarm_script)
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/scripts/prewarm.py`
- `/Users/drewtaylor/Documents/Cevo/Customer-Tariff/.venv/lib/python3.13/site-packages/strands/hooks/` (SDK-internal for FourToolCapHook)

**Files scanned:** 16 source files + 4 SDK-internal (`strands/hooks/registry.py`, `strands/hooks/events.py`, and referenced types)

**Pattern extraction date:** 2026-04-29

**Key amendments honoured:**
- **A-01** (CUST-002 → CUST-003): reflected in D-19 / D-20 / D-21 / D-29 / D-33 assignments above; mock constant renamed to `MOCK_REASONING_TRACE_CUST003`; Marcus is now the non-shock canary foil.
- **A-02** (max_iterations → HookProvider): `agent/hooks/four_tool_cap.py` is the new file; `agent/agent.py` registers via `hooks=[FourToolCapHook(...)]`; D-15 branch inspects `stop_reason == "cancelled"` and raises `RuntimeError` into the existing D-04 `except`.
- **A-03** (2500ms no headroom): `scripts/prewarm.py` gets 3-pass warming (was 2); gate stays at 2500ms hard; planner schedules a pre-lift "sighting shot" measurement and a break-glass 2-tool-CUST-003 flow if the gate fails.

---

## PATTERN MAPPING COMPLETE

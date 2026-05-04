# Trust Architecture — Customer Tariff & Billing Optimisation Agent

> **Audience:** Presenter, technical reviewer, compliance stakeholder.
> **Framing:** Regulatory-aware architecture — patterns the system supports for safe, auditable AI-assisted customer interactions. No specific AER/Ofgem/state-PUC clauses cited.

---

## 1. Core Principle: Code Does Math, LLM Narrates

The system enforces a strict separation between **deterministic computation** (savings arithmetic) and **generative content** (narrative text). The LLM never performs, estimates, or rounds any calculation. Every dollar figure a customer sees originates from a pure Python function with locked test fixtures.

| Layer | Responsibility | Enforcement |
|-------|---------------|-------------|
| `simulate_savings_pure` (Tools Lambda) | All savings arithmetic — monthly, annual, per-plan | 29+ pytest cases lock byte-exact figures per persona ([`tests/test_simulate_savings.py`](../../../tests/test_simulate_savings.py)) |
| Agent system prompt (SAV-03) | Instructs the LLM: "NEVER compute, estimate, round, or adjust numbers yourself" | Prompt text at [`agent/agent.py`](../../../agent/agent.py) `_BASE_SYSTEM_PROMPT` |
| Cross-persona canary | Verifies different personas produce different reasoning traces (detects fabrication) | [`tests/test_bill_shock_flow.py::TestCrossPersonaCanary`](../../../tests/test_bill_shock_flow.py) |
| Latency-floor witness (D-19) | Sub-1s response on a multi-tool turn = fabrication signature | [`tests/test_narrative_eval_live.py::test_agent01_latency_floor`](../../../tests/test_narrative_eval_live.py) |
| CloudWatch invocation counter (D-21) | Zero Tools Lambda invocations in window = LLM skipped real tool calls | [`tests/test_narrative_eval_live.py::test_agent01_tools_actually_invoked`](../../../tests/test_narrative_eval_live.py) |

**Why this matters for regulation:** Energy retailers operating under consumer protection frameworks must ensure savings claims are accurate and reproducible. By isolating arithmetic in tested, deterministic code, the system provides an auditable chain from raw billing data to the figure shown on screen — independent of LLM behaviour.

---

## 2. Narrative Guardrail — The D-15 Dual-Gate

LLM-generated text passes through two independent validation layers before reaching the customer-facing surface:

### Gate 1: Pydantic Structural Validation
- `usage_narrative`: max 20 words / 140 chars
- `call_script`: max 22 words / 180 chars
- Enforced via `Field(max_length=...)` on the Pydantic model ([`agent/agent.py::TrackInfo`](../../../agent/agent.py))

### Gate 2: Content Validation (Banned-Terms Regex)
A compiled regex rejects any narrative containing:
- **Digits or currency symbols** (`$`, `£`, `€`, `%`) — numbers belong in the deterministic layer, not LLM copy
- **Competitor names** (Origin, AGL, EnergyAustralia, Red Energy, Alinta, Momentum)
- **Switch verbs** (switch, move, change, transfer, swap, shift, convert — all inflections)
- **Environmental superlatives** (greenest, cleanest, carbon-neutral, net-zero, etc.)

Source: [`agent/narrative/banned_terms.py`](../../../agent/narrative/banned_terms.py)
Validators: [`agent/narrative/validators.py`](../../../agent/narrative/validators.py)

### Fallback Bank
When validation fails (either gate), the system falls back to **hand-written, pre-validated strings** committed per persona per track:
- [`agent/narrative/fallbacks.py::FALLBACKS`](../../../agent/narrative/fallbacks.py)
- Every fallback string is tested against the same validators at import time (module-level assertions)
- The `_narrative_source` marker tracks whether each field came from the model or the fallback bank — stripped by the API Lambda before reaching the client, visible in observability logs

**Why this matters:** Regulators scrutinise customer-facing communications for misleading claims. The dual-gate ensures no LLM hallucination — numeric, competitive, or environmental — reaches the customer. The fallback bank guarantees the system always has safe copy to serve, even when the LLM misbehaves.

---

## 3. Hardship Short-Circuit (AGENT-02)

When a customer record carries `hardship_flag: true`, the system refuses to present tariff recommendations entirely. This is a **code-side pre-LLM guard**, not a prompt instruction:

1. Before the LLM sees any tariff context, `invoke()` checks the hardship flag via the `CustomerDataProvider`
2. If flagged, the system returns a `HardshipResponse` (Pydantic discriminated union: `kind: "hardship"`) with a dignity-preserving routing message
3. The LLM never sees tariff plans, savings figures, or recommendation context for hardship customers
4. The API returns HTTP 200 (not 404 or 500) — the D-04 never-500 contract holds

Code path: [`agent/agent.py::invoke()`](../../../agent/agent.py) → `_build_hardship_response()`
Test: adversarial 10-seed test confirms zero plan-ID leak even with hardship prompt instructions removed

**Why this matters:** Vulnerable customers in hardship programs should not receive unsolicited tariff-switching suggestions. The code-side guard ensures this protection cannot be bypassed by prompt injection or LLM misbehaviour — the model literally never sees the data it would need to make a recommendation.

---

## 4. Tool-Call Budget (4-Tool Cap)

The agent's tool-call budget is enforced in code via a Strands `HookProvider`, not via prompt instructions or model parameters:

- [`agent/hooks/four_tool_cap.py::FourToolCapHook`](../../../agent/hooks/four_tool_cap.py) counts completed tool calls
- At budget exhaustion, the hook cancels the agent via `event.agent.cancel()`
- The cancellation routes through the D-04 fallback path — HTTP 200 with fallback narrative, never a 500
- Counter is reset per invocation (SC-3 isolation)

**Why this matters:** Unbounded tool loops are a known failure mode in agentic systems. A code-enforced cap provides a deterministic upper bound on cost, latency, and blast radius per customer interaction.

---

## 5. Observability — `_narrative_source` and Reasoning Trace

Two observability surfaces let operators and reviewers understand what the system did:

### `_narrative_source` Marker
- Attached by the agent to every response: per-field indicator of whether narrative came from the model or the fallback bank
- Stripped by `api_lambda/handler.py` before reaching the client (internal-only)
- Available in CloudWatch logs for post-hoc audit

### Reasoning Trace
- Ordered list of tool calls the agent made, with deterministic summaries composed from tool output (not LLM-generated)
- Surfaced in the UI as a collapsed disclosure row
- D-11 exemption: trace summaries intentionally contain digits, currency, and dates (they are code-composed observability data, not customer-facing narrative)
- Source: [`agent/reasoning/summaries.py`](../../../agent/reasoning/summaries.py)

---

## 6. Never-500 Contract (D-04)

The system guarantees HTTP 200 on every code path:

| Scenario | Response |
|----------|----------|
| Normal recommendation | `kind: "recommendation"` with both Green and Cheapest tracks |
| Hardship customer | `kind: "hardship"` with routing message |
| Tool budget exhausted | Fallback recommendation with committed narrative strings |
| LLM validation failure | Per-field salvage from lenient schema, then fallback bank |
| Unknown customer | HTTP 404 (not 500) — detected by missing tracks + UNKNOWN sentinel |
| Infrastructure timeout | HTTP 504 with retry message |

The final `except Exception` in `invoke()` catches everything and stitches together a response from the deterministic savings engine + fallback narrative. The system never surfaces an unhandled exception to the client.

---

## 7. Memory Isolation (WF-01)

The follow-up email workflow uses AgentCore Memory with strict isolation:

- `actorId = f"customer:{customer_id}"` — scoped to the individual customer
- `session_id = f"{customer_id}-{UTC-ISO-day}"` — deterministic, same-day only
- TTL 8–12 hours — no long-term cross-session retention
- `runtimeSessionId` (Strands session) is a separate fresh UUID per invocation — never conflated with Memory session_id
- Cross-customer isolation canary test: lookup customer A → follow-up customer B → verify zero token leakage from A into B's response

**Why this matters:** Customer data isolation is a regulatory baseline. The architecture ensures that one customer's billing data, savings figures, and recommendation context cannot leak into another customer's interaction — even when the same agent runtime serves both.

---

## Summary: Defence-in-Depth Stack

```
┌─────────────────────────────────────────────────┐
│  UI Kill Switch (?narrative=off)                │  ← Emergency collapse to v1.0 shape
├─────────────────────────────────────────────────┤
│  API Lambda: strip _narrative_source            │  ← Internal markers never reach client
├─────────────────────────────────────────────────┤
│  Hardship Pre-LLM Guard (code-side)            │  ← Vulnerable customers never see tariffs
├─────────────────────────────────────────────────┤
│  4-Tool Cap (HookProvider, code-side)           │  ← Bounded cost/latency per interaction
├─────────────────────────────────────────────────┤
│  D-15 Dual-Gate (Pydantic + banned-terms regex) │  ← No digits/competitors/superlatives
├─────────────────────────────────────────────────┤
│  Fallback Bank (per-persona × per-track)        │  ← Safe copy always available
├─────────────────────────────────────────────────┤
│  SAV-03: Pure Python arithmetic (29+ tests)     │  ← LLM never does math
├─────────────────────────────────────────────────┤
│  Memory Isolation (actor + session + TTL)        │  ← Zero cross-customer leakage
└─────────────────────────────────────────────────┘
```

Every layer is independently testable, independently bypassable for debugging, and independently auditable. The system degrades gracefully — removing any single layer still leaves the others intact.

---

*Document: DOC-01 (REQUIREMENTS.md). Committed as part of Phase 16 (Presenter Artefacts + Operational Consolidation).*
*Evidence chain: every claim above links to a pytest file, code reference, or CloudWatch metric path.*

# Phase 6: Agent Narrative + Guardrail - Research

**Researched:** 2026-04-25
**Domain:** LLM-generated narrative on a Strands structured-output agent, Pydantic v2 field validator as the non-negotiable numeric-exclusion gate, per-field fallback policy, live AgentCore redeploy
**Confidence:** HIGH

## Summary

Phase 6 extends the v1.0 Strands agent's `TrackInfo` model with two validated string fields (`usage_narrative`, `call_script`), wires a belt-and-braces guardrail (system-prompt negative constraint + Pydantic `field_validator` backstop), commits demo-ready per-persona × per-card fallback strings, and ships the extended schema to AgentCore in `us-east-1` via `cdk deploy AgentCoreStack`. The load-bearing invariant is "numbers come from `simulate_savings`, words come from the LLM, and the two must never meet in the prompt" — enforced structurally by a shape-token builder (`agent/narrative/shape.py`) that emits qualitative descriptors only, and enforced by the validator as the safety net.

Every dependency this phase needs is already in the v1.0 runtime: `pydantic>=2.4.0,<3.0.0` is pulled transitively by `strands-agents==1.37.0` (HIGH-confidence verification via upstream `pyproject.toml`), so `@field_validator`, `ValidationError`, and `Field(max_length=...)` are directly available — no new runtime deps. No IAM change, no new CDK stack, no new Lambda. The risk surface is the validator + prompt + fallback copy + live smoke.

A key upstream finding resolves SUMMARY.md Gap #3 (Strands retry-on-`ValidationError` behaviour): **Strands 1.37.0 does NOT retry on Pydantic `ValidationError`**. The `BedrockModel.structured_output` implementation (`src/strands/models/bedrock.py`, v1.37.0) yields `output_model(**output_response)` directly — any `ValidationError` propagates immediately to the caller. The `ModelRetryStrategy` hook only retries on `ModelThrottledException`. This confirms D-01's retry-in-`invoke()` approach is the only retry path — no double-retry compounding.

**Primary recommendation:** Implement the phase as a pure-Python extension inside the existing `agent/` package — add `agent/narrative/{shape.py, banned_terms.py, fallbacks.py, prompt.txt}` plus two validators on `TrackInfo`, wire retry-once-then-per-field-fallback in `invoke()`, deploy via `cdk deploy AgentCoreStack`, smoke each persona live once.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**Validator Failure Behaviour**
- **D-01:** On `ValidationError` from the narrative `field_validator`, the handler catches the exception in `invoke()` and issues exactly **one** retry of `structured_output()` with the same prompt. On second failure, swap the offending narrative field to the committed fallback string. Retry is owned in `invoke()` — not delegated to Strands — for predictability, greppability, and survival across Strands SDK upgrades.
- **D-02:** Fallback is **per-field**, not per-response. If `usage_narrative` fails but `call_script` passes (or vice versa), only the failing field swaps to fallback. If both fail, both swap independently. Response always returns 200 with v1.0 `$30` / `$55` numbers intact — numbers are never at risk from a narrative miss.
- **D-03:** When a fallback fires, emit (a) a CloudWatch structured log entry with `narrative_fallback_fired=true`, the field name, persona/`customer_id`, and card track; AND (b) an internal response marker field `_narrative_source: {"usage_narrative": "model"|"fallback", "call_script": "model"|"fallback"}`. The marker is stripped by the API Lambda in Phase 7 and never reaches the UI — Phase 9's eval harness uses it to assert which path fired.
- **D-04:** Under no circumstances does Phase 6 return HTTP 500 or an empty-narrative response on validation failure. The fallback strings are themselves guaranteed validator-passing (enforced by a dedicated pytest).

**Fallbacks + Prompt Strategy**
- **D-05:** Fallback strings live in `agent/narrative/fallbacks.py` as a typed Python constant dict keyed by `customer_id` → `{"green": {"usage_narrative": str, "call_script": str}, "cheapest": {...}}`. Imported once at agent module load. Frozen at DEMO-04.
- **D-06:** The 6 fallback strings are demo-ready copy, written during Phase 6 against the persona profiles in `infrastructure/seed_data/billing_records.py`. They must pass every rule the `field_validator` enforces.
- **D-07:** The LLM sees **shape-tokens only** — never raw kWh, never dollar values. Shape-tokens are qualitative descriptors derived in pure Python. Structural "numbers can't leak" guarantee.
- **D-08:** `build_shape_tokens(billing_history, plan) -> dict[str, str]` is a new pure-Python helper in `agent/narrative/shape.py`. Called from `invoke()` before the prompt is assembled.
- **D-09:** Three few-shot exemplars total — Sarah-green, Marcus-cheapest, Elena-green. Middle-ground prompt size.
- **D-10:** Extended system prompt lives in `agent/narrative/prompt.txt`, loaded once by a `load_prompt()` helper at module import.

**Banned-Terms List**
- **D-11:** Banned-terms list lives in `agent/narrative/banned_terms.py` as three tuple constants: `COMPETITORS`, `SWITCH_VERBS`, `ENV_SUPERLATIVES`.
- **D-12:** `COMPETITORS = ("Origin", "AGL", "EnergyAustralia", "Red Energy", "Alinta", "Momentum")` — non-negotiable.
- **D-13:** `SWITCH_VERBS` and `ENV_SUPERLATIVES` drafted by Claude in Phase 6 planning (starter sets: switch/move/change/transfer/swap/shift/convert + inflections; greenest/cleanest/most sustainable/carbon-neutral/zero-emission/net-zero/best for the planet + similar). Expand during PR review; do not expand inside the DEMO-04 freeze window.
- **D-14:** Case-insensitive word-boundary regex, compiled once at module load: `re.compile(r"\b(term1|term2|…)\b", re.IGNORECASE)`.
- **D-15:** Banned terms **both** injected as a negative constraint in the system prompt AND hard-enforced by the `field_validator`. Dual gate.

### Claude's Discretion
- **Length caps (words + chars):** Pydantic model must express both. Default to the stricter of the two on conflict.
- **Test + deploy gate timing:** Success criterion 5 requires the deployed image in us-east-1 — so at minimum a single-persona live smoke. Planner decides corpus size for poisoned-string injection (recommend ≥3 per banned category).
- **Sample-capture artefact:** `06-SAMPLES.md` or pytest fixture snapshots.
- **Retry logging detail:** Default — log failure reason + persona/card, NOT raw output.
- **Shape-token vocabulary:** Exact set of descriptors. Documented in `shape.py` as the contract fed to the LLM.
- **Pydantic version sanity-check:** Research-phase resolves (see §Pydantic Version Sanity-Check below).

### Deferred Ideas (OUT OF SCOPE)
- Presenter tooltip (alt-click reveals raw LLM + verdict) — Phase 8.
- Haiku fallback path — locked OUT OF SCOPE for v2.0.
- Hard in-Lambda timeout budget (narrative <1500ms else fallback) — Phase 7 (API Lambda).
- `agent/narrative/SHAPE-TOKENS.md` standalone reference — Phase 8 design review.
- CloudWatch alarm on `retry_count > 0` — v3.0 production hardening.
- FEATURES.md anti-feature "LLM quoting dollar figures" distribution tests — Phase 9.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-03 | LLM-generated call-script snippet per card. Second-person voice. ≤22 words. No digits/`$`/`£`/`€`/`%`. No switch verbs, competitor references, environmental superlatives. (backend half) | §Pydantic Model Pattern, §Banned-Terms Regex, §Fallback String Contract |
| UI-04 | LLM-generated usage-narrative sentence per card. Third-person descriptive voice. ≤20 words. Same forbidden-content rules as UI-03. No prescription, no second-person pronouns. (backend half) | §Pydantic Model Pattern, §Shape-Token Vocabulary, §Fallback String Contract |
| UI-05 | Narrative-output validator enforces `max_length` caps and rejects any string containing `$`, `£`, `€`, `%`, or any digit, plus banned-terms list. Validator is a Pydantic `field_validator` — a hard code-level gate. Failure falls back to per-persona × per-card committed fallback string. | §Pydantic Model Pattern, §Validator Retry Semantics, §Fallback String Contract |

## Project Constraints (from CLAUDE.md)

No `./CLAUDE.md` exists in the repo root as of 2026-04-25. Project conventions are enforced via existing test patterns and code structure (see §Code Patterns to Reuse). `[VERIFIED: ls of repo root]`

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Narrative generation | Agent (Strands + Bedrock) | — | LLM is the only tier that can produce natural-language text. Generation happens in the same turn as `simulate_savings` so numbers stay in context. `[VERIFIED: ARCHITECTURE.md Option A]` |
| Shape-token derivation | Agent (pure Python helper) | — | Derived from tool return values before the LLM prompt is assembled. Pure function, no AWS, unit-testable. Keeps the "LLM never sees numbers" invariant structural rather than only prompt-level. `[VERIFIED: CONTEXT.md D-07, D-08]` |
| Field-level validation | Agent (Pydantic `field_validator`) | — | Runs at `output_model(**output_response)` inside `BedrockModel.structured_output`. `[VERIFIED: strands-agents/sdk-python v1.37.0 src/strands/models/bedrock.py]` |
| Retry-once-on-validation-failure | Agent `invoke()` entrypoint | — | Owned in user code, not Strands. Strands 1.37.0's only retry is `ModelRetryStrategy` for throttling (`ModelThrottledException`). `[VERIFIED: strands-agents/sdk-python v1.37.0 src/strands/event_loop/_retry.py]` |
| Per-field fallback swap | Agent `invoke()` | — | Applied after second validation failure. Strips offending field, inserts fallback string keyed on `customer_id` × card track. `[CITED: CONTEXT.md D-02]` |
| CloudWatch structured logging | Agent runtime container | — | `logger.info(..., extra={...})` pattern emits JSON fields when Lambda/AgentCore log format is JSON-configured. AgentCore uses ECS-style container logs — stdout is captured. `[VERIFIED: AWS Lambda Python docs]` |
| `_narrative_source` marker stripping | API Lambda | — | Phase 7 responsibility. Not in Phase 6 scope — but Phase 6 MUST emit the marker so Phase 7 has something to strip. `[CITED: CONTEXT.md D-03]` |
| Live deployment | `cdk deploy AgentCoreStack` | — | Rebuilds agent Docker image from `agent/` directory, pushes to CDK-managed ECR, rolls AgentCore runtime to new image. `[VERIFIED: infrastructure/agentcore_stack.py, infrastructure/constructs/agent_runtime.py]` |

## Standard Stack

### Core (all already installed — no new runtime deps)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pydantic` | `>=2.4.0,<3.0.0` (transitive) | Structured output schema + `field_validator` + `Field(max_length=...)` | Pulled by `strands-agents==1.37.0` per its `pyproject.toml`. v2 decorator-based validator syntax is the stable public API. `[VERIFIED: github.com/strands-agents/sdk-python v1.37.0 pyproject.toml]` |
| `strands-agents` | `1.37.0` | `Agent.structured_output()` for Bedrock tool-calling + structured return | Already pinned in `agent/requirements.txt`. No bump. `[VERIFIED: agent/requirements.txt]` |
| `bedrock-agentcore` | `1.6.3` | `BedrockAgentCoreApp` runtime wrapper (`/invocations`, `/ping`) | Already pinned. No bump. `[VERIFIED: agent/requirements.txt]` |
| `boto3` | `>=1.42.0` | Lambda invocation (fallback path retained); runtime SDK for `invoke_agent_runtime` in tests | Already pinned. No bump. `[VERIFIED: agent/requirements.txt]` |
| Python stdlib `re` | 3.12 | Compiled regex for banned-terms + `[$£€%]|\d` | Zero-dep. No spaCy / NLP library — keeps Lambda bundle slim. `[VERIFIED: CONTEXT.md D-14]` |
| Python stdlib `logging` | 3.12 | Structured CloudWatch logging via `logger.info(msg, extra={...})` | Already in use at `agent.py:20`. `[VERIFIED: agent/agent.py]` |

### Alternatives Considered (and explicitly rejected)

| Instead of | Could Use | Tradeoff | Why Rejected |
|------------|-----------|----------|--------------|
| Pydantic `field_validator` + manual retry | Strands `ModelRetryStrategy` with custom Pydantic-error check | SDK-native retry integration | Strands `ModelRetryStrategy` only catches `ModelThrottledException` — it does NOT catch `ValidationError`. Custom hook would need new HookProvider; adds surface for zero gain. `[VERIFIED: strands-agents/sdk-python v1.37.0]` |
| `re.compile` banned-terms | spaCy NLP | Handles inflections, synonyms automatically | Adds ~50MB wheel to Lambda bundle, +500ms cold-start. Banned-terms list is small (~25 tokens); regex is deterministic and benchmarks at 3.5µs/validation. `[VERIFIED: benchmark run 2026-04-25]` |
| Python dict for fallbacks | YAML/JSON file | Easier to review copy separately | Python module = module-level constant, import-time load, no I/O. Copy-review in PR diff works the same on `.py`. `[CITED: CONTEXT.md D-05]` |
| `print(json.dumps({...}))` | Python `logger.info(msg, extra={...})` | Simpler | AgentCore runtime captures stdout, but `logger` provides level filtering and is the existing project convention (`agent.py:20`). `[VERIFIED: agent/agent.py]` |

**Installation:** No action required. All deps are in `agent/requirements.txt` at pinned v1.0 versions.

**Version verification (run during implementation planning):**
```bash
pip3 install pydantic pytest --target /tmp/v6-check
python3 -c "import pydantic; print(pydantic.VERSION)"
# Expect: 2.x.y (any v2, since strands-agents 1.37.0 pins >=2.4.0,<3.0.0)
```

## Architecture Patterns

### System Architecture Diagram (Phase 6 hot path)

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          AgentCore Runtime microVM                       │
│                     (container built from agent/Dockerfile)              │
│                                                                          │
│   ┌─────────────────┐                                                    │
│   │ invoke(payload) │   ← /invocations (BedrockAgentCoreApp)             │
│   └────────┬────────┘                                                    │
│            │                                                             │
│            │ 1. customer_id extracted                                    │
│            ▼                                                             │
│   ┌──────────────────────────────────────────────┐                       │
│   │ get_billing_history + simulate_savings       │  (tool path —         │
│   │ via @tool → _lambda_client.invoke(ToolsArn)  │   unchanged from v1)  │
│   └──────────────────────┬───────────────────────┘                       │
│                          │  billing_history, plan                        │
│                          ▼                                               │
│   ┌──────────────────────────────────────────────┐                       │
│   │ NEW: build_shape_tokens(billing, plan)       │  (pure Python,        │
│   │  → {season: "winter_heavy",                  │   agent/narrative/    │
│   │     usage_tier: "high",                      │   shape.py)           │
│   │     renewable_profile: "eco_aligned", ...}   │                       │
│   └──────────────────────┬───────────────────────┘                       │
│                          │  shape_tokens                                 │
│                          ▼                                               │
│   ┌──────────────────────────────────────────────┐                       │
│   │ Compose narrative prompt =                   │                       │
│   │   SYSTEM_PROMPT + prompt.txt + shape_tokens  │                       │
│   │ (numbers absent by construction)             │                       │
│   └──────────────────────┬───────────────────────┘                       │
│                          │                                               │
│                          ▼                                               │
│   ┌──────────────────────────────────────────────┐                       │
│   │ _agent.structured_output(                    │                       │
│   │     RecommendationResponse,                  │                       │
│   │     narrative_prompt)                        │                       │
│   │                                              │                       │
│   │ Inside Strands:                              │                       │
│   │   Bedrock stream → tool_use → JSON input     │                       │
│   │   → output_model(**input)                    │                       │
│   │           │                                  │                       │
│   │           ▼                                  │                       │
│   │   @field_validator runs here                 │                       │
│   │   ValidationError propagates ──────────┐    │                       │
│   └────────┬─────────────────────────────────┼───┘                       │
│            │ success                         │ ValidationError           │
│            │                                 ▼                           │
│            │              ┌──────────────────────────────────────┐       │
│            │              │ NEW: invoke() catches ValidationError │       │
│            │              │ RETRY ONCE — same prompt              │       │
│            │              │   success → continue                  │       │
│            │              │   second failure → PER-FIELD FALLBACK │       │
│            │              │     swap to FALLBACKS[cust][track]    │       │
│            │              │     log narrative_fallback_fired      │       │
│            │              │     set _narrative_source.<field>=    │       │
│            │              │         "fallback"                    │       │
│            │              └──────────────────┬───────────────────┘       │
│            │                                 │                           │
│            ▼                                 ▼                           │
│   ┌──────────────────────────────────────────────┐                       │
│   │ RecommendationResponse.model_dump() +        │                       │
│   │   _narrative_source marker field             │                       │
│   │   (stripped by API Lambda in Phase 7)        │                       │
│   └──────────────────────┬───────────────────────┘                       │
│                          │                                               │
│                          ▼                                               │
│                     return dict                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| `TrackInfo` (extended) | `agent/agent.py` | Pydantic model with 4 existing fields + 2 new validated string fields |
| `_narrative_validator` | `agent/narrative/validators.py` (new) | Shared `field_validator` logic: no digits, no currency, no banned terms, max_length enforcement |
| `build_shape_tokens()` | `agent/narrative/shape.py` (new) | Pure function: billing history → qualitative descriptors |
| `BANNED_REGEX`, `COMPETITORS`, `SWITCH_VERBS`, `ENV_SUPERLATIVES` | `agent/narrative/banned_terms.py` (new) | Compiled-once regex constants |
| `FALLBACKS` | `agent/narrative/fallbacks.py` (new) | Committed `{customer_id: {track: {field: str}}}` dict |
| `load_prompt()` | `agent/narrative/prompt_loader.py` (new) or inline in `agent.py` | One-shot read of `prompt.txt` at module load |
| `prompt.txt` | `agent/narrative/prompt.txt` (new) | Narrative rules + 3 few-shot exemplars |
| `invoke()` (extended) | `agent/agent.py` | Retry-once-then-per-field-fallback policy wiring |
| Docker build | `agent/Dockerfile` | Must `COPY agent/narrative/` into the image — verify pattern (see §Pitfalls) |

### Recommended Project Structure
```
agent/
├── agent.py                    # extended TrackInfo + retry logic in invoke()
├── Dockerfile                  # may need COPY update — see Pitfalls
├── requirements.txt            # unchanged
└── narrative/                  # NEW package
    ├── __init__.py             # empty / re-exports
    ├── banned_terms.py         # COMPETITORS, SWITCH_VERBS, ENV_SUPERLATIVES, BANNED_REGEX
    ├── shape.py                # build_shape_tokens(billing, plan) -> dict[str, str]
    ├── fallbacks.py            # FALLBACKS dict (6 strings, frozen at DEMO-04)
    ├── validators.py           # _narrative_validator classmethod
    ├── prompt_loader.py        # load_prompt() helper (reads prompt.txt once)
    └── prompt.txt              # narrative rules + 3 exemplars

tests/
├── test_narrative_validator.py # NEW — poisoned-string corpus, fallback passes validator
├── test_shape_tokens.py        # NEW — shape-token builder, no numbers leak
├── test_agent_tools.py         # unchanged — v1.0 regression suite
├── test_agent_smoke.py         # EXTEND — assert narrative fields present + validator-passing
├── test_schema.py              # unchanged
└── conftest.py                 # extend with mock_trackinfo fixture
```

### Pattern 1: Pydantic v2 `@field_validator` with `mode="after"` + `ValidationInfo`

**Source:** [VERIFIED: pydantic.dev/docs/validation/latest/concepts/validators/]

```python
# agent/narrative/validators.py
import re
from pydantic import field_validator, ValidationInfo
from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX

# Rule set:
#   - Reject any digit 0-9
#   - Reject any currency symbol $ £ € %
#   - Reject any banned term (word-boundary, case-insensitive)
#   - Word count enforced (stricter of word-count or max_length wins)

def _reject_forbidden(value: str, max_words: int, field_label: str) -> str:
    """Raises ValueError (which Pydantic converts to ValidationError)."""
    if NUMERIC_REGEX.search(value):
        raise ValueError(f"{field_label}: contains forbidden digit or currency symbol")
    m = BANNED_REGEX.search(value)
    if m:
        raise ValueError(f"{field_label}: contains banned term {m.group()!r}")
    words = value.split()
    if len(words) > max_words:
        raise ValueError(f"{field_label}: {len(words)} words exceeds cap {max_words}")
    return value.strip()


# Applied on TrackInfo as classmethod validators:
class TrackInfo(BaseModel):
    # ... existing fields ...
    usage_narrative: str = Field(..., max_length=140)  # char cap
    call_script: str = Field(..., max_length=180)

    @field_validator("usage_narrative", mode="after")
    @classmethod
    def _validate_usage_narrative(cls, value: str, info: ValidationInfo) -> str:
        return _reject_forbidden(value, max_words=20, field_label="usage_narrative")

    @field_validator("call_script", mode="after")
    @classmethod
    def _validate_call_script(cls, value: str, info: ValidationInfo) -> str:
        return _reject_forbidden(value, max_words=22, field_label="call_script")
```

**Notes:**
- `mode="after"` (default) runs AFTER type coercion — value is already a `str`. Safer than `mode="before"` where input could be any type. `[VERIFIED: pydantic.dev/docs/validation/latest/concepts/validators/]`
- `ValidationInfo.info.data` exposes sibling fields already validated — available for cross-field checks (e.g. reading `plan_name` for debug log context). Pydantic validates fields in definition order. `[VERIFIED: pydantic.dev/docs/validation/latest/concepts/validators/]`
- `Field(max_length=...)` enforces character count; the validator enforces word count. Both apply. "Stricter wins" is automatic — whichever fails first raises. Per CONTEXT.md Claude's Discretion.
- The `@classmethod` decorator is required on `@field_validator` in Pydantic v2 (distinct from v1 `@validator`). `[VERIFIED: pydantic.dev]`

### Pattern 2: Retry-once-then-per-field-fallback in `invoke()`

```python
# agent/agent.py (extended)
from pydantic import ValidationError
from agent.narrative.fallbacks import FALLBACKS
from agent.narrative.shape import build_shape_tokens

@app.entrypoint
def invoke(payload: dict) -> dict:
    customer_id = payload.get("customer_id", "")
    if not customer_id:
        return {"error": "customer_id is required in the payload"}

    # Shape-tokens derived from billing_history (pure Python)
    # Note: build_shape_tokens may call the tool itself OR the tool result
    #       is passed in; see §Shape-Token Vocabulary for contract.

    narrative_source = {"usage_narrative": "model", "call_script": "model"}

    try:
        result = _agent.structured_output(RecommendationResponse, _build_prompt(customer_id))
    except ValidationError:
        logger.warning("narrative validator failed, retrying once", exc_info=False)
        try:
            result = _agent.structured_output(RecommendationResponse, _build_prompt(customer_id))
        except ValidationError as e:
            # Second failure — apply per-field fallback.
            # _narrative_fallback_salvage() returns a valid RecommendationResponse
            # with offending fields replaced from FALLBACKS.
            result, narrative_source = _narrative_fallback_salvage(
                customer_id, e, logger
            )

    body = result.model_dump()
    body["_narrative_source"] = narrative_source  # stripped by API Lambda in Phase 7
    return body
```

**Critical behavioural guarantees:**
- `ValidationError` propagates cleanly out of Strands' `structured_output` — the retry path owns the retry. `[VERIFIED: strands-agents/sdk-python v1.37.0 src/strands/models/bedrock.py line "yield {\"output\": output_model(**output_response)}"]`
- Strands' `ModelRetryStrategy` does NOT fire on `ValidationError` — only on `ModelThrottledException`. No double-retry. `[VERIFIED: strands-agents/sdk-python v1.37.0 src/strands/event_loop/_retry.py]`
- The existing v1.0 `try/except Exception` fallback path (`agent.py` L130-148) catches a different failure mode (tool-call errors, network errors). Keep it distinct — narrative `ValidationError` must NOT fall through to the direct-Lambda fallback, because that path returns tool output with no narrative fields at all, which would fail the extended schema contract. Add the `ValidationError` branch BEFORE the bare `Exception` catch.

### Pattern 3: Salvage helper — per-field fallback inference from ValidationError

When the second retry fails, we need to identify WHICH field failed to decide what to swap. Pydantic `ValidationError.errors()` returns a list of per-field error dicts:

```python
# Inspecting ValidationError.errors() in Pydantic v2:
# [
#   {"type": "value_error", "loc": ("green", "usage_narrative"), "msg": "...", ...},
#   {"type": "value_error", "loc": ("cheapest", "call_script"), "msg": "...", ...},
# ]
```

**Salvage strategy (two viable approaches — planner picks):**

1. **Re-parse the raw LLM output manually:** Strands returns the parsed Pydantic object or raises; the raw JSON isn't directly exposed. Harder.
2. **Pre-validate against a lenient intermediate model:** Make a `_TrackInfoLenient` with no validators, parse into that on the retry path, then per-field decide model-vs-fallback based on calling `_reject_forbidden` individually. **Recommended.** Matches the "per-field fallback" lock in D-02.

```python
class _TrackInfoLenient(BaseModel):
    """Same fields as TrackInfo but no narrative validators — used for salvage."""
    # ... all TrackInfo fields without @field_validator decorators ...

class _RecommendationResponseLenient(BaseModel):
    green: _TrackInfoLenient
    cheapest: _TrackInfoLenient
```

On the second retry, attempt structured_output against the lenient schema; then per-track, per-field, run `_reject_forbidden` standalone. Fields that pass keep the LLM output. Fields that fail swap to `FALLBACKS[customer_id][track][field]`.

**Tradeoff flag:** This requires Strands to accept a different Pydantic class on retry — confirmed OK since `structured_output` takes the model class as its first argument and converts it to a tool-spec per invocation (`convert_pydantic_to_tool_spec(output_model)` in `BedrockModel.structured_output`). `[VERIFIED: strands-agents/sdk-python v1.37.0 src/strands/models/bedrock.py]`

### Pattern 4: CloudWatch structured logging via `extra=`

**Source:** [VERIFIED: docs.aws.amazon.com/lambda/latest/dg/python-logging.html]

```python
# When Lambda/AgentCore log format is set to JSON (advanced logging controls),
# the stdlib `logging` module emits true JSON with custom fields when passed via `extra=`:

logger.info(
    "narrative fallback fired",
    extra={
        "narrative_fallback_fired": True,
        "field": "usage_narrative",
        "customer_id": customer_id,
        "track": "green",
        "failure_reason": str(err),  # per D-Claude's Discretion: reason, not raw output
    },
)
```

CloudWatch Insights can then query:
```
fields @timestamp, customer_id, track, field, failure_reason
| filter narrative_fallback_fired = 1
```

**AgentCore-specific note:** AgentCore microVM containers capture stdout as CloudWatch logs. The stdlib `logging` root logger writes to stderr by default. Verify at Phase 6 live-smoke time that `logger.info(...)` entries appear in the AgentCore runtime's log group. If they don't, fall back to `print(json.dumps({...}))` — Lambda documentation confirms plain text capture at minimum, and including `"level"` + `"timestamp"` keys in the JSON enables Lambda's built-in JSON log detection. `[VERIFIED: AWS Lambda python-logging docs 2026-04-25]`

### Anti-Patterns to Avoid

- **Don't use `mode="before"` validators for string-content rules.** `mode="after"` runs on a coerced `str` value — safer, simpler, and matches the deceptively-simple shape of the checks. `[VERIFIED: pydantic.dev validators concepts]`
- **Don't mark new narrative fields `Optional`.** The response contract guarantees both always present. Fallback handles the "failed" case at the value level, not via schema optionality. `[CITED: CONTEXT.md Code Insights]`
- **Don't let the v1.0 bare `Exception` catch swallow `ValidationError`.** Order matters: add `except ValidationError` BEFORE the fallback `except Exception`, or the retry never fires.
- **Don't hand-roll string content matching.** Use compiled regex once at module load. Avoid `any(term in s for term in TERMS)` — that misses case and boundary semantics (`origin` vs `original`). `[VERIFIED: benchmark run 2026-04-25]`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| JSON schema enforcement on LLM output | Custom regex `.*"usage_narrative"\s*:\s*"(.*?)".*` | Pydantic `BaseModel` + Strands `structured_output` | v1.0 already uses it. Validation failures raise typed `ValidationError`. Tool-use mode guarantees valid JSON structure before Pydantic runs. |
| String content filtering (banned terms) | `for term in BANNED: if term.lower() in value.lower():` | `re.compile(r"\b(term1|term2)\b", re.IGNORECASE)` compiled once | Word-boundary semantics (case-insensitive). Benchmarks at 3.5µs/call. Handles "origin" ≠ "original" correctly. `[VERIFIED: benchmark]` |
| Length caps | Manual `len(value) > N` or `len(value.split()) > N` checks inline | `Field(max_length=N)` for char cap, `@field_validator` for word cap | Pydantic raises `ValidationError` with proper `.loc` tuples, caught cleanly by the retry path. |
| LLM retry on validation | Roll your own `for _ in range(N):` with backoff | Single manual retry in `invoke()` (D-01) + Strands' own `ModelRetryStrategy` for throttling | Strands' throttling retry handles transient Bedrock errors. The validator retry (single attempt) handles prompt-level misses. Separating concerns means throttle-plus-validator-failure chains don't multiply latency unboundedly. |
| CloudWatch JSON serialisation | `json.dumps(dict) + "\n"` to stdout | `logger.info(msg, extra={...})` with Lambda JSON log format | Native Python stdlib; preserves level filtering; CloudWatch Insights-queryable. |
| Prompt templating | f-strings with manual exemplar escaping | `prompt.txt` loaded once at module init (D-10) | Escaping curly braces for `{plan}` placeholders inside exemplars is a well-known trap. Plain text file avoids it. |

**Key insight:** Every "I'll just write the 20 lines myself" temptation here has a standard library or Pydantic primitive. The Lambda bundle weight matters (AgentCore microVM cold-start cost) — keep the dependency footprint minimal, use stdlib and what Strands already brings.

## Runtime State Inventory

> Phase 6 is a code-and-deploy phase, not a rename/refactor. An inventory is still useful because Phase 6 DEPLOYS to `us-east-1` and the deployment interacts with pre-existing runtime state.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. Narrative is generative per-invocation, not persisted. DynamoDB billing/tariff tables are unchanged. | None. |
| Live service config | AgentCore runtime `tariff_agent` currently serves v1.0 schema (4 fields per track). `cdk deploy AgentCoreStack` rolls the container to the v2.0 image. | `cdk deploy AgentCoreStack` in Phase 6 Wave N. Verify `AgentRuntimeArn` remains stable (it should — same logical resource, new image). `[VERIFIED: infrastructure/agentcore_stack.py]` |
| OS-registered state | None — AgentCore runtime lifecycle is AWS-managed. | None. |
| Secrets/env vars | `TOOLS_LAMBDA_ARN` + `AWS_REGION` env vars injected via CDK (`agent_runtime.py` L40-44). Phase 6 adds NO new env vars. | None. |
| Build artifacts | Current ECR image for `tariff_agent` will be replaced. Old image retained in ECR until CDK garbage-collects (standard CDK asset behaviour). | None — replacement is idempotent. |

**Nothing found in category:** State explicitly ("None — verified by reading `infrastructure/constructs/agent_runtime.py` and `infrastructure/agentcore_stack.py`").

## Common Pitfalls

### Pitfall 1: Dockerfile COPY pattern doesn't pick up `agent/narrative/`

**What goes wrong:** The current `agent/Dockerfile` (line 8) copies only `COPY agent.py .` — it does NOT do `COPY agent/ /app/agent/`. If Phase 6 adds `agent/narrative/*.py`, the `cdk deploy` will build an image that's missing the narrative package. Import fails at container startup. Live smoke fails on first invocation.

**Why it happens:** The Dockerfile was written when `agent/` had one file. The assumption in CONTEXT.md Code Insights ("`COPY agent/ /app/agent/` already includes any new `agent/narrative/` subdirectory — verify during planning") is WRONG based on the actual Dockerfile contents.

**How to avoid:** Update the Dockerfile BEFORE any `cdk deploy`:
```dockerfile
# Replace line 8:
#   COPY agent.py .
# With:
COPY agent.py .
COPY narrative/ ./narrative/
```
Or, more robustly, copy the whole package: `COPY . /app/` (assuming the CDK asset is scoped to `agent/`). Verify by running `docker build` locally and `docker run --rm <image> ls /app/narrative/` before deploying. `[VERIFIED: agent/Dockerfile contents]`

**Warning signs:** `ModuleNotFoundError: No module named 'agent.narrative'` or similar at container startup. CloudWatch logs for the AgentCore runtime will show Python traceback on first invocation.

### Pitfall 2: Import-time circular dependencies between `agent.py` and `agent/narrative/`

**What goes wrong:** `agent/agent.py` imports `TrackInfo` (defines schema with validators from `agent/narrative/validators.py`); `validators.py` needs `banned_terms.py`; `banned_terms.py` is standalone. If `agent.py` itself imports from a submodule that imports `agent.py`, circular-import error at cold start. Not common but possible with `FALLBACKS` keyed on persona IDs — if fallbacks.py imports the agent for tooling, circular.

**How to avoid:** Keep `agent/narrative/*.py` as leaf modules — they import from stdlib + Pydantic only. `agent.py` imports FROM narrative submodules, not the other way. Run `python -c "import agent.agent"` locally before deploying.

**Warning signs:** `ImportError: cannot import name 'X' from partially initialized module 'agent'`.

### Pitfall 3: Strands `structured_output` is deprecated in 1.37.0

**What goes wrong:** The existing `agent.py` uses `_agent.structured_output(RecommendationResponse, "...")`. This method emits a `DeprecationWarning` in 1.37.0. `[VERIFIED: src/strands/agent/agent.py line 573]` It still works, but:
- Tests that capture warnings may fail.
- Future Strands upgrades may remove the method.

**How to avoid for Phase 6:** Keep using `structured_output()` — v1.0 ships with it working and Phase 6 is explicitly scoped to NOT re-architect the agent. Add `pytest.warns(DeprecationWarning)` filter in `conftest.py` or `pytest.ini` so the warning doesn't pollute CI output. Flag the migration to the new "pass `structured_output_model` directly into agent invocation" pattern as a v3.0 consideration — out of scope per CONTEXT.md Deferred.

**Warning signs:** New test failures mentioning DeprecationWarning in `agent.structured_output`.

### Pitfall 4: Fallback strings that accidentally contain banned terms

**What goes wrong:** Copy author writes `"Sarah typically uses more energy in cooler months — consider moving to EcoFlex 100."` — contains the banned switch verb "moving". When the LLM fails and the fallback fires, the fallback ALSO fails validation (if it's re-validated), causing the response to have no narrative at all, violating D-04 (never 500, never empty).

**How to avoid:** 
1. `fallbacks.py` imports `FALLBACKS` as a module-level constant.
2. A dedicated pytest (`test_fallbacks_pass_validator.py`) imports `FALLBACKS` and runs every string through `_reject_forbidden` directly. Blocks the merge if any fails. `[CITED: CONTEXT.md Specifics]`
3. When invoking the fallback path, the fallback string is swapped in by `invoke()` AFTER structured_output — it is NOT re-run through Pydantic validation. This makes the pytest the single guarantor of validity. `[CITED: CONTEXT.md D-04]`

**Warning signs:** `test_fallbacks_pass_validator` fails. A live smoke returns `"Ask about EcoFlex 100 — it suits a strong winter-heating profile like yours."` (no numbers, no banned terms — this is the target shape).

### Pitfall 5: Shape-tokens leak a raw figure

**What goes wrong:** Author writes `build_shape_tokens()` and includes `"saving_band": f"${saving:.0f}"` — now the LLM sees a dollar figure in the prompt tokens. Structural invariant broken. On some invocations the LLM repeats that figure, contradicting the card header.

**How to avoid:**
1. `build_shape_tokens` emits **string enums only** — no f-strings with numeric substitution. Example vocabulary below.
2. Unit test: `test_shape_tokens_no_numerics.py` — for every persona, run `build_shape_tokens()` and assert every value in the returned dict matches `^[a-z_]+$` (or explicit allowed-vocabulary regex). Zero digits, zero `$`.
3. The validator is belt; shape-token test is braces. Both layers catch the same rule at different cost points.

**Warning signs:** Pytest `test_shape_tokens_no_numerics` fails. Eval harness (Phase 9) shows numeric tokens in narrative output above the normal ~0% baseline.

### Pitfall 6: Word-count vs. char-count conflict (D-Claude's Discretion)

**What goes wrong:** `usage_narrative` has `max_length=140` (char cap per ARCHITECTURE.md) and `max_words=20` (per REQUIREMENTS.md UI-04). A 20-word sentence can easily exceed 140 chars (avg 7 chars/word). A 140-char sentence can be <20 words. The CONTEXT directive "default to the stricter of the two" means:

- If generated text is 22 words but 130 chars: word-validator rejects it (22 > 20). Char cap is silent.
- If generated text is 18 words but 160 chars: `Field(max_length=140)` rejects it. Word validator never runs.
- Both rejections propagate to the same `ValidationError` handler.

**How to avoid:** Express both caps in code and let Pydantic short-circuit. The test corpus in `test_narrative_validator.py` MUST include:
- A string that fails char cap but passes word cap (long words).
- A string that fails word cap but passes char cap (many short words).
- A string that fails both.
- A string at exactly the cap boundaries (20 words / 22 words / 140 chars / 180 chars).

**Warning signs:** A well-formed 20-word narrative is unexpectedly rejected — check if char cap is the tripping constraint.

### Pitfall 7: Docker build uses x86_64 on ARM64 runtime

**What goes wrong:** CDK asset in `agent_runtime.py` L30-34 pins `platform=ecr_assets.Platform.LINUX_ARM64`. If a developer runs `docker build` on an x86_64 Mac and tests locally against an x86_64 image, works fine; but `cdk deploy` builds ARM64 for AgentCore. Any arch-sensitive dep (unlikely with Pydantic-only Phase 6) mismatches.

**How to avoid:** Standard CDK asset handling is correct — no code change. Verify `cdk deploy` output shows `linux/arm64` image push. `[VERIFIED: infrastructure/constructs/agent_runtime.py L32]`

**Warning signs:** `exec format error` at container startup (very rare with pure-Python wheel dependencies).

### Pitfall 8: ValidationError.errors() salvage fragility across Pydantic minor versions

**What goes wrong:** Pydantic v2.4 → v2.5 → v2.6 may evolve the `ValidationError.errors()` structure (types, messages, `loc` tuple conventions). Code that navigates `err.errors()[0]["loc"]` to find which field failed could break silently.

**How to avoid:** Use the **lenient-reparse** salvage strategy (Pattern 3 above) — it doesn't depend on `ValidationError.errors()` structure; it just re-runs `_reject_forbidden` per field post-hoc. More robust.

**Warning signs:** Phase 6 passes locally but fails in CI after a Pydantic patch bump. Pin `pydantic<2.X+1` in `agent/requirements.txt` before freeze (DEMO-04 will do this anyway via pip-compile).

## Code Examples

Verified patterns from official sources.

### Example 1: Pydantic v2 `@field_validator` with sibling access
**Source:** `[VERIFIED: pydantic.dev/docs/validation/latest/concepts/validators/]`

```python
from pydantic import BaseModel, field_validator, ValidationInfo

class User(BaseModel):
    password: str
    password_repeat: str

    @field_validator("password_repeat", mode="after")
    @classmethod
    def check_passwords_match(cls, value: str, info: ValidationInfo) -> str:
        if value != info.data["password"]:
            raise ValueError("Passwords do not match")
        return value
```

Adapted for Phase 6:
```python
@field_validator("usage_narrative", mode="after")
@classmethod
def _validate_usage_narrative(cls, value: str, info: ValidationInfo) -> str:
    # info.data contains already-validated fields: plan_id, plan_name, saving_monthly, saving_annual
    # Useful for debug log context, not for validation decisions.
    return _reject_forbidden(value, max_words=20, field_label="usage_narrative")
```

### Example 2: Strands `Agent.structured_output` current usage pattern
**Source:** `[VERIFIED: agent/agent.py lines 131-135 — v1.0 shipped code]`

```python
result = _agent.structured_output(
    RecommendationResponse,
    f"Get tariff savings recommendations for customer {customer_id}",
)
```

Phase 6 extension:
```python
shape_tokens = build_shape_tokens(billing_history, plan)
result = _agent.structured_output(
    RecommendationResponse,
    _build_narrative_prompt(customer_id, shape_tokens),
)
```

### Example 3: Banned-terms compiled regex (module-level init)
**Source:** `[VERIFIED: CONTEXT.md D-14 pattern; benchmark run 2026-04-25]`

```python
# agent/narrative/banned_terms.py
import re

COMPETITORS = ("Origin", "AGL", "EnergyAustralia", "Red Energy", "Alinta", "Momentum")

SWITCH_VERBS = (
    "switch", "switches", "switching", "switched",
    "move", "moves", "moving", "moved",
    "change", "changes", "changing", "changed",
    "transfer", "transfers", "transferring", "transferred",
    "swap", "swaps", "swapping", "swapped",
    "shift", "shifts", "shifting", "shifted",
    "convert", "converts", "converting", "converted",
)

ENV_SUPERLATIVES = (
    "greenest", "cleanest", "most sustainable",
    "carbon-neutral", "carbon neutral",
    "zero-emission", "zero emission",
    "net-zero", "net zero",
    "best for the planet", "planet-friendly", "eco-friendliest",
)

# Compile once at module load — 3.5 µs per validation benchmarked 2026-04-25
BANNED_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in COMPETITORS + SWITCH_VERBS + ENV_SUPERLATIVES) + r")\b",
    re.IGNORECASE,
)

# Any digit OR any of $ £ € %
NUMERIC_REGEX = re.compile(r"[\d$£€%]")
```

**Benchmark evidence (local run, 2026-04-25):**
- Avg 3.51 µs per `BANNED_REGEX.search()` call on realistic narrative-length strings (64 chars mean).
- Word-boundary behaviour: `origin` → match; `original` → no match; `origins` → no match.
- Multi-word tokens like `Red Energy` match with `\b` boundaries on space.
- Hyphen boundaries work: `AGL-owned` matches `AGL`; `carbon-neutral` matches as multi-word token.

### Example 4: Shape-token vocabulary (starter — planner may refine)

```python
# agent/narrative/shape.py
"""Derives qualitative descriptors from billing history + plan attributes.
LLM sees the output of this function — NEVER raw kWh or dollar figures.
"""
from typing import Any

# Bucket thresholds — kept at file top as the CONTRACT fed to the LLM.
_USAGE_TIER_THRESHOLDS_KWH = (200, 400)  # low < 200 <= mid < 400 <= high

_SEASONALITY_LABELS = {
    "winter_heavy": "more usage in cool months than warm",
    "summer_peak": "more usage in warm months than cool",
    "flat": "even usage year-round",
}

def _compute_usage_tier(avg_kwh: float) -> str:
    if avg_kwh < _USAGE_TIER_THRESHOLDS_KWH[0]:
        return "low"
    if avg_kwh < _USAGE_TIER_THRESHOLDS_KWH[1]:
        return "mid"
    return "high"

def _compute_seasonality(billing_history: list[dict[str, Any]]) -> str:
    # Apr–Sep vs Oct–Mar (Australian seasons: winter runs ~Jun-Aug)
    winter_months = {"2025-06", "2025-07", "2025-08", "2025-06", "2026-06", "2026-07"}
    summer_months = {"2025-12", "2026-01", "2026-02", "2025-12"}
    winter_avg = sum(r["usage_kwh"] for r in billing_history if r["month"] in winter_months) / max(1, sum(1 for r in billing_history if r["month"] in winter_months))
    summer_avg = sum(r["usage_kwh"] for r in billing_history if r["month"] in summer_months) / max(1, sum(1 for r in billing_history if r["month"] in summer_months))
    if winter_avg > summer_avg * 1.2:
        return "winter_heavy"
    if summer_avg > winter_avg * 1.2:
        return "summer_peak"
    return "flat"

def build_shape_tokens(billing_history: list[dict[str, Any]], plan: dict[str, Any]) -> dict[str, str]:
    """Returns a dict of string enums. NEVER emits numeric values.
    
    Contract (frozen at DEMO-04):
      usage_tier:         "low" | "mid" | "high"
      seasonality:        "winter_heavy" | "summer_peak" | "flat"
      plan_category:      "green_premium" | "value" | "time_of_use" | "standard"
      renewable_profile:  "eco_aligned" | "cost_aligned"   # derived from plan, not stored in billing
      tenure_band:        "new" | "established"   # placeholder — v2.0 has no tenure data
    """
    avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
    return {
        "usage_tier": _compute_usage_tier(avg_kwh),
        "seasonality": _compute_seasonality(billing_history),
        "plan_category": plan.get("plan_type", "standard"),
        "renewable_profile": "eco_aligned" if plan.get("plan_type") == "green_premium" else "cost_aligned",
        "tenure_band": "established",
    }
```

**Contract properties the planner must enforce:**
1. Every value is a lowercase `[a-z_]+` string — no digits, no currency, no punctuation.
2. The function is pure — no side effects, no AWS, no I/O beyond its inputs.
3. Unit-testable with fixtures from `infrastructure/seed_data/billing_records.py` without AWS creds.
4. The full vocabulary is listed at the top of `shape.py` as the documented interface to the LLM.

### Example 5: Live-smoke output capture pattern

**Source:** `[VERIFIED: tests/test_agent_smoke.py pattern]`

Extend `tests/test_agent_smoke.py` with:

```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_narrative_fields_present_and_valid(agentcore_client, customer_id):
    body = _invoke_agent(agentcore_client, customer_id)
    for track in ("green", "cheapest"):
        assert "usage_narrative" in body[track], f"{track}: missing usage_narrative for {customer_id}"
        assert "call_script" in body[track], f"{track}: missing call_script for {customer_id}"
        # Re-run validator rules as a post-hoc assertion (belt+braces)
        for field_name in ("usage_narrative", "call_script"):
            s = body[track][field_name]
            assert not re.search(r"[\d$£€%]", s), f"{customer_id}/{track}/{field_name}: contains forbidden char: {s!r}"
```

**Sample capture for `06-SAMPLES.md`:** Add a one-shot helper script (`scripts/capture_samples.py`) that invokes each persona and writes output to a Markdown file. Runs ONCE at Phase 6 close, committed for design review. Pattern:

```python
# scripts/capture_samples.py (runs once, artefact committed)
import boto3, json, uuid, os
from pathlib import Path

ARN = os.environ["AGENT_RUNTIME_ARN"]
client = boto3.client("bedrock-agentcore", region_name="us-east-1")
out = Path(".planning/phases/06-agent-narrative-guardrail/06-SAMPLES.md")
with out.open("w") as f:
    f.write("# Phase 6 Live Smoke Samples\n\n")
    for cust in ("CUST-001", "CUST-002", "CUST-003"):
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=ARN,
            runtimeSessionId=str(uuid.uuid4()),
            payload=json.dumps({"customer_id": cust}).encode(),
        )
        body = json.loads(resp["response"].read())
        f.write(f"## {cust}\n```json\n{json.dumps(body, indent=2)}\n```\n\n")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pydantic v1 `@validator` decorator | Pydantic v2 `@field_validator` + `@classmethod` | Pydantic 2.0 release (Jun 2023) | Different import path; `@classmethod` required; `ValidationInfo` replaces `values` dict. This project is on v2 transitively. |
| `Agent.structured_output(model, prompt)` | `Agent(..., structured_output_model=Model)` or passed into invocation kwargs | Strands 1.37.0 deprecation notice | v1.0 uses the deprecated method; Phase 6 keeps it (out of scope to migrate). Planner flags as v3.0. `[VERIFIED: src/strands/agent/agent.py v1.37.0]` |
| Prompt-only numeric exclusion | Prompt + Pydantic `field_validator` (dual gate) | LLM guardrail best practice 2024+ | Prompt reduces validator-fail rate; validator is non-negotiable backstop. CONTEXT.md D-15 locks this. |

**Deprecated/outdated:**
- Pydantic v1 `@validator`: NOT in this project. Use v2 `@field_validator`.
- `pydantic.BaseModel.Config` class: replaced by `model_config = ConfigDict(...)`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `logger.info(msg, extra={...})` surfaces as queryable JSON in the AgentCore runtime's CloudWatch log group (AgentCore uses container stdout capture but JSON-format log parsing depends on AgentCore's log configuration, which is not explicitly documented). | §Pattern 4 CloudWatch structured logging | Low — worst case, logs still appear as plain text and can be parsed by CloudWatch Insights with a regex; D-03's requirement ("CloudWatch structured log entry") is still met. Fallback is `print(json.dumps({...}))` with `"level"` and `"timestamp"` keys. |
| A2 | Strands 1.37.0 does NOT emit a retry on Pydantic `ValidationError` raised from `output_model(**output_response)` inside `BedrockModel.structured_output`. | §Summary, §Validator Retry Semantics | Very low — directly read from source (`src/strands/models/bedrock.py`). `[VERIFIED: upstream source]` Not an assumption. |
| A3 | The SUMMARY.md claim "~50 µs per validation" for banned-terms regex was conservative; actual is ~3.5 µs on realistic strings. | §Banned-Terms Regex | None — lower is strictly better for latency budget. |
| A4 | Shape-token vocabulary starter (usage_tier, seasonality, plan_category, renewable_profile, tenure_band) is sufficient for 6 quality narrative outputs. Planner may refine based on fallback copy review; final vocabulary frozen at Phase 6 close. | §Example 4 | Low — vocabulary can expand in Phase 6 plan wave 0 without schema change; expansion never breaks (it only adds keys). |
| A5 | AgentCore's `cdk deploy AgentCoreStack` completes in 3-8 minutes (Docker build + ECR push + runtime roll). No AWS docs nail a specific SLA. | §Deploy Flow | Low — deploy time affects phase close timing only. Planner should budget 15 min for deploy+smoke. |
| A6 | The Dockerfile pattern `COPY agent/ /app/agent/` that CONTEXT.md Code Insights mentions is ASPIRATIONAL — the actual Dockerfile only copies `agent.py`. Must be updated. | §Pitfall 1 | MEDIUM if overlooked — live deploy fails on first invocation. Mitigation: explicit task in plan to update Dockerfile before deploy; verify with `docker build + docker run <image> ls /app/`. `[VERIFIED: agent/Dockerfile line 8]` |

**User confirmation recommended for:** A6 is the one that most needs planner attention — the Dockerfile MUST be updated and local-verified before `cdk deploy`.

## Open Questions

1. **CloudWatch log format on AgentCore runtime.**
   - What we know: Lambda supports JSON log format via advanced logging controls. AgentCore runs a container and captures stdout. Python stdlib `logger.info(msg, extra={...})` with the right handler formatter emits JSON. `[VERIFIED: AWS Lambda docs]`
   - What's unclear: Whether AgentCore's log group auto-detects JSON, or whether we need an explicit JSON formatter in the agent's logging config.
   - Recommendation: In Phase 6 Wave N (live smoke), eyeball the CloudWatch log group for a narrative_fallback_fired entry. If it appears as JSON fields (queryable in CW Insights), we're good. If it appears as text, add a simple JSON formatter to `agent.py` module init.

2. **Does `structured_output` respect the `output_model` parameter on each call, or is it cached?**
   - What we know: `BedrockModel.structured_output` takes `output_model: type[T]` per-call and invokes `convert_pydantic_to_tool_spec(output_model)` each time. `[VERIFIED: src/strands/models/bedrock.py]`
   - What's unclear: Whether the tool_spec conversion is memoised at the Agent level (would break the lenient-reparse salvage pattern if so).
   - Recommendation: Quick pytest during Phase 6 wave 0 — call `structured_output` twice with two different model classes, assert different schemas are used. Low risk; Strands source shows no caching.

3. **Fallback copy review.**
   - What we know: D-06 says the 6 fallback strings are demo-ready, written during Phase 6. Must pass the validator (enforced by pytest).
   - What's unclear: Who reviews the prose quality — Claude writes them in the plan, engineer reviews in PR diff? Or a third party?
   - Recommendation: Planner includes a specific copy-review gate in the plan (e.g., a PR checkbox: "Read each of the 6 fallback strings aloud — does it scan?"). Not automated.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Agent container build | ✓ (in Dockerfile) | 3.12-slim base | — |
| `strands-agents==1.37.0` | Agent orchestration | ✓ | 1.37.0 pinned | — |
| `bedrock-agentcore==1.6.3` | AgentCore runtime wrapper | ✓ | 1.6.3 pinned | — |
| `pydantic>=2.4.0,<3.0.0` | Schema + validators | ✓ (transitive) | Whatever Strands pulls | — |
| `boto3>=1.42.0` | Lambda + AgentCore invocation | ✓ | 1.42.0+ | — |
| AWS CDK | `cdk deploy AgentCoreStack` | ✓ (v1.0 shipped) | `aws-cdk-lib>=2.250.0` | — |
| Docker (local, for build) | `cdk deploy` builds image via CDK asset | ✓ (dev machine) | Any recent | — |
| AWS credentials, `us-east-1` | CDK deploy + live smoke | ✓ (v1.0 confirmed) | — | Phase 6 live smoke fails without; no silent fallback — this is a hard requirement from success criterion 5 |
| AgentCore service availability (`us-east-1`) | Runtime deploy target | ✓ (v1.0 confirmed) | GA | — |
| Claude 3.7 Sonnet model access | LLM inference | ✓ (v1.0 confirmed) | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | — |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest>=7.0` + `pytest-mock>=3.0` (already in `requirements-dev.txt`) |
| Config file | None currently — uses pytest defaults. Phase 6 adds marker `smoke` (already in use via `@pytest.mark.smoke`). Wave 0 may add `pytest.ini` if a `filterwarnings` entry for Strands deprecation warning is wanted. |
| Quick run command | `pytest -m "not smoke" -x` (offline suite, no AWS) |
| Full suite command | `AGENT_RUNTIME_ARN=<arn> AWS_DEFAULT_REGION=us-east-1 pytest -v` (includes smoke) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-05 | Validator rejects digits in `usage_narrative` | unit | `pytest tests/test_narrative_validator.py::test_digits_rejected -x` | ❌ Wave 0 |
| UI-05 | Validator rejects `$`/`£`/`€`/`%` in `usage_narrative` | unit | `pytest tests/test_narrative_validator.py::test_currency_symbols_rejected -x` | ❌ Wave 0 |
| UI-05 | Validator rejects banned competitors | unit | `pytest tests/test_narrative_validator.py::test_competitors_rejected -x` | ❌ Wave 0 |
| UI-05 | Validator rejects banned switch verbs | unit | `pytest tests/test_narrative_validator.py::test_switch_verbs_rejected -x` | ❌ Wave 0 |
| UI-05 | Validator rejects banned env superlatives | unit | `pytest tests/test_narrative_validator.py::test_env_superlatives_rejected -x` | ❌ Wave 0 |
| UI-05 | Validator rejects word-count over cap | unit | `pytest tests/test_narrative_validator.py::test_word_cap_enforced -x` | ❌ Wave 0 |
| UI-05 | Validator rejects char-count over cap | unit | `pytest tests/test_narrative_validator.py::test_char_cap_enforced -x` | ❌ Wave 0 |
| UI-05 | Validator accepts clean narratives | unit | `pytest tests/test_narrative_validator.py::test_positive_cases_accepted -x` | ❌ Wave 0 |
| UI-05 | FALLBACKS strings themselves pass validator | unit | `pytest tests/test_fallbacks_pass_validator.py -x` | ❌ Wave 0 |
| UI-03/UI-04 | Retry-once-then-per-field-fallback policy | unit (mocked Strands) | `pytest tests/test_agent_narrative.py::test_retry_once_then_fallback -x` | ❌ Wave 0 |
| UI-03/UI-04 | `_narrative_source` marker present in response | unit (mocked) | `pytest tests/test_agent_narrative.py::test_narrative_source_marker -x` | ❌ Wave 0 |
| UI-03/UI-04 | Shape-tokens contain zero numeric tokens for all personas | unit | `pytest tests/test_shape_tokens.py::test_no_numerics_any_persona -x` | ❌ Wave 0 |
| UI-03/UI-04 | Shape-tokens vocabulary matches documented contract | unit | `pytest tests/test_shape_tokens.py::test_vocabulary_whitelist -x` | ❌ Wave 0 |
| UI-03 | Live smoke: `call_script` returned for all 3 personas on both cards, no numeric tokens | smoke | `AGENT_RUNTIME_ARN=... pytest tests/test_agent_smoke.py::test_narrative_fields_present_and_valid -v` | ✅ (extend existing) |
| UI-04 | Live smoke: `usage_narrative` returned for all 3 personas on both cards, no numeric tokens | smoke | (same test — parametrised by field) | ✅ (extend existing) |
| success-crit 5 | Live deployment in `us-east-1` serves extended schema | smoke | (same test) | ✅ (extend existing) |
| success-crit 5 | v1.0 DEMO-02 $30/$55 deltas unchanged | smoke | `AGENT_RUNTIME_ARN=... pytest tests/test_agent_smoke.py::test_sarah_flagship_values` | ✅ (existing, must not regress) |
| roadmap-crit 4 (poisoned corpus) | 10 invocations × 3 personas × 2 cards — zero numeric tokens, 100% pass-or-fallback | offline integration (mocked LLM) | `pytest tests/test_agent_narrative_corpus.py::test_corpus_10x_no_numerics -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest -m "not smoke" -x tests/test_narrative_validator.py tests/test_fallbacks_pass_validator.py tests/test_shape_tokens.py tests/test_agent_narrative.py`
- **Per wave merge:** `pytest -m "not smoke"` (full offline suite — confirms v1.0 regression tests remain green)
- **Phase gate (before `/gsd-verify-work`):** Offline suite green + live smoke on ALL 3 personas + sample capture to `06-SAMPLES.md`

### Wave 0 Gaps
- [ ] `tests/test_narrative_validator.py` — covers UI-05 (9+ tests across banned categories, word cap, char cap, positive cases)
- [ ] `tests/test_fallbacks_pass_validator.py` — covers the "fallbacks must themselves pass validator" invariant (per CONTEXT.md D-04, D-06)
- [ ] `tests/test_shape_tokens.py` — covers shape-token no-numerics invariant and vocabulary whitelist
- [ ] `tests/test_agent_narrative.py` — covers retry-once-then-fallback policy (mocked `structured_output`), `_narrative_source` marker presence
- [ ] `tests/test_agent_narrative_corpus.py` — covers roadmap success criterion 4 (offline, with mocked randomised LLM outputs)
- [ ] `tests/test_agent_smoke.py` extension — new parametrised `test_narrative_fields_present_and_valid` (adds live-smoke coverage)
- [ ] `conftest.py` extension — add `mock_trackinfo` fixture + `clean_narrative_sample` + `poisoned_narrative_samples` fixtures
- [ ] Framework install: none — `pytest` already in `requirements-dev.txt`.

### Poisoned-Test Corpus Size Recommendation
Per CONTEXT.md Claude's Discretion ("recommend ≥3 per banned category"):

| Category | Count | Rationale |
|----------|-------|-----------|
| Digits 0-9 | 5 | Integer in middle of sentence; integer at end; integer with currency prefix; integer with percentage suffix; written-out number ("twelve") — positive case (must PASS, since `\d` only catches digits). |
| Currency symbols | 4 | `$`, `£`, `€`, `%` — one test each. |
| Competitors | 6 | One per entry in `COMPETITORS` tuple — ensures each is individually caught. Plus one case-variation test (`"origin"` lowercase). |
| Switch verbs | 8 | Base form + one inflection for each category of verb; plus one false-positive guard (`"switcheroo"` must NOT match). |
| Env superlatives | 6 | Each starter term once; plus one multi-word test (`"most sustainable"`). |
| Word-count over cap | 2 | Just over (21 words for `usage_narrative`); well over (40 words). |
| Char-count over cap | 2 | Just over (141 chars, 10 words — long-word scenario); well over (200 chars). |
| **Positive cases (MUST pass)** | 6 | One per persona × card — exactly what `FALLBACKS` contains. These overlap with `test_fallbacks_pass_validator.py` but re-assert inside the corpus for independence. |

**Total:** ~39 test cases in `test_narrative_validator.py`. Plus ~10 in `test_agent_narrative_corpus.py` for the mocked-LLM randomised corpus.

## Security Domain

> Phase 6 security implications stem from CONTEXT.md D-Claude's Discretion "Retry logging detail" + PITFALLS.md M7 (PII in logs) + C2 (prompt injection). Narrative generation introduces the first LLM prompt in the project that could accept customer-derived data.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | AgentCore runtime IAM handles; no new auth surface in Phase 6. |
| V3 Session Management | no | `runtimeSessionId` = fresh `uuid4()` per invocation (v1.0 D-11); no narrative-specific session state. |
| V4 Access Control | no | No new IAM permissions (CONTEXT.md code_context "No IAM change"). |
| V5 Input Validation | **yes** | Pydantic `field_validator` enforces string-content rules on LLM output. `customer_id` input validation already in `_validate_customer_id` at `lambda/handler.py:42`. |
| V6 Cryptography | no | No new cryptographic surface. |
| V7 Error Handling & Logging | **yes** | Per D-03 (structured log on fallback fire) + Claude's Discretion "log failure reason, NOT raw output" — PII-safe logging. |

### Known Threat Patterns for Phase 6

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| LLM hallucinated numerics contradict deterministic tool output | Repudiation (user trust) | Shape-token prompt (structural: numbers absent) + Pydantic `field_validator` (enforcement: digits rejected). Dual gate. `[CITED: PITFALLS.md C1]` |
| Prompt injection via customer-derived strings | Tampering | Shape-tokens are enum-only — no free-text interpolation from customer data into the prompt. v2.0 has no customer free-text anyway (only persona ID). `[CITED: PITFALLS.md C2]` |
| PII leakage in CloudWatch logs | Information Disclosure | Log failure REASON + persona ID + card track ONLY. Never log raw LLM output or raw prompt. `customer_id` is a developer-assigned ID (`CUST-001` etc.), not a real PII value in v2.0. `[CITED: PITFALLS.md M7, CONTEXT.md Claude's Discretion]` |
| Banned-terms regex bypass via Unicode lookalikes | Tampering | Low priority for v2.0 (demo environment, single-model LLM, controlled inputs). Document as v3.0 hardening consideration if moving to PROD-01 CRM integration. |
| Fallback string itself contains banned term | Integrity (fallback trust) | Dedicated pytest `test_fallbacks_pass_validator.py` blocks merge if a fallback fails validation. `[CITED: CONTEXT.md Specifics]` |

## Sources

### Primary (HIGH confidence)

- **Strands SDK v1.37.0 source code** (GitHub: `strands-agents/sdk-python` tag `v1.37.0`)
  - `pyproject.toml` — pydantic dependency constraint `>=2.4.0,<3.0.0`. Verified via raw.githubusercontent.com fetch 2026-04-25.
  - `src/strands/models/bedrock.py` `structured_output` method — line `yield {"output": output_model(**output_response)}` confirms Pydantic validation runs there and errors propagate.
  - `src/strands/agent/agent.py` — `structured_output()` deprecated; `structured_output_async()` no retry on ValidationError.
  - `src/strands/event_loop/_retry.py` — `ModelRetryStrategy` only retries on `ModelThrottledException`.

- **Pydantic v2 official docs** (pydantic.dev/docs/validation/latest/concepts/validators/)
  - `@field_validator` decorator signature and `mode` parameter semantics.
  - `ValidationInfo.data` sibling access.
  - `@classmethod` requirement.

- **AWS Bedrock AgentCore Developer Guide** (docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-sessions.html) — 15-min idle timeout verified 2026-04-25.

- **AWS Lambda Python logging docs** (docs.aws.amazon.com/lambda/latest/dg/python-logging.html) — `logger.info(msg, extra={...})` + advanced logging controls JSON format.

- **Existing project code**
  - `agent/agent.py` — v1.0 `TrackInfo` + `SYSTEM_PROMPT` + `invoke()` (extension targets).
  - `agent/requirements.txt` — pinned deps.
  - `agent/Dockerfile` — COPY pattern (pitfall 1).
  - `infrastructure/constructs/agent_runtime.py` — AgentCore runtime CDK construct.
  - `infrastructure/agentcore_stack.py` — deploy target.
  - `infrastructure/seed_data/billing_records.py` — persona profiles.
  - `lambda/handler.py` — billing-history shape fed to `build_shape_tokens`.
  - `tests/test_agent_tools.py`, `tests/test_agent_smoke.py`, `tests/test_schema.py`, `tests/conftest.py` — test patterns to reuse.

### Secondary (MEDIUM confidence)

- **Local benchmark (run 2026-04-25 on project machine)** — banned-terms regex: 3.5 µs/validation mean; word-boundary correctness confirmed for all edge cases.

- **v1.0 research artefacts** (`.planning/research/SUMMARY.md`, `ARCHITECTURE.md`, `STACK.md`, `PITFALLS.md`, `FEATURES.md`) — well-documented and internally consistent. Medium because they're curated summaries, not primary sources.

### Tertiary (LOW confidence — flagged for validation during planning)

- Exact CloudWatch log format behaviour for AgentCore runtime (vs Lambda) — verify during Phase 6 live smoke.
- Deploy time SLA for `cdk deploy AgentCoreStack` — estimate 3-8 min, measure on first run.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every dep verified via upstream `pyproject.toml` and existing `agent/requirements.txt`.
- Architecture: HIGH — four-tier model unchanged from v1.0, extension points validated against upstream Strands source.
- Pitfalls: HIGH on Dockerfile COPY (source-verified) + deprecation warnings + word/char cap interaction. MEDIUM on CloudWatch JSON format behaviour on AgentCore (not Lambda-native).
- Validation architecture: HIGH — follows established `tests/` pattern; Wave 0 gap list is exhaustive and matches one-test-per-rule granularity.
- Security: HIGH — applicable controls are input-validation (Pydantic) + log hygiene (already established pattern).

**Research date:** 2026-04-25
**Valid until:** 2026-05-25 (30 days — stable Pydantic v2, stable Strands 1.37.0, stable AgentCore GA features). Re-verify before any Pydantic minor bump (per Pitfall 8) or Strands major bump (per Pitfall 3).

---

*Research complete. Planner can now create PLAN.md files.*

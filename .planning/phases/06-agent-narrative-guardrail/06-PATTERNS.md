# Phase 6: Agent Narrative + Guardrail — Pattern Map

**Mapped:** 2026-04-25
**Files analyzed:** 14 (7 new, 5 modified, 2 new test fixtures on existing files)
**Analogs found:** 14 / 14 (100% — all new files have a strong in-repo analog)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `agent/narrative/__init__.py` | package-init | module-load | `infrastructure/seed_data/__init__.py` | exact (empty package init) |
| `agent/narrative/shape.py` | pure-utility | transform | `lambda/handler.py` (`simulate_savings_pure` + `_validate_customer_id`) | exact (pure fn + module-level threshold constants) |
| `agent/narrative/fallbacks.py` | config/constant | module-load | `infrastructure/seed_data/billing_records.py` (`SARAH_CHEN_RECORDS` dict + import-time asserts) | exact (typed const dict, frozen artefact) |
| `agent/narrative/banned_terms.py` | config/constant | module-load | `lambda/handler.py:39` `_CUSTOMER_ID_PATTERN = re.compile(...)` | role-match (only in-repo compiled-regex-at-module-load) |
| `agent/narrative/validators.py` (implied by RESEARCH §Pattern 1 — planner may keep inline on `TrackInfo`) | validator | transform | Pydantic `@field_validator` is net-new to repo; closest tonal analog = `lambda/handler.py` `_validate_customer_id` raise-on-bad-input pattern | role-match |
| `agent/narrative/prompt.txt` | config/text-asset | file-I/O at module load | `agent/agent.py:82-96` `SYSTEM_PROMPT` triple-quoted constant (moving to external file) | role-match (externalised form of existing pattern) |
| `agent/narrative/prompt_loader.py` *(optional per RESEARCH §Recommended Structure)* | utility | file-I/O | `lambda/handler.py:19-26` `open("tariff_plans.json")` with path-fallback at import | exact |
| `agent/agent.py` (MODIFY) | controller/entrypoint | request-response | self (v1.0 shipped; in-place extension) | exact (self-analog) |
| `agent/Dockerfile` (MODIFY) | build-config | file-copy | self (v1.0 shipped; single-line `COPY agent.py .` → `COPY` package) | exact (self-analog) — PITFALL 1 |
| `tests/test_narrative_validator.py` | test (unit) | CRUD-on-model | `tests/test_schema.py` (Pydantic-free invariants), `tests/test_simulate_savings.py` (pure-fn assertions) | exact (unit test over pure validator) |
| `tests/test_fallbacks_pass_validator.py` | test (unit) | CRUD-on-model | `tests/test_schema.py` (iterate constant → assert invariants) | exact |
| `tests/test_shape_tokens.py` | test (unit) | CRUD-on-model | `tests/test_simulate_savings.py` (pure-fn + fixture-driven) | exact |
| `tests/test_agent_narrative.py` | test (unit, mocked Strands) | request-response | `tests/test_agent_tools.py` (`MagicMock` + `json.dumps` mock) | exact |
| `tests/test_agent_narrative_corpus.py` | test (unit, randomised mocks) | batch | `tests/test_agent_tools.py` + parametrisation from `test_agent_smoke.py` | role-match (new corpus pattern, built on existing mock plumbing) |
| `tests/test_agent_smoke.py` (MODIFY) | test (live smoke) | request-response | self (extend parametrised pattern) | exact (self-analog) |
| `tests/conftest.py` (MODIFY) | fixture-config | module-load | self (extend persona + mock fixture pattern) | exact (self-analog) |

---

## Pattern Assignments

### `agent/narrative/__init__.py` (package-init, module-load)

**Analog:** `infrastructure/seed_data/__init__.py` — a one-line empty package init (the file has 1 line).

**Pattern to copy:** Minimal empty file marking the directory as a Python package. No re-exports needed — callers import specific submodules (e.g. `from agent.narrative.shape import build_shape_tokens`).

**Conventions:**
- Leaf-module import hygiene (per RESEARCH §Pitfall 2): `agent/narrative/*.py` must NOT import `agent.agent` — circular-import risk. The `__init__.py` stays empty.

---

### `agent/narrative/shape.py` (pure-utility, transform)

**Analog:** `lambda/handler.py` lines 55-118 (`simulate_savings_pure`) — the canonical "pure Python, unit-testable without AWS, module-level constants at top" shape this phase extends.

**Module-level threshold constants** (lambda/handler.py:57):
```python
DAYS_PER_MONTH = 30.44  # 365.25/12; used to annualise daily supply charges
```
→ Phase 6 analog: expose shape-token thresholds the same way (e.g. `_USAGE_TIER_THRESHOLDS_KWH = (200, 400)` at file top, documented inline as the LLM-facing contract).

**Pure-function signature + docstring pattern** (lambda/handler.py:60-74):
```python
def simulate_savings_pure(
    billing_history: List[Dict[str, Any]],
    plans: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Deterministic savings calculator — SAV-03 compliant (no LLM arithmetic).

    Algorithm:
      avg_kwh = mean(record["usage_kwh"])
      ...
    """
    if not billing_history:
        raise ValueError("billing_history must not be empty")
```
→ Phase 6 `build_shape_tokens(billing_history, plan) -> dict[str, str]` follows same shape: typed params, type-annotated return, `Raises ValueError` on empty input, algorithm summary in docstring.

**Input-iteration idiom** (lambda/handler.py:80):
```python
avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
```
→ Reuse this exact idiom for `build_shape_tokens` — same generator expression, same `float()` coercion (DynamoDB returns `Decimal`), same divide-by-`len`.

**Conventions to preserve:**
- Typing imports: `from typing import Any, Dict, List` (handler.py:13). Python 3.12 runtime allows builtin-generic syntax, but the repo consistently uses capital-`Dict`/`List` — match it.
- Docstring has an `Algorithm:` block listing the formula in pseudocode. Phase 6 equivalent: `Contract:` block listing the vocabulary emitted (RESEARCH §Example 4 already demonstrates this).
- File header docstring matches the purpose-sentence style of `lambda/handler.py:1-9`.

---

### `agent/narrative/fallbacks.py` (config/constant, module-load)

**Analog:** `infrastructure/seed_data/billing_records.py` — the canonical "typed Python constant dict, imported once at module load, sanity-asserted at import time, frozen as a demo artefact" pattern.

**Typed constant declaration** (billing_records.py:49-51):
```python
SARAH_CHEN_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-001", m, u) for m, u in zip(_MONTHS, _SARAH_USAGE)
]
```
→ Phase 6 analog:
```python
FALLBACKS: Dict[str, Dict[str, Dict[str, str]]] = {
    "CUST-001": {
        "green":    {"usage_narrative": "...", "call_script": "..."},
        "cheapest": {"usage_narrative": "...", "call_script": "..."},
    },
    "CUST-002": {...},
    "CUST-003": {...},
}
```

**Import-time sanity assertions** (billing_records.py:94-99):
```python
assert len(SARAH_CHEN_RECORDS) == 12, "Sarah must have 12 months"
assert len(MARCUS_WEBB_RECORDS) == 12, "Marcus must have 12 months"
assert len(ELENA_VASQUEZ_RECORDS) == 12, "Elena must have 12 months"
assert len(ALL_RECORDS) == 36, "ALL_RECORDS must contain exactly 36 items"
```
→ Phase 6 analog: at the bottom of `fallbacks.py`, assert `len(FALLBACKS) == 3` and per-persona shape. Fails fast at cold start if a fallback is accidentally dropped during copy editing.

**File header docstring style** (billing_records.py:1-12): describes purpose, the locked-down hard targets (`$30` / `$55`), and the don't-drift constraint. Phase 6 analog header should state: "Frozen at DEMO-04. Each string MUST pass `_reject_forbidden` — enforced by `tests/test_fallbacks_pass_validator.py`."

**Conventions to preserve:**
- Customer IDs as string keys: `"CUST-001"`, `"CUST-002"`, `"CUST-003"` — match conftest.py and billing_records.py exactly.
- Typing: `Dict[str, Dict[str, Dict[str, str]]]` with `from typing import Dict`.
- No f-strings with numeric substitution anywhere in the file (RESEARCH §Pitfall 5) — copy is literal.

---

### `agent/narrative/banned_terms.py` (config/constant, module-load)

**Analog:** `lambda/handler.py:39` — the ONLY existing module-level compiled regex in the repo.

**Module-level compile pattern** (lambda/handler.py:37-52):
```python
# --- Input validation ---

_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")


def _validate_customer_id(customer_id: Any) -> str:
    """Raise ValueError on invalid customer_id; returns normalised string.

    STRIDE: V5 Input Validation — rejects injection attempts, empty strings,
    and non-string types before any DynamoDB query is issued.
    """
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```

**Conventions to mirror:**
- Leading underscore on module-private regex constants (`_CUSTOMER_ID_PATTERN`). Phase 6 departs here by design — `BANNED_REGEX` and `NUMERIC_REGEX` are **public** (imported by `validators.py`). Exported tuple constants (`COMPETITORS`, `SWITCH_VERBS`, `ENV_SUPERLATIVES`) follow SCREAMING_SNAKE_CASE for public module-level config.
- Section-separator comments `# --- <Section> ---` (handler.py:15, :37, :55, :121). Apply to `banned_terms.py`: `# --- Tuple constants ---`, `# --- Compiled patterns ---`.
- STRIDE V5 callout in the module header docstring (handler.py:43-44 notes V5 input validation) — Phase 6 is also V5 (per RESEARCH §Security Domain), mirror the tag.

**Exact code to lay down** (from RESEARCH §Example 3, already verified by local benchmark 2026-04-25):
```python
BANNED_REGEX = re.compile(
    r"\b(" + "|".join(re.escape(t) for t in COMPETITORS + SWITCH_VERBS + ENV_SUPERLATIVES) + r")\b",
    re.IGNORECASE,
)
NUMERIC_REGEX = re.compile(r"[\d$£€%]")
```

---

### `agent/narrative/prompt.txt` (config/text-asset, module-load file-I/O)

**Analog:** `agent/agent.py:82-96` `SYSTEM_PROMPT` constant (the current inline system prompt being externalised).

**Current inline form** (agent.py:82-96):
```python
SYSTEM_PROMPT = """\
You are a call centre tariff recommendation assistant for an energy provider.

Your ONLY job is to retrieve savings data for a customer and present TWO
separate recommendation tracks simultaneously.

RULES:
1. Call the simulate_savings tool ONCE with the customer_id provided.
2. Use ONLY the numbers returned by the tool. Do NOT recalculate, estimate,
   or round the savings figures yourself.
3. Return BOTH the GREEN and CHEAPEST tracks in your response.
...
"""
```

**Pattern to preserve in `prompt.txt`:**
- Opening sentence identifying role ("You are a call centre tariff recommendation assistant...").
- Numbered `RULES:` block — Phase 6 narrative rules follow the same numbered-list convention.
- Rule phrasing: imperative-caps emphasis ("ONLY", "NEVER", "BOTH"). Use the same tone for banned-terms negative constraint (D-15): e.g. `NEVER use: switch, switching, move, moving, ...`.

**File-load pattern to use** (from `lambda/handler.py:19-26`):
```python
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
try:
    with open("tariff_plans.json") as _f:
        TARIFF_PLANS: List[Dict[str, Any]] = json.load(_f)
except FileNotFoundError:
    with open(os.path.join(_THIS_DIR, "tariff_plans.json")) as _f:
        TARIFF_PLANS = json.load(_f)
```
→ Phase 6 analog for `load_prompt()` (either inline in `agent.py` or in `agent/narrative/prompt_loader.py`): same `os.path.dirname(os.path.abspath(__file__))` anchoring so the prompt loads whether cwd is `/app`, repo root, or test working dir. Load ONCE at module-level (not per invocation) — mirrors `TARIFF_PLANS` init.

**Convention note:** Triple-backslash continuation `"""\` (agent.py:82) suppresses leading blank line — not applicable to a `.txt` file, but the equivalent is "no leading blank line in `prompt.txt`".

---

### `agent/agent.py` MODIFY (controller/entrypoint, request-response)

**Analog:** self — in-place extension. Three explicit extension points.

#### Extension Point 1: `TrackInfo` (lines 32-37)

**Current shape:**
```python
class TrackInfo(BaseModel):
    """A single recommendation track (Green or Cheapest)."""
    plan_id: str = Field(description="Tariff plan identifier (e.g. ECO, VAL)")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")
```

**Extension (RESEARCH §Pattern 1):** Add two required-string fields with `max_length` char cap + `@field_validator` for word cap + content rules. Do NOT mark `Optional` (per CONTEXT.md §code_context).

**Convention to preserve:**
- `Field(description=...)` on every field (matches existing four fields).
- Type annotation first, then default — matches existing v1.0 style.
- `@classmethod` on `@field_validator` (v2 requirement, RESEARCH §Pitfall 8).

#### Extension Point 2: `SYSTEM_PROMPT` (lines 82-96)

**Pattern:** Replace the inline triple-quoted string with a composition:
```python
SYSTEM_PROMPT = _BASE_SYSTEM_PROMPT + "\n\n" + load_prompt()
```
Or keep the existing constant and pass a combined prompt into `_agent = Agent(system_prompt=...)` (line 107) — planner chooses. Either way, the file-at-import pattern from `lambda/handler.py:19-26` applies.

#### Extension Point 3: `invoke()` (lines 117-148)

**Current structure (agent.py:130-148):**
```python
try:
    result = _agent.structured_output(
        RecommendationResponse,
        f"Get tariff savings recommendations for customer {customer_id}",
    )
    return result.model_dump()
except Exception:
    # Fallback: if structured_output doesn't work with tool calls,
    # call the Lambda directly and return the raw result.
    logger.warning(
        "structured_output failed — falling back to direct Lambda call",
        exc_info=True,
    )
    resp = _lambda_client.invoke(...)
    return json.loads(resp["Payload"].read())
```

**Extension (CONTEXT.md D-01, D-02, RESEARCH §Pattern 2):**
- Add `except ValidationError:` BEFORE the bare `except Exception:` (RESEARCH §Anti-Patterns — order matters).
- Retry-once inside the `ValidationError` branch, then call `_narrative_fallback_salvage(...)` if the retry also fails.
- Append `_narrative_source` marker to `body` before return.

**Conventions to preserve:**
- `logger.warning(...)` with `exc_info=True` (line 139-142) — Phase 6 retry log follows same call shape.
- `logger.info("Processing recommendation for %s", customer_id)` (line 128) — `%s`-style formatting, not f-strings, for logging (matches stdlib `logging` convention). Phase 6 structured log should use `logger.info(msg, extra={...})` per RESEARCH §Pattern 4, but keep `%s` for the message arg.
- Module-level logger: `logger = logging.getLogger(__name__)` (line 20) — reuse, do not create a new one in narrative submodules (they should use the same idiom with their own `__name__`).
- Module-level boto3 client reuse (line 27: `_lambda_client = boto3.client(...)`) — narrative code does NOT add a new client.

---

### `agent/Dockerfile` MODIFY (build-config, file-copy) — PITFALL 1

**Analog:** self. Current file is 13 lines — reproduced here:

**Current contents** (Dockerfile:1-13):
```dockerfile
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agent.py .

EXPOSE 8080

CMD ["python", "agent.py"]
```

**Required change (RESEARCH §Pitfall 1, Assumption A6):** Line 8 only copies `agent.py`. New `agent/narrative/` package will NOT be in the image. Update to:
```dockerfile
COPY agent.py .
COPY narrative/ ./narrative/
```

**Why this matters:** CONTEXT.md (`canonical_refs` line 90) asserts `COPY agent/ /app/agent/` already works — it does NOT. The Dockerfile predates the multi-file package. RESEARCH flags this as MEDIUM-severity if overlooked (live deploy fails on first invocation with `ModuleNotFoundError`).

**Convention to preserve:** Pin to `linux/arm64` (line 1) — matches `infrastructure/constructs/agent_runtime.py` L32 platform pin. Do NOT change.

**Verification step** (from RESEARCH §Pitfall 1): `docker build -t tariff-agent-test . && docker run --rm tariff-agent-test ls /app/narrative/` before `cdk deploy`.

---

### `tests/test_narrative_validator.py` (test unit, CRUD-on-model)

**Analog:** `tests/test_schema.py` — the "iterate a constant, assert invariants one-per-test" pattern.

**Imports pattern** (test_schema.py:1-9):
```python
"""Schema & invariant tests for seed data — DATA-02 + DATA-03 proof."""
import re
from infrastructure.seed_data.billing_records import (
    ALL_RECORDS,
    DYNAMO_RECORDS,
    SARAH_CHEN_RECORDS,
    MARCUS_WEBB_RECORDS,
    ELENA_VASQUEZ_RECORDS,
)
```
→ Phase 6 analog:
```python
"""Narrative validator tests — UI-05 proof."""
import pytest
from pydantic import ValidationError
from agent.agent import TrackInfo  # or whichever module exposes the extended model
```

**One-test-per-rule shape** (test_schema.py:15-18):
```python
def test_all_records_have_required_fields():
    for record in ALL_RECORDS:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record {record.get('customer_id')} {record.get('month')} missing: {missing}"
```
→ Phase 6 analog — one test per banned category, per RESEARCH §Poisoned-Test Corpus Size Recommendation:
```python
def test_digits_rejected():
    with pytest.raises(ValidationError):
        TrackInfo(
            plan_id="ECO", plan_name="EcoFlex 100",
            saving_monthly=30.0, saving_annual=360.0,
            usage_narrative="Uses 500 kWh in winter months",  # contains digit
            call_script="...clean...",
        )
```

**Assertion-message style** (test_schema.py:18):
```python
assert not missing, f"Record {record.get('customer_id')} {record.get('month')} missing: {missing}"
```
→ Same f-string `!r`/field-context pattern for Phase 6 fail messages.

**Conventions to preserve:**
- Test function names match the pattern `test_<rule_or_invariant>` — short, assertive.
- No docstrings on trivial tests (test_schema.py:15 onwards); use docstrings only when the invariant needs explanation.
- `pytest.raises(ValidationError)` as the negative-case idiom — not try/except.
- Corpus size per RESEARCH table: ~39 test cases.

---

### `tests/test_fallbacks_pass_validator.py` (test unit, CRUD-on-model)

**Analog:** `tests/test_schema.py` — specifically the "iterate ALL_RECORDS, assert every one satisfies X" pattern (lines 15-28).

**Exact shape to copy** (test_schema.py:21-28):
```python
def test_usage_kwh_is_numeric():
    # DATA-03: stored in kWh, numeric — not strings, not Decimals.
    for record in ALL_RECORDS:
        assert isinstance(record["usage_kwh"], int), (
            f"usage_kwh must be int for {record['customer_id']} {record['month']}; "
            f"got {type(record['usage_kwh']).__name__}"
        )
```
→ Phase 6 analog:
```python
def test_all_fallbacks_pass_validator():
    """D-04, D-06: Every FALLBACKS string must itself pass the field_validator.

    If a fallback fails validation, the double-fail recovery path (D-02)
    becomes an exception source.
    """
    from agent.narrative.fallbacks import FALLBACKS
    from agent.agent import TrackInfo

    for customer_id, tracks in FALLBACKS.items():
        for track_name, fields in tracks.items():
            # Construct a TrackInfo with the fallback narrative + valid numerics.
            # ValidationError would bubble up from @field_validator — no pytest.raises.
            TrackInfo(
                plan_id="ECO", plan_name="EcoFlex 100",
                saving_monthly=30.0, saving_annual=360.0,
                usage_narrative=fields["usage_narrative"],
                call_script=fields["call_script"],
            )  # must NOT raise
```

**Convention:** The test PASSES by not raising. No explicit `assert` when the whole point is "constructor does not raise". Matches the v1 `test_all_records_have_required_fields` shape.

---

### `tests/test_shape_tokens.py` (test unit, CRUD-on-model)

**Analog:** `tests/test_simulate_savings.py` — pure-function + persona-fixture + invariant-check pattern.

**Imports + fixture-pattern** (test_simulate_savings.py:9-26):
```python
import importlib
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
simulate_savings_pure = handler.simulate_savings_pure


def test_flagship_persona_green_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01
```
→ Phase 6 analog — no `importlib` dodge needed (`agent.narrative` is not a Python keyword):
```python
import re
import pytest
from agent.narrative.shape import build_shape_tokens


def test_no_numerics_any_persona(sarah_billing, tariff_plans):
    tokens = build_shape_tokens(sarah_billing, tariff_plans[0])
    for key, value in tokens.items():
        assert re.match(r"^[a-z_]+$", value), \
            f"Shape token {key!r}={value!r} must be lowercase-alnum; contains invalid char"
```

**Fixture reuse:** `sarah_billing`, `marcus_billing`, `elena_billing`, `tariff_plans` are ALREADY in `conftest.py:13-39` — no new fixture needed for shape-token tests. Reuse directly.

**Conventions to preserve:**
- Persona fixture names (`sarah_billing`, `marcus_billing`, `elena_billing`) — match conftest.py exactly.
- Assertion with `!r` formatting for debugging context.
- Per-persona test via `@pytest.mark.parametrize` IF all three test the same invariant. See `test_agent_smoke.py:55-60` for the canonical `parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])` pattern.

---

### `tests/test_agent_narrative.py` (test unit, request-response, mocked Strands)

**Analog:** `tests/test_agent_tools.py` — the canonical MagicMock-plus-`json.dumps`-for-Lambda-response pattern.

**Mock-builder helper** (test_agent_tools.py:13-19):
```python
def make_mock_lambda_response(payload_dict):
    """Build a mock boto3 lambda.invoke() response."""
    payload_bytes = json.dumps(payload_dict).encode()
    return {
        "StatusCode": 200,
        "Payload": MagicMock(read=MagicMock(return_value=payload_bytes)),
    }
```
→ Phase 6 analog: a `make_mock_structured_output_result(track_info_dict)` helper that returns a `MagicMock` whose `model_dump()` returns the dict (or a real `RecommendationResponse` instance). Pattern 3 in RESEARCH.md (lenient-reparse salvage) drives what the retry mock must yield.

**Imports pattern** (test_agent_tools.py:1-10):
```python
"""Offline tests for agent tool return shape and savings invariants.

These tests verify the contract between the agent and the ToolsLambda
WITHOUT requiring AWS credentials. The Lambda response is mocked.

Covers: REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03, SC-4 (cheapest >= green).
"""
import json
import pytest
from unittest.mock import MagicMock
```
→ Phase 6 matches: header docstring with requirement IDs covered (UI-03, UI-04, UI-05), `unittest.mock` imports, offline-only (no `@pytest.mark.smoke`).

**Mocking-the-patched-module pattern** — Phase 6 will need to patch `agent.agent._agent.structured_output` to return specific objects. Use `pytest-mock` (`mocker.patch`) — already in `requirements-dev.txt` per RESEARCH §Test Framework. Example shape (derived):
```python
def test_retry_once_then_fallback(mocker, mock_savings_response):
    # First call raises ValidationError, second call also raises → fallback swap
    first_exc = ValidationError.from_exception_data(...)
    mocker.patch(
        "agent.agent._agent.structured_output",
        side_effect=[first_exc, first_exc],
    )
    # ... call invoke({"customer_id": "CUST-001"}) ...
    # assert _narrative_source.usage_narrative == "fallback"
```

**Conventions to preserve:**
- No `smoke` marker — these tests MUST run in the offline suite (`pytest -m "not smoke"`).
- Fixture-keyed-on-persona-id: reuse `mock_savings_response`, `mock_marcus_response`, `mock_elena_response` from conftest.py:47-100.
- Assertion error messages include which track + which field failed (same style as test_agent_tools.py:59-60).

---

### `tests/test_agent_narrative_corpus.py` (test unit, batch, randomised mocks)

**Analog:** `tests/test_agent_tools.py` (mock plumbing) + `tests/test_agent_smoke.py:55` (parametrised persona iteration).

**Parametrised-persona shape** (test_agent_smoke.py:55-60):
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_both_tracks_present(agentcore_client, customer_id):
    """SC-1: invoke_agent_runtime returns both green and cheapest tracks."""
    body = _invoke_agent(agentcore_client, customer_id)
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"
```
→ Phase 6 corpus: parametrise `[("CUST-001", "green"), ("CUST-001", "cheapest"), ("CUST-002", "green"), ...]` (6 combos) × 10 runs each = 60 invocations. Per RESEARCH §Wave 0 Gaps item 5 ("10 invocations × 3 personas × 2 cards").

**Randomisation primitive:** Python stdlib `random.choice(CLEAN_SAMPLES + POISONED_SAMPLES)` — no new dependency. Seed the RNG for reproducibility (`random.seed(42)` at test-module level; test_schema.py lacks this but the corpus test needs it).

**Conventions to preserve:**
- Offline only (no smoke mark) — RESEARCH explicitly maps corpus test to "offline integration (mocked LLM)".
- Reuse `poisoned_narrative_samples` and `clean_narrative_sample` fixtures (to be added in conftest.py — see next section).
- Assert the final invariant per corpus item: "zero numeric tokens in the returned `body[track][field]`".

---

### `tests/test_agent_smoke.py` MODIFY (test live smoke, request-response)

**Analog:** self — extend the existing `@pytest.mark.parametrize("customer_id", [...])` pattern.

**Current parametrised-per-persona test** (test_agent_smoke.py:55-60):
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_both_tracks_present(agentcore_client, customer_id):
    """SC-1: invoke_agent_runtime returns both green and cheapest tracks."""
    body = _invoke_agent(agentcore_client, customer_id)
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"
```

**Extension (from RESEARCH §Example 5):**
```python
@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_narrative_fields_present_and_valid(agentcore_client, customer_id):
    body = _invoke_agent(agentcore_client, customer_id)
    for track in ("green", "cheapest"):
        assert "usage_narrative" in body[track], f"{track}: missing usage_narrative for {customer_id}"
        assert "call_script" in body[track], f"{track}: missing call_script for {customer_id}"
        for field_name in ("usage_narrative", "call_script"):
            s = body[track][field_name]
            assert not re.search(r"[\d$£€%]", s), \
                f"{customer_id}/{track}/{field_name}: contains forbidden char: {s!r}"
```

**Conventions to preserve:**
- Module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(...)]` (test_agent_smoke.py:25-31) applies automatically to every test in the file — no per-test marker needed.
- Reuse `agentcore_client` fixture (lines 34-40) and `_invoke_agent` helper (43-50) — do not re-declare.
- `import re` at top of file (only re-add if not already present — it is not; line 17 has `json, os, uuid` only).
- Existing `test_sarah_flagship_values` (line 100) MUST NOT regress — v1.0 `$30`/`$55` deltas stay intact per CONTEXT.md success criterion preservation.

---

### `tests/conftest.py` MODIFY (fixture-config, module-load)

**Analog:** self — extend the established Phase 1/2/3 fixture-block pattern.

**Existing block-comment convention** (conftest.py:42-44, 102-104):
```python
# --- Phase 2 agent fixtures ---

# --- Phase 3 API Lambda fixtures ---
```
→ Phase 6 additions live under a new block:
```python
# --- Phase 6 narrative fixtures ---
```

**Fixture-style pattern** (conftest.py:19-23):
```python
@pytest.fixture
def sarah_billing():
    from infrastructure.seed_data.billing_records import SARAH_CHEN_RECORDS
    return SARAH_CHEN_RECORDS
```
→ Phase 6 additions (three fixtures per pattern-mapping context spec):

**`mock_trackinfo` fixture** — returns a valid `TrackInfo` dict skeleton for test construction (similar shape to `mock_savings_response` at conftest.py:47-62):
```python
@pytest.fixture
def mock_trackinfo():
    """Baseline valid-narrative TrackInfo dict — tests override specific fields."""
    return {
        "plan_id": "ECO",
        "plan_name": "EcoFlex 100",
        "saving_monthly": 30.00,
        "saving_annual": 360.00,
        "usage_narrative": "Winter usage concentrated in cooler months",
        "call_script": "Ask about EcoFlex 100 — it suits a strong winter-heating profile",
    }
```

**`clean_narrative_sample` fixture** — a single known-clean string passing all validator rules:
```python
@pytest.fixture
def clean_narrative_sample():
    return "Winter-heavy household with consistent mid-range usage across the year"
```

**`poisoned_narrative_samples` fixture** — list of (sample, reason) tuples covering each banned category (count per RESEARCH §Poisoned-Test Corpus):
```python
@pytest.fixture
def poisoned_narrative_samples():
    return [
        ("Saves about 30 dollars a month", "contains digit"),
        ("Saves $30 monthly", "contains currency symbol"),
        ("Switch to EcoFlex to save", "contains switch verb"),
        ("Origin customers switching pay more", "contains competitor"),
        ("The greenest option available", "contains env superlative"),
        # ... continue per corpus-size table in RESEARCH §Poisoned-Test Corpus
    ]
```

**Conventions to preserve:**
- Lazy `from ... import ...` inside fixture body (conftest.py:20-21) — avoids import-cycle surprises at conftest collection time. Phase 6 narrative imports (e.g. from `agent.narrative.banned_terms`) should follow same pattern.
- No fixture docstring on trivial returns (conftest.py:13-22 style) — keep it lean.
- Fixtures return plain Python data structures (dicts, lists, tuples), never mocks. Mocks are built inside tests (test_agent_tools.py:103 `mock_client = MagicMock()`).

---

## Shared Patterns

### Module-level init for reused state

**Source:** `agent/agent.py:20-27`, `lambda/handler.py:15-34`

**Apply to:** `agent/narrative/banned_terms.py` (regex compile), `agent/narrative/fallbacks.py` (dict literal), `agent/narrative/prompt_loader.py` (file read), `agent/narrative/shape.py` (threshold tuples).

**Pattern:**
```python
# agent/agent.py:20-27
logger = logging.getLogger(__name__)

_TOOLS_LAMBDA_ARN = os.environ.get("TOOLS_LAMBDA_ARN", "")
_REGION = os.environ.get("AWS_REGION", "us-east-1")
_lambda_client = boto3.client("lambda", region_name=_REGION)
```
Zero per-invocation overhead. Phase 6 MUST NOT read `prompt.txt`, compile `BANNED_REGEX`, or construct `FALLBACKS` inside `invoke()` — all init happens at module import.

---

### Logger convention

**Source:** `agent/agent.py:20`, `:128`, `:139-142`

**Apply to:** every Phase 6 new `.py` file that logs.

**Pattern:**
```python
import logging
logger = logging.getLogger(__name__)

# At call site:
logger.info("Processing recommendation for %s", customer_id)   # %s formatting, not f-strings
logger.warning("structured_output failed — ...", exc_info=True)  # exc_info on exception paths
```

**Phase 6 extension (RESEARCH §Pattern 4):** When emitting structured log for `narrative_fallback_fired=true`, keep the positional message, use `extra={...}` for queryable fields:
```python
logger.info(
    "narrative fallback fired",
    extra={
        "narrative_fallback_fired": True,
        "field": "usage_narrative",
        "customer_id": customer_id,
        "track": "green",
        "failure_reason": str(err),
    },
)
```

---

### Pydantic model + Field(description=...)

**Source:** `agent/agent.py:32-43`

**Apply to:** extended `TrackInfo` + any new lenient model (`_TrackInfoLenient` per RESEARCH §Pattern 3).

**Pattern:**
```python
class TrackInfo(BaseModel):
    """A single recommendation track (Green or Cheapest)."""
    plan_id: str = Field(description="Tariff plan identifier (e.g. ECO, VAL)")
```
Every field carries a `description` — Strands turns these into tool-spec JSON hints that the LLM uses. Phase 6 new fields MUST include `description` for `usage_narrative` and `call_script` (makes the prompt-side guardrail clearer, per D-15 dual-gate).

---

### Section-separator comments

**Source:** `agent/agent.py:22,26,30,46,80,98,112`; `lambda/handler.py:15,37,55,121`; `tests/conftest.py:42,102`

**Apply to:** every Phase 6 multi-section file.

**Pattern:** `# --- <Section Title> ---` (exactly three dashes on each side). Aids greppability and matches the v1.0 code-review style seen throughout the repo.

---

### Test fixture naming + customer ID constants

**Source:** `tests/conftest.py:19-39`, `tests/test_agent_smoke.py:55`, `tests/test_agent_tools.py:25`

**Apply to:** every Phase 6 test file.

**Pattern:**
- Persona fixtures: `sarah_billing`, `marcus_billing`, `elena_billing`, `all_billing`.
- Persona mocks: `mock_savings_response` (Sarah, default), `mock_marcus_response`, `mock_elena_response`.
- Customer IDs as string literals: `"CUST-001"`, `"CUST-002"`, `"CUST-003"`.
- Parametrisation: `@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])`.

NEVER introduce alternative IDs or new persona names — the demo narrative is frozen.

---

### Offline-vs-smoke test separation

**Source:** `tests/test_agent_smoke.py:25-31` (module-level `pytestmark`), `tests/test_agent_tools.py` (no mark — runs offline by default).

**Apply to:**
- Offline suite (Phase 6 unit + mocked tests): `test_narrative_validator.py`, `test_fallbacks_pass_validator.py`, `test_shape_tokens.py`, `test_agent_narrative.py`, `test_agent_narrative_corpus.py` — NO smoke marker, must run in `pytest -m "not smoke"`.
- Live smoke extension: `test_agent_smoke.py` — inherits module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not AGENT_RUNTIME_ARN, ...)]`.

**Rationale** (CONTEXT.md §specifics): v1.0 close state = 81 passed / 6 skipped. Phase 6 must not regress the offline count; smoke tests stay skipped unless `AGENT_RUNTIME_ARN` is set.

---

### Leaf-module import hygiene (PITFALL 2)

**Source:** RESEARCH §Pitfall 2.

**Apply to:** every file under `agent/narrative/`.

**Rule:** `agent/narrative/*.py` imports ONLY from stdlib + Pydantic. They do NOT import `agent.agent` — that way lies circular import. `agent.agent` imports FROM the narrative submodules, not the reverse. Verification: `python -c "import agent.agent"` before Docker build.

---

## No Analog Found

None. Every new file has at least one strong in-repo analog — most have exact matches. The `@field_validator` construct itself is net-new to the repo (v1.0 `TrackInfo` has no validators), but RESEARCH §Pattern 1 supplies a VERIFIED code excerpt from Pydantic's official docs, and the raise-ValueError-with-field-context tone matches `lambda/handler.py` `_validate_customer_id` (handler.py:42-52).

---

## Metadata

**Analog search scope:**
- `/agent/` — source (agent.py, Dockerfile, requirements.txt)
- `/lambda/` — pure-fn + validator + module-level-init patterns
- `/infrastructure/seed_data/` — typed-constant-dict + frozen-artefact pattern
- `/tests/` — fixture, mock, parametrisation, smoke-vs-offline conventions

**Files scanned:** 14 (all 3 agent files, `lambda/handler.py`, `infrastructure/seed_data/billing_records.py` + `__init__.py`, all 4 relevant test files + conftest, plus grep confirmation across `agent/`, `lambda/`, `infrastructure/` for `re.compile`).

**Pattern extraction date:** 2026-04-25

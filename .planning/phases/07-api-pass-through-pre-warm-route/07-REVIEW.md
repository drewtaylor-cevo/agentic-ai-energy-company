---
phase: 07-api-pass-through-pre-warm-route
reviewed: 2026-04-26T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - api_lambda/handler.py
  - infrastructure/constructs/backend_api.py
  - tests/test_backend_api_handler.py
  - tests/test_backend_api_synth.py
findings:
  critical: 0
  warning: 1
  info: 5
  total: 6
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-04-26
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Phase 7 delivers three discrete changes against a clean baseline: the `_narrative_source` marker strip + structured CloudWatch log in the API Lambda (D-06/D-07), the `?prewarm=1` branch that returns 204 on both success and failure (D-01/D-02/D-04), and the CDK wiring that moves API Gateway integration from the raw function reference to a named `live` alias with optional Provisioned Concurrency (D-09/D-11/D-14). The implementations are tight, internally consistent with the phase design decisions, and comprehensively covered by both handler-level unit tests and synth assertions.

No critical issues were found. One warning concerns a fragility in the narrative-source log filter used by two tests (pattern-based log scraping that is brittle to message-format drift). The remaining items are informational: a minor type-robustness gap if the agent ever returns a non-dict body, an unbounded `demo_pc` context value, a missing exact-count assertion on alias resources, a duplicated agent-response builder already provided by `conftest.py`, and a small inconsistency between the new structured JSON log format and the pre-existing printf-style logs on adjacent error paths.

The pass-through guarantee (D-02, D-08) is correctly preserved — the handler only mutates `body` via one idempotent `pop()` before serialising, and tests verify byte-identical narrative field forwarding. The `?prewarm=1` branch is correctly gated AFTER the D-13 customer ID regex (per Pitfall 4), reuses the shared `_agentcore_client` with the 25s read timeout (D-05), and the bare `except Exception` correctly swallows ClientError, ReadTimeoutError, and transport errors in one place (D-04, SC-2). The CDK changes correctly make the `live` alias unconditional and only attach `provisioned_concurrent_executions` when `demo_pc > 0`, holding the alias ARN stable across PC-on/PC-off deploys (Phase 10 freeze-surface critical).

## Warnings

### WR-01: Log-scraping test filter is brittle to message-format drift

**File:** `tests/test_backend_api_handler.py:231-234, 258-262, 298-301, 324-327, 354-358`
**Issue:** Five test blocks filter `caplog.records` with the pattern `r.message.startswith("{") and "narrative_source" in r.message` (or `"prewarm_failed" in r.message`). This has two weaknesses:

1. The `startswith("{")` predicate silently skips any log record that is not a JSON string — a future refactor that adds a human-readable prefix to the log message (e.g., switching to `logger.info("narrative_source %s", json.dumps(...))` for grepability) would make every one of these assertions pass vacuously with an empty list, and then `len(...) == 1` would fail with a misleading "got 0" message instead of pointing at the format change.
2. The substring check `"narrative_source" in r.message` matches the JSON *key* `"narrative_source"` but also any future log that happens to mention that word in prose.

The handler correctness itself is fine — the log IS structured JSON (handler.py:129-133). The risk is purely test-brittleness: a well-intentioned handler edit could silently make tests pass for the wrong reason.

**Fix:** Filter on `logger name + log level` first, then parse the message as JSON inside a try/except, then assert on the parsed `event` field:

```python
def _structured_logs(caplog, event_name: str) -> list[dict]:
    """Extract structured JSON log records with matching event name."""
    out = []
    for r in caplog.records:
        if r.name != "api_lambda.handler":
            continue
        try:
            parsed = json.loads(r.message)
        except (json.JSONDecodeError, TypeError):
            continue
        if parsed.get("event") == event_name:
            out.append(parsed)
    return out

# Then:
narrative_source_logs = _structured_logs(caplog, "narrative_source")
assert len(narrative_source_logs) == 1
```

This tightens the contract to "exactly one structured log with event=narrative_source" and fails loudly if the format changes.

## Info

### IN-01: Non-dict agent body would AttributeError on `body.pop`

**File:** `api_lambda/handler.py:121`
**Issue:** `body = json.loads(response["response"].read())` (line 118) could produce a list, string, number, `True/False`, or `None` for a malformed agent response. The very next line `body.pop("_narrative_source", None)` assumes `body` is a dict and would raise `AttributeError` on any other type. This is swallowed by the broad `except Exception` at line 145 and returned as a 500 — operationally acceptable — but the 500 message "Internal server error." obscures the underlying shape mismatch, and CloudWatch only gets `exc_info=True` with no customer_id-specific shape hint.

Not a Phase 7 regression — the prior 404-detection path (`"green" not in body`) would have had the same issue. Flagged here because Phase 7's line 121 is the first line in the try block to actually mutate the body.

**Fix:** Guard the type before popping and return 502 with a clearer log on shape mismatch:

```python
body = json.loads(response["response"].read())
if not isinstance(body, dict):
    logger.error(
        "Agent returned non-dict body customer_id=%s type=%s",
        customer_id, type(body).__name__,
    )
    return _error(502, "Recommendation service error. Please try again.")
narrative_source = body.pop("_narrative_source", None)
```

Alternatively, accept the existing broad-except catch as adequate for a demo-grade service and leave as-is; the cost is one slightly less informative 500.

### IN-02: `demo_pc` context has no upper bound

**File:** `infrastructure/constructs/backend_api.py:88-106`
**Issue:** The context value is validated as non-negative but has no upper bound. A typo like `-c demo_pc=100` (instead of `10`) would attempt to provision 100 warm executions against the account concurrency limit, which can partially succeed and then fail partway through the deploy, leaving the alias in a mixed state. For a demo toggle intended to mean "1 or 2 warm instances," a sanity ceiling would catch the typo at synth time.

**Fix:** Add an upper bound consistent with the demo use case:

```python
DEMO_PC_MAX = 10  # well under regional account default of 1000
if demo_pc > DEMO_PC_MAX:
    raise ValueError(
        f"Invalid -c demo_pc value: {demo_pc}. "
        f"Must be <= {DEMO_PC_MAX} (demo toggle, not production scaling)."
    )
```

### IN-03: `_make_agent_response` duplicates `mock_agent_invoke_response` from conftest

**File:** `tests/test_backend_api_handler.py:33-39`
**Issue:** `_make_agent_response` locally rebuilds the same shape that `tests/conftest.py:107-110` already provides as the `mock_agent_invoke_response` fixture. Using the local helper is not wrong — it lets tests build custom-body responses inline — but it also means `conftest.mock_agent_invoke_response` is effectively dead code for this file, and two future edits (e.g., if AgentCore's response shape ever adds a field) have to be kept in sync by hand.

**Fix:** Either (a) parametrise the conftest fixture to accept an override body, or (b) delete `_make_agent_response` and switch to `mock_agent_invoke_response` wherever the default body is fine, keeping a one-liner helper only for custom bodies. No behavioural change, just reduces shape-drift risk.

### IN-04: `test_alias_live_exists` does not assert exactly one alias

**File:** `tests/test_backend_api_synth.py:170-176`
**Issue:** The test asserts an alias named `live` exists, but not that it's the only alias. A future refactor that accidentally adds a second alias (e.g., `blue`/`green` for CDK-native traffic shifting) would leave this test green while silently breaking the Phase 10 freeze-surface assumption that the `live` alias ARN is the single stable integration target.

The adjacent `test_pc_absent_when_demo_pc_zero` (line 228-232) already does `assert len(aliases) == 1` via raw traversal — this test should follow the same pattern.

**Fix:** Add a resource count assertion alongside the property assertion:

```python
def test_alias_live_exists():
    template = _synth_with_context(demo_pc=0)
    template.resource_count_is("AWS::Lambda::Alias", 1)
    template.has_resource_properties(
        "AWS::Lambda::Alias",
        {"Name": "live"},
    )
```

### IN-05: Log-format inconsistency within handler

**File:** `api_lambda/handler.py:94-101, 129-133, 135, 140-143, 146`
**Issue:** Phase 7 added two structured JSON logs (`prewarm_failed` at lines 94-101, `narrative_source` at lines 129-133) using `logger.warning/info(json.dumps({...}))`. The adjacent pre-existing error paths — the 504 timeout log (line 135), the 502 ClientError log (lines 140-143), and the 500 unexpected-error log (line 146) — still use printf-style format strings.

Neither format is wrong; the mix is what a CloudWatch Logs Insights query has to paper over. If the Phase 9 eval harness (referenced in 07-CONTEXT.md) queries both `narrative_source` AND failure logs in the same query, the query has to handle both serialisations. Not a bug; a small consistency tax to be aware of before Phase 9 writes its queries.

**Fix:** Optional — consider converting the three pre-existing error-path logs to the same `logger.xxx(json.dumps({"event": "...", "customer_id": ..., ...}))` shape during a later cleanup pass, or document the mixed-format reality in 07-PATTERNS.md so the Phase 9 query writer knows both formats land in the same log group.

---

_Reviewed: 2026-04-26_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

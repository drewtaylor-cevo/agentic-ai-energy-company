"""Live narrative eval harness — Phase 9 SC-4, ROADMAP closeout gate.

Asserts every persona × card narrative string returned by the live API
passes the Phase 6 Pydantic validator rules (regex + word/char caps)
AND that the Phase 7 `_narrative_source` marker is stripped on the
normal (non-prewarm) path.

Skipped unless BACKEND_API_URL env var is set to the deployed API endpoint.
Runs under `pytest -m smoke`; `pytest -m "not smoke"` collects 0 tests
from this module.

Invocation:
    BACKEND_API_URL=https://... pytest tests/test_narrative_eval_live.py -m smoke

Source-of-truth imports (D-12):
- NUMERIC_REGEX and BANNED_REGEX are imported directly from
  agent.narrative.banned_terms so any drift in Phase 6's validator
  rules is caught here — no copy-paste of regex values.
- Word and char cap constants are mirrored from
  tests/test_fallbacks_pass_validator.py (the offline invariant the
  committed fallback strings are tested against). Single authoritative
  envelope; drift on either side lights up.
"""
import os

import pytest
import requests

from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BACKEND_API_URL,
        reason="BACKEND_API_URL not set — skip live narrative eval harness",
    ),
]

# Mirrored from tests/test_fallbacks_pass_validator.py lines 12-15 (D-12).
# If Phase 6 rule caps change, update both files in the same commit.
_USAGE_NARRATIVE_MAX_WORDS = 20
_CALL_SCRIPT_MAX_WORDS = 22
_USAGE_NARRATIVE_MAX_CHARS = 140
_CALL_SCRIPT_MAX_CHARS = 180


def _fails_rules(value: str, max_words: int, max_chars: int):
    """Return failure reason string, or None if value is clean.

    Mirrors tests/test_fallbacks_pass_validator.py::_fails_rules
    byte-for-byte (D-12 — single-source-of-truth for validator-rule
    application). The eval harness tests live agent output, not
    fallbacks, but applies the identical rule set.
    """
    if not value:
        return "empty string"
    if NUMERIC_REGEX.search(value):
        return f"forbidden digit/currency in {value!r}"
    m = BANNED_REGEX.search(value)
    if m:
        return f"banned term {m.group()!r} in {value!r}"
    if len(value.split()) > max_words:
        return f"{len(value.split())} words > {max_words} cap in {value!r}"
    if len(value) > max_chars:
        return f"{len(value)} chars > {max_chars} cap in {value!r}"
    return None


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005"])
def test_narrative_eval_live(customer_id):
    """SC-4: live API narrative on both tracks passes Phase 6 validator rules;
    Phase 7 D-06 _narrative_source marker is absent from the response body.
    """
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60
    )
    assert r.status_code == 200, (
        f"Expected 200, got {r.status_code}: {r.text}"
    )
    body = r.json()

    # Phase 7 D-06 invariant — marker must never reach the client on the
    # normal (non-prewarm) path. scripts/capture_samples.py captures the
    # AgentCore-direct response (where the marker is visible); this
    # harness runs through the API Lambda which strips it.
    assert "_narrative_source" not in body, (
        f"D-06 violation for {customer_id}: _narrative_source leaked "
        f"to client (keys present: {sorted(body.keys())})"
    )

    # Presence check — both tracks must be present (matches
    # test_backend_api_smoke.py shape check lines 33-34)
    for track in ("green", "cheapest"):
        assert track in body, f"Missing {track} track for {customer_id}"
        for field in ("usage_narrative", "call_script"):
            assert field in body[track], (
                f"Missing {field} in {track} for {customer_id}"
            )

    # Validator rules — per field, per track (D-11 + D-12 + D-13)
    field_caps = (
        ("usage_narrative", _USAGE_NARRATIVE_MAX_WORDS, _USAGE_NARRATIVE_MAX_CHARS),
        ("call_script",     _CALL_SCRIPT_MAX_WORDS,     _CALL_SCRIPT_MAX_CHARS),
    )
    for track in ("green", "cheapest"):
        for field, max_words, max_chars in field_caps:
            value = body[track][field]
            reason = _fails_rules(value, max_words, max_chars)
            assert reason is None, (
                f"{customer_id}/{track}/{field}: {reason}"
            )


# ----------------------------------------------------------------------
# Phase 13 Plan 07 — AGENT-01a live gates (smoke-marked).
# ----------------------------------------------------------------------
# D-19: latency-floor witness (CUST-003 > 1000ms) — sub-1s = fabrication signature.
# D-21: CloudWatch Invocations counter (>= 2 on Tools Lambda) — zero = LLM
#       fabricated tool output.
# Pitfall 5: do NOT shorten the 90-second post-call sleep — CloudWatch
#   emission lag is 60-90s and false negatives emerge below that window.
# ----------------------------------------------------------------------

import time
from datetime import datetime, timedelta, timezone

import boto3


@pytest.mark.smoke
def test_agent01_latency_floor():
    """D-19: CUST-003 live warm latency > 1000ms.

    Sub-1s response on a 2-3 tool turn is a fabrication signature (C5).
    Each Tools Lambda round-trip costs >=400ms; real multi-tool should be
    comfortably above 1000ms. Complements AGENT-01a's 2500ms UPPER bound
    with a fabrication LOWER bound.
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")
    t0 = time.perf_counter()
    r = requests.get(
        f"{backend_api_url}/recommendations/CUST-003", timeout=60
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, f"CUST-003 returned {r.status_code}: {r.text}"
    assert elapsed_ms > 1000, (
        f"CUST-003 returned in {elapsed_ms:.0f}ms (<1000ms — C5 fabrication signature)"
    )


@pytest.mark.smoke
def test_agent01_tools_actually_invoked():
    """D-21: CloudWatch Invocations >= 2 on Tools Lambda during CUST-003 lookup.

    Zero invocations in the window = LLM fabricated tool output (C5). The
    >= 2 threshold allows for hardship_flag + simulate_savings minimal path
    while still catching fabrication.

    CRITICAL: the 90-second post-lookup sleep below is load-bearing
    (Pitfall 5 — CloudWatch emission lag 60-90s). DO NOT shorten.
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")
    tools_lambda_name = os.environ.get("TOOLS_LAMBDA_NAME")
    if not tools_lambda_name:
        # SSM fallback per RESEARCH §5.
        ssm = boto3.client("ssm", region_name="us-east-1")
        try:
            tools_lambda_name = ssm.get_parameter(
                Name="/customer-tariff/tools-lambda-name"
            )["Parameter"]["Value"]
        except Exception:
            pytest.skip(
                "TOOLS_LAMBDA_NAME env var unset and SSM parameter "
                "/customer-tariff/tools-lambda-name missing — set one or the other"
            )

    t0 = datetime.now(timezone.utc)

    # Fire CUST-003 lookup.
    r = requests.get(
        f"{backend_api_url}/recommendations/CUST-003", timeout=60
    )
    assert r.status_code == 200

    # CloudWatch metrics lag ~60-90s after emission — wait for visibility.
    # Pitfall 5: DO NOT shorten this sleep; false negatives emerge < 90s.
    time.sleep(90)

    t1 = datetime.now(timezone.utc) + timedelta(seconds=30)

    cw = boto3.client("cloudwatch", region_name="us-east-1")
    metric = cw.get_metric_statistics(
        Namespace="AWS/Lambda",
        MetricName="Invocations",
        Dimensions=[{"Name": "FunctionName", "Value": tools_lambda_name}],
        StartTime=t0,
        EndTime=t1,
        Period=60,
        Statistics=["Sum"],
    )

    total_invocations = sum(point["Sum"] for point in metric["Datapoints"])
    assert total_invocations >= 2, (
        f"Expected >=2 Tools Lambda invocations in window "
        f"[{t0.isoformat()}, {t1.isoformat()}], got {total_invocations}. "
        f"C5 fabrication signature: agent likely skipped real tool calls."
    )


@pytest.mark.smoke
def test_agent01_non_shock_stays_2_tools():
    """D-13.1-16: CUST-001 Sarah (non-shock) live reasoning_trace has <= 2 entries.

    Paired with D-13.1-03 offline mock-model test TestShortCircuit::
    test_non_shock_sarah_drives_2_tools_only. Offline proves the prompt CAN
    drive 2 tools against a scripted model; this smoke proves Sonnet 4.6's
    actual judgement matches against the real deployed stack.

    If this test fails post-Phase-13.1 ceremony, Gap 1 has regressed — the
    prompt SHORT-CIRCUIT RULE is not firing in production. Triage path:
    (a) re-run offline TestShortCircuit to confirm the prompt text is
    loaded into the container (container rebuild may have failed);
    (b) if offline still passes, iterate the prompt wording in Plan 01
    and re-run the ceremony.

    Latency expectations (not asserted here; Plan 04 ceremony captures
    actuals and updates DEMO-RUNBOOK.md per D-13.1-21):
      Pre-13.1: CUST-001 ~17.2s warm
      Post-13.1 target: warm < 3000ms (per-flow gate; Elena 3-tool path
                        has 2500ms gate and may still miss per D-13.1-02).
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")
    r = requests.get(
        f"{backend_api_url}/recommendations/CUST-001",
        timeout=60,
    )
    assert r.status_code == 200, (
        f"CUST-001 returned {r.status_code}: {r.text}"
    )
    body = r.json()
    trace = body.get("reasoning_trace", [])
    assert len(trace) <= 2, (
        f"Non-shock persona CUST-001 drove {len(trace)} tools "
        f"{[e.get('tool') for e in trace]}; D-13.1-14 requires <= 2 "
        f"(expected shape: get_hardship_flag + simulate_savings)."
    )


# ----------------------------------------------------------------------
# Phase 16 DEMO-10 — new smoke canaries for v3.0 surfaces.
# ----------------------------------------------------------------------


@pytest.mark.smoke
def test_agent02_hardship_refusal_shape():
    """DEMO-10: CUST-006 (hardship) returns kind: "hardship" with no tariff tracks.

    The hardship short-circuit (AGENT-02) must return a dignity-preserving
    routing response with no green/cheapest keys, no plan IDs, and no
    savings figures. The response shape is a discriminated union with
    kind: "hardship".
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")
    r = requests.get(
        f"{backend_api_url}/recommendations/CUST-006", timeout=60
    )
    assert r.status_code == 200, (
        f"CUST-006 returned {r.status_code}: {r.text}"
    )
    body = r.json()

    # Discriminated union shape check.
    assert body.get("kind") == "hardship", (
        f"Expected kind='hardship', got {body.get('kind')!r}"
    )
    assert "green" not in body, (
        f"Hardship response must not contain 'green' track: {sorted(body.keys())}"
    )
    assert "cheapest" not in body, (
        f"Hardship response must not contain 'cheapest' track: {sorted(body.keys())}"
    )

    # Required fields present.
    assert "customer_id" in body, "Missing customer_id in hardship response"
    assert "reason" in body, "Missing reason in hardship response"
    assert "call_script" in body, "Missing call_script in hardship response"
    assert body["customer_id"] == "CUST-006"

    # D-15 validators on hardship narrative fields — no digits, no banned terms.
    for field in ("reason", "call_script"):
        value = body[field]
        assert not NUMERIC_REGEX.search(value), (
            f"CUST-006 hardship {field} contains forbidden digit/currency: {value!r}"
        )
        m = BANNED_REGEX.search(value)
        assert m is None, (
            f"CUST-006 hardship {field} contains banned term {m.group()!r}: {value!r}"
        )


@pytest.mark.smoke
def test_agent01_multi_tool_determinism():
    """DEMO-10: CUST-003 (Elena, bill-shock) reasoning_trace contains deterministic
    tool-result summaries — same tools produce consistent summary shapes across
    two consecutive calls.

    This is NOT a byte-exact test (LLM narrative varies); it asserts that the
    reasoning_trace tool names and summary structure are stable, confirming the
    agent is actually calling tools (not fabricating) and the deterministic
    summary formatters in agent/reasoning/summaries.py are producing output.
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")

    traces = []
    for _ in range(2):
        r = requests.get(
            f"{backend_api_url}/recommendations/CUST-003", timeout=60
        )
        assert r.status_code == 200, f"CUST-003 returned {r.status_code}: {r.text}"
        body = r.json()
        trace = body.get("reasoning_trace", [])
        traces.append(trace)

    # Both calls should produce a non-empty trace.
    for i, trace in enumerate(traces):
        assert len(trace) >= 2, (
            f"Call {i+1}: CUST-003 reasoning_trace has {len(trace)} entries "
            f"(expected >= 2 for multi-tool flow)"
        )

    # Tool names should be consistent across calls (same tools called).
    tools_1 = [e.get("tool") for e in traces[0]]
    tools_2 = [e.get("tool") for e in traces[1]]
    assert tools_1 == tools_2, (
        f"Tool sequence inconsistent: call 1 = {tools_1}, call 2 = {tools_2}"
    )

    # Every entry should have a non-empty summary (deterministic formatter ran).
    for i, trace in enumerate(traces):
        for entry in trace:
            assert entry.get("summary"), (
                f"Call {i+1}: tool {entry.get('tool')!r} has empty summary"
            )

    # simulate_savings must always be the last tool (REC-03 contract).
    assert tools_1[-1] == "simulate_savings", (
        f"Last tool should be simulate_savings, got {tools_1[-1]!r}"
    )


@pytest.mark.smoke
def test_wf01_follow_up_route():
    """DEMO-10: follow-up route returns a well-shaped FollowUpEmailResponse.

    Exercises GET /recommendations/CUST-001/follow-up after a recommendation
    lookup for the same customer. The response should contain subject, body,
    and plan_reference fields. Internal markers (_workflow_source,
    _narrative_source) must be stripped.
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")

    # Step 1: prime the recommendation (populates Memory for the follow-up).
    r1 = requests.get(
        f"{backend_api_url}/recommendations/CUST-001", timeout=60
    )
    assert r1.status_code == 200, (
        f"CUST-001 recommendation returned {r1.status_code}: {r1.text}"
    )

    # Step 2: request the follow-up email draft.
    r2 = requests.get(
        f"{backend_api_url}/recommendations/CUST-001/follow-up", timeout=60
    )
    assert r2.status_code == 200, (
        f"CUST-001 follow-up returned {r2.status_code}: {r2.text}"
    )
    body = r2.json()

    # Shape check — FollowUpEmailResponse fields.
    assert "subject" in body, f"Missing 'subject' in follow-up response: {sorted(body.keys())}"
    assert "body" in body, f"Missing 'body' in follow-up response: {sorted(body.keys())}"
    assert "plan_reference" in body, f"Missing 'plan_reference' in follow-up response: {sorted(body.keys())}"

    # Internal markers must be stripped (parallel to _narrative_source contract).
    assert "_workflow_source" not in body, (
        f"_workflow_source leaked to client: {sorted(body.keys())}"
    )
    assert "_narrative_source" not in body, (
        f"_narrative_source leaked to client: {sorted(body.keys())}"
    )

    # Subject and body must be non-empty strings.
    assert isinstance(body["subject"], str) and len(body["subject"]) > 0, (
        f"Follow-up subject is empty or not a string"
    )
    assert isinstance(body["body"], str) and len(body["body"]) > 0, (
        f"Follow-up body is empty or not a string"
    )


@pytest.mark.smoke
def test_wf01_cross_customer_memory_isolation():
    """DEMO-10: cross-customer Memory isolation canary.

    Lookup CUST-001 → follow-up CUST-002 → verify CUST-002's follow-up
    contains zero tokens from CUST-001's recommendation. This is the live
    equivalent of the Phase 15 offline isolation canary.

    Checks: CUST-001's customer name (Sarah Chen) and plan-specific savings
    figures must NOT appear in CUST-002's follow-up body.
    """
    backend_api_url = os.environ["BACKEND_API_URL"].rstrip("/")

    # Step 1: prime CUST-001 recommendation (populates Memory).
    r1 = requests.get(
        f"{backend_api_url}/recommendations/CUST-001", timeout=60
    )
    assert r1.status_code == 200

    # Step 2: prime CUST-002 recommendation (populates Memory for CUST-002).
    r2 = requests.get(
        f"{backend_api_url}/recommendations/CUST-002", timeout=60
    )
    assert r2.status_code == 200

    # Step 3: request follow-up for CUST-002.
    r3 = requests.get(
        f"{backend_api_url}/recommendations/CUST-002/follow-up", timeout=60
    )
    assert r3.status_code == 200, (
        f"CUST-002 follow-up returned {r3.status_code}: {r3.text}"
    )
    body = r3.json()
    follow_up_body = body.get("body", "")

    # CUST-001 tokens that must NOT appear in CUST-002's follow-up.
    # Sarah Chen's name and her distinctive savings figures.
    cust001_tokens = ["Sarah Chen", "$30.00", "$55.00", "$360.00", "$660.00"]
    for token in cust001_tokens:
        assert token not in follow_up_body, (
            f"Cross-customer leak: CUST-001 token {token!r} found in "
            f"CUST-002 follow-up body (Memory isolation failure)"
        )

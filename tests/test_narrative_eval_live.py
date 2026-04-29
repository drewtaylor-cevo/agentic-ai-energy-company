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


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
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

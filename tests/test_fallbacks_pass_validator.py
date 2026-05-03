"""FALLBACKS-pass-validator invariant — D-04, D-06 proof.

Every string in agent.narrative.fallbacks.FALLBACKS must itself pass the same
rules the field_validator enforces. If a fallback string fails, the double-fail
recovery path (D-02) becomes an exception source and violates D-04 (never 500).
"""
import pytest

from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX
from agent.narrative.fallbacks import FALLBACKS

_USAGE_NARRATIVE_MAX_WORDS = 20
_CALL_SCRIPT_MAX_WORDS = 22
_USAGE_NARRATIVE_MAX_CHARS = 140
_CALL_SCRIPT_MAX_CHARS = 180


def _fails_rules(value: str, max_words: int, max_chars: int):
    """Return failure reason string, or None if value is clean."""
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


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003", "CUST-006"])
@pytest.mark.parametrize("track", ["green", "cheapest"])
def test_usage_narrative_fallback_passes(customer_id, track):
    value = FALLBACKS[customer_id][track]["usage_narrative"]
    reason = _fails_rules(value, _USAGE_NARRATIVE_MAX_WORDS, _USAGE_NARRATIVE_MAX_CHARS)
    assert reason is None, f"{customer_id}/{track}/usage_narrative: {reason}"


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003", "CUST-006"])
@pytest.mark.parametrize("track", ["green", "cheapest"])
def test_call_script_fallback_passes(customer_id, track):
    value = FALLBACKS[customer_id][track]["call_script"]
    reason = _fails_rules(value, _CALL_SCRIPT_MAX_WORDS, _CALL_SCRIPT_MAX_CHARS)
    assert reason is None, f"{customer_id}/{track}/call_script: {reason}"


def test_fallbacks_contains_all_personas():
    assert set(FALLBACKS.keys()) == {"CUST-001", "CUST-002", "CUST-003", "CUST-006"}


def test_fallbacks_contains_all_tracks_and_fields():
    for customer_id, tracks in FALLBACKS.items():
        assert "green" in tracks and "cheapest" in tracks, f"{customer_id}: missing green or cheapest"
        for track_name, fields in tracks.items():
            if track_name == "hardship":
                assert set(fields.keys()) == {"reason", "call_script"}, \
                    f"{customer_id}/{track_name}: hardship must have reason and call_script"
            else:
                assert set(fields.keys()) == {"usage_narrative", "call_script"}, \
                    f"{customer_id}/{track_name}: missing field"


# Phase 14: validate CUST-006 hardship fallback strings pass D-15 rules.
def test_hardship_fallback_reason_passes():
    value = FALLBACKS["CUST-006"]["hardship"]["reason"]
    reason = _fails_rules(value, _USAGE_NARRATIVE_MAX_WORDS, _USAGE_NARRATIVE_MAX_CHARS)
    assert reason is None, f"CUST-006/hardship/reason: {reason}"


def test_hardship_fallback_call_script_passes():
    value = FALLBACKS["CUST-006"]["hardship"]["call_script"]
    reason = _fails_rules(value, _CALL_SCRIPT_MAX_WORDS, _CALL_SCRIPT_MAX_CHARS)
    assert reason is None, f"CUST-006/hardship/call_script: {reason}"

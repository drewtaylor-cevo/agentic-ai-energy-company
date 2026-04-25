"""Agent narrative retry + fallback + marker tests — UI-03/UI-04 offline proof.

Covers CONTEXT.md D-01 (retry-once), D-02 (per-field fallback), D-03
(`_narrative_source` marker + structured log), D-04 (never 500).
"""
import logging
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError


# --- Helpers ---


def _valid_recommendation_response():
    """Build a validator-clean RecommendationResponse."""
    from agent.agent import RecommendationResponse, TrackInfo

    clean_narrative = "Winter-heavy household with consistent mid-range usage across the year"
    clean_script = "Ask about EcoFlex — it suits a strong winter-heating profile like yours"
    return RecommendationResponse(
        green=TrackInfo(
            plan_id="ECO", plan_name="EcoFlex",
            saving_monthly=30.0, saving_annual=360.0,
            usage_narrative=clean_narrative, call_script=clean_script,
        ),
        cheapest=TrackInfo(
            plan_id="VAL", plan_name="Value Twelve",
            saving_monthly=55.0, saving_annual=660.0,
            usage_narrative=clean_narrative, call_script=clean_script,
        ),
    )


def _lenient_response_with_poison(field_poisons: dict):
    """Build a _RecommendationResponseLenient with specific fields poisoned.

    field_poisons keys: ("green", "usage_narrative") -> "Saves $30 a month"
    """
    from agent.agent import _RecommendationResponseLenient, _TrackInfoLenient

    clean_narrative = "Winter-heavy household with consistent mid-range usage across the year"
    clean_script = "Ask about EcoFlex — it suits a strong winter-heating profile like yours"

    def _track(track_name: str):
        return _TrackInfoLenient(
            plan_id="ECO", plan_name="EcoFlex",
            saving_monthly=30.0, saving_annual=360.0,
            usage_narrative=field_poisons.get((track_name, "usage_narrative"), clean_narrative),
            call_script=field_poisons.get((track_name, "call_script"), clean_script),
        )

    return _RecommendationResponseLenient(
        green=_track("green"), cheapest=_track("cheapest"),
    )


def _fake_validation_error():
    from pydantic import ValidationError
    from agent.agent import RecommendationResponse

    try:
        RecommendationResponse(
            green={
                "plan_id": "ECO", "plan_name": "EcoFlex",
                "saving_monthly": 30.0, "saving_annual": 360.0,
                "usage_narrative": "Saves $30 a month",  # poisoned
                "call_script": "clean line here",
            },
            cheapest={
                "plan_id": "VAL", "plan_name": "Value",
                "saving_monthly": 55.0, "saving_annual": 660.0,
                "usage_narrative": "clean",
                "call_script": "clean",
            },
        )
    except ValidationError as e:
        return e
    raise AssertionError("expected ValidationError")


# --- Happy path ---


def test_happy_path_sets_narrative_source_all_model(mocker):
    valid = _valid_recommendation_response()
    mocker.patch("agent.agent._agent.structured_output", return_value=valid)
    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})
    assert "_narrative_source" in body
    assert body["_narrative_source"] == {
        "green":    {"usage_narrative": "model", "call_script": "model"},
        "cheapest": {"usage_narrative": "model", "call_script": "model"},
    }
    assert body["green"]["usage_narrative"]
    assert body["cheapest"]["call_script"]


# --- Retry-once path ---


def test_retry_once_succeeds(mocker):
    valid = _valid_recommendation_response()
    err = _fake_validation_error()
    mocker.patch(
        "agent.agent._agent.structured_output",
        side_effect=[err, valid],
    )
    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})
    # Retry landed valid output → marker still all "model"
    assert body["_narrative_source"]["green"]["usage_narrative"] == "model"


# --- Per-field fallback path ---


def test_retry_once_then_fallback_per_field(mocker, caplog):
    err = _fake_validation_error()
    # Both calls raise ValidationError; lenient parse returns a mix (green/usage_narrative poisoned, others clean).
    lenient = _lenient_response_with_poison({
        ("green", "usage_narrative"): "Saves $30 a month",
    })
    mocker.patch(
        "agent.agent._agent.structured_output",
        side_effect=[err, err, lenient],
    )
    from agent.agent import invoke
    from agent.narrative.fallbacks import FALLBACKS
    with caplog.at_level(logging.INFO, logger="agent.agent"):
        body = invoke({"customer_id": "CUST-001"})
    # Only green/usage_narrative swapped → fallback.
    assert body["_narrative_source"]["green"]["usage_narrative"] == "fallback"
    assert body["_narrative_source"]["green"]["call_script"] == "model"
    assert body["_narrative_source"]["cheapest"]["usage_narrative"] == "model"
    assert body["_narrative_source"]["cheapest"]["call_script"] == "model"
    # Swapped field uses FALLBACKS value.
    assert body["green"]["usage_narrative"] == FALLBACKS["CUST-001"]["green"]["usage_narrative"]
    # D-03 structured log: fallback fire present with field + track + customer_id, NO raw output.
    fallback_records = [r for r in caplog.records if getattr(r, "narrative_fallback_fired", False) is True]
    assert fallback_records, "expected at least one narrative_fallback_fired log record"
    rec = fallback_records[0]
    assert rec.customer_id == "CUST-001"
    assert rec.track == "green"
    assert rec.field == "usage_narrative"
    assert "failure_reason" in rec.__dict__
    # Per PITFALLS M7: never log the raw poisoned value.
    assert "Saves $30 a month" not in rec.getMessage()
    assert "Saves $30 a month" not in str(rec.__dict__.get("failure_reason", ""))


def test_full_fallback_when_lenient_parse_fails(mocker):
    err = _fake_validation_error()
    mocker.patch(
        "agent.agent._agent.structured_output",
        side_effect=[err, err, RuntimeError("lenient also failed")],
    )
    from agent.agent import invoke
    from agent.narrative.fallbacks import FALLBACKS
    body = invoke({"customer_id": "CUST-001"})
    # All 4 marked "fallback"
    for track in ("green", "cheapest"):
        for field in ("usage_narrative", "call_script"):
            assert body["_narrative_source"][track][field] == "fallback"
            assert body[track][field] == FALLBACKS["CUST-001"][track][field]


# --- D-04 never-500 guarantee ---


def test_invoke_never_returns_empty_narrative_on_validation_storm(mocker):
    err = _fake_validation_error()
    mocker.patch(
        "agent.agent._agent.structured_output",
        side_effect=[err, err, RuntimeError("x")],
    )
    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})
    for track in ("green", "cheapest"):
        assert body[track]["usage_narrative"]   # non-empty string
        assert body[track]["call_script"]       # non-empty string


def test_missing_customer_id_returns_error_dict():
    from agent.agent import invoke
    body = invoke({})
    assert "error" in body
    assert "customer_id" in body["error"]


# --- `_narrative_source` marker shape ---


def test_narrative_source_marker_shape(mocker):
    mocker.patch("agent.agent._agent.structured_output", return_value=_valid_recommendation_response())
    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})
    marker = body["_narrative_source"]
    assert set(marker.keys()) == {"green", "cheapest"}
    for track in marker.values():
        assert set(track.keys()) == {"usage_narrative", "call_script"}
        for val in track.values():
            assert val in ("model", "fallback")

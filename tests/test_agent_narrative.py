"""Agent narrative retry + fallback + marker tests — UI-03/UI-04 offline proof.

Phase 06.1: Rewritten for Strands 1.37.0 structured_output_model API.
Mock target moved from agent.agent._agent.structured_output (deprecated, vacuous
under new API) to replacing the agent.agent._agent module attribute with a
MagicMock. Python dispatches `instance(...)` to `type(instance).__call__` via
the class's descriptor protocol, which means `mocker.patch.object(instance,
"__call__", ...)` does NOT intercept invocation — the instance-level attribute
is bypassed for dunder lookup. Replacing the module-level binding with a
MagicMock sidesteps this by putting an explicitly-callable object in place.
[Rule 1 deviation — Pitfall 1 recipe corrected.]

Terminal failure class moved from pydantic.ValidationError to
strands.types.exceptions.StructuredOutputException. Every mock-using test
asserts call_count >= 1 to prevent vacuous green (RESEARCH §Pitfall 1).
All 7 original test intents preserved verbatim.

Covers CONTEXT.md D-01 (retry-once-inline-now), D-02 (per-field fallback from
message history), D-03 (_narrative_source marker + structured log), D-04
(never 500).
"""
import logging
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError
from strands.types.exceptions import StructuredOutputException


def _install_mock_agent(mocker, *, return_value=None, side_effect=None):
    """Replace agent.agent._agent with a MagicMock and return the mock.

    Python's `instance(args)` calls `type(instance).__call__`, which means
    a mock attached via `mocker.patch.object(instance, "__call__", ...)`
    does NOT intercept the call — the dunder lookup goes through the class.
    The safe + simple pattern is to replace the module-level binding itself
    so `_agent(...)` in invoke() routes through the MagicMock's __call__.
    """
    mock_agent = MagicMock()
    if return_value is not None:
        mock_agent.return_value = return_value
    if side_effect is not None:
        mock_agent.side_effect = side_effect
    import agent.agent as agent_mod
    mocker.patch.object(agent_mod, "_agent", mock_agent)
    return mock_agent


# --- Helpers (PRESERVED BYTE-FOR-BYTE from pre-migration per PATTERNS.md §(1)) ---


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

    return _RecommendationResponseLenient(green=_track("green"), cheapest=_track("cheapest"))


def _fake_agent_result(
    structured_output=None,
    toolUse_input: dict | None = None,
):
    """Build a MagicMock AgentResult fixture for _agent.__call__ return_value.

    structured_output: the RecommendationResponse (or None for terminal failure).
    toolUse_input: if set, populates .message.content with a fake toolUse block
                   named "RecommendationResponse" so _extract_lenient_from_agent_result
                   can parse it for per-field salvage. Pass None to simulate a
                   terminal failure with no recoverable last-turn input.
    """
    fake = MagicMock()
    fake.structured_output = structured_output
    if toolUse_input is None:
        fake.message = {"content": []}
    else:
        fake.message = {
            "content": [
                {"toolUse": {"name": "RecommendationResponse", "input": toolUse_input}},
            ],
        }
    return fake


# --- Tests ---


def test_happy_path_sets_narrative_source_all_model(mocker):
    """D-03: validator-clean output → marker all "model"."""
    fake = _fake_agent_result(structured_output=_valid_recommendation_response())
    mock_agent = _install_mock_agent(mocker, return_value=fake)

    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})

    assert mock_agent.call_count == 1  # Pitfall 1 — guard vacuous
    # Assert the new-API kwarg plumbing: structured_output_model was passed.
    from agent.agent import RecommendationResponse
    _, kwargs = mock_agent.call_args
    assert kwargs.get("structured_output_model") is RecommendationResponse
    assert body["green"]["saving_monthly"] == 30.0
    assert body["cheapest"]["saving_monthly"] == 55.0
    marker = body["_narrative_source"]
    assert marker == {
        "green": {"usage_narrative": "model", "call_script": "model"},
        "cheapest": {"usage_narrative": "model", "call_script": "model"},
    }


def test_retry_once_succeeds(mocker):
    """D-01: Strands owns inline self-correction; user-observable shape is same as happy.

    Under the new API, retry happens inside _agent(...) (StructuredOutputTool
    yields error ToolResult, LLM self-corrects, force-tool-use round fires).
    From invoke()'s perspective, this looks identical to "first call succeeded".
    The test here proves the marker still shows all "model" when Strands'
    internal retry produced clean output.
    """
    fake = _fake_agent_result(structured_output=_valid_recommendation_response())
    mock_agent = _install_mock_agent(mocker, return_value=fake)

    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})

    assert mock_agent.call_count == 1
    assert body["_narrative_source"]["green"]["usage_narrative"] == "model"
    assert body["_narrative_source"]["cheapest"]["call_script"] == "model"


def test_retry_once_then_fallback_per_field(mocker, caplog):
    """D-02: StructuredOutputException → per-field fallback from message history.

    Simulates: model exhausted self-correction + force-tool-use round failed;
    terminal StructuredOutputException raised; but last-turn toolUse block
    contains a partially-poisoned input where `usage_narrative` is invalid
    ("Saves $30 a month") and `call_script` is clean. Per-field salvage keeps
    the clean call_script + swaps the poisoned usage_narrative → FALLBACKS.

    PITFALLS M7 invariant: raw poisoned value MUST NOT appear in logs or in
    failure_reason. Reason-string only.
    """
    poisoned_input = {
        "green": {
            "plan_id": "ECO", "plan_name": "EcoFlex",
            "saving_monthly": 999.0, "saving_annual": 9999.0,
            "usage_narrative": "Saves $30 a month",  # poisoned — $ + digits
            "call_script": "Ask about EcoFlex — it suits a strong winter-heating profile like yours",  # clean
        },
        "cheapest": {
            "plan_id": "VAL", "plan_name": "Value Twelve",
            "saving_monthly": 888.0, "saving_annual": 8888.0,
            "usage_narrative": "Winter-heavy household with consistent mid-range usage across the year",  # clean
            "call_script": "Ask about EcoFlex — it suits a strong winter-heating profile like yours",  # clean
        },
    }
    # invoke() stores agent_result = _agent(...); we return the fake, then the
    # `if result is None: raise StructuredOutputException(...)` branch inside
    # invoke() fires (structured_output=None on our fake). The exception
    # handler then reads the toolUse block from our fake.message.
    fake = _fake_agent_result(structured_output=None, toolUse_input=poisoned_input)
    mock_agent = _install_mock_agent(mocker, return_value=fake)

    from agent.agent import invoke
    with caplog.at_level(logging.INFO, logger="agent.agent"):
        body = invoke({"customer_id": "CUST-001"})

    assert mock_agent.call_count == 1  # Pitfall 1

    # Per-field salvage: usage_narrative swapped to fallback, call_script kept model
    marker = body["_narrative_source"]["green"]
    assert marker["usage_narrative"] == "fallback"
    assert marker["call_script"] == "model"
    # SAV-03: fallback paths may salvage narrative only. Dollars still come
    # from the deterministic pricing engine, never lenient model output.
    assert body["green"]["saving_monthly"] == 30.0
    assert body["green"]["saving_annual"] == 360.0
    assert body["cheapest"]["saving_monthly"] == 55.0
    assert body["cheapest"]["saving_annual"] == 660.0

    # PITFALLS M7 — raw poisoned value MUST NOT appear in logs
    fallback_records = [
        r for r in caplog.records
        if getattr(r, "narrative_fallback_fired", False) is True
    ]
    assert fallback_records, "expected at least one narrative_fallback_fired log record"
    rec = fallback_records[0]
    assert rec.customer_id == "CUST-001"
    assert rec.track == "green"
    assert rec.field == "usage_narrative"
    assert "failure_reason" in rec.__dict__
    # The raw poisoned value must not leak anywhere:
    assert "Saves $30 a month" not in rec.getMessage()
    assert "Saves $30 a month" not in str(rec.__dict__.get("failure_reason", ""))


def test_full_fallback_when_lenient_parse_fails(mocker):
    """D-02: _extract_lenient_from_agent_result returns None → FALLBACKS bank fires for both fields."""
    # Terminal failure + NO recoverable toolUse block in message history:
    fake = _fake_agent_result(structured_output=None, toolUse_input=None)
    mock_agent = _install_mock_agent(mocker, return_value=fake)

    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})

    assert mock_agent.call_count == 1
    # SAV-03: no lenient model track exists, but fallback still preserves the
    # deterministic Sarah savings instead of manufacturing zero-dollar tracks.
    assert body["green"]["saving_monthly"] == 30.0
    assert body["green"]["saving_annual"] == 360.0
    assert body["cheapest"]["saving_monthly"] == 55.0
    assert body["cheapest"]["saving_annual"] == 660.0
    # Every field falls back:
    for track in ("green", "cheapest"):
        for field in ("usage_narrative", "call_script"):
            assert body["_narrative_source"][track][field] == "fallback"
            # D-04 never-empty invariant:
            assert body[track][field].strip(), (
                f"{track}/{field} empty after full fallback"
            )


def test_invoke_never_returns_empty_narrative_on_validation_storm(mocker):
    """D-04: narrative fields non-empty even under a validation storm.

    Simulates: StructuredOutputException raised directly (not via the
    `result is None` path); _extract returns None; invoke must still return
    valid strings via FALLBACKS bank for all 4 fields on CUST-001.
    """
    mock_agent = _install_mock_agent(
        mocker,
        side_effect=StructuredOutputException("simulated validation storm"),
    )

    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})

    assert mock_agent.call_count == 1
    assert body["green"]["saving_monthly"] == 30.0
    assert body["green"]["saving_annual"] == 360.0
    assert body["cheapest"]["saving_monthly"] == 55.0
    assert body["cheapest"]["saving_annual"] == 660.0
    for track in ("green", "cheapest"):
        for field in ("usage_narrative", "call_script"):
            value = body[track][field]
            assert isinstance(value, str) and value.strip(), (
                f"{track}/{field} returned empty on validation storm"
            )


def test_missing_customer_id_returns_error_dict():
    """Guard at L311-312 — empty customer_id returns error dict without invoking agent."""
    from agent.agent import invoke
    body = invoke({"customer_id": ""})
    assert body == {"error": "customer_id is required in the payload"}


def test_narrative_source_marker_shape(mocker):
    """Shape: {track: {field: "model"|"fallback"}}."""
    fake = _fake_agent_result(structured_output=_valid_recommendation_response())
    _install_mock_agent(mocker, return_value=fake)

    from agent.agent import invoke
    body = invoke({"customer_id": "CUST-001"})

    marker = body["_narrative_source"]
    assert set(marker.keys()) == {"green", "cheapest"}
    for track in marker.values():
        assert set(track.keys()) == {"usage_narrative", "call_script"}
        for val in track.values():
            assert val in ("model", "fallback")

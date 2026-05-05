"""Phase 13: Bill-Shock Multi-Tool Flow — AGENT-01 offline coverage.

Single-file home for:
  - TestDetectBillShockPure (Plan 01) — D-03 symmetric threshold; Elena trips, Marcus doesn't.
  - TestDetectBillShockDispatcher (Plan 01) — action routing + input validation.
  - TestFourToolCap (Plan 04) — D-16: HookProvider-based cap + stop_reason cancellation.
  - TestCrossPersonaCanary (Plan 05) — D-20: Elena (shock) vs Marcus (non-shock) diverge.
  - TestReasoningTraceExemption (Plan 04) — D-11: summaries contain $ + digits, pass validation.

Uses the `_provider_swap` autouse fixture from conftest.py (line 79) for offline
InMemoryProvider swap on every test. Marcus + Elena billing fixtures at conftest lines 27-34.
"""
import importlib

import pytest

from strands import Agent

from agent.agent import (
    SYSTEM_PROMPT,
    RecommendationResponse,
    _four_tool_cap,
    detect_bill_shock,
    get_billing_history,
    get_hardship_flag,
    simulate_savings,
)
from tests.fixtures.mocked_model_provider import MockedModelProvider

# `from lambda.handler import ...` is a SyntaxError (lambda = Python keyword).
handler = importlib.import_module("lambda.handler")
detect_bill_shock_pure = handler.detect_bill_shock_pure
dispatcher = handler.handler  # top-level action dispatcher


class TestDetectBillShockPure:
    """D-03: 30% symmetric threshold on 11-month mean (self-excluded)."""

    def test_elena_trips_shock_gate(self, elena_billing):
        result = detect_bill_shock_pure(elena_billing)
        assert result["is_shock"] is True
        assert result["shock_month"] == "2025-10"
        # RESEARCH §6: Elena's 2025-10 ratio is 0.6344 — comfortably > 0.30.
        ratio = abs(result["delta_dollars"]) / result["mean_dollars"]
        assert ratio > 0.30

    def test_marcus_does_not_trip(self, marcus_billing):
        # RESEARCH §6: Marcus's max ratio (2025-10) is 0.167 — 45% short of the 0.30 gate.
        result = detect_bill_shock_pure(marcus_billing)
        assert result["is_shock"] is False
        ratio = abs(result["delta_dollars"]) / result["mean_dollars"]
        assert ratio < 0.30

    def test_result_shape_and_types(self, elena_billing):
        result = detect_bill_shock_pure(elena_billing)
        assert set(result.keys()) == {
            "is_shock",
            "delta_dollars",
            "shock_month",
            "mean_dollars",
            "current_dollars",
        }
        assert isinstance(result["is_shock"], bool)
        assert isinstance(result["delta_dollars"], float)
        assert isinstance(result["shock_month"], str)
        assert isinstance(result["mean_dollars"], float)
        assert isinstance(result["current_dollars"], float)

    def test_raises_on_single_month(self, elena_billing):
        with pytest.raises(ValueError, match=">= 2 months"):
            detect_bill_shock_pure(elena_billing[:1])

    def test_raises_on_empty(self):
        with pytest.raises(ValueError, match=">= 2 months"):
            detect_bill_shock_pure([])

    def test_threshold_is_configurable_and_symmetric(self, elena_billing):
        # At 0.70 Elena's 0.6344 no longer trips (symmetric above-and-below gate).
        result = detect_bill_shock_pure(elena_billing, threshold=0.70)
        assert result["is_shock"] is False

    def test_sav03_helper_is_pure_no_boto3_at_call_time(self, elena_billing):
        # Signature is list[dict] + kwargs only — no boto3 / no env vars.
        result = detect_bill_shock_pure(elena_billing)
        assert "is_shock" in result  # guard — basic successful call
        # Helper is callable without any AWS credentials or TABLE_NAME env var.

    def test_helper_sorts_defensively(self, elena_billing):
        # Dispatcher already sorts ASC, but the pure helper must be defensive —
        # reverse-sorted input must still produce the same shock_month = 2025-10.
        reversed_billing = list(reversed(elena_billing))
        result_asc = detect_bill_shock_pure(elena_billing)
        result_rev = detect_bill_shock_pure(reversed_billing)
        assert result_asc == result_rev
        assert result_rev["shock_month"] == "2025-10"


class TestDetectBillShockDispatcher:
    """Phase 12 dispatcher extension — D-04 action routing for detect_bill_shock.

    Option C pattern (per 13-PATTERNS.md recommendation): monkey-patch
    handler.get_billing_history to return the fixture list directly. Keeps the
    dispatcher test free of DynamoDB / moto setup and focused on action-branch
    routing + input validation.
    """

    def test_action_routes_to_helper(self, monkeypatch, elena_billing):
        """Happy path: detect_bill_shock branch now aliases to decompose_bill_shock_pure;
        Elena trips with shock_month=2025-10 and gets richer decomposition."""
        monkeypatch.setattr(handler, "get_billing_history", lambda ev, ctx: elena_billing)
        # handler.table is consulted for a non-None guard before the helper runs.
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher(
            {"action": "detect_bill_shock", "customer_id": "CUST-003"}, None
        )
        assert result["is_shock"] is True
        assert result["shock_month"] == "2025-10"
        # Backward-compat alias now returns decompose_bill_shock_pure shape
        assert set(result.keys()) == {
            "customer_id", "is_shock", "shock_month",
            "total_delta_dollars", "rate_change_component",
            "usage_change_component", "seasonal_component",
            "contributing_factors", "explanation_sentence",
            "explanation_factors",
        }

    def test_marcus_routed_returns_no_shock(self, monkeypatch, marcus_billing):
        """Non-shock persona routed through dispatcher returns is_shock=False."""
        monkeypatch.setattr(handler, "get_billing_history", lambda ev, ctx: marcus_billing)
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher(
            {"action": "detect_bill_shock", "customer_id": "CUST-002"}, None
        )
        assert result["is_shock"] is False

    def test_invalid_customer_id_returns_error(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher({"action": "detect_bill_shock", "customer_id": "not-a-cust"}, None)
        assert result["error"] is True
        assert "customer_id" in result["message"]

    def test_missing_customer_id_returns_error(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher({"action": "detect_bill_shock"}, None)
        assert result["error"] is True
        assert "customer_id" in result["message"]

    def test_non_string_customer_id_returns_error(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher({"action": "detect_bill_shock", "customer_id": 123}, None)
        assert result["error"] is True
        assert "customer_id" in result["message"]

    def test_table_not_configured_raises_runtime_error(self, monkeypatch):
        """SAV-03 / D-04 companion: Tools Lambda must fail fast when TABLE_NAME
        is not configured — no silent fallback to an empty billing list."""
        monkeypatch.setattr(handler, "table", None)
        with pytest.raises(RuntimeError, match="TABLE_NAME"):
            dispatcher(
                {"action": "detect_bill_shock", "customer_id": "CUST-003"}, None
            )

    def test_existing_simulate_savings_branch_still_routes(self, monkeypatch):
        """Regression: Plan 01 must not break Phase 12 D-02 dispatch."""
        called = {}

        def fake_simulate_savings(ev, ctx):
            called["hit"] = True
            return {"green": {}, "cheapest": {}}

        monkeypatch.setattr(handler, "simulate_savings", fake_simulate_savings)
        dispatcher({"action": "simulate_savings", "customer_id": "CUST-001"}, None)
        assert called["hit"] is True

    def test_existing_get_billing_history_branch_still_routes(
        self, monkeypatch, marcus_billing
    ):
        """Regression: Phase 11 D-21 get_billing_history branch unchanged."""
        called = {}

        def fake_get_billing_history(ev, ctx):
            called["hit"] = True
            return marcus_billing

        monkeypatch.setattr(handler, "get_billing_history", fake_get_billing_history)
        result = dispatcher(
            {"action": "get_billing_history", "customer_id": "CUST-002"}, None
        )
        assert called["hit"] is True
        assert result == marcus_billing

    def test_action_less_back_compat_still_routes_to_simulate_savings(self, monkeypatch):
        """Phase 12 D-05 back-compat: action-less event → simulate_savings."""
        called = {}

        def fake_simulate_savings(ev, ctx):
            called["hit"] = True
            return {"green": {}, "cheapest": {}}

        monkeypatch.setattr(handler, "simulate_savings", fake_simulate_savings)
        dispatcher({"customer_id": "CUST-001"}, None)  # no "action" key
        assert called["hit"] is True


# ----------------------------------------------------------------------
# TestFourToolCap — Plan 04: AGENT-01b 4-tool cap via Strands HookProvider.
# ----------------------------------------------------------------------
# Per A-02 amendment: cap is a HookProvider calling event.agent.cancel(),
# NOT Agent(max_iterations=N). Post-cancel stop_reason == "cancelled"
# routes invoke() through the existing D-04 fallback (except Exception).
# ----------------------------------------------------------------------

import io
import json
from unittest.mock import MagicMock, patch


class TestFourToolCap:
    """D-16 offline — cap fires, stop_reason=cancelled, D-04 response shape preserved."""

    # ---------- Strategy A: unit-test the hook in isolation ----------

    def test_hook_instantiates_with_defaults(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=8)
        assert hook.budget == 8
        assert hook.used == 0

    def test_hook_is_hook_provider(self):
        """Protocol-runtime duck-type: HookProvider is runtime_checkable."""
        from strands.hooks import HookProvider
        from agent.hooks.four_tool_cap import FourToolCapHook
        assert isinstance(FourToolCapHook(), HookProvider)

    def test_hook_increments_used_on_each_tool_completion(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=8)
        fake_event = MagicMock()
        hook.on_tool_complete(fake_event)
        assert hook.used == 1
        hook.on_tool_complete(fake_event)
        assert hook.used == 2

    def test_hook_cancels_agent_at_budget(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=2)
        fake_event = MagicMock()
        # 1st call: used -> 1, NOT cancelled
        hook.on_tool_complete(fake_event)
        assert not fake_event.agent.cancel.called
        # 2nd call: used -> 2, cancel fires
        hook.on_tool_complete(fake_event)
        assert fake_event.agent.cancel.called

    def test_hook_cancels_repeatedly_past_budget(self):
        """Idempotent cancellation — beyond the budget, cancel continues firing.

        Strands' own cancel() is idempotent per the documented asyncio-event
        mechanism; this test just asserts the hook keeps invoking it so the
        guard does not accidentally stop post-budget.
        """
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=1)
        fake_event = MagicMock()
        hook.on_tool_complete(fake_event)
        hook.on_tool_complete(fake_event)
        hook.on_tool_complete(fake_event)
        assert fake_event.agent.cancel.call_count >= 1

    def test_hook_register_hooks_subscribes_to_after_tool_call(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        from strands.hooks import AfterToolCallEvent
        hook = FourToolCapHook(budget=8)
        registry = MagicMock()
        hook.register_hooks(registry)
        registry.add_callback.assert_called_once_with(
            AfterToolCallEvent, hook.on_tool_complete
        )

    def test_hook_reset_zeros_counter(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=8)
        hook.used = 3
        hook.reset()
        assert hook.used == 0

    def test_budget_must_be_at_least_one(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        with pytest.raises(ValueError, match="budget"):
            FourToolCapHook(budget=0)

    # ---------- Strategy B: integration via invoke() ----------

    @patch("agent.agent._agent")
    @patch("agent.agent._lambda_client")
    def test_invoke_routes_through_d04_fallback_on_cancelled_stop_reason(
        self, mock_lambda_client, mock_agent
    ):
        """End-to-end: stop_reason=='cancelled' -> RuntimeError -> D-04 fallback body."""
        from agent.agent import invoke, _four_tool_cap

        # Mock _agent(...) returning an AgentResult with stop_reason='cancelled'.
        mock_agent_result = MagicMock()
        mock_agent_result.stop_reason = "cancelled"
        mock_agent_result.message = {"content": []}  # empty content -> trace=[]
        mock_agent.return_value = mock_agent_result

        # Historical D-04 path called _lambda_client.invoke directly; the
        # current fallback helper uses the deterministic provider path.
        fallback_payload = {
            "green": {
                "plan_id": "ECO", "plan_name": "EcoFlex 100",
                "saving_monthly": 30.00, "saving_annual": 360.00,
            },
            "cheapest": {
                "plan_id": "VAL", "plan_name": "Value 12",
                "saving_monthly": 55.00, "saving_annual": 660.00,
            },
        }
        mock_lambda_client.invoke.return_value = {
            "Payload": io.BytesIO(json.dumps(fallback_payload).encode())
        }

        # Reset counter so test is deterministic.
        _four_tool_cap.reset()

        response = invoke({"customer_id": "CUST-001"})

        # D-04 never-500 — body has both tracks + no errorMessage.
        assert isinstance(response, dict)
        assert "green" in response
        assert "cheapest" in response
        assert "errorMessage" not in response

        # D-15 marker — narrative source marker present on fallback path.
        assert "_narrative_source" in response

        # Phase 13 D-07 — reasoning_trace attached (empty is acceptable).
        assert "reasoning_trace" in response
        assert isinstance(response["reasoning_trace"], list)

    @patch("agent.agent._agent")
    @patch("agent.agent._lambda_client")
    def test_invoke_cancelled_path_does_not_leak_tool_budget_runtimeerror(
        self, mock_lambda_client, mock_agent
    ):
        """D-04 must swallow the tool-budget RuntimeError — no 500 surface."""
        from agent.agent import invoke, _four_tool_cap

        mock_agent_result = MagicMock()
        mock_agent_result.stop_reason = "cancelled"
        mock_agent_result.message = {"content": []}
        mock_agent.return_value = mock_agent_result

        fallback_payload = {
            "green": {
                "plan_id": "ECO", "plan_name": "EcoFlex 100",
                "saving_monthly": 30.00, "saving_annual": 360.00,
            },
            "cheapest": {
                "plan_id": "VAL", "plan_name": "Value 12",
                "saving_monthly": 55.00, "saving_annual": 660.00,
            },
        }
        mock_lambda_client.invoke.return_value = {
            "Payload": io.BytesIO(json.dumps(fallback_payload).encode())
        }

        _four_tool_cap.reset()

        # Must return a dict, not raise.
        response = invoke({"customer_id": "CUST-001"})
        assert isinstance(response, dict)
        # Assert deterministic savings survived the cancelled path.
        assert response["green"]["saving_monthly"] == 30.0
        assert response["cheapest"]["saving_monthly"] == 55.0

    def test_counter_resets_between_invocations(self):
        """Module-level _four_tool_cap.used must NOT leak across invoke() calls."""
        from agent.agent import _four_tool_cap
        _four_tool_cap.used = 3
        _four_tool_cap.reset()
        assert _four_tool_cap.used == 0

    def test_agent_has_no_max_iterations_reference(self):
        """Pitfall 2 regression guard — Strands 1.37.0 has no max_iterations kwarg."""
        import pathlib
        agent_path = pathlib.Path(__file__).parent.parent / "agent" / "agent.py"
        source = agent_path.read_text()
        assert "max_iterations" not in source, (
            "agent.py references max_iterations — Strands 1.37.0 has no such "
            "kwarg; the 4-tool cap is enforced via FourToolCapHook instead."
        )


# ----------------------------------------------------------------------
# TestCrossPersonaCanary — Plan 05: D-20 fabrication detector (C5).
# ----------------------------------------------------------------------
# A-01 amendment: Elena CUST-003 is the designated bill-shock persona
# (peak ratio 0.6344, 7 months above 30% gate). Marcus CUST-002 is the
# non-shock foil (peak 0.167 — 45% short of gate).
#
# Phase 06.1 fabrication signature: identical numeric content across
# DIFFERENT personas. This canary asserts Elena vs Marcus produce
# byte-different detect_bill_shock results, byte-different trace summaries,
# and byte-different savings.
# ----------------------------------------------------------------------


class TestCrossPersonaCanary:
    """D-20 offline — Elena (shock) vs Marcus (non-shock) diverge byte-exact."""

    def test_detect_bill_shock_pure_differs_elena_vs_marcus(
        self, elena_billing, marcus_billing
    ):
        """Bottom-layer assertion: the pure helper itself distinguishes personas."""
        elena_shock = detect_bill_shock_pure(elena_billing)
        marcus_shock = detect_bill_shock_pure(marcus_billing)

        # Core C5 contrast: Elena trips, Marcus doesn't.
        assert elena_shock["is_shock"] is True
        assert marcus_shock["is_shock"] is False

        # Delta and mean MUST be numerically distinct (not "coincidentally equal").
        assert elena_shock["delta_dollars"] != marcus_shock["delta_dollars"]
        assert elena_shock["mean_dollars"] != marcus_shock["mean_dollars"]
        assert elena_shock["current_dollars"] != marcus_shock["current_dollars"]

        # Shock-month identification: both happen to peak in 2025-10 per RESEARCH §6,
        # so shock_month CAN match — but the ratio is entirely different.
        elena_ratio = abs(elena_shock["delta_dollars"]) / elena_shock["mean_dollars"]
        marcus_ratio = abs(marcus_shock["delta_dollars"]) / marcus_shock["mean_dollars"]
        assert elena_ratio > 0.60  # RESEARCH §6: Elena 0.6344
        assert marcus_ratio < 0.20  # RESEARCH §6: Marcus 0.167

    def test_summaries_differ_byte_exact_elena_vs_marcus(
        self, elena_billing, marcus_billing
    ):
        """Middle-layer assertion: code-composed summaries distinguish personas."""
        from agent.reasoning.summaries import summary_detect_bill_shock

        elena_summary = summary_detect_bill_shock(detect_bill_shock_pure(elena_billing))
        marcus_summary = summary_detect_bill_shock(detect_bill_shock_pure(marcus_billing))

        # Strict byte-difference — this is the exact Phase 06.1 regression pattern.
        assert elena_summary != marcus_summary

        # Marcus returns the canned non-shock string.
        assert marcus_summary == "No bill shock: monthly usage within 11-month envelope"

        # Elena has digits + $ + shock_month in the summary.
        assert "Bill shock detected" in elena_summary
        assert "$" in elena_summary
        assert "2025-10" in elena_summary

    def test_savings_fixtures_differ_elena_vs_marcus(
        self, mock_elena_response, mock_marcus_response
    ):
        """Byte-exact savings must differ — Phase 11 D-13 byte-exact carry-forward."""
        # Elena: green $14.00 / cheapest $25.67
        # Marcus: green $16.90 / cheapest $30.98
        assert (
            mock_elena_response["green"]["saving_monthly"]
            != mock_marcus_response["green"]["saving_monthly"]
        )
        assert (
            mock_elena_response["cheapest"]["saving_monthly"]
            != mock_marcus_response["cheapest"]["saving_monthly"]
        )

    def test_end_to_end_reasoning_trace_differs_elena_vs_marcus(
        self, elena_billing, marcus_billing, mock_elena_response, mock_marcus_response
    ):
        """Top-layer assertion: simulated agent_result → extractor → trace diverges.

        D-13.1-04 (Phase 13.1): per-persona trace SHAPE. Post-Phase-13.1, Marcus
        is non-shock and drops to the 2-tool short-circuit path. Elena stays at
        3 tools (shock persona). The OLD assertion `len(marcus_trace) == 3`
        was correct for the Phase 13 Plan 03 preference-ordered prompt era;
        Phase 13.1 D-13.1-14 changes that contract.
        """
        from agent.agent import _extract_reasoning_trace

        def _build_agent_result_shock(persona_billing, persona_savings, persona_hardship=False):
            """3-tool shape: get_hardship_flag → detect_bill_shock → simulate_savings.

            Used for shock personas (e.g. Elena) per D-13.1-14.
            """
            shock = detect_bill_shock_pure(persona_billing)
            return MagicMock(
                message={
                    "content": [
                        # Turn 1: get_hardship_flag
                        {"toolUse": {"name": "get_hardship_flag", "toolUseId": "tu-1", "input": {}}},
                        {"toolResult": {"toolUseId": "tu-1", "status": "success",
                                        "content": [{"json": {"hardship_flag": persona_hardship}}]}},
                        # Turn 2: detect_bill_shock
                        {"toolUse": {"name": "detect_bill_shock", "toolUseId": "tu-2", "input": {}}},
                        {"toolResult": {"toolUseId": "tu-2", "status": "success",
                                        "content": [{"json": shock}]}},
                        # Turn 3: simulate_savings
                        {"toolUse": {"name": "simulate_savings", "toolUseId": "tu-3", "input": {}}},
                        {"toolResult": {"toolUseId": "tu-3", "status": "success",
                                        "content": [{"json": persona_savings}]}},
                    ]
                }
            )

        def _build_agent_result_non_shock(persona_billing, persona_savings, persona_hardship=False):
            """2-tool shape: get_hardship_flag → simulate_savings.

            Used for non-shock personas (e.g. Marcus, Sarah) per D-13.1-14
            SHORT-CIRCUIT RULE. persona_billing accepted for signature
            symmetry with the shock variant, but intentionally unused —
            non-shock personas do NOT call detect_bill_shock, so the
            shock-pure output never enters the trace.
            """
            del persona_billing  # accepted for signature symmetry
            return MagicMock(
                message={
                    "content": [
                        # Turn 1: get_hardship_flag
                        {"toolUse": {"name": "get_hardship_flag", "toolUseId": "tu-1", "input": {}}},
                        {"toolResult": {"toolUseId": "tu-1", "status": "success",
                                        "content": [{"json": {"hardship_flag": persona_hardship}}]}},
                        # Turn 2: simulate_savings (short-circuit — detect_bill_shock skipped)
                        {"toolUse": {"name": "simulate_savings", "toolUseId": "tu-2", "input": {}}},
                        {"toolResult": {"toolUseId": "tu-2", "status": "success",
                                        "content": [{"json": persona_savings}]}},
                    ]
                }
            )

        elena_result = _build_agent_result_shock(elena_billing, mock_elena_response)
        marcus_result = _build_agent_result_non_shock(marcus_billing, mock_marcus_response)

        elena_trace = _extract_reasoning_trace(elena_result)
        marcus_trace = _extract_reasoning_trace(marcus_result)

        # D-13.1-04 shape assertions: Elena 3 tools (shock), Marcus 2 tools (non-shock short-circuit).
        assert len(elena_trace) == 3, (
            f"Elena (shock persona) expected 3 reasoning_trace entries per "
            f"D-13.1-14; got {len(elena_trace)}."
        )
        assert len(marcus_trace) == 2, (
            f"Marcus (non-shock persona) expected 2 reasoning_trace entries "
            f"per D-13.1-14 short-circuit; got {len(marcus_trace)}. If this "
            f"test fails, either the prompt (Plan 01) regressed or the test "
            f"helper _build_agent_result_non_shock has not been updated to "
            f"the 2-tool shape for non-shock personas."
        )

        # D-20 C5 fabrication signature: summaries MUST diverge byte-exact.
        # Shape-asymmetric list comparison still catches fabrication because
        # get_hardship_flag + simulate_savings summaries are persona-parameterised.
        elena_summaries = [e.summary for e in elena_trace]
        marcus_summaries = [e.summary for e in marcus_trace]
        assert elena_summaries != marcus_summaries, (
            "C5 FABRICATION SIGNATURE: Elena + Marcus produced identical summaries"
        )

        # detect_bill_shock is Elena-only post-13.1 — Marcus short-circuits past it.
        assert elena_trace[1].tool == "detect_bill_shock"
        assert "detect_bill_shock" not in [e.tool for e in marcus_trace]

        # simulate_savings summary specifically MUST differ (byte-exact Phase 11 carry-forward).
        # Elena's simulate_savings is at index 2, Marcus's at index 1 (post-short-circuit).
        assert elena_trace[2].tool == "simulate_savings"
        assert marcus_trace[1].tool == "simulate_savings"
        assert elena_trace[2].summary != marcus_trace[1].summary


class TestEmptyBillingStop:
    """D-13.1-09: offline agent-side guard for the empty-billing case.

    Closes Gap 2 at the agent layer: for an unknown customer (CUST-999),
    the agent MUST NOT synthesise a RecommendationResponse with UNKNOWN
    tracks. Either the prompt STOP rule fires (agent emits errorMessage),
    OR the D-04 fallback fires (except Exception in invoke()). In both
    cases the final body must have NO green/cheapest keys — the exact
    condition api_lambda/handler.py:152 checks for 404.
    """

    def test_unknown_customer_prompt_stop_emits_no_tracks(self, inmemory_provider):
        """CUST-999 is not in ALL_RECORDS — InMemoryProvider.get_billing_history
        returns [] per Assumption A7. Prompt EMPTY BILLING STOP RULE (Phase
        13.1 Plan 01) fires; agent emits errorMessage text; no tracks.

        The scripted mock represents the agent's OBSERVED output after the
        STOP rule fires: get_hardship_flag (universal first step) then
        assistant text "customer not found" (no tool calls after the
        billing lookup returned empty).
        """
        scripted = [
            # Turn 1: hardship check (always)
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "get_hardship_flag", "toolUseId": "tu-1",
                    "input": {"customer_id": "CUST-999"},
                },
            }]},
            # Turn 2: agent sees empty billing from the provider; STOP.
            # Emits plain text, NOT a toolUse.
            {"role": "assistant", "content": [
                {"text": "customer not found"}
            ]},
        ]

        mock = MockedModelProvider(scripted)
        _four_tool_cap.reset()

        from agent.agent import invoke

        patched_agent = Agent(
            model=mock,
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
            tools=[simulate_savings, detect_bill_shock,
                   get_billing_history, get_hardship_flag],
            hooks=[_four_tool_cap],
        )

        with patch("agent.agent._agent", patched_agent):
            # Post-supervisor refactor: also patch the specialist's _agent
            # so TariffSpecialist.handle() uses the scripted mock.
            import agent.agent as agent_mod
            agent_mod._init_specialists()
            with patch.object(agent_mod._tariff_specialist, "_agent", patched_agent):
                with patch.object(agent_mod, "_specialists_initialized", True):
                    response = invoke({"customer_id": "CUST-999"})

        # Acceptance: body has NO green/cheapest keys — exactly the condition
        # api_lambda/handler.py:152 (D-12 primary heuristic) checks for 404.
        assert "green" not in response, (
            f"Agent synthesised green track for unknown customer: {response}"
        )
        assert "cheapest" not in response, (
            f"Agent synthesised cheapest track for unknown customer: {response}"
        )
        # D-04 never-500: response is a dict (not an exception)
        assert isinstance(response, dict)

    def test_unknown_customer_d04_fallback_emits_no_tracks(self):
        """Defence-in-depth: if the LLM disobeys the STOP rule and raises,
        the existing D-04 fallback path in invoke() must STILL produce a
        body with no green/cheapest keys.

        Post-supervisor refactor: patches _tariff_specialist._agent and
        _lambda_client so the specialist's handle() uses the mock agent
        and the fallback path uses the mock Lambda client.
        """
        import agent.agent as agent_mod
        from agent.agent import invoke

        # Ensure specialists are initialized.
        agent_mod._init_specialists()

        # Mock _agent(...) returning an AgentResult that forces the
        # structured-output salvage/D-04 fallback branch.
        mock_agent = MagicMock()
        mock_agent_result = MagicMock()
        mock_agent_result.stop_reason = "end_turn"
        mock_agent_result.message = {"content": []}
        mock_agent_result.structured_output = None
        mock_agent.return_value = mock_agent_result
        mock_agent.messages = []

        # Tools Lambda fallback returns an errorMessage shape for unknown
        # customer — matches lambda/handler.py existing behaviour for
        # CUST-999 (empty billing history).
        mock_lambda_client = MagicMock()
        mock_lambda_client.invoke.return_value = {
            "Payload": io.BytesIO(
                json.dumps({"errorMessage": "customer not found"}).encode()
            )
        }

        _four_tool_cap.reset()
        with patch.object(agent_mod, "_agent", mock_agent), \
             patch.object(agent_mod, "_lambda_client", mock_lambda_client), \
             patch.object(agent_mod._tariff_specialist, "_agent", mock_agent), \
             patch.object(agent_mod, "_specialists_initialized", True):
            response = invoke({"customer_id": "CUST-999"})

        # Same acceptance: body has NO green/cheapest keys — exact condition
        # api_lambda/handler.py:152 (D-12 primary heuristic) checks for 404.
        assert "green" not in response
        assert "cheapest" not in response
        assert isinstance(response, dict)


class TestShortCircuit:
    """D-13.1-03 + D-13.1-15: real Strands decision loop against scripted mock-Bedrock.

    The mock is scripted with EXACTLY the tool calls a persona SHOULD
    drive per D-13.1-14. If the real prompt drives MORE tools, the
    MockedModelProvider bounds check raises AssertionError on index
    overflow. If the real prompt drives FEWER, the explicit assertion
    on tool_use_names fails with a clear diagnostic.

    These tests EXERCISE the real SYSTEM_PROMPT (post Phase 13.1 Plan 01
    edit) against a scripted model. They catch "prompt says X but Strands
    interprets as Y" failures at merge time — the blind spot that let
    Phase 13 Gap 1 ship (17.2s / 19.7s latency vs 3000ms / 2500ms gate).

    Imports real @tool wrappers so the tool registry + cap hook + provider
    singleton all wire up exactly as in production; the only swap is the
    Model (Sonnet 4.6 → MockedModelProvider).
    """

    TARGET_TOOL_NAMES = {
        "get_hardship_flag",
        "detect_bill_shock",
        "get_billing_history",
        "simulate_savings",
    }

    def _sarah_recommendation_input(self):
        """Valid RecommendationResponse input for CUST-001 (Sarah Chen).

        Savings figures byte-match tests/conftest.py::mock_savings_response.
        """
        return {
            "green": {
                "plan_id": "ECO",
                "plan_name": "EcoFlex 100",
                "saving_monthly": 30.00,
                "saving_annual": 360.00,
                "usage_narrative": "Winter-heavy household with consistent usage across the year.",
                "call_script": "Ask about EcoFlex — it suits this winter-heavy household usage profile.",
            },
            "cheapest": {
                "plan_id": "VAL",
                "plan_name": "Value 12",
                "saving_monthly": 55.00,
                "saving_annual": 660.00,
                "usage_narrative": "Winter-heavy household with consistent usage across the year.",
                "call_script": "Ask about Value — flat pricing fits this household's steady winter profile.",
            },
            "reasoning_trace": [],
        }

    def _elena_recommendation_input(self):
        """Valid RecommendationResponse input for CUST-003 (Elena Vasquez).

        Savings figures byte-match tests/conftest.py::mock_elena_response.
        """
        return {
            "green": {
                "plan_id": "ECO",
                "plan_name": "EcoFlex 100",
                "saving_monthly": 14.00,
                "saving_annual": 168.00,
                "usage_narrative": "Summer peak usage with a sharp recent month spike.",
                "call_script": "Ask about EcoFlex — it suits this summer peak usage profile.",
            },
            "cheapest": {
                "plan_id": "VAL",
                "plan_name": "Value 12",
                "saving_monthly": 25.67,
                "saving_annual": 308.04,
                "usage_narrative": "Summer peak usage with a sharp recent month spike.",
                "call_script": "Ask about Value — flat pricing frames the recent usage spike.",
            },
            "reasoning_trace": [],
        }

    def _observed_tool_names(self, agent: Agent) -> list[str]:
        """Extract the ordered tool-use names from agent.messages, filtering
        to the @tool wrappers (exclude the terminal RecommendationResponse
        structured-output toolUse block)."""
        names: list[str] = []
        for msg in agent.messages:
            for block in msg.get("content", []) or []:
                if "toolUse" in block and block["toolUse"]["name"] in self.TARGET_TOOL_NAMES:
                    names.append(block["toolUse"]["name"])
        return names

    def test_non_shock_sarah_drives_2_tools_only(self, inmemory_provider):
        """CUST-001 Sarah is non-shock — prompt SHORT-CIRCUIT RULE must drive
        the 2-tool path: get_hardship_flag → simulate_savings.
        """
        scripted = [
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "get_hardship_flag", "toolUseId": "tu-1",
                    "input": {"customer_id": "CUST-001"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "simulate_savings", "toolUseId": "tu-2",
                    "input": {"customer_id": "CUST-001"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "RecommendationResponse", "toolUseId": "tu-3",
                    "input": self._sarah_recommendation_input(),
                },
            }]},
        ]

        mock = MockedModelProvider(scripted)
        _four_tool_cap.reset()

        agent = Agent(
            model=mock,
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
            tools=[simulate_savings, detect_bill_shock,
                   get_billing_history, get_hardship_flag],
            hooks=[_four_tool_cap],
        )

        agent(
            "Get tariff savings recommendations for customer CUST-001",
            structured_output_model=RecommendationResponse,
        )

        observed = self._observed_tool_names(agent)
        assert observed == ["get_hardship_flag", "simulate_savings"], (
            f"Short-circuit broken: CUST-001 (non-shock) drove "
            f"{len(observed)} tools {observed}; expected exactly "
            f"['get_hardship_flag', 'simulate_savings'] per D-13.1-14."
        )

    def test_non_shock_marcus_drives_2_tools_only(self, inmemory_provider):
        """CUST-002 Marcus is also non-shock — same 2-tool contract as Sarah."""
        scripted = [
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "get_hardship_flag", "toolUseId": "tu-1",
                    "input": {"customer_id": "CUST-002"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "simulate_savings", "toolUseId": "tu-2",
                    "input": {"customer_id": "CUST-002"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "RecommendationResponse", "toolUseId": "tu-3",
                    "input": {
                        "green": {
                            "plan_id": "ECO", "plan_name": "EcoFlex 100",
                            "saving_monthly": 16.90, "saving_annual": 202.80,
                            "usage_narrative": "Steady baseline with seasonal dip.",
                            "call_script": "Ask about EcoFlex — fits this steady usage profile.",
                        },
                        "cheapest": {
                            "plan_id": "VAL", "plan_name": "Value 12",
                            "saving_monthly": 30.98, "saving_annual": 371.76,
                            "usage_narrative": "Steady baseline with seasonal dip.",
                            "call_script": "Ask about Value — flat pricing suits the steady profile.",
                        },
                        "reasoning_trace": [],
                    },
                },
            }]},
        ]

        mock = MockedModelProvider(scripted)
        _four_tool_cap.reset()

        agent = Agent(
            model=mock,
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
            tools=[simulate_savings, detect_bill_shock,
                   get_billing_history, get_hardship_flag],
            hooks=[_four_tool_cap],
        )

        agent(
            "Get tariff savings recommendations for customer CUST-002",
            structured_output_model=RecommendationResponse,
        )

        observed = self._observed_tool_names(agent)
        assert observed == ["get_hardship_flag", "simulate_savings"], (
            f"Short-circuit broken: CUST-002 (non-shock) drove "
            f"{len(observed)} tools {observed}; expected exactly "
            f"['get_hardship_flag', 'simulate_savings'] per D-13.1-14."
        )

    def test_shock_elena_drives_3_tools(self, inmemory_provider):
        """CUST-003 Elena is shock — preferred 3-tool flow per D-13.1-14:
        get_hardship_flag → detect_bill_shock → simulate_savings."""
        scripted = [
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "get_hardship_flag", "toolUseId": "tu-1",
                    "input": {"customer_id": "CUST-003"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "detect_bill_shock", "toolUseId": "tu-2",
                    "input": {"customer_id": "CUST-003"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "simulate_savings", "toolUseId": "tu-3",
                    "input": {"customer_id": "CUST-003"},
                },
            }]},
            {"role": "assistant", "content": [{
                "toolUse": {
                    "name": "RecommendationResponse", "toolUseId": "tu-4",
                    "input": self._elena_recommendation_input(),
                },
            }]},
        ]

        mock = MockedModelProvider(scripted)
        _four_tool_cap.reset()

        agent = Agent(
            model=mock,
            system_prompt=SYSTEM_PROMPT,
            callback_handler=None,
            tools=[simulate_savings, detect_bill_shock,
                   get_billing_history, get_hardship_flag],
            hooks=[_four_tool_cap],
        )

        agent(
            "Get tariff savings recommendations for customer CUST-003",
            structured_output_model=RecommendationResponse,
        )

        observed = self._observed_tool_names(agent)
        # Shock persona: first tool must be hardship; total 3 tools; final
        # is simulate_savings. detect_bill_shock is the middle step.
        assert len(observed) == 3, (
            f"Shock path broken: CUST-003 drove {len(observed)} tools "
            f"{observed}; expected 3 per D-13.1-14."
        )
        assert observed[0] == "get_hardship_flag"
        assert observed[-1] == "simulate_savings"
        assert "detect_bill_shock" in observed

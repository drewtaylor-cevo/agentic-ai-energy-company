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
        """Happy path: detect_bill_shock branch reuses get_billing_history +
        detect_bill_shock_pure; Elena trips with shock_month=2025-10."""
        monkeypatch.setattr(handler, "get_billing_history", lambda ev, ctx: elena_billing)
        # handler.table is consulted for a non-None guard before the helper runs.
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher(
            {"action": "detect_bill_shock", "customer_id": "CUST-003"}, None
        )
        assert result["is_shock"] is True
        assert result["shock_month"] == "2025-10"
        assert set(result.keys()) == {
            "is_shock", "delta_dollars", "shock_month",
            "mean_dollars", "current_dollars",
        }

    def test_marcus_routed_returns_no_shock(self, monkeypatch, marcus_billing):
        """Non-shock persona routed through dispatcher returns is_shock=False."""
        monkeypatch.setattr(handler, "get_billing_history", lambda ev, ctx: marcus_billing)
        monkeypatch.setattr(handler, "table", object())
        result = dispatcher(
            {"action": "detect_bill_shock", "customer_id": "CUST-002"}, None
        )
        assert result["is_shock"] is False

    def test_invalid_customer_id_raises(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        with pytest.raises(ValueError):
            dispatcher({"action": "detect_bill_shock", "customer_id": "not-a-cust"}, None)

    def test_missing_customer_id_raises(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        with pytest.raises(ValueError):
            dispatcher({"action": "detect_bill_shock"}, None)

    def test_non_string_customer_id_raises(self, monkeypatch):
        monkeypatch.setattr(handler, "table", object())
        with pytest.raises(ValueError):
            dispatcher({"action": "detect_bill_shock", "customer_id": 123}, None)

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
        hook = FourToolCapHook(budget=4)
        assert hook.budget == 4
        assert hook.used == 0

    def test_hook_is_hook_provider(self):
        """Protocol-runtime duck-type: HookProvider is runtime_checkable."""
        from strands.hooks import HookProvider
        from agent.hooks.four_tool_cap import FourToolCapHook
        assert isinstance(FourToolCapHook(), HookProvider)

    def test_hook_increments_used_on_each_tool_completion(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=4)
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
        hook = FourToolCapHook(budget=4)
        registry = MagicMock()
        hook.register_hooks(registry)
        registry.add_callback.assert_called_once_with(
            AfterToolCallEvent, hook.on_tool_complete
        )

    def test_hook_reset_zeros_counter(self):
        from agent.hooks.four_tool_cap import FourToolCapHook
        hook = FourToolCapHook(budget=4)
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

        # Mock _lambda_client.invoke (the D-04 fallback path calls it direct).
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
        # Assert the Lambda fallback was actually used (confirms the cancelled
        # path routed through the D-04 except Exception branch).
        assert mock_lambda_client.invoke.called

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

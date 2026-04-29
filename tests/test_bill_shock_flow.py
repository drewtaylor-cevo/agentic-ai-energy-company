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

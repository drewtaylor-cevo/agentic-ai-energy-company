"""Unit tests for the expanded tool gallery (Task 8).

Tests cover:
  8.1 — Outage status per persona (Sarah=no outage, Elena=planned, Marcus=unplanned)
  8.2 — Concession lookup per persona (Marcus=none, Elena=eligible-not-applied, Sarah=active)
  8.3 — Solar ineligibility for CUST-004 (already has solar)
  8.4 — Payment plan for CUST-006 (hardship, $890 balance, various instalment counts)
  8.5 — Callback confirmation shape and deterministic ID
  8.6 — Summary formatters for all new tools
  8.7 — Action dispatcher routing for all new actions
  8.8 — ToolCapHook + StreamingTraceHook coexistence (covered by test_hook_coexistence.py)
"""
from __future__ import annotations

import importlib
from unittest.mock import MagicMock, patch

import pytest

# Import pure functions from lambda/handler.py using importlib (bi-mode safe)
_handler = importlib.import_module("lambda.handler")
check_outage_status_pure = _handler.check_outage_status_pure
decompose_bill_shock_pure = _handler.decompose_bill_shock_pure
lookup_concessions_pure = _handler.lookup_concessions_pure
estimate_solar_payback_pure = _handler.estimate_solar_payback_pure
propose_payment_plan_pure = _handler.propose_payment_plan_pure
schedule_callback_pure = _handler.schedule_callback_pure
handler = _handler.handler

from agent.reasoning.summaries import (
    summary_check_outage_status,
    summary_decompose_bill_shock,
    summary_estimate_solar_payback,
    summary_lookup_concessions,
    summary_propose_payment_plan,
    summary_schedule_callback,
)


# ---------------------------------------------------------------------------
# 8.1 — Outage Status Tests
# ---------------------------------------------------------------------------


class TestOutageStatus:
    """Outage status per persona suburb."""

    def test_sarah_suburb_no_outage(self) -> None:
        """Sarah (CUST-001) → Bondi → no outage."""
        result = check_outage_status_pure("Bondi")
        assert result["has_outage"] is False
        assert result["outage_type"] == "none"
        assert result["suburb"] == "Bondi"
        assert result["customers_affected"] == 0
        assert result["affected_postcodes"] == []
        assert result["estimated_restoration"] is None

    def test_elena_suburb_planned_outage(self) -> None:
        """Elena (CUST-003) → Marrickville → planned outage."""
        result = check_outage_status_pure("Marrickville")
        assert result["has_outage"] is True
        assert result["outage_type"] == "planned"
        assert result["customers_affected"] == 450
        assert result["suburb"] == "Marrickville"
        assert "2204" in result["affected_postcodes"]

    def test_marcus_suburb_unplanned_outage(self) -> None:
        """Marcus (CUST-002) → Parramatta → unplanned outage."""
        result = check_outage_status_pure("Parramatta")
        assert result["has_outage"] is True
        assert result["outage_type"] == "unplanned"
        assert result["customers_affected"] == 1200
        assert result["suburb"] == "Parramatta"


# ---------------------------------------------------------------------------
# 8.2 — Concession Lookup Tests
# ---------------------------------------------------------------------------


class TestConcessionLookup:
    """Concession lookup per persona."""

    def test_marcus_no_concessions(self) -> None:
        """Marcus (CUST-002) has no eligible concessions."""
        result = lookup_concessions_pure("CUST-002")
        assert result["customer_id"] == "CUST-002"
        assert result["eligible_concessions"] == []
        assert result["total_annual_value"] == 0.0

    def test_elena_eligible_not_applied(self) -> None:
        """Elena (CUST-003) has eligible concessions, none applied."""
        result = lookup_concessions_pure("CUST-003")
        assert result["customer_id"] == "CUST-003"
        assert len(result["eligible_concessions"]) > 0
        assert all(not c["applied"] for c in result["eligible_concessions"])
        assert result["total_annual_value"] > 0.0

    def test_sarah_active_concession(self) -> None:
        """Sarah (CUST-001) has at least one active (applied) concession."""
        result = lookup_concessions_pure("CUST-001")
        assert result["customer_id"] == "CUST-001"
        assert len(result["eligible_concessions"]) > 0
        assert any(c["applied"] for c in result["eligible_concessions"])
        assert result["total_annual_value"] > 0.0


# ---------------------------------------------------------------------------
# 8.3 — Solar Ineligibility Test
# ---------------------------------------------------------------------------


class TestSolarIneligibility:
    """Solar payback ineligibility for CUST-004 (already has solar)."""

    def test_cust_004_solar_ineligible(self) -> None:
        """CUST-004 already has solar — should be ineligible."""
        billing = [
            {"month": "2025-01", "usage_kwh": 300, "customer_id": "CUST-004", "plan_id": "STD"},
            {"month": "2025-02", "usage_kwh": 310, "customer_id": "CUST-004", "plan_id": "STD"},
        ]
        result = estimate_solar_payback_pure("CUST-004", billing)
        assert result["eligible"] is False
        assert "solar" in result["reason"].lower()
        assert result["customer_id"] == "CUST-004"


# ---------------------------------------------------------------------------
# 8.4 — Payment Plan Tests (CUST-006, hardship, $890 balance)
# ---------------------------------------------------------------------------


class TestPaymentPlan:
    """Payment plan for CUST-006 (hardship persona, $890 balance)."""

    def test_cust_006_payment_plan_3_instalments(self) -> None:
        """3 instalments: schedule sums to $890 exactly."""
        result = propose_payment_plan_pure("CUST-006", 3, 890.00)
        assert result["outstanding_balance"] == 890.00
        assert result["instalment_count"] == 3
        assert result["interest_free"] is True
        assert len(result["schedule"]) == 3
        assert sum(e["amount"] for e in result["schedule"]) == 890.00

    def test_cust_006_payment_plan_6_instalments(self) -> None:
        """6 instalments: schedule sums to $890 exactly."""
        result = propose_payment_plan_pure("CUST-006", 6, 890.00)
        assert result["instalment_count"] == 6
        assert len(result["schedule"]) == 6
        assert sum(e["amount"] for e in result["schedule"]) == 890.00
        assert result["interest_free"] is True

    def test_cust_006_payment_plan_12_instalments(self) -> None:
        """12 instalments: schedule sums to $890 exactly."""
        result = propose_payment_plan_pure("CUST-006", 12, 890.00)
        assert result["instalment_count"] == 12
        assert len(result["schedule"]) == 12
        assert sum(e["amount"] for e in result["schedule"]) == 890.00
        assert result["interest_free"] is True


# ---------------------------------------------------------------------------
# 8.5 — Callback Confirmation Shape and Deterministic ID
# ---------------------------------------------------------------------------


class TestCallbackScheduling:
    """Callback confirmation shape and deterministic ID."""

    def test_callback_confirmation_shape(self) -> None:
        """Callback returns all required fields with correct values."""
        result = schedule_callback_pure("CUST-001", "2025-07-20T10:00:00+10:00", "billing query")
        assert result["customer_id"] == "CUST-001"
        assert result["scheduled_time"] == "2025-07-20T10:00:00+10:00"
        assert result["reason"] == "billing query"
        assert result["status"] == "confirmed"
        assert "callback_id" in result
        # callback_id should be a valid UUID string
        assert len(result["callback_id"]) == 36  # UUID format: 8-4-4-4-12

    def test_callback_deterministic_id(self) -> None:
        """Same inputs produce the same callback_id (UUID5 determinism)."""
        r1 = schedule_callback_pure("CUST-001", "2025-07-20T10:00:00+10:00", "billing query")
        r2 = schedule_callback_pure("CUST-001", "2025-07-20T10:00:00+10:00", "billing query")
        assert r1["callback_id"] == r2["callback_id"]

    def test_callback_different_inputs_different_id(self) -> None:
        """Different inputs produce different callback_ids."""
        r1 = schedule_callback_pure("CUST-001", "2025-07-20T10:00:00+10:00", "billing query")
        r2 = schedule_callback_pure("CUST-001", "2025-07-20T11:00:00+10:00", "billing query")
        assert r1["callback_id"] != r2["callback_id"]


# ---------------------------------------------------------------------------
# 8.6 — Summary Formatter Tests
# ---------------------------------------------------------------------------


class TestSummaryFormatters:
    """Summary formatters produce output containing key data points."""

    def test_summary_check_outage_status_with_outage(self) -> None:
        """Outage summary contains suburb name and outage type."""
        result = {
            "suburb": "Marrickville",
            "has_outage": True,
            "outage_type": "planned",
            "affected_postcodes": ["2204"],
            "estimated_restoration": "2025-07-15T14:00:00+10:00",
            "customers_affected": 450,
        }
        summary = summary_check_outage_status(result)
        assert "Marrickville" in summary
        assert "Planned" in summary or "planned" in summary.lower()
        assert "450" in summary

    def test_summary_check_outage_status_no_outage(self) -> None:
        """No-outage summary contains suburb name."""
        result = {
            "suburb": "Bondi",
            "has_outage": False,
            "outage_type": "none",
            "affected_postcodes": [],
            "estimated_restoration": None,
            "customers_affected": 0,
        }
        summary = summary_check_outage_status(result)
        assert "Bondi" in summary
        assert "No outage" in summary or "no outage" in summary.lower()

    def test_summary_decompose_bill_shock_with_shock(self) -> None:
        """Bill shock summary contains dollar amount and month."""
        result = {
            "is_shock": True,
            "total_delta_dollars": 45.20,
            "shock_month": "2025-10",
            "rate_change_component": 12.00,
            "usage_change_component": 28.00,
            "seasonal_component": 5.20,
            "explanation_sentence": "$45.20 over baseline — 27% from rate increase, 62% from usage spike, 12% from seasonal variation",
        }
        summary = summary_decompose_bill_shock(result)
        assert "45.20" in summary
        assert "2025-10" in summary
        # With explanation_sentence, the summary uses it directly
        assert "over baseline" in summary

    def test_summary_decompose_bill_shock_with_shock_legacy(self) -> None:
        """Bill shock summary falls back to legacy format without explanation_sentence."""
        result = {
            "is_shock": True,
            "total_delta_dollars": 45.20,
            "shock_month": "2025-10",
            "rate_change_component": 12.00,
            "usage_change_component": 28.00,
            "seasonal_component": 5.20,
        }
        summary = summary_decompose_bill_shock(result)
        assert "45.20" in summary
        assert "2025-10" in summary
        assert "12.00" in summary
        assert "28.00" in summary

    def test_summary_decompose_bill_shock_no_shock(self) -> None:
        """No-shock summary indicates no bill shock."""
        result = {"is_shock": False}
        summary = summary_decompose_bill_shock(result)
        assert "No bill shock" in summary or "no bill shock" in summary.lower()

    def test_summary_lookup_concessions(self) -> None:
        """Concession summary contains count and annual value."""
        result = {
            "eligible_concessions": [
                {"name": "NSW Energy Rebate", "annual_value": 285.00, "applied": True},
                {"name": "Low Income Rebate", "annual_value": 315.00, "applied": False},
            ],
            "total_annual_value": 600.00,
        }
        summary = summary_lookup_concessions(result)
        assert "2" in summary  # count
        assert "600.00" in summary  # annual value
        assert "1 not yet applied" in summary

    def test_summary_estimate_solar_payback_eligible(self) -> None:
        """Solar summary contains system size and payback years."""
        result = {
            "eligible": True,
            "estimated_system_size_kw": 6.5,
            "annual_savings_dollars": 1200.00,
            "payback_years": 5.2,
            "recommendation": "moderate_candidate",
        }
        summary = summary_estimate_solar_payback(result)
        assert "6.5" in summary
        assert "5.2" in summary
        assert "moderate_candidate" in summary

    def test_summary_estimate_solar_payback_ineligible(self) -> None:
        """Ineligible solar summary contains reason."""
        result = {
            "eligible": False,
            "reason": "Customer already has solar installed",
        }
        summary = summary_estimate_solar_payback(result)
        assert "ineligible" in summary.lower()

    def test_summary_propose_payment_plan(self) -> None:
        """Payment plan summary contains balance and instalment count."""
        result = {
            "outstanding_balance": 890.00,
            "instalment_count": 6,
            "instalment_amount": 148.33,
            "interest_free": True,
        }
        summary = summary_propose_payment_plan(result)
        assert "890.00" in summary
        assert "6" in summary
        assert "interest-free" in summary

    def test_summary_schedule_callback(self) -> None:
        """Callback summary contains scheduled time and reason."""
        result = {
            "scheduled_time": "2025-07-20T10:00:00+10:00",
            "reason": "billing query",
        }
        summary = summary_schedule_callback(result)
        assert "2025-07-20T10:00" in summary
        assert "billing query" in summary


# ---------------------------------------------------------------------------
# 8.7 — Action Dispatcher Routing Tests
# ---------------------------------------------------------------------------


class TestActionDispatcherRouting:
    """Lambda handler routes each new action correctly."""

    def test_check_outage_status_route(self) -> None:
        """check_outage_status action routes to check_outage_status_pure."""
        event = {"action": "check_outage_status", "suburb": "Bondi"}
        result = handler(event, None)
        assert result["suburb"] == "Bondi"
        assert result["has_outage"] is False

    def test_lookup_concessions_route(self) -> None:
        """lookup_concessions action routes to lookup_concessions_pure."""
        event = {"action": "lookup_concessions", "customer_id": "CUST-001"}
        result = handler(event, None)
        assert result["customer_id"] == "CUST-001"
        assert "eligible_concessions" in result

    def test_schedule_callback_route(self) -> None:
        """schedule_callback action routes to schedule_callback_pure."""
        event = {
            "action": "schedule_callback",
            "customer_id": "CUST-001",
            "when": "2025-07-20T10:00:00+10:00",
            "reason": "billing query",
        }
        result = handler(event, None)
        assert result["status"] == "confirmed"
        assert result["customer_id"] == "CUST-001"

    def test_propose_payment_plan_route(self) -> None:
        """propose_payment_plan action routes to propose_payment_plan_pure.

        Note: The dispatcher reads outstanding_balance from BALANCE_DATA for the customer.
        CUST-006 has $890 balance in seed data.
        """
        event = {
            "action": "propose_payment_plan",
            "customer_id": "CUST-006",
            "instalments": 3,
        }
        result = handler(event, None)
        assert result["customer_id"] == "CUST-006"
        assert result["outstanding_balance"] == 890.00
        assert result["instalment_count"] == 3

    def test_check_outage_status_invalid_suburb_returns_error(self) -> None:
        """Invalid suburb (empty string) returns error response."""
        event = {"action": "check_outage_status", "suburb": ""}
        result = handler(event, None)
        assert result["error"] is True
        assert "message" in result

    def test_lookup_concessions_invalid_customer_returns_error(self) -> None:
        """Invalid customer_id returns error response."""
        event = {"action": "lookup_concessions", "customer_id": "INVALID"}
        result = handler(event, None)
        assert result["error"] is True
        assert "message" in result

    def test_schedule_callback_invalid_datetime_returns_error(self) -> None:
        """Invalid datetime returns error response."""
        event = {
            "action": "schedule_callback",
            "customer_id": "CUST-001",
            "when": "not-a-date",
            "reason": "test",
        }
        result = handler(event, None)
        assert result["error"] is True
        assert "message" in result

    def test_detect_bill_shock_backward_compat_alias(self) -> None:
        """detect_bill_shock action is aliased to decompose_bill_shock handler.

        This route requires DynamoDB (TABLE_NAME) for billing history retrieval.
        We verify the route exists by confirming it raises RuntimeError about
        missing table (i.e., it passed customer_id validation and reached the
        DynamoDB check — proving the route is wired correctly).
        """
        event = {"action": "detect_bill_shock", "customer_id": "CUST-001"}
        with pytest.raises(RuntimeError, match="TABLE_NAME"):
            handler(event, None)


# ---------------------------------------------------------------------------
# 8.8 — Integration Test: ToolCapHook + StreamingTraceHook Coexistence
# ---------------------------------------------------------------------------


class TestHookCoexistence:
    """ToolCapHook + StreamingTraceHook coexistence.

    NOTE: tests/test_hook_coexistence.py already provides comprehensive coverage
    of this requirement (Requirement 7.4). This class verifies the existing tests
    pass and adds a minimal smoke test for completeness.
    """

    def test_both_hooks_instantiate_independently(self) -> None:
        """Both hooks can be instantiated without conflict."""
        from agent.hooks.four_tool_cap import FourToolCapHook
        from agent.hooks.streaming_trace import StreamingTraceHook

        cap_hook = FourToolCapHook(budget=8)
        trace_hook = StreamingTraceHook()

        assert cap_hook.budget == 8
        assert cap_hook.used == 0
        assert trace_hook._callback is None

    def test_both_hooks_register_and_fire(self) -> None:
        """Both hooks register on same registry and both fire on event."""
        from strands.hooks import AfterToolCallEvent, HookRegistry

        from agent.hooks.four_tool_cap import FourToolCapHook
        from agent.hooks.streaming_trace import StreamingTraceHook

        registry = HookRegistry()
        cap_hook = FourToolCapHook(budget=8)
        trace_hook = StreamingTraceHook()

        captured = []
        trace_hook.set_callback(lambda name, summary: captured.append((name, summary)))

        cap_hook.register_hooks(registry)
        trace_hook.register_hooks(registry)

        # Fire a known tool event
        event = MagicMock(spec=[])
        event.tool_name = "simulate_savings"
        event.tool_result = {
            "green": {"saving_monthly": 14.0},
            "cheapest": {"saving_monthly": 25.67},
        }
        event.agent = MagicMock()
        event.__class__ = AfterToolCallEvent

        callbacks = list(registry._registered_callbacks.get(AfterToolCallEvent, []))
        for cb in callbacks:
            cb(event)

        # Both hooks fired
        assert cap_hook.used == 1
        assert len(captured) == 1
        assert captured[0][0] == "simulate_savings"

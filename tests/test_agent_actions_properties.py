"""Property-based tests for Agent Action Preparation (Agentic Actions Portfolio).

Feature: agentic-actions-portfolio

Uses Hypothesis for property-based testing with minimum 100 iterations per
property. Each test is tagged with the feature and property reference from
the design document.

Properties tested:
  - Property 4: Action Payload SAV-03 Compliance
  - Property 5: SMS Body Validation
  - Property 6: Payment Plan Offer Conditional
"""
from __future__ import annotations

import importlib
import uuid
from typing import Any, Dict
from unittest.mock import patch, MagicMock

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from agent.agent import (
    ConfirmableAction,
    _validate_sms_body,
    _get_sms_fallback,
    prepare_actions,
)
from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX

# Import simulate_savings_pure and propose_payment_plan_pure for SAV-03 verification
_handler = importlib.import_module("lambda.handler")
simulate_savings_pure = _handler.simulate_savings_pure
propose_payment_plan_pure = _handler.propose_payment_plan_pure


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Valid customer IDs (matching seed data personas)
_seed_customer_ids = st.sampled_from(["CUST-001", "CUST-002", "CUST-003"])

# Valid customer IDs (broader range for property tests)
_valid_customer_id = st.from_regex(r"CUST-\d{3,6}", fullmatch=True)

# Savings output shape (mirrors simulate_savings_pure output)
_saving_monthly = st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False)
_saving_annual = st.floats(min_value=0.12, max_value=6000.0, allow_nan=False, allow_infinity=False)

_plan_ids = st.sampled_from(["ECO", "VAL", "SOL", "EV-TOU", "STD"])
_plan_names = st.sampled_from([
    "EcoFlex 100", "Value 12", "Solar Feed-in", "EV Drive TOU", "Standard"
])

_savings_track = st.fixed_dictionaries({
    "plan_id": _plan_ids,
    "plan_name": _plan_names,
    "saving_monthly": _saving_monthly,
    "saving_annual": _saving_annual,
})

_savings_output = st.fixed_dictionaries({
    "green": _savings_track,
    "cheapest": _savings_track,
})

# Bill shock result shape
_bill_shock_result = st.fixed_dictionaries({
    "is_shock": st.booleans(),
    "total_delta_dollars": st.floats(min_value=-100.0, max_value=200.0, allow_nan=False, allow_infinity=False),
    "shock_month": st.sampled_from(["2025-01", "2025-06", "2025-10"]),
    "mean_dollars": st.floats(min_value=50.0, max_value=300.0, allow_nan=False, allow_infinity=False),
    "current_dollars": st.floats(min_value=50.0, max_value=500.0, allow_nan=False, allow_infinity=False),
})

# SMS body strategies
_clean_sms_words = st.sampled_from([
    "Thank", "you", "for", "speaking", "with", "us", "about", "your",
    "energy", "plan", "options", "Please", "contact", "us", "if",
    "would", "like", "to", "proceed", "household", "profile",
    "winter", "summer", "usage", "pattern", "gentle", "steady",
    "mid-range", "home", "apartment", "family", "cooling", "heating",
])

# Generate clean SMS bodies (no digits, no banned terms, ≤160 chars)
_clean_sms_body = st.lists(
    _clean_sms_words, min_size=3, max_size=20
).map(lambda words: " ".join(words)[:160])

# Generate poisoned SMS bodies (contain digits or banned terms)
_poisoned_sms_body = st.one_of(
    st.just("Save $30 on your next bill"),
    st.just("Switch to EcoFlex today"),
    st.just("You could save 15% monthly"),
    st.just("Better than Origin Energy"),
    st.just("Moving to a cheaper plan saves money"),
    st.just("AGL customers often ask about this"),
    st.just("The greenest option available for you"),
    st.just("Transfer your account to save 20 dollars"),
)


# ---------------------------------------------------------------------------
# Property 4: Action Payload SAV-03 Compliance
# Feature: agentic-actions-portfolio, Property 4: Action Payload SAV-03 Compliance
# **Validates: Requirements 1.6, 3.2**
# ---------------------------------------------------------------------------


class TestActionPayloadSAV03Compliance:
    """Property 4: Action Payload SAV-03 Compliance.

    *For any* tariff_switch or payment_plan_offer Confirmable_Action produced
    by the agent, the numeric fields (estimated_saving_monthly, installment_amount,
    total_owed) SHALL exactly match the output of the corresponding Tools Lambda
    pure function.

    **Validates: Requirements 1.6, 3.2**
    """

    @settings(max_examples=100)
    @given(savings=_savings_output)
    def test_tariff_switch_numeric_fields_match_savings(self, savings):
        """tariff_switch payload numeric fields match simulate_savings output exactly."""
        # Feature: agentic-actions-portfolio, Property 4: Action Payload SAV-03 Compliance
        # **Validates: Requirements 1.6, 3.2**
        customer_id = "CUST-001"

        actions = prepare_actions(customer_id, savings)

        # Find the tariff_switch action
        tariff_actions = [a for a in actions if a["action_type"] == "tariff_switch"]
        assert len(tariff_actions) == 1, "Exactly one tariff_switch action expected"

        tariff_action = tariff_actions[0]
        payload = tariff_action["payload"]

        # SAV-03: numeric fields must exactly match the savings engine output
        assert payload["estimated_saving_monthly"] == savings["green"]["saving_monthly"], (
            f"estimated_saving_monthly={payload['estimated_saving_monthly']} "
            f"!= savings green saving_monthly={savings['green']['saving_monthly']}"
        )
        assert payload["plan_id"] == savings["green"]["plan_id"]
        assert payload["plan_name"] == savings["green"]["plan_name"]

    @settings(max_examples=100)
    @given(
        delta=st.floats(min_value=50.01, max_value=200.0, allow_nan=False, allow_infinity=False),
    )
    def test_payment_plan_numeric_fields_match_pure_function(self, delta):
        """payment_plan_offer payload numeric fields match propose_payment_plan_pure output."""
        # Feature: agentic-actions-portfolio, Property 4: Action Payload SAV-03 Compliance
        # **Validates: Requirements 1.6, 3.2**
        customer_id = "CUST-003"  # Elena — has bill shock in seed data

        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 14.0, "saving_annual": 168.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 25.67, "saving_annual": 308.04},
        }

        bill_shock = {
            "is_shock": True,
            "total_delta_dollars": delta,
            "shock_month": "2025-10",
            "mean_dollars": 100.0,
            "current_dollars": 100.0 + delta,
        }

        # Get the expected output from the pure function
        from infrastructure.seed_data.tool_seed_data import BALANCE_DATA
        outstanding = BALANCE_DATA.get(customer_id, delta)
        expected_pp = propose_payment_plan_pure(customer_id, 6, outstanding)

        actions = prepare_actions(customer_id, savings, bill_shock)

        # Find the payment_plan_offer action
        pp_actions = [a for a in actions if a["action_type"] == "payment_plan_offer"]
        assert len(pp_actions) == 1, (
            f"Expected 1 payment_plan_offer action, got {len(pp_actions)}"
        )

        pp_payload = pp_actions[0]["payload"]

        # SAV-03: numeric fields must exactly match propose_payment_plan_pure output
        assert pp_payload["installment_amount"] == expected_pp["instalment_amount"], (
            f"installment_amount={pp_payload['installment_amount']} "
            f"!= expected={expected_pp['instalment_amount']}"
        )
        assert pp_payload["total_owed"] == expected_pp["outstanding_balance"], (
            f"total_owed={pp_payload['total_owed']} "
            f"!= expected={expected_pp['outstanding_balance']}"
        )
        assert pp_payload["proposed_installments"] == expected_pp["instalment_count"]


# ---------------------------------------------------------------------------
# Property 5: SMS Body Validation
# Feature: agentic-actions-portfolio, Property 5: SMS Body Validation
# **Validates: Requirements 2.1, 2.2**
# ---------------------------------------------------------------------------


class TestSMSBodyValidation:
    """Property 5: SMS Body Validation.

    *For any* send_sms Confirmable_Action produced by the agent, the
    message_body field SHALL have length ≤ 160 characters AND SHALL pass
    D-15 validation (no digits, currency symbols, percentages, competitor
    names, or switch verbs).

    **Validates: Requirements 2.1, 2.2**
    """

    @settings(max_examples=100)
    @given(
        savings=_savings_output,
        sms_body=st.one_of(_clean_sms_body, _poisoned_sms_body, st.none()),
    )
    def test_sms_body_always_valid(self, savings, sms_body):
        """SMS body in produced action always passes D-15 and ≤160 chars."""
        # Feature: agentic-actions-portfolio, Property 5: SMS Body Validation
        # **Validates: Requirements 2.1, 2.2**
        customer_id = "CUST-001"

        actions = prepare_actions(customer_id, savings, sms_body=sms_body)

        # Find the send_sms action
        sms_actions = [a for a in actions if a["action_type"] == "send_sms"]
        assert len(sms_actions) == 1, "Exactly one send_sms action expected"

        sms_payload = sms_actions[0]["payload"]
        message_body = sms_payload["message_body"]

        # Property: message_body ≤ 160 characters
        assert len(message_body) <= 160, (
            f"SMS body length {len(message_body)} exceeds 160 chars"
        )

        # Property: message_body passes D-15 (no digits, currency, %, banned terms)
        assert not NUMERIC_REGEX.search(message_body), (
            f"SMS body contains forbidden digit/currency: {message_body!r}"
        )
        banned_match = BANNED_REGEX.search(message_body)
        assert banned_match is None, (
            f"SMS body contains banned term {banned_match.group()!r}: {message_body!r}"
        )

    @settings(max_examples=100)
    @given(sms_body=_poisoned_sms_body)
    def test_poisoned_sms_triggers_fallback(self, sms_body):
        """When LLM-generated SMS fails D-15, fallback is substituted."""
        # Feature: agentic-actions-portfolio, Property 5: SMS Body Validation
        # **Validates: Requirements 2.1, 2.2**
        customer_id = "CUST-001"
        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 30.0, "saving_annual": 360.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 55.0, "saving_annual": 660.0},
        }

        actions = prepare_actions(customer_id, savings, sms_body=sms_body)
        sms_actions = [a for a in actions if a["action_type"] == "send_sms"]
        assert len(sms_actions) == 1

        message_body = sms_actions[0]["payload"]["message_body"]

        # The poisoned body should NOT appear in the output
        assert message_body != sms_body, (
            f"Poisoned SMS body was not replaced by fallback: {sms_body!r}"
        )

        # The fallback must still pass D-15
        assert not NUMERIC_REGEX.search(message_body)
        assert BANNED_REGEX.search(message_body) is None
        assert len(message_body) <= 160

    @settings(max_examples=100)
    @given(sms_body=_clean_sms_body)
    def test_clean_sms_preserved(self, sms_body):
        """When LLM-generated SMS passes D-15, it is preserved."""
        # Feature: agentic-actions-portfolio, Property 5: SMS Body Validation
        # **Validates: Requirements 2.1, 2.2**
        assume(len(sms_body) <= 160)
        assume(not NUMERIC_REGEX.search(sms_body))
        assume(BANNED_REGEX.search(sms_body) is None)
        assume(len(sms_body.strip()) > 0)

        customer_id = "CUST-001"
        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 30.0, "saving_annual": 360.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 55.0, "saving_annual": 660.0},
        }

        actions = prepare_actions(customer_id, savings, sms_body=sms_body)
        sms_actions = [a for a in actions if a["action_type"] == "send_sms"]
        assert len(sms_actions) == 1

        message_body = sms_actions[0]["payload"]["message_body"]
        assert message_body == sms_body, (
            f"Clean SMS body was replaced: expected {sms_body!r}, got {message_body!r}"
        )


# ---------------------------------------------------------------------------
# Property 6: Payment Plan Offer Conditional
# Feature: agentic-actions-portfolio, Property 6: Payment Plan Offer Conditional
# **Validates: Requirements 3.1, 3.4**
# ---------------------------------------------------------------------------


class TestPaymentPlanOfferConditional:
    """Property 6: Payment Plan Offer Conditional.

    *For any* bill-shock decomposition result, a payment_plan_offer action
    SHALL be produced if and only if is_shock is true AND total_delta_dollars
    exceeds $50. When total_delta_dollars is $50 or less, no payment_plan_offer
    SHALL be produced.

    **Validates: Requirements 3.1, 3.4**
    """

    @settings(max_examples=100)
    @given(
        delta=st.floats(min_value=50.01, max_value=500.0, allow_nan=False, allow_infinity=False),
    )
    def test_offer_produced_when_shock_and_delta_over_50(self, delta):
        """payment_plan_offer produced when is_shock=true AND delta > $50."""
        # Feature: agentic-actions-portfolio, Property 6: Payment Plan Offer Conditional
        # **Validates: Requirements 3.1, 3.4**
        customer_id = "CUST-003"
        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 14.0, "saving_annual": 168.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 25.67, "saving_annual": 308.04},
        }
        bill_shock = {
            "is_shock": True,
            "total_delta_dollars": delta,
            "shock_month": "2025-10",
            "mean_dollars": 100.0,
            "current_dollars": 100.0 + delta,
        }

        actions = prepare_actions(customer_id, savings, bill_shock)
        pp_actions = [a for a in actions if a["action_type"] == "payment_plan_offer"]

        assert len(pp_actions) == 1, (
            f"Expected 1 payment_plan_offer when is_shock=True and delta={delta:.2f} > $50, "
            f"got {len(pp_actions)}"
        )

    @settings(max_examples=100)
    @given(
        delta=st.floats(min_value=-100.0, max_value=50.0, allow_nan=False, allow_infinity=False),
    )
    def test_no_offer_when_delta_50_or_less(self, delta):
        """No payment_plan_offer when delta ≤ $50 (even if is_shock=true)."""
        # Feature: agentic-actions-portfolio, Property 6: Payment Plan Offer Conditional
        # **Validates: Requirements 3.1, 3.4**
        customer_id = "CUST-003"
        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 14.0, "saving_annual": 168.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 25.67, "saving_annual": 308.04},
        }
        bill_shock = {
            "is_shock": True,
            "total_delta_dollars": delta,
            "shock_month": "2025-10",
            "mean_dollars": 100.0,
            "current_dollars": 100.0 + delta,
        }

        actions = prepare_actions(customer_id, savings, bill_shock)
        pp_actions = [a for a in actions if a["action_type"] == "payment_plan_offer"]

        assert len(pp_actions) == 0, (
            f"Expected 0 payment_plan_offer when delta={delta:.2f} ≤ $50, "
            f"got {len(pp_actions)}"
        )

    @settings(max_examples=100)
    @given(
        delta=st.floats(min_value=50.01, max_value=500.0, allow_nan=False, allow_infinity=False),
    )
    def test_no_offer_when_not_shock(self, delta):
        """No payment_plan_offer when is_shock=false (regardless of delta)."""
        # Feature: agentic-actions-portfolio, Property 6: Payment Plan Offer Conditional
        # **Validates: Requirements 3.1, 3.4**
        customer_id = "CUST-003"
        savings = {
            "green": {"plan_id": "ECO", "plan_name": "EcoFlex 100",
                      "saving_monthly": 14.0, "saving_annual": 168.0},
            "cheapest": {"plan_id": "VAL", "plan_name": "Value 12",
                         "saving_monthly": 25.67, "saving_annual": 308.04},
        }
        bill_shock = {
            "is_shock": False,
            "total_delta_dollars": delta,
            "shock_month": "2025-10",
            "mean_dollars": 100.0,
            "current_dollars": 100.0 + delta,
        }

        actions = prepare_actions(customer_id, savings, bill_shock)
        pp_actions = [a for a in actions if a["action_type"] == "payment_plan_offer"]

        assert len(pp_actions) == 0, (
            f"Expected 0 payment_plan_offer when is_shock=False, "
            f"got {len(pp_actions)}"
        )

    @settings(max_examples=100)
    @given(savings=_savings_output)
    def test_no_offer_when_no_bill_shock_result(self, savings):
        """No payment_plan_offer when bill_shock_result is None."""
        # Feature: agentic-actions-portfolio, Property 6: Payment Plan Offer Conditional
        # **Validates: Requirements 3.1, 3.4**
        customer_id = "CUST-001"

        actions = prepare_actions(customer_id, savings, bill_shock_result=None)
        pp_actions = [a for a in actions if a["action_type"] == "payment_plan_offer"]

        assert len(pp_actions) == 0, (
            f"Expected 0 payment_plan_offer when bill_shock_result=None, "
            f"got {len(pp_actions)}"
        )

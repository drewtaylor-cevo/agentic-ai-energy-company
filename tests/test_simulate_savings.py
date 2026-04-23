"""Tests for simulate_savings_pure — DEMO-02 + SAV-03 proof.

All numeric assertions are anchored to the verified rates in
lambda/tariff_plans.json and usage values in infrastructure/seed_data/billing_records.py.

Note: `from lambda.handler import ...` raises SyntaxError (lambda is a Python keyword).
Uses importlib fallback as documented in 01-02-PLAN.md.
"""
import importlib
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
simulate_savings_pure = handler.simulate_savings_pure


# --- Flagship persona (Sarah Chen) — DEMO-02 hard targets ---

def test_flagship_persona_green_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01


def test_flagship_persona_cheapest_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["cheapest"]["saving_monthly"] - 55.00) < 0.01


def test_flagship_persona_annual_savings(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_annual"] - round(result["green"]["saving_monthly"] * 12, 2)) < 0.01
    assert abs(result["cheapest"]["saving_annual"] - round(result["cheapest"]["saving_monthly"] * 12, 2)) < 0.01


def test_green_plan_is_eco(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert result["green"]["plan_id"] == "ECO"


def test_cheapest_plan_is_val(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert result["cheapest"]["plan_id"] == "VAL"


def test_green_cheapest_diverge(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert result["green"]["plan_id"] != result["cheapest"]["plan_id"]


def test_result_shape(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert set(result.keys()) == {"green", "cheapest"}
    for track in ("green", "cheapest"):
        assert set(result[track].keys()) == {
            "plan_id", "plan_name", "saving_monthly", "saving_annual"
        }


# --- Cross-persona invariants ---

def test_cheapest_always_gte_green(sarah_billing, marcus_billing, elena_billing, tariff_plans):
    for billing in (sarah_billing, marcus_billing, elena_billing):
        result = simulate_savings_pure(billing, tariff_plans)
        assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"], \
            f"Invariant violated for {billing[0]['customer_id']}"


def test_tou_never_selected(sarah_billing, marcus_billing, elena_billing, tariff_plans):
    for billing in (sarah_billing, marcus_billing, elena_billing):
        result = simulate_savings_pure(billing, tariff_plans)
        assert result["green"]["plan_id"] != "TOU"
        assert result["cheapest"]["plan_id"] != "TOU"


def test_marcus_savings_approximate(marcus_billing, tariff_plans):
    result = simulate_savings_pure(marcus_billing, tariff_plans)
    # Marcus avg ~281.67 kWh -> Green ~$16.90, Cheapest ~$30.98
    assert abs(result["green"]["saving_monthly"] - 16.92) < 0.10
    assert abs(result["cheapest"]["saving_monthly"] - 31.02) < 0.10


def test_elena_savings_approximate(elena_billing, tariff_plans):
    result = simulate_savings_pure(elena_billing, tariff_plans)
    # Elena avg ~233.33 kWh -> Green ~$13.98, Cheapest ~$25.63
    assert abs(result["green"]["saving_monthly"] - 13.98) < 0.10
    assert abs(result["cheapest"]["saving_monthly"] - 25.63) < 0.10

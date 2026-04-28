# tests/test_tariff_plans_byte_equal.py — M1 mitigation (Phase 11-01 per D-15)
import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LAMBDA_PATH = os.path.join(_REPO_ROOT, "lambda", "tariff_plans.json")
_SEED_PATH = os.path.join(_REPO_ROOT, "infrastructure", "seed_data", "tariff_plans.json")


def test_tariff_plans_byte_equal():
    """M1 mitigation: tariff_plans.json must be byte-equal between lambda/ and seed_data/."""
    with open(_LAMBDA_PATH, "rb") as f:
        lambda_bytes = f.read()
    with open(_SEED_PATH, "rb") as f:
        seed_bytes = f.read()
    assert lambda_bytes == seed_bytes, "tariff_plans.json drift — edit both in same commit"


def test_tariff_plans_structural_equal():
    """Defensive: also assert JSON parse-equal in case whitespace drifts."""
    with open(_LAMBDA_PATH) as f:
        lambda_plans = json.load(f)
    with open(_SEED_PATH) as f:
        seed_plans = json.load(f)
    assert lambda_plans == seed_plans


def test_catalog_has_6_plans():
    """Phase 11: catalog must contain STD, ECO, VAL, TOU, SOL, EV-TOU."""
    with open(_LAMBDA_PATH) as f:
        plans = json.load(f)
    plan_ids = {p["plan_id"] for p in plans}
    assert plan_ids == {"STD", "ECO", "VAL", "TOU", "SOL", "EV-TOU"}

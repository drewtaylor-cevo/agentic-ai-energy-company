"""Live HTTP smoke tests for Phase 3 Backend API — requires deployed stack.

Skipped unless BACKEND_API_URL env var is set to the deployed API endpoint.
Tests all 3 demo personas, error cases (400/404), and session isolation.
"""
import os

import pytest
import requests

BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BACKEND_API_URL,
        reason="BACKEND_API_URL not set — skip live backend API smoke tests",
    ),
]


# --- SC-1: All personas return recommendations ---


@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_all_personas_return_recommendations(customer_id):
    """SC-1: GET /recommendations/{customer_id} returns 200 with green + cheapest."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{customer_id}", timeout=60
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    body = r.json()
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"
    # Verify track shape
    for track in ("green", "cheapest"):
        for key in ("plan_id", "plan_name", "saving_monthly", "saving_annual"):
            assert key in body[track], f"Missing {key} in {track} for {customer_id}"


# --- SC-2: Error cases handled gracefully ---


@pytest.mark.parametrize(
    "bad_id",
    ["NOTVALID", "cust-001", "CUST-1", "CUST-1234567", ""],
)
def test_invalid_format_returns_400(bad_id):
    """SC-2: malformed customer_id returns 400 with friendly error."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/{bad_id}", timeout=10
    )
    assert r.status_code == 400, f"Expected 400 for '{bad_id}', got {r.status_code}"
    body = r.json()
    assert "error" in body


def test_unknown_customer_returns_404():
    """SC-2: unknown customer returns 404 with friendly error."""
    r = requests.get(
        f"{BACKEND_API_URL}/recommendations/CUST-999999", timeout=60
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"
    body = r.json()
    assert "error" in body


# --- SC-3: Fresh session ID — no recommendation bleed ---


def test_fresh_session_no_bleed():
    """SC-3: consecutive calls for different customers return different savings."""
    r1 = requests.get(
        f"{BACKEND_API_URL}/recommendations/CUST-001", timeout=60
    )
    r2 = requests.get(
        f"{BACKEND_API_URL}/recommendations/CUST-002", timeout=60
    )
    assert r1.status_code == 200 and r2.status_code == 200
    # Different customers have different saving amounts — confirms no bleed
    b1, b2 = r1.json(), r2.json()
    assert (
        b1["green"]["saving_monthly"] != b2["green"]["saving_monthly"]
    ), "CUST-001 and CUST-002 should have different green savings"

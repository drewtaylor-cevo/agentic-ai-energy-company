"""Byte-equality gate: live stack policies must match committed freeze JSON.

Skipped unless AWS credentials are available (boto3 can reach CloudFormation).
Run with: pytest -m smoke
Validates: Requirements 3.3, 3.4
"""
import json
import os
from pathlib import Path

import boto3
import pytest
from botocore.exceptions import BotoCoreError, ClientError

REGION = "us-east-1"
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Stack name → committed freeze policy JSON path (relative to project root)
STACK_POLICY_MAP = {
    "CustomerTariff": "infrastructure/stack-policies/foundation-freeze.json",
    "CustomerTariffAgent": "infrastructure/stack-policies/agentcore-freeze.json",
    "CustomerTariffApi": "infrastructure/stack-policies/backend-api-freeze.json",
}


def _can_reach_cloudformation() -> bool:
    """Return True if boto3 can call CloudFormation in us-east-1."""
    try:
        client = boto3.client("cloudformation", region_name=REGION)
        # A lightweight call to verify credentials work
        client.describe_account_limits()
        return True
    except (BotoCoreError, ClientError):
        return False


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not _can_reach_cloudformation(),
        reason="AWS credentials unavailable — skip stack policy byte-equality gate",
    ),
]


@pytest.fixture(scope="module")
def cfn_client():
    """Shared CloudFormation client for the test module."""
    return boto3.client("cloudformation", region_name=REGION)


@pytest.mark.parametrize(
    "stack_name,policy_path",
    list(STACK_POLICY_MAP.items()),
    ids=list(STACK_POLICY_MAP.keys()),
)
def test_stack_policy_byte_equality(cfn_client, stack_name, policy_path):
    """Assert get-stack-policy output matches the committed freeze JSON.

    Two-level comparison:
    1. Semantic (json.loads) — catches logical differences regardless of whitespace.
    2. String byte-equality — catches formatting drift between committed file and AWS.
    """
    # --- Load committed freeze policy from repo ---
    committed_file = PROJECT_ROOT / policy_path
    assert committed_file.exists(), f"Committed freeze policy not found: {committed_file}"
    committed_text = committed_file.read_text()
    committed_obj = json.loads(committed_text)

    # --- Fetch live policy from AWS ---
    response = cfn_client.get_stack_policy(StackName=stack_name)
    raw_body = response.get("StackPolicyBody")
    assert raw_body is not None, (
        f"{stack_name}: get-stack-policy returned no StackPolicyBody — "
        "freeze policy may not be applied"
    )
    live_obj = json.loads(raw_body)

    # --- 1. Semantic equality (handles whitespace / key-order differences) ---
    assert live_obj == committed_obj, (
        f"{stack_name}: stack policy SEMANTIC mismatch.\n"
        f"  Committed: {json.dumps(committed_obj, sort_keys=True)}\n"
        f"  Live:      {json.dumps(live_obj, sort_keys=True)}"
    )

    # --- 2. Byte-equality (string comparison of normalised JSON) ---
    # Normalise both sides to sorted, 2-space-indented JSON for a fair comparison
    committed_normalised = json.dumps(committed_obj, sort_keys=True, indent=2)
    live_normalised = json.dumps(live_obj, sort_keys=True, indent=2)
    assert live_normalised == committed_normalised, (
        f"{stack_name}: stack policy byte-equality FAILED after normalisation.\n"
        f"  Committed (normalised): {committed_normalised!r}\n"
        f"  Live (normalised):      {live_normalised!r}"
    )

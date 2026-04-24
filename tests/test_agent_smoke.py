"""Live AgentCore smoke tests — requires deployed runtime + AWS credentials.

Run AFTER cdk deploy --all succeeds:
    AGENT_RUNTIME_ARN=arn:aws:bedrock-agentcore:... \
    AWS_DEFAULT_REGION=us-east-1 \
    pytest tests/test_agent_smoke.py -v

Tests are SKIPPED if AGENT_RUNTIME_ARN is not set, so they do not break
local CI for developers without a deployed agent.

Covers Phase 2 success criteria:
  SC-1: Both Green and Cheapest returned simultaneously, neither ranked
  SC-2: Monthly + annual savings present, computed by tool (not LLM)
  SC-3: Green = ECO (most efficient), Cheapest = VAL (lowest cost)
  SC-4: cheapest.saving_monthly >= green.saving_monthly for all personas
"""
import json
import os
import uuid

import pytest

AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not AGENT_RUNTIME_ARN,
        reason="AGENT_RUNTIME_ARN not set — skip live agent smoke tests",
    ),
]


@pytest.fixture(scope="module")
def agentcore_client():
    boto3 = pytest.importorskip("boto3")
    return boto3.client(
        "bedrock-agentcore",
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
    )


def _invoke_agent(client, customer_id: str) -> dict:
    """Call invoke_agent_runtime and return parsed JSON body."""
    response = client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId=str(uuid.uuid4()),
        payload=json.dumps({"customer_id": customer_id}).encode(),
    )
    return json.loads(response["response"].read())


# --- SC-1: Both tracks present for all personas ---

@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_both_tracks_present(agentcore_client, customer_id):
    """SC-1: invoke_agent_runtime returns both green and cheapest tracks."""
    body = _invoke_agent(agentcore_client, customer_id)
    assert "green" in body, f"Missing green track for {customer_id}"
    assert "cheapest" in body, f"Missing cheapest track for {customer_id}"


# --- SC-2: Savings fields present and positive ---

@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_savings_fields_present(agentcore_client, customer_id):
    """SC-2: Both tracks carry monthly and annual savings > 0."""
    body = _invoke_agent(agentcore_client, customer_id)
    for track in ("green", "cheapest"):
        assert body[track]["saving_monthly"] > 0, \
            f"{track} saving_monthly <= 0 for {customer_id}"
        assert body[track]["saving_annual"] > 0, \
            f"{track} saving_annual <= 0 for {customer_id}"


# --- SC-3: Correct plan selection ---

@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_correct_plan_selection(agentcore_client, customer_id):
    """SC-3: Green = ECO, Cheapest = VAL for all personas."""
    body = _invoke_agent(agentcore_client, customer_id)
    assert body["green"]["plan_id"] == "ECO", \
        f"Green plan should be ECO for {customer_id}, got {body['green']['plan_id']}"
    assert body["cheapest"]["plan_id"] == "VAL", \
        f"Cheapest plan should be VAL for {customer_id}, got {body['cheapest']['plan_id']}"


# --- SC-4: Cheapest >= Green invariant ---

@pytest.mark.parametrize("customer_id", ["CUST-001", "CUST-002", "CUST-003"])
def test_cheapest_gte_green(agentcore_client, customer_id):
    """SC-4: cheapest.saving_monthly >= green.saving_monthly."""
    body = _invoke_agent(agentcore_client, customer_id)
    assert body["cheapest"]["saving_monthly"] >= body["green"]["saving_monthly"], \
        f"Invariant violated for {customer_id}: cheapest={body['cheapest']['saving_monthly']}, green={body['green']['saving_monthly']}"


# --- DEMO-02: Flagship persona exact values ---

def test_sarah_flagship_values(agentcore_client):
    """DEMO-02: Sarah Chen (CUST-001) Green=$30, Cheapest=$55."""
    body = _invoke_agent(agentcore_client, "CUST-001")
    assert abs(body["green"]["saving_monthly"] - 30.00) < 0.50, \
        f"Sarah green saving expected ~$30, got {body['green']['saving_monthly']}"
    assert abs(body["cheapest"]["saving_monthly"] - 55.00) < 0.50, \
        f"Sarah cheapest saving expected ~$55, got {body['cheapest']['saving_monthly']}"

"""Post-deploy smoke test — requires live AWS credentials + deployed stack.

Run AFTER cdk deploy succeeds:
    AWS_DEFAULT_REGION=us-east-1 pytest tests/test_seeder_smoke.py -v

This test is SKIPPED if AWS credentials are not available, so it does not
break local CI for developers without AWS access.
"""
import os
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_DEFAULT_REGION")
    or os.environ.get("SKIP_AWS_SMOKE") == "1",
    reason="AWS credentials not configured or smoke explicitly skipped",
)


@pytest.fixture(scope="module")
def dynamodb_client():
    boto3 = pytest.importorskip("boto3")
    return boto3.client("dynamodb", region_name=os.environ["AWS_DEFAULT_REGION"])


@pytest.fixture(scope="module")
def lambda_client():
    boto3 = pytest.importorskip("boto3")
    return boto3.client("lambda", region_name=os.environ["AWS_DEFAULT_REGION"])


def test_table_exists(dynamodb_client):
    resp = dynamodb_client.describe_table(TableName="tariff-billing")
    assert resp["Table"]["TableStatus"] == "ACTIVE"


def test_table_has_36_items(dynamodb_client):
    resp = dynamodb_client.scan(TableName="tariff-billing", Select="COUNT")
    assert resp["Count"] == 36, f"Expected 36 seeded items, got {resp['Count']}"


def test_sarah_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-001"}},
    )
    assert len(resp["Items"]) == 12


def test_marcus_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-002"}},
    )
    assert len(resp["Items"]) == 12


def test_elena_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-003"}},
    )
    assert len(resp["Items"]) == 12


def test_lambda_invokes_sarah_savings_match_demo02(lambda_client):
    """DEMO-02 end-to-end: live Lambda returns $30 Green / $55 Cheapest for Sarah."""
    import json
    resp = lambda_client.invoke(
        FunctionName="tariff-tools",
        Payload=json.dumps({"customer_id": "CUST-001"}).encode("utf-8"),
    )
    body = json.loads(resp["Payload"].read().decode("utf-8"))
    assert "FunctionError" not in resp, f"Lambda errored: {body}"
    assert abs(body["green"]["saving_monthly"] - 30.00) < 0.01
    assert abs(body["cheapest"]["saving_monthly"] - 55.00) < 0.01
    assert body["green"]["plan_id"] == "ECO"
    assert body["cheapest"]["plan_id"] == "VAL"

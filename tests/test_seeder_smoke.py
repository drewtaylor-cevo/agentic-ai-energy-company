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


def test_table_has_73_items(dynamodb_client):
    """Phase 11 bumped seed count: 36 v2.0 rows + 36 new billing rows + 1 PROFILE row = 73."""
    resp = dynamodb_client.scan(TableName="tariff-billing", Select="COUNT")
    assert resp["Count"] == 73, f"Expected 73 seeded items, got {resp['Count']}"


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


# --- Phase 11: CUST-004/005/006 + PROFILE smoke assertions ---

def test_cust004_has_12_months(dynamodb_client):
    """CUST-004 solar persona: 12 month rows, no PROFILE row."""
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-004"}},
    )
    assert len(resp["Items"]) == 12


def test_cust005_has_12_months(dynamodb_client):
    """CUST-005 EV persona: 12 month rows, no PROFILE row."""
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-005"}},
    )
    assert len(resp["Items"]) == 12


def test_cust006_has_12_months_plus_profile(dynamodb_client):
    """CUST-006 hardship persona: 12 month rows + 1 PROFILE row = 13 items."""
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-006"}},
    )
    assert len(resp["Items"]) == 13


def test_cust006_profile_row_carries_hardship_flag(dynamodb_client):
    """DATA-06 live smoke: PROFILE row has hardship_flag as native BOOL true."""
    resp = dynamodb_client.get_item(
        TableName="tariff-billing",
        Key={"customer_id": {"S": "CUST-006"}, "month": {"S": "PROFILE"}},
    )
    assert "Item" in resp, "PROFILE row missing for CUST-006"
    assert resp["Item"]["hardship_flag"] == {"BOOL": True}, \
        f"hardship_flag wire format drift: {resp['Item']['hardship_flag']}"
    assert "usage_kwh" not in resp["Item"], "PROFILE row should not carry usage_kwh"
    assert "cost_usd" not in resp["Item"], "PROFILE row should not carry cost_usd"


def test_cust004_has_export_kwh_native_N_type(dynamodb_client):
    """DATA-04 live smoke: CUST-004 April row has export_kwh as DynamoDB N type."""
    resp = dynamodb_client.get_item(
        TableName="tariff-billing",
        Key={"customer_id": {"S": "CUST-004"}, "month": {"S": "2025-04"}},
    )
    assert "Item" in resp, "CUST-004 April row missing"
    assert resp["Item"]["export_kwh"] == {"N": "200"}, \
        f"export_kwh drift: {resp['Item'].get('export_kwh')}"
    assert resp["Item"]["net_kwh"] == {"N": "450"}, \
        f"net_kwh drift (usage 650 - export 200 = 450): {resp['Item'].get('net_kwh')}"


def test_cust005_has_peak_offpeak_native_N_type(dynamodb_client):
    """DATA-05 live smoke: CUST-005 April row has peak_kwh + offpeak_kwh as DynamoDB N type."""
    resp = dynamodb_client.get_item(
        TableName="tariff-billing",
        Key={"customer_id": {"S": "CUST-005"}, "month": {"S": "2025-04"}},
    )
    assert "Item" in resp, "CUST-005 April row missing"
    assert resp["Item"]["peak_kwh"] == {"N": "168"}
    assert resp["Item"]["offpeak_kwh"] == {"N": "392"}
    assert resp["Item"]["usage_kwh"] == {"N": "560"}


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

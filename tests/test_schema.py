"""Schema & invariant tests for seed data — DATA-02 + DATA-03 proof."""
import re
from infrastructure.seed_data.billing_records import (
    ALL_RECORDS,
    DYNAMO_RECORDS,
    SARAH_CHEN_RECORDS,
    MARCUS_WEBB_RECORDS,
    ELENA_VASQUEZ_RECORDS,
)

REQUIRED_FIELDS = {"customer_id", "month", "usage_kwh", "cost_usd", "plan_id"}
_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def test_all_records_have_required_fields():
    for record in ALL_RECORDS:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record {record.get('customer_id')} {record.get('month')} missing: {missing}"


def test_usage_kwh_is_numeric():
    # DATA-03: stored in kWh, numeric — not strings, not Decimals.
    for record in ALL_RECORDS:
        assert isinstance(record["usage_kwh"], int), (
            f"usage_kwh must be int for {record['customer_id']} {record['month']}; "
            f"got {type(record['usage_kwh']).__name__}"
        )
        assert record["usage_kwh"] > 0, "usage_kwh must be positive"


def test_three_customers_present():
    customer_ids = {r["customer_id"] for r in ALL_RECORDS}
    assert customer_ids == {"CUST-001", "CUST-002", "CUST-003"}


def test_twelve_months_per_customer():
    for cust_id in ("CUST-001", "CUST-002", "CUST-003"):
        count = sum(1 for r in ALL_RECORDS if r["customer_id"] == cust_id)
        assert count == 12, f"{cust_id} has {count} records, expected 12"


def test_months_are_yyyy_mm_format():
    for record in ALL_RECORDS:
        assert _MONTH_RE.match(record["month"]), (
            f"Month must be YYYY-MM; got {record['month']!r}"
        )


def test_months_are_unique_per_customer():
    seen = set()
    for record in ALL_RECORDS:
        key = (record["customer_id"], record["month"])
        assert key not in seen, f"Duplicate record for {key}"
        seen.add(key)


def test_dynamo_records_wire_format():
    for record in DYNAMO_RECORDS:
        # Strings wrapped in {"S": "..."}
        assert set(record["customer_id"].keys()) == {"S"}
        assert set(record["month"].keys()) == {"S"}
        assert set(record["plan_id"].keys()) == {"S"}
        # Numerics wrapped in {"N": "..."} — VALUE is a string (DynamoDB requirement)
        assert set(record["usage_kwh"].keys()) == {"N"}
        assert isinstance(record["usage_kwh"]["N"], str), \
            "DynamoDB wire format requires N values as stringified numbers"
        assert set(record["cost_usd"].keys()) == {"N"}
        assert isinstance(record["cost_usd"]["N"], str)


def test_dynamo_records_count_matches_all_records():
    assert len(DYNAMO_RECORDS) == len(ALL_RECORDS) == 36


def test_all_current_plan_is_std():
    # Narrative setup: all 3 personas are on the legacy Standard rate.
    for record in ALL_RECORDS:
        assert record["plan_id"] == "STD", (
            f"All seed records must start on STD for the demo narrative; "
            f"{record['customer_id']} {record['month']} is on {record['plan_id']}"
        )

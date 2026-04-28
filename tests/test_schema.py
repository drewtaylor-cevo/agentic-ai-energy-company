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

# Phase 11 (v3.0) expanded seed data to six personas plus a PROFILE sentinel row
# carrying hardship_flag for CUST-006. The PROFILE row intentionally uses a
# different shape (month="PROFILE", no billing fields) so schema tests targeting
# billing records filter it out.
_V2_PERSONAS = {"CUST-001", "CUST-002", "CUST-003"}
_ALL_PERSONAS = {"CUST-001", "CUST-002", "CUST-003", "CUST-004", "CUST-005", "CUST-006"}
BILLING_RECORDS = [r for r in ALL_RECORDS if r.get("month") != "PROFILE"]
PROFILE_RECORDS = [r for r in ALL_RECORDS if r.get("month") == "PROFILE"]


def test_all_billing_records_have_required_fields():
    for record in BILLING_RECORDS:
        missing = REQUIRED_FIELDS - set(record.keys())
        assert not missing, f"Record {record.get('customer_id')} {record.get('month')} missing: {missing}"


def test_usage_kwh_is_numeric():
    # DATA-03: stored in kWh, numeric — not strings, not Decimals.
    for record in BILLING_RECORDS:
        assert isinstance(record["usage_kwh"], int), (
            f"usage_kwh must be int for {record['customer_id']} {record['month']}; "
            f"got {type(record['usage_kwh']).__name__}"
        )
        assert record["usage_kwh"] > 0, "usage_kwh must be positive"


def test_six_customers_present():
    customer_ids = {r["customer_id"] for r in ALL_RECORDS}
    assert customer_ids == _ALL_PERSONAS


def test_twelve_months_per_customer():
    for cust_id in sorted(_ALL_PERSONAS):
        count = sum(1 for r in BILLING_RECORDS if r["customer_id"] == cust_id)
        assert count == 12, f"{cust_id} has {count} billing records, expected 12"


def test_months_are_yyyy_mm_format():
    for record in BILLING_RECORDS:
        assert _MONTH_RE.match(record["month"]), (
            f"Month must be YYYY-MM; got {record['month']!r}"
        )


def test_months_are_unique_per_customer():
    seen = set()
    for record in BILLING_RECORDS:
        key = (record["customer_id"], record["month"])
        assert key not in seen, f"Duplicate record for {key}"
        seen.add(key)


def test_dynamo_records_wire_format():
    # Only billing rows in DYNAMO_RECORDS carry plan_id/usage_kwh/cost_usd.
    # The PROFILE row uses a sentinel shape (month="PROFILE", hardship_flag BOOL)
    # and is validated separately in test_profile_dynamo_wire_format.
    billing_dynamo = [r for r in DYNAMO_RECORDS if r["month"]["S"] != "PROFILE"]
    for record in billing_dynamo:
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
    # Phase 11: 6 personas × 12 months = 72 billing rows + 1 PROFILE row = 73 total.
    assert len(DYNAMO_RECORDS) == len(ALL_RECORDS) == 73


def test_billing_record_count():
    # 6 personas × 12 months = 72 billing records (excludes PROFILE sentinel).
    assert len(BILLING_RECORDS) == 72


def test_v2_personas_on_std_plan():
    # Narrative setup: v2.0 personas (Sarah/Marcus/Elena) start on the legacy Standard rate.
    # New personas (Maya/Dmitri/Nkechi) start on SOL/EV-TOU/STD respectively per Phase 11 spec.
    for record in BILLING_RECORDS:
        if record["customer_id"] in _V2_PERSONAS:
            assert record["plan_id"] == "STD", (
                f"v2.0 personas must start on STD for the demo narrative; "
                f"{record['customer_id']} {record['month']} is on {record['plan_id']}"
            )


def test_profile_row_present_for_hardship_persona():
    # DATA-06: PROFILE sentinel-SK row carries hardship_flag for CUST-006.
    assert len(PROFILE_RECORDS) == 1
    profile = PROFILE_RECORDS[0]
    assert profile["customer_id"] == "CUST-006"
    assert profile["month"] == "PROFILE"
    assert profile.get("hardship_flag") is True

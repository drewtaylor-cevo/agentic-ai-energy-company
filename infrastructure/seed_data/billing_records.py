"""Engineered dummy billing data for the Customer Tariff demo.

Three personas, 12 months each = 36 DynamoDB records total.
Usage values are verified against the savings formula:
  - Sarah Chen (CUST-001): avg 500 kWh -> Green $30.00/mo, Cheapest $55.00/mo (DEMO-02 flagship)
  - Marcus Webb (CUST-002): avg 282 kWh -> Green $16.92/mo, Cheapest $31.02/mo
  - Elena Vasquez (CUST-003): avg 233 kWh -> Green $13.98/mo, Cheapest $25.63/mo

cost_usd is computed at definition time (not stored as a literal) so it stays
consistent with usage_kwh. Savings math in lambda/handler.py always reads
usage_kwh, never cost_usd (DATA-03 requirement).
"""
from typing import List, Dict, Any, Optional

# Supply charge and current-plan rate are uniform for all personas.
# These constants mirror tariff_plans.json STD entry and must not drift.
STD_RATE = 0.32
SUPPLY_CHARGE = 1.10
DAYS_PER_MONTH = 30.44


def _cost(usage_kwh: int) -> float:
    """Compute cost at STD plan rate. Used only to populate historical
    cost_usd values for realistic demo records. Savings logic never reads this."""
    return round(usage_kwh * STD_RATE + SUPPLY_CHARGE * DAYS_PER_MONTH, 2)


def _record(
    customer_id: str,
    month: str,
    usage_kwh: int,
    *,
    export_kwh: int = 0,
    peak_kwh: Optional[int] = None,
    offpeak_kwh: Optional[int] = None,
) -> Dict[str, Any]:
    """Build a billing record. v2.0 personas call with positional args; new personas use kwargs.

    For solar (CUST-004): export_kwh > 0; net_kwh computed as usage_kwh - export_kwh.
    For EV-TOU (CUST-005): peak_kwh + offpeak_kwh = usage_kwh.
    For v2.0 / CUST-006 (flat): export_kwh=0, peak_kwh=None, offpeak_kwh=None.
    """
    net_kwh = usage_kwh - export_kwh  # D-01 back-compat: v2.0 records → export_kwh=0 → net_kwh=usage_kwh

    record = {
        "customer_id": customer_id,
        "month": month,
        "usage_kwh": usage_kwh,
        # D-20: solar records use net_kwh in cost_usd (reflects STD baseline without FiT);
        # flat records (v2.0 + CUST-006) have export_kwh=0 so net_kwh=usage_kwh → same result.
        "cost_usd": _cost(net_kwh if export_kwh > 0 else usage_kwh),
        "plan_id": "STD",
    }
    if export_kwh > 0:
        record["export_kwh"] = export_kwh
        record["net_kwh"] = net_kwh
    if peak_kwh is not None:
        record["peak_kwh"] = peak_kwh
    if offpeak_kwh is not None:
        record["offpeak_kwh"] = offpeak_kwh
    return record


def _profile_item(customer_id: str, hardship_flag: bool = False) -> Dict[str, Any]:
    """D-08/D-09: PROFILE sentinel-SK row. Phase 11: only hardship_flag attribute."""
    return {
        "customer_id": customer_id,
        "month": "PROFILE",
        "hardship_flag": hardship_flag,
    }


# Month order follows the customer's fiscal year: Apr 2025 -> Mar 2026.
# Index 0 = April 2025, index 11 = March 2026.
_MONTHS = [
    "2025-04", "2025-05", "2025-06", "2025-07", "2025-08", "2025-09",
    "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
]


# Sarah Chen (CUST-001) — flagship persona, high-usage family household.
# Verified avg: (425+400+450+500+550+600+625+600+550+475+450+375)/12 = 500.0 kWh/month
_SARAH_USAGE = [425, 400, 450, 500, 550, 600, 625, 600, 550, 475, 450, 375]
SARAH_CHEN_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-001", m, u) for m, u in zip(_MONTHS, _SARAH_USAGE)
]

# Marcus Webb (CUST-002) — mid-usage apartment dweller.
# Verified avg: (250+235+265+280+300+320+340+325+305+275+255+230)/12 = 281.67 kWh/month (~282)
_MARCUS_USAGE = [250, 235, 265, 280, 300, 320, 340, 325, 305, 275, 255, 230]
MARCUS_WEBB_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-002", m, u) for m, u in zip(_MONTHS, _MARCUS_USAGE)
]

# Elena Vasquez (CUST-003) — seasonal-heavy, near-zero winter, summer peak.
# Verified avg: (110+95+130+160+290+380+420+395+310+230+155+125)/12 = 233.33 kWh/month (~233)
_ELENA_USAGE = [110, 95, 130, 160, 290, 380, 420, 395, 310, 230, 155, 125]
ELENA_VASQUEZ_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-003", m, u) for m, u in zip(_MONTHS, _ELENA_USAGE)
]


ALL_RECORDS: List[Dict[str, Any]] = (
    SARAH_CHEN_RECORDS + MARCUS_WEBB_RECORDS + ELENA_VASQUEZ_RECORDS
)


def to_dynamo(record: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Convert Python-native record to DynamoDB wire format.

    Phase 11: emits optional attributes (export_kwh, net_kwh, peak_kwh, offpeak_kwh) only when
    present; BOOL wire type for hardship_flag on PROFILE rows (Pattern 3).
    """
    out: Dict[str, Dict[str, Any]] = {
        "customer_id": {"S": record["customer_id"]},
        "month": {"S": record["month"]},
    }
    if "usage_kwh" in record:
        out["usage_kwh"] = {"N": str(record["usage_kwh"])}
    if "cost_usd" in record:
        out["cost_usd"] = {"N": str(record["cost_usd"])}
    if "plan_id" in record:
        out["plan_id"] = {"S": record["plan_id"]}
    if "export_kwh" in record:
        out["export_kwh"] = {"N": str(record["export_kwh"])}
    if "net_kwh" in record:
        out["net_kwh"] = {"N": str(record["net_kwh"])}
    if "peak_kwh" in record:
        out["peak_kwh"] = {"N": str(record["peak_kwh"])}
    if "offpeak_kwh" in record:
        out["offpeak_kwh"] = {"N": str(record["offpeak_kwh"])}
    if "hardship_flag" in record:
        out["hardship_flag"] = {"BOOL": bool(record["hardship_flag"])}
    return out


DYNAMO_RECORDS: List[Dict[str, Dict[str, str]]] = [to_dynamo(r) for r in ALL_RECORDS]


# Sanity assertions — fail at import time if anyone tampers with the arrays.
assert len(SARAH_CHEN_RECORDS) == 12, "Sarah must have 12 months"
assert len(MARCUS_WEBB_RECORDS) == 12, "Marcus must have 12 months"
assert len(ELENA_VASQUEZ_RECORDS) == 12, "Elena must have 12 months"
assert len(ALL_RECORDS) == 36, "ALL_RECORDS must contain exactly 36 items"
assert len(DYNAMO_RECORDS) == 36, "DYNAMO_RECORDS must contain exactly 36 items"
assert sum(_SARAH_USAGE) / 12 == 500.0, "Sarah avg must be exactly 500 kWh"

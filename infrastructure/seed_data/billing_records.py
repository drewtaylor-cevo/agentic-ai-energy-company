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


def _profile_item(
    customer_id: str,
    hardship_flag: bool = False,
    hardship_category: Optional[str] = None,
) -> Dict[str, Any]:
    """D-08/D-09: PROFILE sentinel-SK row. Phase 11: hardship_flag; AGENT-03: hardship_category."""
    item: Dict[str, Any] = {
        "customer_id": customer_id,
        "month": "PROFILE",
        "hardship_flag": hardship_flag,
    }
    if hardship_category is not None:
        item["hardship_category"] = hardship_category
    return item


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


# --- Phase 11 v3.0 personas (locked constants from scratch/target_equation_solver_v2.py) ---

# CUST-004 Solar PV (DATA-04) — net-metering shape; summer = low net + high export, winter = reverse.
# Verified: net_avg=667 kWh/mo (sum=8004), export_avg=200 kWh/mo (sum=2400).
# Locked byte-exact savings: Green ECO $40.02/mo, Cheapest SOL $76.03/mo (per Plan 05 fixtures).
_CUST004_USAGE_KWH = [650, 680, 780, 820, 840, 720, 620, 570, 540, 560, 600, 624]
_CUST004_EXPORT_KWH = [200, 180, 120, 100, 90, 160, 220, 260, 300, 290, 260, 220]
CUST004_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-004", m, u, export_kwh=e)
    for m, u, e in zip(_MONTHS, _CUST004_USAGE_KWH, _CUST004_EXPORT_KWH)
]

# CUST-005 EV TOU (DATA-05) — 30/70 peak/offpeak split; overnight-charging-heavy, mild winter skew.
# Verified: total_avg=583.33 kWh/mo (sum=7000), peak_sum=2100 (30%), offpeak_sum=4900 (70%).
# Locked byte-exact savings: Green ECO $35.00/mo, Cheapest EV-TOU $84.00/mo.
_CUST005_USAGE_KWH = [560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560]
_CUST005_PEAK_KWH = [168, 171, 183, 192, 198, 177, 168, 162, 171, 174, 168, 168]
_CUST005_OFFPEAK_KWH = [392, 399, 427, 448, 462, 413, 392, 378, 399, 406, 392, 392]
CUST005_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-005", m, u, peak_kwh=p, offpeak_kwh=o)
    for m, u, p, o in zip(_MONTHS, _CUST005_USAGE_KWH, _CUST005_PEAK_KWH, _CUST005_OFFPEAK_KWH)
]

# CUST-006 Hardship (DATA-06 / D-07) — low, stressed-looking shape; avg 200 kWh/mo (sum=2400).
# Phase 14 will short-circuit to hardship before the LLM sees this — but simulate_savings_pure
# still produces a valid recommendation (ECO Green $12.00, VAL Cheapest $22.00).
_CUST006_USAGE_KWH = [200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185]
CUST006_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-006", m, u) for m, u in zip(_MONTHS, _CUST006_USAGE_KWH)
]

# --- AGENT-03 Typed Hardship Personas (one per category) ---

# CUST-007 Payment Difficulty — low-usage household struggling with bills; avg ~300 kWh/mo.
_CUST007_USAGE_KWH = [280, 290, 310, 320, 330, 315, 300, 285, 275, 280, 295, 320]
CUST007_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-007", m, u) for m, u in zip(_MONTHS, _CUST007_USAGE_KWH)
]

# CUST-008 Medical Equipment — life-support equipment user, low baseline; avg ~350 kWh/mo.
_CUST008_USAGE_KWH = [330, 340, 355, 360, 370, 365, 350, 345, 335, 340, 355, 355]
CUST008_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-008", m, u) for m, u in zip(_MONTHS, _CUST008_USAGE_KWH)
]

# CUST-009 Family Violence — safety-first customer, minimal usage; avg ~220 kWh/mo.
_CUST009_USAGE_KWH = [200, 210, 225, 230, 240, 235, 220, 215, 205, 210, 220, 230]
CUST009_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-009", m, u) for m, u in zip(_MONTHS, _CUST009_USAGE_KWH)
]

# CUST-010 Other — generic hardship, low usage; avg ~260 kWh/mo.
_CUST010_USAGE_KWH = [240, 250, 265, 270, 280, 275, 260, 255, 245, 250, 260, 270]
CUST010_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-010", m, u) for m, u in zip(_MONTHS, _CUST010_USAGE_KWH)
]

# PROFILE items — CUST-006 (legacy, no category) + AGENT-03 typed hardship personas.
PROFILE_ITEMS: List[Dict[str, Any]] = [
    _profile_item("CUST-006", hardship_flag=True),
    _profile_item("CUST-007", hardship_flag=True, hardship_category="payment_difficulty"),
    _profile_item("CUST-008", hardship_flag=True, hardship_category="medical_equipment"),
    _profile_item("CUST-009", hardship_flag=True, hardship_category="family_violence"),
    _profile_item("CUST-010", hardship_flag=True, hardship_category="other"),
]


ALL_RECORDS: List[Dict[str, Any]] = (
    SARAH_CHEN_RECORDS
    + MARCUS_WEBB_RECORDS
    + ELENA_VASQUEZ_RECORDS
    + CUST004_RECORDS
    + CUST005_RECORDS
    + CUST006_RECORDS
    + CUST007_RECORDS
    + CUST008_RECORDS
    + CUST009_RECORDS
    + CUST010_RECORDS
    + PROFILE_ITEMS
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
    if "hardship_category" in record:
        out["hardship_category"] = {"S": record["hardship_category"]}
    return out


DYNAMO_RECORDS: List[Dict[str, Dict[str, str]]] = [to_dynamo(r) for r in ALL_RECORDS]


# --- Bottom-of-file invariant assertions (fail fast at Python import time) ---

# V2.0 persona invariants (unchanged from pre-Phase-11)
assert len(SARAH_CHEN_RECORDS) == 12, "Sarah must have 12 months"
assert len(MARCUS_WEBB_RECORDS) == 12, "Marcus must have 12 months"
assert len(ELENA_VASQUEZ_RECORDS) == 12, "Elena must have 12 months"
assert sum(_SARAH_USAGE) / 12 == 500.0, "Sarah avg must be exactly 500 kWh"

# Phase 11 v3.0 persona invariants (LOCKED per scratch/target_equation_solver_v2.py)
assert len(CUST004_RECORDS) == 12, "CUST-004 must have 12 months"
assert len(CUST005_RECORDS) == 12, "CUST-005 must have 12 months"
assert len(CUST006_RECORDS) == 12, "CUST-006 must have 12 months"
assert sum(_CUST004_USAGE_KWH) == 8004, "CUST-004 usage sum locked at 8004 (avg 667)"
assert sum(_CUST004_EXPORT_KWH) == 2400, "CUST-004 export sum locked at 2400 (avg 200)"
assert sum(_CUST005_USAGE_KWH) == 7000, "CUST-005 usage sum locked at 7000 (avg 583.33)"
assert sum(_CUST005_PEAK_KWH) == 2100, "CUST-005 peak sum locked at 2100 (30% of 7000)"
assert sum(_CUST005_OFFPEAK_KWH) == 4900, "CUST-005 offpeak sum locked at 4900 (70% of 7000)"
assert sum(_CUST006_USAGE_KWH) == 2400, "CUST-006 usage sum locked at 2400 (avg 200)"

# T-Integrity: solar records must never have export > usage (would produce negative net_kwh)
assert all(r["export_kwh"] <= r["usage_kwh"] for r in CUST004_RECORDS), \
    "CUST-004 export_kwh must never exceed usage_kwh (would yield negative net_kwh)"

# T-Integrity: EV-TOU peak + offpeak must equal usage_kwh (30/70 split engineered)
assert all(r["peak_kwh"] + r["offpeak_kwh"] == r["usage_kwh"] for r in CUST005_RECORDS), \
    "CUST-005 peak_kwh + offpeak_kwh must equal usage_kwh"

# PROFILE sentinel-SK invariants
assert len(PROFILE_ITEMS) == 5, "AGENT-03: 5 PROFILE items (CUST-006 + 4 typed hardship)"
assert PROFILE_ITEMS[0]["customer_id"] == "CUST-006"
assert PROFILE_ITEMS[0]["month"] == "PROFILE"
assert PROFILE_ITEMS[0]["hardship_flag"] is True

# AGENT-03 typed hardship PROFILE invariants
assert PROFILE_ITEMS[1]["hardship_category"] == "payment_difficulty"
assert PROFILE_ITEMS[2]["hardship_category"] == "medical_equipment"
assert PROFILE_ITEMS[3]["hardship_category"] == "family_violence"
assert PROFILE_ITEMS[4]["hardship_category"] == "other"

# AGENT-03 new persona record counts
assert len(CUST007_RECORDS) == 12, "CUST-007 must have 12 months"
assert len(CUST008_RECORDS) == 12, "CUST-008 must have 12 months"
assert len(CUST009_RECORDS) == 12, "CUST-009 must have 12 months"
assert len(CUST010_RECORDS) == 12, "CUST-010 must have 12 months"

# Aggregate counts: 36 v2.0 + 36 v3.0 billing + 48 AGENT-03 billing + 5 PROFILE = 125
assert len(ALL_RECORDS) == 125, f"ALL_RECORDS must contain exactly 125 items, got {len(ALL_RECORDS)}"
assert len(DYNAMO_RECORDS) == 125, f"DYNAMO_RECORDS must contain exactly 125 items, got {len(DYNAMO_RECORDS)}"

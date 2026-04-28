# Phase 11: New Personas + Tariff Archetypes - Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 10 (7 modify, 3 create)
**Analogs found:** 10 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `lambda/handler.py` (MODIFY — extend `simulate_savings_pure` + add `get_hardship_flag_pure` + patch `get_billing_history`) | backend pure-helper + Lambda handler | request-response / transform | self — current `simulate_savings_pure` @ lines 60-118 (extend in place) | exact (self-extension per D-12) |
| `lambda/tariff_plans.json` (MODIFY — add SOL + EV-TOU entries) | static config (catalog) | read-only reference | self — existing 4-plan entries @ lines 1-42 | exact |
| `infrastructure/seed_data/tariff_plans.json` (MODIFY — byte-equal copy) | static config (seeder-side duplicate) | read-only reference | self — existing 4-plan entries (byte-equal to `lambda/` copy) | exact |
| `infrastructure/seed_data/billing_records.py` (MODIFY — extend `_record()`, add `_profile_item()`, add CUST004/005/006 arrays) | seed-data module | batch (CDK-time import) | self — existing `_record()` @ lines 28-35, `to_dynamo()` @ 73-87, `SARAH_CHEN_RECORDS` @ 49-51 | exact (self-extension per D-16) |
| `tests/conftest.py` (MODIFY — add 4 fixtures) | test infrastructure | request-response (fixture) | self — existing `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` @ lines 46-100 | exact |
| `tests/test_simulate_savings.py` (MODIFY — extend with CUST-004/005/006 parametrisations) | unit test | test | self — existing Sarah/Marcus/Elena tests @ lines 17-86 | exact |
| `tests/test_seeder_smoke.py` (MODIFY — bump 36→73, add new persona + PROFILE assertions) | smoke test | test (live AWS) | self — existing `test_table_has_36_items` @ 36-38 + `test_sarah_has_12_months` @ 41-47 | exact |
| `tests/test_tariff_plans_byte_equal.py` (NEW — M1 mitigation) | unit test | test | `tests/conftest.py` tariff-plans loading pattern @ lines 7-10 | role-match |
| `tests/test_get_hardship_flag_pure.py` (NEW — DATA-06 coverage) | unit test | test | `tests/test_simulate_savings.py` (importlib pattern + fixture style) | role-match |
| `tests/test_get_billing_history.py` or extension (NEW test — D-21 filter gate) | unit test | test | `tests/test_simulate_savings.py` (importlib pattern) | role-match |

**Non-integration points (do NOT touch):** `agent/agent.py`, `api_lambda/handler.py`, `ui/**`, `infrastructure/agentcore_stack.py`, `infrastructure/backend_api_stack.py`, `infrastructure/frontend_stack.py`, `requirements*.txt`, `ui/package-lock.json`.

## Pattern Assignments

### `lambda/handler.py` — `simulate_savings_pure` dispatcher extension (D-12)

**Analog:** self — extend the existing closure in place (minimum-diff per C7 Chesterton's-Fence).

**Existing `projected_monthly_cost` closure** (`lambda/handler.py:86-90`):

```python
def projected_monthly_cost(plan: Dict[str, Any]) -> float:
    return (
        avg_kwh * float(plan["rate_per_kwh"])
        + float(plan["daily_supply_charge"]) * DAYS_PER_MONTH
    )
```

**Existing `avg_kwh` + `current_plan_id` computation (MUST NOT be reordered — SAV-03 byte-exactness depends on this exact expression)** (`lambda/handler.py:80-84`):

```python
avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)
current_plan_id = billing_history[0]["plan_id"]
current_plan = next((p for p in plans if p["plan_id"] == current_plan_id), None)
if current_plan is None:
    raise ValueError(f"current plan {current_plan_id!r} not in catalog")
```

**Existing green/cheapest selection — STAYS AS-IS per D-03** (`lambda/handler.py:93-100`):

```python
candidates = [p for p in plans if p["plan_id"] != current_plan_id]

green_candidates = [p for p in candidates if p.get("plan_type") == "green_premium"]
if not green_candidates:
    raise ValueError("No green_premium plan in catalog — demo cannot surface Green track")
green_plan = max(green_candidates, key=lambda p: p["green_score"])

cheapest_plan = min(candidates, key=projected_monthly_cost)
```

**Existing return shape — MUST NOT change** (`lambda/handler.py:105-118`):

```python
return {
    "green": {
        "plan_id": green_plan["plan_id"],
        "plan_name": green_plan["plan_name"],
        "saving_monthly": green_saving,
        "saving_annual": round(green_saving * 12, 2),
    },
    "cheapest": {
        "plan_id": cheapest_plan["plan_id"],
        "plan_name": cheapest_plan["plan_name"],
        "saving_monthly": cheapest_saving,
        "saving_annual": round(cheapest_saving * 12, 2),
    },
}
```

**Refactor target — inline branches inside the closure (from RESEARCH.md §Pattern 2, D-12 locked):**

```python
def projected_monthly_cost(plan: Dict[str, Any]) -> float:
    plan_type = plan.get("plan_type", "flat_rate")
    supply = float(plan["daily_supply_charge"]) * DAYS_PER_MONTH

    if plan_type == "time_of_use":
        peak_kwh_avg = sum(float(r.get("peak_kwh", r.get("usage_kwh", 0))) for r in billing_history) / len(billing_history)
        offpeak_kwh_avg = sum(float(r.get("offpeak_kwh", 0)) for r in billing_history) / len(billing_history)
        peak_rate = float(plan.get("peak_rate", plan["rate_per_kwh"]))
        offpeak_rate = float(plan.get("offpeak_rate", plan["rate_per_kwh"]))
        return peak_kwh_avg * peak_rate + offpeak_kwh_avg * offpeak_rate + supply

    if plan_type == "solar_fit":
        net_kwh_avg = sum(float(r.get("net_kwh", r.get("usage_kwh", 0))) for r in billing_history) / len(billing_history)
        export_kwh_avg = sum(float(r.get("export_kwh", 0)) for r in billing_history) / len(billing_history)
        sol_rate = float(plan["rate_per_kwh"])
        fit_rate = float(plan.get("fit_rate", 0))
        return net_kwh_avg * sol_rate - export_kwh_avg * fit_rate + supply

    # Default: flat_rate / green_premium — BYTE-EXACT preservation of v2.0 formula
    return avg_kwh * float(plan["rate_per_kwh"]) + supply
```

**Anti-pattern:** Do NOT extract `supply`, `avg_kwh`, or the flat-path final `return` expression into a helper; `(a * b + c)` float ordering must not change (Pitfall 2 + C7).

---

### `lambda/handler.py` — NEW `get_hardship_flag_pure` helper (D-10)

**Analog:** shape of `simulate_savings_pure` — pure helper with injectable client, `_validate_customer_id` guard at entry.

**Signature pattern to copy (from `simulate_savings_pure` @ lines 60-64 + `get_billing_history` entry guard @ 129-131):**

```python
# Entry-guard pattern (from lambda/handler.py:129-131)
customer_id = _validate_customer_id(event.get("customer_id"))
if table is None:
    raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
```

**Closest sibling — `get_billing_history` DynamoDB-read idiom** (`lambda/handler.py:123-137`):

```python
def get_billing_history(event: Dict[str, Any], context) -> List[Dict[str, Any]]:
    customer_id = _validate_customer_id(event.get("customer_id"))
    if table is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    items = response.get("Items", [])
    return sorted(items, key=lambda x: x["month"])
```

**New helper target (from RESEARCH.md §Pattern 3 — PROFILE SK row direct `get_item` lookup):**

```python
def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    """D-10 pure helper — injectable table_client (mirror of simulate_savings_pure)."""
    _validate_customer_id(customer_id)
    response = table_client.get_item(
        Key={"customer_id": customer_id, "month": "PROFILE"}
    )
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "customer_id": customer_id}
    return {
        "hardship": bool(item.get("hardship_flag", False)),
        "customer_id": customer_id,
    }
```

**Rules:**
- Use `get_item` (PK+SK direct lookup, 1 RCU), NOT `scan` / `query`.
- `bool(...)` coerce defensively — guards against wire-type drift.
- Missing PROFILE row returns `{"hardship": False, ...}` (not an error) — m3 mitigation (hardship default False for existing personas).

---

### `lambda/handler.py` — `get_billing_history` PROFILE filter (D-21)

**Analog:** self — 1-line insertion after the existing DynamoDB query.

**Existing post-process pattern to extend** (`lambda/handler.py:136-137`):

```python
items = response.get("Items", [])
return sorted(items, key=lambda x: x["month"])
```

**Refactor target (from RESEARCH.md §Pitfall 4, Option 2 — Python-level filter):**

```python
items = response.get("Items", [])
# Phase 11 D-21: filter sentinel PROFILE row so simulate_savings_pure sees only month rows
items = [i for i in items if i["month"] != "PROFILE"]
return sorted(items, key=lambda x: x["month"])
```

**Rule:** filter BEFORE sort. Python-level (not `FilterExpression`) keeps diff minimal; `month` is a DynamoDB reserved word, avoiding alias cost.

---

### `lambda/tariff_plans.json` + `infrastructure/seed_data/tariff_plans.json` — SOL + EV-TOU entries

**Analog:** existing 4-plan entries at `lambda/tariff_plans.json:1-42` (byte-equal in `infrastructure/seed_data/tariff_plans.json`).

**Existing entry shape to copy** (`lambda/tariff_plans.json:12-21` — ECO entry):

```json
{
  "plan_id": "ECO",
  "plan_name": "EcoFlex 100",
  "rate_per_kwh": 0.26,
  "daily_supply_charge": 1.10,
  "green_score": 100,
  "plan_type": "green_premium",
  "renewable_pct": 100,
  "description": "100% GreenPower accredited. Variable rate. No exit fee."
}
```

**New entries target — append to the JSON array in BOTH files in the same commit (from RESEARCH.md §Code Examples, D-15 locked constants):**

```json
{
  "plan_id": "SOL",
  "plan_name": "Solar Feed-in",
  "rate_per_kwh": 0.23,
  "daily_supply_charge": 1.10,
  "green_score": 80,
  "plan_type": "solar_fit",
  "renewable_pct": 40,
  "fit_rate": 0.08,
  "description": "Solar net-metering. Export credit at $0.08/kWh offsets consumption."
},
{
  "plan_id": "EV-TOU",
  "plan_name": "EV Drive TOU",
  "rate_per_kwh": 0.40,
  "daily_supply_charge": 1.10,
  "green_score": 30,
  "plan_type": "time_of_use",
  "renewable_pct": 20,
  "peak_rate": 0.40,
  "offpeak_rate": 0.08,
  "description": "EV-optimised time-of-use. Peak $0.40/kWh; off-peak $0.08/kWh (11pm-7am)."
}
```

**Rules:**
- v2.0 plans (STD/ECO/VAL/TOU) — do NOT add new fields (`fit_rate`, `peak_rate`, `offpeak_rate`). Byte-frozen per D-15.
- `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json` must stay byte-equal — M1 drift gate via new `tests/test_tariff_plans_byte_equal.py`.

---

### `infrastructure/seed_data/billing_records.py` — extend `_record()`, add `_profile_item()`, new persona arrays

**Analog:** self — in-place extension.

**Existing `_record()` signature** (`infrastructure/seed_data/billing_records.py:28-35`):

```python
def _record(customer_id: str, month: str, usage_kwh: int) -> Dict[str, Any]:
    return {
        "customer_id": customer_id,
        "month": month,
        "usage_kwh": usage_kwh,
        "cost_usd": _cost(usage_kwh),
        "plan_id": "STD",
    }
```

**Existing `_cost()` — STAYS UNCHANGED per D-16** (`infrastructure/seed_data/billing_records.py:22-25`):

```python
def _cost(usage_kwh: int) -> float:
    """Compute cost at STD plan rate. Used only to populate historical
    cost_usd values for realistic demo records. Savings logic never reads this."""
    return round(usage_kwh * STD_RATE + SUPPLY_CHARGE * DAYS_PER_MONTH, 2)
```

**Existing `to_dynamo()` serializer** (`infrastructure/seed_data/billing_records.py:73-87`):

```python
def to_dynamo(record: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    return {
        "customer_id": {"S": record["customer_id"]},
        "month": {"S": record["month"]},
        "usage_kwh": {"N": str(record["usage_kwh"])},
        "cost_usd": {"N": str(record["cost_usd"])},
        "plan_id": {"S": record["plan_id"]},
    }
```

**Existing persona definition shape — copy for CUST-004/005/006** (`infrastructure/seed_data/billing_records.py:46-51` — Sarah):

```python
# Sarah Chen (CUST-001) — flagship persona, high-usage family household.
# Verified avg: (425+400+450+500+550+600+625+600+550+475+450+375)/12 = 500.0 kWh/month
_SARAH_USAGE = [425, 400, 450, 500, 550, 600, 625, 600, 550, 475, 450, 375]
SARAH_CHEN_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-001", m, u) for m, u in zip(_MONTHS, _SARAH_USAGE)
]
```

**Existing bottom-of-file assertions to extend** (`infrastructure/seed_data/billing_records.py:93-99`):

```python
assert len(SARAH_CHEN_RECORDS) == 12, "Sarah must have 12 months"
assert len(MARCUS_WEBB_RECORDS) == 12, "Marcus must have 12 months"
assert len(ELENA_VASQUEZ_RECORDS) == 12, "Elena must have 12 months"
assert len(ALL_RECORDS) == 36, "ALL_RECORDS must contain exactly 36 items"
assert len(DYNAMO_RECORDS) == 36, "DYNAMO_RECORDS must contain exactly 36 items"
assert sum(_SARAH_USAGE) / 12 == 500.0, "Sarah avg must be exactly 500 kWh"
```

**Refactor target (from RESEARCH.md §Code Examples, D-16 + D-20 + LOCKED arrays from `target_equation_solver_v2.py`):**

```python
def _record(
    customer_id: str,
    month: str,
    usage_kwh: int,
    *,
    export_kwh: int = 0,
    peak_kwh: int | None = None,
    offpeak_kwh: int | None = None,
) -> Dict[str, Any]:
    net_kwh = usage_kwh - export_kwh
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


def to_dynamo(record: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    out = {
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


# LOCKED ARRAYS — from .planning/phases/11-.../scratch/target_equation_solver_v2.py
_CUST004_NET_KWH_USAGE = [650, 680, 780, 820, 840, 720, 620, 570, 540, 560, 600, 624]
_CUST004_EXPORT_KWH    = [200, 180, 120, 100,  90, 160, 220, 260, 300, 290, 260, 220]
CUST004_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-004", m, u, export_kwh=e)
    for m, u, e in zip(_MONTHS, _CUST004_NET_KWH_USAGE, _CUST004_EXPORT_KWH)
]

_CUST005_USAGE_KWH   = [560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560]
_CUST005_PEAK_KWH    = [168, 171, 183, 192, 198, 177, 168, 162, 171, 174, 168, 168]
_CUST005_OFFPEAK_KWH = [392, 399, 427, 448, 462, 413, 392, 378, 399, 406, 392, 392]
CUST005_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-005", m, u, peak_kwh=p, offpeak_kwh=o)
    for m, u, p, o in zip(_MONTHS, _CUST005_USAGE_KWH, _CUST005_PEAK_KWH, _CUST005_OFFPEAK_KWH)
]

_CUST006_USAGE_KWH = [200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185]
CUST006_RECORDS: List[Dict[str, Any]] = [
    _record("CUST-006", m, u) for m, u in zip(_MONTHS, _CUST006_USAGE_KWH)
]

PROFILE_ITEMS: List[Dict[str, Any]] = [_profile_item("CUST-006", hardship_flag=True)]

ALL_RECORDS: List[Dict[str, Any]] = (
    SARAH_CHEN_RECORDS
    + MARCUS_WEBB_RECORDS
    + ELENA_VASQUEZ_RECORDS
    + CUST004_RECORDS
    + CUST005_RECORDS
    + CUST006_RECORDS
    + PROFILE_ITEMS
)
DYNAMO_RECORDS: List[Dict[str, Dict[str, str]]] = [to_dynamo(r) for r in ALL_RECORDS]

# Extended bottom-of-file assertions
assert len(CUST004_RECORDS) == 12
assert len(CUST005_RECORDS) == 12
assert len(CUST006_RECORDS) == 12
assert len(PROFILE_ITEMS) == 1
assert len(ALL_RECORDS) == 73
assert len(DYNAMO_RECORDS) == 73
assert sum(r["usage_kwh"] for r in CUST004_RECORDS) == 8004     # avg 667
assert sum(r["export_kwh"] for r in CUST004_RECORDS) == 2400    # avg 200
assert sum(r["usage_kwh"] for r in CUST005_RECORDS) == 7000     # avg 583.33
assert sum(r["peak_kwh"] for r in CUST005_RECORDS) == 2100      # avg 175
assert sum(r["offpeak_kwh"] for r in CUST005_RECORDS) == 4900   # avg 408.33
assert sum(r["usage_kwh"] for r in CUST006_RECORDS) == 2400     # avg 200
```

**Rules:**
- Keep existing Sarah/Marcus/Elena arrays untouched — SAV-03 byte-exact relies on them.
- Optional `_record()` kwargs are keyword-only (`*,` separator) — v2.0 positional calls unchanged.
- `to_dynamo()` emits optional attrs only when present — v2.0 rows stay byte-exact on the wire.
- `hardship_flag` wire type = `BOOL` (DynamoDB native), NOT string `"true"/"false"`.

---

### `tests/conftest.py` — new fixtures (D-18)

**Analog:** existing `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` @ `tests/conftest.py:46-100`.

**Existing fixture pattern to copy** (`tests/conftest.py:46-62`):

```python
@pytest.fixture
def mock_savings_response():
    """Canonical savings response matching simulate_savings_pure output for Sarah Chen."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 30.00,
            "saving_annual": 360.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 55.00,
            "saving_annual": 660.00,
        },
    }
```

**Append target (from RESEARCH.md §Code Examples — locked byte-exact values):**

```python
@pytest.fixture
def mock_cust004_response():
    """CUST-004 solar persona — Green (ECO) and Cheapest (SOL)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 40.02,
            "saving_annual": 480.24,
        },
        "cheapest": {
            "plan_id": "SOL",
            "plan_name": "Solar Feed-in",
            "saving_monthly": 76.03,
            "saving_annual": 912.36,
        },
    }


@pytest.fixture
def mock_cust005_response():
    """CUST-005 EV persona — Green (ECO) and Cheapest (EV-TOU)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 35.00,
            "saving_annual": 420.00,
        },
        "cheapest": {
            "plan_id": "EV-TOU",
            "plan_name": "EV Drive TOU",
            "saving_monthly": 84.00,
            "saving_annual": 1008.00,
        },
    }


@pytest.fixture
def mock_cust006_response():
    """CUST-006 hardship persona — valid flat-catalog recommendation (Phase 14 short-circuits later)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 12.00,
            "saving_annual": 144.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 22.00,
            "saving_annual": 264.00,
        },
    }


@pytest.fixture
def mock_cust006_hardship():
    """CUST-006 hardship-flag lookup — shape returned by get_hardship_flag_pure."""
    return {
        "hardship": True,
        "customer_id": "CUST-006",
    }
```

**Also consider adding persona-billing fixtures (mirror `sarah_billing`/`marcus_billing`/`elena_billing` @ lines 19-34):**

```python
@pytest.fixture
def cust004_billing():
    from infrastructure.seed_data.billing_records import CUST004_RECORDS
    return CUST004_RECORDS


@pytest.fixture
def cust005_billing():
    from infrastructure.seed_data.billing_records import CUST005_RECORDS
    return CUST005_RECORDS


@pytest.fixture
def cust006_billing():
    from infrastructure.seed_data.billing_records import CUST006_RECORDS
    return CUST006_RECORDS
```

---

### `tests/test_simulate_savings.py` — extend with CUST-004/005/006 parametrisations

**Analog:** existing Sarah/Marcus/Elena tests @ `tests/test_simulate_savings.py:17-86`.

**Existing `importlib` workaround (MUST use — `lambda` is a Python keyword)** (`tests/test_simulate_savings.py:12-14`):

```python
import importlib
import pytest

# importlib fallback — `from lambda.handler import` is a SyntaxError in Python
handler = importlib.import_module("lambda.handler")
simulate_savings_pure = handler.simulate_savings_pure
```

**Existing byte-exact pattern to copy** (`tests/test_simulate_savings.py:19-26`):

```python
def test_flagship_persona_green_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 30.00) < 0.01


def test_flagship_persona_cheapest_saving(sarah_billing, tariff_plans):
    result = simulate_savings_pure(sarah_billing, tariff_plans)
    assert abs(result["cheapest"]["saving_monthly"] - 55.00) < 0.01
```

**Existing cross-persona invariant pattern** (`tests/test_simulate_savings.py:61-72`):

```python
def test_cheapest_always_gte_green(sarah_billing, marcus_billing, elena_billing, tariff_plans):
    for billing in (sarah_billing, marcus_billing, elena_billing):
        result = simulate_savings_pure(billing, tariff_plans)
        assert result["cheapest"]["saving_monthly"] >= result["green"]["saving_monthly"], \
            f"Invariant violated for {billing[0]['customer_id']}"


def test_tou_never_selected(sarah_billing, marcus_billing, elena_billing, tariff_plans):
    for billing in (sarah_billing, marcus_billing, elena_billing):
        result = simulate_savings_pure(billing, tariff_plans)
        assert result["green"]["plan_id"] != "TOU"
        assert result["cheapest"]["plan_id"] != "TOU"
```

**Extension target — add CUST-004/005/006 tests mirroring the Sarah shape:**

```python
def test_cust004_green_saving(cust004_billing, tariff_plans):
    result = simulate_savings_pure(cust004_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 40.02) < 0.01
    assert result["green"]["plan_id"] == "ECO"


def test_cust004_cheapest_is_sol(cust004_billing, tariff_plans):
    result = simulate_savings_pure(cust004_billing, tariff_plans)
    assert result["cheapest"]["plan_id"] == "SOL"
    assert abs(result["cheapest"]["saving_monthly"] - 76.03) < 0.01


def test_cust005_green_saving(cust005_billing, tariff_plans):
    result = simulate_savings_pure(cust005_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 35.00) < 0.01
    assert result["green"]["plan_id"] == "ECO"


def test_cust005_cheapest_is_evtou(cust005_billing, tariff_plans):
    result = simulate_savings_pure(cust005_billing, tariff_plans)
    assert result["cheapest"]["plan_id"] == "EV-TOU"
    assert abs(result["cheapest"]["saving_monthly"] - 84.00) < 0.01


def test_cust006_valid_recommendation(cust006_billing, tariff_plans):
    result = simulate_savings_pure(cust006_billing, tariff_plans)
    assert abs(result["green"]["saving_monthly"] - 12.00) < 0.01
    assert abs(result["cheapest"]["saving_monthly"] - 22.00) < 0.01
    assert result["green"]["plan_id"] == "ECO"
    assert result["cheapest"]["plan_id"] == "VAL"
```

**Also extend `test_cheapest_always_gte_green` and `test_tou_never_selected` to include all 5 personas.** (The TOU-never-selected invariant holds for CUST-004/005 by construction but is worth explicit coverage.)

---

### `tests/test_seeder_smoke.py` — bump 36→73 + new persona/PROFILE assertions

**Analog:** existing Sarah smoke test @ `tests/test_seeder_smoke.py:41-47`.

**Existing count assertion to bump** (`tests/test_seeder_smoke.py:36-38`):

```python
def test_table_has_36_items(dynamodb_client):
    resp = dynamodb_client.scan(TableName="tariff-billing", Select="COUNT")
    assert resp["Count"] == 36, f"Expected 36 seeded items, got {resp['Count']}"
```

**Existing persona-12-months pattern to copy** (`tests/test_seeder_smoke.py:41-47`):

```python
def test_sarah_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-001"}},
    )
    assert len(resp["Items"]) == 12
```

**Extension target:**

```python
def test_table_has_73_items(dynamodb_client):
    resp = dynamodb_client.scan(TableName="tariff-billing", Select="COUNT")
    assert resp["Count"] == 73, f"Expected 73 seeded items, got {resp['Count']}"


def test_cust004_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-004"}},
    )
    # 12 month rows + 0 PROFILE for CUST-004 (no hardship on solar persona)
    assert len(resp["Items"]) == 12


def test_cust005_has_12_months(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-005"}},
    )
    assert len(resp["Items"]) == 12


def test_cust006_has_12_months_plus_profile(dynamodb_client):
    resp = dynamodb_client.query(
        TableName="tariff-billing",
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": {"S": "CUST-006"}},
    )
    # 12 month rows + 1 PROFILE row
    assert len(resp["Items"]) == 13


def test_cust006_profile_row_carries_hardship_flag(dynamodb_client):
    resp = dynamodb_client.get_item(
        TableName="tariff-billing",
        Key={"customer_id": {"S": "CUST-006"}, "month": {"S": "PROFILE"}},
    )
    assert "Item" in resp
    assert resp["Item"]["hardship_flag"] == {"BOOL": True}
```

**Rule:** leave existing `test_lambda_invokes_sarah_savings_match_demo02` @ lines 68-80 UNCHANGED — it is the live SAV-03 byte-exact v2.0 gate.

---

### `tests/test_tariff_plans_byte_equal.py` — NEW (M1 mitigation)

**Analog:** `tests/conftest.py:7-10` — tariff-plans file-loading pattern.

**Existing pattern to copy** (`tests/conftest.py:7-10`):

```python
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_REPO_ROOT, "lambda", "tariff_plans.json")) as f:
    _PLANS = json.load(f)
```

**New file target (from RESEARCH.md §Pattern 4):**

```python
# tests/test_tariff_plans_byte_equal.py — NEW
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
```

**Rule:** write this test FIRST (it will pass against the existing 4-plan files for byte/structural tests — the `test_catalog_has_6_plans` fails until new plans are added). Then add SOL + EV-TOU to both JSON files in the same commit.

---

### `tests/test_get_hardship_flag_pure.py` — NEW (DATA-06 coverage)

**Analog:** `tests/test_simulate_savings.py` (importlib pattern + fixture-driven unit-test style).

**Existing importlib workaround to reuse** (`tests/test_simulate_savings.py:9-14`):

```python
import importlib
import pytest

handler = importlib.import_module("lambda.handler")
simulate_savings_pure = handler.simulate_savings_pure
```

**Existing injection-via-fixture style** — `simulate_savings_pure` is called with two arguments (billing + plans) in tests. Same shape applies here: `get_hardship_flag_pure(customer_id, table_client)` takes an injectable client. Tests must pass a fake/mocked `table_client` (standard pytest unittest.mock or MagicMock).

**New file target:**

```python
# tests/test_get_hardship_flag_pure.py — NEW
import importlib
from unittest.mock import MagicMock
import pytest

handler = importlib.import_module("lambda.handler")
get_hardship_flag_pure = handler.get_hardship_flag_pure


def _fake_table_with_item(item: dict) -> MagicMock:
    client = MagicMock()
    client.get_item.return_value = {"Item": item} if item else {}
    return client


def test_hardship_persona_returns_true():
    """CUST-006 has PROFILE row with hardship_flag=True."""
    client = _fake_table_with_item({
        "customer_id": "CUST-006",
        "month": "PROFILE",
        "hardship_flag": True,
    })
    result = get_hardship_flag_pure("CUST-006", client)
    assert result == {"hardship": True, "customer_id": "CUST-006"}


def test_nonhardship_persona_returns_false_when_profile_missing():
    """CUST-001 has no PROFILE row — default hardship=False per m3 mitigation."""
    client = _fake_table_with_item(None)
    result = get_hardship_flag_pure("CUST-001", client)
    assert result == {"hardship": False, "customer_id": "CUST-001"}


def test_malformed_customer_id_rejected():
    """V5 input validation — _validate_customer_id guards entry."""
    client = MagicMock()
    with pytest.raises(ValueError):
        get_hardship_flag_pure("not-a-customer-id", client)
    # Ensure DynamoDB was NEVER called
    client.get_item.assert_not_called()


def test_profile_item_with_hardship_false_returns_false():
    """Defensive: PROFILE row present but hardship_flag=False still returns False."""
    client = _fake_table_with_item({
        "customer_id": "CUST-001",
        "month": "PROFILE",
        "hardship_flag": False,
    })
    result = get_hardship_flag_pure("CUST-001", client)
    assert result == {"hardship": False, "customer_id": "CUST-001"}
```

**Rules:**
- Use `MagicMock()` for `table_client` — same pattern as pytest standard library usage (no new fixture needed in conftest).
- Validate `_validate_customer_id` is called BEFORE `table_client.get_item` — the regex guard is the V5 gate.

---

### `tests/test_get_billing_history.py` (NEW or extension) — D-21 PROFILE filter gate

**Analog:** `tests/test_simulate_savings.py` importlib + MagicMock pattern.

**Test target:**

```python
# tests/test_get_billing_history.py — NEW (or extend tests/test_simulate_savings.py)
import importlib
from unittest.mock import MagicMock
import os
import pytest

handler = importlib.import_module("lambda.handler")


def _fake_query_returning_13_items():
    """12 month rows + 1 PROFILE row (CUST-006 shape)."""
    months = ["2025-04","2025-05","2025-06","2025-07","2025-08","2025-09",
              "2025-10","2025-11","2025-12","2026-01","2026-02","2026-03"]
    items = [
        {"customer_id": "CUST-006", "month": m, "usage_kwh": 200, "cost_usd": 97.49, "plan_id": "STD"}
        for m in months
    ]
    items.append({"customer_id": "CUST-006", "month": "PROFILE", "hardship_flag": True})
    return {"Items": items}


def test_profile_row_filtered_for_hardship_persona(monkeypatch):
    """D-21: get_billing_history must strip PROFILE sentinel row before returning."""
    fake_table = MagicMock()
    fake_table.query.return_value = _fake_query_returning_13_items()
    monkeypatch.setattr(handler, "table", fake_table)

    result = handler.get_billing_history({"customer_id": "CUST-006"}, None)
    assert len(result) == 12
    assert all(item["month"] != "PROFILE" for item in result)
    # sorted by month ASC
    assert result[0]["month"] == "2025-04"
    assert result[-1]["month"] == "2026-03"
```

**Rules:**
- Use `monkeypatch.setattr(handler, "table", fake_table)` — the module-level `table` is `None` by default when `TABLE_NAME` is unset; tests must patch it in.
- Assert `len(result) == 12` (not 13) — the D-21 filter is the gate.

## Shared Patterns

### Pure-helper-plus-handler (applies to `simulate_savings_pure`, new `get_hardship_flag_pure`)
**Source:** `lambda/handler.py:60-118` (pure) + `lambda/handler.py:140-145` (wrapper).
**Apply to:** New `get_hardship_flag_pure` helper (and any future pure helper in the Tools Lambda).

```python
# Pure: no boto3, no os.environ, injectable clients, raises ValueError on bad input
def simulate_savings_pure(billing_history, plans) -> Dict[str, Any]: ...

# Wrapper: calls pure helper after validating env + fetching data via boto3
def simulate_savings(event, context) -> Dict[str, Any]:
    billing = get_billing_history(event, context)
    if not billing:
        raise ValueError(f"No billing history for {event.get('customer_id')!r}")
    return simulate_savings_pure(billing, TARIFF_PLANS)
```

**Phase 11 note:** `get_hardship_flag_pure` is added this phase WITHOUT a Lambda-handler wrapper. Wrapper comes in Phase 13 (agent action dispatcher). Keep the pure helper offline-testable only.

### Input validation — `_validate_customer_id` (V5 gate)
**Source:** `lambda/handler.py:39-52`.
**Apply to:** New `get_hardship_flag_pure` (any new customer-id-accepting helper).

```python
_CUSTOMER_ID_PATTERN = re.compile(r"^CUST-\d{3,6}$")

def _validate_customer_id(customer_id: Any) -> str:
    if not isinstance(customer_id, str):
        raise ValueError(f"customer_id must be a string, got {type(customer_id).__name__}")
    if not _CUSTOMER_ID_PATTERN.match(customer_id):
        raise ValueError(f"customer_id must match CUST-<digits>; got {customer_id!r}")
    return customer_id
```

**Regex already matches CUST-004/005/006** (3-digit suffix).

### `importlib.import_module("lambda.handler")` — test import of keyword-named module
**Source:** `tests/test_simulate_savings.py:9-14`.
**Apply to:** All new tests that import `lambda/handler.py` (`test_get_hardship_flag_pure.py`, `test_get_billing_history.py`).

```python
import importlib
handler = importlib.import_module("lambda.handler")
get_hardship_flag_pure = handler.get_hardship_flag_pure  # or whatever symbol
```

**Never** `from lambda.handler import ...` — `lambda` is a Python keyword → SyntaxError.

### Byte-exact fixture pattern (SAV-03 golden-values)
**Source:** `tests/conftest.py:46-100`.
**Apply to:** `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`.

**Rule:** exact numeric literals, no arithmetic in fixture. `saving_annual` is the number the pure helper returns (`round(saving_monthly * 12, 2)`), not a test-computed value.

### Smoke-test skip marker (pytest.ini `smoke` marker)
**Source:** `tests/test_seeder_smoke.py:12-16`.
**Apply to:** any new smoke-requiring tests (but Phase 11 only extends the existing one).

```python
pytestmark = pytest.mark.skipif(
    not os.environ.get("AWS_DEFAULT_REGION")
    or os.environ.get("SKIP_AWS_SMOKE") == "1",
    reason="AWS credentials not configured or smoke explicitly skipped",
)
```

### Source-of-truth duplication (byte-equality contract)
**Source:** CLAUDE.md §"Code layout pointers" + RESEARCH.md §Pattern 4.
**Apply to:** `lambda/tariff_plans.json` ↔ `infrastructure/seed_data/tariff_plans.json`.

**Rule:** edit both in the same commit. New `tests/test_tariff_plans_byte_equal.py` enforces this going forward.

### Bottom-of-file import-time assertions
**Source:** `infrastructure/seed_data/billing_records.py:93-99`.
**Apply to:** extended `billing_records.py` (new CUST-004/005/006 asserts).

**Rule:** assertions fail at Python import time — CDK synth fails fast if arrays drift from target averages. Mirror existing shape (`assert len(...) == 12`, `assert sum(...) == N`).

## No Analog Found

None — every file has a strong in-repo analog (most by self-extension).

## Metadata

**Analog search scope:**
- `lambda/` (handler.py, tariff_plans.json)
- `infrastructure/seed_data/` (billing_records.py, tariff_plans.json)
- `infrastructure/constructs/` (seeder.py verified in RESEARCH §Pattern 1, unchanged)
- `tests/` (conftest.py, test_simulate_savings.py, test_seeder_smoke.py)
- `.planning/phases/11-new-personas-tariff-archetypes/` (CONTEXT.md, RESEARCH.md)

**Files scanned:** 9 source/test files + 2 phase docs (CONTEXT + RESEARCH).
**Pattern extraction date:** 2026-04-28.
**Lock status:** All engineered numeric constants (rates, arrays, byte-exact savings) sourced from `.planning/phases/11-.../scratch/target_equation_solver_v2.py` via RESEARCH.md §Code Examples.

## PATTERN MAPPING COMPLETE

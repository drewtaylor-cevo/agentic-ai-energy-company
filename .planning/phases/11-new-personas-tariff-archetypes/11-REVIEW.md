---
phase: 11-new-personas-tariff-archetypes
reviewed: 2026-04-28T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - infrastructure/constructs/seeder.py
  - infrastructure/seed_data/billing_records.py
  - infrastructure/seed_data/tariff_plans.json
  - lambda/handler.py
  - lambda/tariff_plans.json
  - tests/conftest.py
  - tests/test_cdk_synth.py
  - tests/test_get_billing_history.py
  - tests/test_get_hardship_flag_pure.py
  - tests/test_schema.py
  - tests/test_seeder_smoke.py
  - tests/test_simulate_savings.py
  - tests/test_tariff_plans_byte_equal.py
findings:
  critical: 0
  warning: 3
  info: 5
  total: 8
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-04-28
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 11 extends the tariff catalogue with two new archetypes (`SOL`, `EV-TOU`) and adds three personas (CUST-004 solar, CUST-005 EV, CUST-006 hardship) plus a PROFILE sentinel-SK row carrying `hardship_flag`. The review verified:

- **SAV-03 preserved.** All arithmetic lives in `simulate_savings_pure`; the dispatcher's `plan_type` branching routes SOL/EV-TOU through distinct formulas while the flat-rate default preserves the v2.0 path byte-exactly.
- **Byte-exact savings reproduce.** Independent re-derivation confirms CUST-004 (ECO $40.02 / SOL $76.03), CUST-005 (ECO $35.00 / EV-TOU $84.00), CUST-006 (ECO $12.00 / VAL $22.00), and the preserved v2.0 numbers (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67).
- **`tariff_plans.json` byte-equality** is protected by a dedicated test.
- **V5 input validation** on `customer_id` is intact; `get_hardship_flag_pure` also runs the gate before any DynamoDB call.
- **D-21 PROFILE filter** in `get_billing_history` prevents `simulate_savings_pure` from iterating a row without `usage_kwh`.

No critical defects were found, but three meaningful warnings and a handful of doc/style slips are worth fixing before this ships into the narrative work of Phase 14. In particular, a latent correctness trap in the TOU/EV-TOU and SOL fallback logic could bite a future persona if its seed records are only partially populated.

## Warnings

### WR-01: TOU/EV-TOU dispatcher silently mixes populated and unpopulated records

**File:** `lambda/handler.py:90-96`
**Issue:** When `plan_type == "time_of_use"`, the dispatcher computes `peak_kwh_avg` as the per-record fallback `r.get("peak_kwh", r.get("usage_kwh", 0))`. This fallback is **applied per-record**, so a billing history containing a mix of rows — some with `peak_kwh` present, some without — will sum fallback values (full `usage_kwh`) and real peak values into the same average. The current seed data is uniform (all CUST-005 rows carry `peak_kwh`; nobody else does), so the bug is latent — but any future persona with a mid-year plan change, or a data-quality issue producing a single row without `peak_kwh`, would see a wrong projected cost with no signal.

Same shape applies to `plan_type == "solar_fit"` at line 106 (`r.get("export_kwh", 0)`) — a single missing `export_kwh` on an otherwise-solar history would silently zero that month's export credit.

**Fix:** Make the fallback all-or-nothing at the history level, not per-record:

```python
if plan_type == "time_of_use":
    has_split = all("peak_kwh" in r and "offpeak_kwh" in r for r in billing_history)
    if has_split:
        peak_kwh_avg = sum(float(r["peak_kwh"]) for r in billing_history) / len(billing_history)
        offpeak_kwh_avg = sum(float(r["offpeak_kwh"]) for r in billing_history) / len(billing_history)
    else:
        peak_kwh_avg = avg_kwh
        offpeak_kwh_avg = 0.0
    peak_rate = float(plan.get("peak_rate", plan["rate_per_kwh"]))
    offpeak_rate = float(plan.get("offpeak_rate", plan["rate_per_kwh"]))
    return peak_kwh_avg * peak_rate + offpeak_kwh_avg * offpeak_rate + supply
```

Alternatively, add an assertion in the `time_of_use` branch that rejects partial populations.

---

### WR-02: Seeder lacks an `on_update` handler; re-seeds depend on phys-id replacement behaviour

**File:** `infrastructure/constructs/seeder.py:55-67`
**Issue:** The seeder is `on_create`-only. The docstring (lines 7-9, 11-21) acknowledges this and prescribes a `physical_resource_id` suffix bump (`v1 -> v2`) as the re-fire mechanism. The known deploy anomaly documented in the reviewer context (Seeder1 did not re-write its v2 payload; 14 rows were backfilled manually) indicates this mechanism is unreliable in practice — CloudFormation does not always treat a physical-resource-id string change as a replacement trigger for `AwsCustomResource`, especially when nothing else in the construct has drifted. Future phases that add/replace seed rows will hit the same trap, and there is no test or runtime assertion that catches a partial-seed outcome.

**Fix:** Add a symmetric `on_update` handler so CDK re-fires the batch write whenever the `parameters` payload changes (which happens naturally when `DYNAMO_RECORDS` changes):

```python
seeder = cr.AwsCustomResource(
    self,
    f"BillingSeeder{i}",
    on_create=cr.AwsSdkCall(...),
    on_update=cr.AwsSdkCall(  # identical call, different hook
        service="DynamoDB",
        action="batchWriteItem",
        parameters={"RequestItems": {table.table_name: request_items}},
        physical_resource_id=cr.PhysicalResourceId.of(f"BillingSeeder-{i}-v2"),
    ),
    policy=cr.AwsCustomResourcePolicy.from_statements([...]),
)
```

Keep idempotency in mind — `BatchWriteItem` is a `PutItem` under the hood and will overwrite (not merge) any manual edits to existing rows. For a demo this is the desired behaviour.

---

### WR-03: `simulate_savings_pure` selects current plan from the earliest month, not the latest

**File:** `lambda/handler.py:81`
**Issue:** `current_plan_id = billing_history[0]["plan_id"]`. Callers pass the list produced by `get_billing_history`, which is sorted ASC by month, so this picks the **earliest** month's plan, not the customer's most recent plan. With today's seed data every row has the same `plan_id` (`"STD"`), so there is no observable defect — but this is fragile against any future persona that switches plans mid-year, and the implicit contract is backwards (we're recommending what to switch *from*, so "from" should be current, not historical).

**Fix:** Prefer the most-recent record. `billing_history[-1]["plan_id"]` after sort is a one-character change; alternatively, pass `current_plan_id` explicitly as an argument so callers declare intent. Add a test that exercises a mid-year switch to lock the behaviour.

## Info

### IN-01: `tariff_plans` fixture docstring stale — now a 6-plan catalogue

**File:** `tests/conftest.py:15`
**Issue:** The fixture docstring says `"""4-plan tariff catalog (STD/ECO/VAL/TOU) from lambda/tariff_plans.json."""` but the catalog now carries six plans (`STD/ECO/VAL/TOU/SOL/EV-TOU`).
**Fix:** Update the docstring: `"""6-plan tariff catalog (STD/ECO/VAL/TOU/SOL/EV-TOU) from lambda/tariff_plans.json."""`.

---

### IN-02: Marcus / Elena savings figures in module docstring disagree with fixtures and CLAUDE.md

**File:** `infrastructure/seed_data/billing_records.py:6-7`
**Issue:** The module docstring claims:
- `Marcus Webb (CUST-002): avg 282 kWh -> Green $16.92/mo, Cheapest $31.02/mo`
- `Elena Vasquez (CUST-003): avg 233 kWh -> Green $13.98/mo, Cheapest $25.63/mo`

Re-derivation against the tariff catalogue produces `$16.90 / $30.98` and `$14.00 / $25.67` — which matches `mock_marcus_response` / `mock_elena_response` in `tests/conftest.py` and CLAUDE.md's byte-exact invariant. The docstring is the stale artifact.
**Fix:** Update the docstring to `$16.90/$30.98` and `$14.00/$25.67` respectively, matching the canonical values in CLAUDE.md.

---

### IN-03: `test_marcus_savings_approximate` / `test_elena_savings_approximate` comments echo the stale figures

**File:** `tests/test_simulate_savings.py:77-79, 84-86`
**Issue:** Comments refer to `Green ~$16.90, Cheapest ~$30.98` (fine) but the assertion uses `16.92 / 31.02` with a `0.10` tolerance. The same pattern appears for Elena. Tests pass by tolerance, but the target values don't match the byte-exact canonical set.
**Fix:** Tighten to exact equality against the conftest mock responses or at minimum update the comments to reflect the true values `16.90 / 30.98` and `14.00 / 25.67`.

---

### IN-04: `test_schema.py` comment claims new personas start on SOL / EV-TOU / STD — actually all-STD

**File:** `tests/test_schema.py:95-96`
**Issue:** Comment reads `New personas (Maya/Dmitri/Nkechi) start on SOL/EV-TOU/STD respectively per Phase 11 spec`, but `_record` in `billing_records.py:52` hardcodes `"plan_id": "STD"` for every record, so all six personas carry `plan_id="STD"` on all 12 months. The test `test_v2_personas_on_std_plan` is therefore a proper subset of reality; the comment is misleading and will confuse a future reader who tries to extend the test to assert "CUST-004 starts on SOL".
**Fix:** Either (a) update the comment to reflect that all personas currently start on STD for the demo narrative (savings baseline), or (b) if the spec truly intends new personas to start on different plans, update `billing_records.py` to pass `plan_id` through `_record`. Option (a) is lower-risk and preserves the current byte-exact savings.

---

### IN-05: `cost_usd` on solar records is computed from `net_kwh`, labelled "STD baseline"

**File:** `infrastructure/seed_data/billing_records.py:49-51`
**Issue:** Comment states `"solar records use net_kwh in cost_usd (reflects STD baseline without FiT)"`, but STD is a flat tariff that bills **gross** consumption, not net. A real customer on STD with solar export would see a bill based on `usage_kwh * 0.32` (net metering assumed pre-inverter). Using `net_kwh` undercounts the historical cost.

This is not a correctness defect for the demo — `simulate_savings_pure` never reads `cost_usd`, and the invariant is documented — but the comment conflates net-metered billing (what SOL does) with STD billing (what the record claims to describe), which will mislead a future reader into thinking the number is the real historical STD cost.
**Fix:** Either change the formula to `_cost(usage_kwh)` for consistency with the plan_id=STD invariant, or update the comment to say `"stored as a stylised 'would-be on-SOL' cost for demo display — not a real STD bill; savings math never reads it"`.

---

_Reviewed: 2026-04-28_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_

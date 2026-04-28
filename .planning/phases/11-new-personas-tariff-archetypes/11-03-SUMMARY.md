---
phase: 11-new-personas-tariff-archetypes
plan: 03
subsystem: seed-data
tags: [phase-11, DATA-04, DATA-05, DATA-06, DATA-07, cust-004, cust-005, cust-006, profile-item]

dependency_graph:
  requires: [11-01-tariff-catalog]
  provides: [cust-004-records, cust-005-records, cust-006-records, profile-sentinel-sk]
  affects: [foundation-stack-seeder, simulate-savings-pure-input]

tech_stack:
  added: [PROFILE-sentinel-SK-pattern]
  patterns: [optional-kwarg-extension, import-time-assertion-gate, DynamoDB-BOOL-wire-type]

key_files:
  created: []
  modified:
    - path: infrastructure/seed_data/billing_records.py
      role: seed-data-module
      lines_added: 136
      lines_deleted: 17

decisions:
  - id: D-01
    what: Extended `_record()` with optional kwargs (export_kwh, peak_kwh, offpeak_kwh) as keyword-only args
    why: Back-compat — v2.0 personas use positional args unchanged; new personas use kwargs
    impact: Zero byte-diff on existing SARAH/MARCUS/ELENA records
  - id: D-08-D-09
    what: PROFILE sentinel-SK row shape via `_profile_item()` helper
    why: Store hardship_flag on existing tariff-billing table without new CFN resource
    impact: DynamoDB wire type BOOL (not string) for hardship_flag per Pattern 3
  - id: D-16-D-20
    what: Solar records compute cost_usd from net_kwh (not gross usage_kwh)
    why: Reflects STD baseline without FiT credit (customer pays on net consumption)
    impact: Informational field only; simulate_savings_pure never reads cost_usd (DATA-03)

metrics:
  duration_seconds: 161
  tasks_completed: 2
  files_modified: 1
  commits: 2
  test_commands_run: 6
---

# Phase 11 Plan 03: Seed Data Extension (CUST-004/005/006 + PROFILE) Summary

Extended `infrastructure/seed_data/billing_records.py` with three new persona fixture arrays (CUST-004 solar with net-metering, CUST-005 EV-TOU with peak/offpeak split, CUST-006 hardship low-usage) and a PROFILE sentinel-SK row carrying hardship_flag. Total seed data grows from 36 items (v2.0) to 73 items (36 v2.0 + 36 new billing + 1 PROFILE). Extended `_record()` helper with optional kwargs (keyword-only `export_kwh`, `peak_kwh`, `offpeak_kwh`) to support solar and TOU record shapes without breaking v2.0 positional-arg calls. Extended `to_dynamo()` serializer to emit optional attributes only when present, and to use DynamoDB native BOOL wire type for hardship_flag on PROFILE rows. Added comprehensive bottom-of-file import-time assertions (per-persona sum locks, integrity checks for export ≤ usage and peak + offpeak = usage, PROFILE shape guard, 73-item aggregate count). V2.0 persona arrays (Sarah/Marcus/Elena) remain byte-frozen — untouched by this plan.

## One-liner

Three new persona arrays (CUST-004 solar net_avg=667 export_avg=200, CUST-005 EV 30/70 peak/offpeak total_avg=583.33, CUST-006 hardship avg=200) + PROFILE sentinel-SK (hardship_flag=True) extend `billing_records.py` to 73 items with extended `_record()` optional kwargs, BOOL-wire `to_dynamo()`, and import-time assertion gates — v2.0 byte-exact preserved.

## What Was Done

### Task 3.1: Extended `_record()` + `to_dynamo()` + added `_profile_item()` helper

**Commit:** `54ee1e2`

Extended `_record()` signature with keyword-only optional args (`export_kwh=0`, `peak_kwh=None`, `offpeak_kwh=None`). Positional-arg calls (v2.0 personas) unchanged — the `*,` separator enforces keyword-only for new args. Solar records (export_kwh > 0) emit `export_kwh` + `net_kwh` fields; EV-TOU records (peak/offpeak present) emit `peak_kwh` + `offpeak_kwh` fields. Flat records (v2.0 + CUST-006) emit neither. D-20 logic: solar records compute `cost_usd` from `net_kwh` (reflects STD baseline without FiT); flat records compute from `usage_kwh` (back-compat since export_kwh=0 → net_kwh=usage_kwh).

Added `_profile_item(customer_id, hardship_flag=False)` helper emitting PROFILE sentinel-SK row shape per D-08/D-09: `{customer_id, month: "PROFILE", hardship_flag: bool}`. Phase 11 carries only hardship_flag; other PROFILE attributes deferred.

Extended `to_dynamo()` serializer to emit optional attributes only when present in the record dict. For PROFILE rows, `hardship_flag` serializes as `{"BOOL": bool(...)}` (DynamoDB native BOOL wire type per Pattern 3), not a string. V2.0 billing rows (no optional fields) serialize byte-identically to pre-Phase-11.

**Files modified:**
- `infrastructure/seed_data/billing_records.py` — added Optional import, replaced `_record()` with extended signature, added `_profile_item()`, replaced `to_dynamo()` with conditional emission logic

**Verification:**
- V2.0 flat record (CUST-001) has no export_kwh, peak_kwh, net_kwh fields ✓
- Solar record (CUST-004) has export_kwh=200, net_kwh=450 (usage 650 - export 200) ✓
- EV-TOU record (CUST-005) has peak_kwh=168, offpeak_kwh=392 ✓
- PROFILE item wire format has `hardship_flag: {"BOOL": true}`, no usage_kwh leakage ✓

### Task 3.2: Added CUST-004/005/006 arrays + PROFILE_ITEMS + extended ALL_RECORDS / DYNAMO_RECORDS / assertions

**Commit:** `9d70f10`

Added three new persona arrays using locked constants from `scratch/target_equation_solver_v2.py`:

1. **CUST-004 Solar PV (DATA-04):**
   - `_CUST004_USAGE_KWH = [650, 680, 780, 820, 840, 720, 620, 570, 540, 560, 600, 624]` (sum=8004, avg=667)
   - `_CUST004_EXPORT_KWH = [200, 180, 120, 100, 90, 160, 220, 260, 300, 290, 260, 220]` (sum=2400, avg=200)
   - 12 records calling `_record("CUST-004", month, usage, export_kwh=export)`
   - Seasonal shape: summer = low net + high export (self-consumption), winter = high net + low export

2. **CUST-005 EV TOU (DATA-05):**
   - `_CUST005_USAGE_KWH = [560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560]` (sum=7000, avg=583.33)
   - `_CUST005_PEAK_KWH = [168, 171, 183, 192, 198, 177, 168, 162, 171, 174, 168, 168]` (sum=2100, 30%)
   - `_CUST005_OFFPEAK_KWH = [392, 399, 427, 448, 462, 413, 392, 378, 399, 406, 392, 392]` (sum=4900, 70%)
   - 12 records calling `_record("CUST-005", month, usage, peak_kwh=peak, offpeak_kwh=offpeak)`
   - Engineered 30/70 peak/offpeak split (overnight EV charging dominant)

3. **CUST-006 Hardship (DATA-06 / D-07):**
   - `_CUST006_USAGE_KWH = [200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185]` (sum=2400, avg=200)
   - 12 flat records (no optional fields)
   - Low, stressed-looking usage shape

Added `PROFILE_ITEMS = [_profile_item("CUST-006", hardship_flag=True)]` — one PROFILE sentinel-SK row for hardship persona.

Extended `ALL_RECORDS` to concatenate all six persona arrays + PROFILE_ITEMS → 73 items total (36 v2.0 + 36 new billing + 1 PROFILE).

Extended bottom-of-file assertions:
- V2.0 persona invariants unchanged (Sarah avg=500 kWh, etc.)
- New persona sum locks (8004, 2400, 7000, 2100, 4900, 2400)
- T-11-08 integrity: `all(export_kwh ≤ usage_kwh)` for CUST-004 (prevents negative net_kwh)
- T-11-09 integrity: `all(peak_kwh + offpeak_kwh == usage_kwh)` for CUST-005 (30/70 split clean)
- PROFILE shape guard: `len(PROFILE_ITEMS) == 1`, `customer_id == "CUST-006"`, `month == "PROFILE"`, `hardship_flag is True`
- Aggregate count: `len(ALL_RECORDS) == 73`, `len(DYNAMO_RECORDS) == 73`

**Files modified:**
- `infrastructure/seed_data/billing_records.py` — added locked arrays, PROFILE_ITEMS, extended ALL_RECORDS, replaced assertions

**Verification:**
- ALL_RECORDS = 73 items ✓
- DYNAMO_RECORDS = 73 items ✓
- CUST-004: 12 records, usage sum=8004, export sum=2400, all export ≤ usage ✓
- CUST-005: 12 records, peak sum=2100, offpeak sum=4900, all peak+offpeak=usage ✓
- CUST-006: 12 records, usage sum=2400 ✓
- PROFILE_ITEMS = 1 entry with correct shape ✓
- PROFILE wire row has `hardship_flag: {"BOOL": true}`, no usage_kwh ✓

## Deviations from Plan

None — plan executed exactly as written. All locked arrays from `scratch/target_equation_solver_v2.py` used verbatim. V2.0 persona arrays untouched byte-for-byte. No unexpected issues.

## Known Stubs

None. All seed data is deterministic engineered values. No placeholders, no TODO comments.

## Threat Flags

None. No new trust boundaries introduced — seed data consumed by CDK seeder at synth/deploy time only.

## Self-Check: PASSED

✓ File exists: `infrastructure/seed_data/billing_records.py`
✓ Commits exist: `54ee1e2`, `9d70f10`
✓ Import succeeds: `from infrastructure.seed_data.billing_records import CUST004_RECORDS, CUST005_RECORDS, CUST006_RECORDS, PROFILE_ITEMS`
✓ ALL_RECORDS count: 73
✓ DYNAMO_RECORDS count: 73
✓ All bottom-of-file assertions pass at import time

## Next Steps

**Plan 04 (Wave 2):** Add `get_hardship_flag_pure` + PROFILE filter in `lambda/handler.py`. This plan created the PROFILE data; Plan 04 wires the lookup helper.

**Plan 05 (Wave 3):** Add byte-exact test fixtures (`mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`) in `tests/conftest.py` and extend `tests/test_simulate_savings.py` with new persona parametrisations. Plan 03 created the billing data; Plan 05 locks the expected savings figures.

**Plan 06 (Wave 4):** CDK deploy ceremony — lift stack policy on `CustomerTariff`, deploy with 73-item seeder (auto-chunks to 3 BillingSeeder resources per existing chunking logic), verify smoke tests, reapply stack policy. Plan 03 modified the seed data; Plan 06 deploys it to AWS.

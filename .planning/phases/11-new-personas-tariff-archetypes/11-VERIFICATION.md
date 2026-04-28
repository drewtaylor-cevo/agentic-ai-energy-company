---
phase: 11-new-personas-tariff-archetypes
verified: 2026-04-28T09:00:00Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 11: New Personas & Tariff Archetypes Verification Report

**Phase Goal:** Extend the demo with 3 new personas (CUST-004 solar, CUST-005 EV, CUST-006 hardship) and 2 new tariff plans (SOL, EV-TOU), with all byte-exact savings locked and v2.0 invariants preserved.

**Verified:** 2026-04-28T09:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1   | Lookup of CUST-004 returns Solar Feed-in tariff with byte-exact savings locked in fixtures | ✓ VERIFIED | `mock_cust004_response` fixture: Green ECO $40.02, Cheapest SOL $76.03 — matches `test_cust004_byte_exact` PASS |
| 2   | Lookup of CUST-005 returns EV Time-of-Use tariff with byte-exact savings locked in fixtures | ✓ VERIFIED | `mock_cust005_response` fixture: Green ECO $35.00, Cheapest EV-TOU $84.00 — matches `test_cust005_byte_exact` PASS |
| 3   | `lambda/tariff_plans.json == infrastructure/seed_data/tariff_plans.json` and test passes | ✓ VERIFIED | `diff` silent (byte-equal), `test_tariff_plans_byte_equal` PASS |
| 4   | V2.0 persona savings remain byte-exact after dispatcher refactor | ✓ VERIFIED | Sarah $30.00/$55.00, Marcus $16.90/$30.98, Elena $14.00/$25.67 preserved — `test_flagship_persona_*` PASS, manual verification confirms dispatcher output |
| 5   | Customer with `hardship_flag: true` discoverable offline via `get_hardship_flag_pure` | ✓ VERIFIED | `test_hardship_persona_returns_true` PASS, returns `{hardship: True, customer_id: "CUST-006"}` |
| 6   | 73 items seeded (36 v2.0 + 36 new + 1 PROFILE) on deployed stack, SAV-03 live gate holds | ✓ VERIFIED | Per 11-06-SUMMARY: live smoke 12/12 PASS, AWS Lambda invocation Sarah $30/$55 byte-exact, DynamoDB scan count=73 post-backfill |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected    | Status | Details |
| -------- | ----------- | ------ | ------- |
| `lambda/tariff_plans.json` | 6-plan catalog with SOL+EV-TOU | ✓ VERIFIED | 6 plans present: STD, ECO, VAL, TOU, SOL, EV-TOU. SOL=solar_fit rate=0.23 fit_rate=0.08 green_score=80, EV-TOU=time_of_use peak_rate=0.40 offpeak_rate=0.08 green_score=30 |
| `infrastructure/seed_data/tariff_plans.json` | Byte-equal copy of lambda/ | ✓ VERIFIED | `diff` silent (byte-equal) |
| `tests/test_tariff_plans_byte_equal.py` | M1 mitigation gate | ✓ VERIFIED | 3 tests: byte-equal, structural-equal, 6-plan assertion — all PASS |
| `lambda/handler.py::simulate_savings_pure` | Dispatcher with 3 branches | ✓ VERIFIED | `plan_type` dispatcher present: time_of_use (L90-96), solar_fit (L99-106), default flat (L109) |
| `lambda/handler.py::get_hardship_flag_pure` | Pure helper with V5 gate | ✓ VERIFIED | Function exists L138-156, calls `_validate_customer_id` before DynamoDB `get_item` |
| `lambda/handler.py::get_billing_history` | PROFILE filter | ✓ VERIFIED | Line 176: `items = [i for i in items if i["month"] != "PROFILE"]` |
| `infrastructure/seed_data/billing_records.py` | 73 items: CUST004/005/006 + PROFILE | ✓ VERIFIED | ALL_RECORDS=73, DYNAMO_RECORDS=73, CUST004_RECORDS=12, CUST005_RECORDS=12, CUST006_RECORDS=12, PROFILE_ITEMS=1 |
| `tests/conftest.py` | 7 new fixtures for new personas | ✓ VERIFIED | `cust004_billing`, `cust005_billing`, `cust006_billing`, `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship` present |
| `tests/test_simulate_savings.py` | 22 tests (15 v2.0 + 7 new) | ✓ VERIFIED | 22 test functions present, all PASS |
| `tests/test_get_hardship_flag_pure.py` | 4 offline unit tests | ✓ VERIFIED | New file with 4 tests, all PASS |
| `tests/test_get_billing_history.py` | 11 tests (9 existing + 2 PROFILE filter) | ✓ VERIFIED | 11 tests present, all PASS including `test_profile_row_filtered_for_hardship_persona` |
| `tests/test_seeder_smoke.py` | Extended to 73-item + CUST-004/005/006 | ✓ VERIFIED | `test_table_has_73_items`, `test_cust004_has_12_months`, `test_cust005_has_12_months`, `test_cust006_has_12_months_plus_profile`, `test_cust006_profile_row_carries_hardship_flag` present |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| `simulate_savings_pure::projected_monthly_cost` | `plan['plan_type']` | Inline dispatcher | ✓ WIRED | Dispatcher reads `plan_type = plan.get("plan_type", "flat_rate")` and branches on `time_of_use`, `solar_fit`, default |
| `get_hardship_flag_pure` | `_validate_customer_id` | V5 input validation gate | ✓ WIRED | `_validate_customer_id(customer_id)` called at entry (L146), before any DynamoDB call |
| `get_billing_history` | PROFILE sentinel-SK filter | Python-level filter | ✓ WIRED | `items = [i for i in items if i["month"] != "PROFILE"]` present at L176, before sorted return |
| `tests/test_tariff_plans_byte_equal.py` | Both tariff_plans.json files | Binary read comparison | ✓ WIRED | Test opens both files in `'rb'` mode, asserts byte equality |
| `tests/test_simulate_savings.py::test_cust004_byte_exact` | `mock_cust004_response` fixture | Parametrized test assertion | ✓ WIRED | Test compares `simulate_savings_pure` output to fixture values within 0.01 tolerance |
| Plan 11-01 catalog | Plan 11-02 dispatcher | 6-plan catalog consumed by dispatcher | ✓ WIRED | Dispatcher branches route SOL (solar_fit) and EV-TOU (time_of_use) to correct formulas |
| Plan 11-03 persona records | Plan 11-02 dispatcher | Billing records with peak/offpeak/export fields | ✓ WIRED | CUST004_RECORDS carry `export_kwh`, CUST005_RECORDS carry `peak_kwh`+`offpeak_kwh`, dispatcher reads them |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `simulate_savings_pure` | `billing_history` | Passed as argument | Yes — test fixtures and DynamoDB query | ✓ FLOWING |
| `get_hardship_flag_pure` | `item` from DynamoDB | `table_client.get_item` | Yes — returns PROFILE row or empty | ✓ FLOWING |
| `test_cust004_byte_exact` | `cust004_billing` fixture | `CUST004_RECORDS` from billing_records.py | Yes — 12-month array with export_kwh | ✓ FLOWING |
| `test_tariff_plans_byte_equal` | tariff_plans.json contents | File read | Yes — 6-plan catalog | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Sarah byte-exact through dispatcher | `python3 -c "import importlib; h=importlib.import_module('lambda.handler'); ..."` | Green $30.00, Cheapest $55.00 | ✓ PASS |
| 6-plan catalog count | `python3 -c "import json; plans=json.load(open('lambda/tariff_plans.json')); print(len(plans))"` | 6 | ✓ PASS |
| 73-item seed count | `python3 -c "from infrastructure.seed_data.billing_records import ALL_RECORDS; print(len(ALL_RECORDS))"` | 73 | ✓ PASS |
| Tariff byte-equality | `diff lambda/tariff_plans.json infrastructure/seed_data/tariff_plans.json` | Silent (byte-equal) | ✓ PASS |
| Offline test suite | `pytest tests/test_simulate_savings.py tests/test_tariff_plans_byte_equal.py tests/test_get_hardship_flag_pure.py tests/test_get_billing_history.py -q` | 40 passed in 0.53s | ✓ PASS |
| Live smoke tests (per 11-06-SUMMARY) | `pytest -m smoke tests/test_seeder_smoke.py -v` | 12/12 PASS | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| DATA-04 | 11-03, 11-05, 11-06 | Seed Solar PV persona (CUST-004) with realistic 12-month billing profile | ✓ SATISFIED | `CUST004_RECORDS` exists with 12 items, `export_kwh` fields present, `test_cust004_byte_exact` PASS |
| DATA-05 | 11-03, 11-05, 11-06 | Seed EV persona (CUST-005) with realistic 12-month TOU billing profile | ✓ SATISFIED | `CUST005_RECORDS` exists with 12 items, `peak_kwh`+`offpeak_kwh` fields present (30/70 split), `test_cust005_byte_exact` PASS |
| DATA-06 | 11-03, 11-04, 11-06 | Mark one persona with `hardship_flag: true` in customer record | ✓ SATISFIED | `PROFILE_ITEMS` contains CUST-006 with `hardship_flag: True`, `test_hardship_persona_returns_true` PASS, live smoke confirms BOOL wire type |
| DATA-07 | 11-02, 11-03, 11-05 | New personas round-trip through `simulate_savings_pure` with byte-exact engineered savings figures locked in fixtures | ✓ SATISFIED | Fixtures lock CUST-004 ($40.02/$76.03), CUST-005 ($35.00/$84.00), CUST-006 ($12.00/$22.00), all byte-exact tests PASS, v2.0 figures preserved |
| REC-04 | 11-01 | Add Solar Feed-in tariff to `tariff_plans.json` (both locations) | ✓ SATISFIED | SOL plan present in both files, byte-equality test passes, solar_fit dispatcher branch present |
| REC-05 | 11-01 | Add EV Time-of-Use tariff to `tariff_plans.json` (both locations) | ✓ SATISFIED | EV-TOU plan present in both files, byte-equality test passes, time_of_use dispatcher branch routes EV-TOU correctly |

### Anti-Patterns Found

No critical anti-patterns detected. Code review (11-REVIEW.md) identified 3 warnings for future consideration:

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| lambda/handler.py | 90-96 | TOU dispatcher per-record fallback (latent bug on partial record population) | ⚠️ Warning | Currently no-op (uniform seed data), but future persona with mixed records could compute wrong projected cost |
| infrastructure/constructs/seeder.py | 55-67 | on_create-only seeder (unreliable phys-id replacement) | ⚠️ Warning | Manifested as 14-row deficit in live deploy; mitigated via manual backfill; future re-seeds at risk |
| lambda/handler.py | 81 | `current_plan_id` from earliest month not latest | ⚠️ Warning | Fragile against mid-year plan switches; currently no-op (all seed records have plan_id=STD) |

Code review also noted 5 info-level issues (stale docstrings, comment drift) — all non-blocking for verification.

### Human Verification Required

None. All must-haves are programmatically verifiable via pytest or file inspection.

## Verification Details

### Plan 11-01: Tariff Catalog Extension + M1 Mitigation

**Must-haves verified:**
- ✓ 6-plan catalog (STD, ECO, VAL, TOU, SOL, EV-TOU) in both locations
- ✓ Byte-equal: `diff` silent
- ✓ SOL: plan_type='solar_fit', rate=0.23, fit_rate=0.08, green_score=80
- ✓ EV-TOU: plan_type='time_of_use', peak_rate=0.40, offpeak_rate=0.08, green_score=30
- ✓ v2.0 plans (STD/ECO/VAL/TOU) schema byte-frozen — grep confirms no `fit_rate`, `peak_rate`, `offpeak_rate` on v2.0 plans
- ✓ `test_tariff_plans_byte_equal.py` exists with 3 tests, all PASS

**Evidence:**
```bash
$ python3 -c "import json; plans=json.load(open('lambda/tariff_plans.json')); print(f'Plans: {len(plans)}'); print('IDs:', sorted([p['plan_id'] for p in plans]))"
Plans: 6
IDs: ['ECO', 'EV-TOU', 'SOL', 'STD', 'TOU', 'VAL']

$ diff lambda/tariff_plans.json infrastructure/seed_data/tariff_plans.json
(silent — byte-equal)

$ pytest tests/test_tariff_plans_byte_equal.py -v
test_tariff_plans_byte_equal PASSED
test_tariff_plans_structural_equal PASSED
test_catalog_has_6_plans PASSED
3 passed in 0.05s
```

### Plan 11-02: Dispatcher Implementation

**Must-haves verified:**
- ✓ `simulate_savings_pure` dispatches on plan_type with 3 branches
- ✓ v2.0 personas (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67) remain byte-exact
- ✓ TOU math defaults to 100% peak for v2.0 records (validated via `test_legacy_tou_plan_uses_100pct_peak_fallback`)
- ✓ Solar math defaults to export=0 for v2.0 records (validated via negative witness tests)

**Evidence:**
```bash
$ grep -c 'plan_type = plan.get("plan_type", "flat_rate")' lambda/handler.py
1

$ grep -c 'if plan_type == "time_of_use":' lambda/handler.py
1

$ grep -c 'if plan_type == "solar_fit":' lambda/handler.py
1

$ python3 -c "import importlib; h=importlib.import_module('lambda.handler'); p=__import__('json').load(open('lambda/tariff_plans.json')); b=[{'customer_id':'CUST-001','month':'2025-04','usage_kwh':500,'cost_usd':193.48,'plan_id':'STD'}]*12; r=h.simulate_savings_pure(b,p); print(f\"Sarah: Green \${r['green']['saving_monthly']:.2f}, Cheapest \${r['cheapest']['saving_monthly']:.2f}\")"
Sarah: Green $30.00, Cheapest $55.00

$ pytest tests/test_simulate_savings.py::test_flagship_persona_green_saving tests/test_simulate_savings.py::test_flagship_persona_cheapest_saving -v
2 passed in 0.03s
```

### Plan 11-03: Seed Data Extension

**Must-haves verified:**
- ✓ `_record()` accepts optional kwargs (export_kwh, peak_kwh, offpeak_kwh)
- ✓ `_profile_item()` helper exists
- ✓ CUST004_RECORDS, CUST005_RECORDS, CUST006_RECORDS each contain exactly 12 records
- ✓ PROFILE_ITEMS contains exactly 1 entry
- ✓ ALL_RECORDS and DYNAMO_RECORDS each contain exactly 73 items
- ✓ `to_dynamo()` emits optional attributes only when non-default; PROFILE row emits hardship_flag as BOOL
- ✓ v2.0 persona arrays (Sarah/Marcus/Elena) byte-frozen — untouched by this plan

**Evidence:**
```bash
$ python3 -c "from infrastructure.seed_data.billing_records import ALL_RECORDS, DYNAMO_RECORDS, CUST004_RECORDS, CUST005_RECORDS, CUST006_RECORDS, PROFILE_ITEMS; print(f'ALL_RECORDS: {len(ALL_RECORDS)}'); print(f'DYNAMO_RECORDS: {len(DYNAMO_RECORDS)}'); print(f'CUST004: {len(CUST004_RECORDS)}'); print(f'CUST005: {len(CUST005_RECORDS)}'); print(f'CUST006: {len(CUST006_RECORDS)}'); print(f'PROFILE_ITEMS: {len(PROFILE_ITEMS)}')"
ALL_RECORDS: 73
DYNAMO_RECORDS: 73
CUST004: 12
CUST005: 12
CUST006: 12
PROFILE_ITEMS: 1
```

### Plan 11-04: Hardship Helper + PROFILE Filter

**Must-haves verified:**
- ✓ `get_hardship_flag_pure(customer_id, table_client)` returns `{hardship: bool, customer_id: str}`
- ✓ `get_hardship_flag_pure` validates customer_id via `_validate_customer_id` BEFORE any DynamoDB call
- ✓ Missing PROFILE row returns `{hardship: False, ...}` — no error
- ✓ `get_billing_history` filters PROFILE sentinel-SK rows before returning
- ✓ `get_billing_history` returns exactly 12 rows for CUST-006 (PROFILE filtered)

**Evidence:**
```bash
$ grep -c "def get_hardship_flag_pure" lambda/handler.py
1

$ grep -c 'items = \[i for i in items if i\["month"\] != "PROFILE"\]' lambda/handler.py
1

$ pytest tests/test_get_hardship_flag_pure.py -v
test_hardship_persona_returns_true PASSED
test_nonhardship_persona_returns_false_when_profile_missing PASSED
test_malformed_customer_id_rejected PASSED
test_profile_item_with_hardship_false_returns_false PASSED
4 passed in 0.02s

$ pytest tests/test_get_billing_history.py::test_profile_row_filtered_for_hardship_persona -v
1 passed in 0.27s
```

### Plan 11-05: Byte-Exact Test Fixtures

**Must-haves verified:**
- ✓ `mock_cust004_response` fixture locks byte-exact values: Green=ECO $40.02/$480.24, Cheapest=SOL $76.03/$912.36
- ✓ `mock_cust005_response` fixture locks byte-exact values: Green=ECO $35.00/$420.00, Cheapest=EV-TOU $84.00/$1008.00
- ✓ `mock_cust006_response` fixture locks byte-exact values: Green=ECO $12.00/$144.00, Cheapest=VAL $22.00/$264.00
- ✓ `mock_cust006_hardship` fixture = `{hardship: True, customer_id: 'CUST-006'}`
- ✓ `cust004_billing` / `cust005_billing` / `cust006_billing` fixtures import persona arrays from billing_records
- ✓ `simulate_savings_pure` produces those EXACT byte-exact values when fed the persona billing arrays against the 6-plan catalog

**Evidence:**
```bash
$ grep -A 20 "def mock_cust004_response" tests/conftest.py | grep "saving_monthly"
            "saving_monthly": 40.02,
            "saving_monthly": 76.03,

$ pytest tests/test_simulate_savings.py::test_cust004_byte_exact tests/test_simulate_savings.py::test_cust005_byte_exact tests/test_simulate_savings.py::test_cust006_byte_exact -v
test_cust004_byte_exact PASSED
test_cust005_byte_exact PASSED
test_cust006_byte_exact PASSED
3 passed in 0.03s
```

**Integration fix noted:** Plan 11-05 execution surfaced a solar_fit formula mismatch (dispatcher read `net_kwh` instead of gross `avg_kwh`). Fix landed in combined `feat(11-04,11-05)` commit. All byte-exact tests pass post-fix.

### Plan 11-06: Live Deploy Ceremony

**Must-haves verified:**
- ✓ `tests/test_seeder_smoke.py` count assertion is 73 (not 36)
- ✓ `tests/test_seeder_smoke.py` asserts CUST-004 has 12 month rows, CUST-005 has 12 month rows, CUST-006 has 12 month rows + 1 PROFILE row
- ✓ `tests/test_seeder_smoke.py` asserts CUST-006 PROFILE row has hardship_flag as BOOL true
- ✓ Live smoke: DynamoDB scan count = 73 (per 11-06-SUMMARY post-backfill)
- ✓ Live smoke: CUST-001 savings Lambda invocation returns Sarah $30/$55 (SAV-03 live gate held)

**Evidence from 11-06-SUMMARY:**
- Live deploy ceremony completed: stack-policy LIFT → DEPLOY → REAPPLY → VERIFY
- Post-deploy anomaly: 59 items initially (14-row seeder deficit), backfilled to 73 via direct `aws dynamodb batch-write-item`
- Live smoke tests: 12/12 PASS
- SAV-03 live gate: `aws lambda invoke --function-name tariff-tools {"customer_id":"CUST-001"}` returned Green ECO $30.00, Cheapest VAL $55.00 — byte-exact
- Stack policy post-REAPPLY: byte-equal to foundation-freeze.json (silent diff)
- Termination protection re-enabled: `true`

## Self-Check: PASSED

All claimed artifacts exist, all patterns present, all offline tests green (40/40 core Phase 11 tests), live smoke tests green (12/12), no regressions.

**Verification Status Summary:**
- Observable truths: 6/6 VERIFIED
- Required artifacts: 12/12 VERIFIED
- Key links: 7/7 WIRED
- Data-flow traces: 4/4 FLOWING
- Behavioral spot-checks: 6/6 PASS
- Requirements coverage: 6/6 SATISFIED
- Anti-patterns: 0 critical, 3 warnings (documented, non-blocking)
- Human verification: 0 items (all programmatically verifiable)

---

*Verified: 2026-04-28T09:00:00Z*
*Verifier: Claude (gsd-verifier)*

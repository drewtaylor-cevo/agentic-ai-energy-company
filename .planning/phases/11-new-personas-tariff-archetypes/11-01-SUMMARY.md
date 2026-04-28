---
phase: 11-new-personas-tariff-archetypes
plan: 01
subsystem: tariff-catalog
tags: [tariff-catalog, byte-equality, m1-mitigation, tdd, phase-11]
completed_date: 2026-04-28T02:40:07Z
duration_seconds: 95
requirements: [REC-04, REC-05]
dependency_graph:
  requires: []
  provides:
    - 6-plan tariff catalog (STD/ECO/VAL/TOU/SOL/EV-TOU)
    - byte-equality test gate (M1 mitigation)
  affects:
    - lambda/tariff_plans.json
    - infrastructure/seed_data/tariff_plans.json
    - tests/test_tariff_plans_byte_equal.py
tech_stack:
  added: []
  patterns:
    - TDD red-green-refactor cycle
    - byte-equality gate via pytest
    - source-of-truth duplication with automated drift detection
key_files:
  created:
    - tests/test_tariff_plans_byte_equal.py
  modified:
    - lambda/tariff_plans.json
    - infrastructure/seed_data/tariff_plans.json
decisions:
  - "SOL plan_type is 'solar_fit' (not 'green_premium') with green_score=80 (below ECO's 100) so ECO continues to win Green for all personas and SOL only competes on Cheapest — prevents both tracks showing same plan with same saving"
  - "EV-TOU declared as plan_type='time_of_use' with asymmetric peak_rate=0.40 / offpeak_rate=0.08 — wins Cheapest on 70% off-peak usage curves"
  - "v2.0 plans (STD/ECO/VAL/TOU) schema byte-frozen — no new fields (fit_rate, peak_rate, offpeak_rate) added to existing plans per D-15"
  - "Byte-equality test written FIRST (TDD RED) before catalog modification — test_catalog_has_6_plans failed against 4-plan catalog, then passed after adding SOL + EV-TOU"
  - "Locked rates sourced from target_equation_solver_v2.py: SOL rate=0.23, fit_rate=0.08; EV-TOU peak=0.40, offpeak=0.08"
metrics:
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
  commits: 2
  tests_added: 3
---

# Phase 11 Plan 01: Extend Tariff Catalog + Byte-Equality Gate Summary

## One-Liner

Tariff catalog extended from 4 to 6 plans (added SOL solar_fit + EV-TOU time_of_use) with byte-equality gate installed to prevent M1 drift between lambda/ and seed_data/ copies.

## What Was Built

Extended the tariff catalog from 4 plans (STD/ECO/VAL/TOU) to 6 plans by adding:

1. **SOL (Solar Feed-in)**: `plan_type="solar_fit"`, `rate_per_kwh=0.23`, `fit_rate=0.08`, `green_score=80`
   - Below ECO's green_score (100) so ECO continues to win Green track
   - SOL competes only on Cheapest track for solar personas
   - New optional `fit_rate` field for solar export credit calculation

2. **EV-TOU (EV Drive TOU)**: `plan_type="time_of_use"`, `rate_per_kwh=0.40`, `peak_rate=0.40`, `offpeak_rate=0.08`, `green_score=30`
   - Asymmetric TOU rates for EV charging patterns (30% peak / 70% off-peak)
   - New optional `peak_rate` and `offpeak_rate` fields

**M1 Mitigation**: Installed `tests/test_tariff_plans_byte_equal.py` with 3 tests:
- `test_tariff_plans_byte_equal`: asserts byte-level equality between `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json`
- `test_tariff_plans_structural_equal`: asserts JSON parse-equal (defensive against whitespace drift)
- `test_catalog_has_6_plans`: asserts catalog contains exactly STD, ECO, VAL, TOU, SOL, EV-TOU

**TDD Discipline**: Test written FIRST (RED state with 4-plan catalog failing the 6-plan assertion), then catalog extended to make all tests pass (GREEN state).

## Why This Matters

**Unlocks downstream Phase 11 plans**: CUST-004 (solar) and CUST-005 (EV) personas in subsequent plans require SOL and EV-TOU to compute differentiated Cheapest recommendations. Without these plans, new personas would fall back to VAL for Cheapest, producing identical savings figures across different usage profiles.

**Closes pre-existing M1 gap**: Before this plan, `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json` were manually kept in sync with no automated drift detection. Any single-location edit would cause DynamoDB seeder and Tools Lambda to disagree on the catalog. The byte-equality test now gates CI — any commit that touches one file without the other fails pytest.

**Preserves v2.0 SAV-03 invariant**: Existing STD/ECO/VAL/TOU plan schemas are byte-frozen (no new fields added). New optional fields (`fit_rate`, `peak_rate`, `offpeak_rate`) appear only on SOL and EV-TOU. Existing simulate_savings_pure flat-rate path for v2.0 personas (Sarah/Marcus/Elena) reads only `rate_per_kwh` + `daily_supply_charge` — unchanged, so byte-exact savings preserved ($30/$55, $16.90/$30.98, $14.00/$25.67).

## Tests Added

### Unit Tests (Offline)

**`tests/test_tariff_plans_byte_equal.py`** (NEW — 3 tests):
- `test_tariff_plans_byte_equal`: byte-level comparison via `open(..., 'rb').read()`
- `test_tariff_plans_structural_equal`: JSON parse comparison (defensive)
- `test_catalog_has_6_plans`: set assertion on `plan_id` values

All 3 tests pass after catalog extension. The 6-plan test was RED before extension (intentional TDD flow).

### Verification Commands Run

```bash
# Byte-equality between files (silent = success)
diff lambda/tariff_plans.json infrastructure/seed_data/tariff_plans.json

# Plan count verification
python3 -c "import json; plans=json.load(open('lambda/tariff_plans.json')); print(len(plans))"
# → 6

# v2.0 schema freeze verification (no fit_rate/peak_rate/offpeak_rate on STD/ECO/VAL/TOU)
python3 -c "import json; [print(f\"{p['plan_id']:8} fit={'Y' if 'fit_rate' in p else 'N'} peak={'Y' if 'peak_rate' in p else 'N'} off={'Y' if 'offpeak_rate' in p else 'N'}\") for p in json.load(open('lambda/tariff_plans.json'))]"
# → STD/ECO/VAL/TOU all N/N/N; SOL Y/N/N; EV-TOU N/Y/Y

# Green state confirmation
pytest tests/test_tariff_plans_byte_equal.py -v
# → 3 passed in 0.02s
```

## Deviations from Plan

None. Plan executed exactly as written. Both tasks completed atomically with TDD discipline (RED commit → GREEN commit).

## Known Stubs

None. This plan is pure catalog data — no runtime code, no UI, no stub placeholders.

## Threat Flags

None. No new trust boundaries introduced. Tariff catalog is static configuration; no network endpoints, no auth changes, no schema migrations on live data.

## Self-Check: PASSED

**Created files exist:**
```bash
[ -f "tests/test_tariff_plans_byte_equal.py" ] && echo "FOUND"
# → FOUND
```

**Modified files contain expected content:**
```bash
grep -q '"plan_id": "SOL"' lambda/tariff_plans.json && echo "FOUND SOL"
grep -q '"plan_id": "EV-TOU"' lambda/tariff_plans.json && echo "FOUND EV-TOU"
# → FOUND SOL
# → FOUND EV-TOU
```

**Commits exist:**
```bash
git log --oneline --all | grep -q "91317c8" && echo "FOUND: 91317c8 (TDD RED)"
git log --oneline --all | grep -q "0f9444a" && echo "FOUND: 0f9444a (TDD GREEN)"
# → FOUND: 91317c8 (TDD RED)
# → FOUND: 0f9444a (TDD GREEN)
```

**Byte-equality preserved:**
```bash
diff lambda/tariff_plans.json infrastructure/seed_data/tariff_plans.json
# → (silent = byte-equal)
```

All checks PASSED.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1.1 (TDD RED) | `91317c8` | test(11-01): add failing test for 6-plan catalog |
| 1.2 (TDD GREEN) | `0f9444a` | feat(11-01): extend tariff catalog to 6 plans (STD/ECO/VAL/TOU/SOL/EV-TOU) |

## What's Next

**Plan 11-02**: Extend `simulate_savings_pure` with `plan_type` dispatcher (inline if-branch inside `projected_monthly_cost` closure) to compute TOU and solar_fit math paths. Add new personas (CUST-004 solar, CUST-005 EV, CUST-006 hardship) with engineered billing arrays. Install PROFILE SK row for hardship_flag. Extend seeder to 73 items (3 chunks). Verify v2.0 SAV-03 byte-exact preservation via existing test suite.

The 6-plan catalog established here is the foundation for all downstream persona math and demo surfaces.

---

*Executed: 2026-04-28T02:39:32Z → 2026-04-28T02:40:07Z (95 seconds)*
*Wave: 1 | Type: execute | TDD: yes | Autonomous: yes*

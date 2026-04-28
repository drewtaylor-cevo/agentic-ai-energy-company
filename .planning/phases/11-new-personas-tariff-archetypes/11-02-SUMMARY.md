---
phase: 11-new-personas-tariff-archetypes
plan: 02
subsystem: backend-tools-lambda
tags: [sav-03, dispatcher, tou, solar, byte-exact, tdd]
requires: [DATA-07]
provides:
  - simulate_savings_pure plan_type dispatcher (3 branches)
  - TOU peak/offpeak math with 100% peak fallback
  - Solar net/export math with export=0 fallback
affects:
  - lambda/handler.py (simulate_savings_pure extended)
  - tests/test_simulate_savings.py (4 witness tests added)
tech_stack:
  added: []
  patterns:
    - inline dispatcher within closure (D-12)
    - .get() fallback chains for backward compatibility
    - pre-computed supply constant for mathematical equivalence
key_files:
  created: []
  modified:
    - lambda/handler.py (dispatcher: 18 lines added to projected_monthly_cost closure)
    - tests/test_simulate_savings.py (4 witness tests: 50 lines)
decisions:
  - D-12: Inline dispatcher inside projected_monthly_cost closure (minimum diff, Chesterton's-Fence)
  - D-14: Legacy TOU fallback to 100% peak when peak_kwh/offpeak_kwh absent
  - D-01/D-04: Solar fallback to export=0 when export_kwh absent
  - Supply pre-computed once as constant (mathematically equivalent to inline expression)
metrics:
  duration_minutes: ~8
  tasks_completed: 2
  tasks_total: 2
  files_modified: 2
  lines_added: 68
  lines_removed: 4
  tests_added: 4
  tests_passing: 15
  completed_date: 2026-04-28
---

# Phase 11 Plan 02: Tariff Dispatcher Implementation

**One-liner:** Plan_type dispatcher with 3 branches (flat/TOU/solar) inside simulate_savings_pure, preserving v2.0 byte-exact savings ($30/$55, $16.90/$30.98, $14.00/$25.67) while enabling CUST-004/005 archetype math.

## What Was Built

Extended `simulate_savings_pure` in `lambda/handler.py` with an inline `plan_type` dispatcher inside the `projected_monthly_cost` closure. Three branches:

1. **`time_of_use`**: Peak/offpeak rate math with fallback defaults for v2.0 records (100% peak when `peak_kwh` absent, D-14)
2. **`solar_fit`**: Net consumption minus export credit math with fallback (export=0 when `export_kwh` absent, D-01/D-04)  
3. **Default (flat_rate/green_premium)**: Byte-exact preservation of v2.0 formula using pre-computed `supply` constant

Added 4 witness tests in `tests/test_simulate_savings.py`:
- `test_sarah_byte_exact_against_6plan_catalog`: Proves flat-path preservation through refactor
- `test_v2_personas_cheapest_stays_val_under_6plan_catalog`: Negative witness that SOL/EV-TOU fallback math doesn't accidentally beat VAL
- `test_legacy_tou_plan_uses_100pct_peak_fallback`: D-14 compatibility test
- `test_dispatcher_routes_tou_plan`: Positive routing test with explicit peak/offpeak split

## Why This Approach

**SAV-03 extension point:** All new tariff arithmetic (TOU peak/offpeak, solar net-metering) must live in Python on Tools Lambda, never in the LLM. The dispatcher is the minimum-diff extension that adds capability without restructuring.

**Chesterton's-Fence (C7):** The existing `avg_kwh` computation and green/cheapest selection logic are load-bearing for byte-exact preservation. Inline dispatcher inside the closure touches only the cost-projection step, leaving all other logic unchanged.

**Fallback-driven backward compatibility:** v2.0 records lack `peak_kwh`, `offpeak_kwh`, `export_kwh`, `net_kwh` fields. Dispatcher branches use `.get()` chains that degrade gracefully: TOU defaults to 100% peak (produces same result as flat formula), solar defaults to export=0 (net = usage).

## Deviations from Plan

None. Plan executed exactly as written.

## Test Evidence

**All 15 tests pass:**
- 12 pre-existing v2.0 SAV-03 tests (unchanged, still green)
- 3 new witness tests (flat preservation, VAL stability, TOU fallback)
- 1 new dispatcher routing test

**Byte-exact preservation verified:**
```python
# Sarah Chen against 6-plan catalog
python3 -c "import importlib; h=importlib.import_module('lambda.handler'); \
  p=__import__('json').load(open('lambda/tariff_plans.json')); \
  b=[{'customer_id':'CUST-001','month':'2025-04','usage_kwh':500,'cost_usd':193.48,'plan_id':'STD'}]*12; \
  r=h.simulate_savings_pure(b,p); \
  print(r['green']['saving_monthly'], r['cheapest']['saving_monthly'])"
# Output: 30.0 55.0
```

**Acceptance criteria met:**
- ✅ `grep -c 'plan_type = plan.get("plan_type", "flat_rate")' lambda/handler.py` → 1
- ✅ `grep -c 'if plan_type == "time_of_use":' lambda/handler.py` → 1  
- ✅ `grep -c 'if plan_type == "solar_fit":' lambda/handler.py` → 1
- ✅ `grep -c 'net_kwh_avg \* sol_rate - export_kwh_avg \* fit_rate' lambda/handler.py` → 1
- ✅ `grep -c 'peak_kwh_avg \* peak_rate + offpeak_kwh_avg \* offpeak_rate' lambda/handler.py` → 1
- ✅ `grep -c 'return avg_kwh \* float(plan\["rate_per_kwh"\]) + supply' lambda/handler.py` → 1
- ✅ All v2.0 SAV-03 tests pass (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67)

## Known Stubs

None. This is a pure math extension; no UI rendering or data wiring involved.

## Threat Flags

None. All threats in the plan's threat model were mitigated:
- **T-11-04 (SAV-03 byte-exact regression):** Supply pre-computed as constant, default branch mathematically equivalent to v2.0 formula, byte-exact evidence confirmed
- **T-11-05 (KeyError on missing fields):** All new branches use `.get()` with fallback defaults
- **T-11-06 (dispatcher bypass):** `plan_type` defaults to `"flat_rate"` when absent

## Integration Notes

**Downstream impact:**
- **Plan 03 (persona records):** Will add CUST-004/005/006 billing records with `peak_kwh`, `offpeak_kwh`, `export_kwh`, `net_kwh` fields. Dispatcher already ready to consume them.
- **Plan 05 (parametrized tests):** Will add positive byte-exact tests for CUST-004 (solar) and CUST-005 (EV-TOU) using the new dispatcher branches. Foundation laid here.

**No changes required elsewhere:** Agent code, API Lambda, UI, and other stacks untouched. Tools Lambda is the only surface modified.

## Next Steps

1. **Plan 03:** Seed CUST-004/005/006 persona records (12 months each + PROFILE for CUST-006)
2. **Plan 04:** Extend tariff_plans.json byte-equality test, add get_hardship_flag_pure helper
3. **Plan 05:** Add parametrized tests proving CUST-004/005/006 byte-exact savings against new dispatcher branches

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 2.1 + 2.2 | d71d15b | feat(11-02): extend simulate_savings_pure with plan_type dispatcher |

## Self-Check: PASSED

**Files created:** None (witness tests added to existing file)

**Files modified:**
```bash
[ -f "/Users/drewtaylor/Documents/Cevo/Customer-Tariff/lambda/handler.py" ] && echo "✅ lambda/handler.py"
[ -f "/Users/drewtaylor/Documents/Cevo/Customer-Tariff/tests/test_simulate_savings.py" ] && echo "✅ tests/test_simulate_savings.py"
```
Output:
```
✅ lambda/handler.py
✅ tests/test_simulate_savings.py
```

**Commits exist:**
```bash
git log --oneline --all | grep -q "d71d15b" && echo "✅ d71d15b"
```
Output:
```
✅ d71d15b
```

**Dispatcher pattern installed:**
```bash
grep -q 'plan_type = plan.get("plan_type", "flat_rate")' lambda/handler.py && echo "✅ Dispatcher installed"
grep -q 'if plan_type == "time_of_use":' lambda/handler.py && echo "✅ TOU branch present"
grep -q 'if plan_type == "solar_fit":' lambda/handler.py && echo "✅ Solar branch present"
```
Output:
```
✅ Dispatcher installed
✅ TOU branch present
✅ Solar branch present
```

---

*Plan 11-02 complete. Ready for Plan 03 (persona records).*

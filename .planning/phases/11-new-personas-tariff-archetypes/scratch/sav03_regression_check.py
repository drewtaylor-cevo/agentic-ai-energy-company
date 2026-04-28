"""SAV-03 byte-exact regression check — v2.0 personas against 6-plan catalog.

v2.0 LOCKED (tests/conftest.py):
  Sarah (CUST-001, avg 500):  Green ECO $30.00/mo, Cheapest VAL $55.00/mo
  Marcus (CUST-002, avg 282): Green ECO $16.90/mo, Cheapest VAL $30.98/mo
  Elena (CUST-003, avg 233):  Green ECO $14.00/mo, Cheapest VAL $25.67/mo

Must remain byte-exact after:
  - Refactor: simulate_savings_pure dispatches on plan_type (D-12)
  - New plans: SOL (sol_rate=0.23, fit_rate=0.08) + EV-TOU (peak=0.40, off=0.08)
  - Defaults: no export_kwh on v2.0 records -> SOL treats export=0
              no peak_kwh/offpeak_kwh on v2.0 records -> EV-TOU defaults to 100% peak
"""

STD_RATE = 0.32
ECO_RATE = 0.26
VAL_RATE = 0.21
TOU_RATE = 0.36
SOL_RATE = 0.23
FIT_RATE = 0.08
EVTOU_PEAK_RATE = 0.40
EVTOU_OFFPEAK_RATE = 0.08
SUPPLY_MONTHLY = 1.10 * 30.44  # 33.484

def check(customer, avg_kwh, expected_green, expected_cheapest):
    # Currently-on STD (all v2.0 personas) — STD is current plan so excluded from candidates
    # Compute all alternative plan projected costs
    proj_std = avg_kwh * STD_RATE + SUPPLY_MONTHLY
    proj_eco = avg_kwh * ECO_RATE + SUPPLY_MONTHLY
    proj_val = avg_kwh * VAL_RATE + SUPPLY_MONTHLY
    proj_tou = avg_kwh * TOU_RATE + SUPPLY_MONTHLY  # TOU defaults to flat (D-14)
    # SOL default: net=usage (back-compat D-01), export=0
    proj_sol = avg_kwh * SOL_RATE - 0 * FIT_RATE + SUPPLY_MONTHLY
    # EV-TOU default: 100% peak fallback (D-05/D-12)
    proj_evtou = avg_kwh * EVTOU_PEAK_RATE + SUPPLY_MONTHLY

    # Green: max(green_score) over plan_type=green_premium. Only ECO qualifies.
    green_candidates = ["ECO"]
    proj_green = proj_eco

    # Cheapest: min over all non-STD plans
    candidates = {
        "ECO": proj_eco, "VAL": proj_val, "TOU": proj_tou,
        "SOL": proj_sol, "EV-TOU": proj_evtou,
    }
    cheapest_plan = min(candidates, key=candidates.get)

    saving_green = round(proj_std - proj_green, 2)
    saving_cheapest = round(proj_std - candidates[cheapest_plan], 2)

    green_ok = f"Green: ECO ${saving_green:.2f}  (expected ${expected_green:.2f}) {'✓' if saving_green == expected_green else '✗ REGRESSION'}"
    cheap_ok = f"Cheapest: {cheapest_plan} ${saving_cheapest:.2f}  (expected VAL ${expected_cheapest:.2f}) {'✓' if cheapest_plan == 'VAL' and saving_cheapest == expected_cheapest else '✗ REGRESSION'}"

    print(f"\n{customer} (avg {avg_kwh} kWh):")
    print(f"  Projected costs: STD={proj_std:.4f} ECO={proj_eco:.4f} VAL={proj_val:.4f} TOU={proj_tou:.4f} SOL={proj_sol:.4f} EV-TOU={proj_evtou:.4f}")
    print(f"  {green_ok}")
    print(f"  {cheap_ok}")


check("Sarah CUST-001", 500.0, 30.00, 55.00)
check("Marcus CUST-002", 281.6666666667, 16.90, 30.98)  # Elena's avg: verified = 281.67
check("Elena CUST-003", 233.3333333333, 14.00, 25.67)

"""Target-equation solver for CUST-004 (solar) + CUST-005 (EV-TOU) + CUST-006 (hardship).

Phase 11 D-19: researcher produces locked constants from engineered targets.

Baselines (locked in tariff_plans.json and billing_records.py):
  STD_RATE   = 0.32 /kWh  (NOT 0.34 as CONTEXT assumed — confirmed from lambda/tariff_plans.json)
  ECO_RATE   = 0.26 /kWh  (Green — green_premium, green_score=100)
  VAL_RATE   = 0.21 /kWh  (Cheapest for v2.0 personas)
  TOU_RATE   = 0.36 /kWh  (legacy; falls back to flat under D-14)
  SUPPLY     = 1.10 /day
  DAYS_PM    = 30.44

Savings formula (current, flat_rate):
  proj_cost(plan) = avg_kwh * rate + supply * 30.44
  saving(plan)    = proj_cost(STD) - proj_cost(plan)

For solar-fit (D-12 branch):
  proj_cost(SOL) = net_kwh_avg * sol_rate - export_kwh_avg * fit_rate + supply * 30.44

For time_of_use (D-12 branch):
  proj_cost(EV-TOU) = peak_kwh_avg * peak_rate + offpeak_kwh_avg * offpeak_rate + supply * 30.44

Baselines for solar/EV personas (D-04): STD baseline uses `usage_kwh` (net_kwh for solar)
and does NOT credit FiT. That's what "STD is unmetered for solar" means.
  baseline_cost = net_kwh_avg * STD_RATE + supply * 30.44  (solar, no fit)
  baseline_cost = total_kwh_avg * STD_RATE + supply * 30.44  (EV-TOU, total = peak+offpeak)

Engineered targets (D-02):
  CUST-004 Green ~$40/mo, Cheapest ~$70/mo
  CUST-005 Green ~$35/mo, Cheapest ~$60/mo
  CUST-006 no target; savings pop out of math against 6-plan catalog

Locked 4-decimal rates chosen for clean byte-exact pytest invariants.
"""
from typing import List, Tuple

STD_RATE = 0.32
ECO_RATE = 0.26
VAL_RATE = 0.21
TOU_RATE = 0.36
SUPPLY = 1.10
DAYS_PM = 30.44
SUPPLY_MONTHLY = SUPPLY * DAYS_PM  # 33.484


def projected_flat(avg_kwh: float, rate: float) -> float:
    return avg_kwh * rate + SUPPLY_MONTHLY


def projected_tou(peak_kwh: float, offpeak_kwh: float, peak_rate: float, offpeak_rate: float) -> float:
    return peak_kwh * peak_rate + offpeak_kwh * offpeak_rate + SUPPLY_MONTHLY


def projected_sol(net_kwh: float, export_kwh: float, sol_rate: float, fit_rate: float) -> float:
    return net_kwh * sol_rate - export_kwh * fit_rate + SUPPLY_MONTHLY


# =============================================================================
# CUST-004 SOLAR — engineer targets: Green ~$40, Cheapest ~$70
# =============================================================================
# Strategy:
#   net_kwh_avg = household net consumption (after self-consumption)
#   export_kwh_avg = exported to grid
#   Green is ECO @ 0.26 (flat) — "Green" because ECO has green_score=100
#     Note: ECO is flat_rate, doesn't credit export. Same story holds: STD baseline
#     doesn't credit export either, so ECO's saving over STD is just the rate delta.
#     saving_green = net_kwh_avg * (STD_RATE - ECO_RATE) = net_kwh_avg * 0.06
#     For $40: net_kwh_avg = 40 / 0.06 = 666.67 -> pick 667 kWh
#   Or we can make SOL win Green (D-03: SOL green_score=120 > ECO 100)
#     saving_green_sol = net_kwh_avg * (STD_RATE - SOL_RATE) + export_kwh_avg * fit_rate
#   Given D-03 says "SOL is declared plan_type=green_premium with green_score>100 so
#   SOL wins Green for solar personas" — CUST-004 Green = SOL.
#
# Locked: SOL is Green for CUST-004. ECO loses on green_score (100 < SOL's 120).
#   saving_green  = net_avg * (STD - SOL_rate) + export_avg * fit_rate  = $40
#   saving_cheap  = min over catalog. Must verify SOL < VAL < ECO < TOU/EV-TOU.
#
# Chose clean 4-decimal numbers. Let's parameterize:
#   net_avg=500, export_avg=250 (realistic 6.6kW residential solar: ~900 kWh generation,
#   ~600 self-consumed of which say 400 appears as reduced net + 200 exported; tweak)
#
#   Target equations:
#     saving_green_sol = 500 * (0.32 - sol_rate) + 250 * fit_rate = 40
#     saving_cheap_sol = saving_green_sol  (SOL is BOTH green and cheapest — but D-03 says
#       min(projected_cost) over all candidates; need to check)
#
# Note on Cheapest for solar: solar FiT + reduced rate should beat VAL (0.21 flat) on a
# consumer with significant export. We want Cheapest ~$70. That means SOL's proj cost
# is $70 below STD's baseline.
#     baseline_std = 500 * 0.32 + 33.484 = 160 + 33.484 = 193.484
#     proj_sol     = 500 * sol_rate - 250 * fit_rate + 33.484
#     saving_sol   = 193.484 - proj_sol = 500*(0.32-sol_rate) + 250*fit_rate
#
# SOL cannot be both Green ($40) AND Cheapest ($70) — different numbers, same plan.
# The savings number attached to a plan is unique (it's projected cost delta).
# So either SOL wins both tracks (with a single saving figure), OR one of them is
# a different plan.
#
# Reading D-03 more carefully: Green is max(green_score) over green_premium plans.
# If SOL has green_score=120, ECO has 100, SOL wins Green IFF SOL is green_premium.
# Cheapest is min(projected_cost) over all candidates. For solar persona, SOL's
# cost CAN be lowest (with FiT credit), so SOL wins Cheapest too.
#
# If SOL wins BOTH, then the two saving figures are IDENTICAL — the Green card and
# Cheapest card show the same plan with the same saving. That breaks the "two cards,
# two stories" demo visual.
#
# RESOLUTION: CUST-004's Green track picks ECO (standard green_premium plan), Cheapest
# picks SOL. This happens naturally if:
#   - SOL has plan_type != "green_premium" (e.g. plan_type="solar_fit")
#   - ECO remains the only green_premium plan in catalog
#   - SOL's projected cost (with FiT) < VAL's projected cost
#
# But D-03 said SOL has green_score > ECO. Let me re-read...
#
# "SOL is declared plan_type = 'green_premium' with green_score > 100 (above ECO's 100)
#  so SOL wins Green for solar personas"
#
# D-03 INTENDS SOL to win Green for solar. This means:
#   - SOL wins Green (green_premium + green_score=120)
#   - SOL also wins Cheapest (FiT credit beats VAL's flat 0.21)
#   - Both cards show SOL, same saving figure
#
# But then the demo surface is visually redundant. Better design:
#   - SOL is plan_type="solar_fit" (new plan_type), green_score=120 but NOT counted
#     for Green selection (because green_candidates filter is plan_type=="green_premium")
#   - THIS IS AMBIGUOUS in D-03. Need to resolve at planning.
#
# FOR THIS SOLVER: produce BOTH scenarios (A: SOL green_premium, wins both; B: SOL
# solar_fit, ECO wins Green, SOL wins Cheapest). Planner chooses.
#
# ---- Scenario A: SOL green_premium, SOL wins Green AND Cheapest ----
# Target: saving=$55 (split the difference — single saving number for both cards)
# net_avg=500, export_avg=250
#   55 = 500*(0.32 - sol_rate) + 250*fit_rate
# Free parameter: pick fit_rate=0.08 (typical Australian retail FiT 2026)
#   55 - 250*0.08 = 500*(0.32 - sol_rate)
#   55 - 20 = 500*(0.32 - sol_rate)
#   35 = 500*(0.32 - sol_rate)
#   0.32 - sol_rate = 0.07
#   sol_rate = 0.25
# Verify: 500*0.07 + 250*0.08 = 35 + 20 = 55 ✓
#
# ---- Scenario B: SOL plan_type="solar_fit", ECO wins Green ($40), SOL wins Cheapest ($70) ----
# Green saving from ECO: saving_eco = net_avg * (STD - ECO) = net_avg * 0.06 = 40
#   -> net_avg = 40 / 0.06 = 666.67 (round to 667)
# Cheapest saving from SOL: saving_sol = net_avg * (STD - sol_rate) + export_avg * fit_rate = 70
#
# Using net_avg=667, pick fit_rate=0.08 and export_avg=200:
#   70 = 667*(0.32 - sol_rate) + 200*0.08
#   70 - 16 = 667*(0.32 - sol_rate)
#   54 = 667*(0.32 - sol_rate)
#   0.32 - sol_rate = 54/667 = 0.0810
#   sol_rate = 0.2390
# Verify: 667*0.0810 + 16 = 54.027 + 16 = 70.027 -> rounds to $70.03 (close to 70)
#
# Prefer cleaner numbers. Try net_avg=700, export_avg=200, fit_rate=0.08:
#   Green saving ECO = 700 * 0.06 = 42.00 (close to 40, not exact)
#
# Stick with 667 but accept $40.02 / $70.03 is close enough? Depends on D-02:
#   "engineered savings targets are LOCKED" — targets are "~$40 / ~$70" with ~.
# Interpret as: pick any integer/2dp target close to $40 and $70 with clean equations.
#
# RECOMMEND: Scenario B with net_avg=667, export_avg=200, fit_rate=0.08, sol_rate=0.2390
#   => Green $40.02, Cheapest $70.03 (byte-exact once locked; demo says "around $40/$70")
#
# Or cleaner: net_avg=500, export_avg=375, fit_rate=0.08, target the math:
#   Green ECO saving = 500 * 0.06 = 30 (not $40 — doesn't hit target)
# No, must keep net_avg driven by Green target.

def cust004_scenario_B():
    """SOL is solar_fit (not green_premium). ECO wins Green, SOL wins Cheapest."""
    # Solve Green ECO = $40
    #   saving_green = net_avg * 0.06 = 40 -> net_avg = 666.67
    # Use int kWh for demo realism; target acceptance is "approximately $40".
    net_avg = 667  # kWh/month average
    export_avg = 200  # kWh/month average exported
    fit_rate = 0.08  # $/kWh feed-in tariff
    # Cheapest target: saving = 70
    # 70 = 667*(0.32 - sol_rate) + 200*0.08
    # sol_rate = 0.32 - (70 - 16)/667 = 0.32 - 0.0810 = 0.2390
    sol_rate = round(0.32 - (70 - export_avg * fit_rate) / net_avg, 4)

    # Verify
    proj_std = projected_flat(net_avg, STD_RATE)
    proj_eco = projected_flat(net_avg, ECO_RATE)
    proj_val = projected_flat(net_avg, VAL_RATE)
    proj_sol = projected_sol(net_avg, export_avg, sol_rate, fit_rate)

    saving_eco = round(proj_std - proj_eco, 2)
    saving_val = round(proj_std - proj_val, 2)
    saving_sol = round(proj_std - proj_sol, 2)

    return {
        "scenario": "B (SOL=solar_fit; ECO wins Green, SOL wins Cheapest)",
        "net_avg": net_avg,
        "export_avg": export_avg,
        "sol_rate": sol_rate,
        "fit_rate": fit_rate,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_sol": round(proj_sol, 4),
        "saving_eco_green": saving_eco,
        "saving_val": saving_val,
        "saving_sol_cheapest": saving_sol,
    }


def cust004_scenario_A():
    """SOL is green_premium with green_score=120. SOL wins Green AND Cheapest."""
    # Target a single saving figure of $55 (midpoint of 40/70)
    # 55 = 500*(0.32 - sol_rate) + 250*fit_rate
    # fit_rate = 0.08 -> sol_rate = 0.25
    net_avg = 500
    export_avg = 250
    sol_rate = 0.25
    fit_rate = 0.08

    proj_std = projected_flat(net_avg, STD_RATE)
    proj_eco = projected_flat(net_avg, ECO_RATE)
    proj_val = projected_flat(net_avg, VAL_RATE)
    proj_sol = projected_sol(net_avg, export_avg, sol_rate, fit_rate)

    return {
        "scenario": "A (SOL=green_premium green_score=120; SOL wins Green AND Cheapest)",
        "net_avg": net_avg,
        "export_avg": export_avg,
        "sol_rate": sol_rate,
        "fit_rate": fit_rate,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_sol": round(proj_sol, 4),
        "saving_sol_green_AND_cheapest": round(proj_std - proj_sol, 2),
    }


# =============================================================================
# CUST-005 EV-TOU — engineer targets: Green ~$35, Cheapest ~$60
# =============================================================================
# D-05: peak_rate ~0.38, offpeak_rate ~0.12, 30/70 peak/offpeak split.
# Baseline STD is flat over total kWh (100% peak treatment is a separate TOU concept
# that only applies when the plan has peak/offpeak; STD is flat).
#   baseline_cost = total_kwh * STD_RATE + supply = total_kwh * 0.32 + 33.484
# EV-TOU saving:
#   proj_evtou = peak_kwh * peak_rate + offpeak_kwh * offpeak_rate + supply
#   saving_evtou = baseline - proj_evtou = total_kwh * 0.32 - (0.3*total*peak_rate + 0.7*total*off_rate)
#     = total * (0.32 - 0.3*peak_rate - 0.7*off_rate)
#
# Green track: ECO is only green_premium. saving_eco = total * (0.32 - 0.26) = total * 0.06
# Cheapest track: min over all candidates. VAL is 0.21 flat; EV-TOU at 0.3*0.38 + 0.7*0.12 = 0.114 + 0.084 = 0.198
#   -> EV-TOU @ 0.198 effective rate beats VAL @ 0.21. EV-TOU wins Cheapest ✓
#
# Target: Green (ECO) $35. total * 0.06 = 35 -> total = 583.33 kWh/month
# Use total=584 (int): saving_eco = 584 * 0.06 = 35.04 (close to $35)
# Or total=583: saving_eco = 583 * 0.06 = 34.98 (close)
# Or use non-integer avg and lock to 2dp: total=583.33 achieves $35.00 exactly
#   BUT billing records have integer usage_kwh. 12 months must sum to 12*total.
#   12*583.33 = 7000 -> pick 12 ints summing to 7000 with avg=583.33
#
# Simpler: target $35.04 and accept 2dp. Or pick slightly different total to get
# rounder figures. Let's try:
#   total=600 -> saving_eco = 600 * 0.06 = 36.00. Green $36.00.
#   Cheapest (EV-TOU) target $60: 600 * (0.32 - 0.3*peak - 0.7*off) = 60
#     0.32 - 0.3*peak - 0.7*off = 0.10
#     0.3*peak + 0.7*off = 0.22
#     With peak=0.38: 0.114 + 0.7*off = 0.22 -> off = 0.1514 (ugly)
#     Try peak=0.36: 0.108 + 0.7*off = 0.22 -> off = 0.16 (ok)
#     Try peak=0.40: 0.12 + 0.7*off = 0.22 -> off = 0.1429
#
# Target $35/$60 with clean rates. Let's parameterize:
#   Green saving = total * 0.06 = 35 -> total = 583.33
#   Cheapest saving = total * (0.32 - 0.3*peak - 0.7*off) = 60
#   60 / 583.33 = 0.1029  -> 0.3*peak + 0.7*off = 0.32 - 0.1029 = 0.2171
#
# Try round rates: peak=0.40, off=0.12
#   blended = 0.3*0.40 + 0.7*0.12 = 0.12 + 0.084 = 0.204
#   saving_cheap = 583.33 * (0.32 - 0.204) = 583.33 * 0.116 = 67.67 (over target)
# Try peak=0.38, off=0.14
#   blended = 0.3*0.38 + 0.7*0.14 = 0.114 + 0.098 = 0.212
#   saving = 583.33 * 0.108 = 63.00
# Try peak=0.40, off=0.14
#   blended = 0.12 + 0.098 = 0.218
#   saving = 583.33 * 0.102 = 59.50
# Try peak=0.42, off=0.14
#   blended = 0.126 + 0.098 = 0.224
#   saving = 583.33 * 0.096 = 56.00
# Try peak=0.40, off=0.13
#   blended = 0.12 + 0.091 = 0.211
#   saving = 583.33 * 0.109 = 63.58
#
# Clean solution: total=600, peak=0.40, off=0.14
#   Green = 600 * 0.06 = 36.00
#   blended_evtou = 0.3*0.40 + 0.7*0.14 = 0.12 + 0.098 = 0.218
#   Cheap  = 600 * (0.32 - 0.218) = 600 * 0.102 = 61.20
#   Targets $36/$61.20 — close to "$35/$60" per D-02's "~".
#
# Cleaner: total=583.33, peak=0.40, off=0.14 -> avg of int array must = 583.33
#   12*583.33 = 7000 (exact)
#   Green = 583.33 * 0.06 = 35.00
#   Cheap = 583.33 * 0.102 = 59.50  (close to 60)
#
# Best cleanest: total=583.33, peak=0.38, off=0.12
#   blended = 0.114 + 0.084 = 0.198
#   Cheap = 583.33 * 0.122 = 71.17  (far from 60)
#
# Final choice: total=600, peak=0.40, offpeak=0.14 (D-02 "~$35/~$60" hits $36/$61.20)
#   Rates are clean .40 / .14 for demo readability.
#
# Actually let me aim for a solution that gives closer to 35/60 with clean rates.
# total=583.33 (sum=7000), peak=0.40, off=0.14 -> Green $35.00, Cheap $59.50
# That's cleanest: Green=$35.00 exact, Cheap=$59.50 (rounds "~$60" in demo narration).

def cust005_scenario():
    """EV-TOU: Green (ECO) vs Cheapest (EV-TOU), 30/70 peak/offpeak split."""
    total_kwh_avg = 583.33  # exact when 12-month sum = 7000
    # Choose peak/offpeak rates for clean numbers
    peak_rate = 0.40
    offpeak_rate = 0.14
    peak_pct = 0.30
    offpeak_pct = 0.70

    peak_avg = total_kwh_avg * peak_pct  # 175.00
    offpeak_avg = total_kwh_avg * offpeak_pct  # 408.33

    proj_std = projected_flat(total_kwh_avg, STD_RATE)
    proj_eco = projected_flat(total_kwh_avg, ECO_RATE)
    proj_val = projected_flat(total_kwh_avg, VAL_RATE)
    proj_evtou = projected_tou(peak_avg, offpeak_avg, peak_rate, offpeak_rate)

    saving_eco = round(proj_std - proj_eco, 2)
    saving_val = round(proj_std - proj_val, 2)
    saving_evtou = round(proj_std - proj_evtou, 2)

    return {
        "total_kwh_avg": total_kwh_avg,
        "peak_kwh_avg": peak_avg,
        "offpeak_kwh_avg": offpeak_avg,
        "peak_rate": peak_rate,
        "offpeak_rate": offpeak_rate,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_evtou": round(proj_evtou, 4),
        "saving_eco_green": saving_eco,
        "saving_val": saving_val,
        "saving_evtou_cheapest": saving_evtou,
    }


# =============================================================================
# CUST-006 HARDSHIP — no specific target; byte-exact pop-out from catalog
# =============================================================================
# Low usage household, similar to or below Elena's avg (233 kWh).
# D-07: "stressed-looking shape, similar to or lower than Elena"
# Pick avg=200 (flat-rate persona, no special tariff). Savings match ECO/VAL per v2.0 pattern.
#   saving_eco = 200 * 0.06 = 12.00 -> $12.00 Green
#   saving_val = 200 * 0.11 = 22.00 -> $22.00 Cheapest (VAL)
# Still lower than Elena's $14/$25.67. Matches "similar to or lower".

def cust006_scenario():
    """Hardship persona: low usage, flat-rate bill; Green=ECO, Cheapest=VAL."""
    avg_kwh = 200  # kWh/month

    proj_std = projected_flat(avg_kwh, STD_RATE)
    proj_eco = projected_flat(avg_kwh, ECO_RATE)
    proj_val = projected_flat(avg_kwh, VAL_RATE)
    # TOU stays flat-equivalent (0.36 * usage + supply) — losing
    # EV-TOU: no peak/offpeak fields -> D-12 defaults 100% peak -> 200 * 0.40 + supply -> losing
    # SOL: no export_kwh -> D-12 defaults export=0 -> 200 * sol_rate + supply
    #   scenario B sol_rate=0.2390: 200*0.2390+33.484 = 47.80+33.484 = 81.284 (vs STD 97.484) saving=$16.20 (beats VAL!)
    # This is a concern: SOL beats VAL on hardship persona with no export. Check:
    #   VAL @ 0.21 flat: 200*0.21+33.484 = 42+33.484 = 75.484 (vs STD 97.484) saving=$22.00
    #   SOL @ 0.2390, export=0: saving = 200*(0.32-0.2390) = 200*0.081 = 16.20
    # VAL ($22) > SOL ($16.20), so VAL wins. OK.
    #
    # For scenario A sol_rate=0.25, export=0:
    #   saving = 200 * (0.32 - 0.25) = 14.00 < VAL's 22.00 -> VAL wins. OK.

    saving_eco = round(proj_std - proj_eco, 2)
    saving_val = round(proj_std - proj_val, 2)

    return {
        "avg_kwh": avg_kwh,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "saving_eco_green": saving_eco,
        "saving_val_cheapest": saving_val,
    }


# =============================================================================
# Engineered 12-month usage curves (seasonal variation, summing to 12*avg)
# =============================================================================
# Australian fiscal year Apr 2025 -> Mar 2026:
#   Indices: [0]=Apr, [1]=May, [2]=Jun, [3]=Jul, [4]=Aug (winter peak), [5]=Sep,
#            [6]=Oct, [7]=Nov, [8]=Dec, [9]=Jan, [10]=Feb (summer peak), [11]=Mar
# AU seasons: winter=Jun-Aug (heating), summer=Dec-Feb (AC + solar yield)

# CUST-004 SOLAR — summer: low net_kwh (high self-consumption + export)
#                         winter: high net_kwh (less generation)
#   Apr,May: shoulder          net mid-range, export mid
#   Jun,Jul,Aug: winter        net HIGH, export LOW
#   Sep,Oct,Nov: shoulder      net mid, export mid
#   Dec,Jan,Feb: summer        net LOW (or near 0), export HIGH
#   Mar: shoulder

# Scenario B: net_avg=667, export_avg=200, sum(net)=8004, sum(export)=2400
_NET_KWH_CUST004_B = [
    # Apr, May, Jun, Jul, Aug, Sep,  Oct,  Nov, Dec, Jan, Feb, Mar
      650, 680, 780, 820, 840, 720,  620,  570, 540, 560, 600, 624,
]
assert sum(_NET_KWH_CUST004_B) == 8004, f"CUST-004 net sum should be 8004, got {sum(_NET_KWH_CUST004_B)}"
_EXPORT_KWH_CUST004_B = [
    # Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar
      200, 180, 120, 100,  90, 160, 220, 260, 300, 290, 260, 220,
]
assert sum(_EXPORT_KWH_CUST004_B) == 2400, f"CUST-004 export sum should be 2400, got {sum(_EXPORT_KWH_CUST004_B)}"

# CUST-005 EV-TOU — winter: slightly higher (cold-weather EV efficiency loss)
#   total_avg=583.33, sum=7000. 30/70 peak/offpeak — same ratio per month for simplicity
_USAGE_KWH_CUST005 = [
    # Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar
      560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560,
]
assert sum(_USAGE_KWH_CUST005) == 7000, f"CUST-005 usage sum should be 7000, got {sum(_USAGE_KWH_CUST005)}"
# peak_kwh_i = round(0.30 * usage_i); offpeak_kwh_i = usage_i - peak_kwh_i
_PEAK_KWH_CUST005 = [round(0.30 * u) for u in _USAGE_KWH_CUST005]
_OFFPEAK_KWH_CUST005 = [u - p for u, p in zip(_USAGE_KWH_CUST005, _PEAK_KWH_CUST005)]
# Note: integer-rounded peak/offpeak per month; aggregate may drift slightly from 30/70
# Verify:
sum_peak = sum(_PEAK_KWH_CUST005)
sum_off = sum(_OFFPEAK_KWH_CUST005)
print(f"CUST-005 peak sum={sum_peak}, offpeak sum={sum_off}, total={sum_peak+sum_off}")

# CUST-006 HARDSHIP — low, flat-ish (stressed household can't reduce): avg=200
_USAGE_KWH_CUST006 = [
    # Apr, May, Jun, Jul, Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar
      200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185,
]
assert sum(_USAGE_KWH_CUST006) == 2400, f"CUST-006 usage sum should be 2400 (avg 200), got {sum(_USAGE_KWH_CUST006)}"


# =============================================================================
# Run all scenarios
# =============================================================================
if __name__ == "__main__":
    import json
    import pprint

    print("=" * 80)
    print("CUST-004 SCENARIO A (SOL green_premium; SOL wins BOTH tracks)")
    print("=" * 80)
    pprint.pprint(cust004_scenario_A())

    print("\n" + "=" * 80)
    print("CUST-004 SCENARIO B (SOL solar_fit; ECO wins Green, SOL wins Cheapest)")
    print("=" * 80)
    pprint.pprint(cust004_scenario_B())

    print("\n" + "=" * 80)
    print("CUST-005 EV-TOU")
    print("=" * 80)
    pprint.pprint(cust005_scenario())

    print("\n" + "=" * 80)
    print("CUST-006 HARDSHIP")
    print("=" * 80)
    pprint.pprint(cust006_scenario())

    print("\n" + "=" * 80)
    print("12-MONTH ARRAYS")
    print("=" * 80)
    print(f"CUST-004 net_kwh    = {_NET_KWH_CUST004_B}")
    print(f"CUST-004 export_kwh = {_EXPORT_KWH_CUST004_B}")
    print(f"CUST-005 usage_kwh  = {_USAGE_KWH_CUST005}")
    print(f"CUST-005 peak_kwh   = {_PEAK_KWH_CUST005}")
    print(f"CUST-005 offpeak_kwh= {_OFFPEAK_KWH_CUST005}")
    print(f"CUST-006 usage_kwh  = {_USAGE_KWH_CUST006}")

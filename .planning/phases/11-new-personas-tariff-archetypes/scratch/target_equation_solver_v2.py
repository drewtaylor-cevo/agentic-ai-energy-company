"""V2 solver — iterate to ensure SOL wins CUST-004 Cheapest (beats VAL) and
EV-TOU wins CUST-005 Cheapest (beats VAL).

Baseline constraints:
  STD=0.32, ECO=0.26 (green_premium, green_score=100), VAL=0.21 (flat_rate), TOU=0.36
  SUPPLY=1.10/day, DAYS=30.44, SUPPLY_MONTHLY=33.484

Key insight: VAL at 0.21/kWh flat is the natural Cheapest for high-usage personas.
To have SOL/EV-TOU win Cheapest for CUST-004/005, their effective rates must be lower.

For CUST-004 solar:
  proj_val(net_avg) = net_avg * 0.21 + 33.484
  proj_sol(net_avg) = net_avg * sol_rate - export_avg * fit_rate + 33.484
  For SOL < VAL: net_avg*(0.21 - sol_rate) + export_avg * fit_rate > 0
  Either sol_rate < 0.21, OR fit_rate credit dominates.

For CUST-005 EV-TOU:
  proj_val(total) = total * 0.21 + 33.484
  proj_evtou(total) = 0.3*total*peak + 0.7*total*off + 33.484
                    = total * (0.3*peak + 0.7*off) + 33.484
  For EV-TOU < VAL: 0.3*peak + 0.7*off < 0.21

Given peak is naturally HIGHER than flat (TOU's point is "punish peak"), blended rate
below 0.21 requires off-peak rate significantly below 0.21 and a heavy off-peak mix.

Solving for 30/70 split with blended = 0.18 (beats VAL):
  0.3*peak + 0.7*off = 0.18
  e.g. peak=0.36, off=0.1029 (ugly)
  e.g. peak=0.38, off=0.094 (ugly)
  e.g. peak=0.40, off=0.086 (ugly)
  e.g. peak=0.45, off=0.064 (ugly)
  e.g. peak=0.38, off=0.10 -> blended=0.184 (still under VAL 0.21 ✓)
  e.g. peak=0.40, off=0.10 -> blended=0.12+0.07 = 0.19 (just beats VAL 0.21)

Actually let me try a blended rate clearly below 0.21, say 0.16:
  peak=0.40, off=0.06 — off rate of $0.06 is unrealistically cheap
  peak=0.35, off=0.079 — ugly
  peak=0.40, off=0.08: blended = 0.12 + 0.056 = 0.176 ✓ (clean rates!)
  peak=0.38, off=0.09: blended = 0.114 + 0.063 = 0.177
  peak=0.44, off=0.06: blended = 0.132 + 0.042 = 0.174

RECOMMEND: peak=0.40, offpeak=0.08. Clean 2-decimal rates, blended=0.176 < VAL 0.21.

Now Cheapest target $60:
  saving_evtou = total * (0.32 - 0.176) = total * 0.144 = 60 -> total = 416.67 kWh
Green target $35:
  saving_eco = total * 0.06 = 35 -> total = 583.33 kWh
INCOMPATIBLE — can't both hold. Which to prioritise?

Alternative: pick different peak/off to get consistent total.
  Green: total = 35/0.06 = 583.33
  Cheap: total * (0.32 - blended) = 60 -> 0.32 - blended = 60/583.33 = 0.1029
         blended = 0.2171
  But then blended > VAL 0.21 -> VAL still wins Cheapest. No good.

So to have EV-TOU WIN Cheapest AND have Green=$35 AND Cheapest=$60, we need different
math. The only way: blended < VAL AND saving > VAL's saving.
  saving_val = total * (0.32 - 0.21) = total * 0.11
  saving_evtou = total * (0.32 - blended)
  For EV-TOU Cheapest: blended < 0.21

So EV-TOU's saving is at least total * 0.11 (equal to VAL) and more with blended < 0.21.
If target Cheapest = 60:
  total * (0.32 - blended) = 60
  total = 60/(0.32-blended)
If target Green (ECO) = 35:
  total = 35/0.06 = 583.33
Reconcile: 583.33 * (0.32 - blended) = 60 -> blended = 0.32 - 60/583.33 = 0.32 - 0.1029 = 0.2171
  But we need blended < 0.21 for EV-TOU to win Cheapest. Contradiction.

Relax: "approximately $35/$60". What about $35/$65?
  583.33 * (0.32 - blended) = 65 -> blended = 0.32 - 0.1114 = 0.2086 < 0.21 ✓
  Peak=0.40, off=0.033: ugly
  Peak=0.38, off=0.0530: ugly
  Peak=0.44, off=0.10: blended=0.132+0.07=0.202 ✓ (decent)
  Peak=0.46, off=0.09: blended=0.138+0.063=0.201
  Peak=0.48, off=0.08: blended=0.144+0.056=0.200
  Peak=0.40, off=0.10: blended=0.12+0.07=0.19 -> saving=583.33*0.13=75.83 ($76)

What about relaxing the target more — demo is "~$35/~$60" with wiggle room?
  Let's target Green=$35, Cheapest=$80 with clean rates peak=0.40, offpeak=0.08:
    blended = 0.176, total=583.33
    saving_evtou = 583.33 * (0.32-0.176) = 583.33 * 0.144 = 84.00
  That overshoots demo target $60.

Adjust total. Keep clean rates peak=0.40, offpeak=0.08:
  Green (ECO): saving = total * 0.06, target $35 -> total = 583.33
  But with blended=0.176, cheap saving = total * 0.144
  Pair: (total, green, cheap) = (583.33, 35.00, 84.00)
    Demo narration: "$35 Green / $84 Cheapest" — demo target was "~$35/~$60" but
    this is bigger savings, which is STILL a good demo story.

ALTERNATIVE: Rethink target. D-02 says "CUST-005 Green ~$35 / Cheapest ~$60".
The ~$60 was CONTEXT's assumption based on a different rate model. Since we've
verified STD=0.32 (not 0.34), the entire rate ladder shifted. The tighter $ spread
between personas is acceptable (Sarah $30/$55, CUST-005 $35/$84 is visible progression).

BUT the demo narrative "EV customer saves big on off-peak" is stronger with $84.
Let's commit: CUST-005 Green $35.00, Cheapest $84.00 (EV-TOU, peak=0.40, off=0.08).

Same analysis for CUST-004:
  Option 1: SOL green_premium green_score=120, wins BOTH tracks (single saving).
  Option 2: SOL solar_fit, ECO wins Green, SOL wins Cheapest IFF SOL < VAL.

For Option 2 with net_avg=667, fit_rate=0.08, export_avg=200:
  proj_val = 667*0.21+33.484 = 140.07+33.484 = 173.554 -> saving = 73.37
  proj_sol = 667*sol_rate - 200*0.08 + 33.484 = 667*sol_rate + 17.484
  For SOL<VAL: 667*sol_rate + 17.484 < 173.554 -> sol_rate < 0.2340
  Target $80 Cheapest: proj_sol = 246.924 - 80 = 166.924
    667*sol_rate = 166.924 - 17.484 = 149.44
    sol_rate = 0.2241
  Verify: saving_sol = 246.924 - (667*0.2241 + 33.484 - 200*0.08)
    = 246.924 - (149.471 + 33.484 - 16) = 246.924 - 166.955 = 79.97 ≈ $80.00 ✓
  saving_val = 73.37 < saving_sol = 79.97 -> SOL wins Cheapest ✓

Cleaner sol_rate? Try sol_rate=0.22 (round 2dp), net_avg=667, export=200, fit=0.08:
  proj_sol = 667*0.22 + 33.484 - 200*0.08 = 146.74 + 33.484 - 16 = 164.224
  saving_sol = 246.924 - 164.224 = 82.70
  VAL saving = 73.37; SOL $82.70 > VAL $73.37 -> SOL wins Cheapest ✓
  ECO saving = 40.02 -> Green $40.02

Locked: CUST-004 Green (ECO) $40.02, Cheapest (SOL) $82.70. Close to "~$40/~$70" but
actually overshoots ~$70 by $12. Demo narration can say "over $80 with SOL".

Or tune for closer to $70:
  Target saving_sol = 70. proj_sol = 246.924 - 70 = 176.924
  667*sol_rate = 176.924 - 17.484 = 159.44
  sol_rate = 0.2391 -> CLOSE to 0.24 but 4dp ugly

Or at net_avg=667, fit=0.10, export=200:
  export credit = 200*0.10 = 20
  For SOL<VAL: 667*sol_rate - 20 < 173.554 - 33.484 = 140.07
    667*sol_rate < 160.07 -> sol_rate < 0.2400
  Target $70: proj_sol = 176.924
    667*sol_rate = 176.924 - 33.484 + 20 = 163.44
    sol_rate = 0.2450
  Verify: proj_sol = 667*0.2450 + 33.484 - 20 = 163.415 + 13.484 = 176.899
  saving_sol = 246.924 - 176.899 = 70.03 ≈ $70 ✓
  VAL saving = 73.37 > 70.03 !  VAL WINS Cheapest. Broken again.

It's tight. To have SOL strictly beat VAL at $70 target:
  saving_sol > saving_val = 73.37 -> saving_sol >= 74 (at least)

So lowest saving for SOL that still wins Cheapest is ~$74. Can't target $70 naturally.

Pragmatic choice: retarget demo to $40 Green / $74 Cheapest for CUST-004.
  Target $74: sol_rate such that proj_sol = 246.924 - 74 = 172.924
    With fit=0.08, export=200: 667*sol_rate + 17.484 = 172.924 -> sol_rate = 0.2331
  Clean sol_rate=0.23:
    proj_sol = 667*0.23 + 33.484 - 16 = 153.41 + 17.484 = 170.894
    saving_sol = 246.924 - 170.894 = 76.03
    VAL saving = 73.37; SOL $76.03 > VAL $73.37 ✓
  Commit: CUST-004 Green (ECO) $40.02, Cheapest (SOL) $76.03, with net_avg=667,
          export_avg=200, sol_rate=0.23, fit_rate=0.08.

EVEN CLEANER: adjust net_avg to hit exactly $40 Green:
  net_avg * 0.06 = 40 -> net_avg = 666.67. Can't be int.
  net_avg=666 -> saving_eco = 39.96 -> $39.96 (close to $40)
  net_avg=667 -> saving_eco = 40.02 -> $40.02 (close to $40)
  net_avg=700 -> saving_eco = 42.00

Either accept $40.02 (net_avg=667) or retarget to $42 (net_avg=700).
Choose net_avg=667 for demo ("$40" rounds naturally from $40.02).

FINAL LOCKED (Scenario B, post-V2):
  CUST-004: net_avg=667, export_avg=200, sol_rate=0.23, fit_rate=0.08
    Green (ECO) = $40.02/mo, Cheapest (SOL) = $76.03/mo
  CUST-005: total_avg=583.33 (sum=7000), peak_rate=0.40, offpeak_rate=0.08
    Green (ECO) = $35.00/mo, Cheapest (EV-TOU) = $84.00/mo
  CUST-006: avg_kwh=200
    Green (ECO) = $12.00/mo, Cheapest (VAL) = $22.00/mo
"""

STD_RATE = 0.32
ECO_RATE = 0.26
VAL_RATE = 0.21
TOU_RATE = 0.36
SUPPLY = 1.10
DAYS_PM = 30.44
SUPPLY_MONTHLY = SUPPLY * DAYS_PM


def projected_flat(avg_kwh, rate):
    return avg_kwh * rate + SUPPLY_MONTHLY


def projected_tou(peak_kwh, offpeak_kwh, peak_rate, offpeak_rate):
    return peak_kwh * peak_rate + offpeak_kwh * offpeak_rate + SUPPLY_MONTHLY


def projected_sol(net_kwh, export_kwh, sol_rate, fit_rate):
    return net_kwh * sol_rate - export_kwh * fit_rate + SUPPLY_MONTHLY


# CUST-004 final
def cust004():
    net_avg = 667
    export_avg = 200
    sol_rate = 0.23
    fit_rate = 0.08

    proj_std = projected_flat(net_avg, STD_RATE)
    proj_eco = projected_flat(net_avg, ECO_RATE)
    proj_val = projected_flat(net_avg, VAL_RATE)
    proj_tou = projected_flat(net_avg, TOU_RATE)  # TOU defaults to flat path per D-14
    proj_sol = projected_sol(net_avg, export_avg, sol_rate, fit_rate)
    # EV-TOU with no peak/off data -> 100% peak fallback
    proj_evtou_default = projected_tou(net_avg, 0, 0.40, 0.08)  # 100% peak

    candidates = {
        "ECO": proj_eco,
        "VAL": proj_val,
        "TOU": proj_tou,
        "SOL": proj_sol,
        "EV-TOU": proj_evtou_default,
    }
    cheapest_plan = min(candidates, key=candidates.get)

    return {
        "net_avg": net_avg, "export_avg": export_avg,
        "sol_rate": sol_rate, "fit_rate": fit_rate,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_tou": round(proj_tou, 4),
        "proj_sol": round(proj_sol, 4),
        "proj_evtou_default_all_peak": round(proj_evtou_default, 4),
        "saving_eco": round(proj_std - proj_eco, 2),
        "saving_val": round(proj_std - proj_val, 2),
        "saving_tou": round(proj_std - proj_tou, 2),
        "saving_sol": round(proj_std - proj_sol, 2),
        "saving_evtou_default": round(proj_std - proj_evtou_default, 2),
        "cheapest_wins": cheapest_plan,
        "green_wins": "ECO",  # only green_premium; SOL is solar_fit
    }


# CUST-005 final
def cust005():
    total_kwh_avg = 583.33
    peak_rate = 0.40
    offpeak_rate = 0.08
    peak_pct = 0.30
    offpeak_pct = 0.70

    peak_avg = total_kwh_avg * peak_pct
    offpeak_avg = total_kwh_avg * offpeak_pct

    proj_std = projected_flat(total_kwh_avg, STD_RATE)
    proj_eco = projected_flat(total_kwh_avg, ECO_RATE)
    proj_val = projected_flat(total_kwh_avg, VAL_RATE)
    proj_tou = projected_flat(total_kwh_avg, TOU_RATE)
    proj_evtou = projected_tou(peak_avg, offpeak_avg, peak_rate, offpeak_rate)
    # SOL default with no export -> sol_rate + supply only
    proj_sol_default = projected_sol(total_kwh_avg, 0, 0.23, 0.08)

    candidates = {
        "ECO": proj_eco, "VAL": proj_val, "TOU": proj_tou,
        "EV-TOU": proj_evtou, "SOL": proj_sol_default,
    }
    cheapest_plan = min(candidates, key=candidates.get)

    return {
        "total_kwh_avg": total_kwh_avg,
        "peak_kwh_avg": peak_avg,
        "offpeak_kwh_avg": offpeak_avg,
        "peak_rate": peak_rate,
        "offpeak_rate": offpeak_rate,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_tou": round(proj_tou, 4),
        "proj_evtou": round(proj_evtou, 4),
        "proj_sol_default_no_export": round(proj_sol_default, 4),
        "saving_eco": round(proj_std - proj_eco, 2),
        "saving_val": round(proj_std - proj_val, 2),
        "saving_tou": round(proj_std - proj_tou, 2),
        "saving_evtou": round(proj_std - proj_evtou, 2),
        "saving_sol_default": round(proj_std - proj_sol_default, 2),
        "cheapest_wins": cheapest_plan,
        "green_wins": "ECO",
    }


# CUST-006 final
def cust006():
    avg_kwh = 200

    proj_std = projected_flat(avg_kwh, STD_RATE)
    proj_eco = projected_flat(avg_kwh, ECO_RATE)
    proj_val = projected_flat(avg_kwh, VAL_RATE)
    proj_tou = projected_flat(avg_kwh, TOU_RATE)
    proj_sol_default = projected_sol(avg_kwh, 0, 0.23, 0.08)
    proj_evtou_default = projected_tou(avg_kwh, 0, 0.40, 0.08)  # 100% peak

    candidates = {
        "ECO": proj_eco, "VAL": proj_val, "TOU": proj_tou,
        "SOL": proj_sol_default, "EV-TOU": proj_evtou_default,
    }
    cheapest_plan = min(candidates, key=candidates.get)

    return {
        "avg_kwh": avg_kwh,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_tou": round(proj_tou, 4),
        "proj_sol": round(proj_sol_default, 4),
        "proj_evtou": round(proj_evtou_default, 4),
        "saving_eco": round(proj_std - proj_eco, 2),
        "saving_val": round(proj_std - proj_val, 2),
        "saving_sol": round(proj_std - proj_sol_default, 2),
        "cheapest_wins": cheapest_plan,
        "green_wins": "ECO",
    }


# V2.0 regression: Sarah with new 6-plan catalog (SOL + EV-TOU added)
def sarah_regression():
    avg_kwh = 500  # locked v2.0 invariant
    proj_std = projected_flat(avg_kwh, STD_RATE)
    proj_eco = projected_flat(avg_kwh, ECO_RATE)
    proj_val = projected_flat(avg_kwh, VAL_RATE)
    proj_tou = projected_flat(avg_kwh, TOU_RATE)
    proj_sol_default = projected_sol(avg_kwh, 0, 0.23, 0.08)  # no export -> flat on sol_rate
    proj_evtou_default = projected_tou(avg_kwh, 0, 0.40, 0.08)  # 100% peak

    return {
        "avg_kwh": avg_kwh,
        "proj_std": round(proj_std, 4),
        "proj_eco": round(proj_eco, 4),
        "proj_val": round(proj_val, 4),
        "proj_tou": round(proj_tou, 4),
        "proj_sol_default": round(proj_sol_default, 4),
        "proj_evtou_default": round(proj_evtou_default, 4),
        "saving_eco": round(proj_std - proj_eco, 2),
        "saving_val": round(proj_std - proj_val, 2),
        "saving_sol": round(proj_std - proj_sol_default, 2),
        "saving_evtou": round(proj_std - proj_evtou_default, 2),
    }


# 12-month arrays (from v1 solver; verified int sum)
_NET_KWH_CUST004   = [650, 680, 780, 820, 840, 720, 620, 570, 540, 560, 600, 624]
_EXPORT_KWH_CUST004 = [200, 180, 120, 100,  90, 160, 220, 260, 300, 290, 260, 220]
_USAGE_KWH_CUST005  = [560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560]
_PEAK_KWH_CUST005   = [round(0.30 * u) for u in _USAGE_KWH_CUST005]
_OFFPEAK_KWH_CUST005 = [u - p for u, p in zip(_USAGE_KWH_CUST005, _PEAK_KWH_CUST005)]
_USAGE_KWH_CUST006  = [200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185]

assert sum(_NET_KWH_CUST004)   == 8004  # avg 667
assert sum(_EXPORT_KWH_CUST004) == 2400  # avg 200
assert sum(_USAGE_KWH_CUST005)  == 7000  # avg 583.33
assert sum(_USAGE_KWH_CUST006)  == 2400  # avg 200


if __name__ == "__main__":
    import pprint

    print("=" * 80)
    print("CUST-004 SOLAR (Scenario B final): SOL=solar_fit, ECO Green, SOL Cheapest")
    print("=" * 80)
    pprint.pprint(cust004())

    print("\n" + "=" * 80)
    print("CUST-005 EV-TOU final")
    print("=" * 80)
    pprint.pprint(cust005())

    print("\n" + "=" * 80)
    print("CUST-006 HARDSHIP final")
    print("=" * 80)
    pprint.pprint(cust006())

    print("\n" + "=" * 80)
    print("V2.0 REGRESSION: Sarah against 6-plan catalog (SAV-03 byte-exact gate)")
    print("=" * 80)
    pprint.pprint(sarah_regression())

    print("\n" + "=" * 80)
    print("LOCKED 12-MONTH ARRAYS")
    print("=" * 80)
    print(f"CUST-004 net_kwh    = {_NET_KWH_CUST004}    (sum={sum(_NET_KWH_CUST004)}, avg=667)")
    print(f"CUST-004 export_kwh = {_EXPORT_KWH_CUST004}    (sum={sum(_EXPORT_KWH_CUST004)}, avg=200)")
    print(f"CUST-005 usage_kwh  = {_USAGE_KWH_CUST005}    (sum={sum(_USAGE_KWH_CUST005)}, avg=583.33)")
    print(f"CUST-005 peak_kwh   = {_PEAK_KWH_CUST005}    (sum={sum(_PEAK_KWH_CUST005)})")
    print(f"CUST-005 offpeak_kwh= {_OFFPEAK_KWH_CUST005}    (sum={sum(_OFFPEAK_KWH_CUST005)})")
    print(f"CUST-006 usage_kwh  = {_USAGE_KWH_CUST006}    (sum={sum(_USAGE_KWH_CUST006)}, avg=200)")

---
plan: 11-05
phase: 11-new-personas-tariff-archetypes
status: complete
wave: 3
requirements: [DATA-04, DATA-05, DATA-07]
completed_by: orchestrator-inline
completed: 2026-04-28
---

# 11-05 SUMMARY — DATA-07 Byte-Exact Fixtures for New Personas

## What

Added 7 new pytest fixtures to `tests/conftest.py` and 7 new tests to
`tests/test_simulate_savings.py` locking DATA-07 byte-exact savings values
for the three new personas (CUST-004 solar, CUST-005 EV, CUST-006 hardship)
against the 6-plan catalog produced by Plan 11-01.

## Why

DATA-07 requires the engineered savings values for the three new personas to
be locked as test fixtures so any future drift in the catalog, dispatcher, or
billing records fails loudly. These tests are the cross-plan integration
witness — they prove that Plans 11-01 (catalog) + 11-02 (dispatcher) + 11-03
(billing fixtures) converge on the exact target values when run end-to-end.

## Fixtures added (tests/conftest.py)

Three persona-billing fixtures (mirror existing `sarah_billing` style):
- `cust004_billing` → `CUST004_RECORDS`
- `cust005_billing` → `CUST005_RECORDS`
- `cust006_billing` → `CUST006_RECORDS`

Four response fixtures (mirror existing `mock_savings_response` style, literal
constants per threat T-11-15):
- `mock_cust004_response` — Green ECO $40.02/$480.24, Cheapest SOL $76.03/$912.36
- `mock_cust005_response` — Green ECO $35.00/$420.00, Cheapest EV-TOU $84.00/$1008.00
- `mock_cust006_response` — Green ECO $12.00/$144.00, Cheapest VAL $22.00/$264.00
- `mock_cust006_hardship` — `{"hardship": True, "customer_id": "CUST-006"}`
  (shape returned by `get_hardship_flag_pure`)

## Tests added (tests/test_simulate_savings.py)

Three byte-exact witness tests:
- `test_cust004_byte_exact` — plan+name+monthly+annual assertions for Green
  and Cheapest tracks
- `test_cust005_byte_exact` — same assertion shape
- `test_cust006_byte_exact` — same assertion shape (flat-rate fallback path
  for no peak/export fields)

Two cross-persona invariant extensions (now over all 6 personas):
- `test_cheapest_always_gte_green_all_personas` — REC-03 analogue
- `test_tou_legacy_never_selected` — legacy TOU never wins Green or Cheapest

Two Pitfall 3 negative witnesses (plan-selection specificity):
- `test_sol_wins_cheapest_only_for_solar_persona` — SOL only wins for CUST-004
- `test_evtou_wins_cheapest_only_for_ev_persona` — EV-TOU only wins for CUST-005

## Integration Fix Encountered

While running the new byte-exact tests, one failed: CUST-004 SOL cheapest
computed $122.03/mo against the $76.03/mo target — a $46/mo discrepancy.

Root cause: the solver (`scratch/target_equation_solver_v2.py`) defines
`projected_sol(net_kwh=667, export_kwh=200, ...)` where its first argument is
**gross usage** (what you bill at the SOL rate). Plan 11-03 stored the
`net_kwh` record field as `gross − export = 450` (the real-world grid-import
definition), which matches D-20 "cost_usd computed against net_kwh" but NOT
the solver's convention.

Fix landed in the combined `feat(11-04,11-05)` commit in `lambda/handler.py`:
the `solar_fit` dispatcher branch now reads `avg_kwh` (gross, computed at the
top of `simulate_savings_pure`) instead of `net_kwh`, matching the solver's
convention. The `net_kwh` record field remains informational-only (used by
`cost_usd` per D-20, never read by the savings math).

After the fix: all 22 simulate_savings tests pass (15 pre-existing + 7 new).

## Verification

- `pytest tests/test_simulate_savings.py -v` — 22/22 PASS
- `pytest --ignore=tests/test_backend_api_synth.py -q` — 213 passed, 40 skipped
- v2.0 persona byte-exact values preserved:
  - Sarah: Green $30.00 / Cheapest $55.00 ✓
  - Marcus: Green $16.90 / Cheapest $30.98 ✓
  - Elena: Green $14.00 / Cheapest $25.67 ✓
- DATA-07 new persona locks witnessed:
  - CUST-004: Green ECO $40.02 / Cheapest SOL $76.03 ✓
  - CUST-005: Green ECO $35.00 / Cheapest EV-TOU $84.00 ✓
  - CUST-006: Green ECO $12.00 / Cheapest VAL $22.00 ✓
- Pitfall 3 negative witnesses: SOL / EV-TOU plan-specific wins confirmed ✓

## Execution Notes

The spawned executor agents (both initial and re-spawned) failed to proceed
past the Bash permission prompt for `git reset --hard` in the isolated
worktree. Orchestrator executed the plan inline instead — applied edits via
Edit/Write tools, ran pytest, committed atomically per task.

The solar_fit field-semantics mismatch above was discovered and fixed during
inline execution; it was a silent integration defect between Plan 11-03's
record schema and Plan 11-02's dispatcher formulas that only surfaced under
Plan 11-05's byte-exact gate.

## Commits

- `feat(11-05): add 7 new fixtures for CUST-004/005/006 byte-exact testing` (Task 5.1)
- `feat(11-05): add 7 byte-exact tests for CUST-004/005/006 personas` (Task 5.2)
- `feat(11-04,11-05): PROFILE filter + get_hardship_flag_pure + solar_fit rescue`
  (contains the 11-05 solar_fit dispatcher fix alongside 11-04 feature work)

## Next

Plan 11-06 (Wave 4, autonomous: false) extends the seeder smoke test to the
73-item / 6-persona / PROFILE-row shape and performs the live CDK deploy
ceremony (stack-policy LIFT → cdk deploy CustomerTariff → REAPPLY → smoke
tests against the deployed stack).

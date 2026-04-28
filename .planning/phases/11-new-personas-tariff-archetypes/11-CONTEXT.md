# Phase 11: New Personas + Tariff Archetypes - Context

**Gathered:** 2026-04-28
**Status:** Ready for planning

<domain>
## Phase Boundary

Engineered dummy data supports the full v3.0 demo surface: two new personas with realistic billing shapes (CUST-004 Solar PV with net-metering, CUST-005 EV with time-of-use peak/off-peak split), two new tariff archetypes (SOL Solar Feed-in, EV-TOU Time-of-Use), plus one new dedicated hardship persona (CUST-006) carrying a `hardship_flag: true` PROFILE item. `simulate_savings_pure` is extended with a `plan_type` dispatcher (inline if-branch) for TOU and solar math. The three v2.0 persona savings invariants (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67) remain byte-exact through the refactor.

**Out of scope (belongs elsewhere):**
- Agent-side tool dispatcher for `get_hardship_flag` action (Phase 13 owns the action dispatcher).
- `CustomerDataProvider` Protocol + provider implementations (Phase 12).
- Hardship short-circuit in agent `invoke()` / discriminated union / `api_lambda/handler.py:152` update (Phase 14).
- AgentCore Memory wiring (Phase 15).

</domain>

<decisions>
## Implementation Decisions

### Persona & Tariff Design

- **D-01: CUST-004 solar record schema adds `export_kwh` + `net_kwh`, keeps `usage_kwh` for back-compat.** Every record carries all three fields. For CUST-001/002/003 (v2.0 personas), `export_kwh = 0` and `net_kwh = usage_kwh` — back-compat holds and `simulate_savings_pure`'s existing flat path reads `usage_kwh` unchanged. Matches DATA-04 schema extension in research SUMMARY.md.
- **D-02: Engineered savings targets are LOCKED first, usage arrays reverse-engineered from savings equations.** CUST-004 Green ~$40 / Cheapest ~$70; CUST-005 Green ~$35 / Cheapest ~$60. Targets picked before rates or arrays; usage + export + peak/off-peak avgs solved algebraically from the target equation, then a 12-month variation curve is selected that sums to 12 × avg. Mirrors DEMO-02 Phase 1 ceremony for Sarah. CUST-006 has no specific target ($ is whatever the math produces) — byte-exact lock on whatever comes out.
- **D-03: Green/Cheapest selection logic stays as-is** — `max(green_score)` over `plan_type == "green_premium"` and `min(projected_monthly_cost)` over all candidates. No `persona_class`, no `plan_eligibility`, no selection-algorithm rewrite. **SOL is `plan_type = "solar_fit"` with `green_score = 80`** (below ECO's 100) so ECO continues to win Green for CUST-004 and SOL wins Cheapest only — two distinct plans on the two demo cards, not the same plan twice. EV-TOU is declared `plan_type = "time_of_use"` with a non-Green green_score (30) and an asymmetric rate that wins Cheapest on 70% off-peak usage curves. *(Supersedes earlier draft that declared SOL as `green_premium` with score>100 — the research-confirmed numerics in `11-RESEARCH.md` §Code Examples reflect this correction.)*
- **D-04: Solar FiT credit is included in both baseline STD cost comparison AND SOL projected cost calculation.** `projected_cost(SOL) = net_kwh * rate_per_kwh - export_kwh * fit_rate + daily_supply_charge * 30.44`. STD baseline for solar personas does NOT carry FiT (they're unmetered under current STD). This prevents "Cheapest" from accidentally recommending loss of FiT credits. Matches research LD-5 explicit note.
- **D-05: EV-TOU rate structure — peak ~0.38 /kWh, off-peak ~0.12 /kWh** (exact rates solved from $35/$60 targets during research). CUST-005 billing records carry `peak_kwh` + `offpeak_kwh` fields; assumed 30/70 peak/off-peak split is the engineered shape. For v2.0 personas (no peak_kwh/offpeak_kwh), TOU math path defaults to 100% peak — EV-TOU computes expensive, VAL still wins their Cheapest. Byte-exact held by construction.

### Hardship Flag Placement

- **D-06: CUST-006 is a NEW dedicated hardship persona** (not CUST-005, not CUST-003). Rationale: separates narrative surfaces cleanly for rehearsal — CUST-001/002/003 = v2.0 baseline, CUST-004 = solar, CUST-005 = EV, CUST-006 = hardship. No persona carries two conflicting stories (avoids AGENT-01 bill-shock colliding with AGENT-02 short-circuit). REQUIREMENTS.md DATA-06 explicitly allows "existing OR new persona".
- **D-07: CUST-006 carries a full 12-month `usage_kwh` billing history** (low, stressed-looking shape, similar to or lower than Elena). Rationale: Phase 14 AGENT-02 must be testable against "a customer who HAS billing data and is ALSO flagged" — not a data-missing false-positive. `simulate_savings_pure` for CUST-006 produces a valid recommendation (ECO Green, VAL Cheapest per catalog); Phase 14's hardship guard short-circuits before the LLM ever sees that recommendation.
- **D-08: `hardship_flag` lives on a new `SK = "PROFILE"` row on the existing `tariff-billing` DynamoDB table.** Row shape: `{customer_id: "CUST-006", month: "PROFILE", hardship_flag: true}`. No new CFN resource, no new table — minimises freeze surface on `CustomerTariff` stack. Matches research Q8 default.
- **D-09: PROFILE item carries ONLY `hardship_flag` this phase.** No `persona_class`, no `display_name`, no `segment`. Minimum surface; other PROFILE fields deferred. Establishes the SK pattern for Phase 12/14/15 to extend.
- **D-10: `get_hardship_flag_pure(customer_id, table_client) -> dict` is a pure helper in `lambda/handler.py`** returning `{hardship: bool, customer_id: str}`. Offline-testable via the same injection pattern `simulate_savings_pure` uses. NOT wired to any agent action this phase — just a helper sitting there for Phase 13 (tool dispatcher) and Phase 14 (pre-LLM guard) to pick up. Satisfies REQUIREMENTS.md success criterion 5.
- **D-11: `mock_cust006_response` locks byte-exact savings values** (whatever `simulate_savings_pure` produces for CUST-006 against the 6-plan catalog). Separate fixture `mock_cust006_hardship = {"hardship": True, "customer_id": "CUST-006"}` for the helper. SAV-03 holds on the hypothetical-recommendation; hardship guard is a separate code path in Phase 14.

### TOU Dispatcher Refactor

- **D-12: `simulate_savings_pure` dispatches on `plan_type` via inline if-branch inside `projected_monthly_cost(plan)` closure.** Three branches: `flat_rate` / `green_premium` (both use current rate-per-kwh + supply formula); `time_of_use` (peak_rate * peak_kwh + offpeak_rate * offpeak_kwh + supply, with 100%-peak fallback when peak/offpeak fields absent); `solar_fit` (rate * net_kwh - fit_rate * export_kwh + supply, with export=0 fallback). Minimum diff. Existing flat path byte-exact held by construction.
- **D-13: SAV-03 byte-exact gate is the existing `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` fixtures re-run against the refactored `simulate_savings_pure` with the 6-plan catalog** (STD + ECO + VAL + TOU + SOL + EV-TOU). Any deviation on v2.0 persona savings figures ($30/$55, $16.90/$30.98, $14.00/$25.67) is a refactor bug. No new test file needed; existing fixtures ARE the gate. Extended with `mock_cust004/005/006_response` for the new personas.
- **D-14: Legacy `TOU` plan (plan_id='TOU', 'Flex Time') stays unchanged in the catalog.** Once the TOU math path exists, v2.0 personas default to 100% peak — TOU's `rate_per_kwh=0.36` is read as the peak rate; result is `usage_kwh * 0.36 + supply`, identical to the pre-refactor flat computation. V2.0 SAV-03 byte-exact held. Future rehearsal optionality: presenter could add peak_kwh to a v2.0 persona to surface TOU's off-peak benefit.
- **D-15: New plan fields (`fit_rate` on SOL, `peak_rate` + `offpeak_rate` on EV-TOU) extend `tariff_plans.json` as optional plan-level fields.** v2.0 plans (STD/ECO/VAL/TOU) get NO new fields — their schema is byte-frozen. `simulate_savings_pure` branches on `plan_type` and reads the right fields; missing fields on a plan are a defaulted-to-flat scenario. Byte-equality gate between `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json` preserved.

### Seeder & Fixture Strategy

- **D-16: `infrastructure/seed_data/billing_records.py` extends `_record()` with optional kwargs** (`export_kwh=0`, `peak_kwh=None`, `offpeak_kwh=None`). `_cost()` stays at STD rate. `to_dynamo()` emits extra `{N: ...}` attributes only when non-default. New `_profile_item()` helper emits `{customer_id: ..., month: "PROFILE", hardship_flag: bool}`. `ALL_RECORDS` grows to 48 billing records (4 full personas × 12 months; CUST-006 adds 12) + 1 PROFILE = 61 items. Assertions at the bottom of the file updated to match.
  - **Revise at planner:** CUST-004/005/006 each get 12 months → total is 3 × 12 = 36 new billing + 1 PROFILE = 37 new items added to the existing 36 = 73 items total. Confirm exact count during planning.
- **D-17: Seeder chunking against DynamoDB's 25-items-per-BatchWriteItem cap must be verified.** Open item for researcher: inspect `infrastructure/foundation_stack.py` seeder construct — how does the current 36-item seed actually get written? If BatchWriteItem, it must already be chunked OR it's using a different API (e.g., per-item PutItem loop). If chunking is missing, Phase 11 adds it. Post-verification: CDK synth asserts chunked shape; live `cdk deploy CustomerTariff` on scratch stack seeds 73 items successfully.
- **D-18: Fixtures live in `tests/conftest.py` alongside existing v2.0 fixtures.** New entries: `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response` (all matching the existing `{green: {...}, cheapest: {...}}` byte-exact shape), plus `mock_cust006_hardship = {"hardship": True, "customer_id": "CUST-006"}`. One file, one pattern, pytest auto-discovery preserved.
- **D-19: Usage arrays for CUST-004/005 are engineered via target-equation solver** (pre-commit script, NOT committed to repo — output is the Python constants). For CUST-004: solve `(net_kwh_avg × (STD_rate - SOL_rate)) + export_kwh_avg × fit_rate = 70` for Cheapest, analogous for Green; pick avg values, distribute across 12 months with solar-shaped seasonal variation. For CUST-005: solve `peak_kwh_avg × (STD_rate - EV_peak) + offpeak_kwh_avg × (STD_rate - EV_offpeak) = 60` for Cheapest analogous for Green; 30/70 peak/off-peak split; EV-charging seasonal variation. Researcher writes the solver in `.planning/phases/11-new-personas-tariff-archetypes/` scratch space; planner treats its output (usage + peak + offpeak + export arrays + exact SOL/EV-TOU rates) as locked constants. **Verified STD=0.32 (not 0.34 as earlier draft assumed); solver v2 locked constants: SOL `rate=0.23, fit_rate=0.08`; EV-TOU `peak=0.40, offpeak=0.08`; CUST-004 net_avg=667 / export_avg=200; CUST-005 total_avg=583.33 / peak_avg=175 / offpeak_avg=408.33; CUST-006 usage_avg=200. See `scratch/target_equation_solver_v2.py` + locked byte-exact fixtures table in RESEARCH.md §Code Examples.**

- **D-20: CUST-004 `cost_usd` computed against `net_kwh` (not gross `usage_kwh`).** For solar records (`export_kwh > 0`), `_cost(net_kwh)`. For flat records (v2.0 personas + CUST-006, `export_kwh = 0`), `_cost(usage_kwh)` — same result since `net_kwh = usage_kwh` by definition. Rationale: reflects what the customer actually pays on STD baseline (D-04: STD does NOT credit export for solar personas), matches research recommendation. Informational field only; SAV-03 never reads it.

- **D-21: PROFILE sentinel-SK row filtering happens inside `get_billing_history`, not in `simulate_savings_pure`.** Add `items = [i for i in items if i["month"] != "PROFILE"]` immediately after the DynamoDB query returns, before `sorted(items, key=lambda x: x["month"])`. Single point of correctness — downstream consumers (`simulate_savings_pure`, future agent tools in Phase 13/14) stay PROFILE-unaware. Test `test_get_billing_history_cust006` asserts `len == 12` (month rows only, PROFILE excluded).

### Claude's Discretion

- Exact monthly usage curve shapes within the engineered avgs (seasonal variation pattern for solar-peak summer / EV-peak winter) — as long as avg hits the target.
- Whether to compute `net_kwh` at record-creation time in `_record()` vs store both and derive — both acceptable.
- Test organisation: add new test file `tests/test_sav03_byte_exact_v3.py` OR extend `tests/test_simulate_savings.py` with 3 new persona parametrisations — either works as long as v2.0 fixtures are exercised against the refactored function.

### Folded Todos

None — no pending todos matched phase 11 scope at discussion time.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Roadmap

- `.planning/ROADMAP.md` §"Phase 11: New Personas + Tariff Archetypes" — phase goal, success criteria (5 items), invariant ownership statement.
- `.planning/REQUIREMENTS.md` §"Personas & Data (DATA / REC)" — DATA-04, DATA-05, DATA-06, DATA-07, REC-04, REC-05 requirement IDs with exact acceptance language.
- `.planning/REQUIREMENTS.md` §"Locked Decisions" — LD-1 through LD-7 (LD-1 build order, LD-5 PROD-01 scope, LD-6 freeze ceremony are the load-bearing ones for Phase 11 constraints).
- `.planning/PROJECT.md` §"Current Milestone: v3.0" — target features, engineered demo-data framing.
- `.planning/STATE.md` §"Invariants the v3.0 roadmap must preserve" — SAV-03 extension, tariff_plans.json duplication source-of-truth, stack-policy lift ceremony.

### Research (v3.0)

- `.planning/research/SUMMARY.md` — executive summary + LD-1..LD-7 + Phase 1 (DATA-04 + REC-04) build plan + open questions Q7/Q8/Q11/Q12.
- `.planning/research/ARCHITECTURE.md` §Q1 (bill-shock threshold, informs Phase 13 only), §Q2 (hardship-flag storage, PROFILE SK prefix — relevant here), §5 (TOU dispatcher style recommendation).
- `.planning/research/FEATURES.md` §4 Table Stakes — DATA-04 / REC-04 feature scoping, engineered savings framing.
- `.planning/research/PITFALLS.md` M1 (`tariff_plans.json` drift byte-equality gate), M2 (non-reproducible seed — scratch stack `cdk destroy+deploy` rehearsal), m3 (hardship_flag default=False on existing personas — prevent NULL confusion), C5 (Strands fabrication signature — cross-persona canary; Phase 13 primarily but the byte-exact discipline lands here), C6 (stack-policy lift+reapply ceremony), C7 (Chesterton's-Fence refactor risk on `simulate_savings_pure`).
- `.planning/research/STACK.md` §"Summary of v3.0 Stack Deltas" — Phase 11 touches `CustomerTariff` stack (seeder + Tools Lambda asset) only; `CustomerTariffAgent` + `CustomerTariffApi` untouched this phase.

### Load-bearing project-level docs

- `CLAUDE.md` §"Critical invariants — break these and the demo dies" — SAV-03 (LLM never does arithmetic), REC-03 (both tracks always returned), D-04 (never-500), `tariff_plans.json` duplication (`lambda/` vs `infrastructure/seed_data/` byte-equality gate), frozen-lockfile contract (Phase 11 does NOT bump any deps — Phase 15 owns the single permitted bump).
- `CLAUDE.md` §"Code layout pointers" — tariff catalog duplication note, persona fixture naming convention in `tests/conftest.py`, `infrastructure/seed_data/billing_records.py` structure.
- `CLAUDE.md` §"Things to know before changing things" — region hardcoded, frozen lockfiles, stack-policy lift ceremony required for `CustomerTariff` update.
- `.planning/milestones/v2.0-phases/` retrospectives — Sonnet 4.6 tool-use regression precedent (Phase 06.1) for SAV-03 canary discipline when extending tool math.

### Source code to read before touching

- `lambda/handler.py` — `simulate_savings_pure` (lines 60–118), `_validate_customer_id`, existing handler entry points.
- `lambda/tariff_plans.json` — source of truth for plan catalog; 4 plans today → 6 plans after this phase.
- `infrastructure/seed_data/tariff_plans.json` — must stay byte-equal to `lambda/tariff_plans.json`; existing pytest gate covers this.
- `infrastructure/seed_data/billing_records.py` — current 36-item structure, `_record()` + `to_dynamo()` + `ALL_RECORDS` + `DYNAMO_RECORDS` + assertions.
- `infrastructure/foundation_stack.py` — seeder custom resource (open item D-17: verify chunking against 25-item cap).
- `tests/conftest.py` — existing `mock_savings_response`, `mock_marcus_response`, `mock_elena_response` fixtures for byte-exact pattern.
- `DEMO-RUNBOOK.md` — freeze ceremony, scratch-stack test pattern that Phase 11 must preserve.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`_record(customer_id, month, usage_kwh)` in `billing_records.py`:** Extend with optional kwargs (`export_kwh=0`, `peak_kwh=None`, `offpeak_kwh=None`) rather than creating new record factory.
- **`to_dynamo(record)` in `billing_records.py`:** DynamoDB wire-format serializer — extend to emit optional attributes only when non-default. Pattern already proven at CDK deploy time.
- **`_cost(usage_kwh)` in `billing_records.py`:** Stays at STD rate; historical `cost_usd` is realism fluff (never read by savings math per DATA-03). Don't touch.
- **`_MONTHS` array:** Fiscal year Apr 2025 → Mar 2026; new personas use same array for consistency.
- **`projected_monthly_cost(plan)` closure inside `simulate_savings_pure`:** Single extension point for the `plan_type` dispatcher (D-12). All new branches land here.
- **Existing pytest byte-equality gate for `tariff_plans.json`** between `lambda/` and `infrastructure/seed_data/` — extend by re-running on 6-plan catalog, no new test needed.
- **`conftest.py` `mock_*_response` fixture pattern:** Matched byte-for-byte in new `mock_cust004/005/006_response` fixtures.

### Established Patterns

- **Source-of-truth duplication:** `tariff_plans.json` lives in two places; byte-equality test is the contract. Edit both in the same commit.
- **Pure-helper-plus-handler:** `simulate_savings_pure` + `simulate_savings` wrapper — new `get_hardship_flag_pure` follows the same shape (pure, injectable table client, offline-testable).
- **Bottom-of-file invariant assertions:** `billing_records.py` asserts length + averages at import time — mirror this for new personas.
- **Engineered savings targets locked in Python constants, reverse-engineered from equations, not eyeballed** (Sarah's 500 kWh avg was solved from DEMO-02 $30/$55; CUST-004/005 follow same ceremony).
- **Single-commit byte-equality contract:** when `lambda/tariff_plans.json` changes, `infrastructure/seed_data/tariff_plans.json` changes in the same commit.

### Integration Points

- `lambda/handler.py::simulate_savings_pure` — extended with `plan_type` dispatcher.
- `lambda/handler.py` — new pure helper `get_hardship_flag_pure(customer_id, table_client)`.
- `lambda/tariff_plans.json` + `infrastructure/seed_data/tariff_plans.json` — SOL + EV-TOU plan entries added (byte-equal).
- `infrastructure/seed_data/billing_records.py` — CUST-004, CUST-005, CUST-006 usage arrays; export_kwh/peak_kwh/offpeak_kwh optional kwargs; PROFILE item helper; `ALL_RECORDS`/`DYNAMO_RECORDS` grow; assertions update.
- `infrastructure/foundation_stack.py` — seeder custom resource: verify chunking against 25-item BatchWriteItem cap (D-17).
- `tests/conftest.py` — new fixtures (`mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship`).
- `tests/` — new pytest asserting v2.0 byte-exact AND new persona byte-exact AND PROFILE discoverability AND tariff_plans.json byte-equality with 6-plan catalog.

### Non-integration points (do NOT touch this phase)

- `agent/agent.py` — untouched; no new tool wiring until Phase 13.
- `api_lambda/handler.py` — untouched; no detection update until Phase 14.
- `ui/` — untouched; no UI changes for Phase 11.
- `CustomerTariffAgent` stack / `CustomerTariffApi` stack — no lift required. Only `CustomerTariff` stack (Tools Lambda asset + seeder) gets the lift-and-reapply ceremony.
- `agent/providers.py` — does not exist yet; Phase 12 creates it.
- `requirements.txt` / `requirements-dev.txt` / `ui/package-lock.json` — frozen lockfiles untouched this phase. Phase 15 owns the single permitted dep bump.

</code_context>

<specifics>
## Specific Ideas

- **Engineered savings targets are crisp round numbers:** $30/$55 (Sarah), ~$40/$70 (CUST-004), ~$35/$60 (CUST-005). The $30→$40→$35 progression keeps all five personas visually scannable on the demo surface.
- **CUST-006 naming:** Hardship persona — keep the name/domain details (e.g., household shape) plausible but modest. Dignity-first framing per research (Phase 14 owns the narrative but Phase 11 seeds the data). No specific demographic markers; just a real-looking 12-month usage curve.
- **Solar shape "looks like" real solar:** summer months show lower net_kwh (high self-consumption + export), winter months show higher net_kwh (less production). CUST-005 EV shape shows off-peak-heavy (~70% offpeak via overnight charging), winter skew (less off-peak efficiency in cold weather).
- **Seeder chunking verification is a pre-plan must-do** — if `infrastructure/foundation_stack.py` seeder is a 36-item BatchWriteItem, it's already illegally over the 25-item cap OR it's doing something chunked-by-accident. This is a fragility researcher must surface before planning tries to 73-item the payload.

</specifics>

<deferred>
## Deferred Ideas

- **`persona_class` field on PROFILE item** (solar/ev/standard/hardship) — useful for Phase 13 bill-shock dispatch and DOC-03 narrative, but not required this phase. Defer to Phase 12 or 13 when the consuming code lands.
- **`display_name` / `segment` / other customer-profile attributes on PROFILE item** — UI doesn't consume them today; Phase 11 keeps the PROFILE surface minimal.
- **Convert legacy TOU plan to carry explicit `peak_rate` + `offpeak_rate` fields** — half-useful (v2.0 personas still have no peak_kwh/offpeak_kwh to apply them to). Defer until/unless a Sarah/Marcus/Elena TOU demo trick is wanted.
- **Lambda-backed seeder replacing `CfnCustomResource AwsSdkCall` pattern** — bigger architectural change; current pattern works at 36 items and should still work at 73 if chunked. Defer.
- **Separate `customer-profile` DynamoDB table** — cleaner normalisation but adds CFN resource; single-table design wins for demo scope.
- **Plan-eligibility / persona-class filtering for Green/Cheapest selection** — clean per-persona story but couples plans to personas; v3.0 sticks with open-catalog selection by plan_type + green_score + projected_cost.
- **Reviewed Todos (not folded):** None — no pending todos matched phase 11 scope.

</deferred>

---

*Phase: 11-new-personas-tariff-archetypes*
*Context gathered: 2026-04-28*

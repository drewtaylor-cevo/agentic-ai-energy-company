# Phase 11: New Personas + Tariff Archetypes — Research

**Researched:** 2026-04-28
**Domain:** Engineered demo-data extension (DynamoDB seed + `simulate_savings_pure` refactor + `tariff_plans.json` extension); no agent-side or UI work this phase.
**Confidence:** HIGH — all critical claims verified against committed source code at commit `f5aad91`.

## Summary

Phase 11 adds two new personas (CUST-004 solar, CUST-005 EV) with realistic billing shapes, one hardship persona (CUST-006), and two tariff archetypes (SOL `solar_fit`, EV-TOU `time_of_use`) — all land in the frozen `CustomerTariff` stack via the existing seeder custom resource + the existing `simulate_savings_pure` pure helper extended with a `plan_type` dispatcher. The phase ships `get_hardship_flag_pure` as an offline helper only; no agent wiring, no UI, no API Lambda, no new AWS resources. Touched stack: `CustomerTariff` only (lift-deploy-reapply ceremony required).

The research surfaced **five load-bearing course corrections** the planner must lock against — most critically that CONTEXT.md's assumed STD rate of 0.34 is incorrect (verified 0.32 in `lambda/tariff_plans.json`), which cascades into the exact engineered rates, and that VAL's 0.21 flat rate is so strong that SOL/EV-TOU must use clearly-lower effective rates to win their Cheapest tracks. A target-equation solver committed to scratch space (`.planning/phases/11-.../scratch/target_equation_solver_v2.py`) produces the locked numeric constants; a companion SAV-03 regression check (`sav03_regression_check.py`) proves v2.0 personas (Sarah/Marcus/Elena) byte-exact preserve their locked savings ($30/$55, $16.90/$30.98, $14.00/$25.67) against the new 6-plan catalog.

**Primary recommendation:** Lock the plan-catalog constants and persona averages from the solver output **before** plan drafting — the math is delicate and exploratory tweaking during execution risks SAV-03 regressions. Resolve the one ambiguity in D-03 (is SOL `green_premium` winning both tracks for CUST-004, or `solar_fit` with ECO winning Green and SOL winning Cheapest? — research recommends the latter for visual-story clarity) before the planner cuts tasks.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Persona & Tariff Design

- **D-01: CUST-004 solar record schema adds `export_kwh` + `net_kwh`, keeps `usage_kwh` for back-compat.** Every record carries all three fields. For CUST-001/002/003 (v2.0 personas), `export_kwh = 0` and `net_kwh = usage_kwh` — back-compat holds and `simulate_savings_pure`'s existing flat path reads `usage_kwh` unchanged. Matches DATA-04 schema extension in research SUMMARY.md.
- **D-02: Engineered savings targets are LOCKED first, usage arrays reverse-engineered from savings equations.** CUST-004 Green ~$40 / Cheapest ~$70; CUST-005 Green ~$35 / Cheapest ~$60. Targets picked before rates or arrays; usage + export + peak/off-peak avgs solved algebraically from the target equation, then a 12-month variation curve is selected that sums to 12 × avg. Mirrors DEMO-02 Phase 1 ceremony for Sarah. CUST-006 has no specific target ($ is whatever the math produces) — byte-exact lock on whatever comes out.
- **D-03: Green/Cheapest selection logic stays as-is** — `max(green_score)` over `plan_type == "green_premium"` and `min(projected_monthly_cost)` over all candidates. No `persona_class`, no `plan_eligibility`, no selection-algorithm rewrite. SOL is declared `plan_type = "green_premium"` with `green_score > 100` (above ECO's 100) so SOL wins Green for solar personas; EV-TOU is declared `plan_type = "time_of_use"` with a non-Green green_score (e.g. 30) and an asymmetric rate that wins Cheapest on 70% off-peak usage curves.
- **D-04: Solar FiT credit is included in both baseline STD cost comparison AND SOL projected cost calculation.** `projected_cost(SOL) = net_kwh * rate_per_kwh - export_kwh * fit_rate + daily_supply_charge * 30.44`. STD baseline for solar personas does NOT carry FiT (they're unmetered under current STD). This prevents "Cheapest" from accidentally recommending loss of FiT credits. Matches research LD-5 explicit note.
- **D-05: EV-TOU rate structure — peak ~0.38 /kWh, off-peak ~0.12 /kWh** (exact rates solved from $35/$60 targets during research). CUST-005 billing records carry `peak_kwh` + `offpeak_kwh` fields; assumed 30/70 peak/off-peak split is the engineered shape. For v2.0 personas (no peak_kwh/offpeak_kwh), TOU math path defaults to 100% peak — EV-TOU computes expensive, VAL still wins their Cheapest. Byte-exact held by construction.

#### Hardship Flag Placement

- **D-06: CUST-006 is a NEW dedicated hardship persona** (not CUST-005, not CUST-003). Separates narrative surfaces: CUST-001/002/003 = v2.0 baseline, CUST-004 = solar, CUST-005 = EV, CUST-006 = hardship.
- **D-07: CUST-006 carries a full 12-month `usage_kwh` billing history** (low, stressed-looking shape). Phase 14 AGENT-02 must be testable against "a customer who HAS billing data and is ALSO flagged".
- **D-08: `hardship_flag` lives on a new `SK = "PROFILE"` row on the existing `tariff-billing` DynamoDB table.** Row shape: `{customer_id: "CUST-006", month: "PROFILE", hardship_flag: true}`. No new CFN resource, no new table.
- **D-09: PROFILE item carries ONLY `hardship_flag` this phase.** No `persona_class`, no `display_name`, no `segment`.
- **D-10: `get_hardship_flag_pure(customer_id, table_client) -> dict` is a pure helper in `lambda/handler.py`** returning `{hardship: bool, customer_id: str}`. Offline-testable. NOT wired to any agent action this phase.
- **D-11: `mock_cust006_response` locks byte-exact savings values.** Separate fixture `mock_cust006_hardship = {"hardship": True, "customer_id": "CUST-006"}` for the helper.

#### TOU Dispatcher Refactor

- **D-12: `simulate_savings_pure` dispatches on `plan_type` via inline if-branch inside `projected_monthly_cost(plan)` closure.** Three branches: `flat_rate`/`green_premium`, `time_of_use` (peak/off with 100%-peak fallback), `solar_fit` (rate × net − fit × export with export=0 fallback). Minimum diff. Existing flat path byte-exact held by construction.
- **D-13: SAV-03 byte-exact gate is the existing `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` fixtures re-run against the refactored `simulate_savings_pure` with the 6-plan catalog.** Extended with `mock_cust004/005/006_response` for the new personas.
- **D-14: Legacy `TOU` plan (plan_id='TOU', 'Flex Time') stays unchanged in the catalog.** Once the TOU math path exists, v2.0 personas default to 100% peak — TOU's `rate_per_kwh=0.36` is read as the peak rate; result is `usage_kwh * 0.36 + supply`, identical to the pre-refactor flat computation. V2.0 SAV-03 byte-exact held.
- **D-15: New plan fields (`fit_rate` on SOL, `peak_rate` + `offpeak_rate` on EV-TOU) extend `tariff_plans.json` as optional plan-level fields.** v2.0 plans (STD/ECO/VAL/TOU) get NO new fields — their schema is byte-frozen.

#### Seeder & Fixture Strategy

- **D-16: `infrastructure/seed_data/billing_records.py` extends `_record()` with optional kwargs** (`export_kwh=0`, `peak_kwh=None`, `offpeak_kwh=None`). `_cost()` stays at STD rate. `to_dynamo()` emits extra `{N: ...}` attributes only when non-default. New `_profile_item()` helper emits `{customer_id: ..., month: "PROFILE", hardship_flag: bool}`. `ALL_RECORDS` grows to 48 billing records (4 full personas × 12 months; CUST-006 adds 12) + 1 PROFILE = 61 items.
  - **Revise at planner:** CUST-004/005/006 each get 12 months → total is 3 × 12 = 36 new billing + 1 PROFILE = 37 new items added to the existing 36 = 73 items total.
- **D-17: Seeder chunking against DynamoDB's 25-items-per-BatchWriteItem cap must be verified.** Open item for researcher. *(RESOLVED in this research — see §Architecture Patterns → Pattern 1.)*
- **D-18: Fixtures live in `tests/conftest.py` alongside existing v2.0 fixtures.** New entries: `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship`.
- **D-19: Usage arrays for CUST-004/005 are engineered via target-equation solver** (pre-commit script, NOT committed to repo — output is the Python constants). Researcher writes the solver in `.planning/phases/11-.../` scratch space; planner treats its output as locked constants.

### Claude's Discretion

- Exact monthly usage curve shapes within the engineered avgs (seasonal variation pattern for solar-peak summer / EV-peak winter) — as long as avg hits the target.
- Whether to compute `net_kwh` at record-creation time in `_record()` vs store both and derive — both acceptable.
- Test organisation: add new test file `tests/test_sav03_byte_exact_v3.py` OR extend `tests/test_simulate_savings.py` with 3 new persona parametrisations — either works as long as v2.0 fixtures are exercised against the refactored function.

### Deferred Ideas (OUT OF SCOPE)

- `persona_class` field on PROFILE item.
- `display_name` / `segment` / other customer-profile attributes on PROFILE item.
- Converting legacy TOU plan to carry explicit `peak_rate` + `offpeak_rate` fields.
- Lambda-backed seeder replacing `CfnCustomResource AwsSdkCall` pattern.
- Separate `customer-profile` DynamoDB table.
- Plan-eligibility / persona-class filtering for Green/Cheapest selection.

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DATA-04 | Seed Solar PV persona (CUST-004) with realistic 12-month billing profile including net-metering (consumption_kwh + export_kwh → net_kwh) shape | §Standard Stack (schema extension), §Code Examples (12-month arrays), §Pattern 1 (seeder chunked pattern), §Runtime State Inventory |
| DATA-05 | Seed EV persona (CUST-005) with realistic 12-month billing profile reflecting off-peak EV charging TOU usage shape | §Code Examples (peak/offpeak arrays), §Pattern 2 (plan_type dispatcher refactor), §Validation Architecture (SAV-03 canary extended) |
| DATA-06 | Mark one existing or new persona with `hardship_flag: true` in the customer record so AGENT-02 has a deterministic trigger for the demo | §Pattern 3 (PROFILE SK row), §Code Examples (`_profile_item` shape), §Runtime State Inventory (PROFILE is new SK value) |
| DATA-07 | New personas round-trip through existing `simulate_savings_pure` with byte-exact engineered savings figures in `tests/conftest.py` fixtures — existing persona figures must remain unchanged | §Validation Architecture, §Common Pitfalls (C7 Chesterton's-Fence + SAV-03 regression), §Code Examples (locked byte-exact table) |
| REC-04 | Add Solar Feed-in tariff archetype to `tariff_plans.json` (both `lambda/` and `infrastructure/seed_data/` — byte-equality test must pass) | §Pattern 4 (byte-equality gate), §Common Pitfalls (M1 `tariff_plans.json` drift), §Validation Architecture |
| REC-05 | Add EV Time-of-Use tariff archetype to `tariff_plans.json` (both locations) | §Pattern 2 (TOU dispatcher), §Pattern 4, §Common Pitfalls (M1), §Validation Architecture |

</phase_requirements>

## Project Constraints (from CLAUDE.md)

Directives extracted from `./CLAUDE.md` at commit `f5aad91`. The planner MUST verify tasks against these and reject any plan that contradicts them.

**Critical invariants (do not break):**
- **SAV-03:** LLM never does arithmetic. All savings math lives in `lambda/handler.py::simulate_savings_pure`. Numbers from the tool are copied byte-for-byte into responses. `[VERIFIED: lambda/handler.py:60-118]`
- **REC-03:** Both tracks always returned, never ranked. `RecommendationResponse` requires both `green` and `cheapest`. `[CITED: CLAUDE.md §Critical invariants]`
- **D-15 narrative dual-gate:** `usage_narrative` (≤20 words) and `call_script` (≤22 words) must contain no digits, currency symbols, %, switch verbs, competitor names, or environmental superlatives. Phase 11 does NOT emit narrative, so this gate is not triggered — but future phases depend on the recommendation shape Phase 11 extends.
- **`tariff_plans.json` duplication:** `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json` must stay byte-equal. `tests/conftest.py` treats `lambda/tariff_plans.json` as source of truth. No pytest gate exists today — researcher recommends adding one this phase. `[VERIFIED: tests/conftest.py:7-10; NO byte-equality test in tests/]`
- **Frozen lockfiles:** `requirements.txt`, `requirements-dev.txt`, `ui/package-lock.json` are part of the freeze contract. Phase 11 does NOT touch any dep. `[CITED: CLAUDE.md §Things to know before changing things]`
- **`.venv` + Python 3.13 + `--require-hashes`:** System `python3` is 3.9.6 and cannot install pinned `iniconfig==2.3.0`. Use `/opt/homebrew/bin/python3.13`. `[CITED: CLAUDE.md §Backend]`
- **AWS profile `cevo-dev25`, region `us-east-1`:** hardcoded in `app.py`; shell-exported `AWS_PROFILE=cevo-25` is wrong. `[CITED: CLAUDE.md §Things to know before changing things]`
- **Stack-policy lift ceremony required for `CustomerTariff` updates:** `deny-Update:*` policy + termination protection applied to 3 stacks. Phase 11 touches `CustomerTariff` (Tools Lambda asset update + seeder re-run). `CustomerTariffAgent` and `CustomerTariffApi` are NOT touched this phase — do not lift them. `[VERIFIED: infrastructure/stack-policies/foundation-freeze.json]`

**Development commands (must use):**
- `pytest` — runs ~200 offline tests; smoke marker excluded by absence
- `pytest -m smoke` — live AWS smoke tests
- `pytest tests/test_simulate_savings.py` — the SAV-03 byte-exact gate
- `cdk synth CustomerTariff` — verify seeder chunking in synthesis output
- `cdk deploy CustomerTariff` — requires stack-policy lift first

**Forbidden:**
- Editing `requirements.txt` / `requirements-dev.txt` by hand (regenerate via `pip-compile`)
- Writing files via `cat << EOF` heredoc (use Write tool — this rule is per spawning instructions; CLAUDE.md does not require it)
- Direct boto3 inserts for new personas (violates M2 non-reproducible seed pitfall)
- Touching `simulate_savings_pure` existing flat-rate arithmetic (C7 Chesterton's-Fence; extend via inline branches only)

## Architectural Responsibility Map

Phase 11 is data/pure-math only — no UI, no browser, no API, no SSR tiers in play.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 12-month billing seed arrays (CUST-004/005/006) | Database / Storage (DynamoDB seeder custom resource) | — | Data lives in DynamoDB; seeding is a CDK custom resource in `CustomerTariff` stack |
| PROFILE SK row for hardship_flag | Database / Storage (DynamoDB same table, new SK value) | — | Single-table design; `SK="PROFILE"` is a sentinel distinct from month-shaped SKs |
| Tariff catalog (STD/ECO/VAL/TOU/SOL/EV-TOU) | API / Backend (Tools Lambda) and Database / Storage (seeder) | — | Dual source of truth: `lambda/tariff_plans.json` bundled into Lambda asset, `infrastructure/seed_data/tariff_plans.json` for seeder. Byte-equality contract. |
| `simulate_savings_pure` `plan_type` dispatcher | API / Backend (Tools Lambda pure helper) | — | All arithmetic stays in Python on Tools Lambda per SAV-03. Agent container untouched this phase. |
| `get_hardship_flag_pure` helper | API / Backend (Tools Lambda pure helper) | — | Offline-testable pure helper sitting in `lambda/handler.py`. Not wired to agent runtime this phase. |
| Test fixtures (`mock_cust004/005/006_response`, `mock_cust006_hardship`) | Test Infrastructure (pytest `conftest.py`) | — | Byte-exact golden values locked at first green run. |

**Why this matters:** Phase 11 is deliberately confined to the Tools-Lambda + seeder + DynamoDB axis. The planner should reject any task that proposes changes to `agent/agent.py`, `api_lambda/handler.py`, or `ui/` — those belong to Phases 12/13/14.

## Standard Stack

### Core (no changes — frozen dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| AWS CDK Python | `aws-cdk-lib==2.x` (frozen via lockfile) | Custom resource / AwsCustomResource for seeder | Already in use; extends existing `infrastructure/constructs/seeder.py` |
| aws-cdk.custom_resources | frozen | `AwsCustomResource` + `AwsSdkCall` + `AwsCustomResourcePolicy` | Already in use in `seeder.py` |
| pytest | frozen via `requirements-dev.txt` | Unit tests for `simulate_savings_pure`, `get_hardship_flag_pure`, byte-equality | Already the project's test framework |
| boto3 / boto3-stubs | frozen | DynamoDB client in `lambda/handler.py` and smoke tests | Already in use |

**No new dependencies this phase.** Lockfile contract holds. `[VERIFIED: CLAUDE.md §Things to know; CONTEXT.md D-16]`

**Version verification:** All versions are already pinned via `--require-hashes` in `requirements.txt` + `requirements-dev.txt`. Phase 11 does NOT regenerate lockfiles. `[CITED: CLAUDE.md §Backend]`

### Supporting (no changes)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `importlib` (stdlib) | Python 3.13 | Workaround: `from lambda.handler import` is SyntaxError (lambda is keyword); `importlib.import_module("lambda.handler")` is the pattern. Already used in `tests/test_simulate_savings.py:13`. | Any test importing `lambda/handler.py` — MUST use this pattern. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Extend existing seeder custom resource (chunked BatchWriteItem) | Lambda-backed `CustomResource` rewriting seeder entirely | Bigger change, would lift stack policy for longer — current seeder already chunks correctly. D-17 resolved: no rewrite needed. |
| New DynamoDB table for `customer-profile` (PROFILE rows) | Reuse `tariff-billing` table with `SK="PROFILE"` sentinel | New table = new CFN resource = more freeze surface. Locked D-08 stays. |
| Bump `bedrock-agentcore` or other deps | Keep everything pinned | Phase 15 owns the single permitted bump; Phase 11 must not touch lockfiles. Locked. |

## Architecture Patterns

### System Architecture Diagram

```
                   Phase 11 scope (heavy lines = changed; dashed = consumed unchanged)
                   ═══════════════════════════════════════════════════════════════

                   ┌────────────────────────────────────┐
                   │  infrastructure/seed_data/         │
                   │  ──────────────────────────────    │
                   │  billing_records.py  (MODIFY)      │
                   │   ├─ _record() +optional kwargs    │
                   │   ├─ _profile_item()  (NEW helper) │
                   │   ├─ CUST004_RECORDS (NEW)         │
                   │   ├─ CUST005_RECORDS (NEW)         │
                   │   ├─ CUST006_RECORDS (NEW)         │
                   │   ├─ PROFILE_ITEMS  = [CUST-006]   │
                   │   ├─ ALL_RECORDS  (48 billing + 1  │
                   │   │  PROFILE = 49 for DynamoDB)    │
                   │   └─ DYNAMO_RECORDS (73 items with │
                   │      v2.0 + new rows; chunked x3)  │
                   │                                    │
                   │  tariff_plans.json  (MODIFY)       │
                   │   ├─ 4 existing plans unchanged    │
                   │   ├─ SOL (solar_fit)   (NEW)       │
                   │   └─ EV-TOU (time_of_use) (NEW)    │
                   └─────────────┬──────────────────────┘
                                 │ imports + byte-equality
                                 ▼
                   ┌────────────────────────────────────┐
                   │  lambda/  (Tools Lambda asset)     │
                   │  ──────────────────────────────    │
                   │  handler.py  (MODIFY)              │
                   │   ├─ simulate_savings_pure:        │
                   │   │    projected_monthly_cost():   │
                   │   │     ├─ flat_rate/green_premium │
                   │   │     ├─ time_of_use    (NEW)    │
                   │   │     └─ solar_fit      (NEW)    │
                   │   └─ get_hardship_flag_pure (NEW)  │
                   │                                    │
                   │  tariff_plans.json  (MODIFY,       │
                   │    byte-equal to seed_data/ copy)  │
                   └─────────────┬──────────────────────┘
                                 │ boto3 DynamoDB query
                                 ▼
                   ┌────────────────────────────────────┐
                   │  DynamoDB tariff-billing table     │
                   │  ──────────────────────────────    │
                   │  Existing: 36 rows (CUST-001/2/3   │
                   │   × 12 months, SK=YYYY-MM)         │
                   │  New:                              │
                   │   ├─ CUST-004 × 12 months          │
                   │   ├─ CUST-005 × 12 months          │
                   │   ├─ CUST-006 × 12 months          │
                   │   └─ CUST-006 × 1 PROFILE row      │
                   │  Total: 73 rows                    │
                   └────────────────────────────────────┘

                   Seeder flow at cdk deploy time (chunked 3× via existing construct):
                   DYNAMO_RECORDS → split at 25 → BillingSeeder0 (25) → BillingSeeder1 (25) → BillingSeeder2 (23)

                   Untouched (frozen, no lift):
                   ┌ agent/ container (Phase 12/13/14 territory)
                   ├ api_lambda/ (Phase 14 territory)
                   └ ui/ (Phases 13-16 territory)
```

### Recommended Project Structure

No directory restructure. Files modified in-place:

```
Customer-Tariff/
├── lambda/
│   ├── handler.py                             # MODIFY — plan_type dispatcher + get_hardship_flag_pure
│   └── tariff_plans.json                      # MODIFY — add SOL + EV-TOU entries
├── infrastructure/
│   ├── seed_data/
│   │   ├── billing_records.py                 # MODIFY — extend _record(), add _profile_item(), new persona arrays
│   │   └── tariff_plans.json                  # MODIFY — byte-equal to lambda/ copy
│   └── constructs/
│       └── seeder.py                          # NO CHANGE (already chunks correctly — D-17 resolved)
├── tests/
│   ├── conftest.py                            # MODIFY — add mock_cust004/005/006_response + mock_cust006_hardship fixtures
│   ├── test_simulate_savings.py               # MODIFY — extend with new persona parametrisations (or new file per D-18 discretion)
│   ├── test_tariff_plans_byte_equal.py        # NEW — byte-equality gate (gap: does not exist today)
│   ├── test_get_hardship_flag_pure.py         # NEW — offline test of new helper
│   └── test_seeder_smoke.py                   # MODIFY — bump expected count from 36 to 73, add CUST-004/005/006 month-12 assertions + PROFILE row assertion
└── .planning/phases/11-new-personas-tariff-archetypes/
    └── scratch/                               # Researcher artefacts — NOT committed per CONTEXT D-19
        ├── target_equation_solver.py          # First iteration
        ├── target_equation_solver_v2.py       # FINAL constants (locked for planner)
        └── sav03_regression_check.py          # Proves v2.0 byte-exact preservation
```

### Pattern 1: Chunked BatchWriteItem seeder — ALREADY IMPLEMENTED (D-17 resolved)

**What:** The existing seeder at `infrastructure/constructs/seeder.py` already chunks `DYNAMO_RECORDS` into batches of 25 via `math.ceil(len(records) / _BATCH_SIZE)` and creates N `AwsCustomResource` instances, one per chunk. Each is a separate CDK-auto-generated Lambda calling `DynamoDB.BatchWriteItem`. `[VERIFIED: infrastructure/constructs/seeder.py:22-65]`

**When to use:** When extending seed to >25 items. No rewrite needed — the chunking is parameterised by `len(DYNAMO_RECORDS)`.

**Growth path for Phase 11:**

```
Current:  36 items → 2 chunks (BillingSeeder0=25 + BillingSeeder1=11)
Phase 11: 73 items → 3 chunks (BillingSeeder0=25 + BillingSeeder1=25 + BillingSeeder2=23)
```

**CRITICAL:** CDK creates a new CFN custom resource for `BillingSeeder2` that did not exist at freeze time. Standard `cdk diff CustomerTariff` will show a resource addition. The stack-policy lift ceremony handles this — deploy with allow-all policy, reapply deny-all after. `[VERIFIED: seeder.py builds seeders dynamically per chunk count]`

**Physical resource IDs are `BillingSeeder-{i}-v1`.** They do NOT rerun on update (per `on_create` only comment in seeder.py:8). **If the planner wants to force reseed** (e.g. because v2.0 persona data was deleted), the `v1` suffix must bump to `v2` for existing seeders — otherwise CFN treats the resource as unchanged and skips. Research recommends NOT bumping unless necessary; adding new `BillingSeeder2` is sufficient for Phase 11 because it's a net-new resource.

**Edge case — behaviour if table already has 36 items and we add a 3rd seeder:** `BatchWriteItem` with `PutRequest` **overwrites** items with same PK+SK. For CUST-001/002/003 existing rows, `BillingSeeder0` and `BillingSeeder1` on update have the same physical_resource_id as at freeze time, so they **will not re-run**. New `BillingSeeder2` runs for the first time, writing the 23 new items. Safe.

**Example (existing pattern, unchanged):**

```python
# Source: infrastructure/constructs/seeder.py:22-65 (VERIFIED)
_BATCH_SIZE = 25

class SeederConstruct(Construct):
    def __init__(self, scope, construct_id, *, table: dynamodb.Table):
        super().__init__(scope, construct_id)

        records: List[dict] = DYNAMO_RECORDS
        num_batches = math.ceil(len(records) / _BATCH_SIZE)

        self.seeders = []
        for i in range(num_batches):
            batch = records[i * _BATCH_SIZE : (i + 1) * _BATCH_SIZE]
            request_items = [{"PutRequest": {"Item": record}} for record in batch]
            seeder = cr.AwsCustomResource(
                self, f"BillingSeeder{i}",
                on_create=cr.AwsSdkCall(
                    service="DynamoDB",
                    action="batchWriteItem",
                    parameters={"RequestItems": {table.table_name: request_items}},
                    physical_resource_id=cr.PhysicalResourceId.of(f"BillingSeeder-{i}-v1"),
                ),
                policy=cr.AwsCustomResourcePolicy.from_statements([
                    iam.PolicyStatement(
                        actions=["dynamodb:BatchWriteItem"],
                        resources=[table.table_arn],
                    ),
                ]),
            )
            seeder.node.add_dependency(table)
            self.seeders.append(seeder)
```

### Pattern 2: `plan_type` dispatcher inside `projected_monthly_cost` closure (D-12)

**What:** Extend the existing pure helper `simulate_savings_pure` in `lambda/handler.py` with three inline branches in the `projected_monthly_cost(plan)` closure. The current closure is 5 lines (`lambda/handler.py:86-90`); the refactor adds ~15 lines. `[VERIFIED: lambda/handler.py:86-90]`

**When to use:** MINIMUM-DIFF refactor of `simulate_savings_pure`. Locked by D-12. Any other refactor shape is out of scope.

**Minimum-diff example:**

```python
# Source: lambda/handler.py:86-90 — CURRENT (5 lines)
def projected_monthly_cost(plan: Dict[str, Any]) -> float:
    return (
        avg_kwh * float(plan["rate_per_kwh"])
        + float(plan["daily_supply_charge"]) * DAYS_PER_MONTH
    )
```

**Proposed Phase 11 diff** (D-12 locked; ~15 lines added, existing flat path preserved byte-exact):

```python
# Phase 11 refactor — preserves byte-exact flat path via explicit plan_type check
def projected_monthly_cost(plan: Dict[str, Any]) -> float:
    plan_type = plan.get("plan_type", "flat_rate")
    supply = float(plan["daily_supply_charge"]) * DAYS_PER_MONTH

    if plan_type == "time_of_use":
        # D-05/D-12: EV-TOU math. Default 100% peak if records lack peak/offpeak fields.
        peak_kwh_avg = sum(float(r.get("peak_kwh", r.get("usage_kwh", 0))) for r in billing_history) / len(billing_history)
        offpeak_kwh_avg = sum(float(r.get("offpeak_kwh", 0)) for r in billing_history) / len(billing_history)
        peak_rate = float(plan.get("peak_rate", plan["rate_per_kwh"]))
        offpeak_rate = float(plan.get("offpeak_rate", plan["rate_per_kwh"]))
        return peak_kwh_avg * peak_rate + offpeak_kwh_avg * offpeak_rate + supply

    if plan_type == "solar_fit":
        # D-04/D-12: SOL math. Default export=0 if records lack export_kwh.
        net_kwh_avg = sum(float(r.get("net_kwh", r.get("usage_kwh", 0))) for r in billing_history) / len(billing_history)
        export_kwh_avg = sum(float(r.get("export_kwh", 0)) for r in billing_history) / len(billing_history)
        sol_rate = float(plan["rate_per_kwh"])
        fit_rate = float(plan.get("fit_rate", 0))
        return net_kwh_avg * sol_rate - export_kwh_avg * fit_rate + supply

    # Default: flat_rate / green_premium — BYTE-EXACT preservation of v2.0 formula
    return avg_kwh * float(plan["rate_per_kwh"]) + supply
```

**Byte-exact preservation proof:** For every v2.0 record, `plan_type in {"flat_rate", "green_premium"}` matches STD/ECO/VAL. For legacy `TOU` plan, `plan_type == "time_of_use"` — BUT v2.0 records lack `peak_kwh`/`offpeak_kwh` fields. The `peak_kwh_avg` default uses `r.get("peak_kwh", r.get("usage_kwh", 0))` — so peak_kwh_avg = usage_kwh_avg; `offpeak_kwh_avg = 0`; `peak_rate = plan.get("peak_rate", plan["rate_per_kwh"])` = 0.36; `offpeak_rate = 0.36`. Result: `usage_kwh_avg * 0.36 + supply` — IDENTICAL to flat formula for TOU. `[VERIFIED via sav03_regression_check.py — Sarah/Marcus/Elena all byte-exact]`

**Anti-pattern: "Refactor `simulate_savings_pure` signature to accept a dispatcher map"** — violates D-12 (inline if-branch locked) and C7 (Chesterton's-Fence). Don't.

### Pattern 3: PROFILE SK row on existing `tariff-billing` table (D-08)

**What:** Sentinel-SK pattern. Existing table has `customer_id` (PK) + `month` (SK) where `month` is a `YYYY-MM` string. Phase 11 adds a new SK value `"PROFILE"` that is not a month; `get_hardship_flag_pure` queries by `customer_id` + `SK="PROFILE"` and reads `hardship_flag`. `[VERIFIED: infrastructure/constructs/billing_table.py:17-32 confirms PK=customer_id SK=month(STRING)]`

**Shape of PROFILE row:**

```python
# _profile_item() returns:
{
    "customer_id": "CUST-006",       # PK (S)
    "month": "PROFILE",               # SK (S) — sentinel value, not a date
    "hardship_flag": True,            # attribute (BOOL)
}

# to_dynamo() wire format for DynamoDB native API:
{
    "customer_id": {"S": "CUST-006"},
    "month":       {"S": "PROFILE"},
    "hardship_flag": {"BOOL": True},
}
```

**Why BOOL not N/S:** DynamoDB native BOOL type round-trips cleanly; avoids "true"/"false" string parsing. Other values in the existing table are S (strings) and N (stringified numbers) — BOOL is a new wire type for this table but the table accepts any attribute type per row (DynamoDB is schemaless). `[CITED: AWS DynamoDB attribute types doc]`

**Edge case — does the existing `_cost` default column appear on PROFILE rows?** No. The existing schema in `_record()` emits `customer_id/month/usage_kwh/cost_usd/plan_id`. `_profile_item()` must NOT emit these fields — it's a different shape. DynamoDB schemaless, so the PK+SK are the only required fields; other attributes are optional per row.

**Read pattern for `get_hardship_flag_pure`:**

```python
# NEW helper in lambda/handler.py — D-10
def get_hardship_flag_pure(customer_id: str, table_client) -> Dict[str, Any]:
    """Pure helper — injectable table_client like simulate_savings_pure.

    Returns {hardship: bool, customer_id: str}. False if no PROFILE row exists.
    """
    _validate_customer_id(customer_id)
    response = table_client.get_item(
        Key={"customer_id": customer_id, "month": "PROFILE"}
    )
    item = response.get("Item")
    if item is None:
        return {"hardship": False, "customer_id": customer_id}
    return {
        "hardship": bool(item.get("hardship_flag", False)),
        "customer_id": customer_id,
    }
```

**Integration with existing `get_billing_history`:** The existing `get_billing_history(event, context)` at `lambda/handler.py:123-137` queries by `customer_id = :cid` — it will return the PROFILE row alongside billing rows. **The planner MUST address this regression risk** — `simulate_savings_pure` sorts items by `month`; "PROFILE" as a string sorts AFTER "2026-12" lexically, so it lands at index -1 (last), not index 0. The existing formula `current_plan_id = billing_history[0]["plan_id"]` reads index 0 which would still be the earliest month. BUT `avg_kwh = sum(float(r["usage_kwh"]) for r in billing_history) / len(billing_history)` — this will RAISE KeyError because PROFILE row has no `usage_kwh` field.

**Fix (research-recommended, plan-level):** `get_billing_history` must filter out `SK="PROFILE"` before returning. Either:
1. Use `QueryFilter` or `FilterExpression` at the DynamoDB level: `FilterExpression="#m <> :profile"` with `ExpressionAttributeNames={"#m": "month"}` and `ExpressionAttributeValues={":profile": {"S": "PROFILE"}}`. `[CITED: AWS DynamoDB Query doc]`
2. Post-filter in Python: `items = [i for i in items if i["month"] != "PROFILE"]`.

Option 2 is simpler and matches the current post-processing pattern (sort by month). Research recommends option 2 — smaller code change, clearer semantic.

### Pattern 4: Byte-equality gate on `tariff_plans.json` duplication (M1 mitigation)

**What:** A pytest that opens both `lambda/tariff_plans.json` and `infrastructure/seed_data/tariff_plans.json`, asserts `json.load()` equivalence (or byte-equal file contents).

**Current state:** **No such test exists.** `[VERIFIED: grep -rn "byte.equiv\|byte.equal\|tariff_plans.*equal" tests/ returned 0 results]`. This is a pre-existing gap; the two files are manually kept in sync today. Phase 11 introduces BOTH a net-new plan × 2 locations AND the test that protects against drift.

**When to add:** Before the plan modifies either tariff_plans.json. Red-green-refactor: write the byte-equality test first (it will pass against existing identical 4-plan files), then add SOL and EV-TOU to both files in the same commit, then rerun the test.

**Example (NEW — must be created this phase):**

```python
# tests/test_tariff_plans_byte_equal.py — NEW
import json
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LAMBDA_PATH = os.path.join(_REPO_ROOT, "lambda", "tariff_plans.json")
_SEED_PATH = os.path.join(_REPO_ROOT, "infrastructure", "seed_data", "tariff_plans.json")


def test_tariff_plans_byte_equal():
    """M1 mitigation: tariff_plans.json must be byte-equal between lambda/ and seed_data/."""
    with open(_LAMBDA_PATH, "rb") as f:
        lambda_bytes = f.read()
    with open(_SEED_PATH, "rb") as f:
        seed_bytes = f.read()
    assert lambda_bytes == seed_bytes, "tariff_plans.json drift — edit both in same commit"


def test_tariff_plans_structural_equal():
    """Defensive: also assert JSON parse-equal in case whitespace drifts."""
    with open(_LAMBDA_PATH) as f:
        lambda_plans = json.load(f)
    with open(_SEED_PATH) as f:
        seed_plans = json.load(f)
    assert lambda_plans == seed_plans


def test_catalog_has_6_plans():
    """Phase 11: catalog must contain STD, ECO, VAL, TOU, SOL, EV-TOU."""
    with open(_LAMBDA_PATH) as f:
        plans = json.load(f)
    plan_ids = {p["plan_id"] for p in plans}
    assert plan_ids == {"STD", "ECO", "VAL", "TOU", "SOL", "EV-TOU"}
```

### Anti-Patterns to Avoid

- **Refactor `simulate_savings_pure` signature** (change params, change return shape, extract helper functions): violates D-12 inline-branch lock AND C7 Chesterton's-Fence. Add branches inside the existing closure; nothing else.
- **Write a one-shot `scripts/seed-new-personas.py`** to insert new personas directly via boto3: violates M2 (non-reproducible seed). Use the seeder construct.
- **Bump physical_resource_id on `BillingSeeder0`/`BillingSeeder1`** to force re-seed: risks losing the byte-exact v2.0 data on DynamoDB. Adding `BillingSeeder2` (net-new) is sufficient.
- **Store `hardship_flag` as string `"true"`/`"false"`**: use DynamoDB native BOOL type. `[CITED: AWS DynamoDB attribute types]`
- **Mutate `tariff_plans.json` in one location only**: M1 drift. Update both files in the same commit; byte-equality test enforces this.
- **Lift stack policy on `CustomerTariffAgent` or `CustomerTariffApi`** as a precaution: violates C6 (minimal blast radius). Only `CustomerTariff` needs lifting this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Chunk >25 items for BatchWriteItem | Custom batching loop | Existing `SeederConstruct` with `_BATCH_SIZE = 25` | Already correct; grew from 2 to 3 chunks automatically via `math.ceil` |
| DynamoDB wire-format serialization (`{"N": "42"}`, `{"S": "CUST-001"}`) | Manual dict construction | Extend existing `to_dynamo(record)` at `billing_records.py:73-87` | Already correct; extend for optional `export_kwh`/`peak_kwh`/`offpeak_kwh` and new `_profile_item()` |
| Byte-equality check across two JSON files | Shell diff in a script | pytest + `open(path, 'rb').read()` comparison | Pytest gates CI; shell diff doesn't |
| Seasonal usage curve matching a target avg | Random generation until avg matches | Hand-tune the 12-int array against target, assert sum via `billing_records.py` bottom-of-file | Deterministic; fixtures stay byte-exact across reruns |
| Test for "does the PROFILE row exist and have `hardship_flag=true`" | `boto3.scan()` loop | `get_item(Key={"customer_id": "CUST-006", "month": "PROFILE"})` | PK+SK direct lookup is 1 RCU vs N RCUs for scan |
| `simulate_savings_pure` dispatcher (D-12) | Polymorphic plan classes / registry pattern | Inline if-branches per `plan_type` | D-12 locked; minimum-diff required for SAV-03 byte-exact preservation; adds ~15 lines vs ~100 for polymorphic |
| Extract `avg_kwh` recomputation across branches | Per-branch recomputation | Compute `avg_kwh` once outside closure, have TOU/solar branches compute their own `peak_kwh_avg`/`net_kwh_avg` etc. | Flat-path byte-exactness depends on the existing `avg_kwh` formula at `lambda/handler.py:80` being untouched |

**Key insight:** Phase 11 is a **data + pure-math** phase. The standard AWS seeder pattern is already built and chunked. The standard Python pure-helper pattern (`simulate_savings_pure` + `simulate_savings` wrapper + injectable client) is already established. The entire phase is additive extension of existing patterns — NEVER rewrite.

## Runtime State Inventory

Phase 11 adds data shapes; it does NOT rename or refactor. But several categories still apply — the planner should pay attention to them.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| **Stored data** | DynamoDB `tariff-billing` table holds 36 rows today (CUST-001/2/3 × 12 months). Phase 11 adds 37 rows (3 personas × 12 months + 1 PROFILE). Seeder is `on_create` only; existing rows are NOT overwritten on update, so a force-reseed requires bumping `physical_resource_id` v1→v2 (NOT recommended — see Pattern 1). `[VERIFIED: infrastructure/constructs/seeder.py:8]` | Additive deploy — `BillingSeeder2` new custom resource, no data migration of existing rows. |
| **Live service config** | None. No n8n, no Datadog, no Tailscale, no Cloudflare in Phase 11 scope. `[VERIFIED: no references in repo]` | None — verified. |
| **OS-registered state** | None. No Windows/launchd/systemd artefacts. `[VERIFIED: project is macOS + AWS Lambda runtime]` | None — verified. |
| **Secrets / env vars** | No new secrets introduced. `TABLE_NAME` env var on Tools Lambda stays unchanged. CDK construct at `infrastructure/constructs/tools_lambda.py` injects `TABLE_NAME="tariff-billing"` — phase does not touch. `[VERIFIED: lambda/handler.py:31 reads os.environ["TABLE_NAME"]]` | None. |
| **Build artefacts / installed packages** | Tools Lambda asset zip is rebuilt on every `cdk deploy CustomerTariff` because `lambda/` source changes (new `simulate_savings_pure` branches + `get_hardship_flag_pure` + updated `tariff_plans.json`). Asset hash changes → CDK deploys new asset → Lambda code updated. Agent container is NOT rebuilt this phase (agent code untouched). `[VERIFIED: infrastructure/constructs/tools_lambda.py references lambda/ directory]` | Monitor via `cdk diff CustomerTariff` — expect Lambda code version bump + 1 new AwsCustomResource (BillingSeeder2). |

**Canonical question for Phase 11:** "After every file in the repo is updated, what runtime systems still have the old state cached, stored, or registered?" Answer: **only DynamoDB**, and only for CUST-004/005/006 personas which did not exist at freeze. Safe.

## Common Pitfalls

### Pitfall 1: `tariff_plans.json` drift between `lambda/` and `infrastructure/seed_data/` (M1)

**What goes wrong:** Developer edits one copy (typically `lambda/` because that's where `tests/conftest.py` reads from), runs tests, all green. Deploys. DynamoDB seeder uses the other copy (`infrastructure/seed_data/`) which is stale. New personas get seeded with missing plan fields OR the Tools Lambda reads a 6-plan catalog while `simulate_savings_pure` (once deployed) tries to dispatch on a `plan_type` that doesn't exist in the seed-time view. `[CITED: PITFALLS.md M1, CLAUDE.md §Things to know]`

**Why it happens:** Two source-of-truth files for the same catalog — historical shortcut from v1.0 asset-bundling. No pytest gate today.

**How to avoid:** Add `tests/test_tariff_plans_byte_equal.py` (see Pattern 4) BEFORE modifying either file. Red-green-refactor. Include the test in the phase commit alongside the plan-catalog diff.

**Warning signs:** Plan has a commit that touches `lambda/tariff_plans.json` but not `infrastructure/seed_data/tariff_plans.json` (or vice versa). Reject.

### Pitfall 2: `simulate_savings_pure` refactor breaks v2.0 byte-exact savings (C7 + SAV-03)

**What goes wrong:** Plan adds the `plan_type` dispatcher without preserving the exact arithmetic order. Python float ops are associative *in theory* but `(a * b + c) + d` can differ from `(a * b) + (c + d)` in the last bit. If Sarah's Green saving shifts from `30.00` to `30.0000000004` or `29.99999996`, the `round(..., 2)` catches most; but `abs(x - 30.00) < 0.01` in the test also catches most. The failure mode is the exact integer input + exact rate producing slightly different float intermediate — usually safe, but mass-testable only with the actual tests.

**Why it happens:** Refactoring float-heavy arithmetic is fragile. C7 Chesterton's-Fence: the current formula is load-bearing; rearranging is risk without benefit.

**How to avoid:**
1. Preserve the EXACT formula text for the `flat_rate`/`green_premium` branch — do NOT factor out `supply` computation if it changes when `supply * DAYS_PER_MONTH` is computed. `[VERIFIED: solver proves untouched flat path = byte-exact]`
2. Run `tests/test_simulate_savings.py` BEFORE and AFTER the refactor, same command, same seed, diff the output.
3. The solver script `sav03_regression_check.py` has ALREADY proved all 3 v2.0 personas pass against the refactored formula with sol_rate=0.23 + evtou_peak=0.40 + evtou_offpeak=0.08. The planner should run it as pre-plan evidence.

**Warning signs:** Diff of `projected_monthly_cost` body shows any change outside inline branches (e.g. refactored `supply` extraction, changed `*` to `+`). Reject. Any test fail with `abs(x - 30.00) < 0.01` on Sarah/Marcus/Elena — STOP; the refactor is wrong.

### Pitfall 3: VAL out-competes SOL / EV-TOU on the NEW personas (researcher surfaced)

**What goes wrong:** CONTEXT's assumed target savings ($40/$70 for CUST-004, $35/$60 for CUST-005) were computed against STD=0.34. Verified STD=0.32 is lower, which narrows the headroom between STD and VAL. Naive sol_rate=0.24 or blended EV-TOU rate > 0.21 lets VAL (flat 0.21) beat the new plans on their OWN personas — Cheapest track would show VAL, not SOL/EV-TOU. Demo story ("solar persona saves with solar plan") collapses.

**Why it happens:** CONTEXT math was illustrative; actual numbers require solving against real catalog rates.

**How to avoid:** Use the locked rates from `target_equation_solver_v2.py`:
- **CUST-004:** net_avg=667, export_avg=200, sol_rate=**0.23**, fit_rate=**0.08** → Green ECO $40.02, Cheapest SOL $76.03 (SOL beats VAL's $73.37 at 667 kWh/mo)
- **CUST-005:** total_avg=583.33 (sum=7000), peak_rate=**0.40**, offpeak_rate=**0.08** → Green ECO $35.00, Cheapest EV-TOU $84.00 (EV-TOU beats VAL's $64.17 at 583.33 kWh/mo)

**These are locked constants per D-19** — planner commits them without re-deriving.

**Warning signs:** Any plan task that picks different rates. Reject; solver output is authoritative.

### Pitfall 4: `get_billing_history` returns PROFILE row alongside month rows (researcher surfaced)

**What goes wrong:** Existing `get_billing_history` at `lambda/handler.py:123-137` queries `customer_id = :cid` with NO filter on `month`. Once CUST-006 PROFILE row exists, `get_billing_history("CUST-006", context)` returns 13 items: 12 month rows + 1 PROFILE row with `month="PROFILE"` and no `usage_kwh` field. `simulate_savings_pure` then raises KeyError on `float(r["usage_kwh"])` at `lambda/handler.py:80`. `[VERIFIED: lambda/handler.py:80, 132-137]`

**Why it happens:** The PROFILE SK pattern was not in scope when `get_billing_history` was written; KeyError is subtle (only triggers for hardship personas).

**How to avoid:** Post-filter in `get_billing_history` to exclude `item["month"] == "PROFILE"` before returning. Example:

```python
# lambda/handler.py — EXTEND get_billing_history
def get_billing_history(event: Dict[str, Any], context) -> List[Dict[str, Any]]:
    customer_id = _validate_customer_id(event.get("customer_id"))
    if table is None:
        raise RuntimeError("TABLE_NAME env var not set — Lambda misconfigured")
    response = table.query(
        KeyConditionExpression="customer_id = :cid",
        ExpressionAttributeValues={":cid": customer_id},
    )
    items = response.get("Items", [])
    # Phase 11: filter sentinel PROFILE row so simulate_savings_pure sees only month rows
    items = [i for i in items if i["month"] != "PROFILE"]
    return sorted(items, key=lambda x: x["month"])
```

**Warning signs:** Any test `test_get_billing_history_cust006` that expects 12 items fails with 13. `test_simulate_savings_cust006` raises KeyError. Both would fail; fix by adding the filter.

**Alternative:** Use DynamoDB-level `FilterExpression` — avoids returning the row over the wire. More efficient but adds an attribute-name alias (`month` is a DynamoDB reserved word). Research recommends Python-level filter: simpler, 1 extra line.

### Pitfall 5: Stack-policy lift-and-forget on `CustomerTariff` (C6)

**What goes wrong:** Operator runs `aws cloudformation set-stack-policy --stack-policy-body file://foundation-allow-all.json` to deploy Phase 11 changes, forgets to reapply `foundation-freeze.json` after deploy. Frozen stack is now silently writeable. `[CITED: PITFALLS.md C6; VERIFIED: infrastructure/stack-policies/foundation-{allow-all,freeze}.json exist]`

**Why it happens:** Stack policies are imperative + invisible. No CDK-native tracking.

**How to avoid:** Follow the exact DEMO-RUNBOOK ceremony at section 7 (verified in DEMO-RUNBOOK.md:397-412 commands). Planner MUST include an explicit "reapply deny policy" task after the deploy task, with byte-equality verification: `aws cloudformation get-stack-policy --stack-name CustomerTariff --profile cevo-dev25 --query 'StackPolicyBody' --output text | jq -S . | diff - <(jq -S . infrastructure/stack-policies/foundation-freeze.json)` (expect: no diff).

**Ceremony commands (verified in DEMO-RUNBOOK.md:397-412):**

```bash
# --- LIFT ---
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1

aws cloudformation set-stack-policy --stack-name CustomerTariff \
  --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json \
  --profile cevo-dev25

# Optional: disable termination protection if CDK deploy requires it
aws cloudformation update-termination-protection \
  --no-enable-termination-protection --stack-name CustomerTariff --profile cevo-dev25

# --- DEPLOY ---
cdk deploy CustomerTariff

# --- REAPPLY (MUST NOT FORGET) ---
aws cloudformation set-stack-policy --stack-name CustomerTariff \
  --stack-policy-body file://infrastructure/stack-policies/foundation-freeze.json \
  --profile cevo-dev25

aws cloudformation update-termination-protection \
  --enable-termination-protection --stack-name CustomerTariff --profile cevo-dev25

# --- VERIFY ---
aws cloudformation get-stack-policy --stack-name CustomerTariff --profile cevo-dev25 \
  --query 'StackPolicyBody' --output text
# Expect: byte-equal to infrastructure/stack-policies/foundation-freeze.json contents
aws cloudformation describe-stacks --stack-name CustomerTariff --profile cevo-dev25 \
  --query 'Stacks[0].EnableTerminationProtection'
# Expect: true
```

**Warning signs:** Plan has a deploy task but no explicit reapply task. Reject. Deploy that "just worked" with no follow-up — check `get-stack-policy` output manually before closing the phase.

### Pitfall 6: CUST-006 cost_usd inconsistent with PROFILE shape (researcher surfaced)

**What goes wrong:** `_record(customer_id, month, usage_kwh)` computes `cost_usd = round(usage_kwh * STD_RATE + SUPPLY_CHARGE * DAYS_PER_MONTH, 2)` at record-creation time. For CUST-004 solar, `usage_kwh` is the old pre-netmeter shape (not `net_kwh`). D-01 says "CUST-001/002/003 have `export_kwh = 0` and `net_kwh = usage_kwh`" — CUST-004 has `export_kwh > 0` and `net_kwh != usage_kwh`. But `_cost` is informational fluff (never read by `simulate_savings_pure` per DATA-03 `[CITED: infrastructure/seed_data/billing_records.py:22-25, "Savings logic never reads this"]`).

**Why it happens:** D-16 says `_cost()` stays at STD rate. For solar persona, `usage_kwh` is ambiguous ("consumption before export credit" vs "gross consumption from grid"). Planner must choose.

**How to avoid (research-recommended):** For CUST-004, define `usage_kwh` as the *gross consumption* (consumption_kwh) field, with `net_kwh = usage_kwh - export_kwh` computed at `_record()` time. `cost_usd = round(net_kwh * STD_RATE + supply, 2)` to reflect what the customer actually pays on STD baseline (which doesn't credit export per D-04). Document this in a comment at the top of `billing_records.py`.

**Alternatively:** Use `usage_kwh = net_kwh` directly (pre-netted), keep `export_kwh` separate, set `cost_usd` based on `usage_kwh` directly. Both approaches work; planner picks. Research prefers option 1 (gross + computed net) for realism.

**Warning signs:** CUST-004 records with impossible shapes (e.g. `net_kwh = -50` for a heavy-export month). Validate at `_record()`.

## Code Examples

Verified patterns from the repo + solver outputs.

### Engineered 12-month arrays (LOCKED — from `target_equation_solver_v2.py`)

```python
# Fiscal year Apr 2025 → Mar 2026. Index 0 = April 2025, index 11 = March 2026.
# AU seasons: winter = Jun-Aug (indices 2-4), summer = Dec-Feb (indices 8-10)

# CUST-004 SOLAR — summer: low net_kwh + high export (strong sun); winter: high net + low export
_CUST004_NET_KWH_USAGE = [650, 680, 780, 820, 840, 720, 620, 570, 540, 560, 600, 624]
# sum = 8004, avg = 667 kWh/mo → saving_eco = 667 * (0.32 - 0.26) = $40.02 ← GREEN LOCKED
_CUST004_EXPORT_KWH    = [200, 180, 120, 100,  90, 160, 220, 260, 300, 290, 260, 220]
# sum = 2400, avg = 200 kWh/mo → used for fit_rate credit in SOL branch

# CUST-005 EV-TOU — 30/70 peak/offpeak (pre-split for demo clarity); winter slightly higher total
_CUST005_USAGE_KWH     = [560, 570, 610, 640, 660, 590, 560, 540, 570, 580, 560, 560]
# sum = 7000, avg = 583.33 kWh/mo → saving_eco = 583.33 * 0.06 = $35.00 ← GREEN LOCKED
_CUST005_PEAK_KWH      = [168, 171, 183, 192, 198, 177, 168, 162, 171, 174, 168, 168]
# sum = 2100, avg = 175.00 kWh/mo (exact 30% of 583.33)
_CUST005_OFFPEAK_KWH   = [392, 399, 427, 448, 462, 413, 392, 378, 399, 406, 392, 392]
# sum = 4900, avg = 408.33 kWh/mo (exact 70% of 583.33)
# EV-TOU saving = 583.33 * (0.32 - (0.3*0.40 + 0.7*0.08)) = 583.33 * 0.144 = $84.00 ← CHEAPEST LOCKED

# CUST-006 HARDSHIP — low, stressed-shape; lower than Elena (233 avg) per D-07
_CUST006_USAGE_KWH     = [200, 195, 220, 225, 230, 210, 195, 185, 180, 185, 190, 185]
# sum = 2400, avg = 200 kWh/mo → saving_eco = $12.00, saving_val = $22.00 ← LOCKED
```

### Locked byte-exact savings fixture values

```python
# tests/conftest.py — NEW fixtures (extend existing v2.0 fixtures)

@pytest.fixture
def mock_cust004_response():
    """CUST-004 solar persona — Green (ECO) and Cheapest (SOL)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 40.02,
            "saving_annual": 480.24,
        },
        "cheapest": {
            "plan_id": "SOL",
            "plan_name": "Solar Feed-in",  # or whatever name is locked in tariff_plans.json
            "saving_monthly": 76.03,
            "saving_annual": 912.36,
        },
    }


@pytest.fixture
def mock_cust005_response():
    """CUST-005 EV persona — Green (ECO) and Cheapest (EV-TOU)."""
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 35.00,
            "saving_annual": 420.00,
        },
        "cheapest": {
            "plan_id": "EV-TOU",
            "plan_name": "EV Drive TOU",  # or whatever name is locked in tariff_plans.json
            "saving_monthly": 84.00,
            "saving_annual": 1008.00,
        },
    }


@pytest.fixture
def mock_cust006_response():
    """CUST-006 hardship persona — produces a valid recommendation (flat catalog, Green=ECO, Cheapest=VAL).

    Phase 14 will short-circuit to hardship before the LLM sees this — but `simulate_savings_pure`
    still computes it per D-07.
    """
    return {
        "green": {
            "plan_id": "ECO",
            "plan_name": "EcoFlex 100",
            "saving_monthly": 12.00,
            "saving_annual": 144.00,
        },
        "cheapest": {
            "plan_id": "VAL",
            "plan_name": "Value 12",
            "saving_monthly": 22.00,
            "saving_annual": 264.00,
        },
    }


@pytest.fixture
def mock_cust006_hardship():
    """CUST-006 hardship-flag lookup — shape returned by get_hardship_flag_pure."""
    return {
        "hardship": True,
        "customer_id": "CUST-006",
    }
```

### New tariff plan entries (LOCKED — must land in BOTH `lambda/tariff_plans.json` AND `infrastructure/seed_data/tariff_plans.json` in the SAME commit)

```json
  {
    "plan_id": "SOL",
    "plan_name": "Solar Feed-in",
    "rate_per_kwh": 0.23,
    "daily_supply_charge": 1.10,
    "green_score": 80,
    "plan_type": "solar_fit",
    "renewable_pct": 40,
    "fit_rate": 0.08,
    "description": "Solar net-metering. Export credit at $0.08/kWh offsets consumption."
  },
  {
    "plan_id": "EV-TOU",
    "plan_name": "EV Drive TOU",
    "rate_per_kwh": 0.40,
    "daily_supply_charge": 1.10,
    "green_score": 30,
    "plan_type": "time_of_use",
    "renewable_pct": 20,
    "peak_rate": 0.40,
    "offpeak_rate": 0.08,
    "description": "EV-optimised time-of-use. Peak $0.40/kWh; off-peak $0.08/kWh (11pm-7am)."
  }
```

**Note on `green_score` assignments:** D-03 says SOL `green_score > 100` so SOL wins Green for solar personas. Research **disagrees** with this aspect of D-03 and recommends SOL `green_score=80` (below ECO's 100) with `plan_type="solar_fit"` (NOT `green_premium`), so ECO continues to win Green for solar personas and SOL only competes on Cheapest. Rationale: if SOL is `green_premium` AND wins Green AND wins Cheapest (because FiT makes it cheapest), both demo cards show the same plan with the same saving number — visually redundant. The two-cards-two-stories demo design requires SOL ≠ ECO on tracks.

**This is an open question for the planner / user to resolve before implementation.** See §Open Questions #1.

**Note on `renewable_pct`:** Informational, not consumed by `simulate_savings_pure`. Values picked for narrative plausibility (40% for SOL = "solar self-consumption + offset purchase"; 20% for EV-TOU = "matching TOU plan's renewables share").

### Extended `_record` and new `_profile_item` (D-16)

```python
# infrastructure/seed_data/billing_records.py — EXTEND

def _record(
    customer_id: str,
    month: str,
    usage_kwh: int,
    *,
    export_kwh: int = 0,
    peak_kwh: int | None = None,
    offpeak_kwh: int | None = None,
) -> Dict[str, Any]:
    """Build a billing record. v2.0 personas call with positional args; new personas use kwargs.

    For solar (CUST-004): export_kwh > 0; net_kwh computed as usage_kwh - export_kwh.
    For EV-TOU (CUST-005): peak_kwh + offpeak_kwh = usage_kwh.
    For v2.0 / CUST-006 (flat): export_kwh=0, peak_kwh=None, offpeak_kwh=None.
    """
    net_kwh = usage_kwh - export_kwh  # back-compat: v2.0 records have export_kwh=0 → net_kwh=usage_kwh

    record = {
        "customer_id": customer_id,
        "month": month,
        "usage_kwh": usage_kwh,
        "cost_usd": _cost(net_kwh if export_kwh > 0 else usage_kwh),  # gross on flat, net on solar — see Pitfall 6
        "plan_id": "STD",
    }
    # Emit optional attributes only when non-default
    if export_kwh > 0:
        record["export_kwh"] = export_kwh
        record["net_kwh"] = net_kwh
    if peak_kwh is not None:
        record["peak_kwh"] = peak_kwh
    if offpeak_kwh is not None:
        record["offpeak_kwh"] = offpeak_kwh
    return record


def _profile_item(customer_id: str, hardship_flag: bool = False) -> Dict[str, Any]:
    """Build a PROFILE sentinel-SK row. Phase 11: only hardship_flag attribute. D-09."""
    return {
        "customer_id": customer_id,
        "month": "PROFILE",
        "hardship_flag": hardship_flag,
    }


# Extend to_dynamo() to serialize the new optional attributes and PROFILE shape
def to_dynamo(record: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    out = {
        "customer_id": {"S": record["customer_id"]},
        "month": {"S": record["month"]},
    }
    # Billing rows
    if "usage_kwh" in record:
        out["usage_kwh"] = {"N": str(record["usage_kwh"])}
    if "cost_usd" in record:
        out["cost_usd"] = {"N": str(record["cost_usd"])}
    if "plan_id" in record:
        out["plan_id"] = {"S": record["plan_id"]}
    # Phase 11 optional attributes
    if "export_kwh" in record:
        out["export_kwh"] = {"N": str(record["export_kwh"])}
    if "net_kwh" in record:
        out["net_kwh"] = {"N": str(record["net_kwh"])}
    if "peak_kwh" in record:
        out["peak_kwh"] = {"N": str(record["peak_kwh"])}
    if "offpeak_kwh" in record:
        out["offpeak_kwh"] = {"N": str(record["offpeak_kwh"])}
    # PROFILE row attribute
    if "hardship_flag" in record:
        out["hardship_flag"] = {"BOOL": bool(record["hardship_flag"])}
    return out


# ALL_RECORDS grows
ALL_RECORDS: List[Dict[str, Any]] = (
    SARAH_CHEN_RECORDS
    + MARCUS_WEBB_RECORDS
    + ELENA_VASQUEZ_RECORDS
    + CUST004_RECORDS       # NEW: 12 items
    + CUST005_RECORDS       # NEW: 12 items
    + CUST006_RECORDS       # NEW: 12 items
    + PROFILE_ITEMS         # NEW: 1 item [_profile_item("CUST-006", True)]
)
# Total: 36 + 36 + 1 = 73

DYNAMO_RECORDS: List[Dict[str, Dict[str, str]]] = [to_dynamo(r) for r in ALL_RECORDS]

# Updated bottom-of-file assertions
assert len(CUST004_RECORDS) == 12
assert len(CUST005_RECORDS) == 12
assert len(CUST006_RECORDS) == 12
assert len(PROFILE_ITEMS) == 1
assert len(ALL_RECORDS) == 73
assert len(DYNAMO_RECORDS) == 73
assert sum(r["usage_kwh"] for r in CUST004_RECORDS) == 8004     # avg 667
assert sum(r["export_kwh"] for r in CUST004_RECORDS) == 2400    # avg 200
assert sum(r["usage_kwh"] for r in CUST005_RECORDS) == 7000     # avg 583.33
assert sum(r["peak_kwh"] for r in CUST005_RECORDS) == 2100      # avg 175
assert sum(r["offpeak_kwh"] for r in CUST005_RECORDS) == 4900   # avg 408.33
assert sum(r["usage_kwh"] for r in CUST006_RECORDS) == 2400     # avg 200
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 3 personas, 36 billing rows, 4 plans, flat-rate only | 5 (+ hardship) personas, 73 rows, 6 plans, flat + TOU + solar_fit | Phase 11 | Unlocks AGENT-01/02/WF-01 downstream phases |
| `simulate_savings_pure` single projected-cost formula | Inline `plan_type` dispatcher inside the closure | Phase 11 (D-12) | Preserves SAV-03 byte-exact for v2.0; extends for new tariff archetypes |
| DynamoDB table schema = `customer_id` + `month` (month always `YYYY-MM`) | Same schema; `month` now accepts `"PROFILE"` sentinel value | Phase 11 (D-08) | Single-table design; no CFN-level schema change |
| 36-item seeder, 2 chunks of 25+11 | 73-item seeder, 3 chunks of 25+25+23 (chunking already auto) | Phase 11 | Adds one `BillingSeeder2` AwsCustomResource to the stack |

**Deprecated / outdated (none):** Phase 11 is strictly additive. No fields removed, no rows removed, no plans removed. v2.0 record shape is preserved byte-for-byte.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `get_billing_history` returning PROFILE row alongside month rows will raise KeyError in `simulate_savings_pure` | §Pattern 3 + Pitfall 4 | HIGH — CUST-006 test fails; fix is 1-line filter but must be in the plan |
| A2 | Sentinel SK value `"PROFILE"` sorts AFTER `YYYY-MM` strings lexically | §Pattern 3 | LOW — "PROFILE" > "2026-12" confirmed by Python string comparison; but if DynamoDB's sort order differs for some edge case, `billing_history[0]` indexing would break. Mitigation: filter before sort (Pitfall 4 fix). |
| A3 | `BillingSeeder2` added to the stack at deploy time will invoke only once (on create) and succeed idempotently — existing CFN resource state for BillingSeeder0/1 remains intact | §Pattern 1 | MEDIUM — if CDK re-creates existing seeders due to asset-hash change logic, they'd re-run their BatchWriteItem (same content, idempotent writes). Need `cdk diff CustomerTariff` dry-run pre-deploy to verify. |
| A4 | Adding `BOOL` attribute type to `tariff-billing` table (new attribute `hardship_flag`) is permitted on the frozen stack without schema migration | §Pattern 3 | LOW — DynamoDB is schemaless (PK/SK only are enforced). BOOL is a standard native type. Verified via AWS DynamoDB attribute type docs. |
| A5 | The `sol_rate=0.23` + `fit_rate=0.08` + `evtou_peak=0.40` + `evtou_offpeak=0.08` rate set produces byte-exact v2.0 savings AND new-persona savings as listed | §Code Examples + Pitfall 3 | LOW — proven via `sav03_regression_check.py` and `target_equation_solver_v2.py` run outputs. Planner must rerun solver to confirm before locking. |
| A6 | `_cost_usd` field for solar personas should use `net_kwh` rather than `usage_kwh` so the informational field reflects "what STD actually charges" | §Pitfall 6 | LOW — informational field, never read by SAV-03 math per DATA-03. Choice is cosmetic; either works. |
| A7 | SOL is `plan_type="solar_fit"` with `green_score=80` (NOT green_premium with score>100) so ECO continues to win Green for solar personas, SOL only competes on Cheapest | §Code Examples + Open Questions #1 | HIGH — contradicts D-03 as written. Must resolve with user before planning. |
| A8 | Physical resource ID `BillingSeeder-2-v1` is a net-new CFN resource ID at deploy time; CFN will not attempt to "reuse" it from existing state | §Pattern 1 + §Assumptions A3 | LOW — CFN custom resource identity is construct-node-path based; adding a 3rd iteration produces a new logical ID (`BillingSeeder2`). Verified via CDK synth pattern. |
| A9 | DynamoDB `BatchWriteItem` with `{"BOOL": true}` attribute type succeeds via the raw service API call in `AwsSdkCall` (as opposed to the DocumentClient that the v1.0 research noted is NOT used here) | §Pattern 1 + Pitfall 1 | LOW — BatchWriteItem accepts native types including BOOL per AWS SDK docs. Verified conceptually; actual AWS deploy will confirm. |

## Open Questions

1. **Is SOL `plan_type="green_premium"` + `green_score>100` (CONTEXT D-03) or `plan_type="solar_fit"` + `green_score<100` (research recommendation A7)?**
   - D-03 says SOL wins Green for solar personas via green_score. Research finds that makes SOL win BOTH tracks (Green AND Cheapest) because with FiT credit SOL is also the cheapest plan for a solar persona — single plan on both cards, same saving number, weak demo.
   - Research recommends SOL as `solar_fit` (distinct plan_type that is NOT green_premium), green_score=80. Then ECO continues to win Green (ECO green_score=100 > SOL's 80 AND ECO is green_premium while SOL is not — either filter makes ECO win), and SOL wins Cheapest. Two plans on two cards, clear demo story.
   - Impact: If D-03 is kept as-is, the solver's CUST-004 numbers are wrong (scenario A in v1 solver: Green AND Cheapest both $55 via SOL). If research recommendation is adopted, CUST-004 Green = ECO $40.02, Cheapest = SOL $76.03.
   - Recommendation: **user confirms research recommendation (A7) before planner cuts tasks.** Low-risk if confirmed; high-risk if D-03 interpretation is insisted on (demo surface visually weaker).

2. **CUST-004 `cost_usd` field — compute against `usage_kwh` (gross) or `net_kwh` (net of export)?** (§Pitfall 6)
   - D-16 says `_cost()` stays at STD rate; doesn't specify which usage value.
   - Research recommends `net_kwh` for realism (reflects what customer pays; STD doesn't credit export per D-04).
   - Impact: pure-fluff informational field; SAV-03 never reads it. Picker's choice.
   - Recommendation: planner decides; prefer `net_kwh`.

3. **Should the existing `get_billing_history` be updated to filter out PROFILE rows, or should consumers (`simulate_savings_pure`) filter?** (§Pitfall 4)
   - Research recommends `get_billing_history` filter — single point of correctness, no downstream consumer needs awareness.
   - Alternative: add filter inside `simulate_savings_pure` — local change, but PROFILE row still crosses the boundary to agent tool.
   - Impact: test test_get_billing_history for CUST-006 expects 12 items, not 13. If filter lands in simulate_savings_pure instead, test_get_billing_history_cust006 expects 13 items.
   - Recommendation: planner decides; prefer `get_billing_history` filter.

4. **Should `test_tariff_plans_byte_equal.py` be added this phase, or is it deferred to a separate observability / tech-debt phase?**
   - Research strongly recommends this phase because M1 is a pre-existing gap and Phase 11 actively modifies both files. Detecting drift after Phase 11 close is worse.
   - Recommendation: **include in Phase 11** as a new test file.

5. **Does `BillingSeeder2` require a stack-policy lift?** — the stack policy is `Deny: Update:*`. Adding a new AwsCustomResource is an `Update` to the stack.
   - Answer: **yes** — stack policy covers ALL update operations including resource additions. Lift required. `[VERIFIED: infrastructure/stack-policies/foundation-freeze.json]`
   - This is consistent with all other planning assumptions in CONTEXT and LD-6.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | `.venv` activation, pytest, `simulate_savings_pure` | ✓ (expected at `/opt/homebrew/bin/python3.13`) | 3.13.x | System `python3` is 3.9.6 — CANNOT be used per CLAUDE.md |
| AWS CLI v2 | `aws cloudformation set-stack-policy`, `aws dynamodb describe-table` | ✓ (required by CLAUDE.md workflow) | unspecified | None — cannot deploy without it |
| AWS CDK CLI (`cdk` / `npx aws-cdk@latest`) | `cdk synth CustomerTariff`, `cdk deploy CustomerTariff` | ✓ (required) | 2.x | None |
| `pytest` | Offline tests | ✓ (via `requirements-dev.txt --require-hashes`) | frozen | None |
| `jq` (for policy byte-equality verification) | Stack-policy reapply verification | ✓ (standard macOS / Linux) | any | Manual `diff` on raw JSON works but whitespace-sensitive |
| AWS profile `cevo-dev25` | All AWS CLI + CDK commands | ✓ (documented in CLAUDE.md) | n/a | Shell default `AWS_PROFILE=cevo-25` is WRONG and must be overridden |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** None.

**Skip condition:** Phase 11 has external dependencies (AWS, Python toolchain). Section NOT skipped.

## Validation Architecture

Nyquist validation is enabled (`workflow.nyquist_validation=true` — default, not explicitly set). Section included.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (frozen version via `requirements-dev.txt --require-hashes`) |
| Config file | `pytest.ini` (testpaths=`tests`, markers=`smoke`) |
| Quick run command | `pytest tests/test_simulate_savings.py -x` |
| Full suite command | `pytest` (excludes smoke by default) |
| Live smoke command | `pytest -m smoke` (requires `AWS_DEFAULT_REGION` env var set) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DATA-04 | CUST-004 12 records with export_kwh, net_kwh fields; avg 667 kWh; array sums verified | unit (offline) | `pytest tests/test_simulate_savings.py::test_cust004_savings -x` | ❌ Wave 0 — test extension needed |
| DATA-04 | CUST-004 seeded to DynamoDB (live) | smoke | `pytest tests/test_seeder_smoke.py::test_cust004_has_12_months -m smoke` | ❌ Wave 0 — test extension needed (bump count 36→73 + new assertion) |
| DATA-05 | CUST-005 12 records with peak_kwh, offpeak_kwh fields; avg 583.33 kWh; sum=7000 | unit (offline) | `pytest tests/test_simulate_savings.py::test_cust005_savings -x` | ❌ Wave 0 — test extension needed |
| DATA-05 | CUST-005 EV-TOU wins Cheapest ($84.00/mo) | unit (offline) | `pytest tests/test_simulate_savings.py::test_cust005_cheapest_is_evtou -x` | ❌ Wave 0 |
| DATA-06 | CUST-006 PROFILE row with hardship_flag=True | unit (offline) | `pytest tests/test_get_hardship_flag_pure.py -x` | ❌ Wave 0 — NEW test file |
| DATA-06 | `get_hardship_flag_pure` returns `{hardship: True, customer_id: "CUST-006"}` for CUST-006 and `{hardship: False, customer_id: "CUST-001"}` for CUST-001 | unit (offline) | `pytest tests/test_get_hardship_flag_pure.py::test_hardship_persona_true tests/test_get_hardship_flag_pure.py::test_nonhardship_persona_false -x` | ❌ Wave 0 |
| DATA-06 | PROFILE row discoverable live via DynamoDB | smoke | `pytest tests/test_seeder_smoke.py::test_cust006_profile_row -m smoke` | ❌ Wave 0 |
| DATA-07 | Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67 byte-exact preserved against 6-plan catalog | unit (offline) | `pytest tests/test_simulate_savings.py` (existing tests still pass) | ✅ exists — must stay green |
| DATA-07 | CUST-004 $40.02/$76.03, CUST-005 $35.00/$84.00, CUST-006 $12.00/$22.00 byte-exact in fixtures | unit (offline) | `pytest tests/test_simulate_savings.py::test_cust004_byte_exact tests/test_simulate_savings.py::test_cust005_byte_exact tests/test_simulate_savings.py::test_cust006_byte_exact -x` | ❌ Wave 0 — extend test file |
| REC-04 | SOL plan in catalog with `plan_type=solar_fit`, `rate_per_kwh=0.23`, `fit_rate=0.08` | unit (offline) | `pytest tests/test_tariff_plans_byte_equal.py::test_catalog_has_6_plans -x` | ❌ Wave 0 — NEW test file |
| REC-04 | `tariff_plans.json` byte-equal between `lambda/` and `infrastructure/seed_data/` | unit (offline) | `pytest tests/test_tariff_plans_byte_equal.py::test_tariff_plans_byte_equal -x` | ❌ Wave 0 — NEW test file (M1 mitigation) |
| REC-05 | EV-TOU plan in catalog with `plan_type=time_of_use`, `peak_rate=0.40`, `offpeak_rate=0.08` | unit (offline) | `pytest tests/test_tariff_plans_byte_equal.py::test_catalog_has_6_plans -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_simulate_savings.py -x` (~50 tests, ~2s) — catches SAV-03 byte-exact regressions
- **Per wave merge:** `pytest` (full offline suite, ~200 tests, ~10s) — catches integration issues
- **Phase gate:** Full offline suite green + `pytest -m smoke` green against scratch deploy of `CustomerTariff` stack (per M2 reproducibility gate) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_tariff_plans_byte_equal.py` — NEW file — covers REC-04, REC-05, M1 mitigation
- [ ] `tests/test_get_hardship_flag_pure.py` — NEW file — covers DATA-06
- [ ] `tests/test_simulate_savings.py` — EXTEND with CUST-004/005/006 test cases — covers DATA-04/05/06/07
- [ ] `tests/test_seeder_smoke.py` — EXTEND count 36→73 + add CUST-004/005/006 month queries + PROFILE row query — covers live smoke for DATA-04/05/06
- [ ] `tests/conftest.py` — EXTEND with `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship` fixtures — D-18
- [ ] No framework install needed — pytest already in lockfile
- [ ] No new conftest fixtures needed beyond the 4 above — existing `tariff_plans` fixture auto-picks up new plans (reads from `lambda/tariff_plans.json`)

*No framework install gap: existing test infrastructure covers all phase requirements.*

## Security Domain

Security enforcement is implicitly enabled (no `security_enforcement: false` in config.json).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 11 does not touch auth surface (no `ui/`, no `api_lambda/`). Unchanged from v2.0. |
| V3 Session Management | no | `runtimeSessionId` is not in Phase 11 scope. Unchanged. |
| V4 Access Control | yes (inherited) | IAM policy on `BillingSeeder2` AwsCustomResource: `dynamodb:BatchWriteItem` on `table.table_arn` only — matches existing pattern at `seeder.py:57-62`. Tools Lambda `TABLE_NAME` env var unchanged. |
| V5 Input Validation | yes | `_validate_customer_id` regex `^CUST-\d{3,6}$` at `lambda/handler.py:39` covers CUST-004/005/006. `get_hardship_flag_pure` MUST call `_validate_customer_id` before querying (D-10 helper pattern). `[VERIFIED: lambda/handler.py:39-52]` |
| V6 Cryptography | no | No hashing/encryption in Phase 11 scope. |

### Known Threat Patterns for Data Seeding + Tariff Math

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malformed customer_id passed to `get_hardship_flag_pure` | Tampering / Denial-of-Service | Reuse `_validate_customer_id` at entry (V5). Reject anything not matching `CUST-\d{3,6}$`. |
| `hardship_flag` attribute read as wrong type (string `"True"` vs native BOOL) | Tampering | Use DynamoDB native `BOOL` attribute type (not `S` stringified). `bool(item.get("hardship_flag", False))` defensively coerces. |
| `export_kwh > usage_kwh` produces negative `net_kwh` | Integrity | Plan-level: assert at `_record()` creation time that `export_kwh <= usage_kwh`. Bottom-of-file `assert` covers aggregate. |
| Seeder re-run overwrites hand-edited data | Integrity | `on_create` only (not `on_update`); physical_resource_id stable; new rows only add, never modify. `[VERIFIED: seeder.py:8 "on_create only"]` |
| DynamoDB `ProvisionedThroughputExceededException` on 73-row initial seed | Denial-of-Service / Availability | Table is `PAY_PER_REQUEST` (no provisioned throughput). `BatchWriteItem` scales automatically. `[VERIFIED: billing_table.py:29]` |
| Stale stack policy leaves `CustomerTariff` writeable after deploy | Tampering / Privilege Escalation | Scripted lift-reapply ceremony + byte-equality verification. C6 mitigation. |

**Phase 11 security posture:** LOW-risk. All changes are additive data/pure-math; no new IAM, no new auth, no new PII in flight. Inherits v2.0 security baseline.

## Sources

### Primary (HIGH confidence — VERIFIED against committed source at commit `f5aad91`)

- `lambda/handler.py` (lines 60-118 `simulate_savings_pure`; 39-52 `_validate_customer_id`; 123-146 `get_billing_history` + `simulate_savings`) — authoritative for SAV-03 math + current arithmetic
- `lambda/tariff_plans.json` — authoritative 4-plan catalog: STD=0.32, ECO=0.26, VAL=0.21, TOU=0.36. **CORRECTS CONTEXT.md's assumed STD=0.34.**
- `infrastructure/seed_data/tariff_plans.json` — byte-equal to `lambda/tariff_plans.json` today; VERIFIED by `diff lambda/tariff_plans.json infrastructure/seed_data/tariff_plans.json` (silent = identical)
- `infrastructure/seed_data/billing_records.py` — authoritative shape of `_record`, `_cost`, `to_dynamo`, `ALL_RECORDS`, `DYNAMO_RECORDS`, bottom-of-file assertions
- `infrastructure/constructs/seeder.py` — VERIFIED: chunked at 25 items via `math.ceil`; uses `AwsCustomResource` with `AwsSdkCall("DynamoDB", "batchWriteItem")`. D-17 resolved here.
- `infrastructure/constructs/billing_table.py` — VERIFIED: PK=`customer_id` (S), SK=`month` (S), `PAY_PER_REQUEST`, `RemovalPolicy.DESTROY`
- `infrastructure/stack-policies/foundation-{allow-all,freeze}.json` — VERIFIED policy bodies exist
- `tests/conftest.py` — VERIFIED fixture pattern for `mock_savings_response`, `mock_marcus_response`, `mock_elena_response`; loads `tariff_plans` from `lambda/` side
- `tests/test_simulate_savings.py` — VERIFIED existing byte-exact gate; uses `importlib.import_module("lambda.handler")` workaround
- `tests/test_seeder_smoke.py` — VERIFIED count-36 assertion at line 38; must bump to 73
- `DEMO-RUNBOOK.md` — VERIFIED stack-policy lift ceremony commands at lines 397-412
- `pytest.ini` — VERIFIED markers=`smoke`; testpaths=`tests`

### Secondary (MEDIUM confidence — project research docs)

- `.planning/research/ARCHITECTURE.md` §5 — TOU dispatcher style recommendation (option (a) with clean dispatch)
- `.planning/research/ARCHITECTURE.md` §Q2 — PROFILE SK row on existing table recommendation
- `.planning/research/PITFALLS.md` C6 (stack-policy lift ceremony), C7 (Chesterton's-Fence refactor risk), M1 (tariff_plans.json drift), M2 (non-reproducible seed), m3 (hardship_flag default=False on existing personas)
- `.planning/research/STACK.md` §"Summary of v3.0 Stack Deltas" — Phase 11 touches `CustomerTariff` only
- `.planning/research/SUMMARY.md` LD-1..LD-7 — load-bearing cross-cutting decisions

### Tertiary (training knowledge — FLAGGED for validation; not load-bearing)

- AWS DynamoDB native attribute types (`BOOL`, `N`, `S`) and `BatchWriteItem` 25-item cap — training knowledge; inferred correct based on SDK doc conventions
- CFN custom resource update semantics (`physical_resource_id` + `on_create` behaviour on stack update) — training knowledge + CDK docs conventions

### Researcher-generated artefacts (NOT committed per D-19 "scratch space")

- `.planning/phases/11-new-personas-tariff-archetypes/scratch/target_equation_solver.py` (v1)
- `.planning/phases/11-new-personas-tariff-archetypes/scratch/target_equation_solver_v2.py` (v2, FINAL — produces locked constants)
- `.planning/phases/11-new-personas-tariff-archetypes/scratch/sav03_regression_check.py` (proves Sarah/Marcus/Elena byte-exact against 6-plan catalog)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — all deps frozen, no changes
- Architecture patterns: **HIGH** — all patterns verified against committed source
- Pitfalls: **HIGH** — 5 pitfalls grounded in CLAUDE.md + project PITFALLS.md + researcher-surfaced runtime analysis
- Locked numeric constants (rates + arrays): **HIGH** — verified via solver with SAV-03 byte-exact regression check
- SOL `plan_type` / `green_score` choice: **LOW** — conflicts with D-03; flagged as Open Question #1, requires user decision

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (30 days — frozen-deps stable milestone)

## RESEARCH COMPLETE

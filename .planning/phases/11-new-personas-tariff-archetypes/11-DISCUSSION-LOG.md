# Phase 11: New Personas + Tariff Archetypes - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-28
**Phase:** 11-new-personas-tariff-archetypes
**Areas discussed:** Persona & tariff design, Hardship flag placement, TOU dispatcher refactor, Seeder & fixture strategy

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Persona & tariff design | CUST-004 solar + CUST-005 EV billing + SOL + EV-TOU rates | ✓ |
| Hardship flag placement | Which persona, where it lives, helper shape | ✓ |
| TOU dispatcher refactor | simulate_savings_pure plan_type branch style | ✓ |
| Seeder & fixture strategy | billing_records.py evolution + fixture locations + engineering strategy | ✓ |

**User's choice:** All four areas selected.

---

## Persona & Tariff Design

### Net-metering schema

| Option | Description | Selected |
|--------|-------------|----------|
| Add export_kwh + net_kwh, keep usage_kwh for back-compat | All three fields on every record; v2.0 personas get export_kwh=0 | ✓ (Recommended) |
| Replace usage_kwh with net_kwh on solar personas only | Polymorphic schema; branching reader | |
| Keep usage_kwh = net import, ignore solar production | Simplest but kills the solar story | |

### Savings target

| Option | Description | Selected |
|--------|-------------|----------|
| Hold $40/$70 and $35/$60 — reverse-engineer usage arrays | Targets first, engineer to hit | ✓ (Recommended) |
| Let the math produce whatever, lock those bytes | Faster but uglier numbers | |
| Hold targets but accept ±5% wiggle | Soft target = no real lock | |

### Plan selection

| Option | Description | Selected |
|--------|-------------|----------|
| SOL green_premium, EV-TOU time_of_use — existing argmax/argmin finds right track | Minimum change to selection logic | ✓ (Recommended) |
| Add persona_class hint on PROFILE, bias selection | More flexible, SAV-03 risk | |
| Constrain via plan_eligibility list | Cleanest per-persona but couples plans | |

### FiT baseline

| Option | Description | Selected |
|--------|-------------|----------|
| Include FiT credit in baseline + SOL cost; STD unmetered | Real-shaped net-metering | ✓ (Recommended) |
| Treat FiT as fixed monthly credit | Simpler but net-metering story is a lie | |
| Ignore FiT; SOL is just a lower-rate plan | Kills solar narrative | |

### Green tie-break (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| SOL.green_score > ECO.green_score — SOL always wins Green | Risk: breaks v2.0 fixtures unless rate engineering prevents it | ✓ (Recommended, with researcher verification gate) |
| Green selection filters by persona compatibility (export_kwh > 0) | Code-enforced eligibility, minimal SAV-03 risk | |
| Tie to current_plan_id | Awkward baseline-plan coupling | |

### EV rate shape (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Asymmetric peak/off-peak: ~0.38/0.12, 30/70 split | TOU math path; v2.0 personas default to 100% peak | ✓ (Recommended) |
| Single blended rate ~0.17 | Wins for everyone — breaks v2.0 fixtures | |
| Peak-only rate 0.15 | Same fixture-break risk | |

### Peak/off-peak storage (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Add peak_kwh + offpeak_kwh columns on records | CUST-005 carries split; v2.0 personas don't | ✓ (Recommended) |
| Store split ratio at plan level | Plan-level assumption won't match real shape | |
| Store split at persona level (PROFILE item) | Extra DynamoDB call per savings calc | |

**Notes:** SOL wins Green + risk-flag = researcher must verify SOL's rate_per_kwh is set such that `projected_cost(SOL)` for CUST-001/002/003 (who have no export_kwh) is WORSE than `projected_cost(ECO)`. Otherwise v2.0 Green fixtures (ECO plan_id) break. This is a hard gate at Phase 11 planning.

---

## Hardship Flag Placement

### Who

| Option | Description | Selected |
|--------|-------------|----------|
| A new CUST-006 dedicated hardship persona | Separates narratives for rehearsal | ✓ |
| CUST-005 (EV persona) carries hardship_flag | Research suggestion; ties two stories | |
| CUST-002 (Marcus) | Collides with AGENT-01 bill-shock | |
| CUST-003 (Elena) | (was the recommended "clean narrative" option) | |

### Storage

| Option | Description | Selected |
|--------|-------------|----------|
| New SK=PROFILE row on tariff-billing table | Research Q8 default; single-table preservation | ✓ (Recommended) |
| New attribute on every billing row | Denormalised; anti-pattern | |
| Separate DynamoDB table | Adds CFN resource; larger freeze surface | |

### PROFILE shape

| Option | Description | Selected |
|--------|-------------|----------|
| Only hardship_flag (bool) — nothing else this phase | Minimum surface | ✓ (Recommended) |
| hardship_flag + persona_class | Future-proofs but over-specifies | |
| hardship_flag + display_name + segment | Full profile shape; scope creep | |

### Discoverability

| Option | Description | Selected |
|--------|-------------|----------|
| Pure helper in lambda/handler.py that reads PROFILE row | Offline-testable; not wired to agent this phase | ✓ (Recommended) |
| Full Tools Lambda action (action='get_hardship_flag') | Front-loads Phase 13 dispatcher | |
| Just store flag, no helper | Violates REQUIREMENTS.md success criterion 5 | |

### CUST-006 data (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Low stressed-usage 12-month history; AGENT-02 short-circuits later | Phase 14 testable against "has data + flagged" customer | ✓ (Recommended) |
| Minimal/empty billing — just the PROFILE row | Conflates missing with hardship | |
| Copy Elena's shape | Weak narrative, two identical curves | |

### CUST-006 targets (follow-up)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, lock mock_cust006_response + separate hardship helper fixture | Belt-and-braces: savings byte-exact + hardship path separate | ✓ (Recommended) |
| No fixture lock; only hardship discoverability test | Lighter but weaker SAV-03 extension | |

**Notes:** The CUST-006 choice (new persona) is a deliberate departure from the "Recommended" CUST-003 option. Rationale: clean narrative surfaces for rehearsal. Each persona carries ONE story. REQUIREMENTS.md DATA-06 explicitly allows "existing or new persona".

---

## TOU Dispatcher Refactor

### Dispatch style

| Option | Description | Selected |
|--------|-------------|----------|
| Inline if-branch on plan_type inside projected_monthly_cost | Research Q11 default; minimum surface | ✓ (Recommended) |
| Extract per-plan-type helpers + dict dispatch | Cleaner testing, slightly heavier diff | |
| Separate simulate_tou / simulate_solar top-level functions | Duplicates selection logic; rejected | |

### Byte-exact gate

| Option | Description | Selected |
|--------|-------------|----------|
| Existing v2.0 fixtures re-run against refactored simulate_savings_pure + 6-plan catalog | Existing fixtures ARE the gate | ✓ (Recommended) |
| New test_sav03_byte_exact_post_tou_refactor.py | Redundant boilerplate | |
| Accept ±$0.01 tolerance | Explicit SAV-03 regression; rejected | |

### Legacy TOU plan

| Option | Description | Selected |
|--------|-------------|----------|
| Keep existing TOU unchanged; computed via new TOU math path | 100%-peak default = same as pre-refactor flat math | ✓ (Recommended) |
| Deprecate existing TOU | Catalog churn mid-refactor | |
| Convert to carry peak_rate + offpeak_rate | Useless half-step for v2.0 personas | |

### Schema location

| Option | Description | Selected |
|--------|-------------|----------|
| Extend tariff_plans.json with optional fields on plans that need them | Byte-equality gate preserved | ✓ (Recommended) |
| New top-level plan_type_rules section | Over-engineered for 2 new plan types | |
| Split into per-plan-type JSON files | Breaks single source-of-truth contract | |

---

## Seeder & Fixture Strategy

### Seeder shape

| Option | Description | Selected |
|--------|-------------|----------|
| Extend _record() with optional kwargs; add to_dynamo() branches; append arrays + PROFILE items | 48→73 items, single file, pattern preserved | ✓ (Recommended) |
| New billing_records_v3.py file alongside existing | Accreting files; awkward | |
| Lambda-backed seeder replacing CfnCustomResource | Big architectural change mid-milestone | |

### Seed batch size

| Option | Description | Selected |
|--------|-------------|----------|
| Inspect current seeder; add chunking if missing; CDK-synth asserts shape | Mandatory pre-plan verification | ✓ (Recommended) |
| Assume chunking exists; fix if not | Deploy-time risk | |
| Delegate to Phase 12 | Wrong phase | |

### Fixtures

| Option | Description | Selected |
|--------|-------------|----------|
| In tests/conftest.py alongside v2.0 fixtures | One file, pattern preserved, auto-discovery | ✓ (Recommended) |
| New tests/conftest_v3.py | pytest doesn't auto-discover; ceremony | |
| Fixtures inside each test file | Duplicates values; anti-pattern | |

### Reverse-engineering

| Option | Description | Selected |
|--------|-------------|----------|
| Solve target equation for avgs first, pick 12-month curve that sums to 12×avg | Researcher writes solver; exact $ target hit | ✓ (Recommended) |
| Trial-and-error 3-5 candidate curves | Inexact, lands whatever | |
| Fix usage curve, back out rates | Ugly rates (0.2753); plan cards look weird | |

---

## Claude's Discretion

- Exact monthly usage curve shapes within engineered avgs (seasonal variation pattern).
- Whether to compute `net_kwh` at record-creation vs store both and derive.
- Test organisation: new `tests/test_sav03_byte_exact_v3.py` vs extending existing `tests/test_simulate_savings.py` with parametrisations.

## Deferred Ideas

- `persona_class` field on PROFILE item (solar/ev/standard/hardship) — defer to Phase 12 or 13.
- `display_name` / `segment` / other customer-profile attributes on PROFILE item — defer.
- Convert legacy TOU plan to carry explicit `peak_rate` + `offpeak_rate` fields — defer.
- Lambda-backed seeder replacing `CfnCustomResource AwsSdkCall` pattern — defer.
- Separate `customer-profile` DynamoDB table — defer (single-table wins for demo scope).
- Plan-eligibility / persona-class filtering for Green/Cheapest selection — defer.

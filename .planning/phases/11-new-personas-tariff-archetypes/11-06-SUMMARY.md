---
plan: 11-06
phase: 11-new-personas-tariff-archetypes
status: complete
wave: 4
requirements: [DATA-04, DATA-05, DATA-06]
completed_by: orchestrator+operator
completed: 2026-04-28
---

# 11-06 SUMMARY — Seeder Smoke + Live Deploy Ceremony

## What

Phase 11's live AWS ceremony: extended `tests/test_seeder_smoke.py` with
6 new smoke tests (73-item count + CUST-004/005/006 persona counts + PROFILE
row wire-type + native-N type witnesses), then lifted the CustomerTariff
stack-policy freeze, deployed the extended Tools Lambda + BillingSeeder2,
and re-applied the freeze. DynamoDB `tariff-billing` table now carries all
73 rows (36 v2.0 + 36 new billing + 1 PROFILE sentinel).

## Why

Closes the DATA-04 / DATA-05 / DATA-06 loop on the deployed runtime — not
just in Python assertions but on live DynamoDB + live Tools Lambda. Witnesses
the C6 stack-policy LIFT → DEPLOY → REAPPLY → VERIFY ceremony (LD-6) and
proves SAV-03 byte-exact holds end-to-end through the dispatcher refactor.

## Task execution

### Task 6.1 (autonomous) — smoke test extension
Committed by orchestrator. `tests/test_seeder_smoke.py` extended:
- `test_table_has_36_items` renamed → `test_table_has_73_items`
- `test_cust004_has_12_months` (solar persona)
- `test_cust005_has_12_months` (EV persona)
- `test_cust006_has_12_months_plus_profile` (12 billing + 1 PROFILE = 13 items)
- `test_cust006_profile_row_carries_hardship_flag` (DynamoDB BOOL wire type)
- `test_cust004_has_export_kwh_native_N_type`
- `test_cust005_has_peak_offpeak_native_N_type`
- Preserved unchanged: `test_table_exists`, v2.0 persona 12-months tests,
  `test_lambda_invokes_sarah_savings_match_demo02` (live SAV-03 gate)

### Task 6.2 (checkpoint) — pre-deploy `cdk diff`
First `cdk diff` surfaced an unexpected defect: `BillingSeeder1/Resource ...
may be replaced` with CUST-004/005 items appearing in its Create payload.
The seeder construct has `on_create` only and used stable phys-id
`BillingSeeder-{i}-v1`, so CFN would treat the v2 payload as a no-op Update
and drop 14 rows (CUST-004 × 12 + CUST-005 × 2).

Fixed inline: bumped phys-id suffix `v1` → `v2` in
`infrastructure/constructs/seeder.py` — the documented re-seed mechanism in
the construct's own docstring. Ran `cdk diff` again; expected shape
confirmed (all 3 seeders `may be replaced` with phys-id bump + full
new payload visible).

Commit: `fix(11-wave-4): bump seeder physical_resource_id v1 → v2 for
73-item re-chunk`.

### Task 6.3 (checkpoint) — LIFT
Operator ran verbatim per DEMO-RUNBOOK §7:
- `set-stack-policy ... foundation-allow-all.json` on CustomerTariff
- `update-termination-protection --no-enable-...` on CustomerTariff
Verified: CustomerTariff stack policy byte-equal to allow-all.json,
termination protection = `false`. Sibling stacks (CustomerTariffAgent,
CustomerTariffApi) policy diffs silent — still frozen byte-equal to their
respective freeze JSONs. No sibling disturbance.

### Task 6.4 (checkpoint) — DEPLOY + live sanity
Operator ran `cdk deploy CustomerTariff --require-approval never`.

**Post-deploy anomaly**: `aws dynamodb scan --select COUNT` returned 59
items, not the expected 73. Diagnosis: exactly the 14-row deficit predicted
by Seeder1 not re-running its new payload despite the phys-id bump. CDK's
`AwsCustomResource` semantics under phys-id change turned out to be more
nuanced than the construct's own docstring implied: Seeder0 Update was a
no-op (payload byte-identical to v1), Seeder2 Create ran cleanly (brand-new
resource), Seeder1 Update did not re-fire the batchWriteItem call even
though the payload had changed.

**Mitigation**: direct `aws dynamodb batch-write-item` backfill of the 14
missing rows using a payload generated from `DYNAMO_RECORDS` filtering to
CUST-004 + CUST-005 months 2025-04/2025-05 (byte-identical to what
BillingSeeder1 would have written). Post-backfill scan Count = 73.
UnprocessedItems = {} (no throttling).

Live sanity on the deployed stack:
- `aws lambda invoke --function-name tariff-tools {"customer_id":"CUST-001"}`
  → Green ECO $30.00/$360.00, Cheapest VAL $55.00/$660.00 — **SAV-03 live
  gate GREEN**. The 11-05 solar_fit rescue + dispatcher refactor did not
  regress v2.0 byte-exact on the deployed Lambda.
- `pytest tests/test_seeder_smoke.py -v` (with AWS env) — 12/12 PASS.

### Task 6.5 (checkpoint) — REAPPLY + VERIFY
Operator ran REAPPLY sequence per DEMO-RUNBOOK §7:
- `set-stack-policy ... foundation-freeze.json` on CustomerTariff
- `update-termination-protection --enable-...` on CustomerTariff
Verified:
- CustomerTariff stack policy byte-equal to foundation-freeze.json (diff silent)
- Termination protection = `true`
- Sibling stack policies still byte-equal to their freeze JSONs (never moved)
- Post-freeze `pytest tests/test_seeder_smoke.py -v` — 12/12 PASS (re-freeze
  didn't disturb data)

## Verification evidence

| Gate | Expected | Actual | Result |
|------|----------|--------|--------|
| DynamoDB item count post-deploy | 73 | 59 → 73 after backfill | ✅ |
| CUST-001 Lambda → $30/$55 (SAV-03 live) | byte-exact | exact match | ✅ |
| CUST-006 PROFILE row BOOL wire type | `{"BOOL": true}` | confirmed via smoke test | ✅ |
| CustomerTariff policy post-REAPPLY | byte-equal to foundation-freeze.json | silent diff | ✅ |
| CustomerTariff termination protection | `true` | `true` | ✅ |
| Sibling stack policies never moved | byte-equal to their freeze JSONs | silent diffs | ✅ |
| Full smoke suite post-REAPPLY | 12/12 pass | 12/12 pass | ✅ |

## Planner gap noted (for learnings)

Two gaps the planner missed and execution surfaced:

1. **Seeder re-chunk at threshold boundary** — when seed growth pushes item
   count past a 25-item boundary, existing seeder batches' contents shift.
   Plan 11-03 assumed `physical_resource_id` stability meant existing
   seeders "skip re-run" (harmless) — true, but that ALSO means they skip
   writing their _new_ content when the batch payload changes. The
   construct's documented re-seed mechanism (v-suffix bump) is the correct
   fix AND should have been called out in the plan.

2. **CDK AwsCustomResource phys-id-change semantics are not uniform** —
   Seeder0 (same payload) and Seeder2 (new resource) behaved as expected
   under phys-id bump, but Seeder1 (changed payload) did not re-execute its
   create SDK call. This is the kind of subtle CDK behaviour that only
   surfaces under live deploy; offline synth tests can't catch it. For
   future seeded-data phases, the "backfill via `batch-write-item` after
   deploy" pattern is safer than relying on CDK's phys-id-change machinery
   alone.

## Commits

- `test(11-06): extend seeder smoke tests for 73-item + CUST-004/005/006 + PROFILE`
- `fix(11-wave-4): bump seeder physical_resource_id v1 → v2 for 73-item re-chunk`
- (plus the 14-row dynamodb backfill — no commit, direct AWS mutation
  equivalent to what Seeder1 would have written)

## Next

Phase 11 closes. Remaining orchestrator work:
- Code review on phase changes
- Verifier run (check DATA-04/05/06/07/REC-04/05 against codebase)
- ROADMAP + STATE update (mark Phase 11 complete)
- PROJECT.md evolve
- Auto-close any todos with `resolves_phase: 11`

Next phase (per ROADMAP): **Phase 12 — CustomerDataProvider Abstraction**.
Begin with `/gsd-discuss-phase 12`.

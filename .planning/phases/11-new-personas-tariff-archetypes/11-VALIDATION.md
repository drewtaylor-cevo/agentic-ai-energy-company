---
phase: 11
slug: new-personas-tariff-archetypes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-28
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `11-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (frozen via `requirements-dev.txt --require-hashes`) |
| **Config file** | `pytest.ini` (testpaths=`tests`, markers=`smoke`) |
| **Quick run command** | `pytest tests/test_simulate_savings.py -x` |
| **Full suite command** | `pytest` (excludes smoke by default) |
| **Estimated runtime** | ~2s quick, ~10s full offline, smoke adds deploy round-trip |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_simulate_savings.py -x` — catches SAV-03 byte-exact regressions immediately
- **After every plan wave:** Run `pytest` — full offline suite (~200 tests), catches cross-cutting regressions
- **Before `/gsd-verify-work`:** Full offline suite green + `pytest -m smoke` green against a scratch deploy of `CustomerTariff` stack (M2 reproducibility gate)
- **Max feedback latency:** 2 seconds for per-commit; 10 seconds for per-wave

---

## Per-Task Verification Map

Tasks below are the verification contract; actual task IDs resolve to plan IDs during planning. Placeholders `11-0X-0Y` will be replaced by gsd-planner against the plan shape.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 11-0X-0Y | 01 catalog | 1 | REC-04, REC-05 | T-Tampering (M1 drift) | Byte-equal JSON between `lambda/` and `infrastructure/seed_data/`; 6-plan catalog present | unit | `pytest tests/test_tariff_plans_byte_equal.py -x` | ❌ W0 NEW file | ⬜ pending |
| 11-0X-0Y | 02 dispatcher | 2 | DATA-07 | T-Integrity (C7 SAV-03 regression) | v2.0 byte-exact preserved against 6-plan catalog ($30/$55, $16.90/$30.98, $14.00/$25.67) | unit | `pytest tests/test_simulate_savings.py -x` | ✅ EXTEND existing | ⬜ pending |
| 11-0X-0Y | 02 dispatcher | 2 | DATA-04 | — | CUST-004 Green=ECO $40.02, Cheapest=SOL $76.03 byte-exact | unit | `pytest tests/test_simulate_savings.py::test_cust004_byte_exact -x` | ❌ W0 EXTEND | ⬜ pending |
| 11-0X-0Y | 02 dispatcher | 2 | DATA-05 | — | CUST-005 Green=ECO $35.00, Cheapest=EV-TOU $84.00 byte-exact; EV-TOU wins via 70% offpeak | unit | `pytest tests/test_simulate_savings.py::test_cust005_byte_exact -x` | ❌ W0 EXTEND | ⬜ pending |
| 11-0X-0Y | 03 personas | 2 | DATA-04, DATA-05, DATA-06 | T-Integrity (export_kwh > usage_kwh) | CUST-004 12 records avg=667 net / avg=200 export; CUST-005 12 records sum=7000 / peak=2100 / offpeak=4900; CUST-006 12 records sum=2400 | unit | `pytest tests/test_billing_records.py -x` or `python -c "import infrastructure.seed_data.billing_records"` asserts | ❌ W0 EXTEND | ⬜ pending |
| 11-0X-0Y | 04 hardship | 3 | DATA-06 | T-V5 Input Validation | `get_hardship_flag_pure("CUST-006", client)` returns `{hardship: True, customer_id: "CUST-006"}`; `CUST-001` returns `{hardship: False, ...}`; malformed ID rejected | unit | `pytest tests/test_get_hardship_flag_pure.py -x` | ❌ W0 NEW file | ⬜ pending |
| 11-0X-0Y | 04 hardship | 3 | DATA-06 | T-Integrity (PROFILE KeyError) | `get_billing_history("CUST-006", ctx)` returns exactly 12 items (month rows only); PROFILE row filtered | unit | `pytest tests/test_get_billing_history.py::test_profile_filtered -x` | ❌ W0 NEW test | ⬜ pending |
| 11-0X-0Y | 05 fixtures | 3 | DATA-07 | — | `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship` importable from `tests/conftest.py` | unit | `pytest --collect-only tests/ | grep mock_cust` | ❌ W0 EXTEND | ⬜ pending |
| 11-0X-0Y | 06 deploy | 4 | DATA-04, DATA-05, DATA-06 | T-C6 stack-policy lift ceremony | `cdk synth CustomerTariff` shows 3 `BillingSeeder[0-2]` resources (not 2); synthesis passes | integration | `cdk synth CustomerTariff` (offline) | ✅ via CDK | ⬜ pending |
| 11-0X-0Y | 06 deploy | 4 | DATA-04, DATA-05, DATA-06 | T-C6 reapply freeze | Live smoke: CUST-004 / CUST-005 / CUST-006 each 12 month rows + PROFILE row present; v2.0 personas unchanged; stack policy byte-equal to `foundation-freeze.json` post-deploy | smoke | `pytest -m smoke tests/test_seeder_smoke.py` + `aws cloudformation get-stack-policy --stack-name CustomerTariff` | ✅ EXTEND existing | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `tests/test_tariff_plans_byte_equal.py` — NEW file — REC-04, REC-05 + M1 mitigation (3 tests: byte-equal, structural-equal, 6-plan assertion)
- [ ] `tests/test_get_hardship_flag_pure.py` — NEW file — DATA-06 (hardship=True / hardship=False / malformed-ID rejected)
- [ ] `tests/test_simulate_savings.py` — EXTEND with CUST-004/005/006 byte-exact parametrisations — DATA-04, DATA-05, DATA-07
- [ ] `tests/test_seeder_smoke.py` — EXTEND count 36→73 + add CUST-004/005/006 month-12 queries + PROFILE row query — DATA-04/05/06 live-deploy verification
- [ ] `tests/conftest.py` — EXTEND with `mock_cust004_response`, `mock_cust005_response`, `mock_cust006_response`, `mock_cust006_hardship` fixtures — D-18
- [ ] `tests/test_get_billing_history.py` OR extension to existing test module — NEW test — `test_profile_filtered_for_hardship_persona` asserts `len == 12` (D-21 filter)

No framework install needed — pytest already pinned in `requirements-dev.txt --require-hashes`.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Stack-policy reapply after deploy | C6 / LD-6 | `aws cloudformation set-stack-policy` is imperative; no CDK-native tracking | Per DEMO-RUNBOOK.md §7 lines 397-412: `aws cloudformation get-stack-policy --stack-name CustomerTariff \| jq -S . \| diff - <(jq -S . infrastructure/stack-policies/foundation-freeze.json)` — expect silent diff. Re-verify `describe-stacks --query 'Stacks[0].EnableTerminationProtection'` = `true`. |
| Scratch-stack `cdk destroy` + `cdk deploy CustomerTariff-scratch` round-trip seeds 73 items | M2 reproducibility gate | Live AWS round-trip; can't run in CI offline | On scratch stack with allow-all policy: `cdk deploy CustomerTariff-scratch` → `aws dynamodb scan --table-name tariff-billing-scratch --select COUNT --profile cevo-dev25` should report `Count: 73`. |
| DynamoDB native BOOL attribute type for `hardship_flag` persists and round-trips | DATA-06 native type preserved | Requires live service call; offline test uses mocked client | On deployed stack: `aws dynamodb get-item --table-name tariff-billing --key '{"customer_id":{"S":"CUST-006"},"month":{"S":"PROFILE"}}' --profile cevo-dev25` — expect `"hardship_flag": {"BOOL": true}` in response. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (5 new/extend test files listed above)
- [ ] No watch-mode flags (pytest `-x` runs once, exits)
- [ ] Feedback latency < 10s (offline suite)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

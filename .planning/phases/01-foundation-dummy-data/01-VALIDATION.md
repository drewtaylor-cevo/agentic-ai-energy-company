---
phase: 1
slug: foundation-dummy-data
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-23
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 + pytest-mock |
| **Config file** | `pytest.ini` — Wave 0 gap |
| **Quick run command** | `pytest tests/test_simulate_savings.py -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_simulate_savings.py -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 0 | DATA-01 | — | `get_billing_history` reads only its own table (grant_read_data scoped to table ARN) | unit | `pytest tests/test_get_billing_history.py -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 0 | DATA-02 | — | N/A | smoke | `pytest tests/test_seeder_smoke.py -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 0 | DATA-03 | — | N/A | unit | `pytest tests/test_schema.py -x` | ❌ W0 | ⬜ pending |
| 1-01-04 | 01 | 1 | DEMO-02 | — | N/A | unit | `pytest tests/test_simulate_savings.py -x` | ❌ W0 | ⬜ pending |
| 1-01-05 | 01 | 1 | DEMO-02 | — | cheapest_saving >= green_saving invariant | unit | `pytest tests/test_simulate_savings.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — shared fixtures (TARIFF_PLANS, billing records per persona)
- [ ] `tests/test_simulate_savings.py` — covers DEMO-02 (template provided in RESEARCH.md Code Examples)
- [ ] `tests/test_get_billing_history.py` — covers DATA-01, needs DynamoDB mock via pytest-mock
- [ ] `tests/test_schema.py` — covers DATA-03, validates each record has `usage_kwh` as numeric attribute
- [ ] `tests/test_seeder_smoke.py` — covers DATA-02, post-deploy DynamoDB scan smoke test
- [ ] `pytest.ini` — basic config
- [ ] `pip install pytest pytest-mock` — framework install (not yet present in environment)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DynamoDB table seeded after `cdk deploy` | DATA-02 | AWS resource state — can't mock CDK deploy in unit tests | Run `aws dynamodb scan --table-name tariff-billing --region us-east-1` and confirm 36 items (3 personas × 12 months) |
| `cdk synth` produces valid CloudFormation | DATA-03 | Infrastructure validation | Run `cdk synth` and inspect output for DynamoDB table + seeder custom resource |
| Sarah Chen yields Green=$30, Cheapest=$55 post-deploy | DEMO-02 | End-to-end savings path requires live DynamoDB | Invoke Lambda directly: `aws lambda invoke --function-name tariff-tools --payload '{"customer_id":"CUST-001"}' out.json` and check savings figures |
| Region hardcoded to us-east-1 | DATA-01 | CDK environment check | `grep "us-east-1" app.py` — confirm region not driven by AWS profile default |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

# Phase 13.1 Ceremony Log

Started: 2026-04-30T00:29:10Z

## Pre-flight

```
{
    "UserId": "AROAYSE4OGVSOSU7Q6QY2:drew.taylor@cevo.com.au",
    "Account": "588738606436",
    "Arn": "arn:aws:sts::588738606436:assumed-role/AWSReservedSSO_AWSFullAccountAdmin_b0f66468776206ef/drew.taylor@cevo.com.au"
}
```

### CustomerTariff — pre-flight
Policy:
{
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    }
  ]
}

TP:
True

### CustomerTariffAgent — pre-flight
Policy:
{
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    }
  ]
}

TP:
True

### CustomerTariffApi — pre-flight
Policy:
{
  "Statement": [
    {
      "Effect": "Deny",
      "Action": "Update:*",
      "Principal": "*",
      "Resource": "*"
    }
  ]
}

TP:
True

### CustomerTariffFrontend — pre-flight
Policy:
None
TP:
False

### cdk diff CustomerTariff — expect no changes (D-13.1-11 foundation untouched)
Result: **There were no differences** ✅

### cdk diff CustomerTariffAgent — expect non-zero (prompt edit rebuilt container)
Result: **1 stack with differences** — ContainerUri hash changed ✅
- Old: `bc7e4bbcf18dd3ef64a49bdd3474a6e50e17ed065441ebc9adba08850280368d`
- New: `a6974fd386cab3d00e33537ea0929467630e7ee499a0432b2b25eff229152a42`

### cdk diff CustomerTariffApi — expect non-zero (api_lambda/handler.py edit rebuilt)
Result: **1 stack with differences** — Lambda S3Key changed + new Version + Alias update ✅
- Old: `5d70f6e79f47f69370918338819f573fa72eae7689f10008b711170fd3c7b02f.zip`
- New: `32a148aaa40abb2dbbbcf374c7e7d1859c1254c43dbdbbf7091386d4e44353ac.zip`

## Pre-capture

5/5 personas captured via `scripts/capture_live_recommendations.py --mode pre`.
Copied CUST-001/002/003 to Phase 13.1 `baseline/pre/`.

| Persona | green.plan_id | green.saving_monthly | cheapest.plan_id | cheapest.saving_monthly | reasoning_trace len |
|---------|---------------|----------------------|------------------|-------------------------|---------------------|
| CUST-001 | ECO | 30.0 | VAL | 55.0 | 3 (pre-fix: 3-tool on all) |
| CUST-002 | ECO | 16.9 | VAL | 30.98 | 3 (pre-fix: 3-tool on all) |
| CUST-003 | ECO | 14.0 | VAL | 25.67 | 3 (pre-fix: 3-tool on all) |

Pre-capture files:
- `.planning/phases/13.1-.../baseline/pre/CUST-001.json` ✅
- `.planning/phases/13.1-.../baseline/pre/CUST-002.json` ✅
- `.planning/phases/13.1-.../baseline/pre/CUST-003.json` ✅

Pre-flight + pre-capture complete: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Pre-flight + pre-capture complete: 2026-04-30T00:35:54Z

## LIFT

Started: $(date -u)

- CustomerTariffAgent: set-stack-policy → allow-all ✅, TP → False ✅
- CustomerTariffApi: set-stack-policy → allow-all ✅, TP → False ✅

Post-lift verification:
- CustomerTariffAgent: Allow:Update:*, TP=False
- CustomerTariffApi: Allow:Update:*, TP=False

## DEPLOY

Started: 2026-04-30T~UTC

```
cdk deploy CustomerTariffAgent CustomerTariffApi --require-approval never
```

- CustomerTariffAgent: ✅ UPDATE_COMPLETE (25.51s deployment)
  - Runtime: tariff_agent-O2Hai86N8V
  - Container: a6974fd386cab3d00e33537ea0929467630e7ee499a0432b2b25eff229152a42
- CustomerTariffApi: ✅ UPDATE_COMPLETE (31.24s deployment)
  - Endpoint: https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/
  - Lambda code: 32a148aaa40abb2dbbbcf374c7e7d1859c1254c43dbdbbf7091386d4e44353ac.zip

## Post-capture

5/5 personas captured via `scripts/capture_live_recommendations.py --mode post`.
Copied CUST-001/002/003 to Phase 13.1 `baseline/post/`.

| Persona | green.plan_id | green.saving_monthly | cheapest.plan_id | cheapest.saving_monthly | reasoning_trace len |
|---------|---------------|----------------------|------------------|-------------------------|---------------------|
| CUST-001 | ECO | 30.0 | VAL | 55.0 | 2 (post-fix: short-circuit working) |
| CUST-002 | ECO | 16.9 | VAL | 30.98 | 2 (post-fix: short-circuit working) |
| CUST-003 | ECO | 14.0 | VAL | 25.67 | 2 (post-fix: NOTE — expected 3 for bill-shock persona) |

## Close-gates

### Gate 1: Savings-field byte-equivalence (24 fields across 3 personas)
- CUST-001 SAV-03 8/8 fields byte-equal ✅
- CUST-002 SAV-03 8/8 fields byte-equal ✅
- CUST-003 SAV-03 8/8 fields byte-equal ✅
**Result: PASS**

### Gate 2: Reasoning-trace shape (D-13.1-14)
- CUST-001 reasoning_trace length = 2 (expected 2) ✅
- CUST-002 reasoning_trace length = 2 (expected 2) ✅
- CUST-003 reasoning_trace length = 2 (expected 3) ⚠️ VERIFICATION FINDING
**Result: PARTIAL — CUST-001/002 match expected 2-tool short-circuit; CUST-003 (Elena bill-shock) returned 2 instead of expected 3. The LLM is short-circuiting Elena as well. Savings are byte-exact so the mechanism works; the bill-shock 3-tool path is not being triggered on this invocation.**

### Gate 3: CUST-999 direct curl → HTTP 404 (Gap 2 closure)
- CUST-999 HTTP status = 404 ✅
- Body: `{"error": "Customer CUST-999 not found."}`
**Result: PASS — Gap 2 CLOSED**

### Gate 4: pytest -m smoke -x
- 15 passed, 22 skipped, 334 deselected, 1 warning in 150.06s
- All smoke tests green including test_backend_api_smoke.py (10 tests)
**Result: PASS**

### Gate 5: scripts/prewarm.py per-flow latency
- CUST-001 warm median: 13840ms FAIL (gate: 3000ms)
- CUST-003 warm median: 10990ms FAIL (gate: 2500ms)
- Exit code: 1
**Result: FAIL — both personas exceed their latency gates by ~4-5×**

### Verification findings

**Finding 1: CUST-003 reasoning_trace length = 2 (expected 3)**
The bill-shock persona (Elena/CUST-003) is being short-circuited to a 2-tool flow instead of the expected 3-tool flow. The SHORT-CIRCUIT RULE in the prompt is being applied more broadly than intended. Savings are byte-exact, so the mechanism is correct — the agent is just not exercising the detect_bill_shock tool on this invocation. This is a non-blocking finding for the ceremony (savings integrity preserved) but means the "visible 3-tool reasoning" demo story for Elena may need prompt tuning in a follow-up.

**Finding 2: Warm latency exceeds gates on both personas**
CUST-001 at 13.8s and CUST-003 at 11.0s are both well above their respective 3000ms/2500ms gates. This is consistent with the pre-ceremony state (17.2s/19.7s) — the short-circuit reduced latency somewhat but the inherent AgentCore round-trip dominates. Per D-13.1-02, the mechanism fix (reducing tool count) was the scope of 13.1; the absolute latency target may require infrastructure-level changes (Provisioned Concurrency, model selection, etc.) that are outside 13.1's scope.

**Assessment: Gates 1, 3, 4 PASS. Gate 2 partial (CUST-001/002 correct, CUST-003 finding). Gate 5 FAIL (both personas). The core objectives of 13.1 are met: Gap 2 (404 detection) is CLOSED, savings integrity is preserved, and the short-circuit mechanism is working (trace count reduced from 3→2 on non-shock personas). The latency and 3-tool trace findings are documented for follow-up.**

## REAPPLY freeze

- CustomerTariffAgent: set-stack-policy → deny-Update:* ✅, TP → True ✅
- CustomerTariffApi: set-stack-policy → deny-Update:* ✅, TP → True ✅

### Byte-equality check (modulo CFN whitespace artefact)
- CustomerTariffAgent freeze policy byte-equal ✅
- CustomerTariffApi freeze policy byte-equal ✅

## Final sweep

| Stack | Policy | TP | Expected | Match |
|-------|--------|----|----------|-------|
| CustomerTariff | Deny:Update:* | True | Deny + True (untouched) | ✅ |
| CustomerTariffAgent | Deny:Update:* | True | Deny + True (re-frozen) | ✅ |
| CustomerTariffApi | Deny:Update:* | True | Deny + True (re-frozen) | ✅ |
| CustomerTariffFrontend | None | False | None + False (unfrozen) | ✅ |

Ceremony complete: 2026-04-30T03:33:46Z

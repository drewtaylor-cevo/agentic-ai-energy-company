# Phase 15 Ceremony Log

Started: 2026-05-03T20:15:00Z

## Pre-flight

Account: 588738606436 ✅
Stack posture: Deny·Deny·Deny + TP=True on all 3 frozen stacks ✅

### cdk diff CustomerTariff — expect no changes
Result: **There were no differences** ✅

### cdk diff CustomerTariffAgent — expect non-zero
Result: **1 stack with differences** — Memory resource added, ContainerUri hash changed, MEMORY_ID env var added, IAM policy updated ✅

### cdk diff CustomerTariffApi — expect non-zero
Result: **1 stack with differences** — Lambda S3Key changed, new follow-up route + integration + permission ✅

## Pre-capture

| Persona | green.plan_id | cheapest.plan_id | kind | Notes |
|---------|---------------|------------------|------|-------|
| CUST-001 | ECO | VAL | recommendation | Baseline |
| CUST-002 | ECO | VAL | recommendation | Baseline |
| CUST-003 | ECO | VAL | recommendation | Baseline |
| CUST-006 | N/A | N/A | hardship | Hardship guard active |

## LIFT + DEPLOY

- CustomerTariffAgent: Allow:Update:* + TP=False → deployed ✅ (218.66s)
  - Memory ID: `tariff_agent_memory-xVDAvVCTtU`
  - Runtime: `tariff_agent-O2Hai86N8V`
- CustomerTariffApi: Allow:Update:* + TP=False → deployed ✅ (38.26s)
  - New route: `GET /recommendations/{customer_id}/follow-up`

## Close-gates

### Gate 1: SAV-03 byte-equivalence
- CUST-001 8/8 fields byte-equal ✅
- CUST-002 8/8 fields byte-equal ✅
- CUST-003 8/8 fields byte-equal ✅
**Result: PASS**

### Gate 2: CUST-006 hardship response preserved
- HTTP 200 ✅
- kind: "hardship" ✅
- No green/cheapest keys ✅
- routing_target: "hardship_team" ✅
**Result: PASS**

### Gate 3: Follow-up route live
- CUST-001 follow-up: HTTP 200, kind: "follow_up" ✅
- D-15 compliance: no digits, no currency in subject or body ✅
- plan_reference: "EcoFlex Green" (name, not ID) ✅
**Result: PASS**

### Gate 4: Cross-customer Memory isolation canary (MANDATORY)
- Step 1: Lookup CUST-001 recommendation (seed Memory) ✅
- Step 2: Lookup CUST-002 recommendation (seed Memory) ✅
- Step 3: Follow-up CUST-002 → zero CUST-001 tokens in body ✅
  - No "CUST-001", no "Sarah", no "Chen", no CUST-001 savings figures
  - Follow-up customer_id: CUST-002 ✅
  - Follow-up kind: follow_up ✅
**Result: PASS**

### Gate 5: Customer-not-found preserved
- CUST-999 recommendation: HTTP 404 ✅
- CUST-999 follow-up: HTTP 200 (D-04 fallback template — expected) ✅
**Result: PASS**

### Gate 6: Prewarm contract preserved
- ?prewarm=1: HTTP 204 ✅
**Result: PASS**

## REAPPLY freeze

- CustomerTariffAgent: deny-Update:* ✅, TP=True ✅
- CustomerTariffApi: deny-Update:* ✅, TP=True ✅

## Final sweep

| Stack | Policy | TP | Expected | Match |
|-------|--------|----|----------|-------|
| CustomerTariff | Deny | True | Deny + True (untouched) | ✅ |
| CustomerTariffAgent | Deny | True | Deny + True (re-frozen) | ✅ |
| CustomerTariffApi | Deny | True | Deny + True (re-frozen) | ✅ |

## Deployed state

- Memory ID: `tariff_agent_memory-xVDAvVCTtU`
- Runtime: `tariff_agent-O2Hai86N8V`
- API endpoint: `https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/`
- Follow-up route: `GET /recommendations/{customer_id}/follow-up`

## FREEZE-MANIFEST placeholder (for Phase 17)

- `bedrock-agentcore==1.6.4` (bumped from 1.6.3)
- Memory ID: `tariff_agent_memory-xVDAvVCTtU`
- Lockfile hash update required at Phase 17 freeze

Ceremony complete: 2026-05-03T20:30:00Z

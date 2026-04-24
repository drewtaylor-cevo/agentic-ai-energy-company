---
phase: 05-demo-hardening
verified: 2026-04-25T22:34:29Z
status: in_progress
score: "pending — rehearsal section filled by Plan 05"
overrides_applied: 0
requirements_verified:
  - DEMO-01
  - DEMO-02
  - UI-02
human_verification_completed: []
known_issues: []
---

# Phase 5: Demo Hardening Verification Report

**Phase Goal:** The end-to-end demo runs cleanly for all planned personas under realistic conditions and the environment is locked before any presentation.

**Verified:** 2026-04-25T22:34:29Z (Plan 04 completion — No-CRM Audit section)
**Status:** in_progress (Plan 04 complete; Plan 05 appends rehearsal + latency; Plan 07 closes)

## Goal Achievement

### ROADMAP Success Criteria (3)

| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| 1 | End-to-end persona sequence without failure (all 3 personas, live endpoint) | ⏳ PENDING (Plan 05) | Rehearsal results — filled by Plan 05 |
| 2 | <3s warm-median latency for all personas (UI-02) | ⏳ PENDING (Plan 05) | Latency table — filled by Plan 05 |
| 3 | No-CRM validation (structural audit, D-16) | ✓ VERIFIED | See "No-CRM Audit" section below |

### Observable Truths

(Filled by Plan 05 after rehearsal pass.)

### Required Artifacts

(Filled by Plan 05 + Plan 07 — references 05-DEPLOY-OUTPUTS.md, ui/dist/, ui/dist-mock/, DEMO-RUNBOOK.md, and the demo-v1.0 git tag.)

### Behavioral Spot-Checks

(Filled by Plan 07 — npm ci, cdk synth, git tag, live curl.)

## No-CRM Audit (D-16)

**Architectural claim:** The only inputs to savings are dummy data held in this AWS account. There is no CRM client, no HTTP egress to a customer system, no credentials for one. This is a code-structural claim — a reviewer can re-run the grep commands below from the tagged `demo-v1.0` commit and reproduce the same result.

**Audit date:** 2026-04-25T22:34:29Z
**Audit method:** grep against the deployed code trees (`agent/`, `api_lambda/`, `lambda/`, `infrastructure/`). Test trees intentionally excluded — `tests/test_backend_api_smoke.py` uses `requests` to validate the live API, but test code does not ship to AWS.

### Grep 1 — CRM-shaped clients by brand

Command (re-runnable):
```bash
grep -rn -E 'salesforce|hubspot|zendesk|dynamics|pipedrive' agent/ api_lambda/ lambda/ infrastructure/
```

Output:
```
```

Result: **empty / 0 matches** — no CRM brand code in the deployed trees.

### Grep 2 — Generic HTTP clients that could egress to external systems

Command (re-runnable):
```bash
grep -rn -E 'requests\.(get|post|put|delete|patch)|\bimport requests\b|\bimport urllib|\bimport httpx|\bimport aiohttp' agent/ api_lambda/ lambda/
```

Output:
```
```

Result: **empty / 0 matches** — the deployed runtime has no generic HTTP egress path.

### Grep 3 — boto3 service surface enumeration

Command (re-runnable):
```bash
grep -rn 'boto3\.' agent/ api_lambda/ lambda/ infrastructure/
```

Output:
```
agent/agent.py:27:_lambda_client = boto3.client("lambda", region_name=_REGION)
api_lambda/handler.py:39:_agentcore_client = boto3.client(
lambda/handler.py:33:    _dynamodb = boto3.resource("dynamodb")
```

Services referenced (extracted from the grep output above):
- `lambda` — `agent/agent.py:27` invokes the tool Lambda from the Strands agent
- `bedrock-agentcore` — `api_lambda/handler.py:39` invokes the AgentCore runtime from the backend API Lambda (service string on line 40: `"bedrock-agentcore"`)
- `dynamodb` — `lambda/handler.py:33` reads `BillingTable` (DynamoDB resource client)

Result: **every boto3 call targets an internal AWS service within the demo account** — no external-facing client was introduced. Note: CDK constructs in `infrastructure/` do not use `boto3.*` directly at synth time (they use the CDK SDK for CloudFormation); the 3 grep matches above are the complete runtime AWS service surface.

### Data sources (explicit enumeration)

| Source | Type | Provenance | Where it lives at demo time |
|--------|------|------------|-----------------------------|
| DynamoDB `BillingTable` | Customer billing records (3 personas × 12 months) | Seeded from `infrastructure/seed_data/billing_records.py` at deploy time (via `SeederConstruct`) | In the demo AWS account, us-east-1 |
| Tariff catalog JSON | Internal plan portfolio (ECO / VAL / etc.) | Seeded from `infrastructure/seed_data/tariff_plans.json` (bundled as Lambda asset) | Packaged with `ToolsLambda`, deployed to the demo AWS account |
| AgentCore runtime | Bedrock Claude model + tool bindings | Deployed as `CustomerTariffAgent` stack; invokes `lambda/handler.py` for savings math | In the demo AWS account, us-east-1 |

Seed-data file listing (reviewer can re-run `ls -la infrastructure/seed_data/`):
```
total 24
-rw-r--r--  1 drewtaylor  staff     0 23 Apr 20:57 __init__.py
drwxr-xr-x  5 drewtaylor  staff   160 23 Apr 20:57 .
drwxr-xr-x  8 drewtaylor  staff   256 24 Apr 13:41 ..
-rw-r--r--  1 drewtaylor  staff  4169 23 Apr 20:57 billing_records.py
-rw-r--r--  1 drewtaylor  staff  1095 23 Apr 20:57 tariff_plans.json
```

### Conclusion

Structurally, no CRM code path exists. The claim is code-structural (grep-verifiable), not runtime-observational (no airplane-mode test needed). This satisfies Phase 5 Success Criterion #3 per D-16.

## Rehearsal Evidence (filled by Plan 05)

(Plan 05 appends: 2 passes × 3 personas × latency + 2 error paths with verbatim error-copy check.)

## Latency Evidence (filled by Plan 05)

(Plan 05 appends: the persona × cold × warm-median × verdict table.)

## Environment Lock Evidence (filled by Plan 07)

(Plan 07 appends: git tag proof, lockfile reproducibility check, cdk synth green, final gap summary.)

---

_Created by Plan 04 on 2026-04-25T22:34:29Z._
_Next writers: Plan 05 (rehearsal + latency), Plan 07 (lock)._

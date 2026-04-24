---
phase: 05-demo-hardening
plan: 04
type: execute
status: complete
completed: 2026-04-25
---

# Plan 05-04 Summary — No-CRM structural audit

Produced the code-structural proof that no CRM connectivity exists. Three grep commands against the deployed source trees (`agent/`, `api_lambda/`, `lambda/`, `infrastructure/`) — first two empty as required, third contains exactly 3 boto3 call sites, all targeting in-account AWS services.

## Outcome

Phase 5 Success Criterion #3 (no-CRM validation, D-16) is verified and recorded. `05-VERIFICATION.md` is created with the No-CRM Audit section fully populated and clearly-labeled stubs where Plan 05 and Plan 07 will append.

## Evidence

### Grep 1 — CRM-shaped clients by brand

```
$ grep -rn -E 'salesforce|hubspot|zendesk|dynamics|pipedrive' agent/ api_lambda/ lambda/ infrastructure/
(empty)
```

**0 matches.** No salesforce/hubspot/zendesk/dynamics/pipedrive code anywhere in the deployed trees.

### Grep 2 — Generic HTTP clients

```
$ grep -rn -E 'requests\.(get|post|put|delete|patch)|\bimport requests\b|\bimport urllib|\bimport httpx|\bimport aiohttp' agent/ api_lambda/ lambda/
(empty)
```

**0 matches.** No `requests`, `urllib`, `httpx`, or `aiohttp` in the deployed runtime. (Excluded `tests/` — that tree doesn't ship to AWS. `requests` is used there for live smoke testing only.)

### Grep 3 — boto3 service surface enumeration

```
$ grep -rn 'boto3\.' agent/ api_lambda/ lambda/ infrastructure/
agent/agent.py:27:_lambda_client = boto3.client("lambda", region_name=_REGION)
api_lambda/handler.py:39:_agentcore_client = boto3.client(
lambda/handler.py:33:    _dynamodb = boto3.resource("dynamodb")
```

**3 matches, all allowed services:**

| File:Line | Service | Purpose |
|-----------|---------|---------|
| `agent/agent.py:27` | `lambda` | Strands agent invokes ToolsLambda for get_billing_history / simulate_savings |
| `api_lambda/handler.py:39` | `bedrock-agentcore` (verified at line 40) | Backend API invokes the AgentCore runtime |
| `lambda/handler.py:33` | `dynamodb` | Tool Lambda reads BillingTable |

All 3 target in-account AWS services. No external client surface.

### Data sources recorded

| Source | Provenance |
|--------|-----------|
| DynamoDB `BillingTable` | `infrastructure/seed_data/billing_records.py` (4169 bytes, seeded at deploy time) |
| Tariff catalog JSON | `infrastructure/seed_data/tariff_plans.json` (1095 bytes, packaged with ToolsLambda) |
| AgentCore runtime | `CustomerTariffAgent` stack (Phase 2), invokes `lambda/handler.py` for savings math |

Note: plan template referenced `tariff_plans.py`; the actual tree has `tariff_plans.json` — corrected in VERIFICATION.md.

## Self-Check: PASSED

- [x] Grep 1 (CRM brands): 0 matches
- [x] Grep 2 (generic HTTP): 0 matches in deployed trees
- [x] Grep 3 (boto3): 3 matches, all in allowed set (lambda, bedrock-agentcore, dynamodb)
- [x] `05-VERIFICATION.md` exists with frontmatter (`phase`, `requirements_verified`, `status: in_progress`)
- [x] `## No-CRM Audit (D-16)` section exists with 3 sub-sections + re-runnable commands + raw output
- [x] Data sources table has 3 rows (BillingTable, tariff catalog, AgentCore runtime)
- [x] ROADMAP Success Criteria table: #3 = ✓ VERIFIED; #1 and #2 = ⏳ PENDING (Plan 05)
- [x] Stub sections for Plan 05 and Plan 07 labeled `(filled by Plan 05)` / `(filled by Plan 07)`
- [x] Zero `<paste contents of ...>` placeholders remain in committed file

## Key files

### Created
- `.planning/phases/05-demo-hardening/05-VERIFICATION.md` (commit `753afc4`)
- `.planning/phases/05-demo-hardening/05-04-SUMMARY.md` — this file

### Modified
None.

## What this unblocks

- **Plan 05-05** has a clearly labeled append target (`## Rehearsal Evidence (filled by Plan 05)` and `## Latency Evidence (filled by Plan 05)`) for its outputs.
- **Plan 05-07** has `## Environment Lock Evidence (filled by Plan 07)` to append to.
- Phase 5 verifier already has 1/3 ROADMAP success criteria ticked green before rehearsal.

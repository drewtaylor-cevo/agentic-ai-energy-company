# Phase 1: Foundation + Dummy Data - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-23
**Phase:** 01-foundation-dummy-data
**Areas discussed:** Dummy Data Storage

---

## Dummy Data Storage

| Option | Description | Selected |
|--------|-------------|----------|
| S3 JSON files | JSON files in S3, one per customer. Simple to author, realistic data lake path. Already referenced in ROADMAP. | |
| DynamoDB | One table, customer_id (PK) + month (SK). Faster reads, more query-friendly. | ✓ |
| Lambda-local / bundled JSON | JSON files bundled inside Lambda. Fastest to prototype, zero latency, no IAM. Data changes require redeploy. | |

**User's choice:** DynamoDB

---

## DynamoDB Table Design

| Option | Description | Selected |
|--------|-------------|----------|
| Single table — billing only | customer_id (PK) + month (SK). Tariff catalog in separate static file. | ✓ |
| Two tables — billing + tariff catalog | Billing table + tariff_plans table. More production-realistic, more CDK/seeding work. | |
| Single table — billing + tariff (entity pattern) | All entities, prefixed PKs. Most flexible, most complex. | |

**User's choice:** Single table — billing only (tariff catalog in a separate file)

---

## Data Seeding

| Option | Description | Selected |
|--------|-------------|----------|
| CDK custom resource | Deploys table + seeds data as part of `cdk deploy`. One-command setup. | ✓ |
| Seed script (Python CLI) | Separate seed.py run after deploy. Easier to iterate on data. Two-step setup. | |
| Manual / AWS CLI | Hand-seeded. Fine for a spike, slow to reproduce. | |

**User's choice:** CDK custom resource

---

## Tariff Catalog Location

| Option | Description | Selected |
|--------|-------------|----------|
| JSON file in Lambda package | tariff_plans.json bundled with Lambda code. Zero latency, easy to edit, no extra AWS resources. | ✓ |
| SSM Parameter Store | JSON string in SSM parameter. Updatable without redeploy, adds SSM read latency and IAM. | |
| S3 JSON file | tariff_plans.json in S3. Easy to inspect and replace. Adds S3 read latency and IAM. | |

**User's choice:** JSON file in Lambda package

---

## Claude's Discretion

- CDK language (Python recommended for consistency with Strands SDK)
- DynamoDB billing record schema (field names, attribute types)
- Tariff plan catalog schema (plan fields, rating criteria)
- Customer persona design (names, archetypes, usage levels)
- AWS Region confirmation (us-east-1 recommended but not locked in discussion)

## Deferred Ideas

- AWS Region: Surface in research phase — us-east-1 recommended, ap-southeast-2 lacks AgentCore Registry support
- Strands SDK vs classic Bedrock Agents: Phase 2 decision after confirming SDK availability in target region

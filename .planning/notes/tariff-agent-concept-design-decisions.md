---
name: Tariff Agent — concept & design decisions
description: Core design decisions for the Customer Tariff & Billing Optimisation Agent captured during initial exploration
type: note
date: 2026-04-23
context: Energy & Utilities customer engagement, AWS Bedrock AgentCore
---

## Customer Tariff & Billing Optimisation Agent

### What it does

Analyses a customer's billing history → recommends optimal tariff plans → simulates projected savings → surfaces recommendation to call centre agent.

### Core design decisions

**Data source:** CRM billing history (internal). No customer upload required — agent works with data the utility already holds.

**User:** Call centre agent (agent-assist). Not customer-facing in v1. Agent is a tool the call centre rep uses while the customer is on the line.

**Recommendation tracks:** Two options presented per customer:
- **Green** — most energy-efficient plan
- **Cheapest** — lowest projected cost plan

Both options are always surfaced (separate but equal). Customer/agent chooses based on priority.

**Savings simulation:** Projects `~$X/month` saving based on the customer's last 12 months of billing history. 12-month window smooths seasonal variation and is easy to explain to the customer.

**Autonomy level:** Recommendation only — no auto-switching. The agent surfaces the plan and saving; a human confirms before any change is made.

### AgentCore angle

- Personalisation agent: usage pattern analysis tailored per customer
- Decision agent: recommends from plan portfolio based on individual history

### Business value

- Customer retention: gives the call centre agent a compelling reason to keep the customer on the line and on the books
- Trust / CX: "here's what we'd save you" is a trust-building moment, not a sales pitch

### Demo approach

Working demo with dummy data. Dummy data controls the narrative — design the scenario to make the savings delta compelling and the two-track recommendation clear.

### Demo hook

> "Customer bill → instant personalised savings plan"

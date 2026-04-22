# Customer Tariff & Billing Optimisation Agent

## What This Is

An AI-powered call centre agent-assist tool for an Energy & Utilities provider. It analyses a customer's 12-month CRM billing history, recommends the two most optimal tariff plans (Green and Cheapest), and surfaces projected monthly savings — giving call centre agents an instant, personalised savings plan to present while the customer is on the line.

## Core Value

A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Retrieve and analyse 12 months of CRM billing history per customer
- [ ] Recommend the most energy-efficient (Green) tariff plan available
- [ ] Recommend the lowest-cost (Cheapest) tariff plan available
- [ ] Simulate projected monthly savings (~$X/month) for each recommendation
- [ ] Present both recommendations to the call centre agent via an agent-assist interface
- [ ] Demo runs end-to-end with realistic dummy data (no live CRM required)

### Out of Scope

- Auto-switching plans without human confirmation — recommendation only (v1)
- Customer-facing self-service portal — call centre agent-assist first (v2 candidate)
- Third-party / competitor plan comparison — internal plan portfolio only
- Real CRM integration — dummy data for demo, live integration post-demo

## Context

**Engagement type:** Customer demo / proof of concept for an Energy & Utilities provider.

**Platform:** AWS Bedrock AgentCore — Personalisation + Decision agent pattern.

**Data source:** Internal CRM billing history (12 months per customer). The utility already holds this data — no customer upload required.

**Recommendation design:** Two tracks always presented together:
- **Green** — most energy-efficient plan in the portfolio
- **Cheapest** — lowest projected cost based on usage patterns

Neither track is ranked above the other. The call centre agent (and ultimately the customer) chooses based on their priority.

**Savings simulation:** Projected as ~$X/month, calculated against the customer's 12-month billing average. 12 months smooths seasonal variation and is easy to explain to the customer.

**Demo approach:** Working demo with carefully designed dummy data. Data will be crafted to make the savings delta compelling and the two-track recommendation clearly differentiated (e.g., Green saves $30/month, Cheapest saves $55/month).

**Demo hook:** "Customer bill → instant personalised savings plan"

## Constraints

- **Platform:** AWS Bedrock AgentCore — agent architecture must fit Bedrock's patterns
- **Demo scope:** Dummy data only — no live CRM connectivity in v1
- **Autonomy:** No autonomous plan switching — recommendations surface, humans decide
- **Audience:** Call centre agents are the end user — UX must work within a call context (fast, scannable, actionable)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Call centre agent-assist first (not customer-facing) | Reduces scope, controls UX, faster to demo | — Pending |
| Two fixed recommendation tracks (Green / Cheapest) | Keeps the recommendation scannable; avoids decision paralysis | — Pending |
| 12-month billing window for savings simulation | Smooths seasonal variation; easy to explain | — Pending |
| Recommendation-only (no auto-switching) | Trust and compliance — human confirms before anything changes | — Pending |
| Dummy data for demo | Controls the narrative; no integration risk for the POC | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-23 after initialization*

# Requirements: Customer Tariff & Billing Optimisation Agent

**Defined:** 2026-04-23
**Core Value:** A call centre agent can open any customer account and immediately see exactly how much that customer could save and on which plan — making every retention conversation data-driven.

## v1 Requirements

Requirements for the working demo. Each maps to roadmap phases.

### Data (DATA)

- [ ] **DATA-01**: System retrieves 12 months of billing history per customer, including monthly kWh usage, monthly cost, and current tariff plan details
- [ ] **DATA-02**: Dummy dataset covers at least 3 customer personas with meaningfully different usage profiles (e.g. high-usage residential, medium-usage, low-usage or seasonal-heavy)
- [ ] **DATA-03**: Usage data stored in kWh (not dollars) to produce defensible savings calculations that hold up when a customer challenges the figures on a call

### Recommendations (REC)

- [ ] **REC-01**: Agent identifies and recommends the most energy-efficient (Green) tariff plan available in the portfolio for the customer's usage pattern
- [ ] **REC-02**: Agent identifies and recommends the lowest projected cost (Cheapest) tariff plan available for the customer's usage pattern
- [ ] **REC-03**: Both Green and Cheapest recommendations are always surfaced simultaneously — neither is ranked above the other; the call centre agent and customer choose based on their priority

### Savings Simulation (SAV)

- [ ] **SAV-01**: For each recommendation, agent displays projected monthly saving in dollars (~$X/month) calculated against the customer's 12-month billing average on their current plan
- [ ] **SAV-02**: Annual equivalent saving ($X/year) is displayed alongside the monthly figure to amplify the emotional impact of the recommendation
- [ ] **SAV-03**: Savings are calculated by a deterministic tool function — LLM handles orchestration and narrative, arithmetic is done in code (not by the LLM)

### Agent-Assist UI (UI)

- [ ] **UI-01**: Both recommendation cards (Green and Cheapest) are visible above the fold in the call centre agent-assist interface — no scroll required during a live customer call
- [ ] **UI-02**: From customer account lookup to displayed recommendations renders in under 3 seconds (pre-computed dummy data permitted to meet this target)

### Demo (DEMO)

- [ ] **DEMO-01**: End-to-end demo runs on dummy data with no live CRM connectivity required — the demo environment is fully self-contained
- [ ] **DEMO-02**: Dummy data is intentionally designed so that the Green track saves ~$30/month and the Cheapest track saves ~$55/month per persona — the savings delta tells a clear story without ambiguity

## v2 Requirements

Deferred — not in current demo scope.

### Agent-Assist Enhancements

- **UI-03**: LLM-generated call script snippet — a one-liner the call centre agent can use verbatim when presenting the recommendation
- **UI-04**: LLM-generated usage narrative — a one-sentence customer profile ("heavy morning user, above-average winter peaks") displayed on the recommendation card

### Demo Hardening

- **DEMO-03**: Pre-warm script that invokes the agent once before the live demo to avoid cold-start latency
- **DEMO-04**: Frozen demo environment with pinned dependency versions and locked AWS account state established 48 hours before the presentation

### Production Path

- **PROD-01**: Live CRM integration replacing dummy data source
- **PROD-02**: Customer-facing self-service portal (v2 of the agent-assist tool)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-switching plans | Recommendation only — human confirms before any plan change |
| Competitor / third-party plan comparison | Internal plan portfolio only for demo |
| Mobile / responsive layout | Desktop-first (1280px) for call centre context |
| OAuth / authentication | Not needed for demo |
| Real-time tariff price feeds | Static dummy tariff rates sufficient for demo |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | TBD | Pending |
| DATA-02 | TBD | Pending |
| DATA-03 | TBD | Pending |
| REC-01 | TBD | Pending |
| REC-02 | TBD | Pending |
| REC-03 | TBD | Pending |
| SAV-01 | TBD | Pending |
| SAV-02 | TBD | Pending |
| SAV-03 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| DEMO-01 | TBD | Pending |
| DEMO-02 | TBD | Pending |

**Coverage:**
- v1 requirements: 13 total
- Mapped to phases: 0 (pending roadmap)
- Unmapped: 13 ⚠️

---
*Requirements defined: 2026-04-23*
*Last updated: 2026-04-23 after initial definition*

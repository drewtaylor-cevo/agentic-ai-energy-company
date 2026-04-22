# Phase 1: Foundation + Dummy Data - Context

**Gathered:** 2026-04-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the AWS infrastructure skeleton and engineer dummy customer billing data that drives correct, defensible savings calculations — with no AI in the call path. The deliverables are: a DynamoDB billing table seeded with 3+ customer personas, a Lambda-bundled tariff plan catalog, and CDK that deploys and seeds everything in one command.

New capabilities (live CRM integration, real-time pricing, agent orchestration) belong in later phases.

</domain>

<decisions>
## Implementation Decisions

### Dummy Data Storage
- **D-01:** Customer billing history lives in **DynamoDB** — single table, `customer_id` (PK) + `month` (SK), one item per month per customer (12 items per customer). Not S3, not Lambda-local.
- **D-02:** Tariff plan catalog is **not** in DynamoDB. It lives as a `tariff_plans.json` file bundled inside the Lambda package — zero latency, no extra AWS resources, easy to edit between demo runs.
- **D-03:** Dummy data is seeded via a **CDK custom resource** — one `cdk deploy` command stands up the table and populates it. No separate seed script required.

### Claude's Discretion
- **CDK language:** Python CDK preferred for consistency with the Strands SDK / agent code (one language across the stack). Switch to TypeScript only if a specific L3 construct requires it.
- **DynamoDB billing record schema:** Each item should include at minimum: `customer_id`, `month` (YYYY-MM), `usage_kwh` (kWh usage), `cost_usd` (billed amount), `plan_id` (current tariff plan). Claude determines the exact attribute names.
- **Tariff plan catalog schema:** Each plan entry should include: `plan_id`, `plan_name`, `rate_per_kwh`, `daily_supply_charge`, `green_score` (for ranking Green plans), `plan_type` (e.g., flat_rate, time_of_use, green_premium). Claude determines exact structure.
- **Customer personas:** 3+ personas covering meaningfully different usage profiles (e.g., high-usage residential, mid-usage, low-usage or seasonal-heavy). Claude engineers the data so that the flagship persona yields Green savings ~$30/month and Cheapest savings ~$55/month (DEMO-02 requirement). Names and archetypes at Claude's discretion.
- **AWS Region:** us-east-1 strongly recommended — ap-southeast-2/Sydney does NOT support AgentCore Registry. CDK should default to us-east-1 unless the user confirms otherwise before deployment.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements
- `.planning/REQUIREMENTS.md` — Full v1 requirements. Phase 1 maps to DATA-01, DATA-02, DATA-03, DEMO-02. Read §Data and §Demo sections.

### Project Context
- `.planning/PROJECT.md` — Core value, constraints, key decisions, and demo approach. Savings targets ($30/month Green, $55/month Cheapest) and kWh-based billing requirement are defined here.

### Roadmap
- `.planning/ROADMAP.md` — Phase 1 success criteria (4 items). All 4 must be TRUE before Phase 2 begins.

### State / Blockers
- `.planning/STATE.md` §Blockers — Pre-phase actions required: AWS Claude model access enablement, region confirmation (us-east-1), Strands SDK availability check.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — greenfield project. No existing components, hooks, or utilities.

### Established Patterns
- None yet — this phase establishes the patterns downstream phases will follow.

### Integration Points
- Phase 2 (AgentCore Agent) will call `get_billing_history` (reads DynamoDB billing table) and `simulate_savings` (reads tariff_plans.json + billing data). The data schema established in Phase 1 becomes the contract for Phase 2 tool implementations.

</code_context>

<specifics>
## Specific Ideas

- Savings calculations must be **deterministic and done in code** — not by the LLM (SAV-03). The `simulate_savings` tool should be independently verifiable against a spreadsheet.
- The savings delta must be compelling and clearly differentiated: Green ≈ $30/month, Cheapest ≈ $55/month. The dummy data should be engineered to produce these figures reliably for the flagship persona.
- Usage stored in kWh (not dollars) — required so savings figures can be independently recalculated and defended on a customer call (DATA-03).

</specifics>

<deferred>
## Deferred Ideas

- AWS Region: Not locked in this discussion — flagged as a pre-deployment decision. Research agent should surface whether us-east-1 is the correct choice given the client's location and AgentCore feature requirements.
- Strands SDK vs classic Bedrock Agents: Open question for Phase 2 — verify Strands availability and stability in the target region before Phase 2 begins.

</deferred>

---

*Phase: 01-foundation-dummy-data*
*Context gathered: 2026-04-23*

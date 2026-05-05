# Customer Tariff & Billing Optimisation Agent

An AI-powered call centre agent-assist tool for an Energy & Utilities provider. It analyses a customer's 12-month billing history, recommends the two most optimal tariff plans (Green and Cheapest), and surfaces projected monthly and annual savings — giving call centre agents an instant, personalised savings plan to present while the customer is on the line.

## Architecture

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────────────┐
│  React / Vite │────▶│  API Gateway HTTP v2  │────▶│  API Lambda (proxy)  │
│  (Tailwind)   │     │  CORS allow-all       │     │  30s timeout         │
└──────────────┘     └──────────────────────┘     └─────────┬────────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────────┐
                                                  │  Bedrock AgentCore   │
                                                  │  (Strands SDK agent) │
                                                  │  Claude Sonnet 4.6   │
                                                  │                      │
                                                  │  ┌────────────────┐  │
                                                  │  │  Supervisor    │  │
                                                  │  │  (code router) │  │
                                                  │  └──┬─────┬───┬──┘  │
                                                  │     │     │   │     │
                                                  │     ▼     ▼   ▼     │
                                                  │  Tariff Hardship    │
                                                  │  Spec.  Spec.      │
                                                  │     │   Compliance  │
                                                  │     │   Reviewer    │
                                                  └─────┼──────────────┘
                                                        │
                                                        ▼
                                                  ┌──────────────────────┐
                                                  │  Tools Lambda        │
                                                  │  get_billing_history │
                                                  │  simulate_savings    │
                                                  │  detect_bill_shock   │
                                                  │  get_hardship_flag   │
                                                  └─────────┬────────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────────┐
                                                  │  DynamoDB            │
                                                  │  Billing history     │
                                                  │  (125 seeded records)│
                                                  └──────────────────────┘
```

The system is deployed across three CDK stacks in `us-east-1`:

1. **FoundationStack** — DynamoDB billing table, Tools Lambda (billing history retrieval + savings calculation + hardship flag + category), data seeder (10 personas × 12 months + PROFILE rows)
2. **AgentCoreStack** — Bedrock AgentCore managed runtime running a Strands SDK agent in a Docker container (Python 3.12, ARM64). The agent uses a **multi-agent supervisor pattern**: a code-side Supervisor router dispatches to specialist agents (TariffSpecialist, HardshipSpecialist) and a deterministic ComplianceReviewer signs off on every response.
3. **BackendApiStack** — API Gateway HTTP API v2 + API Lambda that proxies `GET /recommendations/{customer_id}` to the AgentCore runtime

Cross-stack wiring uses SSM parameters to avoid hard CloudFormation export dependencies.

### Multi-Agent Supervisor

The `agent/agent.py::invoke()` function acts as a **Supervisor dispatcher** that routes requests to specialist agents:

```
invoke(payload)
  ├── action == "follow_up" → draft_follow_up() (existing handler)
  └── action == "recommend"
       ├── get_hardship_flag(customer_id)
       │    ├── hardship == true
       │    │    ├── extract hardship_category (default "other")
       │    │    └── HardshipSpecialist.handle(payload + category)
       │    └── hardship == false → TariffSpecialist.handle()
       ├── ComplianceReviewer.review(response)
       │    ├── recommendation: reference_period + no_upsell
       │    └── hardship: no_tariff_data + tool_restriction + financial_isolation
       └── attach compliance_review + supervisor_trace
```

- **TariffSpecialist** (`agent/specialists/tariff.py`) — Extracted recommendation logic. Owns the Strands Agent call, FourToolCapHook budget, structured output, D-01 fallback chain, and narrative attachment. Reuses the existing module-level `_agent` instance (no new Agent construction).
- **HardshipSpecialist** (`agent/specialists/hardship.py`) — Code-side only, no LLM turn. Produces a typed `HardshipResponse` with category-specific routing, call scripts, and permitted actions. Has no access to tariff tools. Supports four hardship categories: `payment_difficulty`, `medical_equipment`, `family_violence`, `other`.
- **ComplianceReviewer** (`agent/specialists/compliance.py`) — Deterministic code-side checker (no LLM, no network I/O). Runs five AER NECF-aligned rules: reference-period disclosure, no upsell-to-disadvantage, hardship-flag cross-check, hardship category tool restriction, and family violence financial isolation.
- **AgentRole Protocol** (`agent/roles.py`) — `@runtime_checkable` Protocol with a single `handle(payload) -> dict` method. All specialists satisfy it.

Two new public response fields surface the orchestration for demo audiences:
- `compliance_review` — the ComplianceReviewer's pass/fail verdict, rules checked, and timestamp
- `supervisor_trace` — which specialist was selected, why, and whether compliance ran

Both collapse when `?narrative=off` is active (DEMO-07 kill-switch).

## Key Design Decisions

- **Multi-agent supervisor pattern** — The monolithic `invoke()` is decomposed into a code-side Supervisor router + three specialist agents (TariffSpecialist, HardshipSpecialist, ComplianceReviewer). The Supervisor uses `if/elif` dispatch — zero additional LLM calls for routing. The ComplianceReviewer is pure Python over dicts — microseconds, not seconds.
- **Deterministic savings** — All arithmetic lives in `lambda/handler.py::simulate_savings_pure`. The LLM orchestrates tool calls and composes natural language but never performs math (SAV-03).
- **Compliance gate on every response** — Five AER NECF-aligned checks run on every outbound response: reference-period disclosure, no upsell-to-disadvantage, hardship-flag cross-check, hardship category tool restriction (verifies tools used are within the category's permitted set), and family violence financial isolation (verifies zero financial terminology in family_violence responses). Failures attach a warning rather than blocking the response (D-04 never-500 takes precedence).
- **Typed hardship categories** — Hardship handling is no longer binary. Four categories (`payment_difficulty`, `medical_equipment`, `family_violence`, `other`) drive distinct call scripts, tool permissions, routing targets, and compliance checks. Category detection is deterministic from customer data (DynamoDB PROFILE row), not inferred by the LLM. A `family_violence` customer is immediately routed to a specialist safety team with zero financial terminology in any response field.
- **LLM-generated narratives** — Claude generates a one-sentence usage narrative and a call script snippet per recommendation card. Validated by length/content guardrails with deterministic fallbacks on failure.
- **Mock fallback** — When `VITE_API_URL` is unset, the UI reads from a local fixture so the full flow is demoable without a deployed backend.
- **Feature flags** — `?narrative=off` URL parameter collapses the UI to the v1.0 shape (no narrative text, no compliance review, no supervisor trace). Useful as a kill switch during live demos.

## Demo Personas

### Recommendation Personas

| ID | Name | Avg kWh/mo | Green Saving | Cheapest Saving |
|----|------|-----------|-------------|----------------|
| CUST-001 | Sarah Chen | 500 | ~$30/mo | ~$55/mo |
| CUST-002 | Marcus Webb | 282 | ~$17/mo | ~$31/mo |
| CUST-003 | Elena Vasquez | 233 | ~$14/mo | ~$26/mo |

### Hardship Personas

| ID | Category | Routing Target | Demo Purpose |
|----|----------|---------------|--------------|
| CUST-006 | *(legacy, no category)* | hardship_team | Backward-compat — defaults to "other" |
| CUST-007 | `payment_difficulty` | hardship_team | Payment plan flow |
| CUST-008 | `medical_equipment` | priority_services_team | Priority services routing |
| CUST-009 | `family_violence` | family_violence_team | Safety-first isolation — zero financial terms |
| CUST-010 | `other` | hardship_team | Generic hardship (backward compat proof) |

All personas are seeded into DynamoDB with 12 months of billing history (Apr 2025 – Mar 2026) on the Standard Rate plan. Hardship personas have a PROFILE row with `hardship_flag: true` and `hardship_category` set.

## Tariff Plans

| Plan ID | Name | Rate/kWh | Type | Renewable |
|---------|------|----------|------|-----------|
| STD | Standard Rate | $0.32 | Flat rate | 0% |
| ECO | EcoFlex 100 | $0.26 | Green premium | 100% |
| VAL | Value 12 | $0.21 | Flat rate | 0% |
| TOU | Flex Time | $0.36 | Time of use | 20% |

## Project Structure

```
├── app.py                      # CDK entry point (3 stacks)
├── cdk.json                    # CDK configuration
├── infrastructure/
│   ├── foundation_stack.py     # Stack 1: DynamoDB + Tools Lambda + Seeder
│   ├── agentcore_stack.py      # Stack 2: Bedrock AgentCore runtime
│   ├── backend_api_stack.py    # Stack 3: API Gateway + API Lambda
│   ├── constructs/
│   │   ├── billing_table.py    # DynamoDB table construct
│   │   ├── tools_lambda.py     # Tools Lambda construct
│   │   ├── seeder.py           # Custom resource that seeds demo data
│   │   ├── agent_runtime.py    # AgentCore runtime construct
│   │   └── backend_api.py      # API Gateway + Lambda construct
│   └── seed_data/
│       ├── billing_records.py  # 10 personas × 12 months of billing data + PROFILE rows
│       └── tariff_plans.json   # Tariff catalog
├── agent/
│   ├── agent.py                # Supervisor dispatcher (routes to specialists)
│   ├── Dockerfile              # ARM64 Python 3.12 container
│   ├── requirements.txt        # strands-agents, bedrock-agentcore, boto3
│   ├── providers.py            # CustomerDataProvider Protocol (Phase 12)
│   ├── roles.py                # AgentRole Protocol + ComplianceReview/SupervisorTrace schemas
│   ├── specialists/
│   │   ├── __init__.py
│   │   ├── tariff.py           # TariffSpecialist (recommendation logic)
│   │   ├── hardship.py         # HardshipSpecialist (typed category routing)
│   │   ├── hardship_config.py  # Category registry (types, tool sets, routing targets)
│   │   └── compliance.py       # ComplianceReviewer (deterministic compliance gate)
│   └── narrative/
│       ├── prompt.txt          # System prompt for narrative generation
│       ├── validators.py       # Length/content guardrails
│       ├── fallbacks.py        # Deterministic fallback strings
│       ├── shape.py            # Shape token builder for structured output
│       └── banned_terms.py     # Forbidden terms filter
├── lambda/
│   ├── handler.py              # Tools Lambda: get_billing_history + simulate_savings
│   └── tariff_plans.json       # Tariff catalog (bundled in Lambda asset)
├── api_lambda/
│   ├── handler.py              # API Lambda: proxies to AgentCore runtime
│   └── requirements.txt        # boto3 (bundled for bedrock-agentcore support)
├── ui/                         # React 19 + Vite + TypeScript + Tailwind CSS 4
│   ├── src/
│   │   ├── App.tsx             # Main app: state machine driving UI
│   │   ├── components/
│   │   │   ├── LookupForm.tsx          # Customer ID input form
│   │   │   ├── PersonaChips.tsx        # Quick-pick persona buttons
│   │   │   ├── RecommendationCard.tsx  # Green/Cheapest savings card
│   │   │   ├── RecommendationSkeletons.tsx  # Loading placeholders
│   │   │   ├── ErrorAlert.tsx          # Error display
│   │   │   ├── EmptyState.tsx          # Initial empty state
│   │   │   └── VersionIndicator.tsx    # v2.0 · <git-sha> marker
│   │   ├── hooks/
│   │   │   └── useRecommendations.ts   # Data hook (fetch or mock)
│   │   ├── lib/
│   │   │   ├── types.ts        # TypeScript types
│   │   │   ├── validate.ts     # Customer ID validation
│   │   │   ├── flags.ts        # Feature flag parsing
│   │   │   ├── errors.ts       # Error copy by HTTP status
│   │   │   └── mock/           # Mock data fixtures
│   │   └── personas.ts         # Persona definitions
│   └── vite.config.ts          # Vite + Tailwind + git SHA injection
├── demo/
│   └── mockups/
│       ├── email-nudge.html    # Proactive monthly savings email mockup
│       └── portal-tile.html    # Customer self-service portal mockup
├── scripts/
│   ├── prewarm.py              # Pre-warm CLI (eliminates cold starts)
│   ├── demo-keepalive.sh       # 10-min ping loop (beats 15-min idle timeout)
│   ├── capture_samples.py      # Sample response capture utility
│   ├── hash_dist.sh            # Build artifact hash checker
│   └── hash_synth_assets.sh    # CDK synth asset hash checker
├── tests/                      # ~860 pytest tests
│   ├── test_cdk_synth.py               # CDK synthesis validation
│   ├── test_agent_*.py                 # Agent construction, tools, narrative
│   ├── test_backend_api_*.py           # API handler, synth, smoke
│   ├── test_simulate_savings.py        # Savings arithmetic
│   ├── test_get_billing_history.py     # Billing data retrieval
│   ├── test_narrative_validator.py     # Narrative guardrail validation
│   ├── test_fallbacks_pass_validator.py # Fallback string compliance
│   ├── test_schema.py                  # Response schema validation
│   ├── test_shape_tokens.py            # Shape token builder
│   ├── test_seeder_smoke.py            # Data seeder
│   ├── test_roles.py                   # AgentRole Protocol + schema tests
│   ├── test_specialists.py             # Specialist unit tests
│   ├── test_supervisor.py              # Supervisor routing tests
│   ├── test_supervisor_properties.py   # Property-based tests (hypothesis)
│   ├── test_hardship_config.py         # Hardship category registry tests
│   ├── test_hardship_scripts.py        # Category-specific call script validation
│   ├── test_hardship_categories.py     # CP-1/CP-5 property-based tests
│   ├── test_hardship_specialist_integration.py  # Typed hardship integration tests
│   ├── test_e2e_hardship_categories.py # End-to-end typed hardship tests
│   ├── test_compliance.py              # Compliance reviewer tests (CP-2/CP-3)
│   └── test_observability.py           # Compliance/supervisor trace observability
├── requirements.txt            # Pinned production deps (pip-compile, hashed)
└── requirements-dev.txt        # Dev deps: pytest, pytest-mock, requests
```

## Prerequisites

- Python 3.12+
- Node.js 18+ and npm
- AWS CDK CLI (`npm install -g aws-cdk`)
- AWS credentials configured for `us-east-1`
- Docker (for building the AgentCore agent container and Lambda bundling)

## Setup

### Backend (CDK + Python)

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install production dependencies
pip install -r requirements.txt

# Install dev dependencies (for testing)
pip install -r requirements-dev.txt
```

### Frontend (React)

```bash
cd ui
npm install
```

## Deployment

Deploy all three stacks in order:

```bash
# Deploy foundation (DynamoDB + Tools Lambda + seed data)
cdk deploy CustomerTariff

# Deploy AgentCore runtime
cdk deploy CustomerTariffAgent

# Deploy API Gateway + API Lambda
cdk deploy CustomerTariffApi
```

To enable Provisioned Concurrency on the API Lambda (eliminates cold starts for demos):

```bash
cdk deploy CustomerTariffApi -c demo_pc=1
```

## Running the UI

### Development (mock mode)

With `VITE_API_URL` unset (default in `.env.development`), the UI uses local mock data:

```bash
cd ui
npm run dev
```

### Development (live backend)

```bash
cd ui
VITE_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com npm run dev
```

### Production build

```bash
cd ui
npm run build           # Full build (requires VITE_API_URL)
npm run build:mock      # Mock-only build (no backend needed)
```

## Testing

### Python tests

```bash
# Run all offline tests (~860 tests, includes property-based tests via hypothesis)
pytest

# Run only smoke tests (requires deployed AWS stack + credentials)
pytest -m smoke

# Run only the property-based supervisor tests
pytest tests/test_supervisor_properties.py -v
```

### UI tests

```bash
cd ui
npm run test            # Single run
npm run test:watch      # Watch mode
```

## Demo Tooling

### Pre-warm (eliminate cold starts)

Warms all three personas via the `?prewarm=1` query branch, waits 30s for the microVM pool to settle, then measures response times against a 3000ms median gate:

```bash
BACKEND_API_URL=https://... python3 scripts/prewarm.py
# or from ui/:
BACKEND_API_URL=https://... npm run prewarm
```

Exit codes: `0` = all personas under gate, `1` = gate fail or HTTP error, `2` = setup error.

### Keep-alive (beat idle timeout)

Pings the API every 10 minutes with rotating personas to prevent AgentCore's 15-minute microVM idle timeout from evicting warm instances:

```bash
export BACKEND_API_URL=https://...
bash scripts/demo-keepalive.sh
# Ctrl-C to stop
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Infrastructure | AWS CDK (Python), CloudFormation |
| AI Agent | AWS Bedrock AgentCore, Strands SDK, Claude Sonnet 4.6 |
| Agent Architecture | Multi-agent supervisor (code-side router + 3 specialists) |
| Backend | AWS Lambda (Python 3.12), API Gateway HTTP v2 |
| Database | Amazon DynamoDB |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui |
| Testing | pytest (Python), hypothesis (property-based), Vitest (TypeScript) |
| Dependencies | pip-compile with hash verification |

## Demo Mockups

The `demo/mockups/` directory contains two HTML mockups that show how the same `GET /recommendations/{customer_id}` API can be reused across customer-facing surfaces beyond the call centre agent-assist UI. Open them directly in a browser — they're self-contained, no build step required.

### Email Nudge (`email-nudge.html`)

A proactive monthly email that surfaces a customer's potential savings directly in their inbox. Renders the same Green/Cheapest recommendation pair with LLM-generated narrative and "Why this plan" copy, wrapped in a realistic email client chrome (sender, subject line, footer with unsubscribe).

Key points from the mockup's annotation layer:
- Same API response, same byte-identical dollar values, same Pydantic-validated narrative strings
- Batch-scheduled monthly send with a material-delta filter (only email when savings ≥ $10/mo)
- Highest-stakes surface — no kill switch once sent, narrative validation must be airtight before the batch fires, and proactive savings claims need legal review for regulatory compliance (AEMC, ACCC)

### Customer Portal Tile (`portal-tile.html`)

A mobile-first self-service portal view (375–428px device frame) where the customer sees their own savings recommendations after logging in. Includes a hero savings callout, the same two recommendation cards with narrative and call script, and actionable "Switch to EcoFlex" / "Switch to Value 12" CTAs.

Key points from the mockup's annotation layer:
- Same API, same kill switch (`?narrative=off`), same freeze surface as the agent-assist build
- New requirements: customer authentication (OIDC/MFA), self-serve plan-change workflow, mobile-responsive layout, and rate limiting
- No ranking between Green and Cheapest — the customer chooses, matching the call-centre framing (REC-03)
- Narrative and "Why this plan" fields remain digit-free and currency-free, enforced by the same Pydantic validator regardless of surface

Both mockups demonstrate that the v2.0 backend is surface-agnostic — the same API, validation, and freeze controls serve the internal agent-assist tool, a batch email pipeline, and a customer-facing portal without modification.

## API

### GET /recommendations/{customer_id}

Returns Green and Cheapest tariff recommendations with projected savings.

**Path parameter:** `customer_id` — must match `^CUST-\d{3,6}$`

**Query parameters:**
- `prewarm=1` — triggers a warm-only invocation, returns HTTP 204 with no body

**Success response (200):**
```json
{
  "kind": "recommendation",
  "green": {
    "plan_name": "EcoFlex 100",
    "monthly_saving": 30.0,
    "annual_saving": 360.0,
    "usage_narrative": "Your household averages 500 kWh per month...",
    "call_script": "Based on your usage, switching to EcoFlex 100..."
  },
  "cheapest": {
    "plan_name": "Value 12",
    "monthly_saving": 55.0,
    "annual_saving": 660.0,
    "usage_narrative": "Your household averages 500 kWh per month...",
    "call_script": "Based on your usage, switching to Value 12..."
  },
  "reasoning_trace": [...],
  "compliance_review": {
    "verdict": "pass",
    "rules_checked": ["reference_period_disclosure", "no_upsell_to_disadvantage"],
    "failures": [],
    "reviewed_at": "2025-01-15T10:30:00+00:00"
  },
  "supervisor_trace": {
    "routed_to": "TariffSpecialist",
    "routing_reason": "Standard recommendation request",
    "hardship_checked": true,
    "compliance_reviewed": true
  }
}
```

**Hardship response (200):**
```json
{
  "kind": "hardship",
  "customer_id": "CUST-006",
  "category": "other",
  "reason": "...",
  "routing_target": "hardship_team",
  "call_script": "...",
  "permitted_actions": ["schedule_callback"],
  "compliance_review": {
    "verdict": "pass",
    "rules_checked": ["hardship_no_tariff_data", "hardship_category_tool_restriction"],
    "failures": [],
    "reviewed_at": "2025-01-15T10:30:00+00:00"
  },
  "supervisor_trace": {
    "routed_to": "HardshipSpecialist",
    "routing_reason": "Customer hardship flag is true",
    "hardship_checked": true,
    "compliance_reviewed": true
  }
}
```

**Typed hardship response (200) — family_violence example:**
```json
{
  "kind": "hardship",
  "customer_id": "CUST-009",
  "category": "family_violence",
  "reason": "This customer requires immediate, confidential connection to our specialist safety team.",
  "routing_target": "family_violence_team",
  "call_script": "Your safety is our priority — I am connecting you directly to our specialist support team now.",
  "permitted_actions": ["schedule_callback"],
  "compliance_review": {
    "verdict": "pass",
    "rules_checked": ["hardship_no_tariff_data", "hardship_category_tool_restriction", "family_violence_no_financial_content"],
    "failures": [],
    "reviewed_at": "2025-01-15T10:30:00+00:00"
  },
  "supervisor_trace": {
    "routed_to": "HardshipSpecialist",
    "routing_reason": "Customer hardship flag is true",
    "hardship_checked": true,
    "compliance_reviewed": true
  }
}
```

Note: `compliance_review` and `supervisor_trace` are public fields (not stripped by the API Lambda). They are omitted when `?narrative=off` is active.

**Error responses:** 400 (invalid ID), 404 (unknown customer), 504 (AgentCore timeout), 502 (AgentCore error)

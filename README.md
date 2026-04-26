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
                                                  │  Claude 3.7 Sonnet   │
                                                  └─────────┬────────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────────┐
                                                  │  Tools Lambda        │
                                                  │  get_billing_history │
                                                  │  simulate_savings    │
                                                  └─────────┬────────────┘
                                                            │
                                                            ▼
                                                  ┌──────────────────────┐
                                                  │  DynamoDB            │
                                                  │  Billing history     │
                                                  │  (36 seeded records) │
                                                  └──────────────────────┘
```

The system is deployed across three CDK stacks in `us-east-1`:

1. **FoundationStack** — DynamoDB billing table, Tools Lambda (billing history retrieval + savings calculation), data seeder (3 personas × 12 months)
2. **AgentCoreStack** — Bedrock AgentCore managed runtime running a Strands SDK agent in a Docker container (Python 3.12, ARM64)
3. **BackendApiStack** — API Gateway HTTP API v2 + API Lambda that proxies `GET /recommendations/{customer_id}` to the AgentCore runtime

Cross-stack wiring uses SSM parameters to avoid hard CloudFormation export dependencies.

## Key Design Decisions

- **Deterministic savings** — All arithmetic lives in `lambda/handler.py::simulate_savings_pure`. The LLM orchestrates tool calls and composes natural language but never performs math (SAV-03).
- **LLM-generated narratives** — Claude generates a one-sentence usage narrative and a call script snippet per recommendation card. Validated by length/content guardrails with deterministic fallbacks on failure.
- **Mock fallback** — When `VITE_API_URL` is unset, the UI reads from a local fixture so the full flow is demoable without a deployed backend.
- **Feature flags** — `?narrative=off` URL parameter collapses the UI to the v1.0 shape (no narrative text). Useful as a kill switch during live demos.

## Demo Personas

| ID | Name | Avg kWh/mo | Green Saving | Cheapest Saving |
|----|------|-----------|-------------|----------------|
| CUST-001 | Sarah Chen | 500 | ~$30/mo | ~$55/mo |
| CUST-002 | Marcus Webb | 282 | ~$17/mo | ~$31/mo |
| CUST-003 | Elena Vasquez | 233 | ~$14/mo | ~$26/mo |

All three are seeded into DynamoDB with 12 months of billing history (Apr 2025 – Mar 2026) on the Standard Rate plan.

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
│       ├── billing_records.py  # 3 personas × 12 months of billing data
│       └── tariff_plans.json   # Tariff catalog
├── agent/
│   ├── agent.py                # Strands SDK agent (deployed to AgentCore)
│   ├── Dockerfile              # ARM64 Python 3.12 container
│   ├── requirements.txt        # strands-agents, bedrock-agentcore, boto3
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
├── scripts/
│   ├── prewarm.py              # Pre-warm CLI (eliminates cold starts)
│   ├── demo-keepalive.sh       # 10-min ping loop (beats 15-min idle timeout)
│   ├── capture_samples.py      # Sample response capture utility
│   ├── hash_dist.sh            # Build artifact hash checker
│   └── hash_synth_assets.sh    # CDK synth asset hash checker
├── tests/                      # ~200 pytest tests
│   ├── test_cdk_synth.py               # CDK synthesis validation
│   ├── test_agent_*.py                 # Agent construction, tools, narrative
│   ├── test_backend_api_*.py           # API handler, synth, smoke
│   ├── test_simulate_savings.py        # Savings arithmetic
│   ├── test_get_billing_history.py     # Billing data retrieval
│   ├── test_narrative_validator.py     # Narrative guardrail validation
│   ├── test_fallbacks_pass_validator.py # Fallback string compliance
│   ├── test_schema.py                  # Response schema validation
│   ├── test_shape_tokens.py            # Shape token builder
│   └── test_seeder_smoke.py            # Data seeder
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
# Run all offline tests (~200 tests)
pytest

# Run only smoke tests (requires deployed AWS stack + credentials)
pytest -m smoke
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
| AI Agent | AWS Bedrock AgentCore, Strands SDK, Claude 3.7 Sonnet |
| Backend | AWS Lambda (Python 3.12), API Gateway HTTP v2 |
| Database | Amazon DynamoDB |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS 4, shadcn/ui |
| Testing | pytest (Python), Vitest (TypeScript) |
| Dependencies | pip-compile with hash verification |

## API

### GET /recommendations/{customer_id}

Returns Green and Cheapest tariff recommendations with projected savings.

**Path parameter:** `customer_id` — must match `^CUST-\d{3,6}$`

**Query parameters:**
- `prewarm=1` — triggers a warm-only invocation, returns HTTP 204 with no body

**Success response (200):**
```json
{
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
  }
}
```

**Error responses:** 400 (invalid ID), 404 (unknown customer), 504 (AgentCore timeout), 502 (AgentCore error)

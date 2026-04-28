# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Customer Tariff & Billing Optimisation Agent — an AWS Bedrock AgentCore demo for an Energy & Utilities provider. A call-centre agent-assist tool that takes a customer ID and returns two tariff recommendations (Green + Cheapest) with deterministic savings and LLM-generated narrative. Currently frozen at git tag `demo-v2.0`.

## Architecture

Four CDK stacks deploy in order to `us-east-1` (region is hardcoded — `app.py` overrides any local AWS profile default):

1. **CustomerTariff** (`infrastructure/foundation_stack.py`) — DynamoDB `tariff-billing` table, Tools Lambda (`lambda/handler.py`), seeder custom resource (3 personas × 12 months from `infrastructure/seed_data/billing_records.py`).
2. **CustomerTariffAgent** (`infrastructure/agentcore_stack.py`) — Bedrock AgentCore managed runtime running the Strands SDK agent (`agent/agent.py`) in an ARM64 Python 3.12 Docker container.
3. **CustomerTariffApi** (`infrastructure/backend_api_stack.py`) — API Gateway HTTP API v2 + API Lambda (`api_lambda/handler.py`) that proxies `GET /recommendations/{customer_id}` to the AgentCore runtime via a `live` alias. Pass `-c demo_pc=N` to enable Provisioned Concurrency for cold-start-free demos.
4. **CustomerTariffFrontend** (`infrastructure/frontend_stack.py`) — AWS Amplify Hosting for the pre-built `ui/dist` directory; fully independent of the other stacks.

Cross-stack wiring uses **SSM parameters**, not CloudFormation exports, so stacks can be redeployed independently.

### Request flow

```
React UI → API Gateway → API Lambda → bedrock-agentcore.invoke_agent_runtime → AgentCore container
                                                                                        │
                                                                                        ▼
                                                                                 simulate_savings tool
                                                                                        │
                                                                                        ▼
                                                                                 Tools Lambda → DynamoDB
```

### Critical invariants — break these and the demo dies

- **SAV-03: LLM never does arithmetic.** All savings math lives in `lambda/handler.py::simulate_savings_pure`. The agent system prompt at `agent/agent.py` forbids estimation, rounding, or recalculation; numbers from the tool are copied byte-for-byte into the response. Do not let the LLM "fix" or "round" tool output.
- **REC-03: both tracks always returned, never ranked.** `RecommendationResponse` requires both `green` and `cheapest`; the prompt forbids saying one is better.
- **D-15 narrative dual-gate.** `usage_narrative` (≤20 words) and `call_script` (≤22 words) must contain no digits, currency symbols, %, switch verbs, competitor names, or environmental superlatives. Pydantic `max_length` runs first; then the validators in `agent/narrative/validators.py` (`validate_usage_narrative`, `validate_call_script`) enforce the content rules. On `StructuredOutputException` or `structured_output is None`, `_narrative_fallback_salvage` runs per-field salvage from the lenient schema; remaining failures fall back to strings in `agent/narrative/fallbacks.py::FALLBACKS` (keyed by `customer_id`).
- **D-04 never-500 contract.** The agent invocation has a final `except Exception` that calls Tools Lambda directly and stitches in fallback narrative. Whatever you do, do not raise out of `invoke()`.
- **`_narrative_source` marker is internal.** Agent attaches it; `api_lambda/handler.py` strips it before returning to the client (`body.pop("_narrative_source", None)`). Tests at `tests/test_narrative_eval_live.py` use `boto3.invoke_agent_runtime` directly to read it.
- **API Lambda boto3 client uses `Config(read_timeout=25, connect_timeout=5)`.** The default 60s read timeout outlasts the 30s Lambda timeout, making the 504 branch unreachable. Do not remove the `Config(...)` override at `api_lambda/handler.py:39`.
- **`runtimeSessionId` generated INSIDE `handler()`, not at module scope.** Module-level caching causes session bleed between persona lookups (Pitfall 2 / SC-3).
- **`?prewarm=1` returns 204 on success AND failure.** That branch must never surface 5xx; broad `except` swallows everything by design (D-04).
- **`?narrative=off` URL flag is the live-demo kill switch.** Collapses the UI to v1.0 shape in both loading and success states. Mock fixtures in `ui/src/lib/mock/` mirror Phase 6 fallback strings byte-exact — keep them in sync.
- **Customer-not-found detection** is "no `green` or `cheapest` keys in body" (`api_lambda/handler.py:152`), because the agent's tool-failure fallback path returns `{"errorMessage": "..."}` without tracks.
- **Bi-mode imports in `agent/agent.py`.** Tries `from narrative.X import ...` first (container layout — Dockerfile COPYs `narrative/` to `/app/`), falls back to `from agent.narrative.X import ...` (repo layout for offline pytest). Don't "simplify" by removing one branch.

## Common commands

### Backend (Python 3.13 — system `python3` is 3.9.6 and cannot install pinned `iniconfig==2.3.0`)

```bash
/opt/homebrew/bin/python3.13 -m venv .venv
source .venv/bin/activate
pip install --require-hashes -r requirements.txt
pip install --require-hashes -r requirements-dev.txt
```

`--require-hashes` is the freeze reproducibility contract — any lockfile drift fails install. Edit `requirements.in` / `requirements-dev.in` and regenerate with `pip-compile`, never edit the `.txt` files by hand.

### Tests

```bash
pytest                       # ~200 offline tests (default — smoke marker excluded by absence)
pytest tests/test_simulate_savings.py             # single file
pytest tests/test_simulate_savings.py::test_name  # single test
pytest -m smoke              # live AWS smoke tests (requires deployed stack + AWS_PROFILE=cevo-dev25)
pytest -m "not smoke"        # explicit offline-only
```

Markers are declared in `pytest.ini`. The `smoke` marker also gates `tests/test_narrative_eval_live.py` (Phase 9 live eval harness).

### CDK

```bash
export AWS_PROFILE=cevo-dev25
export AWS_DEFAULT_REGION=us-east-1

cdk synth CustomerTariff
cdk diff CustomerTariffAgent
cdk deploy CustomerTariff CustomerTariffAgent CustomerTariffApi   # in dependency order
cdk deploy CustomerTariffApi -c demo_pc=1                          # enable Provisioned Concurrency
cdk deploy CustomerTariffFrontend                                  # independent — UI redeploy
```

The original 3 stacks have **deny-Update:\* stack policies + termination protection** applied (the `demo-v2.0` freeze ceremony). Updates require lifting the policy via `aws cloudformation set-stack-policy` first — see `infrastructure/stack-policies/` and the freeze section of `DEMO-RUNBOOK.md`. The Frontend stack is unfrozen and can be redeployed freely.

### UI (cd ui/)

```bash
npm ci                       # install (matches package-lock.json)
npm run dev                  # mock mode (VITE_API_URL unset)
VITE_API_URL=https://<api-id>.execute-api.us-east-1.amazonaws.com npm run dev   # live backend
npm run build                # production build (requires VITE_API_URL)
npm run build:mock           # mock-only build → dist-mock/ (emergency swap)
npm run test                 # vitest single run
npm run test:watch           # vitest watch
npm run lint                 # eslint
```

The `__GIT_SHA__` Vite define is injected at build time and rendered in `VersionIndicator.tsx` — never hardcode it.

### Demo tooling

```bash
BACKEND_API_URL=https://... python3 scripts/prewarm.py        # 2-pass warm + 3000ms median gate
BACKEND_API_URL=https://... bash scripts/demo-keepalive.sh    # 10-min ping loop, beats AgentCore 15-min idle
```

`prewarm.py` exit codes: `0` = under gate, `1` = gate fail / HTTP error, `2` = setup error.

## Code layout pointers

- **Tariff catalog** is duplicated: `lambda/tariff_plans.json` (bundled into Lambda asset) and `infrastructure/seed_data/tariff_plans.json`. `tests/conftest.py` treats `lambda/tariff_plans.json` as source of truth.
- **Persona fixtures** in `infrastructure/seed_data/billing_records.py` (`SARAH_CHEN_RECORDS`, `MARCUS_WEBB_RECORDS`, `ELENA_VASQUEZ_RECORDS`, `ALL_RECORDS`). The `mock_savings_response` / `mock_marcus_response` / `mock_elena_response` fixtures in `tests/conftest.py` lock byte-exact savings figures (Sarah $30/$55, Marcus $16.90/$30.98, Elena $14.00/$25.67).
- **Pydantic schema** for the agent response is `RecommendationResponse` in `agent/agent.py`. The lenient `_RecommendationResponseLenient` exists only for the salvage path — never use it on the happy path.
- **System prompt** = `_BASE_SYSTEM_PROMPT` (numeric integrity rules) + `NARRATIVE_PROMPT` (loaded from `agent/narrative/prompt.txt` via `prompt_loader.py`, contains exemplars + banned-terms).
- **Banned terms** centralised in `agent/narrative/banned_terms.py`; `_reject_forbidden` is reused by both the Pydantic validators and the salvage path.
- **`.planning/`** is the GSD workflow state — phase artefacts, retrospectives, decisions. Read-only context for understanding history; do not modify unless using the `gsd-*` commands.
- **`.kiro/specs/`** holds in-flight Kiro spec drafts (e.g. `amplify-frontend-hosting/`).

## Things to know before changing things

- **Region is hardcoded** in `app.py`. AgentCore Agent Registry is not available in `ap-southeast-2` (the local profile default), so do not "fix" the region pin.
- **Bedrock model literal** is `us.anthropic.claude-sonnet-4-6` at `agent/agent.py:309`. Phase 06.1 resolved a Sonnet 4.6 tool-use regression — be careful when changing model IDs; the byte-exact-savings invariant depends on the model honouring the system prompt's "no arithmetic" rule.
- **Frozen lockfiles** (`requirements.txt`, `requirements-dev.txt`, `ui/package-lock.json`) are part of the freeze contract. If you regenerate them, expect `--require-hashes` to fail until you also update the freeze evidence in `.planning/`.
- **Build output (`ui/dist/`, `cdk.out/`) is gitignored** — reproducibility is from sources, not artefacts. The `FrontendStack` deploys whatever is currently in `ui/dist`, so build before `cdk deploy CustomerTariffFrontend`.
- **AWS profile is `cevo-dev25`**, account `588738606436`. The shell-exported `AWS_PROFILE=cevo-25` is stale and wrong — override before AWS commands.

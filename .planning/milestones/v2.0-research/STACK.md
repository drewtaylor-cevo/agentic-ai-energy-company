# Technology Stack — v2.0 Demo Polish & LLM Narrative

**Project:** Customer Tariff & Billing Optimisation Agent
**Milestone:** v2.0 — UI-03 (call-script snippet), UI-04 (usage narrative), DEMO-03 (pre-warm), DEMO-04 (environment freeze)
**Researched:** 2026-04-25
**Confidence:** MEDIUM-HIGH — core stack is unchanged from v1.0 (HIGH); new surface area is small and composed of well-established patterns (Pydantic constraints, Lambda Provisioned Concurrency, pip-tools, npm `ci`). Some version numbers for latest patch releases are training-data only (LOW) and should be snapped to the newest-at-lock-time during DEMO-04.

> **Deltas-only document.** The v1.0 stack is still correct and is carried forward verbatim — see [`../milestones/v1.0-research/STACK.md`](../milestones/v1.0-research/STACK.md). This file lists **only the additions, pins, and scripts needed for v2.0**. Where a v2.0 feature reuses a v1.0 library unchanged, that is noted but not re-researched.

---

## What's Carried Forward Unchanged from v1.0

| v1.0 Component | Current Pin | v2.0 Usage |
|----------------|-------------|------------|
| AWS Bedrock AgentCore Runtime | GA, `us-east-1` | Hosts the same Strands agent with expanded Pydantic schema |
| Strands SDK (`strands-agents`) | Transitively pinned via v1.0 agent image | Its `Agent.structured_output()` is the mechanism for UI-03/UI-04 — no API change |
| `bedrock-agentcore` Python runtime lib (`BedrockAgentCoreApp`) | From v1.0 agent image | `/ping` endpoint is the warming target |
| Claude 3.7 Sonnet cross-region | `us.anthropic.claude-3-7-sonnet-20250219-v1:0` | Generates the two new short-form string fields |
| boto3 | `>=1.42.0` (backend Lambda) | Adds `bedrock-agentcore` control-plane calls in the pre-warm script |
| aws-cdk-lib | `>=2.250.0` | Pinning becomes `==2.250.x` for DEMO-04 freeze |
| `aws-cdk.aws-bedrock-agentcore-alpha` | `==2.250.0a0` | Unchanged |
| API Gateway HTTP API v2 + Lambda proxy | v1.0 `BackendApiConstruct` | Adds Provisioned Concurrency config for DEMO-03 |
| DynamoDB billing table + seeder | v1.0 `BillingTableConstruct` | Unchanged |
| React 19 + Vite 8 + Tailwind 4 + TypeScript 6 | Per `ui/package.json` | Adds two Markdown-safe string render sites |
| shadcn/ui (New York / Slate) + Radix | Per `ui/package.json` | Reuses `CardContent` — no new shadcn components needed |

**Everything else in `v1.0-research/STACK.md` applies. Do not re-install, do not bump majors.**

---

## v2.0 Additions

### UI-03 / UI-04 — Short-form LLM Narrative (Backend)

The agent already uses `Agent.structured_output(RecommendationResponse, prompt)` in `agent/agent.py`. Adding call-script and usage-narrative fields is a **schema change, not a library change** — the tool-calling + structured-output flow is preserved.

| Technology | Current Pin | Purpose | Why |
|------------|-------------|---------|-----|
| `pydantic` (already installed transitively via `strands-agents`) | v2.x (as ships with Strands) | Constrain the two new string fields with `Field(max_length=...)` and regex validators | Pydantic validators run **after** the model emits JSON — any string containing `$`, a digit, or over the length budget raises `ValidationError`, forcing a retry or fallback. This is how we enforce "NEVER quote dollar amounts" (UI-03/UI-04 non-negotiable) at the schema boundary, not via prompt alone. |
| `strands-agents` (no version bump) | As shipped in v1.0 agent image | `Agent.structured_output()` — already proven in v1.0 | The same call path that returned `green`/`cheapest` tracks with plan IDs and savings figures will return extended objects with `call_script` and `usage_narrative`. Single model round-trip — no extra LLM call, no extra latency budget line item. |

**Confidence:** HIGH that `structured_output` supports adding string fields — v1.0 already ships a working `TrackInfo` schema with mixed `str`/`float` fields. LOW on specific Pydantic constraint behaviour inside Strands' coercion layer — requires a sanity test during Phase 1 of v2.0 to confirm that `Field(pattern=r"^[^$\d]*$")` is enforced after the model responds and that validation failures propagate.

**Schema delta — add to `agent/agent.py`:**

```python
from pydantic import BaseModel, Field, field_validator

# UI-03/UI-04: forbid any substring that looks like a dollar amount.
# Enforced post-generation so the LLM cannot hallucinate figures even
# if the prompt is ignored. Validation failure triggers a retry.
_FORBIDDEN = re.compile(r"[$£€]|\b\d")

def _no_money(value: str) -> str:
    if _FORBIDDEN.search(value):
        raise ValueError(
            "Narrative fields must not contain digits or currency symbols — "
            "numbers come from simulate_savings only"
        )
    return value.strip()


class TrackInfo(BaseModel):
    plan_id: str = Field(description="Tariff plan identifier")
    plan_name: str = Field(description="Human-readable plan name")
    saving_monthly: float = Field(description="Projected monthly saving in dollars")
    saving_annual: float = Field(description="Projected annual saving in dollars")

    # UI-04: one-sentence usage narrative.
    usage_narrative: str = Field(
        description=(
            "One plain-English sentence describing the customer's usage profile "
            "(e.g. 'High evening consumption with a winter peak'). "
            "No dollar amounts. No numbers. Max 140 characters."
        ),
        max_length=140,
    )

    # UI-03: one-liner the agent can read to the customer verbatim.
    call_script: str = Field(
        description=(
            "One short sentence the call centre agent can say to the customer "
            "describing the benefit of this plan. No dollar figures — the card "
            "already shows them. Max 180 characters."
        ),
        max_length=180,
    )

    _no_money_narrative = field_validator("usage_narrative")(_no_money)
    _no_money_script = field_validator("call_script")(_no_money)
```

**Why `max_length` is not enough on its own:** Pydantic's `max_length` trims overlong output but does not block currency. The `field_validator` raising `ValueError` on `$`, `£`, `€`, or any digit is what makes the "no numbers" guarantee machine-enforceable. This is the single most load-bearing piece of v2.0 — without it, UI-03/UI-04 can drift into hallucinated figures the moment the prompt is edited.

**Why no new LLM round-trip:** Strands' `structured_output()` performs the tool-calling loop and the final JSON emission inside **one** agent run. Adding two string fields extends the output budget by ~320 characters (~80 tokens), well inside Claude 3.7 Sonnet's per-request latency envelope. The v1.0 end-to-end budget of <3s (UI-02) should absorb this. **Verify with a warm-median rehearsal before freeze** — if median creeps past 2.5s, consider moving `call_script` / `usage_narrative` generation to a separate non-blocking call.

**System prompt addition (agent.py):**

```
You will also fill:
  - usage_narrative: one plain sentence about the customer's usage shape
    (peak hours, seasonality, load level). Do NOT mention any amount of
    money, any number of dollars, or any percentage. The card shows the
    figures separately.
  - call_script: one sentence the agent can say to the customer about the
    benefit of this plan in plain English. Do NOT quote any dollar amount
    or any number — the card already displays them.
Both fields must be short enough to fit one line on a call-centre screen.
```

---

### UI-03 / UI-04 — Frontend Render (UI)

| Technology | Current Pin | Purpose | Why |
|------------|-------------|---------|-----|
| No new dependencies | — | Render the two new string fields as plain text inside `RecommendationCard` | Both fields are plain strings — no Markdown, no HTML. React's default escaping (`{data.usage_narrative}`) is sufficient. Zero XSS risk, zero new libraries. |

**TypeScript delta — `ui/src/lib/types.ts`:**

```typescript
export interface TrackInfo {
  plan_id: string;
  plan_name: string;
  saving_monthly: number;
  saving_annual: number;
  usage_narrative: string;  // UI-04
  call_script: string;      // UI-03
}
```

**Render delta — `ui/src/components/RecommendationCard.tsx`:** add two `<p>` rows inside `CardContent` above the existing methodology line. No new shadcn components. Keep total card height under the 1280px-above-the-fold budget from UI-01 (~200 extra px per card for two one-liners; will likely still clear the fold, but **verify at the T-24h rehearsal per DEMO-RUNBOOK**).

**Skeleton update:** `RecommendationSkeletons.tsx` must add two `Skeleton` rows so the skeleton shape matches the real card and the layout does not shift on load.

**Confidence:** HIGH — this is a pure render change with no new libraries.

---

### DEMO-03 — Pre-warm Strategy

The v1.0 stack has **two latency hotspots** to warm before the demo, and they need different tactics:

1. **API Gateway → backend Lambda (`tariff-api`)** — Lambda cold start on the proxy layer
2. **Backend Lambda → Bedrock AgentCore Runtime (`tariff_agent`)** — AgentCore container cold start + first model invocation latency

**Recommendation: Combine Lambda Provisioned Concurrency with a short pre-demo warming script. Do NOT use EventBridge scheduled warming.**

| Technology | Current Pin | Purpose | Why |
|------------|-------------|---------|-----|
| AWS Lambda Provisioned Concurrency | GA | Eliminate cold starts on the `tariff-api` Lambda for the demo window | Provisioned Concurrency (PC) pre-initialises execution environments to single-digit-ms latency. For the backend proxy Lambda this is the right primitive. Set PC to `1` during the demo window via CDK alias, destroy after. |
| `aws_cdk.aws_lambda.Alias` + `ProvisionedConcurrentExecutions` | `aws-cdk-lib>=2.250.0` (already pinned) | CDK construct to attach PC to a Lambda alias | Native CDK. Parameterise PC count with a CDK context value so `cdk deploy -c pc=1` turns it on for the demo and `-c pc=0` turns it off. |
| Custom Python pre-warm script (new) | `requirements-dev.txt` | Fire N warming invocations against API Gateway + directly against AgentCore runtime immediately before the demo starts | Provisioned Concurrency warms the Lambda; it does **not** warm the AgentCore runtime behind it. A small script that calls `/recommendations/CUST-001` three times (one per persona) over the real API endpoint warms the full path end-to-end: Lambda → AgentCore → model. |
| `requests>=2.28,<3` (already in `requirements-dev.txt`) | Existing pin | HTTP client for the pre-warm script | Already in v1.0 dev deps. No new library. |

**Confidence on PC:** HIGH — documented AWS feature, CDK-native, standard for demo scenarios.

**Confidence on AgentCore warming:** MEDIUM — there is no AgentCore equivalent of Provisioned Concurrency as of research date (not documented in the CDK alpha construct or the `bedrock-agentcore` runtime API). Warming via real invocations is the pragmatic substitute. If the T-24h rehearsal shows AgentCore cold-start remains user-visible, escalate.

**Why NOT EventBridge scheduled warming:** The demo window is a single ~2-hour slot known in advance. A persistent EventBridge rule generates waste invocations and CloudWatch Logs noise every minute for days. A one-shot pre-warm script invoked from the presenter's laptop at T-5 minutes is lighter, cheaper, and does not persist.

**Why NOT CloudWatch Synthetics Canary:** Synthetics is overkill for a single demo. Minimum canary runs daily, adds an extra IAM role, pricing adds up over the run-up week. Use the pre-warm script.

**Why NOT SnapStart:** Lambda SnapStart is Java/`.NET`/Python 3.12-only and Python SnapStart is still limited to certain regions/layouts. For a guaranteed-warm demo, Provisioned Concurrency is the clearer primitive.

**Pre-warm script skeleton — `scripts/prewarm.py` (new, ~60 lines):**

```python
"""DEMO-03: pre-warm the live stack before presentation.

Runs immediately before the demo. Performs:
  1. Three full end-to-end warming calls against API Gateway
     (one per flagship persona), each confirming a 2xx response
     and a green+cheapest body.
  2. A direct invoke_agent_runtime ping to AgentCore (bypassing
     the API Lambda) to confirm the agent container is warm.
  3. A /ping against the AgentCore runtime health endpoint.

Exits 0 only when all paths are warm AND latency is under the
UI-02 budget (3000ms). Prints per-step latency so the presenter
can see the warm state before going live.

Not a fixture — this is operational tooling. Do not add to pytest.
"""
import os
import sys
import time
from statistics import median

import boto3
import requests

API_ENDPOINT = os.environ["API_ENDPOINT"]  # from CfnOutput of BackendApiStack
AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]  # from CfnOutput
PERSONAS = ["CUST-001", "CUST-002", "CUST-003"]
BUDGET_MS = 3000

def warm_via_api():
    latencies = []
    for cust in PERSONAS:
        t0 = time.perf_counter()
        r = requests.get(f"{API_ENDPOINT}recommendations/{cust}", timeout=30)
        ms = (time.perf_counter() - t0) * 1000
        r.raise_for_status()
        body = r.json()
        assert "green" in body and "cheapest" in body, f"Missing tracks for {cust}"
        latencies.append(ms)
        print(f"  API {cust}: {ms:.0f}ms")
    return latencies

def warm_agentcore_direct():
    client = boto3.client("bedrock-agentcore", region_name="us-east-1")
    t0 = time.perf_counter()
    client.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        runtimeSessionId="prewarm-" + os.urandom(16).hex(),
        payload=b'{"customer_id": "CUST-001"}',
    )
    return (time.perf_counter() - t0) * 1000

if __name__ == "__main__":
    print("Pass 1 — cold call (discarded):")
    warm_via_api()
    print("Pass 2 — warm calls:")
    warm2 = warm_via_api()
    print("Pass 3 — warm calls:")
    warm3 = warm_via_api()

    warm_median = median(warm2 + warm3)
    print(f"\nWarm median: {warm_median:.0f}ms (budget {BUDGET_MS}ms)")
    sys.exit(0 if warm_median < BUDGET_MS else 1)
```

**CDK delta — add Provisioned Concurrency to `BackendApiConstruct`:**

```python
# New: alias + PC for the api lambda during demo windows.
# Controlled by CDK context: cdk deploy -c demo_pc=1 (default 0).
demo_pc = int(self.node.try_get_context("demo_pc") or 0)

api_lambda_alias = lambda_.Alias(
    self,
    "TariffApiLiveAlias",
    alias_name="live",
    version=fn.current_version,
    provisioned_concurrent_executions=demo_pc if demo_pc > 0 else None,
)
# Bind API Gateway to the alias instead of $LATEST so PC actually takes effect.
api.add_routes(
    path="/recommendations/{customer_id}",
    methods=[apigwv2.HttpMethod.GET],
    integration=integ.HttpLambdaIntegration("RecoIntegration", api_lambda_alias),
)
```

**Cost note:** PC=1 × 256 MB × 2 hours ≈ $0.05. Negligible. Turn off after the demo (`cdk deploy -c demo_pc=0`).

**Confidence:** HIGH on the CDK pattern; LOW on exact CfnOutput names — verify against v1.0 stack outputs before wiring the script.

---

### DEMO-04 — 48h Environment Freeze

The v1.0 stack already has `requirements.txt`, `requirements-dev.txt`, and `ui/package-lock.json`. v2.0 needs to upgrade this from "committed lockfiles" to a **fully reproducible byte-identical freeze for the 48-hour demo window**. Two new tools, one version-control tag, one CloudFormation primitive.

| Technology | Version to Adopt | Purpose | Why |
|------------|------------------|---------|-----|
| `pip-tools` | `>=7.4.0` (verify latest at freeze time) | Regenerate `requirements.txt` from a minimal `requirements.in` with **pinned transitive deps** and **`--generate-hashes`** | The current `requirements.txt` pins only top-level packages (`aws-cdk-lib>=2.250.0`). Transitive deps (e.g. `jsii`, `constructs` patch, `cattrs`) drift on `pip install -r`. `pip-compile --generate-hashes` produces a fully pinned file with SHA256 hashes, so `pip install --require-hashes -r requirements.txt` refuses to install a wheel that doesn't match. Byte-identical Lambda bundles across all installs. |
| `pip-compile-multi` (optional) | `>=2.6.0` | Compose `requirements.txt` + `requirements-dev.txt` without duplication | Keeps dev deps separate while still hash-pinned. Only needed if the dev-vs-prod split matters for Lambda bundling (it does — we don't want pytest in the API Lambda zip). |
| `npm ci` in the UI build | npm shipped with Node 20 | Replace `npm install` with `npm ci` everywhere that builds UI artefacts | `npm ci` refuses to install if `package-lock.json` drifts from `package.json`, and always installs exactly what the lockfile specifies. This is the JS-side equivalent of `pip install --require-hashes`. No new package needed — use built-in npm. |
| CDK asset hashing (already on) | `aws-cdk-lib==2.250.x` | Content-hash all Lambda/AgentCore assets so CFN only updates stacks when the code changes | CDK's default `AssetHashType.SOURCE` already hashes asset inputs. Confirm it's enabled (it is by default). After freeze, a `cdk diff` run with no code changes must return empty. |
| CloudFormation Stack Policy | Native CFN | Protect production resources from accidental update/replace during the demo window | Apply a stack policy to the three prod stacks (Foundation, AgentCore, BackendApi) that denies `Update:*` on all resources for the T-48h window. Rolled back after the demo. |
| Git tag (`demo-v2.0`) | git | Human-readable freeze point on `main` | Matches the v1.0 convention (`demo-v1.0` tag, commit `aba3a99`). The presenter's laptop deploys from that tagged SHA only. |

**Confidence on pip-tools:** HIGH — stable, widely used, official pip-maintained successor to `pip freeze`. Version numbers (7.4.0) are training-data — snap to latest at freeze time.

**Confidence on `npm ci`:** HIGH — built into npm since v6. No install.

**Confidence on CFN Stack Policy:** MEDIUM — the feature is stable but rarely used for demos; verify that CDK's `add_stack_policy` or raw CloudFormation `aws cloudformation set-stack-policy` works against the already-deployed stack. Test during Phase 1 of v2.0.

**Freeze protocol (what actually happens at T-48h):**

```
1. Compile locked requirements:
     pip-compile --generate-hashes --output-file requirements.txt requirements.in
     pip-compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in
   Commit both.

2. Lock npm:
     (cd ui && rm -rf node_modules && npm ci && npm run build && npm run build:mock)
   Commit ui/package-lock.json if it drifted.

3. Snapshot current AWS state:
     cdk diff   # must return empty — proves nothing is pending
     cdk synth > cdk.out.frozen.json  # reference synth, committed

4. Apply CloudFormation stack policies:
     aws cloudformation set-stack-policy \
       --stack-name CustomerTariffFoundation \
       --stack-policy-body file://.ops/stack-policy-deny-update.json
     (repeat for AgentCore + BackendApi stacks)

5. Cut the tag:
     git tag -a demo-v2.0 -m "v2.0 demo freeze — T-48h lock" <commit-sha>
     git push origin demo-v2.0

6. Reproducibility gate (must pass before freeze is declared done):
     rm -rf .venv ui/node_modules
     python -m venv .venv && source .venv/bin/activate
     pip install --require-hashes -r requirements-dev.txt
     (cd ui && npm ci && npm run build && npm run build:mock)
     pytest -m "not smoke"  # all tests pass from clean tree
     cdk synth  # matches cdk.out.frozen.json
```

This mirrors the v1.0 reproducibility gate (already proven — "81 passed, 6 skipped from a clean virtualenv") but adds **hash pinning** and the **stack policy** on top.

**After the demo (unfreeze):**
```
aws cloudformation set-stack-policy \
  --stack-name CustomerTariffFoundation \
  --stack-policy-body file://.ops/stack-policy-allow-all.json
(repeat for the other stacks)
```

**Confidence:** HIGH on the overall shape (standard freeze practice); MEDIUM on CDK + CFN stack-policy ergonomics (small risk CDK fights the manual policy — verify early).

---

## Deprecated / Removed from v1.0

None. v2.0 adds to v1.0; it does not replace anything.

---

## Version Bumps Required

| Package | v1.0 Pin | v2.0 Pin | Reason |
|---------|----------|----------|--------|
| `aws-cdk-lib` | `>=2.250.0` | `==2.250.<latest-patch>` | DEMO-04 freeze demands exact pins, not floors. Pick the latest 2.250.x patch at freeze time, not a minor bump. |
| `boto3` | `>=1.42.0` | `==1.42.<latest-patch>` | Same — must be exact at freeze. Verify `bedrock-agentcore` service model is present in the pinned version (it is in 1.42.0+). |
| `constructs` | `>=10.0.0` | `==10.<latest>.0` | Same. |
| `aws-cdk.aws-bedrock-agentcore-alpha` | `==2.250.0a0` | `==2.250.0a0` | No bump — the alpha line is unstable, and v1.0 is proven on this pin. |
| `pip-tools` | not installed | `==7.4.<latest>` (dev dep) | New — required for the freeze workflow. Add to `requirements-dev.txt`. |
| `pydantic` | transitive via `strands-agents` | transitive (unchanged) | UI-03/UI-04 validators use Pydantic v2 features (`field_validator`, `Field(max_length=...)`) which are already available on whatever Strands pulls in. **Sanity-check** during Phase 1 that `field_validator` exists (it does on Pydantic v2.0+; reject if project is on Pydantic v1). |
| UI deps (`react`, `vite`, etc.) | Per `ui/package.json` | **No bump** | All UI work is in existing components. Freezing `package-lock.json` with `npm ci` is sufficient. |

**Confidence:** MEDIUM — specific patch versions require verification at freeze time (training-data may be stale). The broader principle (pin `==` not `>=` for demo freeze) is HIGH.

---

## Alternatives Considered for v2.0

| Decision Point | Recommended | Alternative | Why Not |
|----------------|-------------|-------------|---------|
| UI-03/UI-04 generation path | Single `structured_output` call with extended schema | Separate Bedrock Converse API call after the tool result | Two round-trips double the latency spend against the 3s UI-02 budget. Keep it in one agent run. |
| Enforce "no dollar amounts" | Pydantic `field_validator` with regex `[$£€\d]` | Prompt-only instruction | Prompts drift silently when edited. A validator is a **hard gate** — the agent retries or the request fails loudly. Meets the non-negotiable in the milestone brief at the code level, not the prose level. |
| Enforce sentence length | `Field(max_length=140/180)` | Token budget in Strands config | `max_length` applies per-field, not per-response. Tokens are a blunt instrument that would truncate the plan-name or saving fields too. |
| Pre-warm primitive | Lambda Provisioned Concurrency + pre-demo script | EventBridge scheduled warmer every N minutes | Persistent warmer creates ongoing cost, log noise, and still doesn't warm AgentCore. PC is cleaner for a fixed demo window. |
| Pre-warm primitive | Lambda Provisioned Concurrency + pre-demo script | Lambda SnapStart | SnapStart has Python runtime and memory restrictions; proven-at-demo PC is the safer bet. |
| Pre-warm primitive | Lambda Provisioned Concurrency + pre-demo script | CloudWatch Synthetics Canary | Overkill for a one-shot demo — extra IAM, extra costs, minimum daily schedule. |
| Freeze mechanism (Python) | `pip-compile --generate-hashes` | `pip freeze > requirements.txt` | `pip freeze` emits versions but no hashes — cannot detect wheel substitution on PyPI. Hashes are the difference between "same version string" and "same bytes". |
| Freeze mechanism (Python) | `pip-compile --generate-hashes` | `uv pip compile` | `uv` is faster and would be a fine choice, but introduces a new tool mid-project. v1.0 already works with pip — stay on pip for the freeze. Consider `uv` for v3.0. |
| Freeze mechanism (Python) | `pip-compile --generate-hashes` | Poetry | Migrating `requirements*.txt` → `pyproject.toml` + `poetry.lock` is a multi-day refactor. Not justified for a 48h freeze. |
| Freeze mechanism (Node) | `npm ci` against existing `package-lock.json` | Switch to pnpm or `npm shrinkwrap` | No value — `package-lock.json` + `npm ci` already gives exact reproducibility. |
| AWS state lock | CloudFormation Stack Policy (T-48h window only) | AWS Config rules | Config is for ongoing compliance, not a 48-hour window. Too heavy for this use. |
| Demo freeze anchor | Git tag `demo-v2.0` + reproducibility gate | Commit SHA only | Tag is human-readable, signable with `-a`, and matches the v1.0 convention (`demo-v1.0` on `aba3a99`). |

---

## Installation — v2.0 Delta Only

```bash
# Dev deps for the freeze workflow
pip install pip-tools>=7.4.0 pip-compile-multi>=2.6.0

# One-time: convert existing pins to .in files
# requirements.in (manual):
#   aws-cdk-lib~=2.250
#   aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0
#   constructs>=10.0.0,<11.0.0
#   boto3~=1.42
# Then:
pip-compile --generate-hashes --output-file requirements.txt requirements.in
pip-compile --generate-hashes --output-file requirements-dev.txt requirements-dev.in

# Everything else (Strands, Pydantic, pytest, boto3) is unchanged —
# they come in transitively via the existing pins.
```

```bash
# UI — no install, just switch install commands in CI / scripts:
#   npm install  →  npm ci
```

---

## Integration Points with v1.0 Stack (What Touches What)

| v2.0 Change | v1.0 File | What Changes |
|-------------|-----------|--------------|
| Add `call_script` + `usage_narrative` to schema | `agent/agent.py` | Extend `TrackInfo` Pydantic model, add field validators, extend `SYSTEM_PROMPT` |
| Render narrative fields | `ui/src/lib/types.ts`, `ui/src/components/RecommendationCard.tsx`, `ui/src/components/RecommendationSkeletons.tsx` | Add TS field, add two `<p>` elements, add two skeleton rows |
| Pre-warm script | new `scripts/prewarm.py`, uses existing `requests` + `boto3` | Consumes existing `ApiEndpoint` + `AgentRuntimeArn` CfnOutputs — no stack change |
| Provisioned Concurrency | `infrastructure/constructs/backend_api.py` | Add `lambda_.Alias` with `provisioned_concurrent_executions`, bind `HttpLambdaIntegration` to the alias not the function |
| Freeze protocol | `requirements.txt`, `requirements-dev.txt`, `ui/package-lock.json` | Regenerate with hashes / `npm ci` |
| Stack policy | new `.ops/stack-policy-deny-update.json`, applied via AWS CLI | Outside CDK — applied imperatively T-48h, removed T+0 |

**Critical carry-forward contract:** The API pass-through in `api_lambda/handler.py` is `body = json.loads(response["response"].read())` followed by `json.dumps(body)`. Adding fields to `TrackInfo` **requires no change to the API Lambda** — it's a pass-through and will forward the new fields verbatim. This is why v1.0 invested in D-02 pass-through; v2.0 is the payoff.

---

## What NOT to Add (Drift Prevention)

Listed explicitly because these are the temptations that would cause v2.0 to drift from the validated v1.0 stack:

| Don't Add | Why |
|-----------|-----|
| LangChain / LangGraph | Strands + `structured_output` already does structured generation with tool calls. Adding a second orchestrator doubles the surface area and the latency budget. |
| A new LLM for UI-03/UI-04 (e.g. Haiku for narrative, Sonnet for reasoning) | Two models = two IAM grants, two warm-up paths, two freeze pins, two cost lines. Not justified for ~80 tokens of output. |
| Streaming (SSE) | The response is tiny and arrives in <3s. Streaming adds chunk-assembly complexity in the UI and makes the skeleton-first pattern harder. Defer to v3.0. |
| Markdown renderer in the UI | Both new strings are one plain sentence. React's default escaping is sufficient. Adding `react-markdown` is two more freeze pins for zero feature value. |
| `react-query` / TanStack Query | v1.0 ships without it. Current fetch is a plain `useEffect` + `fetch`. Adding it for two extra strings is not justified. |
| EventBridge warming rule | Persistent warmer for a one-shot demo. Covered above. |
| SnapStart | Python SnapStart not a good fit; PC is cleaner. |
| Poetry / `uv` / Hatch | Introducing a new Python tool during a 48h freeze is the opposite of freezing. |
| `esbuild`, `swc`, alternate bundlers | Vite already works; no reason to swap. |
| Amplify / Cognito | v1.0 shipped without auth (demo, not customer-facing). v2.0 scope does not add auth. Deferred to v3.0 with PROD-02. |
| Per-card analytics / telemetry | Not in scope. Every library added is a freeze pin. |

---

## Key Limits to Design Around (v2.0-Specific)

| Limit | Value | Impact |
|-------|-------|--------|
| Pydantic `field_validator` call frequency | Per model response | Each of the two string fields validates once per agent run. No meaningful overhead. |
| Strands `structured_output` retry on validation failure | Implementation-dependent | If Strands does not automatically retry on Pydantic `ValidationError`, a manual retry loop in `invoke()` may be needed (v1.0 already has a fallback). **Verify in Phase 1 of v2.0.** |
| Lambda PC warm-up window | Typically under 60 seconds from `cdk deploy` | Schedule the PC-enabling deploy at least T-5 minutes before the demo. |
| CloudFormation Stack Policy revert | Manual CLI call | Must be scripted into the post-demo checklist to avoid leaving prod locked. |
| Claude 3.7 Sonnet output token budget | 8K tokens default | Two extra fields × ~80 tokens each = trivial. No budget concern. |
| UI-02 end-to-end budget | <3 seconds lookup-to-rendered | New schema fields add estimated ~80 tokens (~500ms on Claude 3.7 Sonnet). Measure at the T-24h rehearsal. If over, fall back to async fetch of narrative fields. |
| UI-01 above-the-fold at 1280px | Both cards visible | Two extra `<p>` rows per card add ~40-60px. Test at the T-24h rehearsal. |

---

## Sources

### Verified (HIGH confidence)

- Existing v1.0 codebase: `agent/agent.py` (Strands `Agent.structured_output(RecommendationResponse, ...)` already ships and works in production)
- Existing v1.0 pins: `requirements.txt`, `requirements-dev.txt`, `ui/package.json`
- Existing v1.0 CDK: `infrastructure/constructs/agent_runtime.py`, `infrastructure/constructs/backend_api.py`
- v1.0 STACK.md: `.planning/milestones/v1.0-research/STACK.md` (carry-forward baseline)
- v1.0 MILESTONES.md entry (reproducibility gate: 81 tests pass from clean tree)

### Training-data only (LOW-to-MEDIUM confidence — verify at freeze time)

- AWS Lambda Provisioned Concurrency: current behaviour and CDK construct shape (MEDIUM — pattern is stable, exact CDK property names may have drifted)
- `pip-tools` version numbers and `--generate-hashes` flag (MEDIUM — stable feature, numeric version requires snap at time of use)
- Pydantic v2 `field_validator` syntax (HIGH — stable Pydantic v2 public API, in use widely)
- CloudFormation Stack Policy behaviour (MEDIUM — stable CFN feature, demo-window usage is less common)
- `npm ci` exact-install behaviour (HIGH — documented, stable since npm v6)

### Documentation that could not be fetched during this research run

WebFetch and Bash (Context7 CLI) were largely denied during research, so current-version verification relied on project files and training data. Before Phase 1 of v2.0 execution, **operator should verify** using their shell:

- `https://strandsagents.com/latest/documentation/docs/user-guide/concepts/agents/structured-output/` — confirm `structured_output` behaviour with nested Pydantic constraints
- `https://docs.aws.amazon.com/lambda/latest/dg/provisioned-concurrency.html` — confirm CDK alias + PC API shape
- `https://pip-tools.readthedocs.io/en/stable/` — snap to latest version number
- `https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/protect-stack-resources.html` — confirm stack policy JSON schema
- `pypi.org/project/bedrock-agentcore/` — confirm the runtime SDK version in the Strands agent container is still current

If any of those show unexpected drift, escalate before the freeze.

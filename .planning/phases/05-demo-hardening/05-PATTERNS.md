# Phase 5: Demo Hardening — Pattern Map

**Mapped:** 2026-04-24
**Files analyzed:** 4 new docs + 1 mock-fallback artifact (form TBD by planner) + 2 possible lightweight helper files = ~5–7 total
**Analogs found:** 5 strong in-repo matches + 2 modify-existing / ~7 total (0 greenfield; every artifact has a prior-phase precedent)

> **Phase shape note:** Phase 5 is operational, not net-new code. The work is (1) `cdk deploy` against the real AWS account, (2) record what was deployed, (3) rehearse, (4) lock. Almost every "new file" is a planning/docs artifact in `.planning/phases/05-demo-hardening/` — the prior phases' SUMMARY/VERIFICATION docs ARE the analogs. Only two production-code-adjacent artifacts exist: the mock-fallback distribution (shape is Claude's discretion per CONTEXT.md) and optionally a shell helper for deploy + capture. Planner must not invent source-code changes CONTEXT.md does not require.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/phases/05-demo-hardening/05-VERIFICATION.md` | doc (verification artifact) | — | `.planning/phases/04-agent-assist-ui/04-VERIFICATION.md` | exact (same phase-closing artifact shape) |
| `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md` | doc (presenter runbook) | — | none in repo — novel doc; structure seeded from D-17/D-19 checklist + prior SUMMARY.md "how-to-verify" blocks | greenfield (spec-driven by CONTEXT.md D-17/D-19) |
| `.planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` (filename is Claude's discretion — may live inline in VERIFICATION.md) | doc (captured ARNs + endpoint + CDK version) | — | `.planning/phases/02-agentcore-agent/02-03-SUMMARY.md` "Final deploy output" block + `infrastructure/*_stack.py` CfnOutput signatures | role-match (same "record what was deployed" purpose) |
| Mock-fallback dist — shape is Claude's discretion per CONTEXT.md (`ui-mock/` sibling dir / `npm run build:mock` script / committed `ui/dist-mock/`) | config/build artifact | build-time | `ui/` + `ui/.env.production` + `ui/package.json` scripts block | modify-existing (extends existing build pipeline with a second `VITE_API_URL`-unset build) |
| OPTIONAL: `scripts/deploy-capture.sh` or `Makefile` target — planner decides if worth the friction reduction | utility (shell helper) | command sequence | `.planning/phases/02-agentcore-agent/02-03-PLAN.md` Task 2 "Deploy" bash block | role-match (captures the same command sequence; does not replace human checkpoint) |
| Live smoke test runs (not a new file — existing `tests/test_backend_api_smoke.py` + `tests/test_agent_smoke.py` re-invoked against live endpoint) | test invocation | — | `tests/test_agent_smoke.py` already executed against live runtime in Phase 2 (02-03-SUMMARY.md records 13/13 pass) | exact (same invocation pattern with new env vars) |
| Git tag `demo-v1.0` + lockfile verification + `npm ci` + `cdk synth` on fresh checkout | deploy/lock action (no file) | — | none — lock action is procedural, recorded in VERIFICATION.md and RUNBOOK | procedural (no file created) |

---

## Pattern Assignments

### `.planning/phases/05-demo-hardening/05-VERIFICATION.md` — Phase closing verification artifact

**Analog:** `.planning/phases/04-agent-assist-ui/04-VERIFICATION.md`

**Frontmatter pattern** (04-VERIFICATION.md lines 1–33) — copy this shape verbatim, swap phase/score/human_verification blocks:

```yaml
---
phase: 05-demo-hardening
verified: <ISO-8601 UTC>
status: passed | partial | failed
score: "<rows-passed>/<rows-total> must-haves verified"
overrides_applied: 0
requirements_verified:
  - DEMO-01
  - DEMO-02
  - UI-02              # re-validated against live infra per CONTEXT.md canonical_refs
human_verification_completed:
  - test: "Live 3-persona rehearsal (cold + warm passes) + 2 error paths via UI"
    completed_by: "user"
    completed_at: "<date>"
    evidence: "Latency table + rehearsal results in this file + RUNBOOK cross-ref"
known_issues: []      # carry-forward WR-01/IN-01/IN-02 from 04-VERIFICATION.md ONLY if still relevant
---
```

**Top-level structure to mirror** (04-VERIFICATION.md — section headings in order):

| Section | Purpose in Phase 5 |
|---------|-------------------|
| `# Phase 5: Demo Hardening Verification Report` | Title |
| `**Phase Goal:** ...` + `**Verified:** ...` + `**Status:** ...` | Header |
| `## Goal Achievement` → `### ROADMAP Success Criteria (3)` | The 3 Phase 5 SCs — end-to-end personas, <3s latency, no-CRM |
| `### Observable Truths` | Each CONTEXT.md decision → a truth row with evidence |
| `### Required Artifacts` | RUNBOOK exists + deploy outputs recorded + git tag cut |
| `### Behavioral Spot-Checks` | `git tag`, `npm ci`, `cdk synth`, curl to live endpoint |
| `### Requirements Coverage` | DEMO-01, DEMO-02 (live), UI-02 (live) table |
| `### Human Verification` | Rehearsal narrative with cold + warm pass results |
| `### Gaps Summary` | Any items that must roll to v2 |

**ROADMAP Success Criteria table shape** (04-VERIFICATION.md lines 44–52):

```markdown
| # | Success Criterion | Status | Evidence |
|---|---|---|---|
| 1 | End-to-end persona sequence without failure | ✓ VERIFIED | 3 personas × 2 passes (cold + warm) recorded in Rehearsal section; curl smoke `pytest tests/test_backend_api_smoke.py` 4/4 pass against live endpoint |
| 2 | <3s latency warm median for all personas (UI-02) | ✓ VERIFIED | Latency table below — warm median for CUST-001/002/003 all < 3000ms (per D-09) |
| 3 | No-CRM validation | ✓ VERIFIED | Code-path audit section — grep output recorded, data source enumeration, architectural claim |
```

**Behavioral Spot-Checks table** (04-VERIFICATION.md lines 151–161 — use this exact column shape):

```markdown
| Behavior | Command | Result | Status |
|---|---|---|---|
| Git tag exists on main | `git tag --list demo-v1.0` | `demo-v1.0` | ✓ PASS |
| `npm ci` green from tagged commit | `cd ui && npm ci` | exit 0 | ✓ PASS |
| Fresh-venv pip install green | `python -m venv .v && .v/bin/pip install -r requirements.txt -r requirements-dev.txt` | exit 0 | ✓ PASS |
| `cdk synth` green | `cdk synth --all` | exit 0 (3 stacks) | ✓ PASS |
| `npm run build` green | `cd ui && npm run build` | exit 0 | ✓ PASS |
| Live API 200 on flagship persona | `curl $BACKEND_API_URL/recommendations/CUST-001` | 200 + `{green:..., cheapest:...}` with $30/$55 | ✓ PASS |
| Live API 400 on malformed | `curl $BACKEND_API_URL/recommendations/cust999` | 400 + `{"error":...}` | ✓ PASS |
| Live API 404 on unknown | `curl $BACKEND_API_URL/recommendations/CUST-999` | 404 + `{"error":...}` | ✓ PASS |
```

**Human Verification block** (04-VERIFICATION.md lines 182–197) — Phase 5 replaces "1280×800 smoke" with "rehearsal":

```markdown
### Human Verification

**Rehearsal (D-14/D-15):** presenter executed 2 passes (cold + warm) against the live endpoint.
Claude recorded results.

**Pass 1 — Cold (first invocation of day):**
  1. CUST-001 Sarah — Green `$30.00/mo · $360.00/yr · EcoFlex 100` + Cheapest `$55.00/mo · $660.00/yr · Value 12` ✓
  2. CUST-002 Marcus — `$16.90/mo` / `$30.98/mo` ✓
  3. CUST-003 Elena — `$14.00/mo` / `$25.67/mo` ✓
  4. Invalid format 400 — exact verbatim: "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits." (en-dash U+2013) ✓
  5. Unknown customer 404 — exact verbatim: "No customer found for CUST-999. Check the ID and try again." ✓

**Pass 2 — Warm (same personas, re-queried):** [repeat with warm numbers]
```

---

### Latency Table pattern (lives inside 05-VERIFICATION.md per D-10)

**Analog:** none — new table shape driven by D-09/D-10. Use Markdown table with `verdict` column mirroring prior VERIFICATION pass/fail visual.

**Exact shape to emit** (D-10 columns: persona, cold ms, warm median ms (n≥2), verdict):

```markdown
### Latency Evidence (D-10)

Measurement method: Chrome DevTools Network panel `fetch()` duration cross-checked with phone stopwatch (D-08). Warm run is median across n≥2 invocations (D-09). `<3000ms warm median` is the pass gate; cold is documented transparently but does NOT gate.

| Persona | Cold (ms) | Warm median (ms, n=<N>) | Verdict (warm vs 3000ms) |
|---------|-----------|-------------------------|--------------------------|
| CUST-001 | <cold> | <median of ≥2 warm samples> | ✓ PASS / ✗ FAIL |
| CUST-002 | <cold> | <median of ≥2 warm samples> | ✓ PASS / ✗ FAIL |
| CUST-003 | <cold> | <median of ≥2 warm samples> | ✓ PASS / ✗ FAIL |

**Gate:** if ANY warm median ≥ 3000ms → phase does not pass (D-09).
```

**Critical per `<specifics>` block:** median-of-n, not best-of-n. Do not cherry-pick fastest sample.

---

### No-CRM Audit pattern (lives inside 05-VERIFICATION.md per D-16)

**Analog:** `.planning/phases/04-agent-assist-ui/04-VERIFICATION.md` "Behavioral Spot-Checks" row that executes a grep (lines 156–158 — `grep -rn -E "TODO|FIXME..." ui/src/`). Phase 5 runs the same grep pattern against CRM-shaped identifiers.

**Shape to emit** (structure-based per D-16, NOT airplane-mode runtime test):

```markdown
### No-CRM Audit (D-16)

**Architectural claim:** the only inputs to savings are dummy data held in this AWS account. There is no CRM client, no HTTP egress to a customer system, no credentials for one.

**Evidence (grep — reviewer can re-run):**

\`\`\`bash
# CRM-shaped clients
grep -rn -E "salesforce|hubspot|zendesk|dynamics|pipedrive" agent/ api_lambda/ lambda/ infrastructure/
# Generic HTTP clients that could reach a CRM
grep -rn -E "requests\.(get|post)|urllib|httpx|aiohttp" agent/ api_lambda/ lambda/
# All expected to return ONLY boto3 DynamoDB / bedrock-agentcore calls
grep -rn "boto3\." agent/ api_lambda/ lambda/ | wc -l
\`\`\`

**Result:** [paste actual output — expected: first two grep commands return empty (beyond any boto3-internal imports), third returns the enumerated DynamoDB + AgentCore calls only].

**Data sources (explicit enumeration):**
- DynamoDB `BillingTable` — seeded from `infrastructure/seed_data/billing_records.py` at deploy time
- S3 `TariffCatalog` — seeded from `infrastructure/seed_data/tariff_plans.py` at deploy time
- AgentCore runtime — invokes Bedrock Claude + internal Lambda (`lambda/handler.py`); no external network calls

**Conclusion:** structurally no CRM code path exists. Claim is code-structural, not runtime-observational.
```

---

### `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md` — Presenter runbook

**Analog:** no prior in-repo runbook; structure is dictated by CONTEXT.md D-17 (sections), D-19 (T-24h/T-2h/T-0 checklist), D-05/D-07 (dual-build launch + swap). Borrow the instruction-block tone from `.planning/phases/02-agentcore-agent/02-03-PLAN.md` Task 2 `<how-to-verify>` (lines 227–287) for command-by-command clarity.

**Required sections (D-17 maps 1:1):**

| Section | Content | Reference |
|---------|---------|-----------|
| Pre-demo setup | AWS account + model access confirm, `git checkout demo-v1.0`, `npm ci`, `cdk deploy`, ARN capture | D-17 bullet 1 |
| T-24h / T-2h / T-0 timed checklist | D-19 enumerated items | D-19 |
| Presenter cheat sheet | 3 persona IDs, expected Green/Cheapest $ values, one-line narrative, equal-cards talking point | D-17 bullet 3 |
| Launch commands | `cd ui && npm run preview` (primary), `cd ../ui-mock && npm run preview` (swap) | D-06, D-07 |
| Fallback procedure | What to say while swapping | D-07 |
| Post-demo teardown | `cdk destroy CustomerTariffApi CustomerTariffAgent CustomerTariff` | D-18 |

**Command-block style** — copy from `02-03-PLAN.md` lines 236–267 (numbered bash blocks with narrative prose):

```markdown
**T-2h:**

1. Confirm `ui/dist/` is the live-API build:
   \`\`\`bash
   grep -l "execute-api" ui/dist/assets/*.js | head -1
   \`\`\`
   Expected: at least one match (the deployed API URL is baked into the bundle).

2. Confirm `ui-mock/dist/` exists and opens in browser:
   \`\`\`bash
   ls ui-mock/dist/index.html  # must exist
   cd ui-mock && npm run preview -- --port 4174   # test open in a second tab
   \`\`\`

3. Warm the stack:
   \`\`\`bash
   curl "$BACKEND_API_URL/recommendations/CUST-001" >/dev/null
   \`\`\`
```

**Cheat sheet persona values** — authoritative source per `<canonical_refs>` is `tests/conftest.py` + 04-05-SUMMARY.md Task 2 detail. Use these exact values:

| ID | Persona | Green saving | Cheapest saving | One-line narrative |
|----|---------|-------------|----------------|---------------------|
| CUST-001 | Sarah Chen — high usage | $30.00/mo · $360.00/yr · EcoFlex 100 | $55.00/mo · $660.00/yr · Value 12 | "Flagship retention save — biggest delta, best plan match" |
| CUST-002 | Marcus Webb — mid usage | $16.90/mo | $30.98/mo | "Typical customer — moderate delta, both tracks still viable" |
| CUST-003 | Elena Vasquez — low usage | $14.00/mo | $25.67/mo | "Low-usage — savings still meaningful, not a rounding error" |

---

### `.planning/phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` (or block inside VERIFICATION.md — Claude's discretion)

**Analog:** `.planning/phases/02-agentcore-agent/02-03-SUMMARY.md` "Final deploy output" block (lines 65–68):

```markdown
**Final deploy output:**
- Runtime ARN: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`
- Runtime status: READY
- All 13 smoke tests: PASSED (21.97s)
```

**CfnOutput values to capture** — authoritative list from `infrastructure/*_stack.py`:

| CfnOutput | Stack | Source |
|-----------|-------|--------|
| `BillingTableName`, `BillingTableArn` | CustomerTariff (FoundationStack) | `infrastructure/foundation_stack.py:24-25` |
| `ToolsLambdaName`, `ToolsLambdaArn` | CustomerTariff (FoundationStack) | `infrastructure/foundation_stack.py:26-27` |
| `AgentRuntimeArn`, `AgentRuntimeId` | CustomerTariffAgent (AgentCoreStack) | `infrastructure/agentcore_stack.py:28-29` |
| `ApiEndpoint` | CustomerTariffApi (BackendApiStack) | `infrastructure/backend_api_stack.py:30` |

**Exact shape to emit** (D-11 list: deployed ARNs + endpoint + CDK CLI version + git SHA):

```markdown
# Phase 5 — Deployed Environment Record

**Tagged at:** <ISO-8601 UTC>
**Git tag:** `demo-v1.0` → commit `<full SHA>`
**Region:** us-east-1 (hardcoded — `app.py` line 19)
**AWS Account:** <redacted or last-4>

## CfnOutputs (from `aws cloudformation describe-stacks --outputs`)

| Stack | Output | Value |
|-------|--------|-------|
| CustomerTariff | BillingTableName | <capture> |
| CustomerTariff | BillingTableArn | <capture> |
| CustomerTariff | ToolsLambdaName | <capture> |
| CustomerTariff | ToolsLambdaArn | <capture> |
| CustomerTariffAgent | AgentRuntimeArn | `arn:aws:bedrock-agentcore:us-east-1:<acct>:runtime/...` |
| CustomerTariffAgent | AgentRuntimeId | <capture> |
| CustomerTariffApi | ApiEndpoint | `https://<id>.execute-api.us-east-1.amazonaws.com` |

## Tool versions

| Tool | Version | Command used |
|------|---------|--------------|
| CDK CLI | <capture> | `npx aws-cdk@latest --version` at deploy time |
| Node | <capture> | `node --version` |
| Python | <capture> | `python --version` |
| Docker | <capture> | `docker --version` |

## Capture commands (reviewer can re-run from the tagged commit)

\`\`\`bash
aws cloudformation describe-stacks --stack-name CustomerTariff --region us-east-1 --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --stack-name CustomerTariffAgent --region us-east-1 --query 'Stacks[0].Outputs'
aws cloudformation describe-stacks --stack-name CustomerTariffApi --region us-east-1 --query 'Stacks[0].Outputs'
aws ssm get-parameter --name /customer-tariff/agent-runtime-arn --region us-east-1    # cross-stack wiring per Phase 3 D-07
\`\`\`
```

---

### Mock-fallback dist (Claude's discretion per CONTEXT.md — `ui-mock/` sibling / `build:mock` script / etc.)

**Analog:** `ui/` directory + `ui/.env.production` + `ui/package.json` scripts block.

**Existing build script** (`ui/package.json` lines 6–13):

```json
"scripts": {
  "dev": "vite",
  "build": "tsc -b && vite build",
  "lint": "eslint .",
  "preview": "vite preview",
  "test": "vitest run",
  "test:watch": "vitest"
}
```

**Existing env file** (`ui/.env.production`):

```
# Empty = mock mode (demo safety net).
# Set to deployed API URL for live-API demo build.
VITE_API_URL=
```

**Existing mock branch in hook** (`ui/src/hooks/useRecommendations.ts` lines 64–79):

```typescript
// 4. Branch on VITE_API_URL (D-02 build-time env, D-03 mock fallback).
//    Empty string OR undefined both map to mock mode. Any truthy origin
//    string triggers a real fetch.
const apiUrl = import.meta.env.VITE_API_URL;

if (!apiUrl) {
  const mockData = MOCK_RECOMMENDATIONS[customerId];
  if (!mockData) {
    setState({ status: 'error', httpStatus: 404, customerId });
    return;
  }
  setState({ status: 'success', data: mockData, customerId });
  return;
}
```

**Planner options** (CONTEXT.md `Claude's Discretion` — "ui-mock/ committed dir vs npm run build:mock script vs rebuild steps"):

| Option | Shape | Pros | Cons |
|--------|-------|------|------|
| A. Sibling `ui-mock/` directory | `cp -r ui ui-mock && cd ui-mock && (edit .env to unset) && npm run build` at T-2h per runbook | Swap is literally `cd ../ui-mock && npm run preview` — muscle-memory | Two copies of node_modules on disk |
| B. `npm run build:mock` script in `ui/package.json` | New script: `"build:mock": "VITE_API_URL= vite build --outDir dist-mock"` + `"preview:mock": "vite preview --outDir dist-mock"` | Single working tree | Presenter swaps by killing primary `preview` and running `npm run preview:mock` — slightly more typing |
| C. Documented rebuild steps at T-2h | Runbook instructs presenter to run a 1-liner rebuild when they need mock fallback | Zero code change | Violates <10s swap requirement (D-07) — REJECT |

**Recommendation for planner:** Option B is the lightest — one-line script addition to `ui/package.json`, uses existing Vite env semantics (`VITE_API_URL= vite build` produces a mock-mode bundle because the hook reads `import.meta.env.VITE_API_URL` which will be empty), single node_modules. Option A works but doubles disk. Either is acceptable per CONTEXT.md; the <10s swap gate is the real constraint.

**Verify the fallback bundle is actually mock-mode** (use this grep pattern the planner should bake into the runbook T-2h check):

```bash
# Primary (live) build must contain the API hostname:
grep -l "execute-api" ui/dist/assets/*.js | head -1   # expect: hit

# Fallback (mock) build must NOT contain it:
grep -l "execute-api" ui-mock/dist/assets/*.js 2>/dev/null   # expect: empty
```

---

### OPTIONAL: `scripts/deploy-capture.sh` (or Makefile target) — planner's call

**Analog:** `.planning/phases/02-agentcore-agent/02-03-PLAN.md` Task 2 `<how-to-verify>` bash blocks (lines 236–267). That plan captured the deploy sequence inline as a manual human-checkpoint. Phase 5 can either do the same (script-free) or wrap the sequence in a shell helper.

**Existing deploy command pattern** (02-03-PLAN.md lines 236–267) — what a script would automate:

```bash
# 1. Deploy stacks in dependency order (SSM wiring requires FoundationStack first)
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariff --require-approval never
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffAgent --require-approval never
AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest deploy CustomerTariffApi --require-approval never

# 2. Capture CfnOutputs
aws cloudformation describe-stacks --stack-name CustomerTariff --region us-east-1 --query 'Stacks[0].Outputs' > /tmp/phase5-foundation.json
aws cloudformation describe-stacks --stack-name CustomerTariffAgent --region us-east-1 --query 'Stacks[0].Outputs' > /tmp/phase5-agent.json
aws cloudformation describe-stacks --stack-name CustomerTariffApi --region us-east-1 --query 'Stacks[0].Outputs' > /tmp/phase5-api.json

# 3. Export the env vars the smoke tests need
export AGENT_RUNTIME_ARN=$(jq -r '.[] | select(.OutputKey=="AgentRuntimeArn") | .OutputValue' /tmp/phase5-agent.json)
export BACKEND_API_URL=$(jq -r '.[] | select(.OutputKey=="ApiEndpoint") | .OutputValue' /tmp/phase5-api.json)

# 4. Run live smoke
pytest tests/test_agent_smoke.py tests/test_backend_api_smoke.py -v -m smoke
```

**Planner guidance:** DEMO-04-style automation is deferred (CONTEXT.md `<deferred>`). A script is ACCEPTABLE only if it reduces friction on demo day — not as a lock mechanism. If included, it lives at `scripts/deploy-capture.sh` and is referenced from RUNBOOK.md Pre-demo setup, not invoked silently.

---

### Live smoke test invocation (no new file)

**Analog:** `tests/test_agent_smoke.py` + `tests/test_backend_api_smoke.py` (already committed).

**Live smoke pattern** (both files — skip guard on env var):

```python
# tests/test_backend_api_smoke.py lines 11–19
BACKEND_API_URL = os.environ.get("BACKEND_API_URL", "").rstrip("/")

pytestmark = [
    pytest.mark.smoke,
    pytest.mark.skipif(
        not BACKEND_API_URL,
        reason="BACKEND_API_URL not set — skip live backend API smoke tests",
    ),
]
```

```python
# tests/test_agent_smoke.py lines 23–31 — same pattern with AGENT_RUNTIME_ARN
```

**Phase 5 invocation** (the thing the planner must record Task-level in a plan):

```bash
# After cdk deploy + ARN capture:
export AGENT_RUNTIME_ARN=<from AgentCoreStack CfnOutput>
export BACKEND_API_URL=<from BackendApiStack CfnOutput>
export AWS_DEFAULT_REGION=us-east-1

pytest tests/test_agent_smoke.py tests/test_backend_api_smoke.py -v -m smoke
# Expected: 13 agent smoke + 7 backend api smoke (parametrized) = 20 tests green
```

**Pass condition (per D-03):** all 3 personas via curl AND all 3 personas via UI. Pytest smoke is the curl side; UI rehearsal (D-14/D-15) is the UI side. Both gates must be green.

---

### Git tag + lockfile verification (procedural, not a file)

**Analog:** none — first tag in the repo.

**Exact commands to include in VERIFICATION.md Behavioral Spot-Checks and RUNBOOK Pre-demo setup** (per D-11, D-12):

```bash
# Verify lockfiles are committed and clean
git status --porcelain ui/package-lock.json requirements.txt requirements-dev.txt
# Expected: empty (all committed)

# Cut the tag (on main, after all Phase 5 planning artifacts committed)
git tag -a demo-v1.0 -m "Demo-ready snapshot — 2026-04-24"
git push origin demo-v1.0

# Reproducibility check (in a fresh clone, or from a fresh worktree)
git checkout demo-v1.0
cd ui && npm ci && npm run build          # must exit 0
cd .. && python -m venv .v && source .v/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cdk synth --all                            # must exit 0 for all 3 stacks
pytest -m "not smoke" tests/ -x -q         # offline suite must be green
```

**Critical per `<specifics>`:** tag name MUST be unique — do not retag. If Phase 5 slips and a fix is needed, tag becomes `demo-v1.0.1`.

---

## Shared Patterns

### Pattern: Human checkpoint for deploy + rehearsal

**Source:** `.planning/phases/02-agentcore-agent/02-03-PLAN.md` Task 2 (`type="checkpoint:human-verify" gate="blocking"`, lines 207–304). Phase 1/2/3/4 all used this for any step that touches AWS or requires eyes-on-screen verification.

**Apply to:** Both the live-deploy plan AND the rehearsal plan in Phase 5. The user IS the presenter (D-15) — Claude cannot self-execute these steps.

**Shape to copy** (02-03-PLAN.md lines 207–304):

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <name>Deploy all 3 stacks and capture outputs</name>
  <what-built>...</what-built>
  <how-to-verify>
    [numbered bash blocks with commands]
    [expected results]
    [failure troubleshooting]
  </how-to-verify>
  <resume-signal>
    Type `approved` once:
    1. cdk deploy --all completed
    2. All CfnOutputs captured into 05-DEPLOY-OUTPUTS.md
    3. AGENT_RUNTIME_ARN + BACKEND_API_URL exported
    4. Live smoke passes
  </resume-signal>
  <acceptance_criteria>...</acceptance_criteria>
</task>
```

### Pattern: Record what was deployed in a SUMMARY/VERIFICATION doc

**Source:** `.planning/phases/02-agentcore-agent/02-03-SUMMARY.md` lines 56–68 — "Final deploy output" block with ARN + status + smoke result.

**Apply to:** `05-DEPLOY-OUTPUTS.md` (or the equivalent VERIFICATION.md section). Mirror the tone: short factual bullet list, not narrative prose.

### Pattern: `@pytest.mark.smoke` skip-guard for live tests

**Source:** `tests/test_agent_smoke.py:25-31` and `tests/test_backend_api_smoke.py:13-19`, registered in `pytest.ini:6-7`.

**Apply to:** Any new smoke-style invocation pattern in Phase 5. Do NOT create new smoke test files — reuse the existing two. Phase 5 only changes the env var values and re-runs.

### Pattern: Docs-committed convention (commit_docs: true)

**Source:** CONTEXT.md `<code_context>` — "all Phase 5 planning artifacts, VERIFICATION, RUNBOOK are committed."

**Apply to:** Every file Phase 5 creates ends up committed on `main`. The git tag `demo-v1.0` must be cut AFTER those commits land so the tagged tree contains the verification evidence.

### Pattern: Verbatim error copy locked in UI-SPEC

**Source:** `ui/src/lib/errors.ts:17-19` (400 copy), `:19` (404 copy with interpolation). Characters to preserve: en-dash U+2013 in 400 copy; middle dot U+00B7 in persona labels.

**Apply to:** Rehearsal Pass 1 + Pass 2 in VERIFICATION.md and the presenter cheat sheet in RUNBOOK.md. Error-copy drift during rehearsal is a bug per `<specifics>`, not a cosmetic issue.

---

## No Analog Found

All Phase 5 artifacts have a strong or role-match analog in prior phases. No greenfield artifacts requiring "see RESEARCH.md" fallback.

The one edge case — `DEMO-RUNBOOK.md` — has no prior analog as a whole document, but every section has a precedent:
- Pre-demo setup section → `02-03-PLAN.md` Task 2 `<how-to-verify>` structure
- Timed checklist → D-19 spec-driven
- Cheat sheet → `04-05-SUMMARY.md` Task 2 human-verify detail (the persona/$ values rows)
- Launch commands → `ui/package.json` scripts + D-06/D-07
- Teardown → `cdk destroy <stack>` inverse of deploy commands (02-03-PLAN.md)

Planner composes these into one new document; no new patterns needed.

---

## Metadata

**Analog search scope:**
- `.planning/phases/` (all 4 prior phases, all PLAN / SUMMARY / VERIFICATION / VALIDATION / PATTERNS / CONTEXT files)
- `tests/` (smoke test files + pytest.ini)
- `ui/` (package.json, vite.config.ts, .env files, hooks/useRecommendations.ts, lib/errors.ts, personas.ts)
- `infrastructure/` (stack files — CfnOutput lines only)
- `app.py` (stack names + region)

**Files opened:**
- `.planning/phases/05-demo-hardening/05-CONTEXT.md`
- `.planning/STATE.md`
- `.planning/phases/04-agent-assist-ui/04-VERIFICATION.md`
- `.planning/phases/04-agent-assist-ui/04-05-SUMMARY.md`
- `.planning/phases/04-agent-assist-ui/04-PATTERNS.md` (head only, for emit-style reference)
- `.planning/phases/03-backend-api/03-VALIDATION.md` (Phase 3 uses VALIDATION, not VERIFICATION — Phase 4 is the closer analog for Phase 5's VERIFICATION shape)
- `.planning/phases/03-backend-api/03-03-SUMMARY.md`
- `.planning/phases/02-agentcore-agent/02-03-PLAN.md`
- `.planning/phases/02-agentcore-agent/02-03-SUMMARY.md`
- `tests/test_agent_smoke.py`
- `tests/test_backend_api_smoke.py`
- `pytest.ini`
- `ui/package.json`
- `ui/vite.config.ts`
- `ui/.env.development`, `ui/.env.production`
- `ui/src/hooks/useRecommendations.ts`
- `ui/src/personas.ts`
- `ui/src/lib/errors.ts`
- `app.py`
- `infrastructure/*_stack.py` (CfnOutput line grep only)

**Pattern extraction date:** 2026-04-24

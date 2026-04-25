# Phase 5: Demo Hardening - Context

**Gathered:** 2026-04-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the full demo stack against real AWS, rehearse all 3 personas end-to-end against the live endpoint, measure and record latency, and lock the environment (git tag + lockfile verification + captured deployed ARNs) so the demo is reproducible from a single pinned commit. The deliverable is: (1) a live deployment that passes curl + UI smoke for all 3 personas, (2) a latency evidence table in 05-VERIFICATION.md, (3) a written no-CRM audit, (4) a tagged git commit `demo-v1.0` with all lockfiles verified, and (5) a DEMO-RUNBOOK.md with a presenter cheat sheet, T-24h/T-2h/T-0 checklist, emergency mock-fallback procedure, and post-demo teardown instructions.

New capabilities — DEMO-03 pre-warm script, DEMO-04 48-hour freeze, S3+CloudFront UI hosting, custom domain, automated latency harness, VPC egress blocks, alternate AWS accounts — remain deferred to v2 or outside scope.

</domain>

<decisions>
## Implementation Decisions

### Deploy Posture
- **D-01:** **Full live deploy of all 3 stacks** — `cdk deploy FoundationStack AgentCoreStack BackendApiStack` into the existing us-east-1 AWS account used in prior phases. Demo runs against the live endpoint. Flushes out cold-start, IAM, cross-stack SSM, and CORS behaviour against the real cloud before the demo.
- **D-02:** **us-east-1, same AWS account used in Phases 1–3** — `app.py` is already hardcoded to us-east-1; AgentCore Registry is available there. No fresh account, no profile switching. Reduces friction; matches every prior phase's deploy target.
- **D-03:** **Smoke gate: all 3 personas succeed via curl AND via the UI** — the Phase 3 live smoke script (`tests/test_api_smoke.py` or equivalent) must pass for all 3 personas, AND `npm run build && npm run preview` with `VITE_API_URL=<live endpoint>` must render the correct $30/$55 (and CUST-002, CUST-003) cards for all 3 personas. Both gates must be green before the phase closes.
- **D-04:** **No pre-warm** — DEMO-03 is explicitly v2-deferred in PROJECT.md. Phase 3 D-04 already accepts cold-start. First customer lookup on demo day may be 5–10 seconds; subsequent lookups benefit from warm Lambda and warm AgentCore runtime. The runbook may include an ad-hoc "invoke once ~2 min before demo" step, but no scheduled warmer or infrastructure change.

### Run-Mode on Demo Day
- **D-05:** **Live API primary with prebuilt mock dist as emergency swap** — presenter's laptop has two builds on disk: `ui/dist/` built with `VITE_API_URL=<live endpoint>` and a second prebuilt `ui-mock/dist/` built with `VITE_API_URL` unset (→ mock fallback per 04-CONTEXT.md D-03). Primary is live; mock is a <10s pivot if AWS is down mid-demo. Matches the "live system but safe" risk profile.
- **D-06:** **`npm run preview` from `ui/` is the launch mechanism** — continues Phase 4's D-05 (vite preview on presenter's laptop). One command, localhost, matches what was smoke-tested in Phase 4. No S3/CloudFront hosting (still deferred).
- **D-07:** **Documented fallback: swap to prebuilt mock dist** — runbook step: "Ctrl+C preview, `cd ../ui-mock && npm run preview`, reload browser." Mock dist MUST be prebuilt on demo day and committed-or-reproducible from a single build command, so the swap is muscle-memory, not improvisation.

### Latency Measurement
- **D-08:** **Chrome DevTools Network/Performance + phone stopwatch** — no new code, no Playwright, no performance.now() instrumentation. Presenter-grade evidence. Each persona lookup's fetch duration is read off DevTools Network; cards-rendered time cross-checked with a physical stopwatch. Records go directly into 05-VERIFICATION.md.
- **D-09:** **Pass threshold: warm-run median <3s for every persona; cold run captured separately** — Phase 3 D-04 accepts cold-start, and UI-02 is practically interpreted against the warm path (the path the second-onward customer lookups hit during a demo). Cold number is documented transparently, not hidden. If warm median exceeds 3s for any persona, the phase does NOT pass.
- **D-10:** **Latency evidence lives in 05-VERIFICATION.md as a small table** — columns: persona, cold ms, warm median ms (n≥2), verdict. One source of truth alongside rehearsal results and the no-CRM audit.

### Environment Lock
- **D-11:** **Lightweight lock: git tag + lockfile verification + captured deployed ARNs** — the lock is a git tag `demo-v1.0` cut from a commit on `main` where: (a) `package-lock.json` and `requirements.txt` / `requirements-dev.txt` are committed and deliver a green `npm ci` + fresh-venv `pip install -r`, (b) the deployed `AgentRuntimeArn`, API endpoint URL, and S3 data bucket name are captured in a Phase 5 artifact, (c) the CDK CLI version used to deploy is recorded. DEMO-04's full 48-hour freeze stays v2-deferred.
- **D-12:** **Trust existing lockfiles; verify by fresh install** — `npm ci` in `ui/` + fresh Python venv with `pip install -r requirements.txt requirements-dev.txt` + `cdk synth` + `npm run build` must all succeed from a clean checkout of the tag. Do NOT regenerate lockfiles — every prior phase has been green against them.
- **D-13:** **Git tag is the lock boundary; AWS resources are "don't touch"** — no CloudFormation drift checks, no isolated demo branch, no AWS account freeze. After tagging, policy is: no planner/agent actions against the deployed stacks until post-demo. This is a discipline commitment recorded in the runbook, not a technical enforcement mechanism.

### Rehearsal Scope
- **D-14:** **Golden path + 2 error paths, 2 full passes (cold + warm), human-executed** — every Phase 5 rehearsal pass consists of:
  - 3 persona lookups (CUST-001 / CUST-002 / CUST-003), each rendering correct Green + Cheapest cards against the live endpoint
  - 1 invalid-format case (e.g. `cust999` → 400, error copy "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits.")
  - 1 unknown-customer case (e.g. `CUST-999` → 404, error copy "No customer found for CUST-999. Check the ID and try again.")
  Two passes required: one cold (first invocation of the day), one warm. Pass = golden results + two error alerts with verbatim Phase 4 copy.
- **D-15:** **Presenter (user) executes the rehearsal; Claude records results** — mirrors the Phase 4 human checkpoint pattern. The user is the presenter and needs to rehearse under realistic conditions. Claude captures what the user observed: latency numbers, card values, error copy exact-match, any surprises. Results written into 05-VERIFICATION.md.

### No-CRM Validation
- **D-16:** **Code-path audit + architectural claim recorded in 05-VERIFICATION.md** — there is structurally no CRM code in the project. Phase 5 produces a short written audit in the verification artifact: (a) grep results for any HTTP/CRM client in `agent/`, `api_lambda/`, `lambda/` (expected empty beyond boto3 calls to DynamoDB/AgentCore), (b) explicit enumeration of data sources (DynamoDB BillingTable seeded from `infrastructure/seed_data/`, S3 for tariff catalog), (c) architectural claim that the only inputs to the savings calculation are dummy data held in the demo account. No airplane-mode test, no VPC egress block — the claim is code-structural, not runtime-observational.

### Deliverables
- **D-17:** **DEMO-RUNBOOK.md** at `.planning/phases/05-demo-hardening/DEMO-RUNBOOK.md` with:
  - Pre-demo setup (AWS account + model access confirmation, `git checkout demo-v1.0`, `npm ci`, `cdk deploy`, captured ARNs reference)
  - T-24h / T-2h / T-0 timed checklist
  - Presenter cheat sheet: three persona IDs with expected Green/Cheapest $ values, one-line narrative per persona, equal-cards talking point (neither track ranked)
  - Launch commands: `npm run preview` (primary), `cd ../ui-mock && npm run preview` (emergency swap)
  - Fallback procedure (what to say while swapping)
  - Post-demo teardown: `cdk destroy` for all 3 stacks
- **D-18:** **Teardown is documented, not executed** — `cdk destroy` instructions live in the runbook for post-demo cleanup. Phase 5 does NOT tear down the stack it just deployed.
- **D-19:** **T-24h / T-2h / T-0 timed checklist format** — lightweight sequencing:
  - T-24h: tag exists, ARNs captured, latency table green, runbook reviewed
  - T-2h: laptop has latest dist built, mock fallback dist prebuilt, browser tab cached with localhost URL, AWS console tab open
  - T-0: invoke once to warm, open UI, begin demo

### Claude's Discretion
- Exact filename and layout of the captured-ARNs artifact (e.g. `05-DEPLOY-OUTPUTS.md` vs a block inside VERIFICATION.md) — planner picks.
- Shape of the code-path audit (inline grep transcript vs summarised finding) in 05-VERIFICATION.md — planner picks, but must include the grep commands so a reviewer can re-run them.
- Whether the rehearsal script is plain Markdown steps or a numbered table inside the runbook — planner picks.
- Exact wording/tone of presenter cheat sheet narrative — planner drafts, user confirms during runbook review.
- Whether the ad-hoc warm-up step (D-04 nuance) is T-2h or T-0-minus-2-min — planner picks based on runbook flow.
- Whether mock fallback dist is a committed `ui-mock/dist/` artifact, a `npm run build:mock` script, or documented rebuild steps — planner picks, but the presenter must be able to swap in <10 seconds.
- Logging/CloudWatch retention settings during the demo deploy — carry forward Phases 1–3 conventions.
- Phase 5 plan count and decomposition — planner decides based on work discovered (likely ~3 plans: deploy+smoke, rehearsal+latency, lock+runbook).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & Goals
- `.planning/ROADMAP.md` §Phase 5 — the 3 Success Criteria (end-to-end persona sequence without failure, <3s latency for all personas, no-CRM validation) are the literal pass gate.
- `.planning/REQUIREMENTS.md` — DEMO-01 (self-contained demo on dummy data) is the locked requirement this phase validates against the integrated whole. DEMO-02 engineered savings ($30/$55 flagship) are what the live deploy must return. UI-02 <3s is re-validated against live infra.
- `.planning/PROJECT.md` — Out of Scope section locks: no OAuth, no live CRM, no auto-switching. DEMO-03 and DEMO-04 listed in Active "v2 candidates" block — Phase 5 must NOT promote these.

### Phase 3 API contract & deploy details (the live thing we're standing up)
- `.planning/phases/03-backend-api/03-CONTEXT.md` — D-01 synchronous JSON, D-02 pass-through shape, D-03 30s Lambda + 504 on agent timeout, D-07 SSM cross-stack ARN wiring, D-10 `GET /recommendations/{customer_id}`, D-11 fresh uuid4 session per invocation, D-12 full HTTP error taxonomy (400/404/500/502/504). Phase 5's live deploy must honour all of these.
- `.planning/phases/03-backend-api/03-03-PLAN.md` — records that live `cdk deploy` was deferred to Phase 5. Read the smoke-test structure already written there (even if not yet executed).
- `api_lambda/handler.py` — error body shape `{"error": "<friendly message>"}`, customer_id regex `^CUST-\d{3,6}$`, 25s botocore timeout. UI copy is keyed off status codes this emits.
- `agent/agent.py::RecommendationResponse` — authoritative response schema the live API returns verbatim.

### Phase 4 UI contract & mock fallback (the thing we're pointing at live)
- `.planning/phases/04-agent-assist-ui/04-CONTEXT.md` — D-01 native fetch hook, D-02 `VITE_API_URL` build-time env, D-03 mock fallback when `VITE_API_URL` unset, D-05 `vite preview` run target, D-07 production-build verification requirement, D-12 form + Enter submission, D-10 input normalization.
- `.planning/phases/04-agent-assist-ui/04-VERIFICATION.md` — 28/28 observable truths verified; 1280×800 human smoke-tested in mock mode. Phase 5 re-runs the persona sequence against the LIVE endpoint, not mock.
- `.planning/phases/04-agent-assist-ui/04-UI-SPEC.md` — locks all copy used in error rehearsal (D-14): "That doesn't look like a customer ID. Format is CUST followed by 3–6 digits." (400), "No customer found for CUST-{id}. Check the ID and try again." (404).
- `ui/src/lib/errors.ts` — error copy lookup used by `ErrorAlert` component, called during rehearsal error paths.
- `ui/src/personas.ts` — the 3 persona constants; values here must match seed data exactly.
- `ui/src/lib/mock/recommendations.ts` — mock fixture that the emergency-swap dist relies on. Values MUST match the Phase 1 seed and the live API for a credible fallback.

### Phase 1 Data & Tools
- `infrastructure/seed_data/` — the billing profiles Phase 1 loads into DynamoDB. The live deploy runs against this exact data. No drift between this and the mock fixture.
- `lambda/handler.py` — Phase 1 `simulate_savings_pure` and `get_billing_history`. The deterministic savings that must surface correctly during live rehearsal.

### CDK Infrastructure (everything the live deploy touches)
- `app.py` — us-east-1 hardcoded; all 3 stacks registered.
- `infrastructure/foundation_stack.py` — BillingTable, ToolsLambda, Seeder. First stack to deploy.
- `infrastructure/agentcore_stack.py` — AgentCore Runtime construct; writes AgentRuntimeArn to SSM (per Phase 3 amendment).
- `infrastructure/backend_api_stack.py` — API Lambda + HTTP API v2 + CORS. Reads AgentRuntimeArn from SSM.
- `infrastructure/constructs/` — shared CDK constructs referenced by all stacks.
- `cdk.json` — CDK toolkit config; record which CDK CLI version is used to deploy (D-11).

### Test Harnesses (reused for live smoke)
- `tests/conftest.py` — persona fixtures with expected $30/$55 flagship values used in Phase 3 live smoke.
- `tests/test_agent_smoke.py` + `tests/test_api_smoke.py` (if present) — `@pytest.mark.smoke` pattern; Phase 5 live smoke reuses these against the real deployed endpoint.
- `pytest.ini` — smoke marker registration.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **All 3 CDK stacks already synthesize and have been offline-tested** (Phase 1/2/3 verification). Phase 5's deploy work is `cdk deploy`, capturing outputs, and running smoke tests — not writing new CDK.
- **Phase 2 `tests/test_agent_smoke.py` and Phase 3 smoke pattern** — reused for Phase 5 live API smoke (per D-03). Same `@pytest.mark.smoke` gating, same persona fixtures.
- **Phase 4 `ui/dist/` build pipeline + mock fallback hook (`useRecommendations`)** — Phase 5 just parameterises it with `VITE_API_URL=<live endpoint>` for the primary dist, and builds a second dist with the env unset for the emergency mock swap (D-05/D-07).
- **Phase 4 error copy in `ui/src/lib/errors.ts` + `ErrorAlert` component** — drives the rehearsal error-path verbatim-copy check (D-14).

### Established Patterns
- **Stack-per-phase deploy order:** FoundationStack → AgentCoreStack → BackendApiStack. `cdk deploy --all` in this order, or individual `cdk deploy <stack>` invocations.
- **SSM cross-stack wiring** (Phase 2/3): each stack writes ARNs to SSM; downstream stacks read via `ssm.StringParameter.value_for_string_parameter`. Phase 5 captures these ARN values post-deploy via `aws cloudformation describe-stacks --outputs` or `aws ssm get-parameter` — not by re-exporting them.
- **us-east-1 hardcoded** — do not parameterise this in Phase 5; AgentCore Registry isn't available in ap-southeast-2.
- **Human checkpoint pattern** (Phase 1/2/3/4) — deploys and rehearsals have always required explicit user sign-off. Phase 5 continues this for the rehearsal (D-15).
- **Docs-committed convention** (config.json `commit_docs: true`) — all Phase 5 planning artifacts, VERIFICATION, RUNBOOK are committed.

### Integration Points
- **Upstream prerequisite (Day 1, BLOCKING):** AWS account must have Claude model access enabled (STATE.md Blockers lists this as an open item from project init). Phase 5 deploy cannot start if this isn't already confirmed.
- **Upstream prerequisite:** AWS credentials + CDK bootstrap in target account + region must already be in place from prior phases. If any prior phase was done on a different AWS profile, Phase 5 must normalise this before deploy.
- **Upstream prerequisite:** The Phase 2 SSM amendment (`AgentRuntimeArn` written to SSM) from Phase 3 D-07 must actually be present in the current code — verify before deploy. This was an explicit Phase 3 work item.
- **Downstream:** none — Phase 5 is the last phase of v1.0. Milestone closes after this.
- **Out of band:** the user (presenter) owns the demo-day execution. Phase 5 prepares them; it does not execute the demo itself.

</code_context>

<specifics>
## Specific Ideas

- **"Live deploy" does not mean "deploy and forget."** D-11's lock is a commitment that the tagged commit reproduces the deployed stacks. If an ARN changes, the tag must be refreshed — or the runbook must record that the live ARN at demo time differs from the tagged-commit ARN.
- **Emergency swap has to be muscle-memory, not improvisation.** D-07's fallback depends on the presenter having a prebuilt mock dist on disk BEFORE the demo starts. The runbook's T-2h line must include "confirm ui-mock/dist/ exists and opens in browser."
- **Warm-run median, not best-of-three.** D-09 says median across n≥2 warm invocations — do not cherry-pick the fastest. A persona whose best is 2.8s but whose warm median is 3.4s fails the gate.
- **Error copy is verbatim.** D-14 rehearses the exact strings locked in 04-UI-SPEC.md. Any drift between UI and spec during rehearsal is a bug, not a cosmetic issue — the error copy is part of how the call-centre agent speaks to customers.
- **The no-CRM claim is structural, not empirical.** D-16's audit is "there is no CRM code to hit"; we are not pulling the network cable to prove it. A reviewer who wants stronger evidence can re-run the grep commands themselves from the tagged commit.
- **Stable card order during rehearsal.** UI-SPEC and Phase 4 lock Green-first, Cheapest-second. Rehearsal is also a chance to confirm this under real data.
- **Flagship persona (CUST-001) $30/$55 is the demo's emotional beat.** If live deploy returns different numbers for this persona, something is wrong with the seed or the savings function — not "demo hardening." Diagnose and re-verify Phase 1/2 before declaring Phase 5 done.
- **The tag name (`demo-v1.0`) is a signal.** v1.0 matches the milestone. If this work slips and becomes v1.0.1, the tag should reflect that. Do not reuse a tag.

</specifics>

<deferred>
## Deferred Ideas

- **DEMO-03 pre-warm script** — v2-deferred in PROJECT.md; Phase 5 explicitly declines to promote. Ad-hoc manual warm-up in the runbook is the compromise.
- **DEMO-04 48-hour freeze with AWS account snapshot** — v2-deferred in PROJECT.md; Phase 5 uses the lightweight git-tag lock instead.
- **S3 + CloudFront UI hosting** — already considered and deferred in Phase 4 D-05. Not revisited for Phase 5; if a shareable URL is required post-demo, it becomes a new phase.
- **Playwright / automated latency harness** — rejected (D-08). DevTools + stopwatch is the evidence layer. If regression automation is wanted post-v1, it's a separate ask.
- **performance.now() instrumentation in `useRecommendations`** — considered under D-08 and rejected to avoid polluting the hook with phase-5-only debug code.
- **Airplane-mode / VPC egress block for no-CRM validation** — considered under D-16 and rejected. Code-path audit is sufficient because there is no CRM code to disable.
- **Full CloudFormation drift check on tagged state** — considered under D-13 and rejected. Discipline + git tag is the lock, not CFN.
- **Isolated `demo-v1.0` branch separate from `main`** — considered under D-13. Deferred unless post-tag commits to `main` start threatening the demo reproducibility.
- **Structured JSON latency artifact** — considered under D-10 and rejected. Markdown table in VERIFICATION.md is the target.
- **Custom domain / branded URL at demo time** — defer. `localhost` + `vite preview` on the presenter's laptop is the demo surface.
- **Post-demo teardown automation** — `cdk destroy` is documented in the runbook (D-18) but not wrapped in a script. Can be scripted later if demos become repeated.
- **Freezing the presenter's laptop OS state** — not in scope. Presenter is responsible for not updating their OS/browser within 24h of demo; the runbook can suggest it.

</deferred>

---

*Phase: 05-demo-hardening*
*Context gathered: 2026-04-24*

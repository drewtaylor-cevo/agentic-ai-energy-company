---
phase: 06-agent-narrative-guardrail
plan: 03
subsystem: agent
tags: [docker, cdk, deploy, smoke, narrative, bedrock-agentcore, bedrock-legacy, claude-sonnet-4-6, strands, tool-use-regression, demo-02-at-risk]

# Dependency graph
requires:
  - phase: 06-01 (narrative foundations)
    provides: agent/narrative package (banned_terms, fallbacks, prompt, prompt_loader, shape, validators)
  - phase: 06-02 (agent narrative integration)
    provides: extended TrackInfo + invoke() retry-once-then-per-field-fallback + _narrative_source marker
  - phase: v1.0 (shipped)
    provides: AgentCoreStack (stack name `CustomerTariffAgent`) + AgentRuntimeConstruct + DEMO-02 $30/$55 contract
provides:
  - Fixed agent/Dockerfile (Pitfall 1 - COPY narrative/ ./narrative/) — deployed and serving in us-east-1
  - Bi-mode narrative imports in agent/agent.py and agent/narrative/validators.py (container layout + repo layout both work) — new container-layout bug found and fixed during live deploy
  - Extended tests/test_agent_smoke.py — test_narrative_fields_present_and_valid + test_narrative_source_marker_present (6 new parametrised smoke tests on top of 13 v1.0 tests)
  - scripts/capture_samples.py — one-shot live-dump helper, committed as an executable script
  - Deployed CustomerTariffAgent stack in us-east-1 serving the extended schema — same ARN (`arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`), new image hash (2 successive image rolls for successive bug fixes)
  - Model upgraded from Claude 3.7 Sonnet (Legacy+blocked) → Claude Sonnet 4.6 (ACTIVE inference profile) — deviation from Plan 06-03 and RESEARCH, forced by Bedrock Legacy 30-day-unused rule
  - System prompt tightened with TOOL OUTPUT IS THE SOURCE OF TRUTH block + Rule 7 — attempt to re-anchor 4.6 on tool output (did NOT resolve the underlying tool-use regression; see Issues Encountered)
  - Live smoke suite green 18/19 against the deployed runtime (only test_sarah_flagship_values fails; see Issues Encountered for root cause)
  - (NOT PROVIDED) 06-SAMPLES.md — NOT populated in this run because test_sarah_flagship_values failure indicates the runtime is not honouring tool output; shipping all-fabricated samples as design-review artefacts would be misleading
  - (NOT PROVIDED) Phase 6 success criterion 5 "deployed image serves the extended schema while v1.0 $30/$55 deltas remain unchanged" — the extended-schema half PASSES on the deployed runtime, but the $30/$55 preservation half FAILS on Claude Sonnet 4.6 (Claude 3.7 worked with these numbers but is no longer accessible)
affects:
  - 06 (phase success criterion 5 partially unmet — tool-use regression is the blocker)
  - 07 (API pass-through cannot be fully validated until DEMO-02 numbers are restored on the deployed runtime)
  - 09 (eval harness needs a working tool-call path — same blocker)
  - 10 (freeze / rollback drill — should not freeze on a runtime that fabricates savings numbers)

# Tech tracking
tech-stack:
  added: []   # no new runtime deps; model_id config change only
  removed: []
  patterns:
    - "Dockerfile file-copy: explicit `COPY <subdir>/ ./<subdir>/` rather than a glob — matches the one-file-per-line convention the existing Dockerfile set at v1.0."
    - "Bi-mode Python imports for runtime-vs-repo layout divergence: `try: from X.Y import Z; except ImportError: from package.X.Y import Z`. Use when the same file is imported both as a module inside a flat WORKDIR (container) and as a subpackage of a namespace package (repo)."
    - "Pre-deploy local gate: `docker build --platform linux/arm64` + `docker run --rm --entrypoint ls <image> /app/<package>/` — validates Dockerfile COPY before any `cdk deploy`. This plan extended the gate to also run the target Python import inside the container (`docker run --entrypoint python <image> -c 'from X import Y'`), which catches module-layout bugs that `ls` does not."
    - "Bedrock Legacy model-access rule (operational): AWS Bedrock blocks ConverseStream on a Legacy-tagged model if the caller has not used that model in the last 30 days. Symptom: `ResourceNotFoundException: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 30 days`. Detection: CloudWatch runtime logs; not visible in the API call error because AgentCore wraps the upstream Bedrock error as a generic 502 RuntimeClientError. Workaround: use an ACTIVE inference profile (e.g. `us.anthropic.claude-sonnet-4-6`), or reactivate access via the Bedrock console."

key-files:
  created:
    - scripts/capture_samples.py
    - .planning/phases/06-agent-narrative-guardrail/06-03-SUMMARY.md
  modified:
    - agent/Dockerfile                     # +1 line (COPY narrative/ ./narrative/)
    - tests/test_agent_smoke.py            # +53 lines (narrative tests + source marker tests)
    - agent/agent.py                       # bi-mode imports (+24 lines), model_id swap to claude-sonnet-4-6, tightened system prompt (+12 lines)
    - agent/narrative/validators.py        # bi-mode import for banned_terms (+5 lines)

key-decisions:
  - "Bi-mode imports (try container layout first, fall back to repo layout) rather than restructuring the Dockerfile to COPY narrative into `/app/agent/narrative/`. Rationale: the Dockerfile layout `WORKDIR /app; COPY agent.py .; COPY narrative/ ./narrative/` is the Plan 06-03 prescription, and repo layout `agent/narrative/*` is how the offline tests resolve the package. Bi-mode imports keep BOTH paths working without a sys.path hack or a per-environment Dockerfile variant. The ImportError fallback branch is covered by offline tests; the primary branch is covered by the deployed runtime."
  - "Committed each bug fix as its own re-deploy cycle rather than batching. Each `cdk deploy` cycle exposed the next failure mode (container ModuleNotFoundError → validators.py still has `from agent.narrative.banned_terms` → Bedrock Legacy rejection → DEMO-02 regression → prompt tightening doesn't hold). Each re-deploy was 25-40s (cached layers). This is the cheapest feedback loop for runtime integration bugs."
  - "Model swap 3.7 → 4.6 recorded as a deviation, not a plan amendment. The plan and RESEARCH pin Claude 3.7 Sonnet; the swap was forced by Bedrock's Legacy-unused rule in this account. If 3.7 access is restored (trivial in Bedrock console), a future phase can revert for demo parity with v1.0."
  - "Stopped before committing a misleading 06-SAMPLES.md. With DEMO-02 numbers fabricated by the model, shipping 3 persona JSON blocks as 'design-review samples' would falsely certify a broken runtime. The capture script is production-ready; `06-SAMPLES.md` will be generated in 6.1 after the tool-use regression is resolved."

patterns-established:
  - "Runtime vs repo module-layout divergence is a real integration surface. Always run `docker run --entrypoint python <image> -c 'from narrative.fallbacks import FALLBACKS'` (or whatever the target import is) BEFORE cdk deploy. Adding this to the plan's pre-deploy gate would have caught the ModuleNotFoundError without a failed deploy."
  - "Bedrock Legacy model access should be verified with a pre-deploy sanity check. Recipe: `aws bedrock list-foundation-models --query \"modelSummaries[?modelId=='<the-pinned-model>'].modelLifecycle.status\"`. If status is LEGACY, also confirm recent 30-day usage via billing/invocation metrics — or switch to the ACTIVE profile before deploying."
  - "Live-smoke 'passes' with fabricated numbers when v1.0 tests match-by-plan-id-only is a failure-mode we must eliminate. `test_correct_plan_selection` and `test_cheapest_gte_green` passed this run against a runtime that was fabricating savings numbers — because they only check plan_id and `cheapest >= green`, not exact values. `test_sarah_flagship_values` IS the canary here, and it fired correctly. Lesson: future assertions for each persona should pin exact $/month and $/annual values (CUST-002: $16.90/$30.98, CUST-003: $14/$25.67), not just Sarah."

requirements-completed: []
requirements-partial:
  - UI-03    # LLM-produced call_script ships in the container response (validator-passed), but the tool-call bypass means the full LLM contract is broken
  - UI-04    # LLM-produced usage_narrative ships in the container response, same caveat
  - UI-05    # banned-terms validator still enforces no-digits / no-currency — passes on the deployed runtime (fallback path fires when validator rejects; model-path passes when output is clean text)

# Metrics
duration: ~2h (multiple deploy-smoke iterations chasing integration bugs)
cycles: 5 successive cdk deploys (initial image → container-layout fix v1 → validators.py fix → model swap to 4.6 → tightened prompt; each exposed the next layer)
completed: 2026-04-25 (Phase 6 PARTIAL — DEMO-02 regression blocks phase closure)
---

# Phase 06 Plan 03: Container + Deploy + Live Smoke Summary

**Dockerfile Pitfall 1 fixed and deployed. Two follow-on bugs found and fixed during live deploy: (a) bi-mode module-layout imports for `/app/narrative/` runtime vs `agent/narrative/` repo, and (b) `agent/narrative/validators.py` had the same module-layout bug. Bedrock rejected Claude 3.7 Sonnet as Legacy+unused; upgraded to Claude Sonnet 4.6 (ACTIVE) per user decision. Live smoke now passes 18/19 with narrative extended-schema green across all 3 personas. `test_sarah_flagship_values` FAILS — Claude Sonnet 4.6 is fabricating savings numbers instead of honouring the `simulate_savings` tool output, violating v1.0 DEMO-02 preservation (success criterion 5). System-prompt tightening did not resolve it; root cause is a Strands+Claude-4.6 tool-use regression (`Agent.structured_output` is deprecated and may not wire tools correctly to 4.6). Phase 6 is PARTIAL — a decimal phase (6.1) is needed to migrate Strands usage to `structured_output_model` and/or restore Claude 3.7 access.**

## Performance

- **Duration (end-to-end):** ~2h (initial local code commit → 5 successive deploys → DEMO-02 regression surfaced → pause)
- **Started:** 2026-04-25T06:10Z (local code commit)
- **Paused:** 2026-04-25T08:30Z (DEMO-02 regression landed)
- **Tasks:** 1 / 2 PARTIAL — Task 1 produced all artefacts except `06-SAMPLES.md`; Task 2 (human-verify checkpoint) not entered because samples would be misleading
- **Live-deploy cycles:** 5 successive `cdk deploy CustomerTariffAgent` runs (each caught by next bug layer)
- **Files created:** 2 (scripts/capture_samples.py, this SUMMARY.md)
- **Files modified:** 4 (agent/Dockerfile, tests/test_agent_smoke.py, agent/agent.py, agent/narrative/validators.py)
- **AWS spend:** negligible (small image pulls + <10 ConverseStream invocations against Claude Sonnet 4.6)

## Accomplishments

### Plan-prescribed work (Steps 1, 3, 4, partial 5)

- **Pitfall 1 fix landed, deployed, verified.** `agent/Dockerfile` now contains `COPY narrative/ ./narrative/` between `COPY agent.py .` and `EXPOSE 8080`. Platform pin and CMD preserved verbatim. Local ARM64 build + `docker run ... ls /app/narrative/` listed all 7 expected files. Live deploy exposed the container-layout bug that the plan's gate didn't catch (see Issues).
- **Live smoke suite extended.** `tests/test_agent_smoke.py` gained `import re`, module-level `_NUMERIC_RE`, plus `test_narrative_fields_present_and_valid` and `test_narrative_source_marker_present` parametrised across CUST-001/002/003. All 6 new cases PASS against the deployed runtime. Existing v1.0 tests preserved verbatim.
- **scripts/capture_samples.py committed.** Executable, syntax-clean, lazy boto3 import inside `main()`, output path anchored to repo-root. Ready to run once DEMO-02 is restored.
- **cdk deploy CustomerTariffAgent succeeded** in us-east-1 (stack name is `CustomerTariffAgent`, not `AgentCoreStack` as written in the plan — see Deviations #1). AgentRuntimeArn stable across all 5 deploy cycles: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`.

### Discovered-and-fixed integration bugs

- **Bug A — Container-layout ModuleNotFoundError in agent.py.** On first deploy, the runtime crashed at startup with `ModuleNotFoundError: No module named 'agent.narrative'; 'agent' is not a package`. `agent.py` imported via `from agent.narrative.X`, but inside the container `/app/agent.py` is a script (not a package) and the narrative package is at `/app/narrative/`. Fixed with bi-mode imports (try container layout, fall back to repo layout). Re-deploy succeeded.
- **Bug B — Same module-layout bug in validators.py.** After fixing A, the runtime still crashed — validators.py had its own `from agent.narrative.banned_terms import ...`. Applied the same bi-mode pattern. Re-deploy succeeded.
- **Bug C — Claude 3.7 Sonnet blocked by Bedrock Legacy rule.** After A+B, ConverseStream returned `ResourceNotFoundException: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 30 days`. Per user decision, upgraded model_id `us.anthropic.claude-3-7-sonnet-20250219-v1:0` → `us.anthropic.claude-sonnet-4-6` (ACTIVE inference profile). Re-deploy succeeded; 18/19 smoke tests pass.

### Offline regression maintained

- `pytest -m "not smoke"` → **161 passed, 7 skipped, 30 deselected** (with `tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter` deselected — pre-existing `aws_bedrock_agentcore_alpha` import bug, not introduced by this plan). Same baseline as pre-phase-6 plus the new Plan 06-02 tests.

## Task Commits

All commits landed on `main` via worktree merge + direct commits:

1. **fix(06-03): add narrative package to container via Dockerfile COPY (Pitfall 1)** — `2371e7f` (worktree; merged)
2. **test(06-03): extend live smoke with narrative field + _narrative_source assertions** — `9e31c0f` (worktree; merged)
3. **feat(06-03): add scripts/capture_samples.py for one-shot live sample dump** — `5ad6741` (worktree; merged)
4. **docs(06-03): partial summary — Task 1 local code committed, AWS auth gate blocks deploy** — `5b105f0` (worktree; merged) — this SUMMARY supersedes that partial
5. **chore: merge executor worktree (worktree-agent-ad3bb7b7fe52e8313) - partial plan 06-03** — `d276496` (merge)
6. **fix(06-03): bi-mode narrative imports + upgrade model to claude-sonnet-4-6** — `368c0cc` (direct; contains Bug A, Bug B, Bug C fixes and the tightened system prompt — landed atomically because all three are a single "make the container serve requests with tool-use" package)

(This SUMMARY overwrites the partial from commit 5b105f0.)

## Files Created/Modified

### Created

- `scripts/capture_samples.py` — 59-line executable Python 3 script. Env-reads `AGENT_RUNTIME_ARN` + `AWS_DEFAULT_REGION`, invokes `bedrock-agentcore.invoke_agent_runtime` once per persona, writes `06-SAMPLES.md` with one fenced JSON block per persona. Lazy boto3 import. **Not yet run to completion** — first attempt crashed on the RuntimeClientError path; second attempt pending resolution of DEMO-02 regression.
- `.planning/phases/06-agent-narrative-guardrail/06-03-SUMMARY.md` — this file (supersedes `5b105f0`).

### Modified

- `agent/Dockerfile` — +1 line. `COPY narrative/ ./narrative/`.
- `tests/test_agent_smoke.py` — +53 lines. `import re`, `_NUMERIC_RE`, two parametrised tests.
- `agent/agent.py` — +42/-13 lines net. Bi-mode imports for narrative package; model_id swap (3.7 Sonnet → Sonnet 4.6); tightened system prompt (new TOOL-OUTPUT-AS-SOURCE-OF-TRUTH paragraph + Rule 7 on verbatim numbers).
- `agent/narrative/validators.py` — +6/-1 lines. Bi-mode import for `banned_terms`.

## Decisions Made

- **Commit the worktree partial, then pivot to inline execution on main.** The executor hit the auth gate and returned with partial commits on a worktree branch. Rather than spawn a new executor (SendMessage unavailable in this runtime), merged the worktree into main and continued inline — matches `<runtime_compatibility>` sequential-inline fallback. No work lost; 4 worktree commits preserved verbatim.
- **Bi-mode imports chosen over Dockerfile restructure.** Could have reorganised the Dockerfile to `COPY agent.py /app/agent/agent.py; COPY narrative/ /app/agent/narrative/; mkdir /app/agent/__init__.py` to preserve the `agent.narrative` import path. Rejected because (a) the plan's prescribed Dockerfile is simpler, (b) bi-mode is a 1-line try/except that keeps the offline tests working untouched, and (c) the Plan 06-02 import convention (`from agent.narrative.X`) reads naturally in-repo.
- **Model upgrade rather than wait for 3.7 access.** User decision. Alternatives considered: (a) wait for user to reactivate 3.7 in Bedrock console (zero code change, but indefinite delay), (b) swap to 4.5 (smaller family jump, still ACTIVE), (c) swap to 4.6 (latest). Went with 4.6 per user selection.
- **Stop after tightened prompt failed rather than migrate Strands.** Migrating `agent.structured_output(...)` to the new `Agent(..., structured_output_model=...)` API is non-trivial; Strands semantics differ (it wires tools differently when structured output is declared at agent-init vs call-time). That work belongs to a discrete decimal-phase plan, not a Plan 06-03 patch — the blast radius is too wide for a 5th in-session deploy cycle.
- **Don't ship a misleading 06-SAMPLES.md.** The capture script works, and running it would produce a file with 3 persona JSON blocks. But every block would contain model-fabricated savings numbers (e.g. Sarah $18.50 instead of $30), and `_narrative_source: model` would mark them as genuine LLM outputs. Design reviewers would have no way to know the numbers are wrong. Better to withhold the file than to certify a broken runtime.

## Deviations from Plan

### 1. [Rule 2 - Plan error, corrected] Stack name is `CustomerTariffAgent`, not `AgentCoreStack`

- **Found during:** `cdk diff AgentCoreStack` → "No stacks match the name(s) AgentCoreStack"
- **Issue:** Plan 06-03 says `cdk deploy AgentCoreStack` but the stack's CloudFormation name (second arg to `AgentCoreStack(...)` in `app.py` line 23-27) is `CustomerTariffAgent`. The Python construct class is `AgentCoreStack`, but that name doesn't appear in CloudFormation.
- **Fix applied:** Used `cdk deploy CustomerTariffAgent` (and `cdk diff CustomerTariffAgent`, `aws cloudformation describe-stacks --stack-name CustomerTariffAgent`, etc.) throughout.
- **Files modified:** none (rename at invocation only).
- **Verification:** `cdk list` → `CustomerTariff`, `CustomerTariffAgent`, `CustomerTariffApi`. `CustomerTariffAgent.AgentRuntimeArn` CfnOutput present.

### 2. [Rule 2 - Runtime layout bug, fixed] Container `agent.narrative` imports fail — bi-mode imports applied

- **Found during:** First `cdk deploy` succeeded but live smoke returned `RuntimeClientError`. CloudWatch logs showed `ModuleNotFoundError: No module named 'agent.narrative'; 'agent' is not a package`.
- **Issue:** The Dockerfile `COPY narrative/ ./narrative/` places the package at `/app/narrative/`, but `agent.py` (and `validators.py`) imported via `from agent.narrative.X`, which in the container would require `/app/agent/narrative/` (with `/app/agent/__init__.py`). The plan's Pitfall-1 mitigation fixed the MISSING-package case but introduced a NEW wrong-path case.
- **Fix applied:** Bi-mode imports in both `agent/agent.py` and `agent/narrative/validators.py` — try container layout first (`from narrative.X`), fall back to repo layout (`from agent.narrative.X`) via `ImportError`.
- **Files modified:** `agent/agent.py`, `agent/narrative/validators.py`.
- **Verification:** Local `docker run --entrypoint python tariff-agent-phase6-local -c 'from narrative.fallbacks import FALLBACKS; ...'` → "container imports OK". Deployed image stops crashing at startup. Offline regression still passes via the ImportError-fallback branch.

### 3. [Rule 2 - Environmental, accepted] Claude 3.7 Sonnet blocked — model upgraded to Sonnet 4.6

- **Found during:** After Deviation 2 fix, live smoke still failed. CloudWatch showed `ResourceNotFoundException: Access denied. This Model is marked by provider as Legacy and you have not been actively using the model in the last 30 days. Please upgrade to an active model on Amazon Bedrock. └ Model id: us.anthropic.claude-3-7-sonnet-20250219-v1:0`.
- **Issue:** Bedrock automatically revokes access to Legacy-tagged models after 30 days of inactivity in the calling account. The v1.0 agent was inactive across the v1→v2.0 gap and has been locked out.
- **Fix applied (per user decision):** `model_id` changed from `us.anthropic.claude-3-7-sonnet-20250219-v1:0` to `us.anthropic.claude-sonnet-4-6` (ACTIVE inference profile verified via `aws bedrock list-inference-profiles`).
- **Files modified:** `agent/agent.py` (line 271).
- **Verification:** Post-upgrade, ConverseStream invocations succeed; `_narrative_source` fields show `"model"` (not `"fallback"`) — LLM is producing output through the validator.
- **Deviation from plan:** Plan 06-03 and 06-RESEARCH.md pin Claude 3.7 Sonnet. The model choice has been changed; this is a meaningful deviation that should be reviewed at Phase 6 close or by a rollback patch.

### 4. [Rule 3 - Blocking, NOT FIXED] DEMO-02 $30/$55 preservation FAILS on Claude Sonnet 4.6

- **Found during:** `pytest tests/test_agent_smoke.py::test_sarah_flagship_values` against the tightened-prompt deploy.
- **Issue:** On Claude Sonnet 4.6, the agent returns `green.saving_monthly = $18.50` (expected $30.00) and `cheapest.saving_monthly = $30.00` (expected $55.00) for Sarah Chen. Direct `aws lambda invoke --function-name tariff-tools` returns the correct `$30/$55` from the deterministic ToolsLambda, so the tool is returning the right numbers. The model is either not calling the tool or ignoring its output. Cross-persona comparison reveals the problem is systematic: CUST-002 also gets `$18.50/$30.00` (same hallucinated pair as CUST-001), and CUST-003 gets `$18.50/$22.00` — meaning the model is anchoring on consistent-looking values across invocations rather than reading them from the tool.
- **Evidence:** CloudWatch runtime logs show invocations completing in ~3.0s (Claude-only round-trip; would be ~0.4-0.8s longer if Lambda was being invoked). `Agent.structured_output method is deprecated` warning fires on every invocation — newer Strands recommends passing `structured_output_model` directly into `Agent(...)` constructor or at invocation time, not via the method chain. Combined with 4.6's stricter tool-use protocol (enhanced tool use v2), this suggests Strands is not wiring `simulate_savings` as a callable tool for 4.6.
- **Attempted fix:** Tightened system prompt with an explicit TOOL-OUTPUT-AS-SOURCE-OF-TRUTH paragraph + Rule 7 verbatim-copy enforcement. Did not resolve the regression — the model still returns the same fabricated numbers after re-deploy. This confirms the issue is not a prompt-following problem but a tool-availability problem.
- **Files modified:** `agent/agent.py` (system prompt tightening, preserved in commit; a future rollback can remove it if it turns out to be counterproductive).
- **Verification:** Three direct `invoke_agent_runtime` calls post-prompt-tightening all returned the same fabricated CUST-001 numbers. `_narrative_source: model` on every field.
- **NOT FIXED in this plan.** Requires Strands API migration (or a Strands version bump), OR a rollback to Claude 3.7 Sonnet once Bedrock access is restored. Scheduled as Phase 6.1 follow-up (see Next Phase Readiness).

## Known Stubs

None introduced by this plan. Plan 01's `tenure_band: "established"` v2.0 placeholder in `agent/narrative/shape.py` is unchanged.

## Threat Flags

- **NEW — Silent tool-call regression.** The agent is returning responses that pass schema validation and pass 12/13 v1.0 smoke tests, but the savings numbers are fabricated. This is a TRUST threat (STRIDE Spoofing of authoritative data) that the existing `tests/test_agent_smoke.py` does NOT fully catch — only `test_sarah_flagship_values` asserts exact numbers; the per-persona parametrised tests (`test_correct_plan_selection`, `test_cheapest_gte_green`) verify plan selection and relative ordering but not absolute values. **Mitigation:** the Phase 6.1 follow-up plan should add `test_marcus_flagship_values` ($16.90/$30.98) and `test_elena_flagship_values` ($14/$25.67) as exact-value canaries alongside the existing Sarah canary.
- **Operational — Bedrock Legacy rule.** Documented in Deviation 3; also a threat to v1.0 rollback drill (Phase 10) if a rollback to the pinned 3.7 image fails because access has since been revoked. **Mitigation:** Phase 10 should add a pre-freeze access check: `aws bedrock get-foundation-model --model-identifier <pinned-model-id>` + a 30-day-freshness invocation check.

## Issues Encountered

### 1. First cdk deploy = runtime crashes at startup (Deviation 2)

Manifested as 19/19 smoke tests failing with `RuntimeClientError: An error occurred when starting the runtime`. Root cause found in CloudWatch: `ModuleNotFoundError: No module named 'agent.narrative'`. Fix: bi-mode imports in agent.py AND validators.py. Two deploys needed (agent.py first, then validators.py).

### 2. Second runtime failure = Bedrock Legacy access revoked (Deviation 3)

After fixing Issue 1, smoke tests still failed but all 19 now "passed" — at first suspicious, then confirmed: validator rejected the broken LLM output, `invoke()` triggered the fallback path, and the FALLBACKS strings passed the numeric-free check. So "passing" was actually the fallback path firing. CloudWatch revealed the true cause: Bedrock blocked ConverseStream on 3.7 Sonnet. This is an important observation — the Plan 06-02 retry-once-then-per-field-fallback contract worked perfectly as designed, silently masking the upstream model failure. Exactly its job; but also a visibility gap that made the root cause harder to spot.

### 3. Claude Sonnet 4.6 fabricates savings numbers (Deviation 4 — the big one)

After fixing 1+2, smoke tests PASSED 18/19 — `_narrative_source: model`, narrative fields pass all validators, persona prose reads naturally. But `test_sarah_flagship_values` fails: $18.50 instead of $30. Deeper inspection across all 3 personas shows the model is never calling simulate_savings (invocations ~3s flat, no Lambda round-trip), and is instead returning the SAME fabricated pair ($18.50/$30) for both CUST-001 and CUST-002. This is NOT a prompt-following issue (the prompt tightening test confirmed) — it's a Strands+Claude-4.6 tool-use binding issue. The `Agent.structured_output method is deprecated` warning points at the probable API migration path.

## User Setup Required

None for this partial completion. The deployed CustomerTariffAgent is live in us-east-1 and serving requests (the user can invoke it, just don't trust the savings numbers on the 4.6 path).

Once Phase 6.1 ships (either Strands migration or 3.7 rollback), full verification closes.

## Pending Checkpoints

### Task 2 human-verify — NOT ENTERED (intentional)

The plan's Task 2 `checkpoint:human-verify` was supposed to be entered once `06-SAMPLES.md` is populated. The samples file has NOT been populated because doing so with the current runtime would produce misleading artefacts (3 persona JSON blocks with model-fabricated savings numbers).

Enter Task 2 only after Phase 6.1 restores tool-honouring behaviour. At that point, the resume-signal tokens from Plan 06-03 apply verbatim:

- `approved`
- `approved with log format v3`
- `fallback prose issues: <description>`
- `cloudwatch needs json formatter`
- `blocked: <description>`

## Next Phase Readiness

**Phase 6 is PARTIAL.** Phase 6 success criterion 5 has two halves:

1. ✅ "Deployed image serves the extended schema in us-east-1" — PASSES. All 3 personas return the extended schema; narrative fields pass validators; `_narrative_source` marker is present and correctly shaped.
2. ❌ "v1.0 DEMO-02 $30/$55 deltas unchanged" — FAILS. Claude Sonnet 4.6 fabricates numbers. 3.7 Sonnet (which honoured the tool) is no longer accessible.

**Phase 7 (API pass-through) is NOT yet safe to start.** Phase 7 forwards the runtime response through the API Lambda to the UI; forwarding fabricated numbers would propagate the regression to the demo.

**Proposed Phase 6.1 scope (decimal follow-up plan):**

1. Investigate Strands `Agent.structured_output` deprecation — migrate call sites to `structured_output_model=...` API.
2. Verify Strands+Claude-4.6 tool-use round-trip in a local smoke (mock Bedrock, assert tool invocation path).
3. Alternative track: reactivate Claude 3.7 Sonnet in Bedrock console; revert `model_id` + remove tightened prompt; validate DEMO-02 preservation.
4. Add `test_marcus_flagship_values` ($16.90/$30.98) and `test_elena_flagship_values` ($14/$25.67) — exact-value canaries so the silent-fabrication mode can't sneak past future smoke runs.
5. Populate `06-SAMPLES.md` via `scripts/capture_samples.py`.
6. Enter Plan 06-03 Task 2 human-verify.

**Phase 6.1 ≠ new phase.** Per project convention, decimal phase = gap-closure against the parent (Phase 6) rather than a new feature milestone.

## Self-Check

### What this plan DID ship

- [x] `agent/Dockerfile` — `COPY narrative/ ./narrative/` landed, deployed, in production in us-east-1.
- [x] `tests/test_agent_smoke.py` — `import re`, `_NUMERIC_RE`, 2 parametrised tests (6 cases) landed. All 6 pass live.
- [x] `scripts/capture_samples.py` — 59 lines, executable, syntax-clean, committed.
- [x] `agent/agent.py` — bi-mode imports (container layout + repo layout), model_id = `us.anthropic.claude-sonnet-4-6`, tightened system prompt.
- [x] `agent/narrative/validators.py` — bi-mode import for `banned_terms`.
- [x] `cdk deploy CustomerTariffAgent` ran successfully in us-east-1. AgentRuntimeArn stable: `arn:aws:bedrock-agentcore:us-east-1:588738606436:runtime/tariff_agent-O2Hai86N8V`.
- [x] Live smoke — 18/19 tests pass against the deployed runtime.
- [x] Offline regression still green: 161 passed.

### What this plan DID NOT ship

- [ ] `06-SAMPLES.md` — NOT populated. Withheld intentionally to avoid certifying a broken runtime.
- [ ] `test_sarah_flagship_values` green on deployed runtime — FAILS. Model fabricates numbers.
- [ ] Phase 6 success criterion 5 full pass — HALF (extended schema yes, DEMO-02 preservation no).
- [ ] Task 2 human-verify — NOT ENTERED (samples not populated).

## Self-Check: PARTIAL — DEMO-02 regression blocks phase closure

Extended schema serves correctly on the deployed runtime. All narrative-specific plan acceptance criteria pass (extended-schema fields, _narrative_source marker, validator enforcement, fallback prose passes validator). But v1.0 DEMO-02 preservation (the plan's final acceptance criterion) fails because the forced model upgrade (3.7 → 4.6) exposed a Strands+Claude-4.6 tool-use regression. Phase 6.1 is required to close.

---
*Phase: 06-agent-narrative-guardrail*
*Completed (partial): 2026-04-25*
*Full completion: pending Phase 6.1 (Strands tool-use migration OR Claude 3.7 reactivation)*

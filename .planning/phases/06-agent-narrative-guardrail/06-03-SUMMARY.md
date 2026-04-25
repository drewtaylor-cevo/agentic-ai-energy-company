---
phase: 06-agent-narrative-guardrail
plan: 03
subsystem: agent
tags: [docker, cdk, deploy, smoke, narrative, bedrock-agentcore, auth-gate]

# Dependency graph
requires:
  - phase: 06-01 (narrative foundations)
    provides: agent/narrative package (banned_terms, fallbacks, prompt, prompt_loader, shape, validators) — must be copied into the container image by this plan's Dockerfile change.
  - phase: 06-02 (agent narrative integration)
    provides: extended TrackInfo + invoke() retry-once-then-per-field-fallback + _narrative_source marker — ships inside the deployed container.
  - phase: v1.0 (shipped)
    provides: AgentCoreStack + AgentRuntimeConstruct (asset from `agent/`, ARM64 platform pin, `AgentRuntimeArn` CfnOutput); tests/test_agent_smoke.py live-invoke pattern with `@pytest.mark.parametrize("customer_id", ...)`.
provides:
  - Fixed agent/Dockerfile (Pitfall 1) — COPY narrative/ into the image
  - Extended tests/test_agent_smoke.py — test_narrative_fields_present_and_valid + test_narrative_source_marker_present (6 new parametrised smoke tests on top of 13 v1.0 tests)
  - scripts/capture_samples.py — one-shot live-dump helper committed as an executable script
  - (DEFERRED pending auth gate) cdk deploy AgentCoreStack in us-east-1
  - (DEFERRED pending auth gate) live smoke green on all 3 personas
  - (DEFERRED pending auth gate) 06-SAMPLES.md populated from live runtime
affects: [06-03 Task 2 (human-verify checkpoint — blocked until live capture is complete), 07 (Phase 7 depends on the Phase-6 image being live in us-east-1), 09 (eval harness reads _narrative_source from the deployed runtime)]

# Tech tracking
tech-stack:
  added: []   # no new deps
  patterns:
    - "Dockerfile file-copy: explicit `COPY <subdir>/ ./<subdir>/` rather than a glob — matches the one-file-per-line convention the existing Dockerfile set at v1.0."
    - "Live-smoke extension pattern: new parametrised tests inherit the module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not AGENT_RUNTIME_ARN, ...)]` — no per-test markers needed; reuses the existing `agentcore_client` fixture and `_invoke_agent` helper verbatim."
    - "One-shot sample-capture script under `scripts/`: lazy boto3 import inside main() so `ast.parse` / import-time linting works without AWS creds; output anchored to `Path(__file__).resolve().parent.parent` for cwd-independence."
    - "Pre-deploy local gate: `docker build --platform linux/arm64` + `docker run --rm --entrypoint ls <image> /app/narrative/` — validates Pitfall 1 fix before any `cdk deploy`, so the cost of a bad COPY is caught locally rather than as a runtime ModuleNotFoundError."

key-files:
  created:
    - scripts/capture_samples.py             # new; +59 lines; executable
    - .planning/phases/06-agent-narrative-guardrail/06-03-SUMMARY.md
  modified:
    - agent/Dockerfile                       # +1 line (`COPY narrative/ ./narrative/`)
    - tests/test_agent_smoke.py              # +53 lines (import re + 2 parametrised tests + module marker = 6 new smoke test cases)

key-decisions:
  - "Committed Task 1 Steps 1, 3, 4 and the SUMMARY.md up-front (before Step 2 cdk deploy) so the Dockerfile fix, smoke-test extension, and capture-script land as discrete, reviewable commits. Step 2 (deploy) + Step 5 (live smoke + sample capture) are deferred pending resolution of the auth gate (see Deviations below) — no local work was blocked and the committed changes are self-contained."
  - "Locally verified Pitfall 1 with a real `docker build --platform linux/arm64` + `docker run ... ls /app/narrative/` round-trip before committing the Dockerfile change, so a bad COPY would have been caught locally (matches the plan's explicit pre-deploy gate). All seven expected files (__init__.py, banned_terms.py, fallbacks.py, prompt.txt, prompt_loader.py, shape.py, validators.py) were listed from inside the built image."
  - "Followed the plan's literal test-extension text verbatim — added `import re` to the existing import block, defined `_NUMERIC_RE` at module level, and appended the two new parametrised tests after `test_sarah_flagship_values`. Did not re-order or refactor any v1.0 tests."

patterns-established:
  - "Auth-gate handling: when AWS credentials are unavailable (missing / invalid / expired SSO), the executor commits all local-safe changes, writes a partial SUMMARY.md that clearly flags the blocked steps, and returns a `human-action` checkpoint to the orchestrator. The orchestrator and user decide whether to re-spawn the continuation agent (post-auth) or chain this plan with a manual `cdk deploy` and sample capture."

requirements-completed: []
requirements-partial: [UI-03, UI-04, UI-05]   # code changes that advance these requirements are committed, but Phase 6 success criterion 5 (live deployed image in us-east-1) is not yet proven — live smoke pending

# Metrics
duration: ~7 min (local work); live-deploy + smoke + sample capture pending auth resolution
completed: 2026-04-25 (Task 1 partial — all local code committed)
---

# Phase 06 Plan 03: Container + Deploy + Live Smoke Summary

**Dockerfile COPY gap (RESEARCH Pitfall 1) fixed and locally verified against a real ARM64 build; live smoke suite extended with two new parametrised narrative tests (6 test cases) on top of 13 v1.0 tests; scripts/capture_samples.py committed as an executable one-shot sample-dump helper. Live `cdk deploy AgentCoreStack` and live smoke + `06-SAMPLES.md` population are DEFERRED behind an auth gate (`AWS_PROFILE=cevo-25` env var points to a profile that does not exist on this machine) — a `human-action` checkpoint has been returned to the orchestrator.**

## Performance

- **Duration (code-only):** ~7 min (start 2026-04-25T06:10Z → three code commits + summary at 06:19Z)
- **Started:** 2026-04-25T06:10:00Z
- **Completed (code-only):** 2026-04-25T06:19:00Z
- **Deferred work:** cdk deploy + live smoke + capture_samples.py run (depends on user resolving auth gate)
- **Tasks:** 1 / 2 partially complete; Task 2 (human-verify) unreachable until Task 1 completes
- **Files created:** 2 (scripts/capture_samples.py, 06-03-SUMMARY.md)
- **Files modified:** 2 (agent/Dockerfile, tests/test_agent_smoke.py)

## Accomplishments

- **Pitfall 1 neutralised in code.** `agent/Dockerfile` now contains the exact `COPY narrative/ ./narrative/` line the plan prescribed, between `COPY agent.py .` and `EXPOSE 8080`. Platform pin (`FROM --platform=linux/arm64 python:3.12-slim`) and `CMD ["python", "agent.py"]` preserved verbatim. Grep checks pass: `grep -cE '^COPY narrative/ \./narrative/$'` → 1; `grep -c '^FROM --platform=linux/arm64 python:3.12-slim'` → 1.
- **Pitfall 1 fix verified locally with a real ARM64 container build.** `docker build --platform linux/arm64 -t tariff-agent-phase6-local .` (from `agent/`) completed cleanly; `docker run --rm --entrypoint ls tariff-agent-phase6-local /app/narrative/` listed all 7 expected files: `__init__.py`, `banned_terms.py`, `fallbacks.py`, `prompt.txt`, `prompt_loader.py`, `shape.py`, `validators.py`. A bad COPY path would have been caught here.
- **Live smoke suite extended with 6 new narrative test cases.** `tests/test_agent_smoke.py` now carries `import re`, `_NUMERIC_RE = re.compile(r"[\d$£€%]")` at module level, plus two parametrised tests — `test_narrative_fields_present_and_valid` and `test_narrative_source_marker_present` — each running against all three personas (CUST-001/002/003). Collection verified: 19 tests total (13 v1.0 + 6 Phase 6). Module-level `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not AGENT_RUNTIME_ARN, ...)]` applies automatically; no per-test marker needed. All v1.0 tests (`test_both_tracks_present`, `test_savings_fields_present`, `test_correct_plan_selection`, `test_cheapest_gte_green`, `test_sarah_flagship_values`) are preserved verbatim — the DEMO-02 $30/$55 contract stays locked.
- **One-shot sample-capture helper committed.** `scripts/capture_samples.py` is executable (chmod +x confirmed via `test -x`), syntax-clean (`ast.parse` round-trip), and follows the plan's literal script body. The boto3 import is lazy (inside `main()`) so the file can be parsed / linted without AWS creds. Output path is anchored to `Path(__file__).resolve().parent.parent` for cwd-independence — safe to run from any directory.
- **Offline regression still green.** `pytest -m "not smoke"` (with `SKIP_AWS_SMOKE=1` and the pre-existing `aws_bedrock_agentcore_alpha` CDK deselect carried forward from Plan 06-02's deferred-items.md) → **155 passed, 13 skipped, 30 deselected, 1 warning**. Same 155-passed baseline as Plan 06-02; the 6-test delta in deselected (24 → 30) is the new smoke tests correctly excluded from the offline run.

## Task Commits

Task 1 (`type="auto"`) committed as three discrete conventional-commits:

1. **fix(06-03): add narrative package to container via Dockerfile COPY (Pitfall 1)** — `2371e7f`
2. **test(06-03): extend live smoke with narrative field + _narrative_source assertions** — `9e31c0f`
3. **feat(06-03): add scripts/capture_samples.py for one-shot live sample dump** — `5ad6741`

Task 1 Steps 2 + 5 (cdk deploy; live smoke run; capture_samples.py invocation populating 06-SAMPLES.md) are DEFERRED — see Deviations #1.

Task 2 (`type="checkpoint:human-verify"`) is unreachable until Task 1 fully completes — see "Pending Checkpoints" below.

## Files Created/Modified

### Created

- `scripts/capture_samples.py` — 59-line executable Python 3 script. Env-reads `AGENT_RUNTIME_ARN` + `AWS_DEFAULT_REGION` (defaults to `us-east-1`), invokes `bedrock-agentcore.invoke_agent_runtime` once per persona, writes `.planning/phases/06-agent-narrative-guardrail/06-SAMPLES.md` with one fenced JSON block per persona. Lazy boto3 import inside `main()`.
- `.planning/phases/06-agent-narrative-guardrail/06-03-SUMMARY.md` — this file.

### Modified

- `agent/Dockerfile` — +1 line. Added `COPY narrative/ ./narrative/` between `COPY agent.py .` and `EXPOSE 8080`. No other change; platform pin + CMD preserved verbatim.
- `tests/test_agent_smoke.py` — +53 lines. Added `import re` to the existing import block, module-level `_NUMERIC_RE`, and two parametrised tests (`test_narrative_fields_present_and_valid`, `test_narrative_source_marker_present`) — 6 new parametrised test cases total.

## Decisions Made

- **Commit local-only work first, then raise auth gate.** Rather than blocking at `cdk deploy` without writing any commits, I landed the Dockerfile fix, smoke-test extension, and capture-script as three discrete conventional commits, wrote this SUMMARY.md capturing partial-Task-1 state, and only then raised the `human-action` checkpoint. The local work is internally consistent and reviewable independently — a continuation agent (post-auth) can pick up from `cdk deploy` without redoing anything.
- **Literal Dockerfile replacement per plan `<action>` — not a glob `COPY . /app/`.** The RESEARCH §Pitfall 1 mitigation offered two forms: explicit `COPY narrative/ ./narrative/` OR glob `COPY . /app/`. I chose the explicit form because it matches the existing Dockerfile's convention (one file per `COPY` line, verified against the 13-line v1.0 baseline), keeps the image layer count minimal and cache-friendly, and is easier to review in a PR diff. No deviation from plan `<action>` text.
- **Local ARM64 docker verification before commit.** The plan's explicit gate is "verify `docker run ... ls /app/narrative/` lists all 7 expected files before proceeding to deploy". I ran that gate and only then committed `2371e7f`. If it had failed I would have treated it as a Rule 1 bug and iterated.
- **`_NUMERIC_RE` defined at module level, not inside each test.** The plan's literal `<action>` text compiles the regex once at module level and reuses it. I followed that exactly — regex is compiled at test-module import, not per-test-call.

## Deviations from Plan

### Deferred (auth gate — Rule 3 blocking, environmental)

**1. [Rule 3 - Blocking, auth gate] `cdk deploy AgentCoreStack` + live smoke + `06-SAMPLES.md` population DEFERRED pending AWS credential resolution**

- **Found during:** Task 1 Step 2 (pre-flight `aws sts get-caller-identity`)
- **Issue:** The execution shell has `AWS_PROFILE=cevo-25` set as an environment variable, but `cevo-25` is NOT a configured profile on this machine. `~/.aws/config` exists with 30+ other profiles (incl. `cevo-sandbox`, `cevo-dev25`, `cevo-demo`) but none named `cevo-25`. `aws sts get-caller-identity` fails with `ProfileNotFound: cevo-25`. With `AWS_PROFILE` unset, default creds fail with `InvalidClientTokenId`. Per this agent's instructions (`awareness` block, `authentication_gates` protocol in `$HOME/.claude/get-shit-done/references/checkpoints.md`), auth errors are gates, not bugs — do NOT retry, do NOT attempt to set AWS creds.
- **Fix:** None applied locally — this is a user-side gate. Committed the three Task 1 code commits (Dockerfile fix, smoke test extension, capture script) so a continuation agent (post-auth) can pick up from Step 2 without redoing local work. Returned a `human-action` checkpoint to the orchestrator with exact resume instructions (see "Pending Checkpoints" below).
- **Files modified:** None — auth-gate is purely environmental.
- **Verification:** `aws sts get-caller-identity 2>&1` returns `ProfileNotFound: cevo-25` (with AWS_PROFILE set) or `InvalidClientTokenId` (with AWS_PROFILE unset). Expected resolution: user either (a) exports a correct AWS_PROFILE pointing to the demo account, (b) runs `aws sso login --profile <profile>`, or (c) runs `cdk deploy` + `python3 scripts/capture_samples.py` manually themselves and reports the ARN + samples file back for Task 2 review.
- **Impact:** Task 1 Steps 2 (deploy) + 5 (live smoke + sample capture) NOT run. Task 2 (human-verify checkpoint — reviews `06-SAMPLES.md` + CloudWatch logs) is unreachable until Steps 2 + 5 complete. 06-SAMPLES.md does NOT yet exist (plan acceptance criterion blocked).

**Total deviations:** 1 auto-raised auth gate (Rule 3). No other deviations from the plan — Steps 1, 3, 4 executed literally verbatim against the plan's `<action>` text.

## Known Stubs

None introduced by this plan. The Plan 01 `tenure_band: "established"` v2.0 placeholder in `agent/narrative/shape.py` is unchanged (Plan 01 decision, out of scope here).

## Threat Flags

None beyond the plan's `<threat_model>`. The Dockerfile change is explicitly covered by T-6-01 (Repudiation — deployed image) and T-6-02 (Integrity — FALLBACKS via deployed image); both require the COPY fix this plan provides. The smoke-test extension is covered by T-6-01 (live assertion on the deployed image). The capture-script is covered by the trust boundary "Human reviewer → sample file" and introduces no new surface.

## Issues Encountered

**AWS authentication unavailable in execution shell.** `AWS_PROFILE=cevo-25` env var does not match any configured profile on this machine, and default creds are invalid. Per instructions this is a gate, not a bug — committed all local work and raised a `human-action` checkpoint. Documented in Deviation #1.

## User Setup Required

**Before this plan can be fully completed, the user must resolve the auth gate:**

1. Either export a correct AWS_PROFILE that points to the Phase-5 demo AWS account (the account that owns the v1.0 `AgentCoreStack` in us-east-1), for example:
   ```bash
   export AWS_PROFILE=<correct-profile-name-e.g.-cevo-demo>
   aws sso login --profile $AWS_PROFILE   # if SSO-based
   aws sts get-caller-identity            # verify
   ```
2. Or run the remaining Task 1 steps manually and report results back for Task 2 review:
   ```bash
   cd /Users/drewtaylor/Documents/Cevo/Customer-Tariff
   export AWS_DEFAULT_REGION=us-east-1
   cdk diff AgentCoreStack
   cdk deploy AgentCoreStack --require-approval never
   export AGENT_RUNTIME_ARN="$(aws cloudformation describe-stacks \
     --stack-name AgentCoreStack \
     --query 'Stacks[0].Outputs[?OutputKey==`AgentRuntimeArn`].OutputValue' \
     --output text)"
   AGENT_RUNTIME_ARN=$AGENT_RUNTIME_ARN AWS_DEFAULT_REGION=us-east-1 \
     /opt/homebrew/bin/python3.13 -m pytest tests/test_agent_smoke.py -v
   AGENT_RUNTIME_ARN=$AGENT_RUNTIME_ARN AWS_DEFAULT_REGION=us-east-1 \
     python3 scripts/capture_samples.py
   git add .planning/phases/06-agent-narrative-guardrail/06-SAMPLES.md
   git commit --no-verify -m "docs(06-03): capture live smoke samples for 3 personas"
   ```

Once Steps 2 + 5 are complete and `06-SAMPLES.md` is committed, Task 2 (human-verify) can be entered per the plan's `<how-to-verify>` block.

## Pending Checkpoints

### Task 1 auth gate → Task 2 human-verify (blocking, gated)

Currently blocked by Deviation #1 (auth gate). Once resolved, the plan's Task 2 `type="checkpoint:human-verify"` becomes active. Its content is quoted verbatim below for orchestrator convenience:

**What built (Task 1 once complete):**
Task 1 captured three live responses into `06-SAMPLES.md` (one per persona) and deployed the extended agent to AgentCore in us-east-1. Automated checks prove no numeric tokens leaked and the schema is correct. Two items remain human-only: (1) fallback-prose quality (06-VALIDATION.md Manual-Only row 1), (2) CloudWatch log format (06-VALIDATION.md Manual-Only row 2, research Open Q1).

**How to verify (Task 2):**
1. `cat .planning/phases/06-agent-narrative-guardrail/06-SAMPLES.md` and ask, per persona's `usage_narrative` + `call_script`: does it scan aloud, does the voice match (Sarah high-usage winter, Marcus mid-usage apartment, Elena summer-peak), is `_narrative_source` mostly `"model"` or did fallbacks fire.
2. `python3 -c "from agent.narrative.fallbacks import FALLBACKS; import json; print(json.dumps(FALLBACKS, indent=2))"` and compare each of 12 fallback strings against the persona profiles in `infrastructure/seed_data/billing_records.py` L46-65.
3. Tail CloudWatch Logs: `aws logs tail /aws/bedrock-agentcore/runtimes/tariff_agent --follow --region us-east-1` in one terminal; trigger `python3 scripts/capture_samples.py` in another. Check whether `narrative fallback fired` records (if any fire) emit queryable JSON `{customer_id, track, field, failure_reason}` or plain text.

**Resume-signal tokens (exact five options from Plan 06-03):**
- `approved`
- `approved with log format v3`
- `fallback prose issues: <description>`
- `cloudwatch needs json formatter`
- `blocked: <description>`

## Next Phase Readiness

Phase 7 is NOT yet unblocked — Phase 7's gate is "Phase 6 image live in us-east-1 serving extended schema", which this plan has not yet proven. Once the auth gate is resolved and the remaining steps run green, Phase 7 will be ready with the full Phase 6 contract honoured by a live runtime.

**Follow-up owned by this plan (post-auth continuation):**
- `cdk deploy AgentCoreStack --require-approval never` in us-east-1 (idempotent; rolls the runtime to the Phase 6 image — same ARN, new image hash)
- `AGENT_RUNTIME_ARN=... pytest tests/test_agent_smoke.py -v` → expected 19 passed
- `AGENT_RUNTIME_ARN=... python3 scripts/capture_samples.py` → populates 06-SAMPLES.md
- Commit `06-SAMPLES.md` as `docs(06-03): capture live smoke samples for 3 personas`
- Re-raise the Task 2 `human-verify` checkpoint with the populated samples

## Self-Check

- `agent/Dockerfile` (modified, `grep -cE '^COPY narrative/ \./narrative/$' agent/Dockerfile` → 1) — FOUND
- `tests/test_agent_smoke.py` (modified, `grep -cE 'def test_narrative_(fields_present_and_valid|source_marker_present)' tests/test_agent_smoke.py` → 2) — FOUND
- `scripts/capture_samples.py` (created, `test -x` → executable) — FOUND
- Commit `2371e7f` (fix Dockerfile) — FOUND in `git log --oneline`
- Commit `9e31c0f` (extend smoke tests) — FOUND in `git log --oneline`
- Commit `5ad6741` (add capture script) — FOUND in `git log --oneline`
- Local Docker build succeeded: `docker build --platform linux/arm64 -t tariff-agent-phase6-local agent/` exit 0
- Local image narrative listing: `docker run --rm --entrypoint ls tariff-agent-phase6-local /app/narrative/` → 7 expected files listed
- Offline regression still green: `SKIP_AWS_SMOKE=1 pytest -m "not smoke" --deselect tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter` → 155 passed, 13 skipped, 30 deselected
- `.planning/phases/06-agent-narrative-guardrail/06-SAMPLES.md` — MISSING (blocked by auth gate; expected to be populated post-auth)
- `cdk deploy AgentCoreStack` — NOT RUN (auth gate; see Deviation #1)
- Live smoke run — NOT RUN (auth gate; needs AGENT_RUNTIME_ARN from deploy)
- Task 2 (human-verify) — NOT REACHED (upstream Task 1 partial)

## Self-Check: PARTIAL — AUTH GATE

Local code changes verified and committed; live-AWS work is blocked behind an authentication gate that only the user can resolve. A `human-action` checkpoint has been returned to the orchestrator with exact resume instructions.

---
*Phase: 06-agent-narrative-guardrail*
*Completed (code-only): 2026-04-25*
*Live deploy + smoke + sample capture: pending auth-gate resolution*

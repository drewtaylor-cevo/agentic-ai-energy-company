---
phase: 05-demo-hardening
plan: 01
type: execute
status: complete
completed: 2026-04-25
---

# Plan 05-01 Summary — Pre-deploy readiness gate

Pre-deploy readiness gate for Phase 5. Confirmed the Claude-model-access blocker is cleared, verified the Phase 3 SSM cross-stack wiring is in source, and proved every fresh-clone toolchain command exits 0. One lockfile-drift gap caught and fixed — exactly the class of issue this gate exists for.

## Outcome

Phase 5 is cleared to run live AWS API calls starting in Plan 05-02.

## Evidence

### Task 1 — Blocker sign-off (human checkpoint)

User typed `approved` after confirming:
- `aws sts get-caller-identity --region us-east-1` returned the intended account
- Bedrock console shows Claude model access "granted" in us-east-1
- `aws cloudformation list-stacks --region us-east-1 ...` ran without AccessDenied
- Region in all AWS output is `us-east-1`

Approval timestamp: 2026-04-25 (this session)

### Task 2 — SSM cross-stack wiring verified (Phase 3 D-07 amendment)

```
$ grep -n '/customer-tariff/agent-runtime-arn' infrastructure/agentcore_stack.py
40:            parameter_name="/customer-tariff/agent-runtime-arn",

$ grep -n '/customer-tariff/agent-runtime-arn' infrastructure/backend_api_stack.py
21:            self, "/customer-tariff/agent-runtime-arn"

$ grep -n 'AgentRuntimeArn' infrastructure/agentcore_stack.py
28:        CfnOutput(self, "AgentRuntimeArn", value=runtime.agent_runtime_arn)
39:            "AgentRuntimeArnParam",
```

All three expected patterns found. Writer (AgentCoreStack) and reader (BackendApiStack) are both in place. CfnOutput for ARN capture in Plan 05-02 is present.

### Task 3 — Fresh-clone dry run

| Step | Command | Result |
|------|---------|--------|
| UI install | `rm -rf ui/node_modules && npm ci --prefix ui` | exit 0 — "added 331 packages, and audited 332 packages in 6s" |
| Python install | fresh `.venv-phase5` + `pip install -r requirements.txt -r requirements-dev.txt` | exit 0 (no ERROR lines; pip-version warning only) |
| CDK synth | `AWS_DEFAULT_REGION=us-east-1 npx aws-cdk@latest synth --all --quiet` | exit 0 — `cdk.out/{CustomerTariff,CustomerTariffAgent,CustomerTariffApi}.template.json` emitted |
| Pytest | `pytest tests/ -m "not smoke" -x -q` | exit 0 — **81 passed, 6 skipped, 23 deselected** (after gap fix below) |
| CDK version | `npx aws-cdk@latest --version > /tmp/phase5-cdk-version.txt` | `2.1119.0 (build 820ac02)` |

### Captured toolchain versions (for Plan 05-07 Environment Lock)

| Tool | Version |
|------|---------|
| Node | v24.12.0 |
| Python | 3.9.6 |
| CDK CLI | 2.1119.0 (build 820ac02) |

## Gap found and closed

**Gap:** `tests/test_backend_api_smoke.py:9` imports `requests` at module level. Even though its tests carry `pytest.mark.smoke` + `skipif(not BACKEND_API_URL)`, pytest must import the module during collection, so a fresh venv fails with `ModuleNotFoundError: No module named 'requests'`.

`requests` was not declared in `requirements.txt` or `requirements-dev.txt` — added in Phase 3 as an implicit/ambient dep.

**Fix:** Added `requests>=2.28,<3` to `requirements-dev.txt` and re-ran pytest. Result: 81 passed, 6 skipped, 23 deselected.

**Commits:**
- `ae627cd fix(05-01): add requests to dev requirements`
- `f277ea3 docs(phase-05): commit phase 5 planning artifacts` (pre-existing plan files committed alongside)

This is exactly the class of issue Plan 05-01 Task 3 exists to catch before `cdk deploy`.

## Self-Check: PASSED

- [x] User approved the Claude-model-access blocker
- [x] SSM wiring grep patterns present in both stacks
- [x] `npm ci` exits 0 from a clean `ui/node_modules`
- [x] Fresh-venv `pip install -r requirements.txt -r requirements-dev.txt` exits 0
- [x] `cdk synth --all` exits 0 with all 3 templates rendered
- [x] `pytest tests/ -m "not smoke"` exits 0 (81 passed, 0 failures)
- [x] CDK CLI version captured
- [x] No lockfile mutation in `package-lock.json`, `requirements.txt`
- [x] `requirements-dev.txt` updated deliberately (gap closure) and committed

## Key files

### Created
- `.planning/phases/05-demo-hardening/05-01-SUMMARY.md` — this file

### Modified
- `requirements-dev.txt` — added `requests>=2.28,<3`

### Verified (not modified)
- `infrastructure/agentcore_stack.py` — SSM writer
- `infrastructure/backend_api_stack.py` — SSM reader
- `app.py` — 3-stack registration
- `cdk.json` — CDK toolkit config
- `ui/package.json` / `ui/package-lock.json` — clean `npm ci` baseline
- `requirements.txt` — unmodified

## What this unblocks

Plan 05-02 (live deploy) can now run `cdk deploy --all` against us-east-1 with:
- Bedrock model access confirmed granted (no surprise runtime failure on first agent invoke)
- Cross-stack SSM wiring verified present (no CloudFormation export/import errors)
- Offline toolchain green (deploy failures will be environmental, not source/toolchain)

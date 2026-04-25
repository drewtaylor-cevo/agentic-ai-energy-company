---
phase: 2
slug: agentcore-agent
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-04-23
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=7.0 (already installed) |
| **Config file** | `pytest.ini` (exists, `testpaths = tests`) |
| **Quick run command** | `pytest tests/test_agent_tools.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds (offline); ~60–120 seconds (with smoke tests) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_agent_tools.py -x`
- **After every plan wave:** Run `pytest tests/ -x -m "not smoke"`
- **Before `/gsd-verify-work`:** Full suite must be green including `pytest tests/test_agent_smoke.py -x`
- **Max feedback latency:** 10 seconds (offline), 120 seconds (with smoke)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 0 | REC-01, REC-02, REC-03 | T-02-01 | Tool docstring prevents LLM arithmetic | unit (mocked) | `pytest tests/test_agent_tools.py::test_both_tracks_present -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 0 | SAV-01, SAV-02, SAV-03 | — | Numbers pass through from tool unchanged | unit (mocked) | `pytest tests/test_agent_tools.py::test_numbers_from_tool_not_llm -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | REC-01, REC-02 | T-02-02 | IAM scoped to ToolsLambda ARN only | unit (mocked) | `pytest tests/test_agent_tools.py::test_green_track_present -x` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | REC-03 | — | Both tracks simultaneously returned | unit (mocked) | `pytest tests/test_agent_tools.py::test_cheapest_track_present -x` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 2 | SAV-01, SAV-02 | — | Monthly saving > 0, annual = monthly * 12 | unit (mocked) | `pytest tests/test_agent_tools.py::test_monthly_saving_nonzero -x` | ❌ W0 | ⬜ pending |
| 02-04-01 | 04 | 3 | REC-01..03, SAV-01..03 | T-02-07 | `bedrock-agentcore:InvokeAgentRuntime` on caller | integration (live) | `pytest tests/test_agent_smoke.py -x -m smoke` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_agent_tools.py` — offline unit tests with mocked boto3 Lambda client; stubs for REC-01, REC-02, REC-03, SAV-01, SAV-02, SAV-03
- [ ] `tests/test_agent_smoke.py` — live `invoke_agent_runtime` per persona (CUST-001, CUST-002, CUST-003); marked `@pytest.mark.smoke`; requires `AGENT_RUNTIME_ARN` env var
- [ ] `tests/conftest.py` addition — `agent_runtime_arn` fixture reading `AGENT_RUNTIME_ARN` env var; `mock_savings_response` fixture with canonical response shape
- [ ] `pytest.ini` addition — register `smoke` marker: `markers = smoke: live AWS smoke tests (requires AWS credentials)`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Cheapest saving >= green saving for all 3 personas (live) | SC-4 | Requires deployed runtime + live AWS credentials | After `cdk deploy AgentCoreStack`, run `pytest tests/test_agent_smoke.py -x -m smoke` with `AGENT_RUNTIME_ARN` set; inspect output for all three personas |
| Container `linux/arm64` architecture | — | CDK build step — not verifiable in pytest | Run `docker inspect <image> --format '{{.Architecture}}'` after `cdk synth` builds the image locally |
| AgentCore runtime status `ACTIVE` | — | CloudFormation output / console | Run `aws bedrock-agentcore list-agent-runtimes --region us-east-1` and confirm status is `ACTIVE` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 10s (offline tasks)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready

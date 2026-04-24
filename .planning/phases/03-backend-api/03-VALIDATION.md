---
phase: 3
slug: backend-api
status: ready
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-24
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini |
| **Quick run command** | `pytest -m "not smoke" tests/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds (offline only; smoke requires deployed stack) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -m "not smoke" tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v` (offline); run smoke suite after Wave 3 deploy completes
- **Before `/gsd-verify-work`:** Full offline suite green AND smoke suite green against deployed stack (smoke deferred to Phase 5)
- **Max feedback latency:** 30 seconds (offline)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 1.1 | 01 | 1 | DEMO-01 / SC-2 | T-03-01 | Input regex fast-fail | static | `grep -c "_CUSTOMER_ID_PATTERN = re.compile" api_lambda/handler.py` == 1 | ✅ | ✅ green |
| 1.3/valid | 01 | 1 | DEMO-01 / SC-1 | — | Pass-through contract (D-02) | unit | `pytest tests/test_backend_api_handler.py::test_valid_customer_returns_200_and_passes_through_body -x -q` | ✅ | ✅ green |
| 1.3/badfmt | 01 | 1 | DEMO-01 / SC-2, D-13 | T-03-01 | 400 on bad regex | unit (parametrized ×5) | `pytest tests/test_backend_api_handler.py::test_invalid_customer_id_returns_400 -x -q` | ✅ | ✅ green |
| 1.3/404-green | 01 | 1 | DEMO-01 / SC-2 | — | 404 on missing green (Pitfall 5) | unit | `pytest tests/test_backend_api_handler.py::test_missing_green_returns_404 -x -q` | ✅ | ✅ green |
| 1.3/404-cheapest | 01 | 1 | DEMO-01 / SC-2 | — | 404 on missing cheapest | unit | `pytest tests/test_backend_api_handler.py::test_missing_cheapest_returns_404 -x -q` | ✅ | ✅ green |
| 1.3/504 | 01 | 1 | DEMO-01 / SC-2 | T-03-03 | 504 on ReadTimeoutError | unit | `pytest tests/test_backend_api_handler.py::test_timeout_returns_504 -x -q` | ✅ | ✅ green |
| 1.3/502 | 01 | 1 | DEMO-01 / SC-2 | — | 502 on ClientError | unit | `pytest tests/test_backend_api_handler.py::test_client_error_returns_502 -x -q` | ✅ | ✅ green |
| 1.3/500 | 01 | 1 | DEMO-01 / SC-2 | T-03-04 | 500 on unknown Exception | unit | `pytest tests/test_backend_api_handler.py::test_unexpected_error_returns_500 -x -q` | ✅ | ✅ green |
| 1.3/session | 01 | 1 | DEMO-01 / SC-3, D-11 | T-03-02 | Fresh uuid4 per invocation | unit | `pytest tests/test_backend_api_handler.py::test_fresh_session_id_per_call -x -q` | ✅ | ✅ green |
| 2.4/synth | 02 | 2 | DEMO-01 | — | Stack synthesises | synth | `pytest tests/test_backend_api_synth.py::test_stack_synthesises -x -q` | ✅ | ✅ green |
| 2.4/httpapi | 02 | 2 | DEMO-01 | — | HttpApi resource count | synth | `pytest tests/test_backend_api_synth.py::test_has_http_api -x -q` | ✅ | ✅ green |
| 2.4/lambda | 02 | 2 | DEMO-01 | — | Lambda resource count | synth | `pytest tests/test_backend_api_synth.py::test_has_lambda -x -q` | ✅ | ✅ green |
| 2.4/route | 02 | 2 | DEMO-01 / D-10 | — | Route GET /recommendations/{customer_id} | synth | `pytest tests/test_backend_api_synth.py::test_has_route -x -q` | ✅ | ✅ green |
| 2.4/lambda-props | 02 | 2 | DEMO-01 / D-03 | — | Lambda runtime=python3.12, handler=handler.handler, 256MB | synth | `pytest tests/test_backend_api_synth.py::test_lambda_runtime_and_handler -x -q` | ✅ | ✅ green |
| 2.4/lambda-timeout | 02 | 2 | DEMO-01 / D-03 | — | Timeout=30s | synth | `pytest tests/test_backend_api_synth.py::test_lambda_timeout -x -q` | ✅ | ✅ green |
| 2.4/cors-origins | 02 | 2 | DEMO-01 / D-09 | T-03-05 | CORS AllowOrigins=["*"] | synth | `pytest tests/test_backend_api_synth.py::test_cors_allow_all -x -q` | ✅ | ✅ green |
| 2.4/cors-methods | 02 | 2 | DEMO-01 / D-09 | T-03-05 | CORS AllowMethods includes GET, OPTIONS | synth | `pytest tests/test_backend_api_synth.py::test_cors_methods -x -q` | ✅ | ✅ green |
| 2.4/cors-headers | 02 | 2 | DEMO-01 / D-09 | T-03-05 | CORS AllowHeaders includes Content-Type | synth | `pytest tests/test_backend_api_synth.py::test_cors_headers -x -q` | ✅ | ✅ green |
| 2.4/iam | 02 | 2 | DEMO-01 | T-03-06 | IAM scoped to InvokeAgentRuntime, no wildcard | synth | `pytest tests/test_backend_api_synth.py::test_has_iam_policy_with_invoke_agent_runtime -x -q` | ✅ | ✅ green |
| 2.4/ssm | 02 | 2 | DEMO-01 | — | AgentCoreStack SSM write (D-07) | synth | `pytest tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter -x -q` | ✅ | ✅ green |
| 3.1/personas | 03 | 3 | DEMO-01 / SC-1 | — | Live 3-persona recommendations | smoke | `BACKEND_API_URL=<url> pytest tests/test_backend_api_smoke.py::test_all_personas_return_recommendations -x -q` | ✅ | ⬜ pending (deploy deferred) |
| 3.1/400 | 03 | 3 | DEMO-01 / SC-2 | T-03-01 | Live 400 on bad ID | smoke | `BACKEND_API_URL=<url> pytest tests/test_backend_api_smoke.py::test_invalid_format_returns_400 -x -q` | ✅ | ⬜ pending (deploy deferred) |
| 3.1/404 | 03 | 3 | DEMO-01 / SC-2 | — | Live 404 on unknown customer | smoke | `BACKEND_API_URL=<url> pytest tests/test_backend_api_smoke.py::test_unknown_customer_returns_404 -x -q` | ✅ | ⬜ pending (deploy deferred) |
| 3.1/bleed | 03 | 3 | DEMO-01 / SC-3 | T-03-02 | No session bleed live | smoke | `BACKEND_API_URL=<url> pytest tests/test_backend_api_smoke.py::test_fresh_session_no_bleed -x -q` | ✅ | ⬜ pending (deploy deferred) |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_backend_api_handler.py` — unit tests for DEMO-01 (handler pass-through, customer_id validation, error taxonomy, fresh session)
- [x] `tests/test_backend_api_synth.py` — CDK synth assertions for `BackendApiStack` + AgentCoreStack SSM amendment
- [x] `tests/test_backend_api_smoke.py` — `@pytest.mark.smoke` live suite (deferred run; file ready)
- [x] `tests/conftest.py` extended with `mock_agent_invoke_response`, `mock_agent_invoke_not_found`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| curl/Postman returns recommendations for all 3 personas | DEMO-01 SC-1 | Live deployed-endpoint verification; literal roadmap text | After deploy: `curl $BACKEND_API_URL/recommendations/CUST-001` for 001/002/003, eyeball `{green, cheapest}` body |
| Call-centre-friendly error messages | DEMO-01 SC-2 | Subjective UX tone check | Trigger 400 (`CUST-abc`), 404 (`CUST-999`), confirm body text is readable, not a stack trace |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s (offline quick run ~10s)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** offline scope approved; live smoke run deferred to Phase 5 demo hardening per 03-03-SUMMARY.md

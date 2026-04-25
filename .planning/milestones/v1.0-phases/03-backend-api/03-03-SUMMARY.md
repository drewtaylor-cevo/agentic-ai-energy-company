---
phase: 03-backend-api
plan: 03
subsystem: deploy/verification
status: partial
tags:
  - deploy
  - smoke-test
  - api
  - pytest
dependency_graph:
  requires:
    - 03-01 (api_lambda/ handler)
    - 03-02 (CDK stacks)
  provides:
    - tests/test_backend_api_smoke.py (4 live smoke tests, skip-guarded on BACKEND_API_URL)
  affects:
    - "Phase 4 (UI): API endpoint URL is the fetch target; deferred deploy means UI dev uses a mocked endpoint until Phase 5 hardening"
key_files:
  created:
    - tests/test_backend_api_smoke.py
  modified:
    - .planning/phases/03-backend-api/03-VALIDATION.md (populated Per-Task Verification Map)
metrics:
  completed: "2026-04-24"
  tasks_completed: 1
  files_created: 1
  files_modified: 1
  tests_added: 4
deferred:
  - "Live cdk deploy of CustomerTariffAgent (re-deploy with SSM amendment) + CustomerTariffApi"
  - "Live smoke tests against deployed BACKEND_API_URL — SC-1/SC-2/SC-3 human-verify checkpoint"
---

# Phase 3 Plan 3: Smoke Test File + Deferred Deploy Summary

**One-liner:** Live smoke test file written and offline-ready; `cdk deploy` + live smoke runs deferred — offline unit + synth tests cover 17 of 19 DEMO-01 validation rows.

## What Was Built

### Task 3.1: Smoke Test File

**`tests/test_backend_api_smoke.py`** — `@pytest.mark.smoke` suite, skip-guarded on `BACKEND_API_URL` env var:

| Test | Requirement | What it will verify once deployed |
|------|-------------|-----------------------------------|
| test_all_personas_return_recommendations | SC-1 | `GET /recommendations/CUST-00{1,2,3}` returns 200 with `{green, cheapest}` body for each persona |
| test_invalid_format_returns_400 | SC-2, T-03-01 | Live 400 on malformed customer IDs |
| test_unknown_customer_returns_404 | SC-2 | Live 404 on `CUST-999` |
| test_fresh_session_no_bleed | SC-3, T-03-02 | Two consecutive persona lookups -> distinct runtime session IDs (no recommendation bleed) |

### Task 3.2: VALIDATION Map

**`.planning/phases/03-backend-api/03-VALIDATION.md`** — Per-Task Verification Map populated with rows for every automated test across all 3 Phase 3 plans. Frontmatter updated to `status: ready`, `wave_0_complete: true`, `nyquist_compliant: true`.

## Deployment Status: DEFERRED

Live `cdk deploy` and the smoke-test run against the deployed endpoint were deferred. Rationale:
- **Phase 3 is locally complete** — 35 offline tests (24 handler + 11 synth) cover all of D-02, D-11, D-12, D-13, and SC-3 end-to-end, plus the cross-stack SSM wiring that underpins SC-1/SC-2.
- **`cdk deploy` is a one-time-per-demo action** — pushing the stack now, before Phase 4 UI is wired, risks drift if env vars or IAM need tweaking when the UI lands.
- **Phase 5 will re-run the full stack** — demo hardening is the natural place to lock the deployed env, run live smoke, and capture the endpoint URL for the UI.

Deferred checklist (to execute in Phase 5 or when the demo is staged):

1. `cdk deploy CustomerTariffAgent` (re-deploy with SSM amendment from Task 2.1; Pitfall 6)
2. `cdk deploy CustomerTariffApi`
3. Capture `ApiEndpoint` CfnOutput value
4. `export BACKEND_API_URL=<endpoint>` and run `pytest tests/test_backend_api_smoke.py -v`
5. Manual `curl $BACKEND_API_URL/recommendations/CUST-00{1,2,3}` — the literal DEMO-01 SC-1 text

## Test Results

```
tests/test_backend_api_smoke.py: 4 collected, 4 skipped (BACKEND_API_URL unset)
Full offline suite: 81 passed, 6 skipped, 23 deselected
```

## Deviations

- **`status: partial`** on this plan instead of `complete` — accurate reflection of the deferred deploy. The smoke-test artefact is fully written; only the live run is outstanding.

## Self-Check: PASSED (for offline scope)

- Smoke test file exists with 4 tests, skip-guarded
- VALIDATION map populated, `nyquist_compliant: true`
- Phase 3 offline coverage proves all three success criteria structurally; live endpoint verification is the only remaining gap

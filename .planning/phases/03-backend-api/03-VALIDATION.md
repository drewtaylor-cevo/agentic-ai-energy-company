---
phase: 3
slug: backend-api
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| **Estimated runtime** | ~30 seconds (offline only; smoke requires deployed stack) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -m "not smoke" tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v` (offline); run smoke suite after Wave N (deploy) completes
- **Before `/gsd-verify-work`:** Full offline suite green AND smoke suite green against deployed stack
- **Max feedback latency:** 30 seconds (offline)

---

## Per-Task Verification Map

*To be populated by planner — each PLAN.md task should map to a row here with its automated command. Plan-checker will enforce Dimension 8 coverage.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | DEMO-01 | — | N/A | — | — | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_backend_api_handler.py` — unit stubs for DEMO-01 (handler returns pass-through, validates customer_id, maps errors per D-12, fresh session ID per invocation)
- [ ] `tests/test_backend_api_synth.py` — CDK synth snapshot stubs for `BackendApiStack` (mirrors tests/test_agentcore_synth.py)
- [ ] `tests/test_backend_api_smoke.py` — `@pytest.mark.smoke` stubs hitting `GET /recommendations/{customer_id}` for all 3 demo personas (CUST-001, CUST-002, CUST-003), plus 400/404/504 negative cases
- [ ] Extend `tests/conftest.py` — fixture for mocked `bedrock-agentcore` client and session-id capture helper

*pytest already installed — no framework bootstrap needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| curl/Postman returns recommendations for all 3 personas | DEMO-01 SC-1 | Live deployed-endpoint verification; also covered by automated smoke test, but manual curl is the literal success criterion | After deploy, run `curl $ENDPOINT/recommendations/CUST-001` for 001/002/003 and eyeball the `{green, cheapest}` body |
| Call-centre-friendly error messages | DEMO-01 SC-2 | Subjective UX check — message tone "customer-friendly" vs raw stack trace | Trigger 400 (`CUST-abc`), 404 (`CUST-999`), and observe error body text is readable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (offline quick run)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

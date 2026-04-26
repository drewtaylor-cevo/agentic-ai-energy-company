---
phase: 7
slug: api-pass-through-pre-warm-route
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-25
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `pytest tests/test_backend_api_handler.py -q` |
| **Full suite command** | `pytest -m "not smoke" -q` |
| **Estimated runtime** | ~15 seconds (handler tests) / ~45 seconds (full offline suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_backend_api_handler.py tests/test_backend_api_synth.py -q`
- **After every plan wave:** Run `pytest -m "not smoke" -q`
- **Before `/gsd-verify-work`:** Full suite must be green + D-15 live-smoke gate passes
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-T1 | 01 | 1 | DEMO-03 | — | Marker-strip before response dump + prewarm branch never returns 5xx | tdd (unit) | `pytest tests/test_backend_api_handler.py -q` | ✅ | ⬜ pending |
| 07-01-T2 | 01 | 1 | DEMO-03 | — | 6 D-13 pytest functions exercise pass-through + prewarm branches | tdd (unit) | `pytest tests/test_backend_api_handler.py -q` | ✅ | ⬜ pending |
| 07-02-T1 | 02 | 1 | DEMO-03 | — | Alias `live` always created; PC attached only when `demo_pc>0`; integration targets alias | tdd (unit + synth) | `python3 -c "from infrastructure.backend_api_stack import BackendApiStack" && pytest tests/test_backend_api_synth.py -q` | ✅ | ⬜ pending |
| 07-02-T2 | 02 | 1 | DEMO-03 | — | 4 D-14 synth assertions verify alias + PC + integration wiring under both `demo_pc=0` and `demo_pc=1` contexts | tdd (unit) | `pytest tests/test_backend_api_synth.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] No Wave 0 tasks needed — existing test infrastructure (`tests/test_backend_api_handler.py`, `tests/test_backend_api_synth.py`, `tests/test_backend_api_smoke.py`) and conftest fixtures cover all Phase 7 requirements per RESEARCH.md.

*Existing infrastructure covers all phase requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| D-15 live-smoke: `?prewarm=1` per persona → 204; 3 warm lookups per persona median <3000ms | DEMO-03 / SC-2 / SC-4 (UI-02) | Requires live `cdk deploy` + ≥3 min PC warm-up + multi-invocation `curl -w "%{time_total}"` timing; expressing as pytest would tempt mocked replacement and lose the real-latency signal | See Phase 7 runbook (D-15): 1) `cdk deploy -c demo_pc=1 BackendApiStack` 2) wait ≥3 min for PC Status=READY 3) curl `?prewarm=1` for CUST-001/002/003 → assert all 204 4) 3× warm lookups per persona with `-w "%{time_total}"` → median <3000ms 5) CloudWatch tail confirms `narrative_source` log present + `prewarm_failed` absent 6) Response body per persona has `usage_narrative`+`call_script` on both tracks; `_narrative_source` absent |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (none required)
- [x] No watch-mode flags
- [x] Feedback latency < 45s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-25

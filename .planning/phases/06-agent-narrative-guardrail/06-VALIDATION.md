---
phase: 6
slug: agent-narrative-guardrail
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-25
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from 06-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest>=7.0` + `pytest-mock>=3.0` (already in `requirements-dev.txt`) |
| **Config file** | None currently — Wave 0 may add `pytest.ini` if `filterwarnings` entry for Strands deprecation is wanted |
| **Quick run command** | `pytest -m "not smoke" -x tests/test_narrative_validator.py tests/test_fallbacks_pass_validator.py tests/test_shape_tokens.py tests/test_agent_narrative.py` |
| **Full suite command** | `pytest -m "not smoke"` (offline) and `AGENT_RUNTIME_ARN=<arn> AWS_DEFAULT_REGION=us-east-1 pytest -v` (full incl. smoke) |
| **Estimated runtime** | Offline ~15s; smoke ~90s (depends on warm/cold runtime) |

---

## Sampling Rate

- **After every task commit:** Run quick command above
- **After every plan wave:** Run `pytest -m "not smoke"` full offline suite (confirms v1.0 regression tests remain green — 81 passed at v1.0 close)
- **Before `/gsd-verify-work`:** Offline suite green + live smoke on ALL 3 personas + sample capture to `06-SAMPLES.md`
- **Max feedback latency:** 15s (offline) / 90s (smoke)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD-01 | TBD | 1 | UI-05 | T-6-01 (banned-terms bypass) | digits rejected | unit | `pytest tests/test_narrative_validator.py::test_digits_rejected -x` | ❌ W0 | ⬜ pending |
| TBD-02 | TBD | 1 | UI-05 | T-6-01 | currency rejected | unit | `pytest tests/test_narrative_validator.py::test_currency_symbols_rejected -x` | ❌ W0 | ⬜ pending |
| TBD-03 | TBD | 1 | UI-05 | T-6-01 | competitors rejected | unit | `pytest tests/test_narrative_validator.py::test_competitors_rejected -x` | ❌ W0 | ⬜ pending |
| TBD-04 | TBD | 1 | UI-05 | T-6-01 | switch verbs rejected | unit | `pytest tests/test_narrative_validator.py::test_switch_verbs_rejected -x` | ❌ W0 | ⬜ pending |
| TBD-05 | TBD | 1 | UI-05 | T-6-01 | env superlatives rejected | unit | `pytest tests/test_narrative_validator.py::test_env_superlatives_rejected -x` | ❌ W0 | ⬜ pending |
| TBD-06 | TBD | 1 | UI-05 | — | word cap enforced | unit | `pytest tests/test_narrative_validator.py::test_word_cap_enforced -x` | ❌ W0 | ⬜ pending |
| TBD-07 | TBD | 1 | UI-05 | — | char cap enforced | unit | `pytest tests/test_narrative_validator.py::test_char_cap_enforced -x` | ❌ W0 | ⬜ pending |
| TBD-08 | TBD | 1 | UI-05 | — | clean narratives accepted | unit | `pytest tests/test_narrative_validator.py::test_positive_cases_accepted -x` | ❌ W0 | ⬜ pending |
| TBD-09 | TBD | 1 | UI-05 | T-6-02 (fallback integrity) | FALLBACKS self-pass | unit | `pytest tests/test_fallbacks_pass_validator.py -x` | ❌ W0 | ⬜ pending |
| TBD-10 | TBD | 2 | UI-03/UI-04 | — | retry-once-then-per-field-fallback | unit (mocked) | `pytest tests/test_agent_narrative.py::test_retry_once_then_fallback -x` | ❌ W0 | ⬜ pending |
| TBD-11 | TBD | 2 | UI-03/UI-04 | — | `_narrative_source` marker present | unit (mocked) | `pytest tests/test_agent_narrative.py::test_narrative_source_marker -x` | ❌ W0 | ⬜ pending |
| TBD-12 | TBD | 1 | UI-03/UI-04 | T-6-03 (structural no-numerics) | shape-tokens no numerics | unit | `pytest tests/test_shape_tokens.py::test_no_numerics_any_persona -x` | ❌ W0 | ⬜ pending |
| TBD-13 | TBD | 1 | UI-03/UI-04 | — | shape-token vocabulary whitelist | unit | `pytest tests/test_shape_tokens.py::test_vocabulary_whitelist -x` | ❌ W0 | ⬜ pending |
| TBD-14 | TBD | 3 | UI-03 + UI-04 + crit-5 | — | live-deployed smoke on 3 personas × 2 cards | smoke | `AGENT_RUNTIME_ARN=... pytest tests/test_agent_smoke.py::test_narrative_fields_present_and_valid -v` | ✅ (extend) | ⬜ pending |
| TBD-15 | TBD | 3 | crit-5 (no regression) | — | v1.0 DEMO-02 $30/$55 deltas unchanged | smoke | `AGENT_RUNTIME_ARN=... pytest tests/test_agent_smoke.py::test_sarah_flagship_values` | ✅ existing | ⬜ pending |
| TBD-16 | TBD | 2 | crit-4 (corpus) | — | 10x × 3 personas × 2 cards no numerics | offline integration | `pytest tests/test_agent_narrative_corpus.py::test_corpus_10x_no_numerics -x` | ❌ W0 | ⬜ pending |

*Task IDs bound to plans after planner emits PLAN.md frontmatter — checker enforces binding.*
*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_narrative_validator.py` — covers UI-05 (~39 test cases across banned categories, caps, positive)
- [ ] `tests/test_fallbacks_pass_validator.py` — covers fallbacks-must-themselves-pass invariant (CONTEXT D-04, D-06)
- [ ] `tests/test_shape_tokens.py` — covers shape-token no-numerics invariant + vocabulary whitelist
- [ ] `tests/test_agent_narrative.py` — covers retry-once-then-per-field-fallback (mocked `structured_output`) + `_narrative_source` marker
- [ ] `tests/test_agent_narrative_corpus.py` — covers roadmap success criterion 4 (offline, mocked randomised LLM outputs)
- [ ] `tests/test_agent_smoke.py` — extend with parametrised `test_narrative_fields_present_and_valid`
- [ ] `tests/conftest.py` — add `mock_trackinfo`, `clean_narrative_sample`, `poisoned_narrative_samples` fixtures
- [ ] Framework install: none — `pytest` already present in `requirements-dev.txt`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fallback string prose quality (demo-ready copy) | UI-03/UI-04 D-06 | Subjective — voice/persona alignment judged by human reviewer in PR diff | Reviewer opens PR, reads each of 6 FALLBACKS strings against persona profile in `infrastructure/seed_data/billing_records.py`, confirms tone matches ("strong winter-heating profile" fits Sarah, "budget-first tilt" fits Marcus, "eco-aligned household" fits Elena) |
| CloudWatch log visibility on AgentCore runtime | D-03 / research Open Q1 | Runtime log-format unverified for AgentCore (MEDIUM confidence — docs cover Lambda only) | During live smoke, tail CloudWatch Log Group for the AgentCore runtime, trigger a fallback by mocking-then-restoring the validator bypass path, confirm `narrative_fallback_fired` key surfaces in CloudWatch Insights. If absent → switch to `print(json.dumps({...}))` fallback pattern documented in research Open Q1 |
| Post-deploy sample capture for design review | success-crit 5 traceability | Visual review of model output against persona voice | After live smoke, capture one successful `invoke_agent_runtime` output per persona × card (6 samples) into `06-SAMPLES.md` for design review |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (7 files + fixture extension)
- [ ] No watch-mode flags (offline suite uses `-x` fail-fast, not `--watch`)
- [ ] Feedback latency < 90s (smoke) / 15s (offline)
- [ ] `nyquist_compliant: true` set in frontmatter after planner binds task IDs and checker verifies coverage

**Approval:** pending

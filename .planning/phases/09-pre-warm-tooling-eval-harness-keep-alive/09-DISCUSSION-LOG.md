# Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 09-pre-warm-tooling-eval-harness-keep-alive
**Areas discussed:** Prewarm script shape, Eval harness shape, Keep-alive shape, Offline tests + closeout gate

---

## Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| Prewarm script shape | Python vs shell for scripts/prewarm.py; stdlib urllib vs requests; per-call latency print; ≥3000ms gate triggers non-zero exit | ✓ |
| Eval harness shape | Pytest under tests/ vs standalone script; live-API vs dual-path; iteration count; reuse validator vs duplicate | ✓ |
| Keep-alive shape | Bash vs Python; which URL to ping; foreground tmux vs nohup; log format + shutdown behaviour | ✓ |
| Offline tests + closeout gate | Offline pytest for scripts vs live-smoke only; D-15-style documented gate in SUMMARY | ✓ |

**User's choice:** All four areas selected.

---

## Prewarm Script Shape

### Language / deps

| Option | Description | Selected |
|--------|-------------|----------|
| Python stdlib urllib | Zero new deps. urllib.request + time.perf_counter. Minimizes freeze surface. | ✓ |
| Python + requests | requests already in requirements-dev.txt. Cleaner but pins a 'dev' package. | |
| Pure bash + curl | Matches curl -f wording, but bash median is painful and ROADMAP says scripts/prewarm.py. | |

**User's choice:** Python stdlib urllib (Recommended).

### End-to-end flow

| Option | Description | Selected |
|--------|-------------|----------|
| Prewarm × 3 → wait → time 3 lookups × 3 personas = 9 timed calls | Two-pass flow; computes per-persona median; exit non-zero on ≥3000ms. Matches SC-1/SC-2. | ✓ |
| Prewarm × 3 only; no measurement pass | Simpler; but SC-2 requires measurement-based exit-code gate. | |
| Prewarm × 3 + single-lookup per persona | Faster (6 calls total); single-sample median is fragile. | |

**User's choice:** Two-pass flow with 9 timed measurement calls (Recommended).

### Gate threshold

| Option | Description | Selected |
|--------|-------------|----------|
| <3000ms per persona | Matches SC-2 + UI-02 + Phase 7 D-15. | ✓ |
| <2500ms on CUST-001 + <3000ms others | Phase 7 CONTEXT hint; tighter but network-variance-sensitive. | |
| <3000ms median + <3500ms hard limit | Two-tier; more nuance, more runbook complexity. | |

**User's choice:** <3000ms per persona (Recommended).

### Per-call log format

| Option | Description | Selected |
|--------|-------------|----------|
| One-line-per-call plain stdout + summary | Human-readable, grep-able, zero deps. Matches capture_samples.py style. | ✓ |
| Structured JSON logs | Machine-parseable but overkill for single-shot tool. | |
| Quiet by default + --verbose flag | Hides info; SC-1 requires per-call latency flatly. | |

**User's choice:** One-line-per-call plain stdout + summary block (Recommended).

### API URL source

| Option | Description | Selected |
|--------|-------------|----------|
| BACKEND_API_URL env var | Matches tests/test_backend_api_smoke.py convention. | ✓ |
| Positional arg + --url flag | Self-documenting but duplicates env-var pattern. | |
| Hard-coded with --url override | Zero-arg invocation; freeze-surface risk if endpoint changes. | |

**User's choice:** BACKEND_API_URL env var (Recommended).

### Wait between passes

| Option | Description | Selected |
|--------|-------------|----------|
| 30 seconds | ARCHITECTURE Phase 2.4 checkpoint. MicroVM pool settle time. | ✓ |
| Zero wait | Noisy; the same microVM may still be busy with the prewarm session. | |
| Configurable --wait (default 30s) | Flexibility; adds a knob with no clear use case. | |

**User's choice:** 30 seconds (Recommended).

### Exit-code taxonomy

| Option | Description | Selected |
|--------|-------------|----------|
| 0=pass / 1=gate-fail / 2=setup-error | Classic shell convention; separates env broken from demo broken. | ✓ |
| 0=pass / non-zero=any-failure | Simpler; blurs triage semantics. | |

**User's choice:** Three-way 0/1/2 taxonomy (Recommended).

### npm wrapper

| Option | Description | Selected |
|--------|-------------|----------|
| ui/package.json script | 'cd .. && python3 scripts/prewarm.py' inside existing scripts block. | ✓ |
| Root package.json with scripts/ | Second package.json = more freeze surface. | |
| No npm wrapper | ROADMAP SC-1 explicitly says 'npm run prewarm'. | |

**User's choice:** ui/package.json script (Recommended).

**Checkpoint:** User chose "Next area" when offered more prewarm questions.

---

## Eval Harness Shape

### Home

| Option | Description | Selected |
|--------|-------------|----------|
| tests/test_narrative_eval_live.py with @pytest.mark.smoke | Byte-for-byte match to test_backend_api_smoke.py pattern. Validator rules from agent.narrative. | ✓ |
| scripts/eval_narrative.py standalone | More presenter-friendly; duplicates validator or re-imports agent.narrative awkwardly. | |
| Both — pytest + scripts/ wrapper | Satisfies both audiences; adds shell-out layer. | |

**User's choice:** Pytest under tests/ (Recommended).

### Eval source

| Option | Description | Selected |
|--------|-------------|----------|
| Live API only | Matches SC-4 'driven through the live endpoint'. _narrative_source stripped by Phase 7. | ✓ |
| Live API + AgentCore direct | Richer (model/fallback visibility); heavier (needs AWS creds). | |
| AgentCore direct only | Misses API Lambda contract. Reject. | |

**User's choice:** Live API only (Recommended).

### Iteration count

| Option | Description | Selected |
|--------|-------------|----------|
| 1 invocation per persona × card | 3 calls × 12 assertions. Fast. Variance is T-24h rehearsal's job. | ✓ |
| 10 invocations per persona | 30 calls ~60s runtime; catches intermittent variance. | |
| 3 invocations per persona | Middle ground. | |

**User's choice:** 1 invocation per persona × card (Recommended).

### Validator reuse

| Option | Description | Selected |
|--------|-------------|----------|
| Import agent.narrative directly | Single source of truth; catches Phase 6 drift. | ✓ |
| Full Pydantic TrackInfo model | Requires unrelated fields; more fragile. | |
| Duplicate regex in test file | Drift risk. Reject. | |

**User's choice:** Import agent.narrative directly (Recommended).

### Harness scope

| Option | Description | Selected |
|--------|-------------|----------|
| Validator + presence + track coverage (12 assertions) | Narrative + call_script on both tracks pass validator; _narrative_source absent. | ✓ |
| Also assert DEMO-02 savings byte-exact | Duplication with Phase 1 pytest + smoke suite. | |
| Also check CloudWatch narrative_source log | AWS creds + pagination complexity; scope-cut. | |

**User's choice:** Validator + presence + track coverage (Recommended).

### Run trigger

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit before phase close + T-24h / T-10m / T-48h | Runbook-invokable. Orthogonal to prewarm. | ✓ |
| Chained from prewarm --then-eval | Couples concerns; prewarm and eval should run independently. | |
| CI cron / GitHub Actions | Single-shot demo; adds freeze surface. Reject. | |

**User's choice:** Explicit runbook trigger (Recommended).

### Report format

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest default + per-assertion failure message | Zero new reporting code. | ✓ |
| Write out 09-EVAL-SAMPLES.md on success | capture_samples.py already covers. Duplication. | |
| Both — pytest + optional --capture flag | More code for marginal value. | |

**User's choice:** Pytest default output (Recommended).

**Checkpoint:** User chose "Next area" when offered more eval questions.

---

## Keep-Alive Shape

### Language/shape

| Option | Description | Selected |
|--------|-------------|----------|
| Pure bash while-loop + trap | ~30 lines; zero deps; .sh extension matches ROADMAP naming. | ✓ |
| Python with signal handler | Cleaner; but bash-file-shelling-python adds indirection. | |
| systemd timer / launchd plist | Overkill for 90-minute tmux-pane use case. | |

**User's choice:** Pure bash while-loop + trap (Recommended).

### Ping URL

| Option | Description | Selected |
|--------|-------------|----------|
| ?prewarm=1 per rotating persona | Warms microVM pool depth end-to-end. | ✓ |
| ?prewarm=1 on CUST-001 only | Warms only one microVM slot. | |
| Lighter GET / or /health | Doesn't warm AgentCore. Reject. | |

**User's choice:** Rotating ?prewarm=1 across personas (Recommended).

### Tick cadence + duration

| Option | Description | Selected |
|--------|-------------|----------|
| 10 min tick, run-forever until SIGINT | Matches SC-3 verbatim; beats 15-min AgentCore timeout. | ✓ |
| 10 min tick, auto-stop after --duration | Q&A overrun would silently stop warming. | |
| 5 min tick | Doubles cost; 10 min is the contract. | |

**User's choice:** 10-min forever (Recommended).

### Tick log format

| Option | Description | Selected |
|--------|-------------|----------|
| One-line-per-tick stdout | ISO timestamp + persona + status + latency + verdict. Visual heartbeat. | ✓ |
| Silent until error | Operator loses visibility after 45 minutes. | |
| Structured JSON to a file | Overkill; stdout + shell redirection covers if needed. | |

**User's choice:** One-line-per-tick stdout (Recommended).

**Checkpoint:** User chose "Next area" when offered more keep-alive questions.

---

## Offline Tests + Closeout Gate

### prewarm.py offline coverage

| Option | Description | Selected |
|--------|-------------|----------|
| tests/test_prewarm_script.py with mocked urllib | Catches logic regressions (gate, exit codes, median) without AWS. | ✓ |
| No — rely on live smoke only | Median-gate bugs surface at T-24h rehearsal — too late. | |
| Minimal smoke only (imports + --help) | Misses all logic. | |

**User's choice:** Offline pytest with mocked urllib (Recommended).

### demo-keepalive.sh offline coverage

| Option | Description | Selected |
|--------|-------------|----------|
| shellcheck only | Test harness would exceed script size. Live 3-tick sanity is real gate. | ✓ |
| Bash unit test via bats/shunit2 | New dev dep for 30 lines. | |
| No tests — live smoke only | Acceptable; shellcheck adds lint value with zero dep cost. | |

**User's choice:** shellcheck only (Recommended).

### Eval harness offline tests

| Option | Description | Selected |
|--------|-------------|----------|
| No — harness is already a test | Testing a test is turtles. Verify via live run + fixture failure path. | ✓ |
| Offline test with mock HTTP | More robust; ~100 lines fixture; freeze-surface unfriendly. | |

**User's choice:** No (Recommended).

### Closeout gate (D-22)

| Option | Description | Selected |
|--------|-------------|----------|
| Live prewarm + live eval + keepalive 3-tick sanity + green "not smoke" + shellcheck | All five validations before Phase 9 closes. | ✓ |
| Lighter — skip live keepalive | Ship-and-trust is risky for demo-day tooling. | |
| Heavier — add visual UAT | Phase 8 already owns UI screenshots. Scope-creep. | |

**User's choice:** Full 5-step live-verified gate (Recommended).

**Checkpoint:** User chose "I'm ready for context" when asked about remaining gray areas.

---

## Claude's Discretion

Documented in CONTEXT.md `<decisions>` § Claude's Discretion:
- `statistics.median` tie-handling (not applicable at 3 samples)
- Whether prewarm.py logs total runtime at end
- `printf` vs `echo -e` for keepalive timestamps
- Stderr vs stdout split for setup errors
- Eval harness uses `requests` (dev dep) vs stdlib urllib
- `--dry-run` flag on prewarm.py
- Rotating persona starting index + randomization
- `trap` signal list (INT/TERM/HUP)
- `test_prewarm_script.py` structure (parametrize vs individual functions)

## Deferred Ideas

Documented in CONTEXT.md `<deferred>` § Deferred Ideas — 22 explicitly deferred options ranging from runbook entries (Phase 10) to production hardening (v3.0) to rejected alternatives (`--then-eval` chain, JSON output, tightened <2500ms gate, dual-path eval, 10-invocation live harness, bash unit tests, EventBridge keep-alive, CloudWatch alarms, etc).

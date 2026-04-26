---
phase: 09-pre-warm-tooling-eval-harness-keep-alive
plan: 03
subsystem: operator-tooling
tags: [keepalive, bash, prewarm, agentcore, demo-05]
requires:
  - "Phase 7 `?prewarm=1` route (D-04 204-only contract) — unchanged"
provides:
  - "scripts/demo-keepalive.sh: pure-bash 10-minute rotating-persona ping loop beating AgentCore's 15-minute microVM idle timeout"
affects:
  - "Phase 10 DEMO-RUNBOOK (T-30m tmux-pane operator pattern will call this script)"
tech_stack_added:
  - bash (stdlib only; no new deps)
  - shellcheck (already on PATH; no lockfile change)
tech_stack_patterns:
  - "D-16: `#!/usr/bin/env bash` + `set -euo pipefail` strict mode"
  - "D-17: deterministic rotation via indexed array + `tick_count % 3`"
  - "D-18: `trap … INT TERM HUP` for clean shutdown; operator owns lifecycle"
  - "D-19: fast-fail via `${BACKEND_API_URL:?…}` parameter expansion; one-line-per-tick log format"
  - "D-21: shellcheck is the sole offline quality gate (test-surface-exceeds-code-surface)"
key_files_created:
  - "scripts/demo-keepalive.sh"
key_files_modified: []
decisions:
  - "Used `printf` (not `echo -e`) for portable output formatting — Claude's Discretion per CONTEXT.md line 157"
  - "Included `SIGHUP` in trap signal list alongside `INT` + `TERM` for tmux-pane-close resilience — Claude's Discretion per CONTEXT.md line 158"
  - "Deterministic rotation starts at CUST-001 (tick_count=0, index=0); no randomization — specifics line 263"
  - "Used `awk` for seconds→milliseconds conversion (bash has no native float math) — baked into the PATTERNS.md-assembled skeleton"
  - "`|| echo \"000 0\"` fallback on curl non-zero keeps the loop alive past 4xx/5xx/network failures — D-19 'loop continues through termination'"
metrics:
  duration_s: 146
  completed: 2026-04-26T07:55:38Z
  tasks_completed: 1
  files_created: 1
  files_modified: 0
requirements_satisfied:
  - DEMO-05
---

# Phase 09 Plan 03: Demo Keep-Alive Script Summary

**One-liner:** Ships `scripts/demo-keepalive.sh` — a 53-line pure-bash rotating-persona ping loop (CUST-001 → CUST-002 → CUST-003 every 10 minutes) that beats AgentCore's 15-minute microVM idle timeout by exercising the Phase 7 `?prewarm=1` route; clean-shutdown trap on `INT/TERM/HUP` and fast-fail on unset `BACKEND_API_URL`.

## What Shipped

A single executable file — `scripts/demo-keepalive.sh` — carrying every Phase 9 context decision baked into code:

- **Shebang:** `#!/usr/bin/env bash` (D-16 env-based for PATH portability)
- **Strict mode:** `set -euo pipefail` (D-16)
- **Env-var fast-fail:** `: "${BACKEND_API_URL:?BACKEND_API_URL not set}"` before the loop starts (D-19)
- **Rotation array:** `personas=(CUST-001 CUST-002 CUST-003)` with index `$((tick_count % 3))` — tick 0 → CUST-001 deterministic (D-17 + specifics line 263)
- **Signal trap:** `trap '…' INT TERM HUP` prints clean-shutdown line and exits 0 (D-18 + Claude's Discretion for tmux-pane-close resilience)
- **Curl shape:** `curl -f -s -o /dev/null -w '%{http_code} %{time_total}'` against `${BACKEND_API_URL}/recommendations/${persona}?prewarm=1` (canonical_refs line 217 + Phase 7 D-04 route)
- **Log format:** `<ISO-8601-UTC> <persona> <status> <latency_ms>ms <verdict>` via `printf` (D-19 byte-for-byte)
- **Cadence:** `sleep 600` = 10 minutes per tick (D-18; NOT 300, NOT 900)
- **Error tolerance:** `|| echo "000 0"` fallback on curl failure → `verdict=WARN` + loop continues (D-19 "continues through termination")

## Verification Results

All structural and quality gates pass. Live 20-minute unattended run is deferred to Phase 9 closeout gate D-22 step 3 — NOT run in this plan per the plan's `<verification>` section.

| Gate | Command | Result |
|------|---------|--------|
| Executable | `test -x scripts/demo-keepalive.sh` | PASS (mode 0755) |
| Shebang | `head -1 scripts/demo-keepalive.sh` | `#!/usr/bin/env bash` (byte-exact) |
| Syntax | `bash -n scripts/demo-keepalive.sh` | exit 0 |
| Quality | `shellcheck scripts/demo-keepalive.sh` | **exit 0, zero warnings** (no suppressions needed) |
| Line count | `wc -l scripts/demo-keepalive.sh` | 53 (≤60-line ceiling; D-16 target was ~30 LOC excl. comments) |
| Strict mode | `grep -qxF "set -euo pipefail"` | 1 match |
| Env fast-fail | `grep -qF 'BACKEND_API_URL:?BACKEND_API_URL not set'` | 1 match |
| Rotation array | `grep -qF "personas=(CUST-001 CUST-002 CUST-003)"` | 1 match |
| Modulo rotation | `grep -qF 'index=$((tick_count % 3))'` | 1 match |
| Trap signals | `grep -qE "trap .* INT TERM HUP"` | 1 match |
| Clean-shutdown log | `grep -qF "keepalive stopped after"` | 1 match |
| Prewarm route | `grep -qF "?prewarm=1"` | 1 match |
| Canonical curl | `grep -qF "curl -f -s -o /dev/null -w"` | 1 match |
| curl -w fields | `grep -qF '%{http_code} %{time_total}'` | 1 match |
| ISO-8601 UTC | `grep -cF 'date -u +%Y-%m-%dT%H:%M:%SZ'` | 2 (once in trap, once in loop) |
| 10-min cadence | `grep -qE '^[[:space:]]*sleep 600[[:space:]]*$'` | 1 match |
| Tick increment | `grep -qF 'tick_count=$((tick_count + 1))'` | 1 match |
| printf usage | `grep -cF 'printf'` | 3 (trap body + log line + awk template) |
| No `/bin/bash` shebang | `grep -cF '#!/bin/bash'` | 0 |
| No 5-min tick | `grep -cE '^[[:space:]]*sleep 300[[:space:]]*$'` | 0 |
| Unset-env fast-fail smoke | `env -u BACKEND_API_URL bash scripts/demo-keepalive.sh` | **exit 1**, stderr: `scripts/demo-keepalive.sh: line 19: BACKEND_API_URL: BACKEND_API_URL not set`, stdout empty |
| Scope (no `__init__.py`) | `test ! -f scripts/__init__.py` | PASS |
| Scope (no root `package.json`) | `test ! -f package.json` | PASS |

### shellcheck output

```
(no warnings)
```

No `# shellcheck disable=…` suppression comments were needed — the script uses simple constructs (array indexing with explicit `$index`, double-quoted expansions throughout, POSIX `[` test for the 204 comparison, arithmetic expansion, parameter-expansion splits) that shellcheck handles cleanly. Ran against shellcheck 0.11.0 (homebrew).

### `bash -n` syntax check

```
(no output, exit 0)
```

### Unset-env fast-fail smoke (live-runnable without a deployed stack)

```
$ env -u BACKEND_API_URL bash scripts/demo-keepalive.sh
scripts/demo-keepalive.sh: line 19: BACKEND_API_URL: BACKEND_API_URL not set
(exit 1, stdout empty)
```

The `${BACKEND_API_URL:?…}` parameter-expansion fast-fail path fires BEFORE the loop starts, before any `curl` attempt, before any network I/O. This is the only script path safely runnable without a deployed AWS stack.

## Claude's Discretion Calls Made

Recorded per plan `<output>` requirements for Phase 9 decision log traceability:

1. **Used `printf` rather than `echo -e`** for both the trap body and the per-tick log line. CONTEXT.md line 157 flagged this as Claude's Discretion ("recommend `printf` for portability"). `echo -e` is non-portable across `sh` implementations and has surprising behavior with backslash sequences; `printf` is stdlib and deterministic. Both log lines (D-18 shutdown line + D-19 per-tick line) use `printf` format strings with explicit field conversions.

2. **Included `SIGHUP` in the trap signal list** alongside `SIGINT` and `SIGTERM`. CONTEXT.md line 158 flagged this as Claude's Discretion ("trap handles SIGHUP — recommend yes"). The rationale: the Phase 10 DEMO-RUNBOOK T-30m pattern runs this in a tmux pane; if the operator closes the pane without Ctrl-C (accidentally or in cleanup), bash receives `SIGHUP`. Without `HUP` in the trap, the script would exit with default SIGHUP handling and skip the clean-shutdown log line. Including `HUP` costs one word and buys pane-close resilience.

3. **Deterministic rotation starts at CUST-001, no randomization.** Specifics line 263 was prescriptive but worth restating: the rotation is `tick_count % 3` with `tick_count` initialized to 0, so the very first tick (before increment) maps to index 0 = CUST-001. An operator reading the log at tick 47 can compute `47 % 3 = 2 → CUST-003` without re-counting — predictability beats the thin "rotate from a random starting point to avoid patterns" argument that's irrelevant here.

## Deviations from Plan

None — plan executed exactly as written. The file contents match the specification in Task 1's `<action>` block byte-for-byte (same shebang, same strict mode line, same fast-fail parameter expansion, same personas array, same trap structure, same loop body, same curl invocation, same awk conversion, same printf log format, same `sleep 600` cadence, same tick_count increment).

### Minor verification-command adjustment (not a deviation from the code)

The plan's `<verify>` section used `grep -qE "^\s*sleep 600\s*$"` with the Perl `\s` shortcut. BSD grep on macOS doesn't expand `\s`, so the verification was run with the POSIX-equivalent `grep -qE "^[[:space:]]*sleep 600[[:space:]]*$"` instead — functionally identical, just using a portable character class. The script contents are unchanged.

## Risks Mitigated per Threat Model

| Threat ID | Category | Component | Disposition | How satisfied |
|-----------|----------|-----------|-------------|---------------|
| T-09-07 | Injection (I) | curl URL construction | mitigate | `persona` values come from the hard-coded `personas=(CUST-001 CUST-002 CUST-003)` array (no user input); double-quoted expansion on `$persona` and `$BACKEND_API_URL` prevents word-splitting / glob expansion. Operator-controlled env var is configuration, not untrusted input. |
| T-09-08 | DoS (D) | AgentCore warm-up abuse | accept | Cadence is fixed at `sleep 600` = one call per 10 minutes per persona; 18 calls per 3-hour demo window within the $3-12 cost envelope per RESEARCH.md. Operator-owned lifecycle; not automatable via cron. |
| T-09-09 | Info disclosure (I) | Stdout/stderr leakage | accept | Log lines contain only persona IDs (non-PII fixtures), HTTP status, integer ms latency, ISO-8601 timestamp. No tokens, no payload bodies. The fast-fail stderr line echoes `BACKEND_API_URL not set` but not the URL value itself (it exits before any value is used). |
| T-09-10 | Resource exhaustion (D) | Unbounded loop | accept | D-18 explicitly rejects auto-stop; operator owns lifecycle via tmux pane (visible during demo). Trap on `INT/TERM/HUP` ensures clean shutdown. 10-minute cadence is low-frequency. |

## Deferred / Not In This Plan

- **Live 20-minute unattended run** (rotating 204s + Ctrl-C clean-shutdown verification against a deployed stack) is deferred to **Phase 9 closeout gate D-22 step 3** per the plan's `<verification>` section. This plan only verifies structural correctness + the unset-env fast-fail path (the only path safely runnable without a deployed stack).
- **Tests:** D-21 explicitly rejected bash unit tests as "test-surface-exceeds-code-surface." `shellcheck` + `bash -n` + the structural grep suite cover the static properties; the live run at D-22 covers dynamic behavior.

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `scripts/demo-keepalive.sh` | **created** (mode 0755, executable) | +53 |

Zero modifications to `agent/`, `api_lambda/`, `infrastructure/`, `ui/`, `tests/`, `requirements*.txt`, or `ui/package.json` — the `files_modified` frontmatter scope (single file) is honored.

## Commits

| Task | Hash | Message |
|------|------|---------|
| Task 1 | `7e91351` | feat(09-03): add scripts/demo-keepalive.sh rotating-persona ping loop |

## Self-Check: PASSED

- `scripts/demo-keepalive.sh` → FOUND (mode 0755)
- commit `7e91351` → FOUND in `git log`
- `bash -n scripts/demo-keepalive.sh` → exit 0
- `shellcheck scripts/demo-keepalive.sh` → exit 0, zero warnings
- `env -u BACKEND_API_URL bash scripts/demo-keepalive.sh` → exit 1, `BACKEND_API_URL` on stderr
- No modifications to `agent/`, `api_lambda/`, `infrastructure/`, `ui/`, `tests/`
- No `scripts/__init__.py` or root `package.json` created (freeze-surface rule honored)
- All 21 acceptance criteria from the plan's `<acceptance_criteria>` block satisfied

# Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Ship three operator artefacts that close **DEMO-03 tooling half** and **DEMO-05**:

1. `scripts/prewarm.py` (invokable as `npm run prewarm` from `ui/`) — warms all 3 personas × both cards through the full API Gateway → Lambda → AgentCore → Bedrock chain via the Phase 7 `?prewarm=1` route, then runs a 9-call timed-lookup measurement pass and asserts per-persona warm median <3000ms with non-zero exit on gate fail.
2. `scripts/demo-keepalive.sh` — pure-bash 10-minute rotating-persona ping loop (CUST-001 → 002 → 003 → 001 …) that runs from T-30m through end of Q&A, beating AgentCore's 15-minute microVM idle timeout.
3. `tests/test_narrative_eval_live.py` — pytest-smoke-gated end-to-end narrative eval harness that hits the live API for all 3 personas × both tracks and asserts presence + Phase 6 validator rules on every `usage_narrative` + `call_script` string, plus the Phase 7 D-06 `_narrative_source`-absent invariant.

Closes **DEMO-03 (complete)** and **DEMO-05** per REQUIREMENTS.md Traceability. Freeze artefacts and rollback drill belong to Phase 10.

**In scope (Phase 9 only):**
- `scripts/prewarm.py` — stdlib-urllib script, per-call latency stdout + summary block, 3× `?prewarm=1` warm pass (2s spacing) → 30s wait → 3× timed `GET /recommendations/{customer_id}` per persona → per-persona median computation → exit 0/1/2 taxonomy.
- `ui/package.json` — add `"prewarm": "cd .. && python3 scripts/prewarm.py"` to the existing `scripts` block.
- `scripts/demo-keepalive.sh` — `#!/usr/bin/env bash` + `set -euo pipefail`, bash while-loop with rotating persona index, `curl -f -s -o /dev/null` against `${BACKEND_API_URL}/recommendations/${persona}?prewarm=1`, `sleep 600`, `trap SIGINT/SIGTERM` for clean shutdown log, one-line-per-tick stdout (`ISO-timestamp persona status latency verdict`).
- `tests/test_narrative_eval_live.py` — `@pytest.mark.smoke` + `pytest.skipif` on missing `BACKEND_API_URL` (matches `tests/test_backend_api_smoke.py` pattern byte-for-byte), one HTTP GET per persona, 12 assertions per run (3 personas × 2 tracks × {narrative, call_script} presence + validator rules + marker-absent). Imports `agent.narrative.banned_terms` directly; mirrors word/char-cap constants from `tests/test_fallbacks_pass_validator.py`.
- `tests/test_prewarm_script.py` — offline pytest with mocked `urllib.request.urlopen` that asserts exit 0 on all-<3000ms, exit 1 on ≥3000ms median + exit 1 on non-204 from prewarm + exit 2 on missing `BACKEND_API_URL`, correct median computation, per-call log lines present. Runs green under `pytest -m "not smoke"`.
- Live-verified Phase 9 closeout gate (documented in SUMMARY, not pytest-ed): (1) `npm run prewarm` → exit 0 with all personas <3000ms; (2) `BACKEND_API_URL=… pytest tests/test_narrative_eval_live.py -m smoke` → green; (3) `scripts/demo-keepalive.sh` runs ≥20 minutes unattended, emits 2 full rotating 204s + start of the 3rd, Ctrl-C fires the trap cleanly; (4) `pytest -m "not smoke"` stays green.

**Out of scope (Phase 9 does NOT do):**
- `pip-compile --generate-hashes`, CFN stack policies, `demo-v2.0` tag, DynamoDB snapshot, `FREEZE-MANIFEST.md` — Phase 10 (DEMO-04).
- Rollback drill — Phase 10 (DEMO-06).
- Any change to `agent/`, `agent/narrative/`, `api_lambda/`, `infrastructure/`, or the UI. Phase 6/7/8 contracts are frozen.
- CloudWatch log-query assertions inside the eval harness (Phase 7 D-07 `narrative_source` log is queryable separately; the live eval harness stays HTTP-only to keep scope tight).
- AgentCore-direct eval variant (`scripts/capture_samples.py` already covers AgentCore-direct capture; Phase 9's eval covers the API Lambda path end-to-end).
- `scripts/prewarm.py --then-eval` chaining — prewarm and eval stay orthogonal (different runbook triggers).
- Offline tests for `scripts/demo-keepalive.sh` beyond shellcheck — script is 30 lines of bash and the mock surface exceeds the script.
- CI cron / scheduled eval runs — single-shot demo.
- A separate root `package.json` — the `npm run prewarm` wrapper lives inside `ui/package.json`.
- DEMO-RUNBOOK.md updates documenting T-30m keep-alive start, T-10m prewarm, T-eval gates — Phase 10 owns the runbook rewrite.

**Success criteria (from ROADMAP.md):**
1. `npm run prewarm` (invoking `scripts/prewarm.py`) warms all 3 personas × both cards through the full API Gateway → Lambda → AgentCore → Bedrock chain in under 30 seconds, with `set -euo pipefail` + `curl -f` semantics and per-call latency printed.
2. The pre-warm script exits non-zero if warm median ≥ 3000ms on any persona, and a subsequent lookup within 5 minutes measures warm median ≤ 2.5s on all personas.
3. `scripts/demo-keepalive.sh` pings the hot path every 10 minutes and continues through termination, beating AgentCore's 15-minute microVM idle timeout.
4. The end-to-end eval harness asserts every persona × card narrative passes the Phase 6 validator when driven through the live endpoint — run green before the phase closes.

</domain>

<decisions>
## Implementation Decisions

### Pre-Warm Script — `scripts/prewarm.py`

- **D-01:** `scripts/prewarm.py` is **Python with stdlib `urllib` only** — no new runtime deps, no reliance on `requests` (which is dev-only in `requirements-dev.txt`). `import urllib.request, urllib.error, time, os, statistics, sys`. Minimizes Phase 10 freeze surface; a demo-critical script should depend on nothing you need to lockfile-pin. Matches `scripts/capture_samples.py` "stdlib where possible" convention.

- **D-02:** Two-pass flow:
  1. **Warm pass:** For each of `CUST-001`, `CUST-002`, `CUST-003`: `GET ${BACKEND_API_URL}/recommendations/${persona}?prewarm=1` (expect HTTP 204). 2-second `time.sleep(2)` between calls. Phase 7 D-03 owns this rotation. Log line per call: `prewarm CUST-001: 204 312ms`. If any prewarm call returns non-204, fast-fail with exit 1 (the Lambda is broken or the endpoint is wrong — don't pretend we warmed).
  2. **Wait:** `time.sleep(30)` — lets AgentCore microVM pool settle (ARCHITECTURE Phase 2.4 checkpoint).
  3. **Measurement pass:** For each persona, 3 timed `GET ${BACKEND_API_URL}/recommendations/${persona}` (no `?prewarm=1`). Record latencies via `time.perf_counter()`. Log line per call: `CUST-001 warm 1/3: 1843ms 200 ok`. Compute `statistics.median([...])` per persona.
  4. **Gate:** Assert every persona's median < 3000ms. On fail, print summary block (`median CUST-001: 3174ms FAIL (≥3000ms)`) and exit 1.
  9 timed calls total for the measurement pass; script runtime envelope ~60s (3× ~0.5s prewarm + 6s spacing + 30s wait + 9× ~2s warm lookups). Matches ARCHITECTURE Phase 2.4 checkpoint and ROADMAP SC-1/SC-2 wording.

- **D-03:** Warm-median gate threshold is **<3000ms per persona**, matching ROADMAP SC-2 verbatim and Phase 7 D-15 runbook gate. Not tightened to <2500ms on flagship; the Phase 7 CONTEXT Claude's Discretion hint ("planner may tighten to <2500ms on the flagship") explicitly defers that to the planner, and at Phase 9 the answer is **do not tighten** — network variance on rehearsal networks would produce false fails. SC-2's aspirational "warm median ≤ 2.5s on all personas" is a *separate* post-gate observation printed in the summary block but not an exit-code trigger; only ≥3000ms flips exit to 1.

- **D-04:** Per-call output is **one-line-per-call plain stdout + summary block** — no JSON, no `--verbose` flag. Format:
  ```
  prewarm CUST-001: 204 312ms ok
  prewarm CUST-002: 204 287ms ok
  prewarm CUST-003: 204 306ms ok
  (wait 30s)
  CUST-001 warm 1/3: 1843ms 200 ok
  CUST-001 warm 2/3: 1912ms 200 ok
  CUST-001 warm 3/3: 1795ms 200 ok
  CUST-002 warm 1/3: ...
  ...
  ---
  median CUST-001: 1843ms PASS (<3000ms)
  median CUST-002: 2104ms PASS (<3000ms)
  median CUST-003: 1967ms PASS (<3000ms)
  all personas under gate — exit 0
  ```
  Matches `scripts/capture_samples.py` stdout style (plain human-readable). Satisfies SC-1 "per-call latency printed" flatly.

- **D-05:** API URL source is **`BACKEND_API_URL` environment variable** — exact match for `tests/test_backend_api_smoke.py` convention. Missing/empty → fast-fail with exit 2 + stderr `"BACKEND_API_URL not set"`. No hard-coded fallback URL (Phase 10 freeze surface: the endpoint is in `.planning/STATE.md` / `05-DEPLOY-OUTPUTS.md`, not baked into a script). No positional arg, no `--url` flag — one source of truth.

- **D-06:** Exit-code taxonomy (strict 0/1/2 three-way):
  - **0:** All personas under gate — happy path.
  - **1:** Gate-fail OR non-204 on a `?prewarm=1` call OR non-200 on a measurement-pass call. "The demo latency is bad or the endpoint is returning errors." Presenter's next step: check CloudWatch and/or re-run after a cold-path recovery.
  - **2:** Setup error — missing `BACKEND_API_URL`, unreachable endpoint on first call (connection refused / DNS failure), import error. "The script's environment is wrong." Presenter's next step: fix the environment, not the demo.
  Shell wrappers (`set -euo pipefail`) distinguish these cleanly. Callers that want the binary view still get it via `exit_code != 0`.

- **D-07:** `npm run prewarm` wrapper lives in **`ui/package.json`** (not a new root `package.json`). Script value: `"prewarm": "cd .. && python3 scripts/prewarm.py"`. Presenter invokes from `ui/` (same directory they use for `npm run build` / `build:mock`). Zero new freeze-surface files; one new line in `ui/package.json` scripts block. ROADMAP SC-1's `"npm run prewarm (invoking scripts/prewarm.py)"` wording is satisfied.

- **D-08:** Per-HTTP-call timeout is **`timeout=30` seconds** on every `urllib.request.urlopen` call. Longer than the UI-02 3000ms gate so a single slow call surfaces in the latency log (rather than raising). Any `urllib.error.URLError` / `socket.timeout` on a measurement call → log `CUST-00N warm N/3: TIMEOUT` and treat as a ≥3000ms sample for median purposes (pushes the median up, which is exactly what should happen when the path is slow enough to time out). Unreachable on the *first* prewarm call → exit 2 (setup error, D-06).

### Eval Harness — `tests/test_narrative_eval_live.py`

- **D-09:** Harness lives at **`tests/test_narrative_eval_live.py`** with `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(not BACKEND_API_URL, reason=…)]` — byte-for-byte the pattern from `tests/test_backend_api_smoke.py`. `pytest -m smoke` runs it, `pytest -m "not smoke"` skips. Reuses existing `conftest.py`; no new fixtures. Invocation: `BACKEND_API_URL=https://… pytest tests/test_narrative_eval_live.py -m smoke`.

- **D-10:** Harness reads narrative from the **live API endpoint only** (HTTP GET). Matches ROADMAP SC-4 "driven through the live endpoint" verbatim. No AgentCore-direct boto3 variant — `scripts/capture_samples.py` already captures the AgentCore-direct payload when the `_narrative_source` marker needs to be inspected, and Phase 7 D-06 strips that marker from the API Lambda response anyway. Keeps the harness zero-AWS-creds; runs from any box with network access to the endpoint.

- **D-11:** **One HTTP GET per persona × 3 personas = 3 calls total.** Each call yields 2 tracks × 2 narrative fields = 4 strings to assert. Per persona: presence of `usage_narrative` + `call_script` on both `green` and `cheapest`, plus validator rules (NUMERIC_REGEX miss, BANNED_REGEX miss, word-count ≤20 for narrative / ≤22 for call_script, char-count ≤140 / ≤180). 12 assertions per run. Fast (~15s on a warm stack). Phase 6's offline 10× pattern is *not* replicated live — the Pydantic validator + fallbacks already bound the output space, and T-24h rehearsal is the variance gate.

- **D-12:** Validator rules come from **importing `agent.narrative` directly**: `from agent.narrative.banned_terms import BANNED_REGEX, NUMERIC_REGEX`. Word and char caps are mirrored as test-module constants matching `tests/test_fallbacks_pass_validator.py` exactly (`_USAGE_NARRATIVE_MAX_WORDS=20`, `_CALL_SCRIPT_MAX_WORDS=22`, `_USAGE_NARRATIVE_MAX_CHARS=140`, `_CALL_SCRIPT_MAX_CHARS=180`). Single source of truth: if Phase 6 rules drift, the harness catches it. Not calling the full Pydantic TrackInfo model (it requires unrelated fields like `plan_id`, `saving_monthly`); regex + caps is the minimal surface this test needs.

- **D-13:** Harness asserts three things per persona: (a) response 200 + body has `usage_narrative` + `call_script` on both `green` and `cheapest`; (b) all 4 strings pass the validator rules; (c) **`_narrative_source` is absent from the response body** (Phase 7 D-06 invariant — the marker must never reach the client). Does NOT assert savings values (Phase 1 pytest + `tests/test_backend_api_smoke.py` already cover DEMO-02). Does NOT query CloudWatch for Phase 7 D-07 `narrative_source` logs — out-of-scope to keep the harness HTTP-only.

- **D-14:** Harness runs **explicitly before phase close** (Phase 9 closeout gate, D-19) and is invokable from the Phase 10 DEMO-RUNBOOK at T-48h / T-24h / T-10min per FEATURES.md playbook. No chain with `prewarm.py` — kept orthogonal because the runbook may want prewarm without eval (T-10m live) or eval without prewarm (T-24h against already-warm stack).

- **D-15:** Report format is **pytest default + per-assertion failure message**. No separate `09-EVAL-SAMPLES.md` capture (capture_samples.py already covers that artefact). Failure messages include persona, track, field, and the offending string, e.g. `AssertionError: CUST-001/green/usage_narrative: forbidden digit in 'usage jumped 15%...'`. Zero new reporting code.

### Keep-Alive — `scripts/demo-keepalive.sh`

- **D-16:** Pure **bash while-loop + `trap`** — no Python wrapper. Shebang `#!/usr/bin/env bash` + `set -euo pipefail`. ROADMAP SC-3 names `demo-keepalive.sh` explicitly; the `.sh` extension is load-bearing for the runbook. Total script length target ~30 lines. Uses stdlib only; no bash-4-isms beyond `trap`.

- **D-17:** Each 10-minute tick rotates through `CUST-001` → `CUST-002` → `CUST-003` → back to `CUST-001`. Rotation index is a counter mod 3. Each tick fires `curl -f -s -o /dev/null -w '%{http_code} %{time_total}' "${BACKEND_API_URL}/recommendations/${persona}?prewarm=1"`. Exercises the full warm path (same semantics as Phase 7 D-02). AgentCore microVM pool is per-session-routing; rotating personas warms pool depth evenly rather than keeping only one slot warm.

- **D-18:** Cadence = **10 minutes per tick**, runs forever until `SIGINT` / `SIGTERM`. `sleep 600` between ticks. Matches ROADMAP SC-3 "every 10 minutes" + "continues through termination" verbatim. Operator pattern: start at T-30m in a tmux pane, Ctrl-C after Q&A. `trap 'echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] keepalive stopped after ${tick_count} ticks"; exit 0' INT TERM`. No auto-stop clock — operator owns lifecycle.

- **D-19:** Tick log is **one line per tick on stdout**:
  ```
  2026-04-26T14:23:45Z CUST-001 204 312ms ok
  2026-04-26T14:33:46Z CUST-002 204 287ms ok
  2026-04-26T14:43:46Z CUST-003 204 306ms ok
  2026-04-26T14:53:47Z CUST-001 204 298ms ok
  ```
  ISO-8601 UTC timestamp + persona + HTTP status + latency + verdict. Non-204 logs `WARN` verdict but loop continues (Phase 7 D-04 guarantees 204 on all failure modes — any non-204 is investigation-worthy but not a loop-killing condition). `BACKEND_API_URL` missing → fast-fail with stderr before the loop starts.

### Offline Tests + Closeout Gate

- **D-20:** **`scripts/prewarm.py` gets offline pytest coverage** at `tests/test_prewarm_script.py`. Pattern: subclass or mock `urllib.request.urlopen` via `unittest.mock.patch` to return canned `(status, body, elapsed_stub)` responses. Test cases:
  - `test_prewarm_happy_path_exit_0` — all 204s + all <3000ms medians → exit 0, correct summary block.
  - `test_prewarm_gate_fail_exit_1` — one persona with 3 samples [3174, 3050, 3100] → median 3100 → exit 1 + `FAIL` in summary line for that persona.
  - `test_prewarm_bad_prewarm_response_exit_1` — `?prewarm=1` returns 500 → exit 1 + fast-fail before measurement pass.
  - `test_prewarm_missing_env_var_exit_2` — `monkeypatch.delenv('BACKEND_API_URL')` → exit 2.
  - `test_prewarm_measurement_timeout_pushes_median` — one call `socket.timeout` → treated as ≥3000ms sample → median flips to fail.
  - `test_prewarm_per_call_log_format` — verify `capsys` output has the D-04 format per call.
  - `test_prewarm_median_computation` — known samples → `statistics.median` result matches.
  ~80–120 lines. Runs green under `pytest -m "not smoke"` (keeps the existing 81-passed/6-skipped baseline intact).

- **D-21:** **`scripts/demo-keepalive.sh` gets `shellcheck` only** — run locally via `shellcheck scripts/demo-keepalive.sh`, result noted in 09-SUMMARY. No bash unit tests (`bats`/`shunit2` = new dev dep for 30 lines of code; rejected on freeze-surface grounds). Live 3-tick sanity at D-22 step 3 is the real gate.

- **D-22:** Phase 9 closeout gate (documented in plan SUMMARY, NOT shipped as pytest):
  1. `BACKEND_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com npm run prewarm` from `ui/` — exit 0; all 3 personas < 3000ms median in summary; 9 per-call latency lines printed; 30s wait clearly logged.
  2. `BACKEND_API_URL=https://… pytest tests/test_narrative_eval_live.py -m smoke` — green; 12 assertions cleared (3 personas × 2 tracks × 2 fields); pytest summary shows `3 passed` or equivalent.
  3. `BACKEND_API_URL=https://… bash scripts/demo-keepalive.sh` — run unattended for ≥20 minutes (2 complete 10-minute ticks + start of a 3rd). Verify stdout shows rotating 204s with UTC timestamps, log format matches D-19, persona rotation cycles CUST-001 → 002 → 003 → 001. Ctrl-C fires the `trap` cleanly (stdout shows "keepalive stopped after 3 ticks" then exit 0).
  4. `pytest -m "not smoke"` from repo root — still green. `test_prewarm_script.py` additions do not regress any v1.0/Phase 6/7/8 test.
  5. `shellcheck scripts/demo-keepalive.sh` — zero warnings (or documented suppressions in the script header).
  Phase 9 does NOT close until all 5 pass. Phase 10 freeze depends on this.

- **D-23:** `requirements.txt` / `requirements-dev.txt` impact = **zero**. All runtime deps already present: `urllib` is stdlib; `statistics` is stdlib; `time` is stdlib; `os` is stdlib; pytest + pytest.mark.smoke + mock come from existing `requirements-dev.txt`. No `pip install` in this phase. Freeze-surface delta for Phase 10: only `scripts/prewarm.py`, `scripts/demo-keepalive.sh`, `tests/test_narrative_eval_live.py`, `tests/test_prewarm_script.py`, and one line in `ui/package.json` scripts block.

### Claude's Discretion

- **Exact `statistics.median` tie-handling.** Python's `statistics.median` on an even-length list averages the two middle values; prewarm.py uses 3 samples per persona (odd), so ties can't happen. Planner does not need to special-case.
- **Whether `prewarm.py` also logs total runtime at the end** (`total: 62.3s`). Nice-to-have; planner decides. Recommend yes (one extra line; lets operator spot script-level regressions).
- **Whether `demo-keepalive.sh` uses `printf` vs `echo -e` for timestamped lines.** Planner picks; `printf` is more portable. Not load-bearing.
- **Exact stderr vs stdout split in `prewarm.py`.** D-04 shows stdout for happy-path; errors go to stderr. Planner confirms `print(..., file=sys.stderr)` is used for exit-code-2 setup errors.
- **Whether the eval harness uses `requests` or stdlib `urllib`.** `requests` is already in `requirements-dev.txt` (used by `test_backend_api_smoke.py`). Planner picks; recommend `requests` for harness consistency with the sibling smoke file; keep stdlib for `prewarm.py` (which is a runtime script, not a test).
- **Whether `scripts/prewarm.py` accepts a `--dry-run` flag.** Operator might want to print the plan without calling AWS. Recommend no — script runtime is ~60s and the plan is obvious from reading D-04's format. Planner can add if rehearsal reveals need.
- **Whether the rotating persona index in `demo-keepalive.sh` starts at CUST-001 or randomizes.** Recommend start at CUST-001 deterministically — easier to reason about in log inspection. Randomization adds no value.
- **Whether `trap` handles SIGHUP.** Recommend yes (tmux-pane-close resilience) — `trap '…' INT TERM HUP`. Planner confirms.
- **`test_prewarm_script.py` test structure — parametrize vs individual functions.** Planner decides. Recommend individual functions (D-20 enumerates 7 cases — parametrize would obscure the distinct semantics of each test).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Requirements + Roadmap

- `.planning/REQUIREMENTS.md` — §"Demo Hardening — Pre-warm (DEMO)" for DEMO-03 (full requirement; Phase 9 completes the tooling half) + DEMO-05 (keep-alive). §"Key Decisions Locked at Requirements Stage" for the keep-alive decision ("ship `scripts/demo-keepalive.sh`" — honest-framing recovery is the secondary net).
- `.planning/ROADMAP.md` §"Phase 9: Pre-Warm Tooling + Eval Harness + Keep-Alive" — 4 success criteria (load-bearing for D-01 through D-19).
- `.planning/PROJECT.md` — Core value, constraints. "Known pre-presentation work" callout captures that T-24h visual rehearsal is still outstanding; Phase 9 delivers the tooling that will drive it.
- `.planning/STATE.md` — v2.0 Blockers/Concerns: UI-01, UI-02, narrative content invariants must stay satisfied; Phase 9 closeout gate (D-22) validates UI-02 via prewarm script median assertion.

### Phase 6 + Phase 7 Artefacts (upstream contracts this phase consumes)

- `.planning/phases/06-agent-narrative-guardrail/06-CONTEXT.md` — **D-02 / D-04 / D-06 load-bearing for the eval harness**: narrative fields always non-empty via per-field fallback, fallback strings committed and validator-passing, word/char caps locked.
- `agent/narrative/banned_terms.py` — **imported directly by `tests/test_narrative_eval_live.py`** (D-12). `BANNED_REGEX` + `NUMERIC_REGEX` are the live harness's single-source-of-truth.
- `agent/narrative/fallbacks.py` — reference only (eval harness reads live agent output, not fallbacks). Committed fallback strings define the `≤140 / ≤180 char, ≤20 / ≤22 word` envelope the live output must also sit inside.
- `.planning/phases/07-api-pass-through-pre-warm-route/07-CONTEXT.md` — **D-01 / D-02 / D-03 / D-04 / D-06 / D-07 all load-bearing**: the `?prewarm=1` query flag on `/recommendations/{customer_id}` that `prewarm.py` and `demo-keepalive.sh` call; Phase 7's D-03 explicitly states "persona rotation is owned by the operator script"; Phase 7's D-04 guarantees `?prewarm=1` always returns 204 (never 5xx); Phase 7's D-06 strips `_narrative_source` (the eval harness asserts this); Phase 7's D-07 `narrative_source` CloudWatch log is available for post-hoc debugging but not queried by the harness.
- `.planning/phases/07-api-pass-through-pre-warm-route/07-VERIFICATION.md` — evidence that `?prewarm=1` 204 contract holds live.
- `.planning/phases/07-api-pass-through-pre-warm-route/07-01-SUMMARY.md` — structured-log conventions (JSON-in-message via `logger.info(json.dumps(...))`) that Phase 9 inherits only if prewarm.py adds any logs (currently stdout only).

### Phase 8 Artefacts (non-blocking parallel)

- `.planning/phases/08-ui-integration-feature-flag-version-indicator/08-CONTEXT.md` — **shares no files with Phase 9**. Referenced only to confirm non-blocking: Phase 9 does not touch `ui/src/`; Phase 8 does not touch `scripts/` or `tests/*.py`. The only UI-layer touch in Phase 9 is a one-line scripts-block addition to `ui/package.json`.

### v2.0 Research

- `.planning/research/ARCHITECTURE.md` §"DEMO-03 — Pre-Warm Architecture" — 5-surface cold-start grid, recommended Option (b)+(d) mechanism (reuse `/recommendations` with `?prewarm=1` + scripted curl rotation — Phase 9 `scripts/prewarm.py` is the (d) half), pre-warm data flow diagram, AP-3 (never cache session IDs — Phase 9's prewarm.py does not mint session IDs; AgentCore + the Lambda own that).
- `.planning/research/ARCHITECTURE.md` §"Latency Budget — Does UI-02 Survive v2.0?" — 1470–3150ms warm envelope on Option A. Phase 9 prewarm.py's 3000ms gate sits at the upper edge of this envelope (the "bad tail" line).
- `.planning/research/ARCHITECTURE.md` §"Phase 2.4 — Pre-Warm Tooling (DEMO-03)" — phase-level checkpoint: "npm run prewarm completes in <30s total; subsequent lookup within 5 min measures warm median ≤2.5s on all personas." D-02 maps the two-pass flow to this checkpoint (except gate is <3000ms per D-03, not ≤2.5s — the ≤2.5s aspiration is printed in summary but not gate-triggering).
- `.planning/research/FEATURES.md` §"DEMO-03 (Pre-Warm) — Playbook" — T-30 / T-10 / T-5 / T-0 checklist. Phase 9 tooling makes T-10 "run prewarm" a one-command step. Phase 10 DEMO-RUNBOOK.md codifies the checklist; Phase 9 delivers the commands it invokes.
- `.planning/research/FEATURES.md` §"Table Stakes (v2.0)" → "LLM warm-path eval harness" — confirmed: "a tiny pytest that invokes the agent end-to-end for each persona and asserts the narrative passes the validator. Runs pre-demo." Phase 9 D-09 through D-15 delivers exactly this.
- `.planning/research/PITFALLS.md` — AP-3 (no cached session IDs — prewarm.py hits `?prewarm=1` which mints uuid4 Lambda-side, no session cache), AP-5 (skipping pre-warm at T-24h rehearsal — Phase 10 runbook addresses).
- `.planning/research/STACK.md` — Python 3.12 Lambda runtime; dev `requirements-dev.txt` already includes `requests`, `pytest`. No new deps for Phase 9.

### v1.0 Carry-Forward (the stack Phase 9 extends)

- `scripts/capture_samples.py` — **primary convention reference**. stdlib-first, sys.exit taxonomy (`return 2` on missing env var, `return 0` on success), `pathlib` for file writes, `boto3` lazy import, stderr for progress messages. Phase 9 `scripts/prewarm.py` mirrors this style (minus boto3, since it's HTTP-only).
- `tests/test_backend_api_smoke.py` — **primary pattern reference** for the eval harness (D-09). `BACKEND_API_URL` env var, `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(...)]`, `requests.get` with `timeout=60`, one test function per persona/scenario. `tests/test_narrative_eval_live.py` follows this byte-for-byte.
- `tests/test_fallbacks_pass_validator.py` — **pattern reference** for the validator rules the eval harness applies (D-12). Word/char cap constants mirrored; `_fails_rules()`-style helper optional but acceptable. The eval harness tests live agent output, not fallbacks, but applies the identical rule set.
- `tests/conftest.py` — existing test setup; unchanged by Phase 9.
- `ui/package.json` — **primary file modified**: one-line `"prewarm"` script added to `scripts` block alongside existing `dev` / `build` / `build:mock` / `lint` / `preview` / `test` / `test:watch`.
- `.gitignore` — unchanged; scripts/ and tests/ already tracked.

### v1.0 Phase Context (for convention carry-forward)

- `.planning/milestones/v1.0-phases/03-backend-api/03-CONTEXT.md` — Phase 3 D-11 (fresh uuid4 per invocation — honoured automatically by `?prewarm=1` since the Lambda mints its own uuid4; prewarm.py does not), D-13 (customer_id regex — live API still rejects bad IDs at 400 even when `?prewarm=1` is passed; harness assumes valid persona IDs), D-12 (error taxonomy — eval harness trusts 200/400/404/5xx semantics; any 5xx on the measurement path is a gate-fail in prewarm.py and a test-fail in the eval harness).
- `.planning/milestones/v1.0-phases/04-agent-assist-ui/04-CONTEXT.md` — Phase 4 skeleton + mock conventions (unrelated to Phase 9 but confirms the `ui/package.json` scripts convention Phase 9 extends).

### External / upstream docs

- Python `urllib.request` stdlib docs — `urlopen(url, timeout=N)` signature, `http.client.HTTPResponse.status` / `.read()` / `.headers` access pattern, `urllib.error.URLError` / `urllib.error.HTTPError` exception hierarchy. Researcher confirms the pattern the planner uses for reading response bodies.
- Python `statistics.median` docs — tie-handling on even-length lists (not relevant at 3 samples per persona, but noted for planner awareness).
- Python `time.perf_counter()` vs `time.monotonic()` — `perf_counter()` is the recommended high-resolution timer for short-interval measurements; `monotonic()` is for long-duration. Phase 9 uses `perf_counter()` for measurement-pass latencies.
- `curl -f -s -o /dev/null -w '%{http_code} %{time_total}'` man page — `-f` fails loudly on 4xx/5xx, `-s` silences progress, `-o /dev/null` discards body, `-w` prints the template to stdout. Standard pattern; confirmed.
- `bash` `trap BUILTIN` — `trap 'cmd' INT TERM HUP` signal list; `trap` fires before `exit`; `exit 0` in the trap overrides any non-zero exit code. Planner confirms.
- `shellcheck` docs — commonly-flagged bash pitfalls (unquoted variables in rotation index, missing `local` in functions, etc.). Planner runs `shellcheck` before calling the script done.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `scripts/capture_samples.py` (57 lines) — stdlib-first stylistic template for `scripts/prewarm.py`. Exit taxonomy (0/2), stderr for progress, `pathlib` for any file writes (prewarm.py writes nothing — pure stdout), `if __name__ == "__main__": sys.exit(main())` convention.
- `tests/test_backend_api_smoke.py` (84 lines) — drop-in pattern for `tests/test_narrative_eval_live.py`. Reuse: `BACKEND_API_URL` env var read, `pytestmark = [pytest.mark.smoke, pytest.mark.skipif(...)]`, `requests.get(..., timeout=60)`, `@pytest.mark.parametrize("customer_id", [...])`, per-assertion failure message style.
- `tests/test_fallbacks_pass_validator.py` (57 lines) — validator-rule-application pattern for the eval harness. `_fails_rules(value, max_words, max_chars)` helper returns `None` on pass, failure-reason string on fail; `NUMERIC_REGEX.search(value)` + `BANNED_REGEX.search(value)`; word count via `len(value.split())`. Eval harness can reuse this helper verbatim or mirror inline.
- `agent/narrative/banned_terms.py` — `BANNED_REGEX` and `NUMERIC_REGEX` imported directly by the eval harness (D-12). No copy-paste drift.
- `tests/conftest.py` — existing pytest fixtures; unchanged.
- `ui/package.json` `scripts` block — existing structure (`dev` / `build` / `build:mock` / `lint` / `preview` / `preview:mock` / `test` / `test:watch`); Phase 9 appends one line.
- `requirements-dev.txt` — `requests`, `pytest` already present; no new additions for Phase 9.

### Established Patterns

- **stdlib-first for operator scripts** (Phase 6 `capture_samples.py` convention). Phase 9 `prewarm.py` uses `urllib` + `time` + `statistics`; no `requests`, no new deps.
- **`BACKEND_API_URL` env var as the live-stack address** (Phase 3 convention, v1.0 `tests/test_backend_api_smoke.py`). Phase 9 prewarm.py + keep-alive + eval harness all consume the same env var.
- **Pytest smoke marker for live-endpoint tests** (`@pytest.mark.smoke` + `pytest.skipif(not BACKEND_API_URL, …)`). `pytest -m "not smoke"` stays green; `pytest -m smoke` runs the live checks. Phase 9 eval harness follows.
- **0/1/2 exit taxonomy for operator scripts** (`capture_samples.py` uses 0/2). Phase 9 prewarm.py extends to 0/1/2 where 1 = gate-fail / endpoint-broken, 2 = setup error.
- **Python 3.12 Lambda runtime parity for scripts** (Phase 3 STACK.md). `scripts/prewarm.py` uses `#!/usr/bin/env python3` and is compatible with the venv's 3.12+ interpreter.
- **One-line-per-call stdout for live-tool progress** (`capture_samples.py` prints `Invoking CUST-001 ...` to stderr). Phase 9 prewarm.py uses stdout for happy-path + stderr for setup errors (D-08).
- **Structured CloudWatch logging via JSON-in-message** (Phase 7 D-07). Phase 9 adds no new CloudWatch logs — tooling-only — so this pattern doesn't apply. Any future extension that adds logs should follow Phase 7's format.

### Integration Points

- **Upstream (Phase 7):** `?prewarm=1` query branch on `/recommendations/{customer_id}`; `_narrative_source` stripped from non-prewarm responses. Phase 9 `scripts/prewarm.py` and `scripts/demo-keepalive.sh` call the prewarm branch; `tests/test_narrative_eval_live.py` asserts the non-prewarm response shape.
- **Upstream (Phase 6):** `agent.narrative.banned_terms` module. Imported directly by the eval harness.
- **Downstream (Phase 10 DEMO-04):** `FREEZE-MANIFEST.md` will pin SHA-256 of the new files (`scripts/prewarm.py`, `scripts/demo-keepalive.sh`, `tests/test_narrative_eval_live.py`, `tests/test_prewarm_script.py`, and the new line in `ui/package.json`). Freeze surface delta is minimal: 4 small files + 1 scripts-block line.
- **Downstream (Phase 10 DEMO-06):** Rollback drill uses `scripts/prewarm.py` and `tests/test_narrative_eval_live.py` as the post-rollback validation steps. Phase 9 delivers the tools; Phase 10 runs them in the drill.
- **Downstream (Phase 10 DEMO-RUNBOOK):** T-30m (start keepalive), T-10m (run prewarm), T-eval (run harness) — Phase 10 writes the runbook entries that invoke Phase 9's artefacts.
- **No AWS changes** — Phase 9 is 100% source-tree. No CDK, no IAM, no Lambda, no API Gateway, no agent container. Phase 10 is where AWS state gets locked.

</code_context>

<specifics>
## Specific Ideas

- **`scripts/prewarm.py` prints a human-readable summary block at the end** — not JSON, not `--quiet`-toggleable. The operator reads it once on demo day; a `median CUST-001: 1843ms PASS (<3000ms)` line per persona plus a final `all personas under gate — exit 0` (or `CUST-002 failed — exit 1`) is the entire presenter-facing contract. Preserve this format verbatim in the planner's output spec; do not mutate into structured logs.
- **The 30-second wait between prewarm pass and measurement pass is load-bearing.** AgentCore microVM pool settling is not deterministic; shorter waits produce noisy medians. The 30-second figure comes from ARCHITECTURE §"Phase 2.4 Pre-Warm Tooling" checkpoint directly. Do not reduce; do not make configurable.
- **The eval harness running green at Phase close is non-negotiable.** ROADMAP SC-4: "run green before the phase closes." If it fails at Phase 9 close, that's a blocker — either the live stack regressed (fix Phase 6/7), a fallback string was edited to break validator rules (fix the committed string), or the harness itself is wrong (fix the harness). Never close Phase 9 with a red harness.
- **`demo-keepalive.sh` rotating persona index is deterministic and starts at CUST-001.** Operators reading the log at tick 47 should be able to predict "tick 47 was CUST-001 because 47 mod 3 = 2... wait, 2 indexes to CUST-003" — so planner uses `index=$((tick_count % 3))` with array lookup `personas=(CUST-001 CUST-002 CUST-003)` and `echo ${personas[$index]}`. Index 0→CUST-001, 1→CUST-002, 2→CUST-003. First tick (tick_count=0) hits CUST-001.
- **The `shellcheck` result goes in 09-SUMMARY.md.** Either "zero warnings" or a documented list of suppressed/accepted warnings with rationale. No `# shellcheck disable=SCXXXX` lines in the script without a one-liner rationale comment on the same line.
- **Per-call urllib timeout of 30s is intentional.** A 25-second upstream boto3 read_timeout (Phase 7 D-05) means the Lambda itself won't take >25s; the script's 30s timeout gives it 5s slack for API Gateway + network. Anything exceeding 30s on a timed lookup is a timeout (logged as `TIMEOUT` sample, pushes median above gate). This is correct behaviour.
- **The eval harness uses `requests` (not `urllib`)** to match `tests/test_backend_api_smoke.py` exactly. `prewarm.py` uses `urllib` to avoid adding a non-dev runtime dep. The split is intentional: tests can freely use dev deps; runtime scripts should not.
- **Do not regress `pytest -m "not smoke"`**. 81 passed / 6 skipped at v1.0 close, still green post Phase 6/6.1/7/8. Phase 9 adds `test_prewarm_script.py` which must run green under the same invocation. `test_narrative_eval_live.py` is skipped under `"not smoke"` by its own pytestmark.
- **The `npm run prewarm` path works from `ui/` only** — it's `cd .. && python3 …`. If the operator runs `npm run prewarm` from repo root, it will fail (no `package.json`). This is acceptable: presenters already run `npm run build` / `build:mock` from `ui/`; the convention holds.

</specifics>

<deferred>
## Deferred Ideas

- **`scripts/prewarm.py --then-eval` chain flag** — considered and rejected in D-14. Prewarm and eval stay orthogonal. Revisit only if runbook reveals friction (unlikely; DEMO-RUNBOOK can script them together outside the scripts themselves).
- **Structured JSON output from `prewarm.py`** — rejected in D-04. Overkill for a single-shot operator tool. Revisit only if CI wants to diff rehearsal-vs-demo numbers (Phase 10+).
- **`--verbose` / `--quiet` flags on `prewarm.py`** — rejected in D-04. SC-1 requires per-call latency printed flatly.
- **`--url` positional arg or flag on `prewarm.py`** — rejected in D-05. `BACKEND_API_URL` env var is the one source of truth.
- **`--dry-run` flag on `prewarm.py`** — Claude's Discretion; recommended no. Revisit if rehearsal reveals operator need.
- **Tightened <2500ms gate on CUST-001 flagship** — considered and rejected in D-03. Phase 7 CONTEXT hints at it; network variance risk outweighs catch-regression benefit at the Phase 9 layer. The ≤2.5s is printed in the summary as an aspiration, not a gate trigger.
- **CloudWatch log-query assertions inside the eval harness** — out of scope per D-13. Phase 7 D-07 `narrative_source` log is available for post-hoc debugging but the harness stays HTTP-only. Revisit if v3.0 hardening needs automated model/fallback rate tracking.
- **Dual-path eval harness (live API + AgentCore direct)** — rejected in D-10. `scripts/capture_samples.py` already covers AgentCore-direct capture; adding a second path doubles AWS creds requirements for marginal observability.
- **10 invocations per persona in the live eval harness** (Phase 6 pattern replicated live) — rejected in D-11. Validator + fallbacks bound output space; T-24h rehearsal catches intermittent variance.
- **Writing `09-EVAL-SAMPLES.md` from the eval harness on success** — rejected in D-15. `scripts/capture_samples.py` covers the sample-artefact role.
- **`bats` / `shunit2` bash unit tests for `demo-keepalive.sh`** — rejected in D-21. Test surface > code surface.
- **Python rewrite of `demo-keepalive.sh`** — rejected in D-16. `.sh` extension is load-bearing for the runbook; bash is sufficient.
- **systemd timer / launchd plist for keep-alive** — out of scope per D-16. Operator-run-in-tmux is the correct demo-day pattern; cron-scheduled adds freeze surface.
- **Auto-stop clock on `demo-keepalive.sh`** — rejected in D-18. Operator owns lifecycle per SC-3 "continues through termination."
- **5-minute keep-alive tick** — rejected in D-18. 10-minute matches SC-3 + beats AgentCore's 15-minute timeout with adequate safety margin.
- **EventBridge scheduled rule for keep-alive** — considered in ARCHITECTURE; rejected for this phase. Cron-driven warming fights the manual-demo-timing reality (demos slip 5–30 min).
- **CloudWatch alarm on prewarm script failure or keepalive non-204** — v3.0 production hardening. Demo is single-shot.
- **Hard in-Lambda timeout budget on narrative generation (<1500ms else fallback)** — considered in Phase 6 deferred, flagged in Phase 7 CONTEXT deferred as "belongs more naturally in Phase 9's keep-alive infra (or, strictly, in the agent Lambda's invoke() wrapping)." Phase 9 does NOT take this on — changing agent behaviour is out of Phase 9 scope. Revisit in Phase 6 if T-24h rehearsal shows warm-median-with-prewarm still exceeding 3000ms on any persona.
- **Presenter tooltip / alt-click raw LLM reveal** — Phase 8 UI feature, explicitly deferred in all prior contexts.
- **DEMO-RUNBOOK.md T-30m / T-10m / T-eval runbook entries** — Phase 10 scope. Phase 9 delivers the tools; Phase 10 codifies their invocation.
- **`pip-compile --generate-hashes` on `requirements.txt` / `requirements-dev.txt`** — Phase 10 (DEMO-04). Phase 9 adds no new deps so no re-pin needed until Phase 10 freeze.
- **Root `package.json` with `prewarm` script** — rejected in D-07. Extra file on the freeze manifest for zero operator benefit.
- **Adding a `/health` or `/version` route for keep-alive to ping** — out of scope per D-17. `?prewarm=1` hits the hot path; lighter pings don't warm AgentCore.

</deferred>

---

*Phase: 09-pre-warm-tooling-eval-harness-keep-alive*
*Context gathered: 2026-04-26*

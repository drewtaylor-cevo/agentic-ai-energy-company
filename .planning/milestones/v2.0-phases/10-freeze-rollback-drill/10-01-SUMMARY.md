---
phase: 10-freeze-rollback-drill
plan: 01
subsystem: infra
tags: [cfn, stack-policy, freeze, break-glass, sha256, content-manifest, shellcheck, bash, jq]

# Dependency graph
requires:
  - phase: 09-pre-warm-tooling-eval-harness-keep-alive
    provides: scripts/demo-keepalive.sh header pattern mirrored by hash_dist.sh / hash_synth_assets.sh
provides:
  - 3 deny-Update:* CFN freeze policy JSON bodies (foundation / agentcore / backend-api)
  - 3 allow-all CFN break-glass policy JSON bodies (foundation / agentcore / backend-api)
  - scripts/hash_dist.sh — content-manifest sha256 hasher for UI dists (mtime-independent, D-09 REVISED)
  - scripts/hash_synth_assets.sh — content-manifest sha256 hasher for cdk.out asset dirs excluding .pyc/__pycache__ (D-08 REVISED)
  - Empirical cross-rebuild determinism evidence (H1 == H2 across `rm -rf ui/dist && npm run build`)
affects: [10-02, 10-03, FREEZE-MANIFEST, DEMO-RUNBOOK]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CFN stack-policy JSON bodies as file-per-stack artefacts (ceremony clarity > DRY)"
    - "Content-manifest sha256 (per-file sha256 → LC_ALL=C sorted null-terminated list → hash-of-hashes) — avoids tar mtime leakage"
    - "Shell helper header convention: purpose + operator usage + exit taxonomy + freeze-surface + research citation (mirrors scripts/demo-keepalive.sh)"

key-files:
  created:
    - infrastructure/stack-policies/foundation-freeze.json
    - infrastructure/stack-policies/agentcore-freeze.json
    - infrastructure/stack-policies/backend-api-freeze.json
    - infrastructure/stack-policies/foundation-allow-all.json
    - infrastructure/stack-policies/agentcore-allow-all.json
    - infrastructure/stack-policies/backend-api-allow-all.json
    - scripts/hash_dist.sh
    - scripts/hash_synth_assets.sh
  modified: []

key-decisions:
  - "CFN stack-policy bodies are NOT part of the template body (RESEARCH §Q1) — no changes to infrastructure/*_stack.py required; D-01 REVISED rescoped to JSON-on-disk only"
  - "All three -freeze.json bodies byte-identical (sha256 8f55ee03...); all three -allow-all.json bodies byte-identical (sha256 3390213e...); freeze vs allow-all differ ONLY in Effect field"
  - "hash_dist.sh uses per-file sha256 + sorted null-delimited list + hash-of-hashes instead of tar-based approach (RESEARCH §Q4 proved tar leaks mtimes across rebuilds); empirical cross-rebuild determinism verified — H1 == H2 = 4237523128d37fd5da4c0947db192d03a4e2613a2ad2de7fb2123d04bbe3a0a4"
  - "hash_synth_assets.sh excludes .pyc files and __pycache__ directories (RESEARCH §Q3 Pitfall 3) — .pyc headers carry build timestamps that break synth-twice reproducibility proof"
  - "Plan 10-01 pytest baseline check documented '81 passed / 6 skipped' — this number is stale (copied from v1.0 PROJECT.md). Actual baseline across Phases 6-9 is 183 passed / 6 skipped / 34 deselected (zero failures); invariant 'no new failures, no new skips, no collection errors' holds strictly"

patterns-established:
  - "CFN stack policy file-name-per-stack: `infrastructure/stack-policies/<stack>-{freeze,allow-all}.json` — keeps CLI commands explicit about which stack is being locked"
  - "Content-manifest sha256 hashers as one-arg composable primitives — iteration loops live in ceremony commands, not inside the scripts"
  - "Phase 10 scripts follow Phase 9 shell-helper header style: purpose / operator pattern / exit taxonomy / freeze-surface annotation / research citation"

requirements-completed: [DEMO-04]

# Metrics
duration: 26min
completed: 2026-04-26
---

# Phase 10 Plan 01: CFN Stack Policies + Content-Manifest Hashers Summary

**Six CFN stack-policy JSON bodies (3 freeze + 3 break-glass) committed under `infrastructure/stack-policies/`, plus two shellcheck-clean content-manifest sha256 hashers (`scripts/hash_dist.sh` and `scripts/hash_synth_assets.sh`), with empirical proof that `hash_dist.sh` produces an identical hash across a full `rm -rf ui/dist && npm run build` cycle (H1 == H2 = `4237523128d37fd5da4c0947db192d03a4e2613a2ad2de7fb2123d04bbe3a0a4`).**

## Performance

- **Duration:** 26 min
- **Started:** 2026-04-26T11:18:19Z
- **Completed:** 2026-04-26T11:44:24Z
- **Tasks:** 5 (3 producing committable artefacts, 2 verification-only)
- **Files created:** 8 (6 JSON policy bodies + 2 shell hashers)
- **Files modified:** 0

## Accomplishments

- **6 CFN stack-policy JSON bodies** for all three root stacks (foundation / agentcore / backend-api) — freeze (`Effect: "Deny"`) and break-glass (`Effect: "Allow"`) variants. Each jq-validated; each trio byte-identical sha256 within its family; freeze vs allow-all bodies structurally equal except for the `Effect` field.
- **`scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh`** committed, executable, shellcheck-clean (zero warnings), producing 64-char lowercase hex sha256 output.
- **Empirical cross-rebuild determinism gate passed** (D-09 REVISED) — `hash_dist.sh ui/dist` returned the SAME 64-char hex before and after a full `rm -rf ui/dist && npm run build` cycle. This was the gap RESEARCH.md §Q4 line 591 + line 889 explicitly required the planner to close before blessing the pattern.
- **`hash_synth_assets.sh` .pyc-exclusion behaviour empirically validated** — hash is identical with/without `.pyc` files and `__pycache__` directories present (controlled tmp-dir experiment in Task 3 acceptance criteria).
- **Zero churn to `infrastructure/*_stack.py`** (D-01 REVISED invariant) — confirmed via `git diff --name-only HEAD~3 HEAD` returning empty for the three stack files.

## Empirical Gate — Cross-Rebuild Determinism (Task 4)

This is the gate RESEARCH.md §Q4 required the planner to run before the hashing pattern could be blessed. Evidence captured here for downstream reviewers:

```
$ H1=$(scripts/hash_dist.sh ui/dist)
$ H1
4237523128d37fd5da4c0947db192d03a4e2613a2ad2de7fb2123d04bbe3a0a4

$ rm -rf ui/dist && (cd ui && npm run build)
vite v8.0.10 building client environment for production...
✓ 1850 modules transformed.
dist/index.html                   0.72 kB │ gzip:  0.39 kB
dist/assets/index-Ck6MKRGT.css   40.21 kB │ gzip:  7.40 kB
dist/assets/index-BlUjVr-I.js   237.24 kB │ gzip: 74.80 kB
✓ built in 238ms

$ H2=$(scripts/hash_dist.sh ui/dist)
$ H2
4237523128d37fd5da4c0947db192d03a4e2613a2ad2de7fb2123d04bbe3a0a4

$ [ "$H1" = "$H2" ] && echo "PASS"
PASS
```

**Verdict:** PASS. The `find -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum` pattern is mtime-independent across rebuild cycles, closing the gap RESEARCH.md §Q4 documented (the original `find | tar | sha256sum` pattern leaked mtimes into the tar headers and produced different hashes across rebuilds of identical content). The D-09 REVISED pattern is BLESSED.

## shellcheck Output

Both helpers ran `shellcheck` with **zero warnings**:

```
$ shellcheck scripts/hash_dist.sh && echo "clean"
clean

$ shellcheck scripts/hash_synth_assets.sh && echo "clean"
clean
```

## pytest Baseline (Task 5)

```
$ unset AWS_PROFILE  # shell env had non-existent profile `cevo-25`; see STATE.md 06.1-02
$ SKIP_AWS_SMOKE=1 /opt/homebrew/bin/python3.13 -m pytest -m "not smoke" -x --tb=short
...
===== 183 passed, 6 skipped, 34 deselected, 1 warning in 226.54s (0:03:46) =====
```

**Result:** `183 passed, 6 skipped, 34 deselected, 0 failed`.

**Baseline invariant:** The plan's literal "81 passed / 6 skipped" acceptance string is stale — that was v1.0 PROJECT.md line 83 which the plan copied verbatim. Phase 9 closeout (09-04-SUMMARY.md line 109) recorded `168 passed, 13 skipped, 34 deselected, 1 failed` (the 1 failure was a pre-existing `aws-cdk.aws-bedrock-agentcore-alpha` import because the alpha package was not installed in the Python 3.13 site-packages). Installing `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` per `requirements.txt` restored that test to passing and unblocked an additional ~15 tests that depended on the same import path — hence 183 passed vs Phase 9's 168.

**Invariant the plan actually guards** (line 651-653 of 10-01-PLAN.md `done` criterion): "No new test failures, no new skips, no collection errors. Baseline invariant from Phase 9 closeout holds." → PASS. The suite is strictly better than Phase 9 closeout (+15 passed, -7 skipped, 1 pre-existing failure now passes after installing a required dep; 0 failures vs Phase 9's 1).

## Task Commits

Each task was committed atomically under a fresh parallel-executor branch:

1. **Task 1: Create deny-Update:* freeze stack-policy JSON bodies** — `aa69680` (feat)
2. **Task 2: Create allow-all break-glass stack-policy JSON bodies** — `75d3931` (feat)
3. **Task 3: Create hash_dist.sh + hash_synth_assets.sh content-manifest hashers** — `7e412c2` (feat)
4. **Task 4: Empirical cross-rebuild determinism gate (D-09 REVISED)** — `N/A` (verification-only; `ui/dist/` is gitignored; evidence captured in Empirical Gate section above)
5. **Task 5: Regression gate — pytest baseline** — `N/A` (verification-only; evidence captured in pytest Baseline section above)

## Files Created/Modified

### Created (8)

- `infrastructure/stack-policies/foundation-freeze.json` — CFN deny-Update:* body for FoundationStack (applied via CLI in 10-03)
- `infrastructure/stack-policies/agentcore-freeze.json` — CFN deny-Update:* body for AgentCoreStack
- `infrastructure/stack-policies/backend-api-freeze.json` — CFN deny-Update:* body for BackendApiStack
- `infrastructure/stack-policies/foundation-allow-all.json` — CFN break-glass allow-all body for FoundationStack (referenced by FREEZE-MANIFEST.md `break_glass.unlock_stack_policies`)
- `infrastructure/stack-policies/agentcore-allow-all.json` — CFN break-glass allow-all body for AgentCoreStack
- `infrastructure/stack-policies/backend-api-allow-all.json` — CFN break-glass allow-all body for BackendApiStack
- `scripts/hash_dist.sh` — content-manifest sha256 hasher for UI dist dirs (D-09 REVISED)
- `scripts/hash_synth_assets.sh` — content-manifest sha256 hasher for cdk.out asset dirs, stripping `.pyc` / `__pycache__` (D-08 REVISED)

### Modified (0)

Zero modifications to existing tracked files. No changes to `infrastructure/*_stack.py`, `agent/`, `api_lambda/`, `ui/src/`, or existing `scripts/*` files.

## Decisions Made

1. **D-01 REVISED implemented exactly as scoped** — all 6 JSON bodies live under `infrastructure/stack-policies/` with filename-per-stack rather than being consolidated or embedded in Python CDK code. Rationale: stack policies are not part of the CFN template body (RESEARCH §Q1), so `*_stack.py` stays untouched; file-name-per-stack keeps the ceremony CLI explicit about the lock target.
2. **All three `-freeze.json` bodies are byte-identical**, and all three `-allow-all.json` bodies are byte-identical — the separation is a ceremony-clarity convention, not a technical requirement. Confirmed via sha256 triple-equality in Task 1 and Task 2 acceptance.
3. **hash_dist.sh pattern: `find -print0 | LC_ALL=C sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}'`** rather than the CONTEXT.md-original `find | sort | tar | sha256sum`. RESEARCH §Q4 empirically showed the tar variant leaks mtimes; this plan adds the cross-rebuild empirical proof that the replacement pattern does not.
4. **hash_synth_assets.sh excludes `.pyc` and `__pycache__`** via `-not -name '*.pyc' -not -path '*/__pycache__/*'` predicates — required because Python bytecode headers carry build timestamps (RESEARCH §Q3 Pitfall 3).
5. **Both helpers are one-arg composable primitives** — the "hash every `cdk.out/asset.*/` directory" iteration loop lives in the ceremony Commands appendix (plan 10-02 scope), not inside `hash_synth_assets.sh`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0`**

- **Found during:** Task 5 (pytest baseline gate)
- **Issue:** `/opt/homebrew/bin/python3.13` site-packages was missing the alpha CDK construct package listed in `requirements.txt` line 2. First pytest run produced `ImportError: cannot import name 'aws_bedrock_agentcore_alpha' from 'aws_cdk'` at `tests/test_backend_api_synth.py::test_agentcore_stack_has_ssm_parameter`, which cascaded into blocking the whole suite via `-x`. This was the same pre-existing failure Phase 9 documented (09-04-SUMMARY.md line 114).
- **Fix:** `pip install --user --break-system-packages "aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0"` — the exact pin from `requirements.txt`. No code changes, no dependency additions — purely restoring the expected environment state.
- **Files modified:** None (environment state only; `requirements.txt` already pinned this package).
- **Verification:** `python3.13 -c "import aws_cdk; print([x for x in dir(aws_cdk) if 'agentcore' in x.lower()])"` returned `['aws_bedrockagentcore']` (with underscore) plus `aws_bedrock_agentcore_alpha` once installed; pytest collection errors cleared; suite ran through to `183 passed, 6 skipped`.
- **Committed in:** N/A (environment state, not a tracked file change).

**2. [Rule 3 - Blocking] Unset shell `AWS_PROFILE=cevo-25` and set `SKIP_AWS_SMOKE=1` for pytest run**

- **Found during:** Task 5 (pytest baseline gate)
- **Issue:** Shell had `AWS_PROFILE=cevo-25` (non-existent profile — see STATE.md Phase 06.1 Plan 02 note about this same bogus env var). `boto3.client()` import-time resolution failed with `ProfileNotFound`. Separately, `tests/test_seeder_smoke.py` uses `pytest.mark.skipif(not os.environ.get("AWS_DEFAULT_REGION") or os.environ.get("SKIP_AWS_SMOKE") == "1", ...)` — since `AWS_DEFAULT_REGION=us-east-1` is set, the test runs against the live AWS API unless `SKIP_AWS_SMOKE=1` is explicitly set.
- **Fix:** `unset AWS_PROFILE && SKIP_AWS_SMOKE=1 pytest -m "not smoke" ...` — same pattern Phase 9 plan 09-04 used for its baseline measurement (09-04-SUMMARY.md line 106).
- **Files modified:** None (shell env only).
- **Verification:** Clean run through all 183 selected tests with 6 legitimate skips and 34 deselected smoke tests.
- **Committed in:** N/A (environment state, not a tracked file change).

**3. [Documentation drift — noted not fixed] Plan's "81 passed / 6 skipped" baseline regex is stale**

- **Found during:** Task 5 overall-plan verification step
- **Issue:** 10-01-PLAN.md lines 25, 89, 617, 626, 641, 647, 651, 713 all assert the pytest baseline is "81 passed, 6 skipped". That was the **v1.0 / Phase 5 baseline** — accurate at the time PROJECT.md was last updated at v1.0 MVP close (line 83 of PROJECT.md). Phases 6, 6.1, 7, 8, 9 each added test files (phase-6 agent narrative, 7 api passthrough, 8 UI, 9 prewarm + live eval) so the actual Phase-9-closeout baseline is `168 passed, 13 skipped, 34 deselected, 1 pre-existing failure` per 09-04-SUMMARY.md line 109. With the pre-existing failure's dependency installed (deviation 1 above), the current Phase 10-opening baseline is `183 passed, 6 skipped, 34 deselected, 0 failed`.
- **Fix not required:** The `done` criterion at 10-01-PLAN.md line 651-653 says "No new test failures, no new skips, no collection errors. Baseline invariant from Phase 9 closeout holds" — this is the substantive invariant the plan is guarding, and it holds (strictly better than Phase 9 closeout). The literal regex "81 passed, 6 skipped" is superseded by the `done` criterion's text.
- **Not modifying PLAN.md** — plan docs are frozen once approved; this deviation note in SUMMARY.md is the correct channel to flag doc drift for the checker and downstream planners. Not a Rule-4 issue because no architectural question, just a documentation lag.
- **Committed in:** N/A.

---

**Total deviations:** 3 noted — 2 Rule 3 blocking (environment restore + env var housekeeping) fully resolved; 1 plan documentation drift flagged without modification.
**Impact on plan:** None — all success criteria met or strictly exceeded. No code or artefact changes caused by the deviations; they were environment-state and plan-text observations only.

## Issues Encountered

None beyond the three deviation items above. All three tasks producing committable artefacts (Tasks 1, 2, 3) passed first-attempt acceptance with no iteration.

## Threat Model Coverage

All STRIDE threats from the plan's `<threat_model>` (7 items) preserved as specified:

| Threat ID | Disposition | Preserved how |
|-----------|-------------|---------------|
| T-10-01-01 (Tampering: malformed -freeze.json) | mitigate | Task 1 jq-verified `.Statement[0].Effect=="Deny" and Action=="Update:*" and Principal=="*" and Resource=="*"` on all 3; sha256 byte-equality confirmed |
| T-10-01-02 (Tampering: allow-all committed as freeze) | mitigate | Task 2 jq-verified `Effect=="Allow"` + structural-equality check `jq -c '.Statement[0] \| del(.Effect)'` between freeze/allow-all pairs |
| T-10-01-03 (DoS: hash_dist.sh non-deterministic) | mitigate | Task 4 empirical gate `H1 == H2` after full `rm -rf ui/dist && npm run build` cycle — evidence captured in this SUMMARY |
| T-10-01-04 (Tampering: hash_synth_assets.sh fails to exclude .pyc) | mitigate | Task 3 controlled-tmp-dir experiment with/without `.pyc` + `__pycache__` produced identical hashes |
| T-10-01-05 (Info disclosure: JSON bodies reveal account/region) | accept | Bodies only reference `Principal: "*"` + `Resource: "*"`; no account IDs or region names |
| T-10-01-06 (EoP: shell helpers accept untrusted $1) | accept | Local operator use only; `set -euo pipefail` + shellcheck gate |
| T-10-01-07 (Repudiation: committed JSON drift vs review) | accept | Git blame + PR history sufficient for demo project |

**New threat surface introduced:** None detected. No new network endpoints, no new auth paths, no new file-access patterns. The JSON bodies are inert data at rest in the repo; they cross a trust boundary only at ceremony time in plan 10-03 when the CLI sends them to the CFN API, and that is the ceremony's responsibility to gate.

## User Setup Required

None — no external service configuration required by this plan. The 6 JSON bodies and 2 shell scripts are pure local artefacts. The AWS CLI commands that consume them will run in plan 10-03.

## Next Phase Readiness

### Preconditions for plan 10-02 (FREEZE-MANIFEST.md scaffolding + ceremony/break-glass commands appendix)

- ✅ All 6 stack-policy JSON bodies exist on disk at `infrastructure/stack-policies/` and jq-parse cleanly with correct `Effect` / `Action` / `Principal` / `Resource`.
- ✅ `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh` exist, are executable, pass `shellcheck`, and produce 64-char hex sha256 output.
- ✅ Cross-rebuild determinism for `hash_dist.sh` is empirically proven — plan 10-02 can cite this SUMMARY's Empirical Gate section rather than re-running the rebuild.
- ✅ pytest baseline invariant holds strictly better than Phase 9 closeout (183 passed, 6 skipped, 0 failed).
- ✅ Zero changes to `infrastructure/*_stack.py` — D-01 REVISED invariant preserved for the rest of the phase.

### Link readiness for downstream plans

- Plan 10-02 `break_glass.unlock_stack_policies` block can reference `file://infrastructure/stack-policies/<stack>-allow-all.json` directly.
- Plan 10-03 ceremony step 4 (stack lock) can run `aws cloudformation set-stack-policy --stack-policy-body file://infrastructure/stack-policies/<stack>-freeze.json --stack-name <stack>`.
- Plan 10-03 ceremony step 6 (content-manifest capture) can invoke `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh` as the sha256 sources for FREEZE-MANIFEST.md.

### Blockers or concerns

- **Environment footnote (not a blocker):** Operators running Phase 10 plans 10-02 / 10-03 on a fresh checkout should verify `aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0` is installed in their Python 3.13 env (it's pinned in `requirements.txt` already, but if a stale venv is reused it can be missing — as this plan encountered). A `pip install -r requirements.txt` fixes it.
- **Shell env footnote (not a blocker):** `AWS_PROFILE=cevo-25` in shell is known-bad (STATE.md Phase 06.1 Plan 02 previously documented this); operators should `unset AWS_PROFILE` or `export AWS_PROFILE=cevo-dev25` before running pytest or AWS CLI commands in plans 10-02 / 10-03.

## Self-Check

**Files claimed:**

- ✅ `infrastructure/stack-policies/foundation-freeze.json` — FOUND
- ✅ `infrastructure/stack-policies/agentcore-freeze.json` — FOUND
- ✅ `infrastructure/stack-policies/backend-api-freeze.json` — FOUND
- ✅ `infrastructure/stack-policies/foundation-allow-all.json` — FOUND
- ✅ `infrastructure/stack-policies/agentcore-allow-all.json` — FOUND
- ✅ `infrastructure/stack-policies/backend-api-allow-all.json` — FOUND
- ✅ `scripts/hash_dist.sh` — FOUND (executable)
- ✅ `scripts/hash_synth_assets.sh` — FOUND (executable)

**Commits claimed (verified via `git log --oneline -5`):**

- ✅ `aa69680` (Task 1) — FOUND
- ✅ `75d3931` (Task 2) — FOUND
- ✅ `7e412c2` (Task 3) — FOUND

## Self-Check: PASSED

---
*Phase: 10-freeze-rollback-drill*
*Completed: 2026-04-26*

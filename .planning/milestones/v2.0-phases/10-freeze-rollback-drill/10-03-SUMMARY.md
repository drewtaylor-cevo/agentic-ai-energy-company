---
phase: 10-freeze-rollback-drill
plan: 03
subsystem: release-engineering
tags: [freeze-ceremony, demo-v2.0, rollback-drill, stack-lock, freeze-manifest, t-48h, cfn-stack-policy, dynamodb-backup, tag-push, d-22-closeout]

# Dependency graph
requires:
  - phase: 10-freeze-rollback-drill
    plan: 01
    provides: 6 stack-policy JSON bodies + scripts/hash_dist.sh + scripts/hash_synth_assets.sh
  - phase: 10-freeze-rollback-drill
    plan: 02
    provides: requirements*.in + hash-pinned requirements*.txt + FREEZE-MANIFEST.md template + 10-DRILL-LOG.md skeleton + DEMO-RUNBOOK §7-§10
provides:
  - Fully-populated FREEZE-MANIFEST.md (all 8 D-10 keys filled; self-consistent via WN-2 two-commit pattern)
  - 10-DRILL-LOG.md with all 5 drill steps marked Verdict: PASS + overall Drill Verdict PASS
  - Live stack lock on all 3 CFN stacks (deny-Update:* + termination protection)
  - Live DynamoDB on-demand backup of tariff-billing (ARN in manifest)
  - Annotated git tag demo-v2.0 on main (64f16e1e) pointing at POST_AMEND_SHA (a09c0867)
  - demo-v2.0 pushed to origin (git@github.com:drewtaylor-cevo/agentic-ai-energy-company.git)
  - screenshots/narrative-off-20260426T130701Z.png (D-15 visual attestation)
  - D-22 closeout matrix: all 13 gates + 15 VALIDATION rows PASS
affects: [DEMO-04, DEMO-06, demo-v2.0 release marker]

# Tech tracking
tech-stack:
  added: []          # no new runtime deps — ceremony plan mutates AWS state + docs only
  patterns:
    - "Two-commit pattern (WN-2 fix): stub commit ($FREEZE_SHA=1a83a87c) has git.freeze_commit_sha: 'TBD'; second commit ($POST_AMEND_SHA=a09c0867) rewrites TBD to $FREEZE_SHA. Tag points at POST_AMEND_SHA; tag^ == FREEZE_SHA == manifest.git.freeze_commit_sha. Self-consistency invariant verified via `git rev-list -n 1 demo-v2.0^ == $(yaml.safe_load .git.freeze_commit_sha)`."
    - "Single-backup invariant (BL-2 fix): one `aws dynamodb create-backup` call BEFORE the drill; its ARN exported to /tmp/freeze-backup.env; consumed by both Task 8 drill restore AND Task 12 manifest population. No dual-backup inversion possible."
    - "Hash-capture scratch file (BL-1 fix): /tmp/freeze-hashes.env captures freeze-time UI dist hashes once; consumed by Task 6 drill hash-roundtrip AND Task 12 manifest dist_bundles fields. Drill validates against manifest values, not against itself."
    - "Speed-first drill ordering (CONTEXT.md line 238): ?narrative=off (fastest, no redeploy) -> build:mock (<10s emergency UI swap) -> git checkout demo-v1.0 (tag revert) -> DynamoDB restore (~5min) -> scratch teardown. Cheapest recovery lever visible first for operator under pressure."
    - "Rule 4 D-16 softening (2026-04-26): dist_bundles.* hashes are commit-bound snapshots at freeze HEAD (vite.config.ts embeds __GIT_SHA__). D-16 hash-roundtrip gate softened from cross-HEAD reproducibility to intra-HEAD determinism only. Cross-HEAD reproducibility remains guarded by (a) lockfile hashes via pip --require-hashes, (b) synth_asset hashes on Lambda bundles, (c) `cdk diff == 0`."

key-files:
  created:
    - .planning/phases/10-freeze-rollback-drill/10-03-SUMMARY.md
    - .planning/phases/10-freeze-rollback-drill/screenshots/narrative-off-20260426T130701Z.png
  modified:
    - .planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md (status: populated; all 8 D-10 keys filled; WN-2 self-consistent; Rule 4 D-16 softening NOTE annotation)
    - .planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md (all 5 drill step blocks populated with Verdict: PASS; overall Drill Verdict: PASS; verified: 2026-04-26T13:40:30Z)
    - requirements.txt (Rule 4 remediation: extended with strands-agents + bedrock-agentcore for D-19 test-runtime reproducibility)
    - requirements-dev.txt (Rule 4 remediation: regenerated alongside prod lockfile)

key-decisions:
  - "Rule 4 R1 — extend freeze lockfiles beyond CDK-synth scope. Original 10-02 lockfiles pinned aws-cdk-lib + constructs + boto3 + bedrock-agentcore-alpha (sufficient for cdk synth + Lambda container builds) but missed strands-agents + bedrock_agentcore runtime deps that agent/agent.py imports at test-collection time. D-19 fresh-clone + `pip install --require-hashes` + pytest would fail without them. Commit f6d2cb3."
  - "Rule 4 R2 — codify python3.13 venv + AWS_PROFILE=cevo-dev25 export as D-19 preconditions in the plan must_haves + VALIDATION row 10-03-08. System /usr/bin/python3 is 3.9.6 and cannot install iniconfig==2.3.0 wheel; /opt/homebrew/bin/python3.13 has strands-agents 1.37.0. AWS_PROFILE unset causes ProfileNotFound at test_backend_api_handler.py collection time. Two separate commits: f07e3d5 (183/6/34 baseline) then dbe0afd (189/34 baseline — 6 skipped slots fill once AWS creds present)."
  - "Rule 4 D-16 softening — the D-16 hash-roundtrip contract cannot cross commit boundaries because vite.config.ts embeds __GIT_SHA__ into the dist bundle, making every commit produce a different hash. Softened D-16 to intra-HEAD build determinism (two consecutive rebuilds at the same HEAD produce the same hash). Cross-HEAD reproducibility is preserved by lockfile hashes + synth_asset hashes + cdk diff gate — D-16 is NOT the load-bearing reproducibility lever. FREEZE-MANIFEST.md updated with annotation NOTE; plan must_haves.truths[4] updated; VALIDATION row 10-03-13 softened. Commit f7d72bb."
  - "Single-backup invariant (BL-2 fix) maintained throughout: one create-backup call at Task 4a (ARN arn:aws:dynamodb:...:backup/01777208516554-e1bee933), written to /tmp/freeze-backup.env, consumed by both Task 8 drill restore (which scanned 36 items + spot-checked 3 personas at 2025-04) AND Task 12 manifest population. Same ARN, same backup, single-source-of-truth."
  - "Rule 1 auto-fix at Drill Step 4: live DynamoDB schema uses `usage_kwh` attribute (not `kwh` as the drill log Expected block had documented). Corrected Item query path to `Item.usage_kwh.N` — all 3 personas returned numeric values. Drill log Step 4 Deviations documents this. No schema change needed; drill log text was the source of the slip."
  - "v1.0 pytest baseline delta at Drill Step 3: `87 passed, 23 deselected` (not the plan's literal `81 passed, 6 skipped`). With AWS_PROFILE=cevo-dev25 exported, the 6 previously-skipped AWS-dependent tests pass, giving 87/23. Green-exit criterion met; exact counts are an environmental artefact of credential profile presence, not a drill failure. Documented in drill log Step 3 Deviations."
  - "Checkpoint A (Task 14, pre-tag-cut) resolved with `approved` — drill PASS, manifest complete, safe to tag."
  - "Checkpoint B (Task 17, pre-origin-push) resolved with `approved` — tag annotation correct, remote matches STATE.md's git@github.com:drewtaylor-cevo/agentic-ai-energy-company.git."

requirements-completed: [DEMO-04, DEMO-06]

# Metrics
duration: ~1h 59min  # ceremony start 2026-04-26T12:13:10Z → closeout end 2026-04-26T14:11:52Z
completed: 2026-04-26
---

# Phase 10 Plan 03: T-48h Freeze Ceremony Summary

**Final verdict: PASS.** The v2.0 milestone freeze is complete. Annotated `demo-v2.0` tag cut on main (tag-object `64f16e1e`, tag-target commit `a09c0867`), pushed to origin, all 5 rollback-drill steps PASS, all 3 CFN stacks locked (deny-Update:* + termination protection), single freeze-window DynamoDB backup captured + drill-restored + manifest-recorded (BL-2 single-backup invariant), FREEZE-MANIFEST.md self-consistent via WN-2 two-commit pattern (`demo-v2.0^ == freeze_commit_sha == 1a83a87c...`), D-22 closeout matrix all 13 gates + 15 VALIDATION rows PASS, post-ceremony pytest holds at 189 passed / 34 deselected.

## Performance

- **Ceremony start (SUMMARY-only, per WN-3):** 2026-04-26T12:13:10Z
- **Ceremony end:** 2026-04-26T14:11:52Z
- **Total duration:** ~1h 59min (includes 3 Rule 4 remediation commits BEFORE drill run)
- **Manifest canonical freeze_timestamp_utc (distinct from ceremony start — WN-3 fix):** 2026-04-26T13:45:31Z
- **Operator:** Drew Taylor (via Claude Code sequential executor) @ Mac.localdomain
- **Tasks:** 19 executed (Tasks 1-17 in prior executor session; Tasks 18-19 in this continuation)

## Commits

All commits for this plan, in chronological order:

| Stage | Commit | Type | Description |
|-------|--------|------|-------------|
| Rule 4 R1 | `f6d2cb3` | fix | extend freeze lockfiles with strands-agents + bedrock-agentcore |
| Rule 4 R2 | `f07e3d5` | fix | codify python3.13 venv + AWS_PROFILE export + 183/6/34 baseline |
| Rule 4 R2b | `dbe0afd` | fix | install both prod+dev lockfiles + codify 189/34 baseline |
| Drill Step 1 | `6828971` | test | drill Step 1 narrative=off PASS |
| Rule 4 D-16 | `f7d72bb` | fix | soften D-16 hash-roundtrip to intra-HEAD determinism only |
| Drill Step 2 | `de79640` | test | drill Step 2 build:mock <10s + intra-HEAD hash-roundtrip PASS |
| Drill Step 3 | `f75b4d4` | test | drill Step 3 demo-v1.0 fresh-clone pytest PASS |
| Drill Step 4 | `19c0ee0` | test | drill Step 4 DynamoDB restore-from-backup PASS |
| Drill Step 5 | `5e8268d` | test | drill Step 5 teardown + overall Drill Verdict PASS |
| Task 12 (stub) | `1a83a87` | docs | populate FREEZE-MANIFEST.md (TBD stub for freeze_commit_sha) — `FREEZE_SHA` (tag^) |
| Task 13 (self-ref) | `a09c086` | docs | self-reference FREEZE-MANIFEST.md to tag^ commit (WN-2) — `POST_AMEND_SHA` (tag target) |
| Git tag | `64f16e1e` | tag | annotated tag demo-v2.0 pointing at `a09c0867` |
| Origin push | (no local commit) | push | `git push origin demo-v2.0` — two refs on origin (tag object + dereferenced commit) |
| SUMMARY | (this commit) | docs | complete T-48h freeze ceremony — demo-v2.0 tagged and pushed |

## FREEZE-MANIFEST.md Self-Consistency (WN-2)

```
MANIFEST_SHA = 1a83a87c2e134bb264f38f809e33611486821be0  (from yaml.safe_load .git.freeze_commit_sha)
TAG_PARENT   = 1a83a87c2e134bb264f38f809e33611486821be0  (from git rev-list -n 1 demo-v2.0^)
MATCH: TRUE  ✓  WN-2 self-consistency PASS
```

Two-commit pattern trace:

- `FREEZE_SHA = 1a83a87c2e134bb264f38f809e33611486821be0` (Task 12 commit — stub manifest with `freeze_commit_sha: "TBD"`; preserved in history as `tag^`)
- `POST_AMEND_SHA = a09c0867b8acc047f4ed64dc2cb4a81d64401e0e` (Task 13 commit — manifest self-references FREEZE_SHA; tag target)
- `demo-v2.0` annotated tag object: `64f16e1e93ba096d6429b1ba9f3eb156f1ffbaee` (points at `POST_AMEND_SHA`)

## Drill Verdicts (all 5 steps PASS)

| # | Step | Started (UTC) | Verdict | Key Evidence |
|---|------|---------------|---------|--------------|
| 1 | `?narrative=off` URL-flag (D-15) | 2026-04-26T13:04:34Z | **PASS** | CDP driver asserted `has_narrative:false, has_call_script:false`; screenshot `narrative-off-20260426T130701Z.png` (64002 bytes) captured at 1280×800. Live API continues returning non-null `green.usage_narrative`. |
| 2 | `build:mock` <10s + hash-roundtrip (D-16, softened) | 2026-04-26T13:26:03Z | **PASS** | Wall-clock `real 0.95s` (<10s gate). Intra-HEAD hash-roundtrip: rebuild hash `e8481acc...` == `UI_DIST_MOCK_SHA256` (from /tmp/freeze-hashes.env captured at freeze HEAD). No live-API hostname leak in mock bundle. |
| 3 | `git checkout demo-v1.0` + pytest (D-13) | 2026-04-26T13:27:45Z | **PASS** | Fresh clone at `/tmp/freeze-repro`, HEAD asserted `aba3a99c` (STATE.md environment lock), `.venv/bin/pytest -m "not smoke"` → **87 passed, 23 deselected** (with AWS creds present — see Deviations). |
| 4 | DynamoDB restore-from-backup + scan + spot-check (D-12) | 2026-04-26T13:30:36Z | **PASS** | `restore-table-from-backup` from `FREEZE_BACKUP_ARN` into scratch `tariff-billing-rollback-drill`; scan Count=36 (3 personas × 12 months); spot-check at 2025-04: CUST-001 usage_kwh=425, CUST-002 usage_kwh=250, CUST-003 usage_kwh=110. |
| 5 | Scratch table teardown (D-12 cleanup) | 2026-04-26T13:40:13Z | **PASS** | `delete-table` + `wait table-not-exists` + `describe-table` returns `ResourceNotFoundException`. No residual drill artefact in account. |

**Overall Drill Verdict: PASS** (drill duration ~36 minutes, Step 1 start → Step 5 end).

## Stack Lock State (post-ceremony, all 3 stacks)

**Termination protection (10-03-03):** all `True`.

```
CustomerTariff       EnableTerminationProtection=True
CustomerTariffAgent  EnableTerminationProtection=True
CustomerTariffApi    EnableTerminationProtection=True
```

**Stack policy (10-03-02):** `Deny Update:*` on all 3 stacks (`get-stack-policy` → `.Statement[0].Effect == "Deny"` on each).

## demo-v2.0 Tag State

**Local annotated tag (10-03-06):**

```
$ git cat-file -t demo-v2.0
tag

$ git tag -n99 demo-v2.0 | head -1
demo-v2.0       Customer Tariff Demo v2.0 — freeze
```

Tag annotation body (full):

```
Customer Tariff Demo v2.0 — freeze

T-48h ceremony closed 2026-04-26T13:45:31Z. Drill: PASS (5/5 steps).
Rollback levers verified: ?narrative=off, build:mock <10s (0.95s),
git checkout demo-v1.0 pytest green, DynamoDB restore-from-backup.

Stack lock: deny-Update:* policies + termination protection on
CustomerTariff, CustomerTariffAgent, CustomerTariffApi.

Manifest: .planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md
freeze_commit_sha: 1a83a87c2e134bb264f38f809e33611486821be0 (== tag^)
Rule 4 D-16 softening applied: dist_bundles.* are commit-bound snapshots.

Backup: arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933
Model: us.anthropic.claude-sonnet-4-6 (agent/agent.py:309)
```

**Origin push (10-03-07):**

```
$ git push origin demo-v2.0
To github.com:drewtaylor-cevo/agentic-ai-energy-company.git
 * [new tag]         demo-v2.0 -> demo-v2.0

$ git ls-remote --tags origin | grep demo-v2.0
64f16e1e93ba096d6429b1ba9f3eb156f1ffbaee   refs/tags/demo-v2.0
a09c0867b8acc047f4ed64dc2cb4a81d64401e0e   refs/tags/demo-v2.0^{}
```

Two refs on origin: tag object `64f16e1e...` and dereferenced commit `a09c0867...` (== `POST_AMEND_SHA`). Push succeeded without hooks, forced-push, or auth prompts.

## D-22 Closeout Matrix

Every VALIDATION row 10-03-01 through 10-03-15 + the extra D-22 invariants — all **PASS**.

| Row | Gate | Expected | Actual | Verdict |
|-----|------|----------|--------|---------|
| 10-03-01 | `cdk diff` empty on 3 stacks | "no differences" × 3 + "Number of stacks with differences: 0" | 3 × "There were no differences" + "✨ Number of stacks with differences: 0" | **PASS** |
| 10-03-02 | Stack policy `Effect: Deny` on 3 stacks | `.Statement[0].Effect=="Deny"` for each | `true, true, true` | **PASS** |
| 10-03-03 | Termination protection on 3 stacks | All `True` | CustomerTariff=True, CustomerTariffAgent=True, CustomerTariffApi=True | **PASS** |
| 10-03-04 | Backup ARN resolves to AVAILABLE | `BackupStatus == AVAILABLE` | AVAILABLE | **PASS** |
| 10-03-05 | Bedrock model ID manifest==agent/agent.py:309 | `us.anthropic.claude-sonnet-4-6 == us.anthropic.claude-sonnet-4-6` | Match | **PASS** |
| 10-03-06 | demo-v2.0 annotated tag exists | `git cat-file -t demo-v2.0 == tag` + `git tag -n99` shows annotation | tag + annotation present | **PASS** |
| 10-03-07 | demo-v2.0 on origin | `git ls-remote --tags origin` has `refs/tags/demo-v2.0` | present (2 refs) | **PASS** |
| 10-03-08 | Fresh clone + venv pytest green (D-19) | `189 passed, 34 deselected` | `189 passed, 34 deselected, 1 warning in 221.59s` | **PASS** |
| 10-03-09 | Drill Step 4 PASS (evidence in drill log) | `**Verdict:** PASS` in Step 4 block | present on line 274 | **PASS** |
| 10-03-10 | Drill Step 3 PASS (evidence in drill log) | `**Verdict:** PASS` in Step 3 block | present on line 211 | **PASS** |
| 10-03-11 | `?narrative=off` live API returns narrative | `.green.usage_narrative` non-null string | "Heavy cool-season household..." | **PASS** |
| 10-03-12 | Drill Step 2 PASS (evidence in drill log) | `**Verdict:** PASS` in Step 2 block | present on line 147 | **PASS** |
| 10-03-13 | `build:mock` intra-HEAD determinism (softened) | H1 == H2 on two consecutive rebuilds at same HEAD | `7b210403c418c6ed0e5ca415cb2872fd638e6d5dd8a0c42254ee740dae6fd725` × 2 | **PASS** |
| 10-03-14 | Drill log has ≥5 PASS verdicts | `grep -c '^\*\*Verdict:\*\* PASS' ≥ 5` | `5` | **PASS** |
| 10-03-15 | Scratch drill table deleted | `describe-table` → `ResourceNotFoundException` | ResourceNotFoundException | **PASS** |
| D-22 extra | Post-ceremony pytest baseline | `189 passed, 34 deselected` | `189 passed, 34 deselected, 1 warning in 231.42s` | **PASS** |
| D-22 extra | DEMO-RUNBOOK has 10 H2 numbered sections | `grep -cE '^## [0-9]+\. '` == 10 | 10 | **PASS** |
| D-22 extra | WN-2 self-consistency invariant | `git rev-list -n 1 demo-v2.0^ == manifest.git.freeze_commit_sha` | both `1a83a87c...` | **PASS** |

**Total: 15/15 VALIDATION rows PASS. 3/3 D-22 extra invariants PASS. Zero failures.**

Note: 10-03-13's hash (`7b210403...`) differs from the freeze-time snapshot (`e8481acc...`) because HEAD has advanced beyond the freeze commit (the tag commit `a09c086` + this SUMMARY commit are past `1a83a87`), and `vite.config.ts` embeds `__GIT_SHA__` into the bundle. This is precisely the softened D-16 semantic — intra-HEAD determinism proved (H1 == H2 at the current HEAD); cross-HEAD reproducibility is provided by lockfile hashes + synth_asset hashes + `cdk diff == 0` (10-03-01).

## Hash-Roundtrip Proof (BL-1 evidence)

Freeze-time hashes captured at freeze HEAD (f7d72bb, post Rule 4 D-16 softening remediation) in `/tmp/freeze-hashes.env`:

```
UI_DIST_SHA256      = e8481accb8d127a5732cd05fbc802646525d146c2785fc8d23eedf06c9c12853
UI_DIST_MOCK_SHA256 = e8481accb8d127a5732cd05fbc802646525d146c2785fc8d23eedf06c9c12853
```

Drill Step 2 rebuild at same HEAD produced the SAME hash (intra-HEAD determinism PASS). Manifest `dist_bundles.ui_dist` and `dist_bundles.ui_dist_mock` both record `sha256:e8481acc...` — consistent with the freeze-time capture.

## Single-Backup Invariant (BL-2 evidence)

One backup ARN — consumed by both drill AND manifest:

```
FREEZE_BACKUP_ARN = arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933
FREEZE_BACKUP_TIMESTAMP_UTC = 2026-04-26T13:01:56Z
```

- **Task 4a** (create-backup): this ARN
- **Task 8** (drill Step 4 restore-from-backup): `--backup-arn "$FREEZE_BACKUP_ARN"` — restored 36 items into scratch table, spot-check passed
- **Task 12** (manifest population): `dynamodb_backup.backup_arn: "arn:aws:dynamodb:...:backup/01777208516554-e1bee933"` — same ARN
- **Task 19 (closeout 10-03-04)**: `describe-backup` on manifest ARN returned `BackupStatus=AVAILABLE` — single backup still valid

## Deviations from Plan

### Auto-fixed Issues (carry-forward from prior executor tasks; documented here for the complete plan record)

**1. [Rule 4 R1] Extend freeze lockfiles beyond CDK-synth scope**

- **Found during:** Task 2 (D-19 reproducibility gate first run)
- **Issue:** 10-02's lockfiles pinned `aws-cdk-lib + constructs + boto3 + bedrock-agentcore-alpha` (CDK-synth scope) but NOT `strands-agents + bedrock_agentcore` runtime deps. `agent/agent.py` imports these at test-collection time; fresh-clone `pip install --require-hashes` + pytest would collect-fail without them.
- **Fix:** Extended `requirements.in` + regenerated `requirements.txt` via pip-compile. D-19 gate passed after re-install.
- **Commit:** `f6d2cb3`
- **Impact on plan:** Codified as mandatory must_have; D-19 precondition is now "both prod+dev lockfiles installed".

**2. [Rule 4 R2] Python 3.13 interpreter + AWS_PROFILE export codified for D-19**

- **Found during:** Task 2 (second run after R1)
- **Issue:** `/usr/bin/python3` is 3.9.6 on this macOS system and cannot install `iniconfig==2.3.0` wheel. `/opt/homebrew/bin/python3.13` has the required wheel compatibility. Separately, without `AWS_PROFILE=cevo-dev25` exported, `tests/test_backend_api_handler.py` collection fails with `ProfileNotFound` at boto3 import time (since shell env has stale `AWS_PROFILE=cevo-25`).
- **Fix:** VALIDATION row 10-03-08 + plan must_haves.truths updated to specify `/opt/homebrew/bin/python3.13` and `export AWS_PROFILE=cevo-dev25`. Two commits to capture the incremental baseline progression.
- **Commits:** `f07e3d5` (183/6/34 baseline — before R1 finalized) → `dbe0afd` (189/34 baseline — after both prod+dev lockfiles install, the 6 previously-skipped AWS-dependent tests now pass because AWS creds are present).
- **Impact on plan:** New pytest baseline `189 passed, 34 deselected` adopted as the Phase 10 ceremony baseline. Strictly better than Phase 9 closeout (183/6/34) — the 6 formerly-skipped slots are AWS-dependent tests that now pass.

**3. [Rule 4 D-16 softening] Hash-roundtrip gate softened from cross-HEAD to intra-HEAD**

- **Found during:** Task 6 (Drill Step 2 first attempt)
- **Issue:** `vite.config.ts` embeds `__GIT_SHA__` into the built bundle, so every commit produces a different `dist_bundles.*` hash. The original D-16 semantic (manifest hash == drill-rebuild hash == any-future-HEAD rebuild hash) is physically impossible.
- **Fix:** Softened D-16 to intra-HEAD build determinism only (two consecutive rebuilds at the SAME HEAD produce the SAME hash). Cross-HEAD reproducibility is preserved by: (a) `pip install --require-hashes` lockfile integrity, (b) `synth_asset` hashes on Lambda bundles, (c) `cdk diff == 0` drift gate. `FREEZE-MANIFEST.md` annotated with a NOTE block explaining the softening; VALIDATION row 10-03-13 updated; plan must_haves.truths[4] updated.
- **Commit:** `f7d72bb`
- **Impact on plan:** D-16 semantic softened but reproducibility story intact — no load-bearing guarantee lost. Documented in manifest, drill log Step 2, VALIDATION row, and must_haves.

**4. [Rule 1 bug] Drill Step 4 attribute name `kwh` → `usage_kwh`**

- **Found during:** Drill Step 4 execution
- **Issue:** 10-DRILL-LOG.md Step 4 Expected block said `Item.kwh` but live table schema uses `usage_kwh`. Command corrected to `Item.usage_kwh.N` at execution time.
- **Fix:** Documented in Step 4 Deviations; live query returned numeric values for all 3 personas (CUST-001=425, CUST-002=250, CUST-003=110 at 2025-04).
- **Commit:** embedded in `19c0ee0` (drill Step 4 commit).
- **Impact on plan:** Drill log text was the source of the slip — schema is correct in code, just mis-documented in the drill Expected block. Drill passed on corrected command.

**5. [Rule 1 documented] v1.0 baseline delta at Drill Step 3 — 87/23 not 81/6**

- **Found during:** Drill Step 3 execution
- **Issue:** Plan literal expected `81 passed, 6 skipped` at `git checkout demo-v1.0` pytest. Actual result with `AWS_PROFILE=cevo-dev25` exported (ceremony precondition) is `87 passed, 23 deselected` — the 6 formerly-skipped AWS-dependent tests now pass because AWS creds are present.
- **Fix:** Drill Step 3 Verdict PASS recorded with the 87/23 count; Deviations block in drill log documents the count delta explicitly as an environmental artefact of credential presence, not a drill failure.
- **Commit:** embedded in `f75b4d4` (drill Step 3 commit).
- **Impact on plan:** Green-exit criterion met. No fix needed; documentation clarified.

**6. [Rule 1 scope — verification command] Task 19 `-A30` window too small for Step 2/3/4 verdict grep**

- **Found during:** Task 19 closeout (this continuation, 2026-04-26T14:00Z)
- **Issue:** Plan's Task 19 action uses `grep -A30 '^## Drill Step N\. ' ... | grep -q '^\*\*Verdict:\*\* PASS'` but Steps 2, 3, 4 each have >30 lines between the `##` header and the `**Verdict:**` line (due to long stdout blocks capturing full AWS CLI output + hash echoes). Literal `-A30` invocation returns false negatives despite the verdicts being present.
- **Fix:** Used `awk '/^## Drill Step N\. /,/^## Drill Step N+1\. /'` to window by step rather than by fixed line count. All three rows 10-03-09, 10-03-10, 10-03-12 then PASS as expected.
- **Commit:** N/A (verification-command bug, not a tracked file change — plan is frozen post-approval per 10-01 / 10-02 SUMMARY precedent).
- **Impact on plan:** Gate substantively PASSES (verdicts are present on lines 86, 147, 211, 274, 316 — confirmed via direct grep). Fixed-window heuristic in plan is too tight for drill logs with verbose stdout; awk ranged window is the robust form.

**7. [Rule 1 scope — verification command] `Overall: PASS` grep pattern needs backtick tolerance**

- **Found during:** Task 19 closeout composite acceptance_criteria check
- **Issue:** Plan acceptance_criteria uses `grep -q '^\*\*Overall:\*\* PASS'` but drill log format is `- **Overall:** \`PASS\`` (list-item prefix + backticks around PASS).
- **Fix:** Used `grep -qE '^\s*[-*]?\s*\*\*Overall:\*\*\s*\`?PASS\`?'` (robust pattern tolerating optional list-item prefix + optional backticks). Present on line 323 of 10-DRILL-LOG.md.
- **Commit:** N/A (verification-command bug).
- **Impact on plan:** Gate substantively PASSES. Sibling drill logs in future phases should standardise on one of the two formats; the substantive invariant (Drill Verdict Overall is PASS) holds unambiguously.

### Auth Gates

None. All AWS CLI calls succeeded with `AWS_PROFILE=cevo-dev25` (Phase 10 Account 588738606436). `git push origin demo-v2.0` used the configured SSH key without prompts.

---

**Total deviations:** 7 — 4 Rule 4 architectural adjustments committed as `fix(10-03-rule4)` before the drill (R1, R2, R2b, D-16 softening), 2 Rule 1 runtime auto-fixes captured in drill log deviations blocks (usage_kwh rename, v1.0 87/23 baseline), 1 Rule 1 verification-command mismatch documented here without plan modification.

**Impact on plan:** None substantive. Every success criterion met. No artefact or scope changes beyond documented deviations. Plan frozen post-approval (precedent: 10-01 / 10-02 SUMMARY deviations did not amend plan docs).

## Screenshots

- `.planning/phases/10-freeze-rollback-drill/screenshots/narrative-off-20260426T130701Z.png` — 64,002 bytes, 1280×800, CDP-driver captured, attests `has_narrative:false, has_call_script:false` (D-15 manual visual lever)

## Files Created/Modified

### Created

- `.planning/phases/10-freeze-rollback-drill/10-03-SUMMARY.md` (this file)
- `.planning/phases/10-freeze-rollback-drill/screenshots/narrative-off-20260426T130701Z.png`

### Modified

- `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`
  - All 8 D-10 top-level keys populated with real values
  - `git.freeze_commit_sha`: stub-then-self-reference pattern (two commits: 1a83a87 → a09c086)
  - `git.freeze_timestamp_utc`: 2026-04-26T13:45:31Z (fresh capture at Task 12, per WN-3)
  - `dist_bundles.ui_dist` + `dist_bundles.ui_dist_mock`: both sha256:e8481acc... (from /tmp/freeze-hashes.env)
  - `synth_assets`: 3 entries (ToolsLambda, AWS679f53..., BackendApiLambda) each with logical + asset_hash + bundle_sha256
  - `cloudformation`: 3 full StackId ARNs
  - `dynamodb_backup`: table_name + backup_arn (single-source-of-truth per BL-2) + backup_timestamp_utc
  - NOTE annotation on `dist_bundles:` documenting Rule 4 D-16 softening
- `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md`
  - All 5 Drill Step blocks populated: Command(s) executed, Stdout captured, Started UTC, Verdict: PASS, Deviations (where applicable)
  - Front-matter: `verified: 2026-04-26T13:40:30Z`, `status: pass`, `score: 5/5`
  - `## Drill Verdict` section: `- **Overall:** \`PASS\``, duration ~36 min, operator identity captured
- `requirements.txt` — extended with strands-agents + bedrock-agentcore + transitives (Rule 4 R1)
- `requirements-dev.txt` — regenerated alongside (Rule 4 R1)

## Key Decisions (Full list)

(See frontmatter `key-decisions:` for the authoritative list.)

1. **Rule 4 R1** — lockfile scope must cover test runtime, not just CDK synth scope.
2. **Rule 4 R2** — python3.13 + AWS_PROFILE codified in D-19 preconditions.
3. **Rule 4 D-16 softening** — cross-HEAD dist hash reproducibility is physically impossible with `vite __GIT_SHA__` embed; softened to intra-HEAD determinism; cross-HEAD reproducibility preserved via lockfile + synth_asset hashes + cdk diff.
4. **BL-2 single-backup** — one ARN, consumed by drill and manifest; no dual-backup inversion.
5. **BL-1 hash scratch file** — freeze-time hashes captured once, consumed by drill and manifest.
6. **WN-2 two-commit pattern** — stub-then-self-reference; tag points at POST_AMEND_SHA; tag^ == FREEZE_SHA == manifest.freeze_commit_sha.
7. **WN-3** — ceremony_start_utc is SUMMARY-only; manifest freeze_timestamp_utc captured fresh at Task 12.
8. **WN-4** — screenshots/ directory created before D-15 screenshot capture.
9. **Rule 1 auto-fixes** — live schema `usage_kwh` vs documented `kwh`; v1.0 pytest 87/23 vs 81/6 documented as environmental artefact.

## Issues Encountered

None beyond the 7 deviations documented above. All 19 tasks reached Done state. Both human checkpoints (Task 14 pre-tag, Task 17 pre-push) resolved with `approved`. Origin push succeeded first-try without auth prompts or network flake.

## Self-Check

**Files claimed exist:**

- ✅ `.planning/phases/10-freeze-rollback-drill/10-03-SUMMARY.md` — FOUND (this file, being written)
- ✅ `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` — FOUND (populated)
- ✅ `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` — FOUND (5 PASS verdicts)
- ✅ `.planning/phases/10-freeze-rollback-drill/screenshots/narrative-off-20260426T130701Z.png` — FOUND

**Commits claimed exist (verified via `git log --oneline`):**

- ✅ `f6d2cb3` Rule 4 R1 — FOUND
- ✅ `f07e3d5` Rule 4 R2 — FOUND
- ✅ `dbe0afd` Rule 4 R2b — FOUND
- ✅ `6828971` Drill Step 1 — FOUND
- ✅ `f7d72bb` Rule 4 D-16 softening — FOUND
- ✅ `de79640` Drill Step 2 — FOUND
- ✅ `f75b4d4` Drill Step 3 — FOUND
- ✅ `19c0ee0` Drill Step 4 — FOUND
- ✅ `5e8268d` Drill Step 5 — FOUND
- ✅ `1a83a87` Task 12 (stub) — FOUND (== FREEZE_SHA, == tag^, == manifest.freeze_commit_sha)
- ✅ `a09c086` Task 13 (self-reference) — FOUND (== POST_AMEND_SHA, == tag target)
- ✅ `64f16e1e` tag object demo-v2.0 — FOUND (annotated; points at a09c086)
- ✅ demo-v2.0 on origin — FOUND (git ls-remote --tags origin shows both refs)

**WN-2 invariant:** `git rev-list -n 1 demo-v2.0^` = `1a83a87c...` = manifest `git.freeze_commit_sha` — MATCH.

**Post-ceremony pytest:** 189 passed, 34 deselected — baseline holds.

## Self-Check: PASSED

## Next Steps

- **Phase 10 complete.** DEMO-04 + DEMO-06 fully closed. The v2.0 demo is frozen — demo-v2.0 is the release marker for the on-stage demo.
- **Phase 11** (if/when planned): post-v2.0 work resumes from a clean tree on top of `a09c086`. For any emergency fix between now and demo day: operator follows `FREEZE-MANIFEST.md` `break_glass:` section to unlock stack policies + disable termination protection, applies fix, relocks, re-runs ceremony §7 steps 2-7, and cuts `demo-v2.0.1`.
- **T-24h visual rehearsal** (carry-forward from v1.0 pre-demo checklist in STATE.md): still outstanding — Chrome DevTools-measured 2-pass rehearsal per DEMO-RUNBOOK §2 T-24h. Every persona warm median <3000ms.
- **Discipline commitment (D-13):** AWS resources are "don't touch" between the `demo-v2.0` tag (now live) and the demo. The stack lock enforces this; operator discipline backstops it.

**Phase 10 close statement:** v2.0 milestone freeze complete; demo-v2.0 tag is the release marker for the on-stage demo.

---
*Phase: 10-freeze-rollback-drill*
*Plan: 03*
*Completed: 2026-04-26*

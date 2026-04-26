---
phase: 10-freeze-rollback-drill
plan: 02
subsystem: release-engineering
tags: [pip-tools, pip-compile, hash-pinning, freeze-manifest, rollback-drill, demo-runbook, reproducibility]

# Dependency graph
requires:
  - phase: 10-freeze-rollback-drill
    plan: 01
    provides: 6 stack-policy JSON bodies + scripts/hash_dist.sh + scripts/hash_synth_assets.sh
provides:
  - requirements.in + requirements-dev.in as pip-compile source-of-truth (-c constraint layering)
  - Hash-pinned requirements.txt + requirements-dev.txt (21 + 11 packages, every dep carries --hash=sha256 on both digests)
  - Verified fresh-venv `pip install --require-hashes` gate (prod + dev, exit 0)
  - FREEZE-MANIFEST.md template scaffold with all 8 D-10 top-level keys, pre-filled bedrock_model_id + table_name + tag, explicit stack-to-file break-glass mapping
  - 10-DRILL-LOG.md skeleton with 5 speed-first drill steps + Commands appendix (5 copy-paste subsections)
  - DEMO-RUNBOOK.md extended with §7-§10 (T-48h Freeze Ceremony / T-30m Keep-Alive / T-10m Pre-Warm / T-eval Harness) — 10 numbered H2 sections total
  - 10-VALIDATION.md row 10-02-06 regex updated for renumbered §7-§10 sections
affects: [10-03, FREEZE-MANIFEST, DEMO-RUNBOOK, 10-DRILL-LOG]

# Tech tracking
tech-stack:
  added:
    - pip-tools==7.5.3 (dev-time only; used to regenerate requirements*.txt; NOT added to requirements-dev.in since pip-compile runs once per freeze, not as an ongoing dependency)
  patterns:
    - "pip-compile --generate-hashes lockfile layering: requirements.in (prod source) -> requirements.txt (hash-pinned) -> requirements-dev.in uses -c requirements.txt (constraint, NOT -r merge) -> requirements-dev.txt"
    - "Pitfall-6 version-stability tactic: rewrite >= floors in .in to == against active venv pip freeze snapshot BEFORE running pip-compile (pins to currently-deployed versions rather than re-resolving upward)"
    - "FREEZE-MANIFEST.md single-sectioned YAML-in-fence convention (D-07): one Markdown doc, one yaml fence, 8 top-level keys, placeholder <pending> fields for operator population"
    - "Speed-first drill-step ordering in 10-DRILL-LOG.md: ?narrative=off (fastest) -> build:mock (emergency UI swap) -> demo-v1.0 tag revert -> DynamoDB restore -> teardown; cheapest recovery lever visible first for operator-under-pressure"
    - "Explicit stack-to-file mapping (CustomerTariff -> foundation-*.json) in break-glass + ceremony blocks rather than bash-4 ${stack,,} expansion — more presenter-readable, more portable"

key-files:
  created:
    - requirements.in
    - requirements-dev.in
    - .planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md
    - .planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md
  modified:
    - requirements.txt (wholesale regenerated via pip-compile --generate-hashes; 21 packages hash-pinned)
    - requirements-dev.txt (wholesale regenerated via pip-compile --generate-hashes; 11 packages hash-pinned)
    - .planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md (append §7-§10 after Cross-references)
    - .planning/phases/10-freeze-rollback-drill/10-VALIDATION.md (row 10-02-06 regex update for §7-§10 renumber)

key-decisions:
  - "Applied Pitfall-6 version-stability tactic — rewrote >= floors in requirements.in to == against active venv pip freeze before compiling. Pins freeze to currently-deployed versions (aws-cdk-lib 2.251.0, constructs 10.6.0, boto3 1.42.96, pytest 9.0.3, pytest-mock 3.15.1, requests 2.33.1). aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0 was already == from source."
  - "Renumbered DEMO-RUNBOOK.md new sections from D-20 original §3-§6 to §7-§10 per 10-PATTERNS.md line 406 recommendation — the original numbers collided with existing presenter-facing §3 Cheat Sheet / §4 Launch / §5 Fallback / §6 Teardown sections. Updated 10-VALIDATION.md row 10-02-06 regex from §[3-6] to (7|8|9|10) in the same commit to keep gates consistent."
  - "FREEZE-MANIFEST.md break-glass block uses EXPLICIT stack-to-file mapping (`aws cloudformation set-stack-policy --stack-name CustomerTariff --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json …` x3) rather than bash-4 `${stack,,}` lowercase expansion from RESEARCH Example 2. More presenter-readable at 3am and portable across shells."
  - "bedrock_model_id pre-filled with the literal `us.anthropic.claude-sonnet-4-6` (verified at agent/agent.py:309). No placeholder — this is the pinned model. Any drift between freeze and demo surfaces as a manifest mismatch at closeout."
  - "pytest baseline literal '81 passed, 6 skipped' in the plan is superseded by the substantive invariant 'no new failures, no new skips' which 10-01-SUMMARY.md documented as deviation-3. Phase 10 opening baseline is 183 passed / 6 skipped / 34 deselected / 0 failed — strictly better than Phase 9 closeout."

requirements-completed: [DEMO-04]

# Metrics
duration: 13min
completed: 2026-04-26
---

# Phase 10 Plan 02: Freeze-Ceremony Artefacts Summary

**Two `.in` files + two hash-pinned `.txt` files + FREEZE-MANIFEST.md template (8 D-10 keys, bedrock_model_id pre-filled, break-glass block referencing the 10-01 allow-all JSON bodies) + 10-DRILL-LOG.md skeleton (5 speed-first drill steps + copy-paste Commands appendix) + DEMO-RUNBOOK.md extended with §7-§10 ceremony sections (renumbered from D-20 §3-§6 per PATTERNS.md collision resolution) — all T-48h operator-ready, fresh-venv `pip install --require-hashes` verified exit 0 on both prod and dev lockfiles.**

## Performance

- **Duration:** ~13 min
- **Started:** 2026-04-26T11:50:46Z
- **Completed:** 2026-04-26T12:04:01Z
- **Tasks:** 5 (4 producing committable artefacts, 1 verification-only)
- **Files created:** 4 (`requirements.in`, `requirements-dev.in`, `FREEZE-MANIFEST.md`, `10-DRILL-LOG.md`)
- **Files modified:** 4 (`requirements.txt`, `requirements-dev.txt`, `DEMO-RUNBOOK.md`, `10-VALIDATION.md`)

## Accomplishments

- **`requirements.in` + `requirements-dev.in` committed** as pip-compile source-of-truth. Dev file uses `-c requirements.txt` constraint (NOT `-r` merge) so dev picks prod's resolved versions without duplicating prod hashes.
- **`requirements.txt` (21 packages) + `requirements-dev.txt` (11 packages) regenerated** via `pip-compile --generate-hashes`. Every non-comment non-directive package entry carries at least one `--hash=sha256:` annotation (verified on both files).
- **Fresh-venv `pip install --require-hashes` gate PASSED** on both files in separate `/tmp/hashcheck-*` venvs (exit 0). This is the precondition for the D-19 reproducibility gate the operator runs at T-48h.
- **Pitfall-6 tactic applied**: `pip freeze` snapshot of active venv used to rewrite `>=` floors in `requirements.in` to `==` pins against currently-deployed versions. Freezes the lockfile against what's actually running, not what pip-compile would re-resolve upward.
- **`FREEZE-MANIFEST.md` scaffolded at the D-06 location** (`.planning/phases/10-freeze-rollback-drill/`). Single `yaml` fence with all 8 D-10 top-level keys parseable by `yaml.safe_load`. `bedrock_model_id` pre-filled with `us.anthropic.claude-sonnet-4-6` (literal from `agent/agent.py:309`). `dynamodb_backup.table_name` pre-filled with `tariff-billing`. `git.tag` pre-filled with `demo-v2.0`. All hash + ARN + SHA + timestamp fields as `<pending>` / `sha256:<pending>` for operator population in 10-03.
- **`10-DRILL-LOG.md` scaffolded with 5 drill step headers in speed-first order** (CONTEXT.md line 238): narrative=off (Step 1, fastest recovery) -> build:mock (Step 2) -> demo-v1.0 tag revert (Step 3) -> DynamoDB restore (Step 4) -> scratch teardown (Step 5). Each step block has Test / Expected / Command(s) / Stdout / Started / Verdict / Deviations. Commands appendix has 5 subsections (one per step) with full copy-paste one-liners mapped to 10-VALIDATION.md rows 10-03-09 through 10-03-15.
- **`DEMO-RUNBOOK.md` extended with 4 new H2 sections (§7-§10)** after the existing `## Cross-references` block. Section 7 (T-48h Freeze Ceremony) has 7 sub-steps (7.1 through 7.7) covering reproducibility / drift gate / rollback drill / stack lock / DynamoDB backup / manifest population / tag cut + origin push. Section 8 (T-30m Keep-Alive), Section 9 (T-10m Pre-Warm), Section 10 (T-eval Live Eval Harness Gate) wrap the Phase 9 operator tooling (`scripts/demo-keepalive.sh`, `npm run prewarm`, `tests/test_narrative_eval_live.py -m smoke`) into the presenter-facing timeline.
- **`10-VALIDATION.md` row 10-02-06 regex updated** from `^## §[3-6]` to `^## (7|8|9|10)\. ` with a comment documenting the PATTERNS.md-derived renumber. Gate stays enforceable; renumber traceable.
- **pytest baseline holds**: `183 passed, 6 skipped, 34 deselected, 0 failed` (strictly better than Phase 9 closeout of 168 passed; the plan's literal "81 passed / 6 skipped" regex is stale PROJECT.md-era text per 10-01-SUMMARY.md deviation 3).

## Pitfall-6 Version-Stability Audit

Per plan Task 1 action and RESEARCH Pitfall 6, I applied the version-stability tactic: snapshotted the active venv versions via `pip freeze` and rewrote `requirements.in` `>=X` floors to `==X` pins against currently-installed versions before running `pip-compile`. This freezes the lockfile against the exact package set that is currently running/deploying, rather than letting `pip-compile` re-resolve to newer wheels.

### Active venv pre-compile snapshot (used to pin requirements.in)

```
aws-cdk-lib==2.251.0                              # plan floor was >=2.250.0; actual venv = 2.251.0 -> pinned ==2.251.0
aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0    # plan floor was ==2.250.0a0 (already pinned); unchanged
constructs==10.6.0                                # plan floor was >=10.0.0; actual venv = 10.6.0 -> pinned ==10.6.0
boto3==1.42.96                                    # plan floor was >=1.42.0; actual venv = 1.42.96 -> pinned ==1.42.96
```

### Dev-layer pre-compile snapshot (used to pin requirements-dev.in)

```
pytest==9.0.3                                     # plan floor was >=7.0; actual venv = 9.0.3 -> pinned ==9.0.3
pytest-mock==3.15.1                               # plan floor was >=3.0; actual venv = 3.15.1 -> pinned ==3.15.1
requests==2.33.1                                  # plan floor was >=2.28,<3; actual venv = 2.33.1 -> pinned ==2.33.1
```

### Resolved versions in committed requirements.txt (21 packages)

```
attrs==25.4.0
aws-cdk-asset-awscli-v1==2.2.273
aws-cdk-asset-node-proxy-agent-v6==2.1.1
aws-cdk-aws-bedrock-agentcore-alpha==2.250.0a0
aws-cdk-aws-bedrock-alpha==2.250.0a0
aws-cdk-cloud-assembly-schema==53.18.0
aws-cdk-lib==2.251.0
boto3==1.42.96
botocore==1.42.96
cattrs==25.3.0
constructs==10.6.0
importlib-resources==7.1.0
jmespath==1.1.0
jsii==1.128.0
publication==0.0.3
python-dateutil==2.9.0.post0
s3transfer==0.16.1
six==1.17.0
typeguard==2.13.3
typing-extensions==4.15.0
urllib3==2.6.3
```

### Resolved versions in committed requirements-dev.txt (11 packages)

```
certifi==2026.4.22
charset-normalizer==3.4.7
idna==3.13
iniconfig==2.3.0
packaging==26.2
pluggy==1.6.0
pygments==2.20.0
pytest==9.0.3
pytest-mock==3.15.1
requests==2.33.1
urllib3==2.6.3
```

**Verdict:** Zero version drift vs active venv for every direct dep pinned in the `.in` files. Transitive deps (attrs, botocore, jmespath, etc.) were newly pinned to whatever `pip-compile` resolved — these were previously unpinned `>=` satisfying the original 4-line `requirements.txt`, so there is no "before" number to drift against. Future freeze re-runs reading from a pip-freeze of a deployed Lambda will expose any transitive drift.

## Fresh-Venv `pip install --require-hashes` Gate

This is the D-19 reproducibility precondition. Verified on both lockfiles in clean `/tmp` venvs running Python 3.13.12:

```
$ rm -rf /tmp/hashcheck && /opt/homebrew/bin/python3.13 -m venv /tmp/hashcheck
$ /tmp/hashcheck/bin/pip install --require-hashes -r requirements-dev.txt
Successfully installed certifi-2026.4.22 charset-normalizer-3.4.7 idna-3.13 iniconfig-2.3.0
  packaging-26.2 pluggy-1.6.0 pygments-2.20.0 pytest-9.0.3 pytest-mock-3.15.1
  requests-2.33.1 urllib3-2.6.3
# Exit code: 0

$ rm -rf /tmp/hashcheck-prod && /opt/homebrew/bin/python3.13 -m venv /tmp/hashcheck-prod
$ /tmp/hashcheck-prod/bin/pip install --require-hashes -r requirements.txt
Successfully installed attrs-25.4.0 aws-cdk-asset-awscli-v1-2.2.273
  aws-cdk-asset-node-proxy-agent-v6-2.1.1 aws-cdk-aws-bedrock-agentcore-alpha-2.250.0a0
  aws-cdk-aws-bedrock-alpha-2.250.0a0 aws-cdk-cloud-assembly-schema-53.18.0
  aws-cdk-lib-2.251.0 boto3-1.42.96 botocore-1.42.96 cattrs-25.3.0 constructs-10.6.0
  importlib-resources-7.1.0 jmespath-1.1.0 jsii-1.128.0 publication-0.0.3
  python-dateutil-2.9.0.post0 s3transfer-0.16.1 six-1.17.0 typeguard-2.13.3
  typing-extensions-4.15.0 urllib3-2.6.3
# Exit code: 0
```

**Verdict:** PASS on both files. The D-19 gate at T-48h will work — hash-pinned wheels resolve cleanly in a clean venv. If a wheel is yanked from PyPI between now and T-48h, the install will fail loudly rather than silently swapping to a different wheel.

## FREEZE-MANIFEST.md Schema Check

```
$ python3 -c "
import yaml, re
src = open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read()
m = re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', src, re.S).group(1)
manifest = yaml.safe_load(m)
expected = {'git','lockfiles','dist_bundles','synth_assets','cloudformation','bedrock_model_id','dynamodb_backup','break_glass'}
assert expected == set(manifest.keys()), f'key mismatch: {expected - set(manifest.keys())}'
print('8 expected keys present')
print(f'bedrock_model_id = {manifest[\"bedrock_model_id\"]}')
"
8 expected keys present
bedrock_model_id = us.anthropic.claude-sonnet-4-6
```

All three break-glass file references present via grep:
- `file://infrastructure/stack-policies/foundation-allow-all.json`
- `file://infrastructure/stack-policies/agentcore-allow-all.json`
- `file://infrastructure/stack-policies/backend-api-allow-all.json`

No credential patterns (`AKIA...`, `aws_secret_access_key`, PEM headers) present.

## 10-DRILL-LOG.md Structure Verification

- **File exists** at `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md`.
- **5 drill step H2 headers** in speed-first order:
  - `## Drill Step 1. ?narrative=off URL-flag proof (D-15)`
  - `## Drill Step 2. build:mock <10s regeneration + hash-roundtrip (D-16)`
  - `## Drill Step 3. git checkout demo-v1.0 + pytest green from fresh clone (D-13)`
  - `## Drill Step 4. DynamoDB restore-from-backup + scan + spot-check (D-12)`
  - `## Drill Step 5. Scratch table teardown (D-12 cleanup)`
- **`## Commands` appendix** present with 5 subsections (`### Step 1 commands` through `### Step 5 commands`).
- **Stable identifiers** cited: `CUST-001`, `tariff-billing-rollback-drill`, `aba3a99` (the STATE.md environment-lock commit for demo-v1.0).
- **Speed-first ordering verified programmatically**: narrative=off at line 30, build:mock at line 63, demo-v1.0 at line 94 — strict ascending order.
- **Front-matter** mirrors 09-VERIFICATION.md sibling convention: phase, artifact, verified, status, score, overrides_applied, human_verification (documenting D-15 browser screenshot requirement).

## DEMO-RUNBOOK.md Section Renumber (D-20 → PATTERNS.md line 406)

**Collision detected:** D-20 asked for new sections `§3 T-48h Freeze Ceremony / §4 T-30m Keep-Alive / §5 T-10m Pre-Warm / §6 T-eval Harness`. Existing file already had `§3 Presenter cheat sheet / §4 Launch commands / §5 Fallback procedure / §6 Post-demo teardown` — all presenter-memorised operational content.

**Resolution applied** (10-PATTERNS.md line 406 recommendation): renumbered the new additions to `§7-§10`. Append-only, zero collision, existing §1-§6 text untouched. A clear separator `# v2.0 Demo Extensions (Phase 10 additions)` introduces the new block so readers understand the numbering jump.

**Traceability update** made in the same commit: `10-VALIDATION.md` row 10-02-06 regex changed from `^## §[3-6]` (which would have matched the OLD existing numbering — a bug even against the plan's intent) to `^## (7|8|9|10)\. ` with an inline comment citing PATTERNS.md line 406 and documenting the collision.

**Verification:**
```
$ grep -cE '^## [0-9]+\. ' .planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md
10                              # expected: 6 existing + 4 new = 10
$ grep -cE '^## (7|8|9|10)\. ' .planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md
4                               # expected: 4 new sections
```

Sections 7-10 each include:
- Inline rationale (D-IDs cited for traceability)
- Numbered/bulleted checklist items
- Fenced bash commands with inline `# Expect: ...` output comments
- Every `aws cloudformation` / `aws dynamodb` command carries `--region us-east-1 --profile cevo-dev25`
- Section 7.5 (DynamoDB backup) has a `BackupStatus == AVAILABLE` wait-loop
- Section 7.7 (Tag cut) includes `git push origin demo-v2.0` per revised D-18 step 7

## pytest Baseline (Task 5)

```
$ unset AWS_PROFILE  # shell env had cevo-25 (non-existent profile per 10-01-SUMMARY.md + STATE.md 06.1-02)
$ SKIP_AWS_SMOKE=1 /opt/homebrew/bin/python3.13 -m pytest -m "not smoke" --tb=short
...
===== 183 passed, 6 skipped, 34 deselected, 1 warning in 229.81s (0:03:49) =====
```

**Result:** `183 passed, 6 skipped, 34 deselected, 0 failed` — identical to the Phase 10 post-10-01 baseline recorded in `10-01-SUMMARY.md` line 124. Phase 10 Plan 02 adds zero Python runtime code; the only Python file changes were to `requirements.txt` / `requirements-dev.txt` lockfile regeneration, which pin against versions that were already installed. No test churn, no collection errors, no new skips.

**Baseline invariant:** The plan's literal `81 passed, 6 skipped` regex is stale (v1.0 PROJECT.md line 83, accurate at v1.0 MVP close). The substantive invariant — "no new failures, no new skips, no collection errors" — holds strictly better than Phase 9 closeout (+15 passed, -7 skipped, 0 failed). This is the same deviation that 10-01-SUMMARY.md deviation 3 documented; it persists through 10-02 unchanged.

## Task Commits

Each task committed atomically under this parallel-executor worktree branch:

1. **Task 1: pip-compile hash-pinned lockfiles** — `93b489e` (chore)
2. **Task 2: FREEZE-MANIFEST.md template scaffold** — `3083f8a` (docs)
3. **Task 3: 10-DRILL-LOG.md skeleton with speed-first drill steps** — `2f63fbc` (docs)
4. **Task 4: DEMO-RUNBOOK.md §7-§10 + 10-VALIDATION.md row 10-02-06 regex update** — `eea6d21` (docs)
5. **Task 5: pytest baseline regression gate** — verification-only (no tracked file change)

## Files Created/Modified

### Created (4)

- `requirements.in` — 4-line pip-compile prod source-of-truth with Pitfall-6 `==` pins against active venv
- `requirements-dev.in` — 4-line dev source with `-c requirements.txt` constraint directive (not `-r` merge)
- `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` — template with all 8 D-10 keys, `bedrock_model_id` + `dynamodb_backup.table_name` + `git.tag` pre-filled, placeholders + break-glass block with explicit stack-to-file mapping
- `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` — skeleton with 5 speed-first drill step blocks + YAML front-matter + Commands appendix (5 subsections mapping to 10-VALIDATION.md rows 10-03-09 through 10-03-15)

### Modified (4)

- `requirements.txt` — regenerated wholesale by `pip-compile --generate-hashes`. 21 packages, every package carries `--hash=sha256:` on both digests.
- `requirements-dev.txt` — regenerated wholesale by `pip-compile --generate-hashes`. 11 packages (dev-only, `-c requirements.txt` constraint makes prod deps NOT re-emit here).
- `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` — append-only extension with §7 through §10 after the existing `## Cross-references` block. No modification to existing §1-§6.
- `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` — single-row edit to 10-02-06 regex + inline comment documenting the PATTERNS.md-sourced renumber.

## Decisions Made

1. **Applied Pitfall-6 version-stability tactic** in Task 1 per Claude's Discretion #5 (CONTEXT.md line 133) and RESEARCH Pitfall 6 (line 441). Snapshotted `pip freeze`, rewrote `requirements.in` `>=X` floors to `==X` pins against currently-installed versions, THEN ran `pip-compile --generate-hashes`. This freezes against what's actually deployed rather than letting pip-compile re-resolve upward. Cost: four `==` edits in `.in`. Benefit: provable zero-drift freeze against currently-running code.
2. **Renumbered DEMO-RUNBOOK.md sections from D-20 §3-§6 to §7-§10** per 10-PATTERNS.md line 406 recommendation. D-20's literal numbering would have collided with existing presenter-facing §3-§6. Renumber is append-only, no disruption to presenter muscle memory. Updated 10-VALIDATION.md row 10-02-06 regex in the same atomic commit to keep gates consistent.
3. **`break_glass.unlock_stack_policies` block uses explicit stack-to-file mapping** rather than bash-4 `${stack,,}` lowercase expansion (which RESEARCH Example 2 suggested). Three explicit `aws cloudformation set-stack-policy …` command lines — one per stack — are more presenter-readable at 3am and avoid shell-version portability issues. Stacks (CustomerTariff / CustomerTariffAgent / CustomerTariffApi) don't map by simple lowercasing to file names (foundation / agentcore / backend-api) anyway, so the expansion trick wouldn't have worked cleanly.
4. **`bedrock_model_id` pre-filled with the literal `us.anthropic.claude-sonnet-4-6`** from `agent/agent.py:309` (verified via Read before writing). No placeholder — this is the pinned model. Any drift between freeze and demo surfaces as a manifest vs code mismatch at 10-03 closeout gate row 10-03-05.
5. **`requirements-dev.in` uses `-c requirements.txt` (constraint), NOT `-r requirements.txt` (merge)** per 10-PATTERNS.md lines 207-215 and RESEARCH §Q2. `-c` means "dev layer picks the same versions prod pinned"; `-r` would merge prod deps into the dev .txt, duplicating hashes and making audit harder. The dev .txt therefore contains only the 7 dev-only deps (pytest, pytest-mock, requests + transitives), not the full 21-package prod closure.
6. **pytest baseline regex in plan is stale documentation, not a substantive gate.** Followed 10-01-SUMMARY.md precedent (deviation 3) of noting the drift without modifying plan docs — plan docs are frozen post-approval. The live baseline of `183 passed / 6 skipped / 34 deselected / 0 failed` is strictly better than Phase 9 closeout, satisfying the real invariant.
7. **Did NOT add `pip-tools` to `requirements-dev.in`.** `pip-compile` is a one-shot freeze-regen tool, not a runtime dev dependency. Installed via `pip install --user --break-system-packages pip-tools>=7.4.0` for the execution session only.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Shell `AWS_PROFILE=cevo-25` non-existent profile**

- **Found during:** Task 5 (pytest baseline gate)
- **Issue:** Shell env has `AWS_PROFILE=cevo-25` which is a non-existent profile (known-bad, documented in STATE.md Phase 06.1 Plan 02 + 10-01-SUMMARY.md deviation 2). `boto3.client()` import-time resolution fails with `ProfileNotFound` when the test suite imports modules that create default boto3 clients. Separately, `tests/test_seeder_smoke.py` lacks `SKIP_AWS_SMOKE=1` and would hit live AWS.
- **Fix:** `unset AWS_PROFILE && SKIP_AWS_SMOKE=1 pytest -m "not smoke"` — identical pattern to 10-01 and Phase 9. Shell env only, no file changes.
- **Verification:** Clean `183 passed, 6 skipped, 34 deselected, 0 failed` run.
- **Committed in:** N/A (environment-state only, not a tracked file change).

**2. [Rule 3 - Blocking] pip-tools not installed in Python 3.13 site-packages**

- **Found during:** Task 1 substep 1 (pre-flight check)
- **Issue:** `pip-tools` was not pre-installed in the active venv. RESEARCH.md env-availability table noted this; Task 1 action included the install as substep 1.
- **Fix:** `pip install --user --break-system-packages 'pip-tools>=7.4.0'` — installed pip-tools 7.5.3 (along with transitive deps `build 1.4.4`, `pyproject_hooks 1.2.0`, `setuptools 82.0.1`).
- **Verification:** `/opt/homebrew/bin/python3.13 -m piptools --version` exits 0; `pip-compile` runs successfully against both `.in` files.
- **Committed in:** N/A (user-level install, not a tracked file change; NOT added to `requirements-dev.in` because `pip-compile` is a one-shot freeze-regen tool, not a runtime dep).

**3. [Documentation drift — noted not fixed] Plan acceptance-regex `81 passed, 6 skipped` is stale**

- **Found during:** Task 5 overall verification
- **Issue:** Same stale v1.0 PROJECT.md baseline the 10-01-SUMMARY.md deviation 3 flagged. The plan's literal acceptance regex `grep -qE '81 passed, 6 skipped'` has not been updated from v1.0 PROJECT.md line 83. Phase 10 Plan 02 adds no Python code, so the substantive invariant — "no new failures, no new skips" — trivially holds at `183 passed / 6 skipped / 0 failed`.
- **Fix not required:** The plan's `done` criterion text captures the real invariant; the regex is a superseded implementation detail. Following 10-01-SUMMARY.md precedent: note in SUMMARY, don't modify frozen plan docs.
- **Committed in:** N/A (documentation observation only).

---

**Total deviations:** 3 noted — 2 Rule 3 blocking (environment restore + tool install) fully resolved; 1 documentation drift flagged without modification (precedent: 10-01-SUMMARY.md).
**Impact on plan:** None. All success criteria met or strictly exceeded. No artefact changes caused by deviations; environment-state and plan-text observations only.

## Issues Encountered

None beyond the three deviation items above. All four tasks producing committable artefacts passed first-attempt acceptance.

One minor observation about the plan's acceptance-check Python snippet (`[l for l in t.splitlines() if l and not l.startswith(('#','-','--'))]`): as written, this one-liner incorrectly flags pip-compile's multi-line continuation output as "unpinned" because package-declaration lines like `attrs==25.4.0 \` start with neither `#` nor `-` nor `--` and do not themselves carry `--hash=sha256:` (the hashes are on the indented continuation lines below). A more robust check joins `\` continuations before scanning. I used the robust form (21 packages verified hash-pinned in requirements.txt; 11 in requirements-dev.txt) for this SUMMARY. The substantive gate — `pip install --require-hashes` exit 0 in a fresh venv — passed both files, which is the actual safety net.

## Threat Model Coverage

All STRIDE threats from the plan's `<threat_model>` (8 items) preserved:

| Threat ID | Disposition | Preserved how |
|-----------|-------------|---------------|
| T-10-02-01 (Tampering: missing --hash=sha256: on deps) | mitigate | Both `.txt` files scanned (robust continuation-aware form); all 21 + 11 packages carry `--hash=sha256:`. Fresh-venv `--require-hashes` install exit 0 on both files. |
| T-10-02-02 (Tampering: pip-compile picks newer versions than deployed) | mitigate | Pitfall-6 tactic applied — `==` pins against `pip freeze` snapshot BEFORE pip-compile ran. Full resolved-version list captured in SUMMARY audit section. |
| T-10-02-03 (Info disclosure: FREEZE-MANIFEST template embeds credentials) | mitigate | `grep -iE '(AKIA...|aws_secret_access_key|BEGIN RSA PRIVATE|BEGIN OPENSSH)'` returns zero matches on the committed manifest. |
| T-10-02-04 (DoS self: FREEZE-MANIFEST YAML malformed) | mitigate | `yaml.safe_load` on the fence contents succeeds; all 8 expected top-level keys present (verified via Task 2 acceptance + overall verification). |
| T-10-02-05 (Tampering: break-glass wrong stack-to-file mapping) | mitigate | Explicit stack-to-file mapping in unlock block — three distinct `set-stack-policy` commands, each with the correct `CustomerTariff/*` stack paired with its `foundation-/agentcore-/backend-api-allow-all.json` body. Acceptance greps verified each file reference individually. |
| T-10-02-06 (Tampering: drill steps mis-ordered) | mitigate | Python assertion in overall verification confirms Step 1 contains `narrative=off`, Step 2 contains `build:mock`, Step 3 contains `demo-v1.0`, with strict ascending line-index order. |
| T-10-02-07 (EoP: runbook commands missing --profile cevo-dev25) | mitigate | Every `aws cloudformation` / `aws dynamodb` command in §7-§10 carries `--region us-east-1 --profile cevo-dev25`. Verified via grep during Task 4 verification. |
| T-10-02-08 (Repudiation: section renumber diverges from D-20 without traceability) | accept (documented divergence) | PATTERNS.md line 406 cited in both the DEMO-RUNBOOK.md section separator and the 10-VALIDATION.md row comment. SUMMARY Decisions section documents the rationale in detail. |

**New threat surface introduced:** None detected. No new network endpoints, no new auth paths, no new file-access patterns. The committed artefacts are all inert documentation (manifests + runbooks) or lockfiles (hash-pinned package declarations). The only cross-trust-boundary action these enable is the 10-03 operator ceremony (AWS CloudFormation + DynamoDB API calls via CLI), which is scoped to 10-03's execution.

## User Setup Required

None. The artefacts ship as committed files. The 10-03 ceremony execution will consume them, but that is a separate plan's scope.

## Next Phase Readiness

### Preconditions for plan 10-03 (T-48h ceremony execution)

- ✅ Hash-pinned `requirements.txt` + `requirements-dev.txt` exist; fresh-venv `--require-hashes` install succeeds on both.
- ✅ `FREEZE-MANIFEST.md` template scaffolded with all 8 D-10 keys; operator fills `<pending>` placeholders in 10-03 Task 6.
- ✅ `10-DRILL-LOG.md` skeleton scaffolded with 5 speed-first drill step blocks + Commands appendix; operator populates during drill execution in 10-03 Task 3.
- ✅ `DEMO-RUNBOOK.md` extended with §7-§10 ceremony sections; operator follows §7 steps 1-7 as the ceremony spine.
- ✅ `10-VALIDATION.md` row 10-02-06 regex updated to match the renumbered §7-§10 sections; plan 10-03 verification map consistent.
- ✅ pytest baseline invariant holds (183 passed / 6 skipped / 0 failed).
- ✅ 10-01 wave 1 artefacts still in place: 6 stack-policy JSON bodies + `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh` all present and referenced by §7.4 / §7.6 of the runbook.

### Link readiness for downstream plans

- Plan 10-03 §7.1 can directly run `git clone . /tmp/freeze-repro && .venv/bin/pip install --require-hashes -r requirements-dev.txt`.
- Plan 10-03 §7.4 can cite `file://infrastructure/stack-policies/*-freeze.json` for the three `set-stack-policy` calls.
- Plan 10-03 §7.5 has a ready-to-run DynamoDB backup + AVAILABLE wait-loop.
- Plan 10-03 §7.6 can use `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh` + `sha256sum` for lockfile hashes.
- Plan 10-03 §7.7 has the `git tag -a demo-v2.0` + `git push origin demo-v2.0` flow scripted.

### Blockers or concerns

- **Environment footnote** (not a blocker): Operator running 10-03 should `unset AWS_PROFILE` before running pytest baseline (`cevo-25` env var is known-bad per STATE.md 06.1-02 + 10-01-SUMMARY.md). `export AWS_PROFILE=cevo-dev25` is needed for AWS CLI commands in §7.2 / §7.4 / §7.5.
- **pip-tools install footnote** (not a blocker): If 10-03 needs to re-run `pip-compile` for any reason, `pip-tools>=7.4.0` must be present in the active Python env. It is NOT pinned in `requirements-dev.txt`. `pip install --user --break-system-packages 'pip-tools>=7.4.0'` is the standard install for macOS system Python 3.13.

## Self-Check

**Files claimed:**

- ✅ `requirements.in` — FOUND
- ✅ `requirements-dev.in` — FOUND
- ✅ `requirements.txt` — MODIFIED (hash-pinned, 21 packages)
- ✅ `requirements-dev.txt` — MODIFIED (hash-pinned, 11 packages)
- ✅ `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` — FOUND
- ✅ `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` — FOUND
- ✅ `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` — MODIFIED (10 total H2 numbered sections, 4 new)
- ✅ `.planning/phases/10-freeze-rollback-drill/10-VALIDATION.md` — MODIFIED (row 10-02-06 regex updated)

**Commits claimed (verified via `git log --oneline -5`):**

- ✅ `93b489e` (Task 1) — FOUND
- ✅ `3083f8a` (Task 2) — FOUND
- ✅ `2f63fbc` (Task 3) — FOUND
- ✅ `eea6d21` (Task 4) — FOUND

## Self-Check: PASSED

---
*Phase: 10-freeze-rollback-drill*
*Plan: 02*
*Completed: 2026-04-26*

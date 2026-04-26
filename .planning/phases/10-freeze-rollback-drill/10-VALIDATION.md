---
phase: 10
slug: freeze-rollback-drill
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-26
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **Phase 10 is artefact-driven validation**, not code-test-driven — Phase 10 adds no new pytest code. Validation = manifest YAML schema checks, git tag presence, CFN API queries, `cdk diff` output, hash-roundtrip checks.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.0+ (already installed) — used only for the D-19 reproducibility gate, not new tests |
| **Config file** | `pytest.ini` at repo root (existing) |
| **Quick run command** | `pytest -m "not smoke" -x --tb=short` |
| **Full suite command** | `pytest -m "not smoke"` |
| **Estimated runtime** | ~10 seconds (81 pass / 6 skip baseline) |

---

## Sampling Rate

- **After every task commit (plans 10-01, 10-02):** `pytest -m "not smoke" -x --tb=short` — the 81-pass baseline must hold (Phase 10 adds no code, so any change means churn was unintended)
- **After every plan wave:** `pytest -m "not smoke"` full run
- **Before `/gsd-verify-work` (plan 10-03 ceremony):** every row in the Per-Task Verification Map below must PASS with evidence in FREEZE-MANIFEST.md or 10-DRILL-LOG.md
- **Max feedback latency:** 10 seconds (pytest baseline)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | DEMO-04 | Deny-Update:* policy JSON committed | artefact presence | `test -f infrastructure/stack-policies/foundation-freeze.json && jq -e '.Statement[0].Effect=="Deny" and .Statement[0].Action=="Update:*"' infrastructure/stack-policies/foundation-freeze.json` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | DEMO-04 | All 3 freeze policy JSONs committed | artefact presence | `for s in foundation agentcore backend-api; do test -f infrastructure/stack-policies/${s}-freeze.json || exit 1; done` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | DEMO-04 | All 3 allow-all break-glass policy JSONs committed | artefact presence | `for s in foundation agentcore backend-api; do test -f infrastructure/stack-policies/${s}-allow-all.json || exit 1; done` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | DEMO-04 | UI dist content-manifest hash is cross-rebuild stable | reproducibility check | `H1=$(scripts/hash_dist.sh ui/dist); rm -rf ui/dist && (cd ui && npm run build); H2=$(scripts/hash_dist.sh ui/dist); [ "$H1" = "$H2" ]` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 1 | DEMO-04 | Synth asset content-manifest helper strips .pyc | helper correctness | `cdk synth && scripts/hash_synth_assets.sh cdk.out/ \| grep -v -E '\.pyc\|__pycache__'` returns non-empty | ❌ W0 | ⬜ pending |
| 10-01-06 | 01 | 1 | — | pytest baseline holds after 10-01 commits | regression | `pytest -m "not smoke"` → `81 passed, 6 skipped` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 2 | DEMO-04 | `requirements.in` + `requirements-dev.in` committed as source-of-truth | artefact presence | `test -f requirements.in && test -f requirements-dev.in` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 2 | DEMO-04 | `requirements.txt` has `--hash=sha256:` entries on every dep | hash-pin check | `python3 -c "import re,sys; t=open('requirements.txt').read(); pkgs=[l for l in t.splitlines() if l and not l.startswith(('#','-','--'))]; [sys.exit(f'unpinned: {p}') for p in pkgs if '--hash=sha256:' not in p]"` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 2 | DEMO-04 | `requirements-dev.txt` hash-pinned | hash-pin check | same pattern as 10-02-02 on `requirements-dev.txt` | ❌ W0 | ⬜ pending |
| 10-02-04 | 02 | 2 | DEMO-04 | `pip install --require-hashes -r requirements-dev.txt` succeeds in fresh venv | reproducibility | `python3 -m venv /tmp/hashcheck && /tmp/hashcheck/bin/pip install --require-hashes -r requirements-dev.txt` → exit 0 | ❌ W0 | ⬜ pending |
| 10-02-05 | 02 | 2 | DEMO-04 | `FREEZE-MANIFEST.md` template has all D-07/D-10 top-level keys | schema | `python3 -c "import yaml,re,sys; m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(), re.S).group(1)); expected={'git','lockfiles','dist_bundles','synth_assets','cloudformation','bedrock_model_id','dynamodb_backup','break_glass'}; missing=expected-m.keys(); sys.exit(f'missing keys: {missing}' if missing else 0)"` | ❌ W0 | ⬜ pending |
| 10-02-06 | 02 | 2 | DEMO-04 | DEMO-RUNBOOK.md has new §7–§10 headings (renumbered from D-20 §3–§6 per 10-PATTERNS.md line 406 — original numbers collided with existing file's cheat-sheet/launch/fallback/teardown sections) | artefact | `grep -cE '^## (7\|8\|9\|10)\. ' .planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` returns `4` | ❌ W0 | ⬜ pending |
| 10-02-07 | 02 | 2 | — | pytest baseline holds after 10-02 commits | regression | `pytest -m "not smoke"` → `81 passed, 6 skipped` | ✅ | ⬜ pending |
| 10-03-01 | 03 | 3 | DEMO-04 | `cdk diff` empty on all 3 stacks at ceremony time | drift gate | `cdk diff CustomerTariff CustomerTariffAgent CustomerTariffApi 2>&1 \| grep -E '(no differences\|Number of stacks with differences: 0)'` | ❌ W0 | ⬜ pending |
| 10-03-02 | 03 | 3 | DEMO-04 | Stack policy applied on all 3 stacks | API query | `for s in CustomerTariff CustomerTariffAgent CustomerTariffApi; do aws cloudformation get-stack-policy --stack-name $s --profile cevo-dev25 --query 'StackPolicyBody' --output text \| jq -e '.Statement[0].Effect=="Deny"' \|\| exit 1; done` | ❌ W0 | ⬜ pending |
| 10-03-03 | 03 | 3 | DEMO-04 | Termination protection enabled on all 3 stacks | API query | `aws cloudformation describe-stacks --profile cevo-dev25 --query 'Stacks[?starts_with(StackName,\`CustomerTariff\`)].[StackName,EnableTerminationProtection]' --output text \| awk '{exit !($2=="True")}'` | ❌ W0 | ⬜ pending |
| 10-03-04 | 03 | 3 | DEMO-04 | DynamoDB backup exists + ARN captured in manifest | manifest + API | `BACKUP_ARN=$(python3 -c "import yaml,re; m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(), re.S).group(1)); print(m['dynamodb_backup']['backup_arn'])") && aws dynamodb describe-backup --backup-arn "$BACKUP_ARN" --profile cevo-dev25 --query 'BackupDescription.BackupDetails.BackupStatus' --output text \| grep -q AVAILABLE` | ❌ W0 | ⬜ pending |
| 10-03-05 | 03 | 3 | DEMO-04 | Bedrock model ID in manifest matches `agent/agent.py:309` literal | content equality | `LIVE=$(grep -oE 'us\.anthropic\.claude-[a-z0-9.-]+' agent/agent.py \| head -1) && FROZEN=$(python3 -c "import yaml,re; m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(), re.S).group(1)); print(m['bedrock_model_id'])") && [ "$LIVE" = "$FROZEN" ]` | ❌ W0 | ⬜ pending |
| 10-03-06 | 03 | 3 | DEMO-04 | `demo-v2.0` annotated tag exists at freeze commit | git | `git tag -n99 demo-v2.0 \| head -1 \| grep -E '^demo-v2\.0 '` + `git cat-file -t demo-v2.0` returns `tag` (annotated, not lightweight) | ❌ W0 | ⬜ pending |
| 10-03-07 | 03 | 3 | DEMO-04 | `demo-v2.0` pushed to origin (revised D-18 step 7) | git remote | `git ls-remote --tags origin \| grep -q 'refs/tags/demo-v2.0'` | ❌ W0 | ⬜ pending |
| 10-03-08 | 03 | 3 | DEMO-04 | D-19 reproducibility gate: fresh clone + fresh venv pytest green (Rule 3 codified per Rule 4 remediation 2026-04-26: `/opt/homebrew/bin/python3.13` — `/usr/bin/python3` is 3.9.6 and cannot install iniconfig==2.3.0 wheel; `export AWS_PROFILE=cevo-dev25` prevents ProfileNotFound on backend-api-handler test collection) | reproducibility | `git clone . /tmp/freeze-repro && cd /tmp/freeze-repro && /opt/homebrew/bin/python3.13 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt && export AWS_PROFILE=cevo-dev25 && .venv/bin/pytest -m "not smoke"` → `183 passed, 6 skipped, 34 deselected` (Phase 10 closeout baseline per 10-02-SUMMARY deviation 3) | ❌ W0 | ⬜ pending |
| 10-03-09 | 03 | 3 | DEMO-06 | Scratch `tariff-billing-rollback-drill` table has 36 items | AWS CLI | `aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT --profile cevo-dev25 --query 'Count' --output text` returns `36` | ❌ W0 | ⬜ pending |
| 10-03-10 | 03 | 3 | DEMO-06 | `git checkout demo-v1.0` + pytest baseline matches v1.0 | reproducibility | `cd /tmp/freeze-repro && git checkout demo-v1.0 && .venv/bin/pytest -m "not smoke"` → `81 passed, 6 skipped` | ❌ W0 | ⬜ pending |
| 10-03-11 | 03 | 3 | DEMO-06 | `?narrative=off` curl returns non-null `usage_narrative` on green path | live API | `curl -sf "$BACKEND_API_URL/recommendations/CUST-001" \| jq -e '.green.usage_narrative \| strings'` | ❌ W0 | ⬜ pending |
| 10-03-12 | 03 | 3 | DEMO-06 | `npm run build:mock` completes in <10s wall-clock | timed shell | `cd ui && /usr/bin/time -p npm run build:mock 2>&1 \| awk '/^real/{exit $2>10}'` | ❌ W0 | ⬜ pending |
| 10-03-13 | 03 | 3 | DEMO-06 | `build:mock` regenerated `ui/dist-mock` hashes to manifest value (hash-roundtrip) | equality | `H=$(scripts/hash_dist.sh ui/dist-mock) && FROZEN=$(python3 -c "import yaml,re; m=yaml.safe_load(re.search(r'\`\`\`yaml\n(.*?)\n\`\`\`', open('.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md').read(), re.S).group(1)); print(m['dist_bundles']['ui_dist_mock'])") && [ "$H" = "$FROZEN" ]` | ❌ W0 | ⬜ pending |
| 10-03-14 | 03 | 3 | DEMO-06 | 10-DRILL-LOG.md present + every drill step has PASS verdict | artefact | `grep -c '^Verdict: PASS' .planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` returns `>=5` | ❌ W0 | ⬜ pending |
| 10-03-15 | 03 | 3 | DEMO-06 | Scratch drill table deleted post-drill (cleanup gate) | AWS CLI | `aws dynamodb describe-table --table-name tariff-billing-rollback-drill --profile cevo-dev25 2>&1 \| grep -q ResourceNotFoundException` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*"File Exists" column: ✅ = helper/artefact committed before wave runs; ❌ W0 = planner-scaffolded as Wave 0 task dependency; baseline pytest rows stay ✅ because Phase 10 adds no code.*

---

## Wave 0 Requirements

- [ ] `infrastructure/stack-policies/{foundation,agentcore,backend-api}-freeze.json` — deny-Update:* policy bodies (committed in 10-01)
- [ ] `infrastructure/stack-policies/{foundation,agentcore,backend-api}-allow-all.json` — break-glass relock bodies (committed in 10-01)
- [ ] `scripts/hash_dist.sh` — content-manifest hasher for UI dists (D-09 revised; committed in 10-01). Pattern: `(cd "$1" && find . -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | awk '{print $1}')`
- [ ] `scripts/hash_synth_assets.sh` — content-manifest hasher for `cdk.out/asset.*/` dirs stripping `.pyc`/`__pycache__` (D-08 revised; committed in 10-01)
- [ ] `requirements.in` + `requirements-dev.in` — pip-compile source-of-truth (committed in 10-02)
- [ ] `.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` — scaffolded template with empty hash fields + break-glass block (committed in 10-02)
- [ ] DEMO-RUNBOOK.md §3–§6 amendments (committed in 10-02)
- [ ] `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` — runbook skeleton + Commands appendix (scaffolded in 10-02, populated in 10-03)

*No new pytest test files. Existing `pytest -m "not smoke"` baseline is the reproducibility gate (D-19), not a Phase-10-authored test.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `?narrative=off` visually hides narrative rows in browser at 1280×800 | DEMO-06 | Flag is client-side JS; HTML identical; Playwright/headless-browser automation rejected in D-15 | Open `https://<frontend-url>/?narrative=off` in desktop browser at 1280×800; visually confirm narrative rows absent; screenshot into 10-DRILL-LOG.md evidence block |
| Human checkpoint before `git tag -a demo-v2.0` | DEMO-04 | 10-03 `autonomous: false` gate per D-21; operator confirms drill passed + manifest complete before the tag is cut | Re-read 10-DRILL-LOG.md final verdict row; re-read FREEZE-MANIFEST.md `dist_bundles:` + `synth_assets:` + `dynamodb_backup:` fields non-empty; type `yes` when prompted |
| Human checkpoint before `git push origin demo-v2.0` | DEMO-04 | Push is low-risk but irreversible on a public-ish remote; double-confirm (revised D-18 step 7) | Confirm `git tag -n99 demo-v2.0` annotation is correct; run `git push origin demo-v2.0` |
| Break-glass dry-run familiarity | DEMO-04 | D-04 human-gated by design; ensures operator can execute the documented relock sequence under pressure | Optional pre-demo: operator reads FREEZE-MANIFEST.md break-glass section aloud end-to-end; no AWS calls |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all ❌ W0 references (8 helpers/artefacts above)
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s (pytest baseline)
- [ ] `nyquist_compliant: true` set in frontmatter after plan-checker pass

**Approval:** pending

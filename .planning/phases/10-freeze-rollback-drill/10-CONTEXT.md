# Phase 10: Freeze + Rollback Drill - Context

**Gathered:** 2026-04-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock the production AWS stack against drift at T-48h **and** drill the rollback mechanism before depending on it at presentation time. Closes **DEMO-04** (freeze) and **DEMO-06** (rollback drill). Final phase of the v2.0 milestone — emits the `demo-v2.0` annotated git tag.

**In scope (Phase 10 only):**

1. **Reproducibility** — `pip-compile --generate-hashes` on `requirements.txt` + `requirements-dev.txt`; verify `npm ci` reproduces UI build against committed `ui/package-lock.json`; reproducibility gate (`pytest -m "not smoke"` green) run from a fresh git clone + fresh venv by the freeze owner.
2. **Drift gate** — `cdk diff` empty against all three stacks (FoundationStack, AgentCoreStack, BackendApiStack) at freeze time.
3. **Rollback drill (DEMO-06)** — scratch `tariff-billing-rollback-drill` table restored from on-demand backup in the same account/region (us-east-1, account 588738606436); `git checkout demo-v1.0` + `pytest -m "not smoke"` green from clean tree; `?narrative=off` browser + curl proof against live endpoint; `build:mock` regenerates `ui/dist-mock/` <10s from committed sources. All evidence captured into `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md`.
4. **Stack lock** — CFN stack policies deny `Update:*` on FoundationStack, AgentCoreStack, BackendApiStack via CDK-native `add_override` (travels with stack definition, survives `cdk deploy`); termination protection enabled on all three stacks via `aws cloudformation update-termination-protection` (manual at T-48h, not CDK code — stays a freeze-time posture).
5. **Backup** — DynamoDB on-demand backup of `tariff-billing`; backup ARN + UTC timestamp captured.
6. **FREEZE-MANIFEST.md** — single sectioned YAML-in-fence with: lockfile sha256s, dist bundle sha256s (sorted-file tar per dist), cdk synth asset sha256s (double-synth reproducibility proof), CloudFormation StackIds (all 3), DynamoDB backup ARN + timestamp, pinned Bedrock model ID, freeze commit SHA + UTC timestamp, break-glass unlock steps.
7. **Tag** — annotated `demo-v2.0` tag cut on `main` at the freeze commit **after** the drill passes.
8. **DEMO-RUNBOOK amendment** — add T-48h freeze ceremony, T-30m keep-alive start, T-10m prewarm, T-eval harness gates to existing `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` (already holds T-24h visual rehearsal; Phase 10 extends in place).

**Out of scope (Phase 10 does NOT do):**

- Any change to `agent/`, `agent/narrative/`, `api_lambda/`, `ui/src/`, or `scripts/`. Phases 6–9 contracts are frozen; Phase 10 only adds stack policy blocks to `infrastructure/`.
- Pushing any tag to origin — `demo-v1.0` is local-only and `demo-v2.0` will be too (no origin configured).
- Auto-destroying / recreating AWS resources during the freeze window. The 'don't touch AWS between tag and demo' discipline (STATE.md D-13) is load-bearing.
- `scripts/freeze-unlock.sh` / `scripts/freeze-relock.sh` pair — break-glass is human-gated runbook text, not automation.
- A full `cdk deploy` of demo-v1.0 stacks during the drill — scratch-region deploy is rejected; git-checkout + pytest is the v1.0 revert proof.
- Playwright / headless-browser automation for `?narrative=off` verification — manual browser check + curl assertion is the presenter-friendly proof.
- CI-run reproducibility gate — no origin, no CI; freeze-owner-on-fresh-clone is the current-state answer.
- Changes to v1.0 artefacts under `.planning/milestones/v1.0-phases/` other than amending DEMO-RUNBOOK.md in place.
- Re-deploying live AWS stacks solely to force reapplication of the new stack policies — planner decides whether the policy-reapply deploy is Phase 10 scope or T-48h operator work.

**Success criteria (from ROADMAP.md):**

1. `pip-compile --generate-hashes` produces pinned `requirements.txt` + `requirements-dev.txt` that rebuild byte-identical Lambda bundles from a clean venv; `npm ci` reproduces the UI build against committed `ui/package-lock.json`.
2. CloudFormation stack policies deny `Update:*` on FoundationStack, AgentCoreStack, BackendApiStack; FoundationStack is termination-protected (extended to all 3 stacks per D-02); `cdk diff` empty against deployed stack at freeze time.
3. On-demand DynamoDB backup taken; `FREEZE-MANIFEST.md` captures SHA-256 of lockfiles + dist bundles + CloudFormation stack IDs + pinned Bedrock model ID as YAML inside a Markdown code fence.
4. Annotated `demo-v2.0` tag cut on `main`; reproducibility gate (`pytest -m "not smoke"` green from a clean tree) holds.
5. Rollback drill at T-48h proves: revert to `demo-v1.0` works from clean tree, `?narrative=off` toggles narrative off without redeploy, `build:mock` regenerates the <10s emergency UI swap dist.

</domain>

<decisions>
## Implementation Decisions

### Stack Lock Mechanism

- **D-01:** CFN stack policies applied **CDK-native via `add_override`** — one block per stack in `infrastructure/foundation_stack.py`, `infrastructure/agentcore_stack.py`, `infrastructure/backend_api_stack.py`. Pattern: `stack.node.default_child.add_override("StackPolicy", {...})` or equivalent documented approach. Policy travels with the stack definition; any future `cdk deploy` re-applies it. Alternative (`aws cloudformation set-stack-policy` post-deploy as a shell step) rejected because it introduces drift risk between stack code and post-deploy state. Researcher confirms the exact CDK override syntax — the `.template_options` / escape-hatch path for CFN stack policies is not first-class CDK.

- **D-02:** `Update:*` deny AND termination protection applied to **all three stacks** (FoundationStack, AgentCoreStack, BackendApiStack). ROADMAP SC-2 names all three for the `Update:*` deny verbatim; REQUIREMENTS.md names only FoundationStack for termination protection but the ROADMAP is the primary authority and extending termination protection is additive safety. All three stacks hold irrecoverable or hard-to-recreate state during the freeze window: Foundation holds the DynamoDB billing table, AgentCore holds the stable `tariff_agent-O2Hai86N8V` runtime ARN, Backend holds the API Gateway stage the UI calls — recreating any triggers a new ARN/endpoint that invalidates the manifest.

- **D-03:** Termination protection enabled **manually at T-48h via `aws cloudformation update-termination-protection --enable-termination-protection --stack-name <each>`** — NOT CDK code. Non-freeze `cdk deploy` / `cdk destroy` cycles for future development stay unaffected. Cleanup command captured in FREEZE-MANIFEST.md break-glass: `aws cloudformation update-termination-protection --no-enable-termination-protection --stack-name <each>`. Framing: termination protection is a freeze-time *posture*, not permanent architecture; stack policy is the architectural lock.

- **D-04:** Break-glass procedure **documented in FREEZE-MANIFEST.md break-glass section** — no shipped scripts. If an emergency fix needs to redeploy during the freeze window, operator runs the documented unlock commands (disable termination protection per stack + `aws cloudformation set-stack-policy --stack-name <stack> --stack-policy-body <allow-all>`), applies the fix, re-runs the freeze ceremony to relock. Break-glass is human-gated — no script, no CI, no automation. Matches the 'tag-revert-is-authoritative' philosophy (REQUIREMENTS.md Key Decisions locked).

- **D-05:** `cdk diff` gate: **all three stacks clean** via `cdk diff FoundationStack AgentCoreStack BackendApiStack`. Any reported change blocks tag cut. Freeze script captures full stdout of `cdk diff` into FREEZE-MANIFEST.md evidence section. Single-synth approach (no `--app cdk.out/` compare); the deployed state vs local code comparison is what `cdk diff` does by default.

### FREEZE-MANIFEST Format & Hashing

- **D-06:** File location: **`.planning/phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`**. Gets committed to main as part of the Phase 10 close; the `demo-v2.0` tag points at the commit that adds this file. Not placed at repo root because it's phase-scoped evidence, not runtime config.

- **D-07:** Manifest structure: **single sectioned YAML-in-fence**. One Markdown file with one `yaml` code fence containing all freeze evidence. Top-level keys: `lockfiles:`, `dist_bundles:`, `synth_assets:`, `cloudformation:`, `bedrock_model_id:`, `git:`, `dynamodb_backup:`, `break_glass:`. Human-readable in GitHub view, machine-parseable during the drill (`python -c "import yaml; print(yaml.safe_load(open('FREEZE-MANIFEST.md').read().split('\`\`\`yaml')[1].split('\`\`\`')[0]))"` or similar). Outside the code fence: short prose framing (what this manifest is, when it was frozen, what invalidates it).

- **D-08:** Lambda bundle reproducibility proved by **`cdk synth` twice + sha256 of `cdk.out/asset.<hash>/` bundles**. Sequence: (1) from a clean git clone of the freeze commit, create a fresh venv, `pip install --require-hashes -r requirements.txt`, run `cdk synth`, record sha256 of each asset zip under `cdk.out/`; (2) in a separate tmp dir, repeat from scratch, record sha256s again; (3) assert identical. Manifest stores: final asset sha256s + freeze commit SHA. Wheel hashes are the *input* proof (captured by `pip-compile --generate-hashes` in requirements.txt itself), not duplicated in the manifest. The synth-twice evidence is the *output* proof — what actually matters for the Lambda bundle at deploy time.

- **D-09:** UI dist hashing: **sha256 of sorted-file tar per dist dir**. Command: `find ui/dist -type f | sort | tar -cf - -T - | sha256sum` for both `ui/dist/` (primary build) and `ui/dist-mock/` (emergency `build:mock` fallback). Stable across Vite output ordering jitter; captures every file exactly once; one sha256 per dist; two sha256s total in the manifest. Rejected alternatives: per-file hash listing (too noisy for a single-shot manifest), gzipped archive hash (`--sort=name` is GNU-tar-only and fragile on the macOS dev machine the freeze owner uses). The freeze ceremony rebuilds both dists from source before hashing — the committed `ui/dist/` is not trusted as-is.

- **D-10:** Manifest metadata sections populated:
  - `git:` — freeze commit SHA + ISO-8601 UTC freeze timestamp.
  - `cloudformation:` — StackId ARN for all three stacks (matches ROADMAP SC-3 'CloudFormation stack IDs' wording literally; StackId is rename-immune, unlike stack name).
  - `dynamodb_backup:` — on-demand backup ARN + ISO-8601 UTC time the backup was taken.
  - `bedrock_model_id:` — full ID as pinned in `agent/agent.py` (currently `us.anthropic.claude-sonnet-4-6` at `agent/agent.py:309`). Proves no silent model swap between freeze and demo.
  - `lockfiles:` — sha256 of `requirements.txt`, `requirements-dev.txt`, `ui/package-lock.json`.
  - `dist_bundles:` — sha256 of primary + mock dist (D-09).
  - `synth_assets:` — sha256 per `cdk.out/asset.<hash>/` (D-08).
  - `break_glass:` — prose + command block; see D-04.

- **D-11:** AgentRuntimeArn + ApiEndpoint are **NOT duplicated into FREEZE-MANIFEST.md**. They already live in `.planning/STATE.md` and Phase 5 deploy outputs (`.planning/milestones/v1.0-phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md`). Cross-referencing invites staleness; duplicating invites drift. Only `bedrock_model_id` (ROADMAP SC-3 literal) and the `cloudformation:` StackIds (rename-immune identifiers not in STATE.md) are in the manifest. Freeze owner is responsible for confirming STATE.md values match reality at T-48h — not Phase 10's job.

### Rollback Drill Mechanism

- **D-12:** Scratch DynamoDB restore target: **new table `tariff-billing-rollback-drill` in us-east-1, account 588738606436** (same region/account as live). Command: `aws dynamodb restore-table-from-backup --target-table-name tariff-billing-rollback-drill --backup-arn <D-10 backup ARN>`. Assertions: `aws dynamodb scan --table-name tariff-billing-rollback-drill --select COUNT` returns 36 (3 personas × 12 months); `aws dynamodb get-item` on `CUST-001` / month `2025-04` returns the expected kWh reading (spot-check at least one record from each persona, matching Phase 1 seed data). Teardown at drill end: `aws dynamodb delete-table --table-name tariff-billing-rollback-drill` — scratch table removed before Phase 10 closes. Rejected: restore-in-place (violates freeze discipline), cross-region restore (Bedrock availability complexity for zero benefit).

- **D-13:** `demo-v1.0` revert proof: **`git checkout demo-v1.0` + `pytest -m "not smoke"` green from a clean tree**, run from a fresh clone + fresh venv. Does NOT re-deploy to AWS. The whole architecture of the rollback mechanism (feature flag primary, tag secondary, build:mock emergency) is precisely so that tag-revert is a source-tree operation, not an AWS operation. Captured evidence: `git rev-parse HEAD` (confirms tag points at expected v1.0 commit `aba3a99`) + `pytest` stdout tail showing pass count matches v1.0 baseline (v1.0 summary: `81 passed, 6 skipped` from `pytest -m "not smoke"`). Both go into 10-DRILL-LOG.md.

- **D-14:** Drill format: **manual runbook in `10-DRILL-LOG.md`** with scripted sub-commands in a `## Commands` appendix. Operator follows numbered steps from the runbook top-level, pastes `$command` + `stdout` into the log with ISO-8601 UTC timestamps. Expensive / repeatable steps (restore-from-backup, row-count scan, `?narrative=off` curl, `build:mock` timing, pytest invocation) are listed as one-liners in the appendix so the operator copies them verbatim — reduces typo risk at 3am-before-the-demo. No end-to-end bash script (100+ lines of bash for one-shot use rejected on maintenance-cost grounds). Rejected: scripted pipeline (brittle, used once); playwright automation (new dev dep).

- **D-15:** `?narrative=off` drill proof: **manual browser check + curl assertion against live endpoint**. Three-step sequence: (1) `curl -s "${BACKEND_API_URL}/recommendations/CUST-001" | jq '.green.usage_narrative'` returns a non-null string; (2) open `https://<frontend-url>/?narrative=off` in a browser; (3) visually verify narrative rows absent, screenshot at 1280×800; paste both curl stdout and screenshot reference into 10-DRILL-LOG.md. The flag is client-side URL-param logic (Phase 8 D-10 contract: UI collapses to v1.0 shape in loading + success states) so the API call still returns narrative data — proof is that the UI hides it, not that the API stops returning it. Rejected alternatives: pure-curl HTML diff (the HTML bundle is identical either way — flag is runtime JS), Playwright DOM assertion (new dep).

- **D-16:** `build:mock` <10s drill proof: run `time npm run build:mock` from `ui/` on the operator's machine, paste real output (`real 0m8.412s` or similar) into 10-DRILL-LOG.md. Assert wall-clock < 10s; assert `ui/dist-mock/` regenerates; assert the regenerated dist hash matches D-09's manifest entry (this is the reproducibility-round-trip proof — manifest hash was computed on a freshly-built dist, drill regenerates the same dist and hashes to the same value).

- **D-17:** Drill closeout evidence: `10-DRILL-LOG.md` captures for each step — step number + name, ISO-8601 UTC start timestamp, command(s) run, stdout excerpt (truncated if long), verdict (PASS/FAIL), any deviation notes. Final section: drill verdict (`all 5 SC items PASS — rollback mechanism proven — safe to cut demo-v2.0`), drill duration, operator identity. Phase 10 does NOT close until 10-DRILL-LOG.md is committed AND the drill passes.

### Freeze Ceremony Sequence

- **D-18:** T-48h ceremony step order (load-bearing dependency chain):
  1. **Reproducibility** — `pip-compile --generate-hashes requirements.in → requirements.txt` + same for `requirements-dev`; verify `npm ci` from `ui/package-lock.json` completes cleanly; `pytest -m "not smoke"` green from fresh clone + fresh venv (D-19).
  2. **Drift gate** — `cdk diff FoundationStack AgentCoreStack BackendApiStack` → all clean. Any drift blocks the tag (D-05).
  3. **Rollback drill** — Full 10-DRILL-LOG.md populated (D-12 through D-17). Must pass BEFORE any tag is cut — a failed drill post-tag leaves the tag pointing at an unprovable commit.
  4. **Stack lock** — `cdk deploy` with the new stack policies (D-01); manually enable termination protection on all three stacks via CLI (D-03).
  5. **DynamoDB backup** — `aws dynamodb create-backup --table-name tariff-billing --backup-name tariff-billing-freeze-v2.0-<UTC-date>`. Capture backup ARN + timestamp.
  6. **FREEZE-MANIFEST.md** — compute all hashes (D-08, D-09, D-10), fill manifest, commit.
  7. **Tag** — `git tag -a demo-v2.0 -m "..." <freeze-commit-SHA>` on the manifest-commit SHA. Local-only; no origin push (matches `demo-v1.0` posture).

- **D-19:** Reproducibility gate operator: **freeze owner in a fresh git clone + fresh venv**. Commands: `git clone /path/to/repo /tmp/freeze-repro && cd /tmp/freeze-repro && python -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt && .venv/bin/pytest -m "not smoke"`. Captured stdout tail (showing pass count) goes into FREEZE-MANIFEST.md evidence. Rejected: peer-on-different-machine (no origin push means no peer can pull), CI job (no CI infrastructure). Single-operator discipline matches the solo-demo reality.

- **D-20:** DEMO-RUNBOOK amendments: **edit `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` in place**. Existing v1.0 runbook already has `§2 T-24h visual rehearsal`. Phase 10 appends new sections: `§3 T-48h Freeze Ceremony` (the 7-step D-18 sequence), `§4 T-30m Keep-Alive Start` (`BACKEND_API_URL=… bash scripts/demo-keepalive.sh` in a tmux pane), `§5 T-10m Pre-Warm` (`cd ui && BACKEND_API_URL=… npm run prewarm` asserting exit 0), `§6 T-eval Live Eval Harness Gate` (`BACKEND_API_URL=… pytest tests/test_narrative_eval_live.py -m smoke`). Single canonical runbook for both milestones. Rejected: phase-scoped `10-DEMO-RUNBOOK.md` (splits the presenter's attention), inline-in-manifest (conflates posture with process).

### Plan Structure

- **D-21:** Phase 10 splits into **3 plans**:
  - **10-01** (Wave 1, autonomous): CDK changes — add stack policy `add_override` blocks to all three stacks; add a Python helper script `scripts/verify_synth_repro.py` (or inline in plan summary) that does the double-synth sha256 comparison. Researcher confirms the exact CDK escape-hatch syntax. No AWS changes; planner can run `cdk synth` to verify locally.
  - **10-02** (Wave 2, autonomous, depends on 10-01): Freeze ceremony artefacts — run `pip-compile --generate-hashes`, scaffold FREEZE-MANIFEST.md template (empty hash fields, all structural keys present), update DEMO-RUNBOOK.md with §3–§6 per D-20. This plan does NOT fill the manifest hashes or cut the tag — those belong to 10-03.
  - **10-03** (Wave 3, **autonomous: false** — human checkpoint before tag): T-48h ceremony execution — operator runs steps 1–7 of D-18 sequence, fills FREEZE-MANIFEST.md hashes, runs the rollback drill (populates 10-DRILL-LOG.md), takes DynamoDB backup, enables termination protection, cuts `demo-v2.0` tag. Human checkpoint: 'drill passed, manifest complete, safe to tag?' before the `git tag` step.

- **D-22:** Phase 10 closeout gate (documented in 10-03 plan SUMMARY):
  1. All 6 success criteria from ROADMAP SC-1 through SC-5 verified via 10-DRILL-LOG.md + FREEZE-MANIFEST.md.
  2. `demo-v2.0` annotated tag present on `main` at the freeze commit; `git tag -n99 demo-v2.0` shows the annotation.
  3. `pytest -m "not smoke"` still green from the freeze commit (81 passed / 6 skipped baseline holds — Phase 10 adds no runtime code, so no test churn expected).
  4. `cdk diff` empty across all three stacks.
  5. Scratch drill table `tariff-billing-rollback-drill` deleted (cleanup complete).
  6. Termination protection enabled on all three stacks (verified via `aws cloudformation describe-stacks --query 'Stacks[].{name: StackName, tp: EnableTerminationProtection}'`).
  7. Stack policy in effect on all three stacks (verified via `aws cloudformation get-stack-policy --stack-name <each>`).
  8. FREEZE-MANIFEST.md committed; 10-DRILL-LOG.md committed; DEMO-RUNBOOK.md amended.

### Claude's Discretion

- **Exact CDK `add_override` syntax for CFN stack policies** — researcher confirms the escape-hatch path. CFN stack policies are not first-class CDK constructs; planner decides whether to use `stack.template_options.metadata` / `CfnResource.add_override` / `cdk.CfnStackPolicy` construct (if it exists) / post-synth JSON patch. Recommend: whichever minimises freeze-surface delta.
- **Whether FREEZE-MANIFEST.md template lives in `.planning/phases/10-*/` (phase-scoped, follows it into `.planning/milestones/v2.0-phases/` at milestone close) or at `.planning/FREEZE-MANIFEST.md` (repo-root, survives milestone archival).** Recommend phase-scoped per D-06; planner has final say.
- **Whether `scripts/verify_synth_repro.py` ships as a reusable artefact (committed to `scripts/`) or runs inline as a one-time check in 10-03 plan summary**. Recommend inline-in-plan-summary — freeze is one-shot, script surface for one-shot use is excessive. Planner decides if rehearsal reveals reuse need.
- **Exact wording / tone of the break-glass section in FREEZE-MANIFEST.md.** Should be presenter-adjacent (assume operator is stressed, 3am pre-demo) — clear command blocks, minimal prose, explicit 'after fix, re-run freeze ceremony steps 2–7' reminder.
- **Whether `pip-compile` output diff from the current `requirements.txt` is zero-delta** (current `requirements.txt` is not hash-pinned — it has `>=` constraints). Planner handles the `pip-compile` workflow: either pins to exact current-resolved versions, or lets pip-compile freshly resolve. Either produces a hash-pinned file; the former is safer for freeze.
- **Whether the rollback drill spot-check on DynamoDB restored table includes all 3 personas × 1 month or 1 persona × multiple months.** Recommend 3 personas × 1 month (confirms data breadth); planner decides the specific months.
- **ISO-8601 timestamp format in 10-DRILL-LOG.md** — recommend `YYYY-MM-DDTHH:MM:SSZ` (UTC, no subsecond) for readability; planner uses whatever `date -u +%Y-%m-%dT%H:%M:%SZ` produces.
- **Whether DEMO-RUNBOOK.md gets a single monolithic edit or multiple small commits per section.** Recommend single edit committed as part of 10-02; the sections are tightly coupled.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Requirements + Roadmap

- `.planning/REQUIREMENTS.md` — §"Demo Hardening — Freeze & Rollback (DEMO)" for DEMO-04 (full bullet list Phase 10 must close) + DEMO-06 (drill items). §"Key Decisions Locked at Requirements Stage": rollback mechanism is 'Feature flag + `demo-v1.0` tag + `build:mock` dist, drilled at T-48h'; interim `demo-v1.1` tag NOT cut.
- `.planning/ROADMAP.md` §"Phase 10: Freeze + Rollback Drill" — 5 success criteria (load-bearing for D-01 through D-22).
- `.planning/PROJECT.md` — Current state at Phase 10 start (Phase 9 complete 2026-04-26); "Known pre-presentation work" callout (DEMO-RUNBOOK §2 T-24h visual rehearsal scheduled — runbook now amended in Phase 10 D-20 to add §3–§6).
- `.planning/STATE.md` — Environment lock: `demo-v1.0` annotated tag on commit `aba3a99c67994f39d9d496ddfd29c9116b756928`, tag object `3bb0f51380176deedd1712d5dee17a70ccd94887`, local-only (no origin). AgentRuntimeArn `tariff_agent-O2Hai86N8V` (Phase 10 must not recreate). AWS profile `cevo-dev25`, account 588738606436, us-east-1.

### Prior Milestone Infrastructure

- `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md` — **primary file amended in place by Phase 10** (D-20). Already contains §1 overview + §2 T-24h visual rehearsal. Phase 10 appends §3 T-48h Freeze Ceremony, §4 T-30m Keep-Alive, §5 T-10m Pre-Warm, §6 T-eval Harness Gate.
- `.planning/milestones/v1.0-phases/05-demo-hardening/05-DEPLOY-OUTPUTS.md` — ApiEndpoint URL + AgentRuntimeArn captured at v1.0 deploy. Phase 10 references but does not duplicate into FREEZE-MANIFEST.md (D-11).
- `.planning/milestones/v1.0-ROADMAP.md` — v1.0 decision log; confirms `demo-v1.0` tag at `aba3a99` is the authoritative rollback target.

### Upstream Phase Artefacts (contracts Phase 10 depends on)

- `.planning/phases/06-agent-narrative-guardrail/06-CONTEXT.md` — Phase 6 fallbacks + validator rules frozen (referenced in rollback drill as: 'the v2.0 narrative layer must be intact or fall back gracefully — drill does not re-test this, Phase 6 owns the contract').
- `.planning/phases/07-api-pass-through-pre-warm-route/07-CONTEXT.md` — **D-01 / D-04 / D-06 load-bearing**: `?prewarm=1` query flag returns 204 on all failure modes (operator uses this during T-10m prewarm); `_narrative_source` stripped from non-prewarm responses (still true post-rollback).
- `.planning/phases/08-ui-integration-feature-flag-version-indicator/08-CONTEXT.md` — **D-10 load-bearing for D-15**: `?narrative=off` collapses UI to v1.0 shape in loading AND success states. Phase 10 drill asserts this behaviour against the live endpoint.
- `.planning/phases/09-pre-warm-tooling-eval-harness-keep-alive/09-CONTEXT.md` — **D-22 Phase 9 closeout gate feeds Phase 10 DEMO-RUNBOOK §4–§6**: `npm run prewarm` (exit 0 + <3000ms median), `pytest tests/test_narrative_eval_live.py -m smoke` (green), `bash scripts/demo-keepalive.sh` (ticks every 10m). Phase 9 delivered the tools; Phase 10 codifies their T-x invocation.

### Infrastructure Code (Phase 10 modifies these)

- `infrastructure/foundation_stack.py` — FoundationStack definition; D-01 adds stack policy `add_override` block here.
- `infrastructure/agentcore_stack.py` — AgentCoreStack definition; D-01 adds stack policy here. Contains `CfnOutput AgentRuntimeArn` (infrastructure/agentcore_stack.py:28) — Phase 10 does NOT change this.
- `infrastructure/backend_api_stack.py` — BackendApiStack definition; D-01 adds stack policy here. Contains `CfnOutput ApiEndpoint` (infrastructure/backend_api_stack.py:30) — Phase 10 does NOT change this.
- `infrastructure/constructs/billing_table.py` — currently `removal_policy=RemovalPolicy.DESTROY` + `point_in_time_recovery=False`. Phase 10 does NOT change these (on-demand backup is a one-off CLI operation, not CDK config); break-glass reminds operator to re-enable protection post-demo if the table survives.
- `agent/agent.py:309` — `model_id="us.anthropic.claude-sonnet-4-6"` — pinned Bedrock model. FREEZE-MANIFEST.md `bedrock_model_id:` key reads this value. Phase 10 does NOT change this.

### Lockfiles (Phase 10 modifies `requirements*.txt` via `pip-compile`)

- `requirements.txt` — currently `aws-cdk-lib>=2.250.0 / aws-cdk.aws-bedrock-agentcore-alpha==2.250.0a0 / constructs>=10.0.0 / boto3>=1.42.0`. NOT currently hash-pinned. Phase 10 runs `pip-compile --generate-hashes` to produce a hash-pinned version. May require creating a `requirements.in` source file if one doesn't exist.
- `requirements-dev.txt` — currently `-r requirements.txt / pytest>=7.0 / pytest-mock>=3.0 / requests>=2.28,<3`. Same hash-pinning treatment.
- `ui/package-lock.json` — already exists (214KB, committed). Phase 10 verifies `npm ci` reproduces against it; does not modify.

### v2.0 Research

- `.planning/research/ARCHITECTURE.md` — freeze + rollback architecture if a relevant section exists (Phase 10 researcher verifies; fallback is the v2.0 STATE.md/REQUIREMENTS.md pair).
- `.planning/research/PITFALLS.md` — freeze-adjacent AP items (AP-3 no cached session IDs survives rollback; freeze owner confirms).
- `.planning/research/STACK.md` — Python 3.12 Lambda runtime; cdk bundling behaviour; reproducibility surface.
- `.planning/research/FEATURES.md` — DEMO-RUNBOOK playbook references (Phase 10 amendments land in §3–§6 of the existing runbook).

### External / upstream docs

- AWS CDK: `Stack.node.default_child.add_override()` + `Stack.template_options` — researcher confirms the exact CDK API for setting CFN stack policies (may require escape hatch; no first-class construct as of 2.250.0).
- AWS CloudFormation: `StackPolicyBody` — JSON schema; `"Deny" ... "Update:*"` pattern.
- `aws cloudformation update-termination-protection` CLI reference.
- `aws cloudformation get-stack-policy` — drill / verification command.
- `aws dynamodb create-backup` + `restore-table-from-backup` — backup/restore CLI pattern, backup ARN format.
- `pip-compile --generate-hashes` docs — output format (`--hash=sha256:…` per dep); input file convention (`requirements.in` → `requirements.txt`).
- `git tag -a` annotated tag semantics; `git tag -n99` for annotation display.
- `find ... | sort | tar -cf - -T - | sha256sum` — portable sorted-file hashing pattern (works on BSD tar + GNU tar; avoids `--sort=name` portability issue).
- `time npm run build:mock` — POSIX `time` builtin vs `/usr/bin/time` output format distinction (drill uses shell builtin for simplicity; captures `real X.XXXs` line).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`infrastructure/foundation_stack.py`** (38 lines), **`infrastructure/agentcore_stack.py`** (~45 lines est.), **`infrastructure/backend_api_stack.py`** (~30 lines est.) — small, focused stack files. D-01 stack policy `add_override` block is a ~5-line addition per file.
- **`scripts/capture_samples.py`** (57 lines) — stdlib-first, `sys.exit` taxonomy, `pathlib` for file writes. Convention reference for any Phase 10 Python helper (e.g., `scripts/verify_synth_repro.py` if the planner ships it per Claude's Discretion).
- **`scripts/prewarm.py`** + **`scripts/demo-keepalive.sh`** (Phase 9 artefacts) — already-tested operator tooling referenced by DEMO-RUNBOOK §4–§5 (D-20). Phase 10 does not modify.
- **`tests/test_narrative_eval_live.py`** (Phase 9) — referenced by DEMO-RUNBOOK §6 (D-20).
- **`ui/package.json` scripts block** — already has `build`, `build:mock`, `prewarm`. Phase 10 does not modify.
- **`.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`** — amended in place (D-20), not replaced.
- **`demo-v1.0` annotated tag** — already on `aba3a99`, local-only. Phase 10 follows the exact same local-only posture for `demo-v2.0`.
- **`.gitignore`** — `cdk.out/` is almost certainly ignored; freeze ceremony regenerates it. Planner verifies.

### Established Patterns

- **CDK stack wiring in `infrastructure/<stack>.py` with constructs in `infrastructure/constructs/`** — Phase 10 D-01 adds stack-level policies at the stack file (not construct) level. Construct files stay untouched.
- **Phase artefacts in `.planning/phases/<padded>-<slug>/`** — CONTEXT, PLAN, SUMMARY, VERIFICATION files per phase. FREEZE-MANIFEST.md (D-06) and 10-DRILL-LOG.md (D-17) follow this convention.
- **Annotated-tag posture for milestone boundaries** — `demo-v1.0` pattern: `git tag -a <tag> -m "<annotation>" <commit>`, local-only, no origin push. `demo-v2.0` matches.
- **Runbook amendments in place rather than new files** — DEMO-RUNBOOK.md is the single source of truth for presenter-facing ops; Phase 10 extends it (D-20).
- **v1.0 milestone-archived artefacts live under `.planning/milestones/v1.0-phases/`** — Phase 10 references but does not modify v1.0 files except DEMO-RUNBOOK.md.
- **Exit-code taxonomy for operator scripts** (Phase 9 convention: 0 ok / 1 gate-fail / 2 setup-error) — if Phase 10 ships `scripts/verify_synth_repro.py`, it follows the same taxonomy.

### Integration Points

- **Upstream (Phase 9):** `scripts/prewarm.py`, `scripts/demo-keepalive.sh`, `tests/test_narrative_eval_live.py` — DEMO-RUNBOOK §4–§6 invokes these as-is. Phase 10 does not modify them.
- **Upstream (Phase 8):** `?narrative=off` URL flag contract — D-15 drill step asserts this works against the live endpoint. Phase 10 does not modify the UI.
- **Upstream (Phase 7):** `?prewarm=1` route contract — referenced by T-10m prewarm gate in DEMO-RUNBOOK §5.
- **Upstream (Phase 6):** narrative validator + fallbacks — frozen contract; Phase 10 does not invoke or test directly.
- **Downstream (v2.0 milestone close / `/gsd-complete-milestone`):** `.planning/phases/10-freeze-rollback-drill/` moves to `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/`. FREEZE-MANIFEST.md + 10-DRILL-LOG.md travel with the phase.
- **Downstream (v2.0 demo day):** presenter uses the amended DEMO-RUNBOOK.md as the single operational doc; FREEZE-MANIFEST.md is referenced only if something needs verification or break-glass.
- **Downstream (v3.0 milestone, if ever):** freeze/rollback pattern established here becomes the template. CI-gated reproducibility (deferred) and `scripts/freeze-unlock.sh` (deferred) become candidates when origin push exists.

</code_context>

<specifics>
## Specific Ideas

- **Rollback mechanism is three independent levers, intentionally ordered by speed:** (1) `?narrative=off` URL flag = fastest, no deploy, no git; (2) `demo-v1.0` tag revert = authoritative, source-tree only, ~minutes; (3) `build:mock` dist = emergency <10s UI swap, last-resort. Phase 10 drills all three. The drill ORDER in 10-DRILL-LOG.md matches this speed ordering so the operator-under-pressure sees the cheapest recovery option first.
- **The drill is the real proof — the tag is a bookmark.** A passed drill at T-48h is worth more than the tag itself; the tag is just a label pointing at the verified commit. Never cut the tag before the drill passes (D-18 step order is load-bearing for this reason).
- **Don't trust committed `ui/dist/` — always rebuild.** The v1.0 pattern (from PROJECT.md) is that build output is NOT committed. Freeze ceremony D-09 rebuilds both dists from source before hashing; the hash in FREEZE-MANIFEST.md is the hash of a freshly-built dist, which means the drill regeneration at D-16 will hash to the same value iff reproducibility holds.
- **`us.anthropic.claude-sonnet-4-6` is the current model pin** (`agent/agent.py:309`). This string goes verbatim into `FREEZE-MANIFEST.md` `bedrock_model_id:`. If the model ID changes between freeze and demo, the manifest hash comparison fails and the demo surfaces it. Do not indirect through a constant — write the literal string.
- **Break-glass is human-gated by design.** Resist the urge to automate it. The goal is to make break-glass slightly uncomfortable so it's only used when genuinely necessary; a one-click unlock invites casual use during the freeze window.
- **Termination protection is a freeze-time posture, NOT permanent architecture.** D-03 is deliberate: manual-at-T-48h, not CDK code. Permanent termination protection would taint every future dev cycle. The FREEZE-MANIFEST.md break-glass block spells out the `--no-enable-termination-protection` commands for post-demo cleanup.
- **`cdk diff` clean is the deployment-side mirror of reproducibility.** Reproducibility gate (D-19) proves source tree ⇒ same bundle; `cdk diff` (D-05) proves same bundle ⇒ same deployed stack. Together they close the loop.
- **Scratch table name `tariff-billing-rollback-drill` is presenter-obvious** — if anyone pokes at DynamoDB post-freeze and sees the table, the name explains itself. Deleted at drill end per D-12.
- **The manifest's sectioned YAML is presenter-readable on stage** — if something goes wrong at demo time, the presenter can open FREEZE-MANIFEST.md in GitHub and read 'the live endpoint is at <x>, the backup is at <y>, the break-glass is <z>' without parsing custom formats. Human-first, machine-second.
- **Phase 10 adds no new runtime Python code** (besides optional `scripts/verify_synth_repro.py` per Claude's Discretion). Test-suite churn risk: zero. `pytest -m "not smoke"` baseline (81 passed / 6 skipped) must hold.
- **Drill reproducibility of `build:mock` hash (D-16) is a tight loop:** manifest captures hash_A of freshly-built dist; drill rebuilds and expects hash_A; if hashes differ, the freeze-manifest reproducibility claim is invalid and the drill fails. This is intentional — the drill catches the 'reproducibility was broken between freeze and T-48h' case.

</specifics>

<deferred>
## Deferred Ideas

- **CI-run reproducibility gate** — peer / CI verification of the freeze tag. Rejected for current state (no origin push, no CI infrastructure). Revisit when repo has origin and/or CI exists; would replace D-19's single-operator check with a peer machine or GitHub Actions job.
- **`scripts/freeze-unlock.sh` + `scripts/freeze-relock.sh`** — automated break-glass. Rejected in D-04 (human-gated is the point). Worth recording for 'if freeze pattern is reused across multiple milestones / customers'.
- **Playwright / headless-browser DOM check for `?narrative=off`** — rejected in D-15 (new dev dep for one-shot use). Revisit for v3.0 if automated pre-demo UI verification becomes a recurring need.
- **End-to-end drill pipeline script (`scripts/rollback-drill.sh`)** — rejected in D-14. Maintenance cost for one-shot use. Revisit if the demo becomes a recurring customer engagement and the drill is run monthly.
- **Permanent `termination_protection=True` in CDK code** — rejected in D-03 (freeze-time posture, not architecture). Revisit if this engagement transitions to a long-lived production deployment (v3.0 PROD-01 / PROD-02).
- **Cross-region scratch DynamoDB restore (us-west-2)** — rejected in D-12. Revisit only if the primary region becomes untrustworthy for drill purposes (very unlikely).
- **Full `cdk deploy` of demo-v1.0 stacks in the drill** — rejected in D-13. The whole rollback architecture is source-tree-first; an AWS-side drill is redundant. Revisit if a future incident reveals the source-tree test was insufficient.
- **`scripts/verify_synth_repro.py` as a committed, reusable artefact** — deferred per Claude's Discretion. Revisit if rehearsal shows inline-in-plan-summary is insufficient.
- **Phase-scoped `10-DEMO-RUNBOOK.md`** — rejected in D-20. Single canonical runbook is better. Revisit only if v3.0 runbook divergence is needed (e.g., customer-facing portal adds operator responsibilities).
- **Duplicating AgentRuntimeArn + ApiEndpoint into FREEZE-MANIFEST.md** — rejected in D-11. Source of truth lives in STATE.md + 05-DEPLOY-OUTPUTS.md. Revisit if either of those files is ever deleted / renamed.
- **Hash-pinning only `requirements.txt` (leaving `requirements-dev.txt` unpinned)** — rejected; both must be pinned for true reproducibility (Phase 10 test-pass gate uses `requirements-dev.txt`).
- **Per-file sha256 of dist bundles instead of sorted-file-tar** — rejected in D-09. Noisy; presenter-unfriendly. Revisit only if individual-file diffing becomes a post-incident need.
- **Monolithic single-plan Phase 10** — considered; rejected for D-21 3-plan split. Revisit if the split proves over-engineered in retrospective.
- **EventBridge / scheduled freeze verification** — out of scope; v3.0 production hardening. Single-shot demo.
- **Cloud backup to S3 (beyond DynamoDB on-demand)** — out of scope. The DynamoDB on-demand backup is sufficient for the 36-record dataset; S3 copy adds freeze surface for no drill benefit.

</deferred>

---

*Phase: 10-freeze-rollback-drill*
*Context gathered: 2026-04-26*

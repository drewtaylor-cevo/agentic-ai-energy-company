# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.0 — Demo Polish & LLM Narrative

**Shipped:** 2026-04-26
**Phases:** 5 (+1 decimal phase 6.1) | **Plans:** 16 | **Tasks:** 47
**Git range:** `demo-v1.0..demo-v2.0` (157 commits, +4,392 / −29 lines across 63 source files)

### What Was Built

- **LLM-narrative layer (Phase 6 + 6.1):** `usage_narrative` + `call_script` fields on every recommendation card, Pydantic validator hard-rejecting digits/currency symbols, banned-terms regex (6 competitors + 28 switch verbs + 12 env superlatives), 12 per-persona × per-card committed fallbacks, retry-once-then-fallback wired into `invoke()`. Phase 6.1 inserted mid-milestone to resolve a Claude Sonnet 4.6 + Strands `structured_output` tool-use regression — migrated to `Agent.structured_output_model` and restored byte-exact DEMO-02 savings.
- **API pass-through + pre-warm route (Phase 7):** `api_lambda/handler.py` strips `_narrative_source` marker, forwards narrative fields byte-identically, `?prewarm=1` returns HTTP 204 with swallow-all exception handling. CDK wires API Gateway to a named Lambda alias `live` with context-gated Provisioned Concurrency (`-c demo_pc=N`, defaults to 0 for cost safety).
- **UI integration (Phase 8):** narrative rows render italic-muted + track-accent bordered call-script quote block, matching skeleton placeholders, `?narrative=off` URL kill switch (byte-equivalence with v1.0 shape in both loading AND success), `v2.0 · <git-sha>` bottom-right version indicator via build-time `__GIT_SHA__` Vite define.
- **Pre-warm tooling + eval harness (Phase 9):** stdlib-only `scripts/prewarm.py` (2-pass warm + 9 measurement GETs, 3000ms median gate, 0/1/2 exit taxonomy), `scripts/demo-keepalive.sh` (10-min CUST-001→002→003 rotation), smoke-gated `tests/test_narrative_eval_live.py` live eval harness.
- **Freeze + rollback drill (Phase 10):** 6 CFN stack-policy JSON bodies (3 deny-Update:* + 3 allow-all break-glass), hash-pinned `requirements.{in,txt}` + `requirements-dev.{in,txt}`, `FREEZE-MANIFEST.md` with 8 D-10 keys + single DynamoDB backup ARN, `demo-v2.0` annotated tag (WN-2 two-commit self-consistency, `demo-v2.0^ == manifest.freeze_commit_sha`) pushed to origin, rollback drill 5/5 PASS, D-22 closeout 15/15 PASS.

### What Worked

- **Wave-based parallel execution with worktree isolation** (Phases 6-9): orchestrator dispatched plans one Task() per message with `run_in_background: true`, letting git worktrees settle sequentially while agents ran in parallel. Phase 10 Waves 1 and 2 single-plan waves merged cleanly via the post-merge worktree protocol.
- **Inline sequential execution for ceremony-style plans** (Phase 10 Wave 3): running the T-48h freeze ceremony inline on main (not in a worktree) let the two mandatory human checkpoints surface directly to the user without worktree merge-latency, and AWS state changes landed on the correct branch the first time.
- **Rule 4 decision checkpoints** paid off during Phase 10: three architectural deviations (R1 lockfile scope extension, R2 python3.13/AWS_PROFILE codification, D-16 hash-roundtrip softening) were surfaced with structured options rather than silently improvised. Each was user-approved, codified into plan + VALIDATION text, and referenced by commit (`fix(10-03-rule4): …`).
- **Two-commit WN-2 pattern** held across the freeze ceremony: stub commit → self-reference commit → annotated tag. `demo-v2.0^ == freeze_commit_sha == 1a83a87c` three-way invariant verified live.
- **Single-backup BL-2 invariant** throughout Phase 10: one `create-backup` call at Task 4a; the ARN was consumed by both the drill restore (Task 8) AND the manifest `dynamodb_backup.backup_arn` field (Task 12). Same backup, single source of truth.

### What Was Inefficient

- **Lockfile scope mismatch in Phase 10-02 → Rule 4 R1 rework during ceremony.** Phase 10-02 produced `requirements.{txt,-dev.txt}` covering CDK-synth scope only (aws-cdk-lib + constructs + boto3 + pytest); test-runtime imports of `pydantic`/`strands-agents` went unpinned. Phase 10-03's D-19 fresh-clone reproducibility gate hit `ModuleNotFoundError` and required a mid-ceremony lockfile extension. A forward-looking lockfile scoping policy (or `pip-compile` that reads both `requirements.in` AND test imports) would have caught this at 10-02 close.
- **Phase 7-02 undeployed commit discovered at Phase 10 drift gate.** Commit `c033836` (Phase 7-02 live alias) landed in git but was never `cdk deploy`'d; `cdk diff == 0` gate failed, requiring a reconciliation deploy before the ceremony could proceed. A phase-close "deploy gate" for infrastructure phases would prevent recurrence.
- **`vite.config.ts` `__GIT_SHA__` embed vs D-16 hash-roundtrip.** The UI-07 version indicator inadvertently made `dist_bundles.*` hashes commit-dependent, so the strict cross-HEAD reproducibility claim in D-16 couldn't hold. Softened to intra-HEAD determinism (Option A), which is the right architectural answer — but discovering it at Task 6 rather than during 10-02 planning cost a decision-checkpoint cycle.
- **Stale shell `AWS_PROFILE=cevo-25`** surfaced repeatedly (Phase 06.1-02, Phase 10-03 Task 1, VERIFICATION live-state checks). Codified as explicit export at ceremony start per Rule 4 R2, but remains a recurring trap — argues for a project-level direnv file pinning `AWS_PROFILE=cevo-dev25` at repo root.

### Patterns Established

- **Two-commit self-reference pattern for manifest freezes (WN-2).** Commit stub → capture SHA → rewrite manifest with self-ref → second commit → tag points at second commit. Solves the chicken-and-egg "manifest can't embed its own commit SHA" problem without `git commit --amend` (which would dangle the referenced SHA).
- **Single-scratch-file invariant across drill + manifest (BL-2).** Ceremony scratch files (`/tmp/freeze-backup.env`, `/tmp/freeze-hashes.env`, `/tmp/freeze-commits.env`) consumed by BOTH drill steps AND manifest population steps guarantee the drill validates what the manifest names.
- **Rule 4 checkpoint protocol for unplanned architectural issues.** Executor HALTs with structured checkpoint (completed table + current task + options table + "awaiting"). Orchestrator presents to user via AskUserQuestion. Approved path codified into plan/VALIDATION as `fix(<phase>-<plan>-rule4): ...` commit before execution resumes. Beats silent improvisation.
- **Reconciliation deploy as first-class ceremony step.** When the drift gate fails because code is ahead of deployed state, reconcile by deploying the code first (with cost-safe context like `-c demo_pc=0`), then re-gate. Cheaper than reverting the code.
- **Dual commit range per milestone close.** `demo-v{X.Y}` (operational tag — freeze target, cut during ceremony) + `v{X.Y}` (process tag — milestone close, on milestone-close commit). Separating them keeps the operational artifact stable across any post-close admin commits.

### Key Lessons

1. **`pip-compile` freeze lockfiles must cover every import scope** — CDK synth, Lambda runtime, AND test runtime. If the test suite imports a package, it needs a pin. Otherwise the D-19 fresh-clone reproducibility gate is unachievable.
2. **`cdk diff == 0` is a powerful forward indicator of undeployed-code risk.** Run it at phase close for infrastructure phases, not just at freeze time. The earlier an undeployed commit is spotted, the cheaper the reconciliation.
3. **Build-time git SHA embeds undermine content-hash reproducibility.** If you want `hash_dist.sh` to be a cross-commit reproducibility gate, don't embed the git SHA in the bundle. Either accept intra-HEAD determinism (the pragmatic Option A) or move the SHA to a runtime-fetched asset excluded from the hash input.
4. **Human checkpoints before irreversible ops (tag cut, origin push) paid for themselves.** Both Checkpoint A and Checkpoint B caught zero issues this run, but the review cost was seconds and the blast radius if something was wrong was a misnamed tag or a premature push visible to the team.
5. **Three consecutive Rule 4 checkpoints in one plan is a signal to re-plan.** Phase 10-03 hit three architectural deviations in the first half of execution. Each was legitimate and user-approved. But if a pattern of mid-plan rework becomes recurring, the plan's upstream research phase should absorb more discovery work rather than pushing it into execution.

### Cost Observations

- Model mix: executor agents on `sonnet`, verifier on `sonnet`, orchestrator on `opus-4.7`. Inline-sequential Phase 10-03 produced 5 orchestrator-spawned executor sub-runs (initial + 3 Rule 4 resumptions + final checkpoint-B resumption), each a fresh context.
- The Rule 4 checkpoint loop (halt → AskUserQuestion → resume) was more token-efficient than blind retry because each resumption carried a 1-2KB continuation prompt rather than re-reading the full 2041-line plan.

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 5 | 21 | Initial GSD workflow adoption. Phase-per-capability granularity. Inline sequential execution throughout. |
| v2.0 | 5 + 1 decimal | 16 | Wave-based parallel execution via worktrees. Decimal phases (6.1) for mid-milestone regressions. Rule 4 checkpoints for architectural deviations. Inline execution reserved for ceremony-style plans. |

### Cumulative Quality

| Milestone | Post-ceremony pytest | Fresh-clone reproducibility | Verified via live AWS |
|-----------|----------------------|------------------------------|------------------------|
| v1.0 | 81 passed, 6 skipped | Partial (no hash-pin on requirements) | `cdk deploy` + smoke test |
| v2.0 | 189 passed, 34 deselected | Full hash-pinned (`--require-hashes`) | `cdk diff == 0` + `get-stack-policy` + `describe-backup` + `git ls-remote --tags origin` |

### Top Lessons (Verified Across Milestones)

1. **An annotated tag without a fresh-clone reproducibility gate is just a bookmark.** Both v1.0 and v2.0 closed with `git tag -a demo-v{X.Y}` cut on a verified-green working tree; the v2.0 ceremony strengthened this with hash-pinned lockfiles so the gate holds from any fresh clone.
2. **"Don't touch AWS between tag and demo" is a discipline commitment, not a technical control.** Both milestones relied on the operator honoring D-13. Phase 10 added technical reinforcement (deny-Update:* stack policies + termination protection) but the discipline commitment still carries the final mile.
3. **The best way to discover a bad assumption is to try to reproduce the build from zero.** Both milestone closures surfaced real issues during fresh-clone verification that had been invisible in the dev environment.

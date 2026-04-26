# Phase 10: Freeze + Rollback Drill - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `10-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-26
**Phase:** 10-freeze-rollback-drill
**Areas discussed:** Stack lock mechanism, FREEZE-MANIFEST format & hashing, Rollback drill mechanism, Freeze ceremony sequence

---

## Stack Lock Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| CDK-native via add_override | Stack policy travels with CDK code; every deploy reapplies. | ✓ |
| Post-deploy `aws cloudformation set-stack-policy` | Shell step after deploy; JSON file. | |
| Both — CDK sets it, shell verifies | Belt-and-braces with expected-policy diff. | |

**User's choice:** CDK-native via add_override (Recommended)
**Notes:** Feeds D-01.

| Option | Description | Selected |
|--------|-------------|----------|
| All three stacks | Deny + term-protect on Foundation, AgentCore, Backend. | ✓ |
| Per REQUIREMENTS literally | Deny on 3; term-protect only Foundation. | |
| Asymmetric (irrecoverable vs config) | Only Foundation term-protected. | |

**User's choice:** All three stacks (Recommended)
**Notes:** Feeds D-02. ROADMAP SC-2 wording honoured; REQUIREMENTS term-protection line extended.

| Option | Description | Selected |
|--------|-------------|----------|
| Document unlock in FREEZE-MANIFEST.md | Human-gated break-glass prose. | ✓ |
| Ship freeze-unlock.sh + freeze-relock.sh | Automated break-glass scripts. | |
| No break-glass — tag revert only | Purist; forces clean recovery. | |

**User's choice:** Document the unlock steps in FREEZE-MANIFEST.md (Recommended)
**Notes:** Feeds D-04.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual at T-48h via aws CLI | Ceremony, not architecture. | ✓ |
| CDK code (termination_protection=True) | Permanent in stack defs. | |
| CDK for Foundation only; manual for others | Asymmetric. | |

**User's choice:** Manual at T-48h via aws CLI (Recommended)
**Notes:** Feeds D-03.

| Option | Description | Selected |
|--------|-------------|----------|
| All three stacks clean via `cdk diff` | Baseline gate. | ✓ |
| Plus `cdk diff --app cdk.out/` | Synth-vs-deployed belt-and-braces. | |

**User's choice:** All three stacks clean (Recommended)
**Notes:** Feeds D-05.

---

## FREEZE-MANIFEST Format & Hashing

| Option | Description | Selected |
|--------|-------------|----------|
| cdk synth twice + diff, sha256 asset zips | Real reproducibility output proof. | ✓ |
| pip install --require-hashes + wheel hashes | Input proof only. | |
| Both (wheel + synth) | Maximum evidence; +30 manifest lines. | |

**User's choice:** cdk synth twice + diff, sha256 asset zips (Recommended)
**Notes:** Feeds D-08. Wheel hashes still present inside requirements.txt via pip-compile output; not duplicated.

| Option | Description | Selected |
|--------|-------------|----------|
| sha256 of sorted-file tar per dist dir | Stable across Vite ordering. | ✓ |
| sha256 of each file listed individually | Noisy but grep-friendly. | |
| sha256 of zipped archive | `--sort=name` portability issue on BSD tar. | |

**User's choice:** sha256 of sorted-file tar per dist dir (Recommended)
**Notes:** Feeds D-09.

| Option | Description | Selected |
|--------|-------------|----------|
| Sectioned YAML in one fence | Human + machine-readable. | ✓ |
| Flat YAML — one key per artefact | Simple; less signal. | |
| Multiple fenced blocks with headings | Runbook-like; harder to parse. | |

**User's choice:** Sectioned YAML in one fence (Recommended)
**Notes:** Feeds D-07.

| Option | Description | Selected |
|--------|-------------|----------|
| Freeze commit SHA + UTC timestamp | When/what was frozen. | ✓ |
| AgentRuntimeArn + ApiEndpoint + Bedrock model ID | Deployment snapshot. | |
| CloudFormation StackIds + DynamoDB backup ARN + timestamp | Rename-immune + restore targets. | ✓ |
| All three above | Everything. | |

**User's choice:** Freeze commit SHA + UTC timestamp; CloudFormation StackIds + DynamoDB backup ARN + timestamp
**Notes:** Feeds D-10 + D-11. Follow-up needed to satisfy ROADMAP SC-3 Bedrock model ID literal.

| Option | Description | Selected |
|--------|-------------|----------|
| Add model ID only; skip ARN + endpoint | Minimum to satisfy SC-3 literally. | ✓ |
| Add model ID + ARN + endpoint | Full deployment snapshot. | |
| Model ID only; ref STATE.md for ARN/endpoint | Cross-ref risks staleness. | |

**User's choice:** Add model ID only; skip ARN + endpoint (Recommended)
**Notes:** Follow-up that resolves D-11. ARN + endpoint live in STATE.md / 05-DEPLOY-OUTPUTS.md; manifest avoids duplication.

---

## Rollback Drill Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Same account/region scratch table | `tariff-billing-rollback-drill`. | ✓ |
| Restore-in-place | Violates freeze discipline. | |
| Cross-region (us-west-2) | Bedrock availability complexity. | |

**User's choice:** New table in same account/region (Recommended)
**Notes:** Feeds D-12.

| Option | Description | Selected |
|--------|-------------|----------|
| git checkout + pytest green from clean tree | Source-tree-first revert proof. | ✓ |
| Full cdk deploy of demo-v1.0 stacks | AWS-side drill. | |
| git checkout + pytest + AgentCore-direct against live | Muddles two orthogonal checks. | |

**User's choice:** git checkout demo-v1.0 + pytest green (Recommended)
**Notes:** Feeds D-13.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual runbook in 10-DRILL-LOG.md | Operator-driven with evidence capture. | ✓ |
| scripts/rollback-drill.sh | Full automation. | |
| Hybrid: runbook + scripted sub-commands | Middle ground. | |

**User's choice:** Manual runbook in 10-DRILL-LOG.md (Recommended)
**Notes:** Feeds D-14. `## Commands` appendix for copy-paste one-liners retained per the hybrid description.

| Option | Description | Selected |
|--------|-------------|----------|
| Manual browser check + curl assertion | Visual + API sanity. | ✓ |
| Playwright/headless DOM check | New dev dep. | |
| Pure curl HTML diff | Wrong (flag is runtime JS). | |

**User's choice:** Manual browser check + curl assertion (Recommended)
**Notes:** Feeds D-15.

---

## Freeze Ceremony Sequence

| Option | Description | Selected |
|--------|-------------|----------|
| Reproducibility → drift → drill → lock → backup → manifest → tag | Drill-before-tag discipline. | ✓ |
| Tag first, then lock + backup + drill | Tag-as-intent ceremonial. | |
| Drill last, after tag | Operator paranoia. | |

**User's choice:** Reproducibility → drift → drill → lock → backup → manifest → tag (Recommended)
**Notes:** Feeds D-18.

| Option | Description | Selected |
|--------|-------------|----------|
| Freeze owner in fresh git clone + venv | Single-operator drill. | ✓ |
| Peer reviewer on different machine | No origin push — can't pull. | |
| CI job on tag push | No CI infrastructure. | |

**User's choice:** Freeze owner in a fresh git clone + fresh venv (Recommended)
**Notes:** Feeds D-19.

| Option | Description | Selected |
|--------|-------------|----------|
| Update existing DEMO-RUNBOOK.md | Single canonical runbook. | ✓ |
| New 10-DEMO-RUNBOOK.md | Duplicate. | |
| Inline in FREEZE-MANIFEST.md | Conflates posture with process. | |

**User's choice:** Update existing DEMO-RUNBOOK.md (Recommended)
**Notes:** Feeds D-20. Amended file: `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`.

| Option | Description | Selected |
|--------|-------------|----------|
| 3 plans (CDK / ceremony artefacts / execution) | Clean wave 1→2→3 structure. | ✓ |
| 4 plans (split drill setup + execution) | Thin plans. | |
| 2 plans (ceremony lumped / drill standalone) | Chunky first plan. | |

**User's choice:** 3 plans (Recommended)
**Notes:** Feeds D-21. Plan 10-03 is `autonomous: false` — human checkpoint before tag cut.

---

## Final scope-hygiene pass

| Option | Description | Selected |
|--------|-------------|----------|
| Check v1.0 archive for DEMO-RUNBOOK.md and reuse | Grep first; amend in place if found. | ✓ |
| Always create new at .planning/DEMO-RUNBOOK.md | Ignore archive. | |
| Defer — planner decides | Claude's Discretion. | |

**User's choice:** Check v1.0 archive and reuse (Recommended)
**Notes:** Confirmed existing at `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`. Phase 10 amends in place.

| Option | Description | Selected |
|--------|-------------|----------|
| CI-run reproducibility gate | Peer/CI verification. | ✓ |
| scripts/freeze-unlock.sh + freeze-relock.sh | Automated break-glass. | |
| Playwright DOM check for ?narrative=off | Scripted UI check. | |
| All three | Save everything. | |

**User's choice:** CI-run reproducibility gate
**Notes:** Only CI-gate is worth preserving in Deferred. `freeze-unlock.sh` and Playwright both rejected on merits and not worth noting. Deferred section trimmed accordingly.

---

## Claude's Discretion

- Exact CDK `add_override` syntax for CFN stack policies (researcher confirms escape-hatch path).
- FREEZE-MANIFEST.md location phase-scoped vs repo-root.
- Whether `scripts/verify_synth_repro.py` ships as committed artefact or inline in plan summary.
- Exact break-glass wording tone.
- Whether `pip-compile` pins to exact current-resolved versions or freshly resolves.
- Specific months for persona spot-checks in rollback drill DynamoDB verification.
- ISO-8601 timestamp format minutiae in 10-DRILL-LOG.md.
- Single vs multi-commit DEMO-RUNBOOK.md edit.

## Deferred Ideas

Captured in `10-CONTEXT.md` `<deferred>` section. Primary: CI-run reproducibility gate (revisit when origin push exists).

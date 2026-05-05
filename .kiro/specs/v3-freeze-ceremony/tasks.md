# Implementation Plan: v3.0 Freeze Ceremony (Phase 17)

## Overview

This plan implements the v3.0 freeze ceremony — a scripted, operator-driven sequence that locks the demo surface behind an annotated `demo-v3.0` git tag. The agent creates file templates and verification scripts; the operator executes all AWS CLI and CDK commands against live infrastructure. Tasks are strictly sequential — each depends on the previous step's success.

**Convention:** Tasks marked "OPERATOR-EXECUTED" require the human operator to run commands and report results back. The agent creates files, populates templates, and writes verification logic.

## Tasks

- [x] 1. LIFT — Apply allow-all stack policies and disable termination protection
  - [x] 1.1 Operator lifts stack policies on all 3 stacks
    - Run `aws cloudformation set-stack-policy` with the allow-all JSON for each stack: `foundation-allow-all.json` (CustomerTariff), `agentcore-allow-all.json` (CustomerTariffAgent), `backend-api-allow-all.json` (CustomerTariffApi)
    - All commands use `--region us-east-1 --profile cevo-dev25`
    - OPERATOR-EXECUTED: the agent cannot run AWS CLI commands against live infrastructure
    - _Requirements: 1.1_

  - [x] 1.2 Operator disables termination protection on all 3 stacks
    - Run `aws cloudformation update-termination-protection --no-enable-termination-protection` for each of CustomerTariff, CustomerTariffAgent, CustomerTariffApi
    - OPERATOR-EXECUTED
    - _Requirements: 1.2_

  - [x] 1.3 Operator verifies lift succeeded
    - Run `aws cloudformation describe-stacks` and confirm `EnableTerminationProtection: false` on all 3 stacks
    - Run `aws cloudformation get-stack-policy` for each stack and confirm the allow-all policy body is returned
    - OPERATOR-EXECUTED
    - _Requirements: 1.3_

- [x] 2. DEPLOY — Reconcile v3.0 code to deployed state
  - [x] 2.1 Operator deploys all 3 stacks
    - Run `cdk deploy CustomerTariff CustomerTariffAgent CustomerTariffApi --require-approval never`
    - Confirm all 3 stacks reach `UPDATE_COMPLETE` or `CREATE_COMPLETE`
    - OPERATOR-EXECUTED
    - _Requirements: 2.1_

  - [x] 2.2 Operator verifies zero drift via cdk diff
    - Run `cdk diff CustomerTariff CustomerTariffAgent CustomerTariffApi`
    - Output must show zero differences across all 3 stacks
    - If any diff exists, resolve and re-deploy before proceeding
    - OPERATOR-EXECUTED
    - _Requirements: 2.2, 2.3_

- [x] 3. Checkpoint — Confirm LIFT + DEPLOY succeeded
  - Ensure all stacks are deployed with zero drift. Ask the user if questions arise.

- [x] 4. REAPPLY — Freeze policies + termination protection + byte-equality gate
  - [x] 4.1 Operator re-applies deny-Update:* freeze policies on all 3 stacks
    - Run `aws cloudformation set-stack-policy` with the freeze JSON for each stack: `foundation-freeze.json` (CustomerTariff), `agentcore-freeze.json` (CustomerTariffAgent), `backend-api-freeze.json` (CustomerTariffApi)
    - All commands use `--region us-east-1 --profile cevo-dev25`
    - OPERATOR-EXECUTED
    - _Requirements: 3.1_

  - [x] 4.2 Operator re-enables termination protection on all 3 stacks
    - Run `aws cloudformation update-termination-protection --enable-termination-protection` for each of CustomerTariff, CustomerTariffAgent, CustomerTariffApi
    - OPERATOR-EXECUTED
    - _Requirements: 3.2_

  - [x] 4.3 Operator verifies byte-equality of freeze policies
    - Run `aws cloudformation get-stack-policy` for each stack and compare output to the committed freeze JSON files under `infrastructure/stack-policies/`
    - The output must be byte-equivalent to the committed JSON
    - OPERATOR-EXECUTED
    - _Requirements: 3.3_

  - [x] 4.4 Write pytest byte-equality gate for stack policies
    - Create or update a pytest test that asserts `get-stack-policy` output matches the committed freeze JSON for all 3 stacks
    - Test should be runnable with `pytest -m smoke` and require AWS credentials
    - The test must fail if any stack policy body differs from the committed freeze JSON
    - _Requirements: 3.3, 3.4_

- [x] 5. BACKUP — DynamoDB on-demand freeze backup
  - [x] 5.1 Operator creates DynamoDB backup
    - Run `aws dynamodb create-backup --table-name tariff-billing --backup-name "tariff-billing-v3.0-freeze-$(date -u +%Y%m%dT%H%M%SZ)" --region us-east-1 --profile cevo-dev25`
    - Record the returned backup ARN
    - OPERATOR-EXECUTED
    - _Requirements: 4.1_

  - [x] 5.2 Operator verifies backup is AVAILABLE
    - Run `aws dynamodb describe-backup --backup-arn <arn>` and confirm `BackupStatus: AVAILABLE`
    - Confirm the backup ARN differs from the v2.0 backup ARN (`01777208516554-e1bee933`) — single-backup-per-milestone invariant
    - OPERATOR-EXECUTED
    - _Requirements: 4.1, 4.3_

- [x] 6. Checkpoint — Confirm REAPPLY + BACKUP succeeded
  - Ensure freeze policies are byte-equal, termination protection is on, and DynamoDB backup is AVAILABLE. Ask the user if questions arise.

- [x] 7. MANIFEST — Create and populate FREEZE-MANIFEST.md
  - [x] 7.1 Create the v3.0 FREEZE-MANIFEST.md template with `<pending>` placeholders
    - Create `.planning/milestones/v3.0-phases/17-freeze-ceremony/FREEZE-MANIFEST.md` based on the v2.0 template structure at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md`
    - Include all v2.0 keys plus v3.0 additions: `memory_id`, `agent_runtime_arn`, `api_endpoint`
    - Pre-fill known constants: `bedrock_model_id: us.anthropic.claude-sonnet-4-6`, `agent_runtime_arn`, `api_endpoint`, `tag: demo-v3.0`, `dynamodb_backup.table_name: tariff-billing`
    - Use `<pending>` for values that require operator computation: `freeze_commit_sha`, lockfile hashes, dist bundle hashes, synth asset hashes, CloudFormation stack ARNs, backup ARN, `memory_id`
    - Include the `break_glass:` section with unlock/disable/after-fix commands referencing the allow-all policy JSON files
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9_

  - [x] 7.2 Operator computes and populates manifest hash values
    - Run `sha256sum requirements.txt`, `sha256sum requirements-dev.txt`, `sha256sum ui/package-lock.json` for lockfile hashes
    - Run `scripts/hash_dist.sh ui/dist` and `scripts/hash_dist.sh ui/dist-mock` for dist bundle hashes
    - Run `cdk synth` then `scripts/hash_synth_assets.sh` for each `cdk.out/asset.*/` directory for synth asset hashes
    - Retrieve CloudFormation stack ARNs via `aws cloudformation describe-stacks`
    - Retrieve `memory_id` from SSM parameter `/customer-tariff/memory-id`
    - Replace all `<pending>` placeholders with computed values
    - OPERATOR-EXECUTED
    - _Requirements: 5.2, 5.4, 5.5, 5.6, 5.7, 5.8_

  - [x] 7.3 Operator commits the populated manifest
    - `git add .planning/milestones/v3.0-phases/17-freeze-ceremony/FREEZE-MANIFEST.md`
    - `git commit -m "chore(17): v3.0 FREEZE-MANIFEST"`
    - Record the commit SHA — this becomes `freeze_commit_sha` in the manifest
    - Update the manifest's `freeze_commit_sha` field with this SHA, amend the commit
    - OPERATOR-EXECUTED
    - _Requirements: 5.1, 5.10_

- [x] 8. LOCKFILE GATE — Fresh venv reproducibility verification
  - [x] 8.1 Operator runs lockfile reproducibility gate
    - Create fresh venv: `/opt/homebrew/bin/python3.13 -m venv /tmp/freeze-gate-venv`
    - Install: `/tmp/freeze-gate-venv/bin/pip install --require-hashes -r requirements.txt`
    - Install dev: `/tmp/freeze-gate-venv/bin/pip install --require-hashes -r requirements-dev.txt`
    - Install UI: `npm ci --prefix ui`
    - Run tests: `/tmp/freeze-gate-venv/bin/pytest -m "not smoke"`
    - All commands must exit 0; record the pytest pass count for the manifest
    - Confirm `requirements.txt` contains `bedrock-agentcore==1.6.4` with a valid hash
    - OPERATOR-EXECUTED
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [x] 9. DRILL — 5-step rollback drill
  - [x] 9.1 Create the drill log skeleton file
    - Create `.planning/milestones/v3.0-phases/17-freeze-ceremony/17-DRILL-LOG.md` with the 5-step table structure from the design document
    - Include columns: Step, What was drilled, Evidence, Verdict
    - Pre-fill the "What was drilled" column with the 5 drill steps
    - Leave Evidence and Verdict columns as `<pending>`
    - _Requirements: 6.6_

  - [x] 9.2 Operator executes drill step 1: `?narrative=off` kill switch
    - Open `http://localhost:4173/?narrative=off` at 1280×800 viewport
    - Verify reasoning trace, hardship banner, and follow-up email drawer all collapse to v2.0 shape
    - Record evidence and PASS/FAIL verdict in the drill log
    - OPERATOR-EXECUTED
    - _Requirements: 6.1_

  - [x] 9.3 Operator executes drill step 2: `npm run build:mock` emergency swap
    - Run `rm -rf ui/dist-mock && npm run build:mock --prefix ui`
    - Verify build completes in <10s wall-clock
    - Run `scripts/hash_dist.sh ui/dist-mock` and compare to manifest value
    - Record evidence and PASS/FAIL verdict in the drill log
    - OPERATOR-EXECUTED
    - _Requirements: 6.2_

  - [x] 9.4 Operator executes drill step 3: `git checkout demo-v2.0` rollback
    - Fresh clone → `git checkout demo-v2.0` → `pytest -m "not smoke"`
    - Verify exit code 0 (expect ~87 passed / ~23 deselected — v2.0 test surface)
    - Record evidence and PASS/FAIL verdict in the drill log
    - OPERATOR-EXECUTED
    - _Requirements: 6.3_

  - [x] 9.5 Operator executes drill step 4: DynamoDB restore + spot-check
    - Run `aws dynamodb restore-table-from-backup --target-table-name tariff-billing-rollback-drill --backup-arn <arn>`
    - Verify scan count matches expected (60 billing + 5 PROFILE + CUST-006 records)
    - Spot-check 5 recommendation personas at month `2025-04` for non-null `usage_kwh`
    - Record evidence and PASS/FAIL verdict in the drill log
    - OPERATOR-EXECUTED
    - _Requirements: 6.4_

  - [x] 9.6 Operator executes drill step 5: scratch table teardown
    - Run `aws dynamodb delete-table --table-name tariff-billing-rollback-drill`
    - Run `aws dynamodb describe-table --table-name tariff-billing-rollback-drill` and confirm `ResourceNotFoundException`
    - Record evidence and PASS/FAIL verdict in the drill log
    - OPERATOR-EXECUTED
    - _Requirements: 6.5_

  - [x] 9.7 Populate drill log with ceremony evidence
    - Update the drill log file with all 5 step verdicts, timestamps, and evidence from the operator
    - Overall verdict must be PASS (all 5 steps PASS) before proceeding to tag
    - _Requirements: 6.6_

- [x] 10. Checkpoint — Confirm LOCKFILE GATE + DRILL passed
  - Ensure lockfile gate exited 0, all 5 drill steps are PASS, and drill log is populated. Ask the user if questions arise.

- [x] 11. TAG — Cut annotated `demo-v3.0` and push
  - [x] 11.1 Operator commits drill log and cuts annotated tag
    - `git add .planning/milestones/v3.0-phases/17-freeze-ceremony/`
    - `git commit -m "chore(17): v3.0 freeze drill log — 5/5 PASS"`
    - `git tag -a demo-v3.0 -m "v3.0 freeze — <ISO-8601-UTC> freeze_commit_sha: <sha> manifest: .planning/milestones/v3.0-phases/17-freeze-ceremony/FREEZE-MANIFEST.md"`
    - OPERATOR-EXECUTED
    - _Requirements: 7.1, 7.4_

  - [x] 11.2 Operator verifies WN-2 self-consistency
    - Run `git rev-list -n 1 demo-v3.0^` and confirm it equals the `freeze_commit_sha` in the manifest
    - The tag must point one commit past the manifest commit (two-commit pattern)
    - OPERATOR-EXECUTED
    - _Requirements: 7.2_

  - [x] 11.3 Operator pushes tag and main to origin
    - `git push origin main`
    - `git push origin demo-v3.0`
    - Verify `git ls-remote --tags origin` shows both the tag object ref and dereferenced commit ref for `demo-v3.0`
    - OPERATOR-EXECUTED
    - _Requirements: 7.3_

- [x] 12. RUNBOOK — Update DEMO-RUNBOOK.md §7 with v3.0 ceremony evidence
  - [x] 12.1 Update DEMO-RUNBOOK.md §7 with v3.0 freeze record
    - Replace the v2.0 ceremony record in §7 with v3.0 evidence
    - Include: `demo-v3.0` tag SHA, v3.0 FREEZE-MANIFEST path (`.planning/milestones/v3.0-phases/17-freeze-ceremony/FREEZE-MANIFEST.md`), v3.0 drill log path (`17-DRILL-LOG.md`), DynamoDB backup ARN, ceremony timestamps
    - Include the 5-step drill summary table with PASS verdicts matching the format used for v2.0
    - Preserve the break-glass section with updated commands
    - Update the T-48h verification checklist to reference `demo-v3.0` tag SHA
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 12.2 Update DEMO-RUNBOOK.md §2 pre-demo setup to reference demo-v3.0
    - Update the `git checkout` command from `demo-v2.0` to `demo-v3.0`
    - Ensure the 4-stack verification block references the correct freeze state
    - _Requirements: 10.1_

- [x] 13. PREWARM LATENCY GATE — T-24h visual rehearsal
  - [x] 13.1 Operator runs prewarm latency gate
    - Run `BACKEND_API_URL=https://y9w9qwegwe.execute-api.us-east-1.amazonaws.com/ python3 scripts/prewarm.py`
    - Single-tool personas (CUST-001, CUST-002, CUST-004, CUST-005): warm median must be < 3000ms
    - Multi-tool persona (CUST-003 Elena): warm median must be < 2500ms
    - Exit code 0 = all gates pass; record exit code as evidence
    - If any gate fails, record measured latency and make go/no-go decision based on overshoot magnitude
    - OPERATOR-EXECUTED
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [x] 14. Final checkpoint — Ceremony complete
  - Ensure all tasks are complete: stacks frozen with byte-equal policies, DynamoDB backup AVAILABLE, FREEZE-MANIFEST populated and committed, drill 5/5 PASS, `demo-v3.0` tag pushed with WN-2 self-consistency, DEMO-RUNBOOK §7 updated, prewarm latency gate passed. Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster execution
- Tasks marked "OPERATOR-EXECUTED" require the human to run commands against live AWS infrastructure — the agent cannot execute these
- Each task references specific requirements for traceability (Requirement N.M from requirements.md)
- Checkpoints ensure incremental validation between ceremony phases
- The ceremony is strictly sequential — do not skip ahead or parallelize steps
- The v2.0 FREEZE-MANIFEST at `.planning/milestones/v2.0-phases/10-freeze-rollback-drill/FREEZE-MANIFEST.md` is the structural template for the v3.0 manifest
- The v3.0 manifest adds `memory_id`, `agent_runtime_arn`, and `api_endpoint` keys not present in v2.0

# Requirements Document

## Introduction

Phase 17 of the Customer Tariff & Billing Optimisation Agent project: the v3.0 Freeze Ceremony. This phase locks the entire v3.0 demo surface behind an annotated `demo-v3.0` git tag with deny-Update:* CloudFormation stack policies, a fresh DynamoDB backup, a self-consistent FREEZE-MANIFEST, and a proven 5/5 rollback drill — mirroring the v2.0 Phase 10 ceremony exactly but adapted for the v3.0 surface (6 personas, multi-tool reasoning, hardship short-circuit, follow-up email, AgentCore Memory).

The ceremony follows the scripted lift → deploy → verify → re-apply sequence established in v2.0 (LD-6). The 3 stacks currently carry deny-Update:* policies from the v2.0 freeze; they must be lifted, v3.0 code deployed to reconcile code-to-deployed state, verified via `cdk diff == 0`, then re-frozen with byte-equivalent policies and termination protection.

**Requirement source:** DEMO-08 from REQUIREMENTS.md. **Locked decision:** LD-6 (freeze ceremony is a dedicated phase).

## Glossary

- **Ceremony**: The scripted sequence of lift → deploy → verify → re-apply → backup → manifest → drill → tag → push that produces a frozen, proven demo environment.
- **Stack_Policy**: A CloudFormation stack policy JSON document applied via `aws cloudformation set-stack-policy` that controls which update actions are permitted on stack resources. The freeze policy denies all updates (`Deny Update:*`); the allow-all policy permits all updates.
- **Termination_Protection**: A CloudFormation stack-level flag that prevents accidental stack deletion. Applied via `aws cloudformation update-termination-protection`.
- **FREEZE_MANIFEST**: A Markdown file containing YAML-in-fence with all freeze evidence: commit SHAs, lockfile hashes, dist bundle hashes, synth asset hashes, CloudFormation stack IDs, DynamoDB backup ARN, Bedrock model ID, AgentCore Memory ID, agent runtime ARN, API endpoint, and break-glass commands.
- **Rollback_Drill**: A 5-step manual verification that all rollback levers work: `?narrative=off` kill switch, `build:mock` emergency UI swap, `git checkout demo-v2.0` tag revert, DynamoDB restore-from-backup, and scratch table teardown.
- **WN_2_Self_Consistency**: The invariant that `git rev-list -n 1 demo-v3.0^` equals the `freeze_commit_sha` recorded in FREEZE-MANIFEST — the tag points one commit past the manifest commit.
- **Byte_Equality_Gate**: A verification step that asserts the stack policy JSON returned by `aws cloudformation get-stack-policy` is byte-equivalent to the committed freeze policy JSON files under `infrastructure/stack-policies/`.
- **Content_Manifest_Hash**: A deterministic sha256 computed by sorting file paths, hashing each file individually, then hashing the concatenated per-file hashes — avoids tar mtime leakage.
- **Break_Glass**: The documented human-gated procedure to unlock frozen stacks for an emergency fix, then re-lock and cut a patch tag.
- **Freeze_Ceremony_Operator**: The human who executes the ceremony steps, verifies outputs, and makes go/no-go decisions at checkpoints.
- **Three_Stacks**: The three CloudFormation stacks subject to freeze: CustomerTariff, CustomerTariffAgent, CustomerTariffApi.

## Requirements

### Requirement 1: Lift Existing v2.0 Stack Policies

**User Story:** As a Freeze_Ceremony_Operator, I want to lift the existing deny-Update:* stack policies and disable termination protection on all Three_Stacks, so that v3.0 code can be deployed to reconcile the code-to-deployed state.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator runs the allow-all stack policy commands, THE Three_Stacks SHALL each accept the `foundation-allow-all.json`, `agentcore-allow-all.json`, and `backend-api-allow-all.json` policy bodies via `aws cloudformation set-stack-policy`.
2. WHEN the Freeze_Ceremony_Operator disables termination protection, THE Three_Stacks SHALL each report `EnableTerminationProtection: false` via `aws cloudformation describe-stacks`.
3. WHEN the lift is complete, THE Freeze_Ceremony_Operator SHALL verify that `aws cloudformation get-stack-policy` for each stack returns the allow-all policy body before proceeding to deployment.

### Requirement 2: Deploy v3.0 Surface to Reconcile Code and Deployed State

**User Story:** As a Freeze_Ceremony_Operator, I want to deploy all Three_Stacks so that the deployed CloudFormation state matches the v3.0 codebase at HEAD, so that `cdk diff` returns zero drift.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator runs `cdk deploy CustomerTariff CustomerTariffAgent CustomerTariffApi`, THE Three_Stacks SHALL each reach `UPDATE_COMPLETE` or `CREATE_COMPLETE` status.
2. WHEN deployment completes, THE Freeze_Ceremony_Operator SHALL run `cdk diff CustomerTariff CustomerTariffAgent CustomerTariffApi` and THE CDK_CLI SHALL report zero differences across all Three_Stacks.
3. IF `cdk diff` reports any difference after deployment, THEN THE Freeze_Ceremony_Operator SHALL resolve the drift before proceeding to the re-apply step.

### Requirement 3: Re-Apply Deny-Update Stack Policies with Byte-Equality Verification

**User Story:** As a Freeze_Ceremony_Operator, I want to re-apply deny-Update:* stack policies and re-enable termination protection on all Three_Stacks with byte-equality verification, so that the v3.0 surface is locked against accidental drift.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator runs the freeze stack policy commands, THE Three_Stacks SHALL each accept the `foundation-freeze.json`, `agentcore-freeze.json`, and `backend-api-freeze.json` policy bodies via `aws cloudformation set-stack-policy`.
2. WHEN the Freeze_Ceremony_Operator re-enables termination protection, THE Three_Stacks SHALL each report `EnableTerminationProtection: true` via `aws cloudformation describe-stacks`.
3. THE Byte_Equality_Gate SHALL assert that `aws cloudformation get-stack-policy` output for each of the Three_Stacks is byte-equivalent to the corresponding committed freeze JSON file under `infrastructure/stack-policies/`.
4. THE Byte_Equality_Gate SHALL execute as a pytest assertion before the tag is cut, and THE pytest test SHALL fail if any stack policy body differs from the committed freeze JSON.

### Requirement 4: Create DynamoDB Freeze Backup

**User Story:** As a Freeze_Ceremony_Operator, I want to create a fresh on-demand DynamoDB backup of the `tariff-billing` table, so that the v3.0 data layer can be restored if needed.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator creates the backup, THE DynamoDB_Service SHALL return a backup ARN and the backup status SHALL reach `AVAILABLE` within 10 minutes.
2. THE backup SHALL contain the full v3.0 dataset: 60 billing items (5 recommendation personas times 12 months) plus 5 PROFILE items plus any additional rows (CUST-006 billing records), verified via a scan count on the restored scratch table during the Rollback_Drill.
3. THE single-backup-per-milestone invariant SHALL hold: the v3.0 backup ARN SHALL differ from the v2.0 backup ARN (`arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933`).

### Requirement 5: Populate FREEZE-MANIFEST with All Required Keys

**User Story:** As a Freeze_Ceremony_Operator, I want to populate a FREEZE-MANIFEST.md under `.planning/milestones/v3.0-phases/` with all freeze evidence keys, so that the byte-level identity of the v3.0 demo is captured and machine-verifiable.

#### Acceptance Criteria

1. THE FREEZE_MANIFEST SHALL contain a `git:` section with `freeze_commit_sha`, `freeze_timestamp_utc`, and `tag: demo-v3.0`.
2. THE FREEZE_MANIFEST SHALL contain a `lockfiles:` section with sha256 hashes of `requirements.txt` (62 or more prod entries including `bedrock-agentcore==1.6.4`), `requirements-dev.txt` (33 or more dev entries), and `ui/package-lock.json`.
3. THE FREEZE_MANIFEST SHALL contain a `bedrock_model_id:` key with value `us.anthropic.claude-sonnet-4-6`.
4. THE FREEZE_MANIFEST SHALL contain an `agent_runtime_arn:` key with the AgentCore runtime ARN and an `api_endpoint:` key with the API Gateway URL.
5. THE FREEZE_MANIFEST SHALL contain a `memory_id:` key referencing the AgentCore Memory resource provisioned in Phase 15.
6. THE FREEZE_MANIFEST SHALL contain a `dynamodb_backup:` section with `table_name`, `backup_arn`, and `backup_timestamp_utc`.
7. THE FREEZE_MANIFEST SHALL contain a `cloudformation:` section with the full StackId ARN for each of the Three_Stacks.
8. THE FREEZE_MANIFEST SHALL contain `dist_bundles:` and `synth_assets:` sections with Content_Manifest_Hash values computed by `scripts/hash_dist.sh` and `scripts/hash_synth_assets.sh`.
9. THE FREEZE_MANIFEST SHALL contain a `break_glass:` section with unlock stack policy commands, disable termination protection commands, and after-fix re-ceremony instructions referencing the allow-all policy JSON files.
10. THE FREEZE_MANIFEST SHALL be committed to `main` as an atomic commit before the tag is cut, and THE `freeze_commit_sha` SHALL equal the SHA of that commit.

### Requirement 6: Execute 5-Step Rollback Drill

**User Story:** As a Freeze_Ceremony_Operator, I want to execute a 5-step rollback drill that proves all recovery levers work, so that the demo environment has a verified escape path before the tag is cut.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator tests the `?narrative=off` kill switch, THE UI SHALL collapse all v3.0 surfaces (reasoning trace, hardship banner, follow-up email drawer) to v2.0 shape, verified via browser inspection at 1280x800 viewport.
2. WHEN the Freeze_Ceremony_Operator runs `npm run build:mock`, THE build SHALL complete in under 10 seconds wall-clock and THE regenerated `ui/dist-mock/` Content_Manifest_Hash SHALL match the value recorded in the FREEZE_MANIFEST.
3. WHEN the Freeze_Ceremony_Operator checks out `demo-v2.0` in a fresh clone and runs `pytest -m "not smoke"`, THE test suite SHALL exit with status 0.
4. WHEN the Freeze_Ceremony_Operator restores the DynamoDB backup into a scratch table `tariff-billing-rollback-drill`, THE scan count SHALL confirm the expected row count (60 billing items plus 5 PROFILE items plus CUST-006 billing records) and spot-check queries for each of the 5 recommendation personas at month `2025-04` SHALL return non-null `usage_kwh` values.
5. WHEN the Freeze_Ceremony_Operator deletes the scratch table, THE `aws dynamodb describe-table` command SHALL return `ResourceNotFoundException`, confirming clean teardown.
6. THE Rollback_Drill SHALL produce a drill log file with ISO-8601 UTC timestamps, command outputs, and per-step PASS/FAIL verdicts, and THE overall drill verdict SHALL be PASS before the tag is cut.

### Requirement 7: Cut and Push Annotated demo-v3.0 Tag with WN-2 Self-Consistency

**User Story:** As a Freeze_Ceremony_Operator, I want to cut an annotated `demo-v3.0` git tag on `main` with WN-2 self-consistency and push it to origin, so that the frozen v3.0 surface is identifiable and retrievable by any team member.

#### Acceptance Criteria

1. THE `demo-v3.0` annotated tag SHALL exist on `main` and SHALL point at the commit immediately after the FREEZE_MANIFEST commit.
2. THE WN_2_Self_Consistency invariant SHALL hold: `git rev-list -n 1 demo-v3.0^` SHALL equal the `freeze_commit_sha` recorded in the FREEZE_MANIFEST.
3. WHEN the tag is pushed to origin, THE `git ls-remote --tags origin` output SHALL show both the tag object ref and the dereferenced commit ref for `demo-v3.0`.
4. THE tag annotation message SHALL include the freeze commit SHA, the ceremony date in ISO-8601 UTC, and a reference to the FREEZE_MANIFEST file path.

### Requirement 8: T-24h Visual Rehearsal Latency Gate

**User Story:** As a Freeze_Ceremony_Operator, I want to verify that warm median latency per persona stays under the per-flow gate during the T-24h visual rehearsal, so that the demo meets the UI-02 lookup-to-rendered contract.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator runs `scripts/prewarm.py` against the live endpoint, THE warm median for single-tool personas (CUST-001, CUST-002, CUST-004, CUST-005) SHALL be measured against the 3000ms per-flow gate.
2. WHEN the Freeze_Ceremony_Operator runs `scripts/prewarm.py` against the live endpoint, THE warm median for the multi-tool persona (CUST-003 Elena) SHALL be measured against the 2500ms per-flow gate.
3. THE prewarm script SHALL exit with code 0 when all per-flow gates pass, and THE exit code SHALL be recorded in the drill log as evidence.
4. IF any per-flow gate fails, THEN THE Freeze_Ceremony_Operator SHALL record the measured latency as a finding and make a go/no-go decision based on the magnitude of the overshoot, consistent with the Phase 13.1 latency findings.

### Requirement 9: Frozen-Lockfile Reproducibility Gate

**User Story:** As a Freeze_Ceremony_Operator, I want to verify that the hash-pinned lockfiles reproduce a working environment from a fresh clone, so that the freeze reproducibility contract holds.

#### Acceptance Criteria

1. WHEN the Freeze_Ceremony_Operator runs `pip install --require-hashes -r requirements.txt` in a fresh venv using Python 3.13, THE installation SHALL complete with exit code 0.
2. WHEN the Freeze_Ceremony_Operator runs `pip install --require-hashes -r requirements-dev.txt` in a fresh venv using Python 3.13, THE installation SHALL complete with exit code 0.
3. WHEN the Freeze_Ceremony_Operator runs `npm ci --prefix ui`, THE installation SHALL complete with exit code 0 against the committed `ui/package-lock.json`.
4. WHEN the Freeze_Ceremony_Operator runs `pytest -m "not smoke"` from the fresh venv, THE test suite SHALL exit with status 0 and THE pass count SHALL be recorded in the FREEZE_MANIFEST as evidence.
5. THE `requirements.txt` lockfile SHALL contain `bedrock-agentcore==1.6.4` with a valid hash, confirming the Phase 15 dependency bump is captured in the freeze.

### Requirement 10: DEMO-RUNBOOK v3.0 Freeze Section Update

**User Story:** As a Freeze_Ceremony_Operator, I want the DEMO-RUNBOOK.md section 7 to be updated with v3.0 ceremony evidence, so that future presenters have a complete record of the freeze state.

#### Acceptance Criteria

1. WHEN Phase 17 completes, THE DEMO-RUNBOOK.md section 7 SHALL reference the `demo-v3.0` tag, the v3.0 FREEZE-MANIFEST path, and the v3.0 drill log path.
2. THE DEMO-RUNBOOK.md T-48h verification checklist SHALL reference the `demo-v3.0` tag SHA and the v3.0 DynamoDB backup ARN.
3. THE DEMO-RUNBOOK.md SHALL document the v3.0 rollback drill results (5/5 PASS) with a summary table matching the format used for the v2.0 drill in the existing section 7.

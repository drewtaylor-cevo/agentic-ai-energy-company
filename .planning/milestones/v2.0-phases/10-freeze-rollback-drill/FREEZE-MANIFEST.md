---
phase: 10-freeze-rollback-drill
artifact: freeze-manifest
status: populated
created: 2026-04-26
---

# FREEZE-MANIFEST — Customer Tariff Demo v2.0

This manifest captures the byte-level identity of the v2.0 demo at T-48h. Every
hash here proves the corresponding artefact was frozen at the freeze commit and
has not drifted since. Operator populates the `<pending>` fields in plan 10-03;
the structure, break-glass block, and pre-filled literals (`bedrock_model_id`,
`dynamodb_backup.table_name`, `git.tag`) are locked here in 10-02.

**What this proves:** source → build → deploy reproducibility holds at freeze
time; same source + same lockfiles + same model + same CFN stacks → same demo.

**What invalidates this:** any non-zero `cdk diff`, any hash mismatch on
rebuild, any CloudFormation stack-policy or termination-protection drift, or
any silent Bedrock model swap between freeze and demo.

**Break-glass:** see `break_glass:` section below. All commands use
`--region us-east-1 --profile cevo-dev25`. After unlocking, applying a fix, and
relocking, re-run DEMO-RUNBOOK.md section 7 steps 2-7 and cut `demo-v2.0.1`.

```yaml
git:
  freeze_commit_sha: "1a83a87c2e134bb264f38f809e33611486821be0"  # Task-13 two-commit pattern per WN-2: this commit is tag^ (one parent of demo-v2.0)
  freeze_timestamp_utc: "2026-04-26T13:45:31Z"
  tag: demo-v2.0

lockfiles:
  requirements_txt: "sha256:6a8e507f4ad2fafd6ecf2377f3e6ec77fe50f222c9596becd041e4db0fa3193b"
  requirements_dev_txt: "sha256:893ff8f5500171ba82d8f262725c547f6cd437b16117ff664a78f45412cec8e7"
  ui_package_lock_json: "sha256:12a7b9efb73ea27c4b5f89b816c4702d60c36684d0ae8762c1347531d8e10a41"

# NOTE (Rule 4 D-16 softening — 2026-04-26):
# dist_bundles.* hashes are commit-bound snapshots captured at the freeze HEAD.
# They are NOT a fresh-clone reproducibility gate — vite.config.ts embeds the
# git short SHA into the bundle, so every commit produces a different hash.
# Cross-HEAD reproducibility is guarded by: (a) lockfile hashes (Python + npm
# require-hashes install), (b) synth_asset hashes (Lambda bundles), and
# (c) cdk diff == 0.
dist_bundles:
  ui_dist: "sha256:e8481accb8d127a5732cd05fbc802646525d146c2785fc8d23eedf06c9c12853"
  ui_dist_mock: "sha256:e8481accb8d127a5732cd05fbc802646525d146c2785fc8d23eedf06c9c12853"

# Populated by 10-03 — one entry per cdk.out/asset.*/ directory.
# logical = asset logical ID from cdk.out/manifest.json (rename-immune).
# asset_hash = the CDK-generated content hash (matches cdk.out/asset.<hash>/ dir name).
# bundle_sha256 = scripts/hash_synth_assets.sh output for that asset dir (strips .pyc / __pycache__).
synth_assets:
  - logical: "CustomerTariff/ToolsLambda/TariffTools/Code"
    asset_hash: "66095db4be2e278815a9e1f0c0684b11a3052c994e6ab1d12770560e67d43cc6"
    bundle_sha256: "sha256:69750af13b62672cae654b7fc77f2a5c165c0df2a21b7ccf329c235b63f6c5c3"
  - logical: "CustomerTariff/AWS679f53fac002430cb0da5b7982bd2287/Code"
    asset_hash: "56f7467bbde8a5efebcf57ae9e460027607099bab9f844669dcf5d800172ee5a"
    bundle_sha256: "sha256:62a98a12fb3edd2bfd8d69e645f241faa69c57b50a6ad60549f1004866dd295d"
  - logical: "CustomerTariffApi/BackendApi/TariffApiLambda/Code"
    asset_hash: "5d70f6e79f47f69370918338819f573fa72eae7689f10008b711170fd3c7b02f"
    bundle_sha256: "sha256:4bc87ea7c15905e9e0dcee35f1abeba8aaf5ec60a495970dc2c68151e71a0078"

cloudformation:
  # Full StackId ARN format: arn:aws:cloudformation:us-east-1:588738606436:stack/<name>/<guid>
  FoundationStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariff/642a1730-3f11-11f1-b95c-0e3dd0f0bb6b"
  AgentCoreStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffAgent/9b4763d0-3f1b-11f1-9085-0affd0ba2291"
  BackendApiStack: "arn:aws:cloudformation:us-east-1:588738606436:stack/CustomerTariffApi/8505daf0-3f90-11f1-b399-1252c9745d9f"

bedrock_model_id: "us.anthropic.claude-sonnet-4-6"

dynamodb_backup:
  table_name: tariff-billing
  backup_arn: "arn:aws:dynamodb:us-east-1:588738606436:table/tariff-billing/backup/01777208516554-e1bee933"
  backup_timestamp_utc: "2026-04-26T13:01:56Z"

break_glass:
  unlock_stack_policies: |
    # Apply allow-all policy to each stack (replaces the deny-Update:* freeze policy).
    # Each stack has its own policy file under infrastructure/stack-policies/.
    aws cloudformation set-stack-policy --stack-name CustomerTariff \
        --stack-policy-body file://infrastructure/stack-policies/foundation-allow-all.json \
        --region us-east-1 --profile cevo-dev25
    aws cloudformation set-stack-policy --stack-name CustomerTariffAgent \
        --stack-policy-body file://infrastructure/stack-policies/agentcore-allow-all.json \
        --region us-east-1 --profile cevo-dev25
    aws cloudformation set-stack-policy --stack-name CustomerTariffApi \
        --stack-policy-body file://infrastructure/stack-policies/backend-api-allow-all.json \
        --region us-east-1 --profile cevo-dev25

  disable_termination_protection: |
    for stack in CustomerTariff CustomerTariffAgent CustomerTariffApi; do
      aws cloudformation update-termination-protection --no-enable-termination-protection \
          --stack-name "$stack" --region us-east-1 --profile cevo-dev25
    done

  after_fix: |
    # After applying the emergency fix:
    #   1. Reapply deny-Update:* policies by swapping -allow-all.json -> -freeze.json
    #      in the unlock_stack_policies commands above.
    #   2. Re-enable termination protection (swap --no-enable-termination-protection
    #      for --enable-termination-protection in the loop above).
    #   3. Recompute all manifest hashes (scripts/hash_dist.sh + scripts/hash_synth_assets.sh
    #      + sha256sum on lockfiles).
    #   4. Commit the updated FREEZE-MANIFEST.md and cut a new annotated tag (demo-v2.0.1).
    # Full ceremony re-run is DEMO-RUNBOOK.md section 7 steps 2-7.
```

---

## References

- **Ceremony runbook:** `.planning/milestones/v1.0-phases/05-demo-hardening/DEMO-RUNBOOK.md`
  section 7 (T-48h Freeze Ceremony) — the 7-step sequence that populates every
  `<pending>` field above.
- **Drill evidence log:** `.planning/phases/10-freeze-rollback-drill/10-DRILL-LOG.md` —
  rollback drill outcomes for the five drill steps; must be `PASS` overall before this
  manifest is finalised and the `demo-v2.0` tag is cut.
- **Stack-policy JSON bodies:** `infrastructure/stack-policies/*.json` — six files
  (three `-freeze.json` + three `-allow-all.json`) committed in plan 10-01.
- **Content-manifest hashers:** `scripts/hash_dist.sh` + `scripts/hash_synth_assets.sh`
  committed in plan 10-01; empirically cross-rebuild stable per 10-01-SUMMARY.md.
- **Bedrock model source of truth:** `agent/agent.py:309` (`us.anthropic.claude-sonnet-4-6`).
